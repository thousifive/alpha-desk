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

### Setup
```bash
make install                                  # uv sync + pnpm install
cp backend/.env.example backend/.env
cd backend && uv run alpha-desk hash-password # paste the printed line into backend/.env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"  # use as SESSION_SECRET
cd .. && make dev                             # API on :8000, app on http://localhost:5173
```
The SQLite database is created by Alembic on first `make dev-backend`, and `/content` is
synced into it on every startup. The fictional market dataset is committed in
`data/meridian/`; `make seed` regenerates it deterministically.

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
| `make dev` | backend + frontend with reload |
| `make test` | pytest + vitest |
| `make lint` / `make fmt` | ruff, oxlint, tsc, prettier |
| `make sync-content` | validate and load `/content` YAML into the DB |
| `make seed` | regenerate the Parquet dataset |

### Your TODO(me) tasks
Search for `TODO(me)` in `backend/app`. Each has strict-xfail tests: when you finish
one, its tests start passing and fail the run until you delete the `pytestmark` line.

## Roadmap
- [x] M1: Dashboard, XP and levels, full SQL branch
- [ ] M2: Python exercises, daily quests, streaks
- [ ] M3: Flashcards, achievements, skill tree graph
- [ ] M4: AI hints, PM Chat
- [ ] M5: Boss fights, Interview Arena
- [ ] M6: MCP server, deployment, weekly report
