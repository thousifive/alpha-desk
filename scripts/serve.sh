#!/usr/bin/env bash
# Run the backend for a study session, private to your tailnet:
#   Docker Compose on 127.0.0.1:8000  +  tailscale serve  ->  https://<machine>.<tailnet>.ts.net
# Ctrl+C turns serve off, stops the backend, and takes a backup. Never uses Tailscale Funnel.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/env.sh
. scripts/tailscale.sh

if [ ! -f backend/.env ]; then
  echo "backend/.env is missing: cp backend/.env.example backend/.env and fill it in" >&2
  exit 1
fi
# Before starting anything: fail fast with a clear message if Tailscale isn't ready.
ts_require
if [ -z "$(docker compose ps --status running -q api 2>/dev/null)" ] &&
  curl -fsS --max-time 2 -o /dev/null http://127.0.0.1:8000/health 2>/dev/null; then
  echo "Port 8000 is taken by another server (make dev?). Stop it first." >&2
  exit 1
fi
mkdir -p data backups

started=0
stopped=0
cleanup() {
  [ "$stopped" = 1 ] && return
  stopped=1
  echo
  # Serve off first, so devices see "offline" right away. Also: left on, the tailnet URL would
  # keep proxying to :8000, and a later `make dev` (same port) would be exposed by accident.
  echo "Turning off tailscale serve…"
  ts_serve_off || echo "could not turn serve off; check: $TS serve status" >&2
  [ "$started" = 1 ] || return 0
  echo "Stopping the backend…"
  docker compose stop
  scripts/backup.sh || echo "backup failed (see above)" >&2
}
trap cleanup EXIT INT TERM

# --wait: return once the healthcheck passes (migrations done, DB reachable).
started=1
docker compose up -d --build --wait
ts_serve_on

echo "Checking $(ts_url)/api/health through the tailnet…"
if health="$(ts_health 20)"; then
  echo "  $health"
else
  echo "  not answering yet. The first HTTPS certificate can take a minute;" >&2
  echo "  check later with: make serve-status" >&2
fi
cat <<MSG

  Alpha Desk API:  $(ts_url)
  (private to your tailnet; Netlify's VITE_API_URL should be exactly this)
  Ctrl+C to stop: serve off, backend stopped, backup written.

MSG

# macOS: keep the machine awake while serving (-s: on AC power; -w: until this script exits).
if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -s -w $$ &
fi

# Follow the logs in the foreground; Ctrl+C ends this and triggers cleanup.
docker compose logs -f --no-log-prefix --since 0s api || true
