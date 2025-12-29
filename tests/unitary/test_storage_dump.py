"""
Tests for storage dump functionality.

These tests verify that storage dump correctly captures various storage types.
"""

import pytest

import boa


def _get_storage_dump(contract):
    """Helper to get storage dump from a contract."""
    return contract._storage.dump()


def test_storage_array_assign():
    """Test DynArray storage and dump."""
    src = """
a: DynArray[uint256, 10]

@external
def foo() -> uint256:
    self.a = [1, 2]
    self.a[0] = 3
    return self.a[0] + self.a[1]
    """

    c = boa.loads(src)
    assert c.foo() == 5

    dump = _get_storage_dump(c)
    assert dump["a"] == [3, 2]


def test_storage_variables():
    """Test simple uint256 storage and dump."""
    src = """
d: uint256

@external
def foo() -> uint256:
    a: uint256 = 1
    self.d = a
    if a == 1:
        a = 2
    else:
        a = 3
    return self.d + 42
    """

    c = boa.loads(src)
    assert c.foo() == 43

    dump = _get_storage_dump(c)
    assert dump["d"] == 1


def test_storage_variables2():
    """Test multiple uint256 storage variables and dump."""
    src = """
d: uint256
k: uint256

@external
def foo() -> uint256:
    self.k = 1
    self.d = self.k
    self.d += self.k
    return self.d + self.k
    """

    c = boa.loads(src)
    assert c.foo() == 3

    dump = _get_storage_dump(c)
    assert dump["d"] == 2
    assert dump["k"] == 1


def test_storage_variables3():
    """Test storage modified by internal function and dump."""
    src = """
d: uint256

@internal
def bar():
    a: DynArray[uint256, 10] = [1, 2, 3]
    for i: uint256 in a:
        self.d += i


@external
def foo() -> uint256:
    a: DynArray[uint256, 10] = [1, 2, 3]
    counter: uint256 = 0
    for i: uint256 in a:
        self.d += i
    self.bar()
    return self.d
    """
    c = boa.loads(src)
    assert c.foo() == 12

    dump = _get_storage_dump(c)
    assert dump["d"] == 12


def test_statefulness_of_storage():
    """Test storage persists across calls and dump reflects latest state."""
    src = """
d: uint256

@external
def foo() -> uint256:
    self.d += 1
    return self.d
    """

    c = boa.loads(src)
    for i in range(5):
        assert c.foo() == i + 1

    dump = _get_storage_dump(c)
    assert dump["d"] == 5


def test_range_builtin():
    """Test storage with range loop and dump."""
    src = """
a: uint256

@external
def foo() -> uint256:
    for i: uint256 in range(10):
        self.a += i
    return self.a
    """

    c = boa.loads(src)
    expected = sum(range(10))
    assert c.foo() == expected

    dump = _get_storage_dump(c)
    assert dump["a"] == expected


def test_len_builtin_dynarray():
    """Test DynArray storage with len and dump."""
    src = """
d: DynArray[uint256, 3]

@external
def foo() -> uint256:
    return len(self.d)

@external
def set_array():
    self.d = [1, 2, 3]
    """
    c = boa.loads(src)
    assert c.foo() == 0

    c.set_array()
    assert c.foo() == 3

    dump = _get_storage_dump(c)
    assert dump["d"] == [1, 2, 3]


def test_len_builtin_string():
    """Test String storage and dump."""
    src = """
s: String[10]

@external
def foo() -> uint256:
    self.s = "hello"
    return len(self.s)
    """
    c = boa.loads(src)
    assert c.foo() == 5

    dump = _get_storage_dump(c)
    assert dump["s"] == "hello"


def test_len_builtin_bytes():
    """Test Bytes storage and dump."""
    src = """
s: Bytes[10]

@external
def foo() -> uint256:
    self.s = b"hello"
    return len(self.s)
    """
    c = boa.loads(src)
    assert c.foo() == 5

    dump = _get_storage_dump(c)
    assert dump["s"] == b"hello"


