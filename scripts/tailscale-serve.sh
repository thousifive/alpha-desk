#!/usr/bin/env bash
# For systemd (the always-on server): point tailscale serve at the backend, or remove it.
#   scripts/tailscale-serve.sh on    # checks Tailscale + Funnel, then serves (idempotent)
#   scripts/tailscale-serve.sh off
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/tailscale.sh
ts_require
case "${1:-}" in
  on) ts_serve_on && echo "serving $(ts_url) -> $TS_TARGET" ;;
  off) ts_serve_off && echo "serve off for $(ts_url)" ;;
  *) echo "usage: $0 on|off" >&2; exit 2 ;;
esac
