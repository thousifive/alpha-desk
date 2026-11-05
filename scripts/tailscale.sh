#!/usr/bin/env bash
# Tailscale helpers, sourced by serve.sh, serve-status.sh and tailscale-serve.sh.
#
# The API is private to the tailnet: `tailscale serve` proxies
# https://<machine>.<tailnet>.ts.net -> http://127.0.0.1:8000 for devices on the tailnet only.
# Never `tailscale funnel` (that would make it public). ts_require refuses to run if Funnel is on.

TS_PORT=443
TS_TARGET="http://127.0.0.1:8000"

# The CLI: $TAILSCALE if set, else on PATH (Linux, Homebrew), else inside the macOS app.
ts_cli() {
  if [ -n "${TAILSCALE:-}" ]; then echo "$TAILSCALE"; return; fi
  if command -v tailscale >/dev/null 2>&1; then command -v tailscale; return; fi
  local app=/Applications/Tailscale.app/Contents/MacOS/Tailscale
  if [ -x "$app" ]; then echo "$app"; return; fi
  return 1
}

# Prints one field from `tailscale status --json`: state | dns | certs.
_ts_status_field() {
  "$TS" status --json 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
field = sys.argv[1]
if field == "state":
    print(d.get("BackendState", ""))
elif field == "dns":
    print((d.get("Self") or {}).get("DNSName", "").rstrip("."))
elif field == "certs":
    # Non-empty only when "HTTPS Certificates" is enabled in the admin console.
    print(" ".join(d.get("CertDomains") or []))
' "$1"
}

# Prints one fact from `tailscale serve status --json`: target | funnel.
_ts_serve_field() {
  "$TS" serve status --json 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin) or {}
except ValueError:
    d = {}
host, port, field = sys.argv[1], sys.argv[2], sys.argv[3]
if field == "target":
    h = ((d.get("Web") or {}).get(f"{host}:{port}") or {}).get("Handlers") or {}
    print((h.get("/") or {}).get("Proxy", ""))
elif field == "funnel":
    # AllowFunnel maps "host:port" -> true for anything exposed to the internet.
    print("on" if any((d.get("AllowFunnel") or {}).values()) else "off")
' "$TS_HOST" "$TS_PORT" "$1"
}

ts_target() { _ts_serve_field target; }
ts_funnel() { _ts_serve_field funnel; }
ts_url() { echo "https://$TS_HOST"; }

# Checks everything `make serve` needs and sets TS + TS_HOST. Explains the fix on failure.
ts_require() {
  if ! TS="$(ts_cli)"; then
    echo "Tailscale is not installed. Install it (tailscale.com/download) and log in." >&2
    return 1
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is needed to read Tailscale's status (macOS: xcode-select --install)." >&2
    return 1
  fi
  local state
  state="$(_ts_status_field state)"
  if [ "$state" != "Running" ]; then
    echo "Tailscale is not connected (state: ${state:-unknown})." >&2
    echo "Open the Tailscale app and log in, or run: $TS up" >&2
    return 1
  fi
  TS_HOST="$(_ts_status_field dns)"
  if [ -z "$TS_HOST" ]; then
    echo "This machine has no MagicDNS name. Enable MagicDNS in the admin console (DNS page)." >&2
    return 1
  fi
  if [ -z "$(_ts_status_field certs)" ]; then
    echo "HTTPS certificates are off for your tailnet, so serve can't use https://$TS_HOST." >&2
    echo "Enable them: admin console -> DNS -> HTTPS Certificates -> Enable. See README." >&2
    return 1
  fi
  if [ "$(ts_funnel)" = on ]; then
    echo "Tailscale Funnel is ON for this machine: something here is public on the internet." >&2
    echo "Alpha Desk must stay private. Check: $TS funnel status; turn it off before serving." >&2
    return 1
  fi
}

# Points https://$TS_HOST at the backend (idempotent). Persists in tailscaled until turned off.
ts_serve_on() {
  local current
  current="$(ts_target)"
  if [ -n "$current" ] && [ "$current" != "$TS_TARGET" ]; then
    echo "https://$TS_HOST already serves $current, not Alpha Desk. Not overwriting it." >&2
    echo "Remove it with: $TS serve --https=$TS_PORT off" >&2
    return 1
  fi
  [ "$current" = "$TS_TARGET" ] && return 0
  if ! "$TS" serve --bg --yes --https="$TS_PORT" "$TS_TARGET" >/dev/null; then
    echo "tailscale serve failed (see above)." >&2
    if [ "$(uname -s)" = Linux ]; then
      echo "On Linux, allow your user once: sudo tailscale set --operator=\$USER" >&2
    fi
    return 1
  fi
}

# Removes only our handler (`serve reset` would wipe any other serve config on this machine).
ts_serve_off() {
  [ "$(ts_target)" = "$TS_TARGET" ] || return 0
  "$TS" serve --yes --https="$TS_PORT" off >/dev/null
}

# GET /api/health through the tailnet URL. Retries: the first request after enabling serve
# waits for Let's Encrypt to issue the certificate (can take ~30 s).
ts_health() {
  local tries="${1:-1}" i
  for ((i = 1; i <= tries; i++)); do
    if curl -fsS --max-time 10 "$(ts_url)/api/health" 2>/dev/null; then return 0; fi
    [ "$i" -lt "$tries" ] && sleep 3
  done
  return 1
}
