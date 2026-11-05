# Deploying Alpha Desk

Zero hosting cost: the frontend is a PWA on Netlify's free plan, and the backend runs on your
own machine (Docker) whenever it's on. Remote access from phones goes over Tailscale (set up
after M2.5; until then the backend is reachable from this machine only). Progress lives on each device and
syncs when the backend is reachable, so the backend being off is a normal state.

- Frontend: this document, "Netlify".
- Backend: "Backend (self-hosted)".

## Netlify (frontend)

### Budget

The free plan has **300 credits a month**. A production deploy costs about **15**, and
bandwidth about **20 per GB**. When credits run out, the site is paused until next month.

What this repo does to keep that low:

| Cost | How it's kept down |
|---|---|
| Deploys | Only `main` builds. `frontend/scripts/netlify-ignore.sh` cancels deploy previews, branch deploys, and `main` commits that don't touch `frontend/`, `backend/app/` or `netlify.toml`. Docs and content-only merges don't deploy. |
| Bandwidth | Pyodide and DuckDB-WASM (the big parts: 10+ MB and 36 MB) load from jsDelivr at exact pinned versions, not from Netlify. The app shell is ~4 MB raw (~1.2 MB gzipped) per device per release, and the service worker caches it. |
| Repeat visits | `/assets/*` is hashed and cached for a year; only `index.html`, `sw.js` and the manifest revalidate. |

At ~15 credits per deploy, merging to `main` once per milestone stays far under budget.

### One-time setup

1. **Create the site.** Netlify → Add new site → Import from Git → pick the repo. Leave build
   settings empty: `netlify.toml` provides them (base `frontend`, `pnpm build`, publish `dist`).
2. **Set the API origin.** Site configuration → Environment variables → add
   `VITE_API_URL` = your backend's public origin (Tailscale, coming), e.g. `https://api.example.com` (no trailing slash, no
   `/api`). The build fails on purpose if it's missing.
3. **Production branch only.** Site configuration → Build & deploy → Continuous deployment →
   Branches and deploy contexts:
   - Production branch: `main`
   - Branch deploys: **None**
   - Deploy previews: **None**

   The ignore script cancels these anyway, but turning them off in the UI means Netlify never
   even starts them.
4. **Backend CORS.** Add the site's origin to the backend's `CORS_ORIGINS`, e.g.
   `CORS_ORIGINS=https://alpha-desk.netlify.app` in `backend/.env`, and restart it.

### Deploying

Merge to `main` and push. That's the only thing that deploys.

To check a build locally first, with the same settings Netlify uses:

```sh
cd frontend
VITE_API_URL=https://api.example.com pnpm build
pnpm preview   # serves dist/; the service worker is active here, unlike in pnpm dev
```

### Pinned third-party assets

| Asset | Where | Pinned in |
|---|---|---|
| Pyodide runtime + wheels | `cdn.jsdelivr.net/pyodide/v<version>/full/` | `frontend/src/lib/pyodide/protocol.ts` |
| DuckDB-WASM (`.wasm` + worker) | `cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@<version>/dist/` | `frontend/src/lib/duckdb/cdn.ts` |
| DuckDB parquet extension | `extensions.duckdb.org/v<duckdb version>/` | follows the DuckDB-WASM version |

Each version constant must equal the npm package version in `frontend/package.json`; unit
tests fail if they drift. After the first use, the service worker serves all of these from its
cache (`pyodide`, `duckdb`, `duckdb-extensions`), so they also work offline.

### When updates reach devices

A new deploy installs in the background. The app shows **"Update available · tap to reload"**
and never reloads by itself, so a half-written exercise isn't lost. An installed PWA that stays
open also checks for updates hourly.

## Backend (self-hosted)

One container (`docker-compose.yml`, service `api`): FastAPI + SQLite, port bound to
`127.0.0.1:8000` only, so nothing on the LAN or internet can reach it until a tunnel is added.

### Run it

```sh
cp backend/.env.example backend/.env   # then fill in APP_PASSWORD_HASH, SESSION_SECRET, CORS_ORIGINS
make serve    # build, start, wait for /health, follow logs. Ctrl+C = stop + backup
make backup   # snapshot any time (works whether the container runs or not)
make logs / make stop
```

`restart: unless-stopped` brings it back after a crash or Docker restart, but not after you
stopped it yourself.

