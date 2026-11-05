#!/usr/bin/env bash
# One-screen answer to "is my server reachable from my phone?"
set -uo pipefail
cd "$(dirname "$0")/.."
. scripts/env.sh
. scripts/tailscale.sh

row() { printf '  %-11s %s\n' "$1" "$2"; }
echo "Alpha Desk"

state="$(docker compose ps --format '{{.State}} ({{.Status}})' api 2>/dev/null | head -1)"
row Backend "${state:-not running}"
if local_health="$(curl -fsS --max-time 3 http://127.0.0.1:8000/health 2>/dev/null)"; then
  row Health "$local_health"
  # Something answers on :8000 but it isn't the container: `make dev` (same port).
  [ -n "$state" ] || row "" "^ not the Docker backend (make dev running?). make serve needs :8000 free."
else
  row Health "no answer on 127.0.0.1:8000"
fi

if ! TS="$(ts_cli)"; then
  row Tailscale "not installed"
  exit 1
fi
ts_state="$(_ts_status_field state)"
row Tailscale "${ts_state:-unknown}"
if [ "$ts_state" != Running ]; then exit 1; fi
TS_HOST="$(_ts_status_field dns)"
[ -n "$(_ts_status_field certs)" ] || row HTTPS "certificates OFF in the admin console (see README)"
target="$(ts_target)"
if [ -n "$target" ]; then row Serve "on: $(ts_url) -> $target"; else row Serve "off"; fi
if [ "$(ts_funnel)" = on ]; then
  row Funnel "ON: something on this machine is public. Turn it off: $TS funnel status"
else
  row Funnel "off (private to your tailnet)"
fi
row URL "$(ts_url)"
if [ -n "$target" ]; then
  if h="$(ts_health 1)"; then row "Via tailnet" "$h"; else row "Via tailnet" "no answer"; fi
fi
