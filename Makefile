.PHONY: install dev dev-backend dev-frontend test test-backend test-frontend lint fmt seed sync-content serve backup stop logs

install:
	cd backend && uv sync
	cd frontend && pnpm install

# Runs both servers; Ctrl+C stops both.
dev:
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	cd backend && uv run alembic upgrade head && uv run uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && pnpm dev

test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest -q

test-frontend:
	cd frontend && pnpm test

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && pnpm lint && pnpm typecheck && pnpm format:check

fmt:
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd frontend && pnpm format

seed:
	cd backend && uv run alpha-desk seed-dataset

sync-content:
	cd backend && uv run alpha-desk sync-content

# ---- self-hosted backend (Docker) -------------------------------------------------------
# Session server on this machine; Ctrl+C stops it and writes a backup. See docs/DEPLOY.md.
serve:
	scripts/serve.sh

# Snapshot data/alpha.db into backups/ (SQLite backup API), keeping the newest 14.
backup:
	scripts/backup.sh

stop:
	. scripts/env.sh && docker compose stop

logs:
	. scripts/env.sh && docker compose logs -f api
