#!/usr/bin/env bash
set -e

echo "=== Running Alembic Database Migrations ==="
alembic upgrade head

echo "=== Verifying Master Catalog & Super Admin ==="
python scripts/init_db.py

echo "=== Booting Production Uvicorn Engine ==="
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2