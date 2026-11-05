# Alpha Desk

A gamified learning app for becoming an AI full-stack engineer at a hedge fund.

You play a new AI engineer at **Meridian Capital**, a fictional fund. Colleagues send you
tickets, and solving them teaches Python, FastAPI, SQL, Polars, DuckDB, LangGraph, RAG, MCP,
cloud deployment, and buy-side finance. You earn XP, level up from Intern to Partner, keep
streaks, and beat "boss fights" that are real milestones of a working Research Copilot.

> Status: in development. See `docs/SPEC.md` for the full spec and milestones.

## Features
- Skill tree with six branches and unlockable nodes
- Daily quests weighted toward your weakest skills
- In-browser SQL (DuckDB-WASM) and Python (Pyodide) exercises with hidden tests
- Finance flashcards with spaced repetition (SM-2)
- PM Chat: practice explaining technical results to a non-technical portfolio manager
- Interview Arena: timed mock interviews with AI feedback
- Boss fights graded by an AI code reviewer
- MCP server so you can query your progress from Claude

## Tech stack
- **Frontend:** React, TypeScript, Vite, Tailwind, TanStack Query, D3, Monaco
- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLModel, pytest, uv
- **AI:** Claude API, LangGraph, MCP

## Project structure
```
alpha-desk/
├── CLAUDE.md      # rules for Claude Code
├── README.md
├── docs/SPEC.md   # full product spec
├── docs/DEPLOY.md, docs/MIGRATION.md   # hosting, backups, moving machines
├── frontend/      # React PWA (local-first event log, Pyodide, DuckDB-WASM)
├── backend/       # FastAPI app + Dockerfile
├── content/       # YAML curriculum
├── data/          # fictional dataset (committed); the server DB lands here too (gitignored)
├── deploy/        # systemd units for the always-on server
└── scripts/       # make serve / backup / LAN helpers
```

**How it runs.** The app is a PWA (Netlify, free) that keeps your progress on each device and
works offline. The backend runs on your own machine only when you want it (`make serve`),
and devices sync with it whenever it's reachable. See `docs/SPEC.md` §7.

## Getting started

### Prerequisites
- Node.js 22+ and `pnpm`
- `uv` (installs Python 3.12 for you)
- An Anthropic API key (needed from M4 onward)
- For `make serve` only: Docker (Docker Desktop or OrbStack on macOS, Docker Engine on Linux)

Install the tools on macOS:
```bash
brew install node uv     # Node 22+ and uv
corepack enable pnpm     # pnpm ships with Node via corepack
```

### Setup, step by step

**1. Clone and install dependencies**
```bash
git clone https://github.com/<your-username>/alpha-desk.git
cd alpha-desk
make install             # uv sync (backend) + pnpm install (frontend)
```

**2. Create your env file**
```bash
cp backend/.env.example backend/.env
```

**3. Set a login password.** The app is single-user and password-protected.
```bash
cd backend && uv run alpha-desk hash-password && cd ..
```
Type a password twice, then replace the `APP_PASSWORD_HASH=''` line in `backend/.env`
with the printed line. Keep the single quotes, because the hash contains `$`.

**4. Set a session secret**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```
Paste the output as `SESSION_SECRET=...` in `backend/.env`.

**5. Start the app**
```bash
make dev                 # API on :8000, app on http://localhost:5173
```

**6. Log in and play.** Open http://localhost:5173 and log in with the password from
step 3. Pick a ticket from the dashboard or skill tree, solve it in the editor, and submit to
run the hidden tests and earn XP.

**7. Day to day**
- `make dev` to start, Ctrl+C to stop both servers.
- After editing YAML in `/content`, run `make sync-content` (or restart the backend).
- `make test` and `make lint` before committing.

The SQLite database is created by Alembic on first `make dev-backend`, and `/content` is
synced into it on every startup. The fictional market dataset is committed in
`data/meridian/`; `make seed` regenerates it deterministically.

Python tickets run in Pyodide, loaded from the jsDelivr CDN on first use (about 10 MB, then
cached by the browser), so they need internet access. SQL tickets are fully self-hosted.

### Environment variables
`backend/.env` (gitignored):
```
APP_PASSWORD_HASH='...'   # from `uv run alpha-desk hash-password`
SESSION_SECRET=...
# CORS_ORIGINS=https://<your-site>.netlify.app   # for the Netlify app
# ANTHROPIC_API_KEY=...   # from M4
```
`backend/.env.example` lists every setting with a comment.

### Commands
| | |
|---|---|
| `make dev` | backend + frontend with reload, on the LAN (prints the phone URL) |
| `make serve` | the backend in Docker for your devices; Ctrl+C stops it and backs up |
| `make backup` | snapshot the server database into `backups/` |
| `make stop` / `make logs` | stop the Docker backend / follow its logs |
| `make test` | pytest + vitest |
| `make lint` / `make fmt` | ruff, oxlint, tsc, prettier |
| `make sync-content` | validate and load `/content` YAML into the DB |
| `make seed` | regenerate the Parquet dataset |

### Testing on a phone
`make dev` binds both servers to all interfaces and prints a URL like
`http://192.168.1.8:5173`. Open it on a phone or iPad on the same Wi-Fi. The phone talks only
to Vite, which proxies `/api` to the backend, so no CORS setup is needed.

