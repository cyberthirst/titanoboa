from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Dict, List, Union
import re

from eth._utils.numeric import ceil32
from eth.exceptions import Revert

from vyper.evm.opcodes import OPCODES
import vyper.ir.optimizer

def debug(*args, **kwargs):
    pass

def _debug(*args, **kwargs):
    print(*args, **kwargs)

if False:
    debug = _debug

@dataclass
class OpcodeInfo:
    # model of an opcode from vyper.evm.opcodes

    opcode: int  # opcode number ex. 0x01 for ADD
    consumes: int  # number of stack items this consumes
    produces: int  # number of stack items this produces, must be 0 or 1
    _gas_estimate: int  # in vyper.evm.opcodes but not useful

    def __post_init__(self):
        assert self.produces in (0, 1)

    @classmethod
    def from_opcode_info(cls, opcode_info):
        # info from vyper.evm.opcodes
        opcode, consumes, produces, gas_estimate = opcode_info
        return cls(opcode, consumes, produces, gas_estimate)


@dataclass
class EvalContext:
    computation: Any  # ComputationAPI
    call_frames: List[Dict[str, int]] = field(default_factory=lambda: [{}])

    @property
    def local_vars(self):
        return self.call_frames[-1]

    def goto(self, compile_ctx, label, arglist):
        if label == "returnpc":  # i.e. exitsub
            return

        self.call_frames.append({})
        compile_ctx.labels[label].execute_subroutine(self, *arglist)
        self.call_frames.pop()


class IRBaseExecutor:
    def __init__(self, *args):
        self.args = args

    @property
    def name(self):
        return self._name

    def __repr__(self):
        ret = self.name + "("

        show = lambda s: s if isinstance(s, str) else hex(s) if isinstance(s, int) else repr(s)
        arg_reprs = [show(arg) for arg in self.args]
        arg_reprs = [x.replace("\n", "\n  ") for x in arg_reprs]
        ret += ",\n  ".join(arg_reprs)
        ret += ")"

        has_inner_newlines = any("\n" in t for t in arg_reprs)
        output_on_one_line = re.sub(r",\n *", ", ", ret).replace("\n", "")

        should_output_single_line = len(output_on_one_line) < 80 and not has_inner_newlines

        if should_output_single_line:
            return output_on_one_line
        else:
            return ret

    def eval(self, context):
        debug("ENTER", self.name)
        args = self._eval_args(context)
        return self._impl(context, *args)

    def _eval_args(self, context):
        ret = [_eval_single(arg, context) for arg in reversed(self.args)]
        ret.reverse()
        return ret


def _eval_single(arg, context):
    if isinstance(arg, str):
        return context.local_vars[arg]
    if isinstance(arg, int):
        return arg
    return arg.eval(context)

# an IR executor for evm opcodes which dispatches into py-evm
class DefaultIRExecutor(IRBaseExecutor):
    def __init__(self, name, opcode_impl, opcode_info, *args):
        self.opcode_impl = opcode_impl  # py-evm OpcodeAPI
        self.opcode_info: OpcodeInfo = opcode_info  # info from vyper.evm.opcodes
        self._name = "__" + name + "__"
        super().__init__(*args)

    @cached_property
    def produces(self):
        return self.opcode_info.produces

    def eval(self, context):
        debug("ENTER", self.name)
        evaled_args = self._eval_args(context)
        debug(self.name,"args.", evaled_args)
        computation = context.computation
        for arg in reversed(evaled_args):
            if isinstance(arg, int):
                computation.stack_push_int(arg)
            elif isinstance(arg, bytes):
                computation.stack_push_bytes(arg)
            #elif isinstance(arg, str) and arg.startswith("_sym_"):
            #    # it's a returnpc for a function
            #    pass
            else:
                raise RuntimeError(f"Not a stack item. {type(arg)} {arg}")

        self.opcode_impl.__call__(computation)

        if self.produces:
            return computation.stack_pop1_any()


_executors = {}

# decorator to register an executor class in the _executors dict.
def executor(cls):
    _executors[cls._name] = cls
    return cls

StackItem = Union[int, bytes]

def _to_int(stack_item: StackItem) -> int:
    if isinstance(stack_item, int):
        return stack_item
    return int.from_bytes(stack_item, "big")


def _to_bytes(stack_item: StackItem) -> bytes:
    if isinstance(stack_item, bytes):
        return stack_item
    return stack_item.to_bytes(32, "big")


def _wrap256(x):
    return x % 2**256


def _as_signed(x):
    return unsigned_to_signed(x, 256, strict=True)


@dataclass
class CompileContext:
    labels: Dict[str, IRBaseExecutor]


class IRExecutor(IRBaseExecutor):
    _sig = None

    def __init__(self, compile_ctx, *args):
        self.compile_ctx = compile_ctx
        super().__init__(*args)

    def eval(self, context):
        debug("ENTER", self.name)
        args = self._eval_args(context)
        if self.sig_mapper:
            assert len(args) == len(self.sig_mapper)
            args = (mapper(arg) for (mapper, arg) in zip(self.sig_mapper, args))
        ret = self._impl(context, *args)
        debug(f"({self.name} returning {ret})")
        return ret

    @cached_property
    def sig_mapper(self):
        return tuple(_to_int if typ is int else _to_bytes for typ in self._sig)


class UnsignedBinopExecutor(IRExecutor):
    _sig = (int, int)

    def _impl(self, context, x, y):
        return _wrap256(self._op(x, y))

