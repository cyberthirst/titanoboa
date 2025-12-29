"""
Tests for hex string support in ABI bytes encoding.

These tests verify that hex strings are correctly accepted and converted
for bytes and bytesN ABI types, including in arrays and tuples.
"""

import pytest
from eth.codecs.abi.exceptions import ABIError

import boa
from boa.util.abi import _hex_to_bytes, abi_decode, abi_encode, is_abi_encodable


# =============================================================================
# Unit tests for _hex_to_bytes helper
# =============================================================================


class TestHexToBytesHelper:
    """Tests for the _hex_to_bytes conversion function."""

    def test_basic_hex_conversion(self):
        """Test basic hex string to bytes conversion."""
        assert _hex_to_bytes("0x1234") == b"\x12\x34"
        assert _hex_to_bytes("0xabcdef") == b"\xab\xcd\xef"
        assert _hex_to_bytes("0xABCDEF") == b"\xab\xcd\xef"  # uppercase

    def test_empty_hex_string(self):
        """Test that '0x' converts to empty bytes."""
        assert _hex_to_bytes("0x") == b""

    def test_odd_length_hex_raises(self):
        """Test that odd-length hex strings raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _hex_to_bytes("0x1")
        assert "Invalid hex string" in str(exc_info.value)

        with pytest.raises(ValueError):
            _hex_to_bytes("0x123")

        with pytest.raises(ValueError):
            _hex_to_bytes("0xabc")

    def test_uppercase_prefix(self):
        """Test that 0X prefix (uppercase) is accepted."""
        assert _hex_to_bytes("0X1234") == b"\x12\x34"

    def test_size_validation_exact_match(self):
        """Test that exact size match passes validation."""
        result = _hex_to_bytes("0x12345678", expected_size=4)
        assert result == b"\x12\x34\x56\x78"
        assert len(result) == 4

    def test_size_validation_failure_too_short(self):
        """Test that too-short value raises clear error."""
        with pytest.raises(ValueError) as exc_info:
            _hex_to_bytes("0x1234", expected_size=8)
        assert "bytes8 expects 8 bytes, got 2" in str(exc_info.value)

    def test_size_validation_failure_too_long(self):
        """Test that too-long value raises clear error."""
        with pytest.raises(ValueError) as exc_info:
            _hex_to_bytes("0x" + "ab" * 10, expected_size=4)
        assert "bytes4 expects 4 bytes, got 10" in str(exc_info.value)

    def test_missing_0x_prefix_raises(self):
        """Test that missing 0x prefix raises clear error."""
        with pytest.raises(ValueError) as exc_info:
            _hex_to_bytes("1234")
        assert "must start with '0x'" in str(exc_info.value)

    def test_invalid_hex_chars_raises(self):
        """Test that invalid hex characters raise clear error."""
        with pytest.raises(ValueError) as exc_info:
            _hex_to_bytes("0x123g")
        assert "Invalid hex string" in str(exc_info.value)

    def test_non_string_raises_type_error(self):
        """Test that non-string input raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            _hex_to_bytes(1234)
        assert "Expected str, got int" in str(exc_info.value)


# =============================================================================
# Unit tests for ABI encoding with hex strings
# =============================================================================


class TestAbiEncodeDynamicBytes:
    """Tests for dynamic bytes ABI encoding with hex strings."""

    def test_encode_bytes_from_hex_string(self):
        """Test encoding dynamic bytes from hex string."""
        result = abi_encode("bytes", "0x1234")
        expected = abi_encode("bytes", b"\x12\x34")
        assert result == expected

    def test_encode_bytes_empty_hex(self):
        """Test encoding empty bytes from '0x'."""
        result = abi_encode("bytes", "0x")
        expected = abi_encode("bytes", b"")
        assert result == expected

    def test_encode_bytes_long_hex(self):
        """Test encoding long bytes from hex string."""
        hex_str = "0x" + "ab" * 100
        result = abi_encode("bytes", hex_str)
        expected = abi_encode("bytes", bytes.fromhex("ab" * 100))
        assert result == expected

    def test_existing_bytes_behavior_unchanged(self):
        """Test that existing bytes behavior is unchanged."""
        # bytes input still works
        result = abi_encode("bytes", b"\x12\x34")
        # Verify it encodes correctly
        decoded = abi_decode("bytes", result)
        assert decoded == b"\x12\x34"

    def test_encode_bytes_odd_length_hex_raises(self):
        """Test encoding bytes with odd-length hex raises."""
        with pytest.raises(ABIError) as exc_info:
            abi_encode("bytes", "0x1")
        assert "Invalid hex string" in str(exc_info.value)


