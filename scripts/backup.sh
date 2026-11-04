#!/usr/bin/env bash
# Back up data/alpha.db into backups/ via the SQLite backup API, inside the container (the
# only process that opens the DB, so file locking never crosses the Docker boundary).
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/env.sh
mkdir -p backups

if [ ! -f data/alpha.db ]; then
  echo "backup: no data/alpha.db yet, nothing to back up"
  exit 0
fi
if [ -n "$(docker compose ps --status running -q api 2>/dev/null)" ]; then
  docker compose exec -T api alpha-desk backup
else
  # Stopped (e.g. right after `make serve` exits): a throwaway container with the same mounts.
  docker compose run --rm --no-deps -T --entrypoint alpha-desk api backup
fi
