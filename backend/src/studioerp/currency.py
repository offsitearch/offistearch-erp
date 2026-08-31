"""Currency formatting and INR conversion helpers (kernel k0)."""

from __future__ import annotations

from decimal import Decimal

_CURRENCY_SYMBOLS: dict[str, str] = {
    "INR": "\u20b9",   # ₹
    "USD": "$",
    "EUR": "\u20ac",   # €
    "GBP": "\u00a3",   # £
    "JPY": "\u00a5",   # ¥
    "AED": "AED ",
    "SAR": "SAR ",
    "CAD": "C$",
    "AUD": "A$",
    "SGD": "S$",
}

_ZERO_DECIMAL = {"JPY"}


def currency_symbol(code: str) -> str:
    """Return the symbol for a currency code (defaults to code + space)."""
    code = (code or "INR").upper()
    return _CURRENCY_SYMBOLS.get(code, f"{code} ")


def format_amount(amount: Decimal | float | int | None, code: str = "INR", symbol: bool = True) -> str:
    """Format an amount with the currency's symbol, preserving Indian grouping for INR."""
    if amount is None:
        return "-----"
    code = (code or "INR").upper()
    value = float(amount)
    if code in _ZERO_DECIMAL:
        digits = f"{value:,.0f}"
    else:
        digits = f"{value:,.2f}"
    if code == "INR":
        digits = _inr_grouping(digits)
    return f"{currency_symbol(code)}{digits}" if symbol else digits


def _inr_grouping(comma_digits: str) -> str:
    """Re-group a western-style comma number into Indian lakh/crore grouping."""
    negative = comma_digits.startswith("-")
    if negative:
        comma_digits = comma_digits[1:]
    if "." in comma_digits:
        whole, frac = comma_digits.split(".")
    else:
        whole, frac = comma_digits, ""
    parts = whole.split(",")
    scales = len(parts)
    if scales <= 2:
        grouped = whole
    else:
        tail = ",".join(parts[-2:])
        head = parts[:-2]
        head_str = "".join(head)
        head_groups = []
        while len(head_str) > 2:
            head_groups.insert(0, head_str[-2:])
            head_str = head_str[:-2]
        if head_str:
            head_groups.insert(0, head_str)
        grouped = ",".join(head_groups + [tail])
    return f"-{grouped}" + (f".{frac}" if frac else "") if negative else grouped + (f".{frac}" if frac else "")


def inr_value(amount: Decimal | float | int | None, exchange_rate: Decimal | float | int | None) -> Decimal:
    """Convert an amount in its own currency to INR using the stored rate."""
    if amount is None:
        return Decimal("0")
    rate = Decimal(str(exchange_rate or 1))
    return Decimal(str(amount)) * rate