class TestAbiEncodeFixedBytesM:
    """Tests for fixed-size bytesM ABI encoding with hex strings."""

    def test_encode_bytes4(self):
        """Test encoding bytes4 from hex string."""
        result = abi_encode("bytes4", "0x01abcdef")
        expected = abi_encode("bytes4", b"\x01\xab\xcd\xef")
        assert result == expected

    def test_encode_bytes32(self):
        """Test encoding bytes32 from hex string."""
        hex_str = "0x" + "ff" * 32
        result = abi_encode("bytes32", hex_str)
        expected = abi_encode("bytes32", b"\xff" * 32)
        assert result == expected

    def test_encode_bytes1(self):
        """Test encoding bytes1 from hex string."""
        result = abi_encode("bytes1", "0xab")
        expected = abi_encode("bytes1", b"\xab")
        assert result == expected

    def test_bytes4_wrong_length_raises(self):
        """Test that wrong length for bytes4 raises ABIError."""
        with pytest.raises(ABIError) as exc_info:
            abi_encode("bytes4", "0x1234")  # only 2 bytes
        assert "bytes4 expects 4 bytes, got 2" in str(exc_info.value)

    def test_bytes32_wrong_length_raises(self):
        """Test that wrong length for bytes32 raises ABIError."""
        with pytest.raises(ABIError) as exc_info:
            abi_encode("bytes32", "0x1234")
        assert "bytes32 expects 32 bytes, got 2" in str(exc_info.value)

    def test_existing_bytes_behavior_unchanged(self):
        """Test that existing bytes input behavior is unchanged."""
        result = abi_encode("bytes4", b"\x01\x02\x03\x04")
        # Verify it encodes correctly (right-padded to 32 bytes)
        assert len(result) == 32
        assert result[:4] == b"\x01\x02\x03\x04"


class TestAbiEncodeBytesArrays:
    """Tests for bytes array ABI encoding with hex strings."""

    def test_encode_bytes32_dynamic_array(self):
        """Test encoding bytes32[] with hex strings."""
        hex_vals = ["0x" + "ab" * 32, "0x" + "cd" * 32]
        result = abi_encode("bytes32[]", hex_vals)
        expected = abi_encode("bytes32[]", [b"\xab" * 32, b"\xcd" * 32])
        assert result == expected

    def test_encode_bytes_dynamic_array(self):
        """Test encoding bytes[] (dynamic bytes array) with hex strings."""
        hex_vals = ["0x1234", "0xabcdef", "0x"]
        result = abi_encode("bytes[]", hex_vals)
        expected = abi_encode("bytes[]", [b"\x12\x34", b"\xab\xcd\xef", b""])
        assert result == expected

    def test_encode_bytes4_static_array(self):
        """Test encoding bytes4[3] (static array) with hex strings."""
        hex_vals = ["0x11223344", "0x55667788", "0x99aabbcc"]
        result = abi_encode("bytes4[3]", hex_vals)
        expected = abi_encode(
            "bytes4[3]", [b"\x11\x22\x33\x44", b"\x55\x66\x77\x88", b"\x99\xaa\xbb\xcc"]
        )
        assert result == expected

    def test_encode_nested_bytes_array(self):
        """Test encoding bytes32[][] (nested array) with hex strings."""
        hex_vals = [["0x" + "11" * 32], ["0x" + "22" * 32, "0x" + "33" * 32]]
        result = abi_encode("bytes32[][]", hex_vals)
        expected = abi_encode("bytes32[][]", [[b"\x11" * 32], [b"\x22" * 32, b"\x33" * 32]])
        assert result == expected

    def test_mixed_hex_and_bytes_in_array(self):
        """Test encoding array with mix of hex strings and bytes."""
        mixed_vals = ["0x" + "ab" * 32, b"\xcd" * 32]
        result = abi_encode("bytes32[]", mixed_vals)
        expected = abi_encode("bytes32[]", [b"\xab" * 32, b"\xcd" * 32])
        assert result == expected