**macOS tip:** `make serve` runs `caffeinate -s` for as long as it runs, so the Mac doesn't
sleep while plugged in. Closing the lid still sleeps it unless an external display is attached.

### Data

| Host path | In container | What |
|---|---|---|
| `data/alpha.db` | `/data/alpha.db` | the database (plus `-wal`/`-shm` while open) |
| `data/meridian/` | `/data/meridian` | fictional dataset (committed to git) |
| `content/` | `/content` (read-only) | curriculum YAML |
| `backups/` | `/backups` | snapshots |

The container runs as your UID/GID (`scripts/env.sh`), so these files stay owned by you on
Linux. Everything except the dataset is gitignored.

**Why WAL:** readers (sync pulls, `/health`) don't block the writer, and a crash can't
corrupt the file. `synchronous=NORMAL` is safe in WAL mode and much faster. Set per connection
in `backend/app/db.py`.

**Why Alembic, not `create_all`:** `create_all` only creates missing tables; it never adds a
column to an existing one. The server DB lives for months across releases, so the container
runs `alembic upgrade head` on every start (`backend/docker-entrypoint.sh`). A no-op when
already current.

### Backups

`make backup` uses SQLite's online backup API (safe while the server writes; copying the file
could catch a half-written page or miss the WAL), checks `PRAGMA integrity_check`, and writes
`backups/alpha-<UTC timestamp>.db` atomically. It keeps the newest 14 (`BACKUP_KEEP`); pruning
waits on TODO(me) M2.5-3, and until then old backups are kept.

Runs automatically when `make serve` stops, and daily on the Linux server (below).

**Restore:**

```sh
make stop
cp backups/alpha-20261105T031500Z.db data/alpha.db
rm -f data/alpha.db-wal data/alpha.db-shm
make serve
```

Devices keep their own full log and re-upload anything the restored DB lacks on the next sync
(uploads are idempotent by event id).

### Health

`GET /health` (also `/api/health`):

```json
{"status": "ok", "version": "0.1.0+e46c2e7", "db": "ok", "host": "meridian-mac"}
```

503 with `"db": "error"` when SQLite doesn't answer within 2 s. The app's sync pill polls it.

### Security

- **Password stays.** One user, one password (`APP_PASSWORD_HASH`, argon2).
- **Auth across origins is a bearer token, not a cookie.** The app (Netlify) and the API are
  on different sites. A cross-site cookie needs `SameSite=None; Secure`, and Safari's tracking
  prevention (ITP) blocks third-party cookies outright, so login would silently fail on every
  iPhone and iPad. Instead `/api/auth/login` returns a signed 30-day token the app keeps in
  IndexedDB and sends as `Authorization: Bearer`. The app swaps it for a fresh one at most
  daily, so a device in use never expires. Same-origin dev still gets the cookie too.
- **CORS** allows only `CORS_ORIGINS` (comma-separated, exact origins), no credentials.
- **Rate limiting:** 10 failed logins per IP per 15 min, then 429 with `Retry-After`. AI
  endpoints arrive in M4 and will use the same limiter (`backend/app/ratelimit.py`).
  In-memory, which is right for one process; restarts reset it.
- **Anthropic key** only in `backend/.env`. The image never contains it (`.dockerignore` is an
  allowlist); compose passes it in at runtime.

### Remote access: Tailscale (coming)

Not set up yet. Until then the API is reachable only at `http://127.0.0.1:8000` on the machine
running it. When it lands: set Netlify's `VITE_API_URL` and the backend's `CORS_ORIGINS`, and
`FORWARDED_ALLOW_IPS` to the proxy address so rate limits key on real client IPs.

### Phase 2: always-on Linux laptop

```sh
sudo usermod -aG docker "$USER"   # once, then log out and in
git clone … && cd alpha-desk && cp backend/.env.example backend/.env   # fill it in
scripts/install-systemd.sh
```

Installs three units from `deploy/systemd/`:

- `alpha-desk.service`: `docker compose up` at boot; stopping it writes a backup.
- `alpha-desk-backup.timer` + `.service`: daily backup at 03:30 (runs at boot if missed).

Check with `systemctl status alpha-desk` and `journalctl -u alpha-desk-backup`. To update:
`git pull && sudo systemctl restart alpha-desk` (rebuilds the image).
