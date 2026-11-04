# Alpha Desk API. Built from the repo root (see docker-compose.yml) so the same image runs on
# macOS (Docker Desktop / OrbStack, arm64) and the Linux laptop (amd64): every dependency
# has wheels for both.
FROM python:3.12-slim

# Pinned uv binary from its official image: same resolver as `uv sync` on your machine.
COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend

# Dependencies first, in their own layer: code edits don't reinstall polars/duckdb.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
RUN uv sync --frozen --no-dev \
    # Readable/executable by any uid: compose runs as your host uid so files in ./data and
    # ./backups belong to you, not root.
    && chmod -R a+rX /app

ARG GIT_SHA=""
ENV GIT_SHA=${GIT_SHA}

EXPOSE 8000
ENTRYPOINT ["sh", "/app/backend/docker-entrypoint.sh"]
