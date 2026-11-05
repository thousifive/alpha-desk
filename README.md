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
├── frontend/      # React app
├── backend/       # FastAPI app
└── content/       # YAML curriculum
```

## Getting started

### Prerequisites
- Node.js 22+ and `pnpm`
- `uv` (installs Python 3.12 for you)
- An Anthropic API key (needed from M4 onward)

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
# ANTHROPIC_API_KEY=...   # from M4
```

### Commands
| | |
|---|---|
| `make dev` | backend + frontend with reload, on the LAN (prints the phone URL) |
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

### Your TODO(me) tasks
Search for `TODO(me)` in `backend/app`. Each has strict-xfail tests: when you finish
one, its tests start passing and fail the run until you delete the xfail marker (a
`pytestmark = ...` line, or the `todo` / `needs_todos` decorators in mixed test files).
Until then the feature degrades visibly: a 501 "offline" message or a notice in the UI.

## Roadmap
- [x] M1: Dashboard, XP and levels, full SQL branch
- [ ] M2: Python exercises, daily quests, streaks
- [ ] M3: Flashcards, achievements, skill tree graph
- [ ] M4: AI hints, PM Chat
- [ ] M5: Boss fights, Interview Arena
- [ ] M6: MCP server, deployment, weekly report
