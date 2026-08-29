"""FastAPI application factory + router registry (API composition root).

Assembles the kernel middleware, global error boundary and the ring routers.
This is the only place allowed to wire across rings.
"""

import os
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
    yield


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

    for router in (
        departments_router,
        org_levels_router,
        settings_router,
        notifications_router,
        auth_router,
        users_router,
        employees_router,
        attendance_router,
    ):
        app.include_router(router, prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False, response_model=None)
    async def root() -> RedirectResponse | dict:
        if is_production:
            return {"status": "ok", "docs": "/api/v1/system/health"}
        return RedirectResponse(url="/docs")

    app.state.api_v1_prefix = settings.api_v1_prefix
    return app


app = create_app()