class SignedBinopExecutor(UnsignedBinopExecutor):
    def _impl(self, x, y):
        debug("entered _impl.", self.name)
        x = unsigned_to_signed(x, 256, strict=True)
        y = unsigned_to_signed(y, 256, strict=True)
        return _wrap256(self._op(x, y))

# just use routines from vyper optimizer
for opname, (op, _, unsigned) in vyper.ir.optimizer.arith.items():
    base = UnsignedBinopExecutor if unsigned else SignedBinopExecutor
    _executors[opname] = type(opname.capitalize(), (base,), {"_op": op, "_name": opname})

@executor
class MLoad(IRExecutor):
    _name = "mload"
    _sig = (int,)

    def _impl(self, context, ptr):
        context.computation._memory.extend(ptr, 32)
        return context.computation._memory.read_bytes(ptr, 32)

@executor
class MStore(IRExecutor):
    _name = "mstore"
    _sig = (int,bytes)

    def _impl(self, context, ptr, val):
        context.computation._memory.extend(ptr, 32)
        context.computation._memory.write(ptr, 32, val)
 

@executor
class Ceil32(IRExecutor):
    _name = "ceil32"
    _sig = (int,int)

    def _impl(self, context, x):
        return eth._utils.numeric.ceil32(x)



#@executor
class DLoad(IRExecutor):
    _name = "dload"
    _sig = (int,)

    def _impl(self, context, ptr):
        raise RuntimeError("unimplemented")

#@executor
class DLoadBytes(IRExecutor):
    _name = "dloadbytes"
    sig = (int,int,int)
    def _impl(self, context, dst, src, size):
        raise RuntimeError("unimplemented")


@executor
class Pass(IRExecutor):
    _name = "pass"

    def eval(self, context):
        pass

@executor
class Seq(IRExecutor):
    _name = "seq"

    def eval(self, context):
        debug("ENTER", self.name)

        for arg in self.args:
            lastval = _eval_single(arg, context)
            debug(self.name,"evaled",lastval)

        return lastval

@executor
class Repeat(IRExecutor):
    _name = "repeat"

    def eval(self, context):
        debug("ENTER", self.name)

        i_name, start, rounds, rounds_bound, body = self.args

        start = _eval_single(start, context)
        rounds = _eval_single(rounds, context)
        assert rounds <= rounds_bound

        assert i_name not in context.local_vars

        for i in range(start, start + rounds):
            context.local_vars[i_name] = i
            body.eval(context)

        del context.local_vars[i_name]


@executor
class If(IRExecutor):
    _name = "if"

    # override `eval()` so we can get the correct lazy behavior
    def eval(self, context):
        debug("ENTER", self.name)
        try:
            test, body, orelse = self.args
        except ValueError:
            test, body = self.args
            orelse = None

        test = _to_int(_eval_single(test, context))
        if bool(test):
            return _eval_single(body, context)

        elif orelse is not None:
            return _eval_single(orelse, context)

        return


@executor
class Assert(IRExecutor):
    _name = "assert"
    _sig = (int,)

    def _impl(self, context, test):
        if not bool(test):
            context.computation.output = b""
            raise Revert(b"")

@executor
class VarList(IRExecutor):
    _name = "var_list"


@executor
class Goto(IRExecutor):
    _name = "goto"

    def get_label(self):
        label = self.args[0]
        if label.startswith("_sym_"):
            label = label[len("_sym_"):]
        return label

    def eval(self, context):
        debug("ENTER", self.name)
        label = self.get_label()
        args = reversed([_eval_single(arg, context) for arg in reversed(self.args[1:])])
        context.goto(self.compile_ctx, label, args)


@executor
class ExitTo(Goto):
    # exit_to and goto have pretty much the same semantics as far as we
    # are concerned here.
    _name = "exit_to"


@executor
class Label(IRExecutor):
    _name = "label"

    def __init__(self, compile_ctx, name, var_list, body):
        self.compile_ctx = compile_ctx
        self.var_list = var_list.args
        self.body = body
        self.labelname = name

        self.args = (name, var_list, body)

        compile_ctx.labels[name] = self

    def eval(self, context):
        debug("ENTER", self.name)
        pass

    def execute_subroutine(self, context, *args):
        assert len(args) == len(self.var_list), (self.labelname, [x for x in args], self.var_list)
        for varname, val in zip(self.var_list, args):
            context.local_vars[varname] = val

        self.body.eval(context)

@executor
class With(IRExecutor):
    _name = "with"

    def eval(self, context):
        debug("ENTER", self.name)
        varname, val, body = self.args

        val = _eval_single(val, context)

        backup = context.local_vars.get(varname)
        context.local_vars[varname] = val

        ret = body.eval(context)

        if backup is None:
            del context.local_vars[varname]
        else:
            context.local_vars[varname] = backup

        return ret

def executor_from_ir(ir_node, opcode_impls: Dict[int, Any], compile_ctx = None) -> Any:
    instr = ir_node.value
    if isinstance(instr, int):
        return instr

    if compile_ctx is None:
        compile_ctx = CompileContext({})

    args = (executor_from_ir(arg, opcode_impls, compile_ctx) for arg in ir_node.args)

    if instr in _executors:
        return _executors[instr](compile_ctx, *args)

    if instr.upper() in OPCODES:
        opcode_info = OpcodeInfo.from_opcode_info(OPCODES[instr.upper()])
        opcode_impl = opcode_impls[opcode_info.opcode]
        return DefaultIRExecutor(instr, opcode_impl, opcode_info, *args)

    assert len(ir_node.args) == 0, ir_node
    return ir_node.value