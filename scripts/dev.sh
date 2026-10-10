#!/usr/bin/env bash
# Локальный запуск API без Docker и Postgres: SQLite-файл, демо-данные создаются при старте.
set -euo pipefail
cd "$(dirname "$0")/.."
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///$PWD/.dev.db}"
export SECRET_KEY="${SECRET_KEY:-dev-only-secret-key-change-me-0123456789}"
export ENVIRONMENT="${ENVIRONMENT:-development}"
alembic upgrade head
cd src && exec uvicorn app.main:app --reload --port "${PORT:-8000}"
