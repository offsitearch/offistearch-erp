"""Ring 4 (money) — finance (invoices, expenses, overview) module.

PDF generation, email and receipt upload/download are deferred until the
storage/email/PDF abstractions land in the kernel (Ring 5 reports phase).
"""

from studioerp.rings.money.finance import service, models, schemas

__all__ = ["service", "models", "schemas"]
