#!/usr/bin/env bash
# Linux only: install and start the systemd units for this checkout and user.
# Your user must be in the `docker` group (sudo usermod -aG docker "$USER", then log in again).
set -euo pipefail
cd "$(dirname "$0")/.."
[ "$(uname -s)" = Linux ] || { echo "systemd units are for the Linux laptop" >&2; exit 1; }

repo="$(pwd)"
for unit in alpha-desk.service alpha-desk-backup.service alpha-desk-backup.timer; do
  sed -e "s|@REPO@|$repo|g" -e "s|@USER@|$(id -un)|g" \
      -e "s|@UID@|$(id -u)|g" -e "s|@GID@|$(id -g)|g" \
      "deploy/systemd/$unit" | sudo tee "/etc/systemd/system/$unit" >/dev/null
  echo "installed /etc/systemd/system/$unit"
done
sudo systemctl daemon-reload
sudo systemctl enable --now alpha-desk.service alpha-desk-backup.timer
systemctl --no-pager status alpha-desk.service | head -5
