from decimal import Decimal

import pytest
from eth.codecs.abi.exceptions import ABIError

from boa.util.abi import abi_encode


def test_encode_int168_decimal_matches_scaled_int():
    value = Decimal("248.3805279542")
    result = abi_encode("int168", value)
    expected = abi_encode("int168", 2483805279542)
    assert result == expected


def test_encode_int168_decimal_negative():
    value = Decimal("-1.5")
    result = abi_encode("int168", value)
    expected = abi_encode("int168", -15000000000)
    assert result == expected


def test_encode_int168_decimal_precision_too_high():
    with pytest.raises(ABIError):
        abi_encode("int168", Decimal("1.00000000001"))
