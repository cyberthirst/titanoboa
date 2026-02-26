import boa


def _load(source: str):
    return boa.loads(source, compiler_args={"experimental_codegen": True})


def test_eval_with_experimental_codegen():
    contract = _load(
        """
x: public(uint256)

@external
def set_x(v: uint256):
    self.x = v
"""
    )
    contract.set_x(3)

    assert contract.eval("self.x") == 3
    contract.eval("self.x = 7")
    assert contract.x() == 7


def test_internal_wrappers_with_experimental_codegen():
    contract = _load(
        """
@internal
@pure
def _plus(x: uint256, y: uint256 = 2) -> uint256:
    return x + y
"""
    )

    assert contract.internal._plus(40) == 42
    assert contract.internal._plus(40, 3) == 43


def test_inject_with_experimental_codegen():
    contract = _load(
        """
total: public(uint256)
"""
    )

    contract.inject_function(
        """
@external
def mint(amt: uint256 = 1):
    self.total += amt
"""
    )

    contract.inject.mint(5)
    contract.inject.mint()
    assert contract.total() == 6