def test_hash_map():
    """Test HashMap storage and dump."""
    src = """
var: HashMap[uint256, uint256]

@external
def foo() -> uint256:
    self.var[0] = 42
    return self.var[0] + self.var[1]
    """

    c = boa.loads(src)
    assert c.foo() == 42

    dump = _get_storage_dump(c)
    assert dump["var"] == {0: 42}


def test_hash_map_multiple_keys():
    """Test HashMap with multiple keys and dump."""
    src = """
var: HashMap[uint256, uint256]

@external
def set_values():
    self.var[0] = 10
    self.var[1] = 20
    self.var[5] = 50
    """

    c = boa.loads(src)
    c.set_values()

    dump = _get_storage_dump(c)
    assert dump["var"] == {0: 10, 1: 20, 5: 50}


def test_struct_storage():
    """Test struct storage and dump."""
    src = """
struct S:
    a: uint256
    b: uint256

s: S

@external
def foo() -> uint256:
    self.s = S(a=1, b=2)
    self.s.a = 3
    return self.s.a + self.s.b
    """

    c = boa.loads(src)
    assert c.foo() == 5

    dump = _get_storage_dump(c)
    assert dump["s"]["a"] == 3
    assert dump["s"]["b"] == 2


def test_struct_with_dynarray():
    """Test struct with DynArray member and dump."""
    src = """
struct S:
    a: uint256
    b: DynArray[uint256, 3]

v: S

@external
def foo():
    self.v = S(a=1, b=[2, 3, 4])
    """

    c = boa.loads(src)
    c.foo()

    dump = _get_storage_dump(c)
    assert dump["v"]["a"] == 1
    assert dump["v"]["b"] == [2, 3, 4]


def test_dynarray_of_structs():
    """Test DynArray of structs and dump."""
    src = """
struct S:
    a: uint256
    b: uint256

d: DynArray[S, 3]

@external
def foo() -> uint256:
    self.d = [S(a=0, b=1), S(a=2, b=3), S(a=4, b=5)]

    acc: uint256 = 0
    for s: S in self.d:
        acc += s.a + s.b
    return acc
    """

    c = boa.loads(src)
    expected = 1 + 2 + 3 + 4 + 5
    assert c.foo() == expected

    dump = _get_storage_dump(c)
    assert len(dump["d"]) == 3
    assert dump["d"][0]["a"] == 0
    assert dump["d"][0]["b"] == 1
    assert dump["d"][1]["a"] == 2
    assert dump["d"][1]["b"] == 3
    assert dump["d"][2]["a"] == 4
    assert dump["d"][2]["b"] == 5


def test_static_array():
    """Test static array storage and dump."""
    src = """
a: uint256[3]

@external
def foo() -> uint256[3]:
    self.a[0] = 1
    self.a[1] = 2
    return self.a
    """

    c = boa.loads(src)
    res = c.foo()
    assert res == [1, 2, 0]

    dump = _get_storage_dump(c)
    assert dump["a"] == [1, 2, 0]


def test_nested_dynarray():
    """Test nested DynArray and dump."""
    src = """
d: DynArray[DynArray[uint256, 3], 3]

@external
def foo():
    self.d = [[1], [2, 3, 4], [5, 6]]
    """

    c = boa.loads(src)
    c.foo()

    dump = _get_storage_dump(c)
    assert dump["d"] == [[1], [2, 3, 4], [5, 6]]


def test_hashmap_string_value():
    """Test HashMap with String values and dump."""
    src = """
h: HashMap[uint256, String[32]]

@external
def foo():
    for i: uint8 in range(3):
        self.h[convert(i, uint256)] = uint2str(i)
    """

    c = boa.loads(src)
    c.foo()

    dump = _get_storage_dump(c)
    assert dump["h"] == {0: "0", 1: "1", 2: "2"}


