#!/usr/bin/env bash
# Phase 1 (dev machine): run the backend for a session. Ctrl+C stops it and takes a backup.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/env.sh

if [ ! -f backend/.env ]; then
  echo "backend/.env is missing: cp backend/.env.example backend/.env and fill it in" >&2
  exit 1
fi
mkdir -p data backups

stopped=0
cleanup() {
  [ "$stopped" = 1 ] && return
  stopped=1
  echo
  echo "Stopping the backend…"
  docker compose stop
  scripts/backup.sh || echo "backup failed (see above)" >&2
}
trap cleanup EXIT INT TERM

# --wait: return once the healthcheck passes (migrations done, DB reachable).
docker compose up -d --build --wait
echo "Alpha Desk API on http://127.0.0.1:8000 (host: $ALPHA_HOST). Ctrl+C to stop + back up."

# macOS: keep the machine awake while serving (-s: on AC power; -w: until this script exits).
if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -s -w $$ &
fi

# Follow the logs in the foreground; Ctrl+C ends this and triggers cleanup.
docker compose logs -f --no-log-prefix --since 0s api || true
