#!/usr/bin/env sh
# Print the URL a phone or iPad on the same Wi-Fi can open for `make dev`.
port="${1:-5173}"
case "$(uname -s)" in
  Darwin)
    # en0 is Wi-Fi on most Macs; en1 on some with built-in Ethernet.
    ip="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)" ;;
  *)
    ip="$(hostname -I 2>/dev/null | awk '{print $1}')" ;;
esac
if [ -z "$ip" ]; then
  echo "LAN URL: no LAN address found (not on Wi-Fi?)"
  exit 0
fi
cat <<MSG

  ┌─────────────────────────────────────────────────────────────
  │ Phone / iPad on this Wi-Fi:  http://$ip:$port
  │ Plain HTTP: fine for testing; can't install as a PWA or work
  │ offline (needs HTTPS). See README "Testing on a phone".
  └─────────────────────────────────────────────────────────────

MSG
