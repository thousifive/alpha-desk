"""`uv run alpha-desk <command>`: admin CLI."""

import typer

from app.auth import hash_password
from app.config import get_settings
from app.dataset.generate import generate

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


@app.callback()
def main() -> None:
    """Alpha Desk admin commands."""