def test_bytes_m():
    """Test bytesM types and dump."""
    src = """
bm: bytes2
bytesm_list: bytes1[1]

@external
def foo():
    self.bm = 0x1234
    self.bytesm_list[0] = 0xab
    """

    c = boa.loads(src)
    c.foo()

    dump = _get_storage_dump(c)
    assert dump["bm"] == b"\x12\x34"
    assert dump["bytesm_list"] == [b"\xab"]


def test_complex_storage_dump():
    """Test complex contract with multiple storage types and dump."""
    src = """
i: uint256
k: String[32]
j: Bytes[10]
s: uint256[3]
d: DynArray[DynArray[uint256, 3], 3]
h: HashMap[uint256, String[32]]

struct S:
    a: uint256
    b: DynArray[uint256, 3]

v: S

@external
def foo():
    self.i = 1
    self.k = "hello"
    self.j = b"hello"
    self.s[0] = 1
    self.s[1] = 2
    self.d = [[1], [2, 3, 4], [5, 6]]
    for n: uint8 in range(3):
        self.h[convert(n, uint256)] = uint2str(n)
    self.v = S(a=1, b=self.d[1])
    """

    c = boa.loads(src)
    c.foo()

    dump = _get_storage_dump(c)
    assert dump["i"] == 1
    assert dump["k"] == "hello"
    assert dump["j"] == b"hello"
    assert dump["s"] == [1, 2, 0]
    assert dump["d"] == [[1], [2, 3, 4], [5, 6]]
    assert dump["h"] == {0: "0", 1: "1", 2: "2"}
    assert dump["v"]["a"] == 1
    assert dump["v"]["b"] == [2, 3, 4]


def test_darray_append():
    """Test DynArray append and dump."""
    src = """
a: DynArray[uint256, 10]

@external
def foo() -> uint256:
    self.a = []
    self.a.append(1)
    return self.a[0]
    """

    c = boa.loads(src)
    assert c.foo() == 1

    dump = _get_storage_dump(c)
    assert dump["a"] == [1]


def test_darray_pop():
    """Test DynArray pop and dump."""
    src = """
a: DynArray[uint256, 10]

@external
def foo() -> uint256:
    self.a = [1, 2, 3]
    return self.a.pop()
    """

    c = boa.loads(src)
    assert c.foo() == 3

    dump = _get_storage_dump(c)
    assert dump["a"] == [1, 2]


def test_internal_call_modifies_storage():
    """Test internal call modifying storage and dump."""
    src = """
a: uint256

@internal
def bar():
    self.a = 42

@external
def foo() -> uint256:
    self.bar()
    return self.a
    """
    c = boa.loads(src)
    assert c.foo() == 42

    dump = _get_storage_dump(c)
    assert dump["a"] == 42


def test_self_call_modifies_storage():
    """Test self call modifying storage and dump."""
    src = """
interface Foo:
    def bar() -> String[32]: payable

a: uint256

@external
def bar() -> String[32]:
    self.a += 42
    return "hello"

@external
def foo() -> uint256:
    self.a = 10
    s: String[32] = extcall Foo(self).bar()
    return self.a
    """

    c = boa.loads(src)
    assert c.foo() == 52

    dump = _get_storage_dump(c)
    assert dump["a"] == 52


def test_hashmap_with_struct_value():
    """Test HashMap with struct values and dump."""
    src = """
struct Data:
    x: uint256
    y: uint256

m: HashMap[uint256, Data]

@external
def foo():
    self.m[0] = Data(x=10, y=20)
    self.m[1] = Data(x=30, y=40)
    """

    c = boa.loads(src)
    c.foo()

    dump = _get_storage_dump(c)
    assert dump["m"][0]["x"] == 10
    assert dump["m"][0]["y"] == 20
    assert dump["m"][1]["x"] == 30
    assert dump["m"][1]["y"] == 40


def test_hashmap_nested():
    """Test nested HashMap and dump."""
    src = """
m: HashMap[uint256, HashMap[uint256, uint256]]

@external
def foo():
    self.m[0][0] = 100
    self.m[0][1] = 200
    self.m[1][0] = 300
    """

    c = boa.loads(src)
    c.foo()

    dump = _get_storage_dump(c)
    assert dump["m"][0][0] == 100
    assert dump["m"][0][1] == 200
    assert dump["m"][1][0] == 300


