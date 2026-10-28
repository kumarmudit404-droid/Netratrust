"""T-02: the seven tables and the append-only triggers.

The triggers are the point of this file. A table that is documented as
append-only but enforces nothing is a comment, not a control.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

# RAISE(ABORT, ...) surfaces as sqlite3.IntegrityError, not OperationalError.
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel

from netra.db.models import (
    APPEND_ONLY_TABLES,
    Checkpoint,
    Encounter,
    LedgerEntry,
    Referral,
    ReferralEvent,
)
from netra.db.util import new_id, now_iso
from tests.conftest import TEST_KID, TEST_SITE

EXPECTED_TABLES = {
    "sites",
    "devices",
    "encounters",
    "referrals",
    "referral_events",
    "ledger",
    "checkpoints",
    # Eighth table: server-side dedup for at-least-once delivery (SPEC.md
    # section 5). Holds no clinical fact and adds no endpoint.
    "idempotency_keys",
}


def _table_names(engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).all()
    return {r[0] for r in rows}


def test_architecture_tables_exist(engine):
    assert EXPECTED_TABLES <= _table_names(engine)


def test_seven_ledger_bearing_and_registry_tables_are_declared(engine):
    """architecture.md section 3 names seven; idempotency_keys is the documented eighth."""
    assert len(EXPECTED_TABLES) == 8
    assert set(SQLModel.metadata.tables) >= EXPECTED_TABLES


def test_foreign_keys_are_enforced(engine, registered):
    """SQLite has foreign keys OFF by default; make_engine turns them on."""
    with pytest.raises(IntegrityError, match="FOREIGN KEY"), Session(engine) as s:
        s.add(
            Encounter(
                id=new_id("enc"),
                site_id="site-does-not-exist",
                device_kid=TEST_KID,
                quality_verdict="usable",
                image_sha256="a" * 64,
                model_version="test",
                device_seq=1,
                created_at=now_iso(),
            )
        )
        s.commit()


# ------------------------------------------------------- append-only triggers


def test_every_append_only_table_has_both_triggers(engine):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='trigger'")
        ).all()
    names = {r[0] for r in rows}
    for table in APPEND_ONLY_TABLES:
        assert f"trg_{table}_no_update" in names
        assert f"trg_{table}_no_delete" in names


def _seed_rows(session) -> dict[str, str]:
    enc_id = new_id("enc")
    ref_id = new_id("ref")
    session.add(
        Encounter(
            id=enc_id,
            site_id=TEST_SITE,
            device_kid=TEST_KID,
            quality_verdict="usable",
            image_sha256="b" * 64,
            dr_grade=2,
            prediction_set="[2]",
            model_version="test",
            device_seq=1,
            created_at=now_iso(),
        )
    )
    session.add(
        Referral(
            id=ref_id,
            encounter_id=enc_id,
            state="issued",
            created_at=now_iso(),
            updated_at=now_iso(),
        )
    )
    session.flush()
    session.add(
        ReferralEvent(
            id=new_id("rev"),
            referral_id=ref_id,
            from_state="",
            to_state="issued",
            created_at=now_iso(),
        )
    )
    session.add(
        LedgerEntry(
            seq=1,
            prev_hash="0" * 64,
            payload_hash="c" * 64,
            entry_hash="d" * 64,
            payload_json="{}",
            signer_kid=TEST_KID,
            signature="e" * 128,
            created_at=now_iso(),
        )
    )
    session.add(
        Checkpoint(
            seq=1,
            root_hash="d" * 64,
            signer_kid=TEST_KID,
            signature="f" * 128,
            created_at=now_iso(),
        )
    )
    session.commit()
    return {"encounter_id": enc_id, "referral_id": ref_id}


@pytest.mark.parametrize("table", APPEND_ONLY_TABLES)
def test_update_is_refused(engine, registered, table):
    with Session(engine) as session:
        _seed_rows(session)
    with engine.connect() as conn, pytest.raises(IntegrityError, match="append-only"):
        conn.execute(text(f"UPDATE {table} SET created_at = 'rewritten'"))


@pytest.mark.parametrize("table", APPEND_ONLY_TABLES)
def test_delete_is_refused(engine, registered, table):
    with Session(engine) as session:
        _seed_rows(session)
    with engine.connect() as conn, pytest.raises(IntegrityError, match="append-only"):
        conn.execute(text(f"DELETE FROM {table}"))


def test_referrals_is_deliberately_mutable(engine, registered):
    """`referrals.state` must advance; its history lives in referral_events."""
    with Session(engine) as session:
        ids = _seed_rows(session)
    with Session(engine) as session:
        referral = session.get(Referral, ids["referral_id"])
        referral.state = "contacted"
        session.add(referral)
        session.commit()
    with Session(engine) as session:
        assert session.get(Referral, ids["referral_id"]).state == "contacted"


def test_init_db_is_idempotent(tmp_path):
    from netra.db.engine import init_db

    path = str(tmp_path / "twice.db")
    init_db(path)
    init_db(path)  # CREATE TRIGGER IF NOT EXISTS, so this must not raise
