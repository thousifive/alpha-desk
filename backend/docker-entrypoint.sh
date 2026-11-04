#!/bin/sh
# Container start: bring the schema up to date, then serve.
set -eu

# Alembic, not SQLModel.metadata.create_all(): create_all only creates missing tables and
# silently ignores changed ones (a new column never appears in an existing DB). Alembic
# applies each versioned migration exactly once, tracked in the alembic_version table, so a
# months-old backup restored on the laptop upgrades to the current schema.
alembic upgrade head

# One worker on purpose: the login rate limiter and the derived-tables lock live in process
# memory, and SQLite has a single writer anyway.
# --proxy-headers: when a proxy (Tailscale, later) sits in front, take the client IP from
# X-Forwarded-For, but only from the addresses in FORWARDED_ALLOW_IPS.
exec uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 --workers 1 \
  --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
