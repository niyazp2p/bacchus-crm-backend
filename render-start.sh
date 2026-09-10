#!/usr/bin/env bash
set -e

echo "=== Initializing Database Schema & Seeding Master Data ==="
python scripts/init_db.py

echo "=== Stamping Alembic Migration Baseline ==="
alembic stamp head

echo "=== Booting Production Uvicorn Engine ==="
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2