def test_default_storage_values_dump():
    """Test that default storage values are captured in dump."""
    src = """
struct S:
    a: uint256

a: uint256
b: uint256
c: DynArray[uint256, 10]
d: S
e: Bytes[10]
f: String[10]

@external
def foo() -> uint256:
    assert self.a == 0
    assert self.b == 0
    assert len(self.c) == 0
    assert self.d.a == 0
    assert len(self.e) == 0
    assert len(self.f) == 0
    return 1
    """

    c = boa.loads(src)
    assert c.foo() == 1

    dump = _get_storage_dump(c)
    assert dump["a"] == 0
    assert dump["b"] == 0
    assert dump["c"] == []
    assert dump["d"]["a"] == 0
    assert dump["e"] == b""
    assert dump["f"] == ""


def test_interface_storage():
    """Test interface stored in storage and dump."""
    src = """
interface Foo:
    def bar() -> uint256: payable
    def foobar() -> uint256: view

i: Foo

@external
def bar() -> uint256:
    return 1

@external
def foobar() -> uint256:
    return 2

@external
def foo() -> uint256:
    a: uint256 = 0
    self.i = Foo(self)
    a = extcall self.i.bar()
    a += staticcall self.i.foobar()
    return a
    """

    c = boa.loads(src)
    assert c.foo() == 3

    dump = _get_storage_dump(c)
    # Interface storage is stored as address
    assert dump["i"] == c.address


def test_bug1_struct_field_offset():
    """
    Bug #1: HashMap[K, Struct] entries disappear when only a non-first field is written.

    When you write to map[key].f where 'f' is not the first field, the SSTORE
    records slot = base_hash + offset, but sha3_trace only contains base_hash.
    The lookup fails and the entry is completely lost from storage dump.
    """
    src = """
struct Foo:
    a: uint256  # offset 0
    b: uint256  # offset 1
    c: uint256  # offset 2
    d: uint256  # offset 3
    e: uint256  # offset 4
    f: uint256  # offset 5

w: HashMap[uint256, Foo]

@external
def set_first_field_only():
    self.w[1].a = 100

@external
def set_last_field_only():
    self.w[2].f = 750

@external
def set_both_fields():
    self.w[3].a = 100
    self.w[3].f = 750
"""

    contract = boa.loads(src)

    contract.set_first_field_only()
    contract.set_last_field_only()
    contract.set_both_fields()

    dump = _get_storage_dump(contract)

    # Key 1: only first field set
    assert dump["w"][1]["a"] == 100

    # Key 2: only last field set (this is the bug - entry may be missing)
    assert dump["w"][2]["a"] == 0
    assert dump["w"][2]["f"] == 750

    # Key 3: both fields set
    assert dump["w"][3]["a"] == 100
    assert dump["w"][3]["f"] == 750


def test_hashmap_static_array_value_offset():
    """Test HashMap with static array value where non-zero index is written."""
    src = """
w: HashMap[uint256, uint256[10]]

@external
def set_fifth():
    self.w[1][5] = 999
"""
    contract = boa.loads(src)
    contract.set_fifth()

    dump = _get_storage_dump(contract)
    assert dump["w"][1][5] == 999


def test_bug2_string_key_double_hash():
    """
    Bug #2: HashMap[String, V] keys show as hashes instead of original strings.

    For String/Bytes keys, Vyper computes:
      key_hash = keccak256(string_content)  <- NOT captured (size != 64)
      slot = keccak256(base_slot || key_hash)  <- captured

    The first hash is lost, so we can only recover key_hash, not the original string.
    """
    src = """
balances: HashMap[String[64], uint256]

@external
def set_balance(name: String[64], amount: uint256):
    self.balances[name] = amount
"""

    contract = boa.loads(src)

    contract.set_balance("alice", 1000)
    contract.set_balance("bob", 2000)

    dump = _get_storage_dump(contract)
    assert dump["balances"]["alice"] == 1000
    assert dump["balances"]["bob"] == 2000


