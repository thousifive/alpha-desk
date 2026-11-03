"""`uv run alpha-desk <command>`: admin CLI."""

import typer

from app.auth import hash_password

app = typer.Typer(no_args_is_help=True)


@app.command("hash-password")
def hash_password_cmd() -> None:
    """Prompt for a password and print the APP_PASSWORD_HASH line for backend/.env."""
    pw = typer.prompt("Password", hide_input=True, confirmation_prompt=True)
    # Single quotes: argon2 hashes contain `$`, which dotenv would otherwise try to expand.
    typer.echo(f"APP_PASSWORD_HASH='{hash_password(pw)}'")


@app.callback()
def main() -> None:
    """Alpha Desk admin commands."""
