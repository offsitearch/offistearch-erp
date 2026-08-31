"""Ring 3 (work) — site visits module (CRUD). Photo/report plumbing deferred
until the storage and PDF abstractions land in the kernel."""

from studioerp.rings.work.site_visits import service, models, schemas

__all__ = ["service", "models", "schemas"]
