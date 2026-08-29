"""Money primitives (kernel k0).

All rupee/currency amounts are handled as ``Decimal`` quantized to 2 decimal
places via :func:`q`. Never use ``float`` for money. This is the single money
policy entry point for every ring.
"""

from decimal import Decimal
from typing import Any

_PENNY = Decimal("0.01")


def q(value: Any) -> Decimal:
    """Quantize a value to 2 decimal places (currency penny)."""
    return Decimal(value or 0).quantize(_PENNY)
