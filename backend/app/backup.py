"""SQLite backups: consistent online snapshots, plus retention."""

import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

# alpha-20261105T221530Z.db: UTC and zero-padded, so name order == time order.
BACKUP_RE = re.compile(r"^alpha-(\d{8}T\d{6}Z)\.db$")


class BackupError(RuntimeError):
    pass


def backup_name(now: datetime) -> str:
    return f"alpha-{now.astimezone(UTC):%Y%m%dT%H%M%SZ}.db"


def sqlite_path(database_url: str) -> Path:
    """sqlite+aiosqlite:////data/alpha.db -> /data/alpha.db"""
    prefix, sep, path = database_url.partition(":///")
    if not prefix.startswith("sqlite") or not sep or not path:
        raise BackupError(f"Not a file-backed SQLite URL: {database_url}")
    return Path(path)


def backup_sqlite(src: Path, dest_dir: Path, now: datetime | None = None) -> Path:
    """Snapshot `src` into dest_dir with SQLite's online backup API.

    Why not `cp`? With WAL on, recent commits live in alpha.db-wal until a checkpoint, and a
    copy taken mid-write can catch a half-updated page. The backup API reads through SQLite
    itself: it sees every committed transaction (WAL included) as one consistent snapshot, and
    the server can keep running while it does.
    """
    if not src.exists():
        raise BackupError(f"No database at {src}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    final = dest_dir / backup_name(now or datetime.now(UTC))
    partial = final.with_suffix(".db.partial")
    partial.unlink(missing_ok=True)
    # closing(): sqlite3's own context manager only commits; it doesn't close the connection.
    with closing(sqlite3.connect(src)) as s, closing(sqlite3.connect(partial)) as d:
        s.backup(d)
        check = d.execute("PRAGMA integrity_check").fetchone()[0]
        # A backup should be one self-contained file, not a WAL-mode db expecting a -wal file.
        d.execute("PRAGMA journal_mode=DELETE")
    if check != "ok":
        partial.unlink(missing_ok=True)
        raise BackupError(f"Backup failed integrity_check: {check}")
    # Rename is atomic on one filesystem: a crash never leaves a half-written alpha-*.db that
    # retention would count as a real backup.
    partial.rename(final)
    return final


def prune_backups(backup_dir: Path, keep: int) -> list[Path]:
    """Delete all but the newest `keep` backups in backup_dir. Returns the deleted paths,
    oldest first.

    TODO(me) M2.5-3. Teaches: retention policies, and why "newest" must come from data you
    control (the timestamp in the name) rather than file mtimes, which a copy or a restore
    from another machine resets.

    - Only touch files whose name matches BACKUP_RE. Anything else in the folder (a
      `.partial` from a crashed run, a file you dropped in by hand) is left alone.
    - Order by the timestamp in the name; ignore mtimes.
    - keep < 1 is a mistake (it would delete every backup): raise ValueError.
    - Fewer than `keep` backups: delete nothing, return [].
    """
    raise NotImplementedError("TODO(me) M2.5-3: implement prune_backups")
