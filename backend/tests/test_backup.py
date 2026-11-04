"""Backups. prune_backups is TODO(me) M2.5-3 (strict xfail below)."""

import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.backup import BackupError, backup_name, backup_sqlite, prune_backups, sqlite_path

todo = pytest.mark.xfail(reason="TODO(me) M2.5-3: implement prune_backups", strict=True)

T0 = datetime(2026, 11, 5, 22, 15, 30, tzinfo=UTC)


def _wal_db(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE t (n INTEGER)")
    con.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(100)])
    con.commit()
    return con


def test_backup_includes_commits_still_in_the_wal(tmp_path: Path) -> None:
    src = tmp_path / "alpha.db"
    live = _wal_db(src)  # held open: the commits sit in alpha.db-wal, not yet checkpointed
    assert (tmp_path / "alpha.db-wal").stat().st_size > 0
    out = backup_sqlite(src, tmp_path / "backups", T0)
    live.close()
    assert out.name == "alpha-20261105T221530Z.db"
    with closing(sqlite3.connect(out)) as b:
        assert b.execute("SELECT count(*) FROM t").fetchone()[0] == 100
        # Self-contained: opening it doesn't need a -wal file next to it.
        assert b.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    assert not list((tmp_path / "backups").glob("*.partial"))


def test_backup_of_missing_db_fails_cleanly(tmp_path: Path) -> None:
    with pytest.raises(BackupError):
        backup_sqlite(tmp_path / "nope.db", tmp_path / "backups")


def test_backup_names_sort_by_time() -> None:
    names = [backup_name(T0 + timedelta(hours=h)) for h in (0, 5, 30, 24 * 40)]
    assert names == sorted(names)
    # Converted to UTC, so a non-UTC clock can't reorder them.
    assert backup_name(T0) == "alpha-20261105T221530Z.db"


def test_sqlite_path_from_database_url() -> None:
    assert sqlite_path("sqlite+aiosqlite:////data/alpha.db") == Path("/data/alpha.db")
    assert sqlite_path("sqlite+aiosqlite:///./alpha.db") == Path("./alpha.db")
    with pytest.raises(BackupError):
        sqlite_path("postgresql+asyncpg://u@h/db")


# ---- TODO(me) M2.5-3: prune_backups ------------------------------------------------------


def _backups(d: Path, n: int) -> list[Path]:
    d.mkdir(exist_ok=True)
    paths = []
    for i in range(n):
        p = d / backup_name(T0 + timedelta(days=i))
        p.write_bytes(b"x")
        # mtimes in *reverse* order: the newest-by-name looks oldest on disk, as after a
        # restore or a copy between machines.
        os.utime(p, (1_000_000 - i, 1_000_000 - i))
        paths.append(p)
    return paths


@todo
def test_prune_keeps_the_newest_by_name_not_mtime(tmp_path: Path) -> None:
    paths = _backups(tmp_path, 17)
    deleted = prune_backups(tmp_path, keep=14)
    assert deleted == paths[:3]
    assert sorted(tmp_path.iterdir()) == paths[3:]


@todo
def test_prune_leaves_other_files_alone(tmp_path: Path) -> None:
    paths = _backups(tmp_path, 3)
    others = [tmp_path / "alpha-20261105T000000Z.db.partial", tmp_path / "notes.txt"]
    for o in others:
        o.write_text("keep me")
    assert prune_backups(tmp_path, keep=1) == paths[:2]
    assert all(o.exists() for o in others)


@todo
def test_prune_with_fewer_than_keep_deletes_nothing(tmp_path: Path) -> None:
    _backups(tmp_path, 5)
    assert prune_backups(tmp_path, keep=14) == []
    assert len(list(tmp_path.iterdir())) == 5


@todo
def test_prune_refuses_to_delete_everything(tmp_path: Path) -> None:
    _backups(tmp_path, 2)
    with pytest.raises(ValueError):
        prune_backups(tmp_path, keep=0)
    assert len(list(tmp_path.iterdir())) == 2
