"""The dev seed script, which the demo depends on.

A seeded database that fails `GET /v1/ledger/verify` would break the one claim
the demo exists to make, and a seed that quietly skips a site leaves the Sites
view empty on stage. Both are cheap to catch here and expensive to discover
during a three-minute demo.

`scripts/` is not a package, so the script is loaded by path.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest
from sqlmodel import Session, select

from netra.db.engine import make_engine
from netra.db.models import Encounter, Referral, Site
from netra.ledger.verify import verify

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "seed_dev.py"


@pytest.fixture(scope="module")
def seed_dev():
    spec = importlib.util.spec_from_file_location("seed_dev", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["seed_dev"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def seeded(seed_dev, tmp_path_factory):
    """Run the seed once and let every assertion read the same database.

    Module-scoped on purpose: seeding posts ~120 encounters through the real
    app, and doing that per test would dominate the suite's runtime.
    """
    tmp = tmp_path_factory.mktemp("seed")
    db = tmp / "netra.db"
    code = seed_dev.main(["--db", str(db), "--keys", str(tmp / "keys")])
    assert code == 0
    return db


def test_the_seeded_chain_verifies(seeded):
    """The whole point. Seeding goes through the API, so the chain is real."""
    with Session(make_engine(str(seeded))) as session:
        result = verify(session)
    assert result.ok, result.reason
    assert result.checked > 0


def test_every_site_is_created(seeded, seed_dev):
    with Session(make_engine(str(seeded))) as session:
        ids = set(session.exec(select(Site.id)).all())
    assert ids == {s.site_id for s in seed_dev.SITES}


def test_the_demo_site_the_ui_posts_to_exists(seeded, seed_dev):
    """`Capture.tsx` hardcodes a site id; without it every capture is a 404."""
    with Session(make_engine(str(seeded))) as session:
        assert session.get(Site, seed_dev.DEMO_SITE) is not None


def test_each_site_gets_the_encounters_its_spec_asks_for(seeded, seed_dev):
    with Session(make_engine(str(seeded))) as session:
        for spec in seed_dev.SITES:
            rows = session.exec(
                select(Encounter).where(Encounter.site_id == spec.site_id)
            ).all()
            assert len(rows) == spec.n, spec.site_id
            rejects = [r for r in rows if r.quality_verdict == "reject"]
            assert len(rejects) == spec.reject_n, spec.site_id


def test_no_rejected_encounter_carries_a_grade(seeded):
    """A failed quality gate is "no result", never a negative DR result."""
    with Session(make_engine(str(seeded))) as session:
        rejects = session.exec(
            select(Encounter).where(Encounter.quality_verdict == "reject")
        ).all()
    assert rejects, "the seed is meant to include rejects"
    for r in rejects:
        assert r.dr_grade is None
        assert r.prediction_set is None
        # A reject is not an abstention either: nothing was graded, so there
        # was nothing to abstain from.
        assert r.abstained is False


def test_one_site_is_below_the_n_30_floor(seeded, seed_dev):
    """The no-bare-percentage rule cannot be demonstrated if every site clears it."""
    assert any(s.n < 30 for s in seed_dev.SITES)
    assert any(s.n >= 30 for s in seed_dev.SITES)


def test_there_is_a_referral_part_way_through_the_state_machine(seeded):
    with Session(make_engine(str(seeded))) as session:
        referrals = session.exec(select(Referral)).all()
    assert len(referrals) == 1
    # Left mid-machine so the Referrals view has moves still available.
    assert referrals[0].state == "contacted"


# --------------------------------------------------------------- idempotency
#
# On Fly the database is on a PERSISTENT volume, so a re-run during a redeploy
# is the normal case, not an edge case. A doubled chain is still a VALID chain -
# `verify` returns ok:true on it - so nothing downstream would catch this. The
# demo would simply quote twice the real figures.


def _census(db: pathlib.Path) -> dict[str, int]:
    """Row counts for every table seeding writes to."""
    from netra.db.models import Device, LedgerEntry, ReferralEvent, Site

    engine = make_engine(str(db))
    try:
        with Session(engine) as session:
            return {
                model.__name__: len(session.exec(select(model)).all())
                for model in (
                    Site,
                    Device,
                    Encounter,
                    Referral,
                    ReferralEvent,
                    LedgerEntry,
                )
            }
    finally:
        # Dispose, or the pooled connection keeps the file open and a later
        # --force cannot unlink it on Windows.
        engine.dispose()


def _genesis_links(db: pathlib.Path) -> int:
    from netra.db.models import GENESIS_PREV_HASH, LedgerEntry

    engine = make_engine(str(db))
    try:
        with Session(engine) as session:
            rows = session.exec(
                select(LedgerEntry).where(LedgerEntry.prev_hash == GENESIS_PREV_HASH)
            ).all()
    finally:
        engine.dispose()
    return len(rows)


@pytest.fixture
def own_seed(seed_dev, tmp_path):
    """A database this test alone owns, so it can re-run the seed against it."""
    db = tmp_path / "netra.db"
    keys = tmp_path / "keys"
    assert seed_dev.main(["--db", str(db), "--keys", str(keys)]) == 0
    return db, keys


def test_a_second_run_exits_zero_and_changes_nothing(own_seed, seed_dev):
    """The property the deploy depends on: re-running is a no-op, not an error.

    Exit 0 matters as much as the no-op. A non-zero exit here would fail a
    release command that seeds on every boot, so the honest answer to "seed an
    already-seeded database" is "done, nothing to do".
    """
    db, keys = own_seed
    before = _census(db)

    assert seed_dev.main(["--db", str(db), "--keys", str(keys)]) == 0

    assert _census(db) == before


def test_seeding_twice_leaves_one_verifying_chain_of_the_same_length(
    own_seed, seed_dev
):
    db, keys = own_seed
    with Session(make_engine(str(db))) as session:
        before = verify(session)
    assert before.ok

    seed_dev.main(["--db", str(db), "--keys", str(keys)])

    with Session(make_engine(str(db))) as session:
        after = verify(session)
    assert after.ok, after.reason
    # Same number of entries checked: the chain did not grow and did not fork.
    assert after.checked == before.checked


def test_a_second_run_never_creates_a_second_genesis(own_seed, seed_dev):
    """Two genesis links would mean a second chain started on top of the first."""
    db, keys = own_seed
    assert _genesis_links(db) == 1

    seed_dev.main(["--db", str(db), "--keys", str(keys)])

    assert _genesis_links(db) == 1


def test_a_second_run_says_what_is_there_rather_than_going_quiet(
    own_seed, seed_dev, capsys
):
    db, keys = own_seed
    seed_dev.main(["--db", str(db), "--keys", str(keys)])
    out = capsys.readouterr().out
    assert "already seeded" in out
    assert "verify       ok" in out


def test_an_existing_but_empty_database_is_seeded_in_place(seed_dev, tmp_path):
    """What a Fly volume looks like after the API has booted and nothing posted.

    `init_db` runs in the app's lifespan, so the file exists with tables and no
    rows. Reading that as "already seeded" would leave the demo with an empty
    ledger, which is the failure this whole section exists to prevent.
    """
    from netra.db.engine import init_db

    db = tmp_path / "netra.db"
    init_db(str(db))
    assert db.exists()

    assert seed_dev.main(["--db", str(db), "--keys", str(tmp_path / "keys")]) == 0

    census = _census(db)
    assert census["Encounter"] == sum(spec.n for spec in seed_dev.SITES)
    with Session(make_engine(str(db))) as session:
        assert verify(session).ok


def test_a_tampered_database_is_reported_and_left_alone(own_seed, seed_dev, capsys):
    """`netra.ledger.tamper` breaks the chain ON PURPOSE during the demo.

    Re-seeding over it would destroy the evidence the operator is looking at,
    and appending to a broken chain would hide the break behind valid entries.
    """
    db, keys = own_seed
    before = _census(db)

    import os

    os.environ["NETRA_KEYS_DIR"] = str(keys)
    from netra.ledger import tamper

    assert tamper.main(["--seq", "50", "--db", str(db)]) == 0

    assert seed_dev.main(["--db", str(db), "--keys", str(keys)]) == 1
    assert "VERIFY FAILED" in capsys.readouterr().err
    # Nothing appended: the break stays visible at the index it happened.
    assert _census(db) == before


def test_force_resets_to_the_same_size_rather_than_doubling(own_seed, seed_dev):
    db, keys = own_seed
    before = _census(db)

    assert seed_dev.main(["--db", str(db), "--keys", str(keys), "--force"]) == 0

    assert _census(db) == before
    assert _genesis_links(db) == 1


def test_force_on_a_missing_database_is_not_an_error(seed_dev, tmp_path):
    db = tmp_path / "netra.db"
    assert (
        seed_dev.main(["--db", str(db), "--keys", str(tmp_path / "k"), "--force"]) == 0
    )


def test_the_seed_is_reproducible(seed_dev, tmp_path):
    """Same seed, same database - so a rehearsed demo matches the real one."""
    first = tmp_path / "a.db"
    second = tmp_path / "b.db"
    assert seed_dev.main(["--db", str(first), "--keys", str(tmp_path / "k1")]) == 0
    assert seed_dev.main(["--db", str(second), "--keys", str(tmp_path / "k2")]) == 0

    def fingerprint(db: pathlib.Path) -> list[str]:
        with Session(make_engine(str(db))) as session:
            rows = session.exec(select(Encounter)).all()
        # Joined into strings because `dr_grade` is None for a reject and a
        # tuple holding None is not sortable against one holding an int.
        return sorted(
            f"{e.site_id}|{e.quality_verdict}|{e.dr_grade}|{e.abstained}|{e.image_sha256}"
            for e in rows
        )

    # Ids are random per run, so compare the decisions rather than the rows.
    assert fingerprint(first) == fingerprint(second)


def test_force_is_safe_while_something_else_holds_the_database(own_seed, seed_dev):
    """The reset must be visible to a connection that was already open.

    This is why `--force` empties the tables instead of unlinking the file. A
    reset is usually run with the API up, and deleting the file would either
    fail (Windows holds it) or silently succeed and leave the running server
    reading an unlinked inode while the seed filled a different file at the
    same path - two databases, one path, no error.
    """
    from netra.db.engine import make_engine
    from netra.db.models import Encounter

    db, keys = own_seed
    holder = make_engine(str(db))  # stands in for the running uvicorn
    try:
        with Session(holder) as session:
            before = session.exec(select(Encounter)).all()
        assert before

        assert seed_dev.main(["--db", str(db), "--keys", str(keys), "--force"]) == 0

        # Same engine, same file, and it sees the re-seeded rows.
        with Session(holder) as session:
            after = session.exec(select(Encounter)).all()
        assert len(after) == len(before)
        assert {e.id for e in after} != {e.id for e in before}
    finally:
        holder.dispose()


def test_force_leaves_a_verifying_chain_and_the_append_only_triggers_back(
    own_seed, seed_dev
):
    """The reset drops the triggers to empty the tables; it must put them back."""
    from sqlalchemy import text

    from netra.db.engine import make_engine
    from netra.db.models import APPEND_ONLY_TABLES

    db, keys = own_seed
    assert seed_dev.main(["--db", str(db), "--keys", str(keys), "--force"]) == 0

    engine = make_engine(str(db))
    try:
        with Session(engine) as session:
            assert verify(session).ok
            names = set(
                session.exec(
                    text("SELECT name FROM sqlite_master WHERE type='trigger'")
                ).scalars()
            )
    finally:
        engine.dispose()

    for table in APPEND_ONLY_TABLES:
        for op in ("update", "delete"):
            assert f"trg_{table}_no_{op}" in names, f"{table}/{op} trigger is missing"