class TestAbiEncodeTuples:
    """Tests for tuple ABI encoding with hex strings in bytes components."""

    def test_encode_tuple_with_bytes_and_bytes32(self):
        """Test encoding (bytes,bytes32) tuple with hex strings."""
        result = abi_encode("(bytes,bytes32)", ["0x1234", "0x" + "ff" * 32])
        expected = abi_encode("(bytes,bytes32)", [b"\x12\x34", b"\xff" * 32])
        assert result == expected

    def test_encode_tuple_with_mixed_types(self):
        """Test encoding tuple with bytes among other types."""
        result = abi_encode("(uint256,bytes4,address)", [123, "0xdeadbeef", "0x" + "11" * 20])
        expected = abi_encode(
            "(uint256,bytes4,address)", [123, b"\xde\xad\xbe\xef", "0x" + "11" * 20]
        )
        assert result == expected

    def test_encode_nested_tuple_with_bytes(self):
        """Test encoding nested tuple with bytes."""
        result = abi_encode(
            "((bytes4,uint256),bytes)", [["0x12345678", 100], "0xabcd"]
        )
        expected = abi_encode(
            "((bytes4,uint256),bytes)", [[b"\x12\x34\x56\x78", 100], b"\xab\xcd"]
        )
        assert result == expected

    def test_encode_tuple_with_bytes_array(self):
        """Test encoding tuple containing bytes array."""
        result = abi_encode(
            "(bytes32[],uint256)", [["0x" + "aa" * 32, "0x" + "bb" * 32], 42]
        )
        expected = abi_encode("(bytes32[],uint256)", [[b"\xaa" * 32, b"\xbb" * 32], 42])
        assert result == expected


class TestIsAbiEncodable:
    """Tests for is_abi_encodable with hex strings."""

    def test_hex_string_is_encodable_as_bytes(self):
        """Test that hex strings are recognized as encodable for bytes."""
        assert is_abi_encodable("bytes", "0x1234") is True

    def test_hex_string_is_encodable_as_bytes32_correct_length(self):
        """Test that correct-length hex is encodable for bytes32."""
        assert is_abi_encodable("bytes32", "0x" + "ab" * 32) is True

    def test_hex_string_not_encodable_as_bytes32_wrong_length(self):
        """Test that wrong-length hex is not encodable for bytes32."""
        assert is_abi_encodable("bytes32", "0x1234") is False

    def test_invalid_hex_not_encodable(self):
        """Test that invalid hex is not encodable."""
        assert is_abi_encodable("bytes", "0xGGGG") is False

    def test_non_prefixed_string_not_encodable(self):
        """Test that string without 0x prefix is not encodable as bytes."""
        assert is_abi_encodable("bytes", "1234") is False


# =============================================================================
# Integration tests with Vyper contracts
# =============================================================================


