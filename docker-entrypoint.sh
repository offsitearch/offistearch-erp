#!/bin/sh
# studioerp-v2 container entrypoint: bootstrap the schema/seed, then serve.
set -e

echo "==> Running DB bootstrap"
python -m scripts.bootstrap

# Render (and many PaaS) inject the port via PORT; prefer explicit APP_PORT
# when set, otherwise fall back to PORT, then the default 8100.
APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-${PORT:-8100}}"

echo "==> Starting uvicorn on ${APP_HOST}:${APP_PORT}"
exec uvicorn studioerp.api.app:app --host "${APP_HOST}" --port "${APP_PORT}" "${@}"
