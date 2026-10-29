"""Engine, schema creation and the append-only triggers.

SQLite is blocking, so API handlers are sync `def` and share one engine. SQLite
has a single writer; `check_same_thread=False` plus the default pool is enough
for a 256 MB Fly.io instance and avoids `aiosqlite`, which is banned in
rules.md section 1.
"""

from __future__ import annotations

import os
import pathlib
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from netra.db import models as _models  # noqa: F401  (registers the tables)
from netra.db.models import APPEND_ONLY_TABLES

DEFAULT_DB_PATH = "netra.db"


def database_url(path: str | None = None) -> str:
    """Resolve the SQLite URL. `NETRA_DB` wins, then the argument, then the default."""
    return f"sqlite:///{path or os.environ.get('NETRA_DB') or DEFAULT_DB_PATH}"


class DatabaseDirectoryMissing(RuntimeError):
    """The database's parent directory does not exist. Almost always a volume."""


def _check_parent_directory(url: str) -> None:
    """Fail with the actual cause before SQLite fails with a vague one.

    SQLite answers `unable to open database file` whether the path is wrong,
    the directory is missing or the disk is read-only. On Fly that message is
    what you get when the volume did not attach or `[[mounts]]` names a volume
    that does not exist, and it tells you none of that.

    This deliberately does NOT create the directory. If `/data` is absent
    because the volume failed to mount, creating it would put the ledger on the
    container filesystem, where it works perfectly until the next deploy
    silently discards every entry. An error at boot is the only safe answer.
    """
    if not url.startswith("sqlite:///"):
        return
    path = url[len("sqlite:///") :]
    if not path or path == ":memory:":
        return
    parent = pathlib.Path(path).parent
    if parent and not parent.exists():
        raise DatabaseDirectoryMissing(
            f"{parent} does not exist, so the database at {path} cannot be "
            f"opened. On Fly this means the volume is not mounted: check that "
            f"[[mounts]] in fly.toml names a volume that exists in this "
            f"region (`fly volumes list`). The directory is NOT created here "
            f"on purpose - a ledger written outside the volume is discarded by "
            f"the next deploy."
        )


def make_engine(path: str | None = None, echo: bool = False):
    _check_parent_directory(database_url(path))
    engine = create_engine(
        database_url(path),
        echo=echo,
        connect_args={"check_same_thread": False},
    )
    with engine.connect() as conn:
        # Foreign keys are OFF by default in SQLite and must be set per
        # connection; without this the FKs above are decoration.
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.commit()
    return engine


# --------------------------------------------------------------- triggers


def _trigger_sql(table: str, op: str) -> str:
    return (
        f"CREATE TRIGGER IF NOT EXISTS trg_{table}_no_{op.lower()} "
        f"BEFORE {op} ON {table} BEGIN "
        f"SELECT RAISE(ABORT, '{table} is append-only: {op} is forbidden'); "
        f"END"
    )


def install_append_only_triggers(engine) -> None:
    """Raise on UPDATE and DELETE for every ledger-bearing table.

    These stop the application from rewriting history. They do NOT stop someone
    with direct database access, who can drop a trigger - which is exactly why
    the hash chain and the Ed25519 signatures exist, and what the tamper demo
    in `netra.ledger.tamper` shows.
    """
    with engine.connect() as conn:
        for table in APPEND_ONLY_TABLES:
            for op in ("UPDATE", "DELETE"):
                conn.execute(text(_trigger_sql(table, op)))
        conn.commit()


def drop_append_only_triggers(engine, table: str) -> None:
    """Remove one table's append-only triggers. Used ONLY by the tamper demo."""
    with engine.connect() as conn:
        for op in ("update", "delete"):
            conn.execute(text(f"DROP TRIGGER IF EXISTS trg_{table}_no_{op}"))
        conn.commit()


def init_db(path: str | None = None, echo: bool = False):
    """Create the engine, the tables and the triggers. Idempotent."""
    engine = make_engine(path, echo=echo)
    SQLModel.metadata.create_all(engine)
    install_append_only_triggers(engine)
    return engine


@contextmanager
def session_scope(engine) -> Iterator[Session]:
    """One transaction. Commits on success, rolls back on any exception."""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
