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


def test_a_second_run_refuses_rather_than_doubling_the_counts(seeded, seed_dev, capsys):
    code = seed_dev.main(["--db", str(seeded)])
    assert code == 2
    assert "already exists" in capsys.readouterr().err


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
