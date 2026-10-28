"""Engine, schema creation and the append-only triggers.

SQLite is blocking, so API handlers are sync `def` and share one engine. SQLite
has a single writer; `check_same_thread=False` plus the default pool is enough
for a 256 MB Fly.io instance and avoids `aiosqlite`, which is banned in
rules.md section 1.
"""

from __future__ import annotations

import os
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


def make_engine(path: str | None = None, echo: bool = False):
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
