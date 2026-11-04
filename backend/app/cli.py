"""`uv run alpha-desk <command>`: admin CLI."""

import asyncio
import json

import typer

from app.auth import hash_password
from app.backup import BackupError, backup_sqlite, prune_backups, sqlite_path
from app.config import get_settings
from app.content.bundle import build_bundle
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


@app.command("backup")
def backup_cmd() -> None:
    """Snapshot the database into BACKUP_DIR, then keep only the newest BACKUP_KEEP."""
    settings = get_settings()
    try:
        path = backup_sqlite(sqlite_path(settings.database_url), settings.backup_dir)
    except BackupError as e:
        typer.echo(f"backup failed: {e}", err=True)
        raise typer.Exit(1) from e
    typer.echo(f"backup: {path} ({path.stat().st_size / 1024:.0f} KB)")
    try:
        deleted = prune_backups(settings.backup_dir, settings.backup_keep)
    except NotImplementedError as e:
        # The backup itself succeeded; only retention is waiting on the TODO.
        typer.echo(f"note: old backups not pruned yet ({e})", err=True)
        return
    for p in deleted:
        typer.echo(f"pruned: {p.name}")


@app.command("export-bundle")
def export_bundle() -> None:
    """Print the offline content bundle as JSON (used by the frontend's kernel e2e test)."""
    settings = get_settings()
    typer.echo(
        json.dumps(build_bundle(load_content(settings.content_dir), settings.current_milestone))
    )


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
