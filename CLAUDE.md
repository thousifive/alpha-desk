# Alpha Desk: project rules for Claude Code

Full product spec: `docs/SPEC.md`. Read it before planning or starting any milestone.

## About me
Senior frontend engineer (React/TS expert, D3, trading UIs) learning Python, FastAPI, Polars,
DuckDB, and LangGraph through this project. On the frontend, skip the basics. On the backend
and data side, explain non-obvious Python and data-engineering decisions in short code comments.

## Working rules
- Work one milestone at a time (M1–M6 in `docs/SPEC.md`). Never start the next milestone
  without my explicit OK.
- Before coding a milestone, propose a plan (files, data model changes, risks), then wait for approval.
- Leave 2–4 `TODO(me)` Python tasks per milestone, each with tests already written and a
  one-line note on what it teaches. Never implement a `TODO(me)` yourself, even if tests fail
  because of it. Mark those tests as expected to fail until I finish them.
- After each milestone: run all tests and lint, then summarize what was built, what I should
  test manually, and which `TODO(me)` tasks are waiting for me.
- Keep curriculum content in `/content` as YAML. Never hardcode exercises in components.
- Keep LLM prompts in `backend/prompts/` as versioned files, not inline strings.
- Use small, focused commits with clear messages. Don't rewrite unrelated code.
- If something in the spec is ambiguous or conflicts, ask instead of guessing.

## Stack
- `frontend/`: React + TypeScript + Vite, Tailwind, TanStack Query, D3, Monaco, Framer Motion
- `backend/`: Python 3.12, FastAPI (async), Pydantic v2, SQLModel, pytest; deps managed with `uv`
- `content/`: YAML curriculum (skill nodes, exercises, flashcards)
- In-browser execution: DuckDB-WASM (SQL), Pyodide in a web worker (Python)
- AI: Anthropic Python SDK, LangGraph (grader), MCP server (progress tools)

## Security
- The Anthropic API key lives only in `backend/.env` (gitignored). Never put it in frontend code or commit it.
- Any backend code execution must be sandboxed: subprocess, time and memory limits, no network.

## Conventions
- TypeScript strict mode. No `any` without a comment explaining why.
- Python: type hints everywhere, Ruff for lint and format, async endpoints by default.
- Fictional data only: the fund is "Meridian Capital"; never use real fund or client names.

## Commands
- Both: `make dev` (backend on 0.0.0.0:8000 + Vite `--host` on :5173; prints the LAN URL for phones)
- Frontend dev: `make dev-frontend` (Vite on :5173, proxies `/api` to `API_URL` or :8000)
- Backend dev: `make dev-backend` (runs Alembic migrations, then uvicorn on :8000)
- Self-hosted backend: `make serve` (Docker Compose, 127.0.0.1:8000, DB in `./data/alpha.db`;
  Ctrl+C stops and backs up), `make stop`, `make logs`. Uses port 8000 like `make dev`: one at a time.
- Backup: `make backup` (SQLite backup API into `./backups`)
- Run all tests: `make test` (pytest + vitest; `TODO(me)` tests are strict xfail)
- Lint/format: `make lint` / `make fmt`
- Content: `make sync-content` after editing `/content` YAML; `make seed` regenerates the dataset
- Deploy and ops docs: `docs/DEPLOY.md` (Netlify, Docker backend, backups), `docs/MIGRATION.md`
