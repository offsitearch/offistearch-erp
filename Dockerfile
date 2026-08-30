# studioerp-v2 — kernel+rings API dev image
# Python 3.12 (asyncpg supports 3.12 with prebuilt wheels for PostgreSQL access;
# the local dev box runs 3.14 but the container pins 3.12 for asyncpg wheels).
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# -- run as non-root -------------------------------------------------------
RUN groupadd --gid 1000 appuser && useradd --uid 1000 --gid 1000 -m appuser

# -- source (required before the editable install can resolve packages) ----
COPY pyproject.toml .
COPY src ./src
COPY scripts ./scripts

# Install the package (editable) + runtime and .dev extras (pytest, ruff,
# import-linter) so tests/lint work inside the container too.
RUN pip install --no-cache-dir -e ".[dev]"

# Playwright/Chromium is used by the reports PDF path.
RUN playwright install --with-deps chromium

# -- runtime -----------------------------------------------------------------
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint
RUN chmod +x /usr/local/bin/docker-entrypoint

RUN mkdir -p /app/uploads && chown -R appuser:appuser /app

USER appuser
WORKDIR /app

EXPOSE 8100
ENV APP_PORT=8100

ENTRYPOINT ["docker-entrypoint"]