def test_bug2_bytes_key_double_hash():
    """
    Same as bug #2 but with Bytes instead of String.
    """
    src = """
data: HashMap[Bytes[32], uint256]

@external
def set_data(key: Bytes[32], val: uint256):
    self.data[key] = val
"""

    contract = boa.loads(src)

    contract.set_data(b"mykey", 42)

    dump = _get_storage_dump(contract)
    assert dump["data"][b"mykey"] == 42


def test_hashmap_string_key_empty_and_max_length():
    """Test HashMap[String[N], V] key recovery for empty and max-length keys."""
    src = """
balances: HashMap[String[64], uint256]

@external
def set_balance(name: String[64], amount: uint256):
    self.balances[name] = amount
"""
    contract = boa.loads(src)

    contract.set_balance("", 1)
    contract.set_balance("a", 2)
    contract.set_balance("b" * 64, 3)

    dump = _get_storage_dump(contract)
    assert dump["balances"][""] == 1
    assert dump["balances"]["a"] == 2
    assert dump["balances"]["b" * 64] == 3


def test_hashmap_bytes_key_empty_nulls_and_full_length():
    """Test HashMap[Bytes[N], V] key recovery for empty/null/full-length keys."""
    src = """
data: HashMap[Bytes[32], uint256]

@external
def set_data(key: Bytes[32], val: uint256):
    self.data[key] = val
"""
    contract = boa.loads(src)

    contract.set_data(b"", 1)
    contract.set_data(b"\x00", 2)
    contract.set_data(b"a" * 31, 3)
    contract.set_data(b"a" * 32, 4)
    contract.set_data(b"\x00" * 32, 5)

    dump = _get_storage_dump(contract)
    assert dump["data"][b""] == 1
    assert dump["data"][b"\x00"] == 2
    assert dump["data"][b"a" * 31] == 3
    assert dump["data"][b"a" * 32] == 4
    assert dump["data"][b"\x00" * 32] == 5


def test_hashmap_struct_value_deep_slot_write_only():
    """Test HashMap value offset probing when only a deep struct slot is written."""
    src = """
struct Foo:
    a: uint256
    b: uint256[10]

w: HashMap[uint256, Foo]

@external
def set_deep():
    self.w[1].b[9] = 999
"""
    contract = boa.loads(src)
    contract.set_deep()

    dump = _get_storage_dump(contract)
    assert dump["w"][1]["a"] == 0
    assert dump["w"][1]["b"][9] == 999


def test_hashmap_nested_string_key_struct_value_offset():
    """Test nested HashMap with String key and struct value offset probing."""
    src = """
struct Foo:
    a: uint256
    b: uint256
    c: uint256

outer: HashMap[String[64], HashMap[uint256, Foo]]

@external
def set_c(name: String[64], k: uint256, val: uint256):
    self.outer[name][k].c = val
"""
    contract = boa.loads(src)
    contract.set_c("alice", 2, 7)
    contract.set_c("bob", 3, 9)

    dump = _get_storage_dump(contract)
    assert dump["outer"]["alice"][2]["a"] == 0
    assert dump["outer"]["alice"][2]["c"] == 7
    assert dump["outer"]["bob"][3]["c"] == 9


def test_hashmap_nested_bytes_key_static_array_value_offset():
    """Test nested HashMap with Bytes key and static array value offset probing."""
    src = """
outer: HashMap[Bytes[32], HashMap[uint256, uint256[10]]]

@external
def set_inner(key: Bytes[32], k: uint256):
    self.outer[key][k][5] = 999
"""
    contract = boa.loads(src)
    contract.set_inner(b"mykey", 1)

    dump = _get_storage_dump(contract)
    assert dump["outer"][b"mykey"][1][5] == 999


