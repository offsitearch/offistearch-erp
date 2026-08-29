"""Kernel middleware (k0): request-id capture + request logging.

Ported from the reference monolith ``app/main.py`` (request logging & request_id
middleware + JSON log formatter). CORS, security headers and rate-limit tracker
are assembled in the API composition root (``studioerp.api``) and wired around
these; the kernel keeps the correlation-capture primitive.
"""

import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from studioerp.request_context import (
    FORWARDED_FOR_HEADER,
    USER_AGENT_HEADER,
    capture_request_context,
)


class JsonRequestFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for attr in (
            "request_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
        ):
            if hasattr(record, attr):
                log_entry[attr] = getattr(record, attr)
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def setup_logging(name: str = "app") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonRequestFormatter())
    logger.handlers = [handler]
    logger.propagate = False
    return logger


logger = setup_logging()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request_id, capture client IP/UA into the ambient context, and
    set the ``X-Request-ID`` response header."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        forwarded_for = request.headers.get(FORWARDED_FOR_HEADER)
        client_ip = (
            forwarded_for.split(",")[0].strip()
            if forwarded_for
            else (request.client.host if request.client else None)
        )
        capture_request_context(request_id, client_ip, request.headers.get(USER_AGENT_HEADER))

        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "%s %s",
            request.method,
            request.url.path,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
