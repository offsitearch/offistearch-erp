"""Unit tests for kernel money primitives (q) and currency formatting."""

from decimal import Decimal

from studioerp.currency import format_amount, inr_value
from studioerp.money import q


def test_q_quantizes_to_two_decimals():
    assert q("12.345") == Decimal("12.34")  # ROUND_HALF_EVEN on 2dp
    assert q(12) == Decimal("12.00")
    assert q("0") == Decimal("0.00")


def test_q_handles_none_and_zero():
    assert q(None) == Decimal("0.00")
    assert q(0) == Decimal("0.00")


def test_q_rejects_float_precision_trap():
    # 0.1 + 0.2 must not surface as 0.30000000000000004
    assert q(0.1 + 0.2) == Decimal("0.30")


def test_inr_symbol():
    from studioerp.currency import currency_symbol

    assert currency_symbol("INR") == "\u20b9"
    assert currency_symbol("usd") == "$"
    assert currency_symbol("JPY") == "\u00a5"
    assert currency_symbol("XYZ") == "XYZ "


def test_format_amount_none():
    assert format_amount(None) == "-----"


def test_inr_grouping_lakh_uses_western():
    # Reference behaviour: Indian regrouping only kicks in for amounts whose
    # leading western groups exceed 2 digits (>= 3-crore-ish). 2.5 lakh stays
    # western grouping. Behaviour = parity with the reference monolith.
    assert format_amount(Decimal("250000")) == "\u20b9250,000.00"


def test_inr_grouping_crore_regrouped():
    # 10 crore -> head "100,000,000" yields Indian grouping.
    from studioerp.currency import _inr_grouping

    assert _inr_grouping("100,000,000.00") == "1,00,000,000.00"


def test_inr_grouping_single_crore_stays_western():
    from studioerp.currency import _inr_grouping

    assert _inr_grouping("10,000,000.00") == "10,000,000.00"


def test_format_usd():
    assert format_amount(Decimal("1234.5"), code="USD") == "$1,234.50"


def test_inr_value_uses_rate():
    assert inr_value(Decimal("10"), Decimal("2")) == Decimal("20.00")


def test_inr_value_none_defaults_zero():
    assert inr_value(None, None) == Decimal("0")