Limits of the LAN URL:
- **It's plain HTTP**, so the browser treats it as an insecure context. The app runs, but it
  can't be installed as a PWA, there is no service worker (no offline mode), and Web Locks
  aren't available (two tabs could sync at the same time; harmless, uploads are idempotent).
- **Slow on iPhone and iPad.** Safari runs WebAssembly far slower on insecure origins:
  Pyodide boots in ~45 s instead of ~2 s (measured in WebKit; Chrome isn't affected). Every
  page uses the Pyodide rules engine, so each full reload pays that again. Fine for checking
  layout; for real use on iOS, use HTTPS (the Tailscale URL, once set up).
- **The Netlify site can't use a LAN backend.** An HTTPS page can't call a plain-HTTP API
  (mixed content: the browser blocks it), so `https://….netlify.app` talks to the backend over
  the HTTPS remote-access URL (Tailscale, see `docs/DEPLOY.md`), never to `http://192.168…`.
- macOS may ask to allow incoming connections for `python` and `node` the first time. Allow
  them, or the phone just times out.
- `make dev` and `make serve` both use port 8000: run one at a time.

## Guides

### Run the server for your devices (`make serve`)
Your phone and iPad keep working without it; this is what they sync with.

1. Do steps 2–4 of the setup above (`backend/.env` with password hash and session secret).
2. Add the Netlify site's origin: `CORS_ORIGINS=https://<your-site>.netlify.app` in
   `backend/.env`.
3. Start Docker, then:
   ```bash
   make serve
   ```
   First run builds the image (a few minutes). It waits until `/health` is OK, then shows the
   logs. On macOS it keeps the Mac awake (`caffeinate -s`) while running.
4. Check it: `curl localhost:8000/health` →
   `{"status":"ok","version":"…","db":"ok","host":"<this machine>"}`.
5. **Remote access: Tailscale (coming).** The port is bound to `127.0.0.1` only, so devices
   can't reach it yet. Once Tailscale is set up, its HTTPS URL is what Netlify's `VITE_API_URL`
   points at.
6. Done for the day: **Ctrl+C**. It stops the server and writes `backups/alpha-<time>.db`.

For an always-on Linux machine, see `docs/DEPLOY.md` (systemd) and `docs/MIGRATION.md`.

### Deploy the app to Netlify (free plan)
The free plan has 300 credits a month; a deploy costs ~15. This repo deploys **only `main`**,
and skips commits that don't change the app, so normal use stays far under budget.

1. Netlify → **Add new site → Import from Git** → pick this repo. Leave the build settings
   empty; `netlify.toml` sets them.
2. **Site configuration → Environment variables:** add `VITE_API_URL` = your backend's HTTPS
   origin (no trailing slash). The build fails on purpose without it.
3. **Build & deploy → Branches and deploy contexts:** production branch `main`, branch deploys
   **None**, deploy previews **None**. (These save credits.)
4. Put the site's URL in the backend's `CORS_ORIGINS` and restart it.
5. Deploy = merge to `main` and push. Devices show "Update available · tap to reload".

Details, budget table and pinned CDN assets: `docs/DEPLOY.md`.

### Install on iPhone and iPad
1. Open the Netlify URL in **Safari**.
2. Tap **Share → Add to Home Screen → Add**.
3. Open **Alpha Desk from the Home Screen** and log in there. The installed app has its own
   storage, separate from the Safari tab, so log in and play in the installed app.
4. With the server reachable, open each kind of page once (dashboard, an SQL ticket, a Python
   ticket): that downloads Python and DuckDB (~50 MB) so they work offline afterwards.
5. Settings → **SYNC** shows the server state, queued events and last sync.

### Back up your progress
Each device holds its full progress. The server holds everything that has synced.

- **On a device:** Settings → MY PROGRESS → **EXPORT MY PROGRESS** downloads a JSON file of
  every event. **IMPORT…** merges a file back by event id, so importing twice or into another
  device never duplicates anything. The app reminds you if you haven't exported in 14 days.
  Worth doing on iOS: Safari can clear website data that hasn't been used for a while.
- **On the server:** `make backup` any time; it also runs when `make serve` stops and daily
  on the Linux server. Restore steps: `docs/DEPLOY.md` → Backups.

### Your TODO(me) tasks
Search for `TODO(me)` in `backend/app`. Each has strict-xfail tests: when you finish
one, its tests start passing and fail the run until you delete the xfail marker (a
`pytestmark = ...` line, or the `todo` / `needs_todos` decorators in mixed test files).
Until then the feature degrades visibly: a 501 "offline" message or a notice in the UI.

## Roadmap
- [x] M1: Dashboard, XP and levels, full SQL branch
- [ ] M2: Python exercises, daily quests, streaks
- [ ] M2.5: offline-first PWA, sync, mobile layouts, Netlify + self-hosted backend
  (built; remote access via Tailscale still to do)
- [ ] M3: Flashcards, achievements, skill tree graph
- [ ] M4: AI hints, PM Chat
- [ ] M5: Boss fights, Interview Arena
- [ ] M6: MCP server, deployment, weekly report