class TestVyperContractBytesM:
    """Integration tests for bytesM types with hex string inputs."""

    def test_bytes4_function_arg(self):
        """Test passing hex string as bytes4 function argument."""
        src = """
@external
def check_bytes4(x: bytes4) -> bytes4:
    return x
        """
        c = boa.loads(src)
        result = c.check_bytes4("0xdeadbeef")
        assert result == b"\xde\xad\xbe\xef"

    def test_bytes32_function_arg(self):
        """Test passing hex string as bytes32 function argument."""
        src = """
@external
def check_bytes32(x: bytes32) -> bytes32:
    return x
        """
        c = boa.loads(src)
        hex_val = "0x" + "ab" * 32
        result = c.check_bytes32(hex_val)
        assert result == b"\xab" * 32

    def test_bytes1_function_arg(self):
        """Test passing hex string as bytes1 function argument."""
        src = """
@external
def check_bytes1(x: bytes1) -> bytes1:
    return x
        """
        c = boa.loads(src)
        result = c.check_bytes1("0xff")
        assert result == b"\xff"

    def test_bytes4_wrong_length_raises(self):
        """Test that wrong-length hex for bytes4 raises error."""
        src = """
@external
def check_bytes4(x: bytes4) -> bytes4:
    return x
        """
        c = boa.loads(src)
        with pytest.raises(ABIError) as exc_info:
            c.check_bytes4("0x1234")  # only 2 bytes
        assert "bytes4 expects 4 bytes" in str(exc_info.value)

    def test_bytes4_in_struct(self):
        """Test hex string for bytes4 in struct argument."""
        src = """
struct MyStruct:
    id: bytes4
    value: uint256

@external
def check_struct(s: MyStruct) -> bytes4:
    return s.id
        """
        c = boa.loads(src)
        result = c.check_struct(["0xdeadbeef", 100])
        assert result == b"\xde\xad\xbe\xef"


class TestVyperContractDynamicBytes:
    """Integration tests for dynamic Bytes types with hex string inputs."""

    def test_bytes_function_arg(self):
        """Test passing hex string as Bytes[N] function argument."""
        src = """
@external
def check_bytes(x: Bytes[100]) -> Bytes[100]:
    return x
        """
        c = boa.loads(src)
        result = c.check_bytes("0x1234abcd")
        assert result == b"\x12\x34\xab\xcd"

    def test_bytes_empty(self):
        """Test passing empty hex string as Bytes argument."""
        src = """
@external
def check_bytes(x: Bytes[100]) -> uint256:
    return len(x)
        """
        c = boa.loads(src)
        result = c.check_bytes("0x")
        assert result == 0

    def test_bytes_long_value(self):
        """Test passing long hex string as Bytes argument."""
        src = """
@external
def check_bytes(x: Bytes[200]) -> uint256:
    return len(x)
        """
        c = boa.loads(src)
        hex_val = "0x" + "ab" * 100
        result = c.check_bytes(hex_val)
        assert result == 100

    def test_bytes_existing_behavior_unchanged(self):
        """Test that existing bytes literal behavior is unchanged."""
        src = """
@external
def check_bytes(x: Bytes[100]) -> Bytes[100]:
    return x
        """
        c = boa.loads(src)
        # Test with regular bytes
        result = c.check_bytes(b"\x12\x34")
        assert result == b"\x12\x34"


class TestVyperContractBytesArrays:
    """Integration tests for bytes array types with hex string inputs."""

    def test_bytes32_dynamic_array_arg(self):
        """Test passing hex strings in bytes32 dynamic array argument."""
        src = """
@external
def check_array(x: DynArray[bytes32, 10]) -> bytes32:
    return x[0]
        """
        c = boa.loads(src)
        result = c.check_array(["0x" + "ff" * 32, "0x" + "00" * 32])
        assert result == b"\xff" * 32

    def test_bytes4_static_array_arg(self):
        """Test passing hex strings in bytes4 static array argument."""
        src = """
@external
def check_array(x: bytes4[3]) -> bytes4:
    return x[1]
        """
        c = boa.loads(src)
        result = c.check_array(["0x11111111", "0x22222222", "0x33333333"])
        assert result == b"\x22\x22\x22\x22"

    def test_dynamic_bytes_array_arg(self):
        """Test passing hex strings in dynamic Bytes array argument."""
        src = """
@external
def check_array(x: DynArray[Bytes[32], 10]) -> Bytes[32]:
    return x[0]
        """
        c = boa.loads(src)
        result = c.check_array(["0xabcd", "0x1234"])
        assert result == b"\xab\xcd"


