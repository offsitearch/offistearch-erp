"""API composition root: FastAPI app + dependencies + router registry.

The API layer is the one place that may reach across rings to wire routers and
dependencies. Business logic stays in ring services; these handlers only
authenticate, authorize and delegate.
"""
