"""FastAPI application factory + router registry (API composition root).

Assembles the kernel middleware, global error boundary and the ring routers.
This is the only place allowed to wire across rings.
"""

import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from studioerp.config import settings
from studioerp.middleware import RequestContextMiddleware, setup_logging

logger = setup_logging()


async def _init_db() -> None:
    """Startup data-bootstrap hook.

    Alembic migrations + reference-data seeding are wired here as they land
    (fresh-baseline decision — see the kernel+rings spec). No-op for now so the
    app can be imported without a live database during early ring builds.
    """
    return None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await _init_db()

    from studioerp.generate_timesheet import close_browser
    from studioerp.rings.comms.backup import scheduler as backup_scheduler
    from studioerp.rings.work.timesheets import scheduler as timesheet_scheduler

    backup_scheduler.start_backup_scheduler()
    timesheet_scheduler.start_timesheet_scheduler()
    try:
        yield
    finally:
        timesheet_scheduler.stop_timesheet_scheduler()
        backup_scheduler.stop_backup_scheduler()
        await close_browser()


def create_app() -> FastAPI:
    is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url=None if is_production else "/docs",
        redoc_url=None,
        openapi_url=None if is_production else "/openapi.json",
    )

    # ── Global error boundary ────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
        logger.error(
            "Unhandled exception on %s %s",
            request.method,
            request.url.path,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
            },
            exc_info=exc,
        )
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
        )
        response.headers["X-Request-ID"] = request_id
        return response

    # ── Middleware (outermost → innermost matters) ───────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["authorization", "content-type", "x-request-id"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_min_size)
    if settings.security_headers_enabled:
        _SecurityHeadersMiddleware.install(app)
    app.add_middleware(RequestContextMiddleware)

    # ── Routers ──────────────────────────────────────────────────────
    from studioerp.platform.notifications.router import router as notifications_router
    from studioerp.platform.orgstructure.router import (
        departments_router,
        org_levels_router,
    )
    from studioerp.platform.settings.router import router as settings_router
    from studioerp.rings.people.identity.router import auth_router, users_router
    from studioerp.rings.people.employees.router import router as employees_router
    from studioerp.rings.people.attendance.router import router as attendance_router
    from studioerp.rings.people.leave.router import router as leave_router
    from studioerp.rings.people.holidays.router import router as holidays_router
    from studioerp.rings.work.projects.router import router as projects_router
    from studioerp.rings.work.tasks.router import router as tasks_router
    from studioerp.rings.work.timesheets.router import router as timesheets_router
    from studioerp.rings.work.site_visits.router import router as site_visits_router
    from studioerp.rings.money.clients.router import router as clients_router
    from studioerp.rings.money.payroll.router import payroll_router
    from studioerp.rings.money.finance.router import (
        expenses_router,
        finance_router,
        invoices_router,
    )
    from studioerp.rings.comms.notices.router import router as notices_router
    from studioerp.rings.comms.meetings.router import router as meetings_router
    from studioerp.rings.comms.audit.router import router as audit_router
    from studioerp.rings.comms.backup.router import router as backup_router
    from studioerp.rings.comms.dashboard.router import router as dashboard_router
    from studioerp.rings.comms.reports.router import router as reports_router

    # ── Cross-ring wiring (composition root only) ──────────────────────
    # The work ring stores Project.client_id as a plain int and exposes an
    # injectable client_name_resolver hook. Register the money-ring-backed
    # implementation here so project listings resolve client display names.
    from sqlalchemy import select as _select

    from studioerp.rings.money.clients.models import Client
    from studioerp.rings.work.projects import service as project_service

    async def _resolve_client_names(db, client_ids):
        if not client_ids:
            return {}
        rows = (
            await db.execute(
                _select(Client.id, Client.name).where(
                    Client.id.in_(client_ids), Client.is_active.is_(True)
                )
            )
        ).all()
        return {cid: name for cid, name in rows}

    project_service.client_name_resolver = _resolve_client_names

    for router in (
        departments_router,
        org_levels_router,
        settings_router,
        notifications_router,
        auth_router,
        users_router,
        employees_router,
        attendance_router,
        leave_router,
        holidays_router,
        projects_router,
        tasks_router,
        timesheets_router,
        site_visits_router,
        clients_router,
        payroll_router,
        finance_router,
        invoices_router,
        expenses_router,
        notices_router,
        meetings_router,
        audit_router,
        backup_router,
        dashboard_router,
        reports_router,
    ):
        app.include_router(router, prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False, response_model=None)
    async def root() -> RedirectResponse | dict:
        if is_production:
            return {"status": "ok", "docs": "/api/v1/system/health"}
        return RedirectResponse(url="/docs")

    # ── Health endpoints (public — uptimerobot) ────────────────────
    # Registered under the v1 prefix so the prod root's /api/v1/system/health
    # link is real. Uptimerobot monitors /api/v1/system/health.
    from fastapi import APIRouter as _APIRouter

    system_router = _APIRouter()

    @system_router.api_route("/system/health", methods=["GET", "HEAD"], include_in_schema=False)
    async def health_check() -> dict:
        t0 = time.monotonic()
        try:
            from sqlalchemy import text as _sqltext
            from studioerp.db.session import get_session_factory

            async with get_session_factory()() as session:
                await session.execute(_sqltext("SELECT 1"))
            db_ms = round((time.monotonic() - t0) * 1000, 1)
            return {"status": "ok", "version": settings.app_version, "db_ms": db_ms}
        except Exception:
            return {"status": "degraded", "version": settings.app_version}

    app.include_router(system_router, prefix=settings.api_v1_prefix)

    app.state.api_v1_prefix = settings.api_v1_prefix
    return app


class _SecurityHeadersMiddleware:
    """Lightweight security headers — off by default, enable via SECURITY_HEADERS_ENABLED."""

    _HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }

    def __init__(self, app):  # type: ignore[no-untyped-def]
        self.app = app

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] == "http":

            async def send_with_headers(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    for k, v in self._HEADERS.items():
                        headers.append((k.lower().encode(), v.encode()))
                    message["headers"] = headers
                await send(message)

            await self.app(scope, receive, send_with_headers)
        else:
            await self.app(scope, receive, send)

    @classmethod
    def install(cls, app: FastAPI) -> None:
        app.add_middleware(cls)


app = create_app()