class TestVyperContractConstructorBytes:
    """Integration tests for bytes in constructor arguments."""

    def test_bytes32_constructor_arg(self):
        """Test passing hex string as bytes32 constructor argument."""
        src = """
hash: bytes32

@deploy
def __init__(h: bytes32):
    self.hash = h

@external
def get_hash() -> bytes32:
    return self.hash
        """
        c = boa.loads(src, "0x" + "ab" * 32)
        assert c.get_hash() == b"\xab" * 32

    def test_bytes4_constructor_arg(self):
        """Test passing hex string as bytes4 constructor argument."""
        src = """
selector: bytes4

@deploy
def __init__(m: bytes4):
    self.selector = m

@external
def get_selector() -> bytes4:
    return self.selector
        """
        c = boa.loads(src, "0xdeadbeef")
        assert c.get_selector() == b"\xde\xad\xbe\xef"

    def test_dynamic_bytes_constructor_arg(self):
        """Test passing hex string as Bytes[N] constructor argument."""
        src = """
data: Bytes[100]

@deploy
def __init__(d: Bytes[100]):
    self.data = d

@external
def get_data() -> Bytes[100]:
    return self.data
        """
        c = boa.loads(src, "0x1234567890")
        assert c.get_data() == b"\x12\x34\x56\x78\x90"


class TestVyperContractMixedTypes:
    """Integration tests for mixed bytes types in function signatures."""

    def test_multiple_bytes_args(self):
        """Test function with multiple bytes arguments."""
        src = """
@external
def check_multi(a: bytes4, b: Bytes[32], c: bytes32) -> bool:
    return True
        """
        c = boa.loads(src)
        result = c.check_multi("0xdeadbeef", "0x1234", "0x" + "ff" * 32)
        assert result is True

    def test_bytes_in_complex_struct(self):
        """Test bytes types in complex struct."""
        src = """
struct Config:
    version: bytes4
    data: Bytes[64]
    hash: bytes32

@external
def process_config(cfg: Config) -> bytes4:
    return cfg.version
        """
        c = boa.loads(src)
        config = ["0x01020304", "0xabcdef", "0x" + "99" * 32]
        result = c.process_config(config)
        assert result == b"\x01\x02\x03\x04"


class TestEdgeCases:
    """Edge case tests for hex string bytes encoding."""

    def test_hex_string_with_leading_zeros(self):
        """Test hex string with leading zeros is preserved."""
        src = """
@external
def check_bytes(x: bytes4) -> bytes4:
    return x
        """
        c = boa.loads(src)
        result = c.check_bytes("0x00001234")
        assert result == b"\x00\x00\x12\x34"

    def test_all_zeros_bytes32(self):
        """Test all-zeros bytes32."""
        src = """
@external
def check_bytes(x: bytes32) -> bytes32:
    return x
        """
        c = boa.loads(src)
        result = c.check_bytes("0x" + "00" * 32)
        assert result == b"\x00" * 32

    def test_all_ff_bytes32(self):
        """Test all-0xff bytes32."""
        src = """
@external
def check_bytes(x: bytes32) -> bytes32:
    return x
        """
        c = boa.loads(src)
        result = c.check_bytes("0x" + "ff" * 32)
        assert result == b"\xff" * 32

    def test_odd_hex_length_raises(self):
        """Test odd-length hex string raises ABIError."""
        src = """
@external
def check_bytes(x: Bytes[10]) -> Bytes[10]:
    return x
        """
        c = boa.loads(src)
        with pytest.raises(ABIError) as exc_info:
            c.check_bytes("0x1")
        assert "Invalid hex string" in str(exc_info.value)

    def test_case_insensitive_hex(self):
        """Test that hex characters are case-insensitive."""
        src = """
@external
def check_bytes(x: bytes4) -> bytes4:
    return x
        """
        c = boa.loads(src)
        result_lower = c.check_bytes("0xabcdef01")
        result_upper = c.check_bytes("0xABCDEF01")
        result_mixed = c.check_bytes("0xAbCdEf01")
        assert result_lower == result_upper == result_mixed
