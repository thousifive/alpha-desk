"""`uv run alpha-desk <command>`: admin CLI."""

import asyncio

import typer

from app.auth import hash_password
from app.config import get_settings
from app.content.loader import load_content, sync_content
from app.dataset.generate import generate
from app.db import dispose_engine, get_sessionmaker

app = typer.Typer(no_args_is_help=True)


@app.command("hash-password")
def hash_password_cmd() -> None:
    """Prompt for a password and print the APP_PASSWORD_HASH line for backend/.env."""
    pw = typer.prompt("Password", hide_input=True, confirmation_prompt=True)
    # Single quotes: argon2 hashes contain `$`, which dotenv would otherwise try to expand.
    typer.echo(f"APP_PASSWORD_HASH='{hash_password(pw)}'")


@app.command("seed-dataset")
def seed_dataset(
    validate: bool = typer.Option(False, help="Run validate_ohlcv (TODO(me)) before writing."),
) -> None:
    """Regenerate the fictional Meridian dataset Parquet files (deterministic)."""
    out = get_settings().dataset_dir
    counts = generate(out, validate=validate)
    for table, n in counts.items():
        typer.echo(f"{table:>18}: {n:>7,} rows")
    typer.echo(f"wrote {out}")


@app.command("sync-content")
def sync_content_cmd() -> None:
    """Validate /content YAML and upsert nodes + exercises into the database."""

    async def _run() -> dict[str, int]:
        bundle = load_content(get_settings().content_dir)
        async with get_sessionmaker()() as session:
            counts = await sync_content(session, bundle)
        await dispose_engine()
        return counts

    # Typer commands are sync; asyncio.run starts an event loop just for this call.
    counts = asyncio.run(_run())
    typer.echo(f"synced {counts['nodes']} nodes, {counts['exercises']} exercises")


@app.callback()
def main() -> None:
    """Alpha Desk admin commands."""