def test_fixed_size_list_assignment_and_index_update():
    """Test fixed-size list assignment plus single index update in storage dump."""
    src = """
exampleList: int128[3]

@external
def set_only_third():
    self.exampleList[2] = -1

@external
def set_list():
    self.exampleList = [10, 11, 12]
    self.exampleList[2] = 42
"""
    contract = boa.loads(src)

    contract.set_only_third()
    dump = _get_storage_dump(contract)
    assert dump["exampleList"] == [0, 0, -1]

    contract.set_list()
    dump = _get_storage_dump(contract)
    assert dump["exampleList"] == [10, 11, 42]


def test_hashmap_bytes_key_from_constructor():
    """
    Test that Bytes keys in HashMap are correctly captured in storage dump
    when set in constructor.
    """
    source = """
a: HashMap[Bytes[100], int128]

@deploy
def __init__():
    self.a[b"hello"] = 1069
"""
    contract = boa.loads(source)
    dump = _get_storage_dump(contract)
    assert b"hello" in dump.get("a", {}), f"Expected b'hello' key in dump, got: {dump}"
    assert dump["a"][b"hello"] == 1069


def test_hashmap_string_key_from_constructor():
    """
    Test that String keys in HashMap are correctly captured in storage dump
    when set in constructor.
    """
    source = """
a: HashMap[String[100], int128]

@deploy
def __init__():
    self.a["hello"] = 1069
"""
    contract = boa.loads(source)
    dump = _get_storage_dump(contract)
    assert "hello" in dump.get("a", {}), f"Expected 'hello' key in dump, got: {dump}"
    assert dump["a"]["hello"] == 1069


def test_hashmap_struct_late_fields_from_constructor():
    """
    Test that HashMap entries are captured when only non-first struct fields are set.

    Previously, entries were dropped when only late struct fields (not field 0) were set.
    """
    source = """
struct W:
    a: uint256
    f: uint256
    g: uint256

w: HashMap[int128, W]

@deploy
def __init__():
    self.w[1].a = 11
    self.w[3].f = 750
    self.w[3].g = 751
"""
    contract = boa.loads(source)
    dump = _get_storage_dump(contract)
    assert 1 in dump["w"], "w[1] should exist"
    assert 3 in dump["w"], "w[3] should exist (only f,g set)"
    assert dump["w"][1]["a"] == 11
    assert dump["w"][3]["f"] == 750
    assert dump["w"][3]["g"] == 751


def test_hashmap_struct_with_nested_array():
    """
    Test HashMap with struct containing nested static array.

    Tests that all keys are tracked when struct has nested array and
    different fields are written for different keys.
    """
    source = """
struct W:
    a: uint256
    e: int128[3][3]
    f: uint256

w: public(HashMap[int128, W])

@deploy
def __init__():
    self.w[1].a = 11
    self.w[2].e[1][2] = 17
    self.w[3].f = 750
"""
    contract = boa.loads(source)
    dump = _get_storage_dump(contract)
    assert 1 in dump["w"], "w[1] should exist"
    assert 2 in dump["w"], "w[2] should exist"
    assert 3 in dump["w"], "w[3] should exist"
    assert dump["w"][1]["a"] == 11
    assert dump["w"][2]["e"][1][2] == 17
    assert dump["w"][3]["f"] == 750


@pytest.mark.xfail(reason="venom codegen may not properly record SHA3 preimages for storage ops")
def test_hashmap_struct_with_nested_array_venom():
    """
    Test HashMap with struct containing nested static array using venom codegen.

    Venom codegen may not properly record SHA3 preimages for storage operations.
    """
    source = """
struct W:
    a: uint256
    e: int128[3][3]
    f: uint256

w: public(HashMap[int128, W])

@deploy
def __init__():
    self.w[1].a = 11
    self.w[2].e[1][2] = 17
    self.w[3].f = 750
"""
    contract = boa.loads(source, compiler_args={"experimental_codegen": True})
    dump = _get_storage_dump(contract)
    assert 1 in dump["w"], "w[1] should exist"
    assert 2 in dump["w"], "w[2] should exist"
    assert 3 in dump["w"], "w[3] should exist"
