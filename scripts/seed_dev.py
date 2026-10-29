"""Seed a development database so the demo has something to show.

    python scripts/seed_dev.py                 # writes ./netra.db
    python scripts/seed_dev.py --db demo.db    # somewhere else
    python scripts/seed_dev.py --force         # overwrite a seeded database

Every clinical fact is created by calling the REAL endpoints through a
`TestClient` over the real app, not by inserting rows. That is the whole point:
a row written straight into `ledger` would have no valid hash chain, so a
hand-seeded database would fail `GET /v1/ledger/verify` and the one thing the
demo has to prove would be broken by its own fixtures. Seeding through the API
means the seeded chain verifies, and this script ends by checking that it does.

Sites are the exception: there is no endpoint that creates one. The nine
endpoints in SPEC.md are frozen and none of them is `POST /v1/sites`, because
site provisioning is an out-of-band administrative act, not a clinical
decision. `sites` is not a ledger-bearing table and nothing is appended for it.

The four sites are chosen to make the Sites view tell the truth rather than to
look good:

| site    | n   | what it demonstrates                                   |
|---------|-----|--------------------------------------------------------|
| site-07 | 40  | the demo site the UI is pointed at; audit PASSES       |
| site-03 | 34  | a second passing site, so pooled is not one site       |
| site-12 | 12  | **n < 30** - the no-bare-percentage rule fires here    |
| site-21 | 31  | drift flagged, so the audit FAILS and stays unpinned   |

site-12 is deliberately under the floor. CLAUDE.md forbids a bare percentage
for n < 30, and a demo where every site clears the floor never shows the rule
working.

IDEMPOTENT
----------
Running this twice must not append a second copy of the chain. On Fly the
database lives on a PERSISTENT volume, so a re-run during a redeploy would
double every count and leave the demo quoting twice the real figures, with
`GET /v1/ledger/verify` still cheerfully returning ok:true because a doubled
chain is a perfectly valid chain.

So the decision is made on the database's CONTENTS, never on whether the file
exists (the API's own `init_db` creates an empty file on first boot):

- populated and the chain verifies  -> print what is there and exit 0, writing
                                       nothing
- populated and verify FAILS        -> exit 1 and touch nothing. The chain is
                                       the evidence, and `netra.ledger.tamper`
                                       breaks it on purpose during the demo;
                                       silently re-seeding would destroy what
                                       the operator is looking at
- empty, or no file at all          -> seed it
- `--force`                         -> delete it first, then seed
"""

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import random
import sys
import uuid
from typing import NamedTuple

# The project root, so `python scripts/seed_dev.py` works from anywhere.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

#: The seed from `scripts/make_splits.py`. Reused so two runs of this script
#: produce the same database and a demo is reproducible.
SEED = 20261027

MODEL_VERSION = "simulated-gate@seed"


class SiteSpec:
    """One seeded site: how many images, and how they came out."""

    def __init__(
        self,
        site_id: str,
        name: str,
        region: str,
        n: int,
        reject_n: int,
        abstain_n: int,
        referable_n: int,
        drift: bool = False,
    ) -> None:
        self.site_id = site_id
        self.name = name
        self.region = region
        self.n = n
        self.reject_n = reject_n
        self.abstain_n = abstain_n
        self.referable_n = referable_n
        self.drift = drift

    @property
    def admitted_n(self) -> int:
        return self.n - self.reject_n


SITES = [
    SiteSpec("site-03", "Chikkaballapur camp", "south", 34, 5, 3, 6),
    SiteSpec("site-07", "Kolar camp", "south", 40, 7, 4, 8),
    SiteSpec("site-12", "Hoskote outreach", "south", 12, 2, 1, 2),
    SiteSpec("site-21", "Doddaballapur camp", "south", 31, 11, 5, 7, drift=True),
]

#: The demo site. `netra/ui/src/routes/Capture.tsx` posts to this id, so if it
#: is missing every capture is a 404.
DEMO_SITE = "site-07"


def _image_hash(site_id: str, i: int) -> str:
    """A stable 64-hex stand-in for an image that was never uploaded.

    There is no image here and there never will be - SPEC.md says only the
    hash travels. Hashing a label keeps the field honest about being synthetic
    while still being a real SHA-256.
    """
    return hashlib.sha256(f"seed:{site_id}:{i}".encode()).hexdigest()


def _cases(spec: SiteSpec, rng: random.Random) -> list[dict]:
    """The encounter bodies for one site, shuffled so the order is not a tell."""
    cases: list[dict] = []

    for _ in range(spec.reject_n):
        # A reject carries NO prediction set. A failed gate is "no result",
        # never a negative DR result, and the API returns 422 if a set arrives.
        cases.append(
            {
                "gate_verdict": "reject",
                "cause": rng.choice(["focus", "exposure", "fov_mask"]),
                "prediction_set": None,
            }
        )
    for _ in range(spec.abstain_n):
        # {1,2} spans the refer / do-not-refer boundary, so this abstains.
        cases.append(
            {"gate_verdict": "usable", "cause": None, "prediction_set": [1, 2]}
        )
    for _ in range(spec.referable_n):
        cases.append(
            {
                "gate_verdict": "usable",
                "cause": None,
                "prediction_set": [rng.choice([2, 3, 4])],
            }
        )
    while len(cases) < spec.n:
        # The rest are confidently not referable, which is what most screening
        # images actually are.
        verdict = "borderline" if rng.random() < 0.15 else "usable"
        cases.append(
            {
                "gate_verdict": verdict,
                "cause": "exposure" if verdict == "borderline" else None,
                "prediction_set": [rng.choice([0, 0, 0, 1])],
            }
        )

    rng.shuffle(cases)
    return cases[: spec.n]


def _post(client, path: str, body: dict) -> dict:
    """POST with a fresh Idempotency-Key, and refuse to continue on an error.

    A seed script that swallows a 422 leaves a half-populated database that
    looks fine until the demo, so this is loud.
    """
    res = client.post(path, json=body, headers={"Idempotency-Key": str(uuid.uuid4())})
    if res.status_code >= 400:
        raise SystemExit(f"{path} returned {res.status_code}: {res.text}")
    return res.json()


def _patch(client, path: str, body: dict) -> dict:
    res = client.patch(path, json=body, headers={"Idempotency-Key": str(uuid.uuid4())})
    if res.status_code >= 400:
        raise SystemExit(f"{path} returned {res.status_code}: {res.text}")
    return res.json()


def create_sites(db_path: str) -> None:
    """Insert the site rows. The only thing here that bypasses the API."""
    from sqlmodel import Session

    from netra.db.engine import init_db
    from netra.db.models import Site
    from netra.db.util import now_iso

    engine = init_db(db_path)
    try:
        with Session(engine) as session:
            for spec in SITES:
                if session.get(Site, spec.site_id) is None:
                    session.add(
                        Site(
                            id=spec.site_id,
                            name=spec.name,
                            region=spec.region,
                            created_at=now_iso(),
                        )
                    )
            session.commit()
    finally:
        # Windows will not unlink a file that a pooled connection still holds,
        # so --force would fail with WinError 32 after this ran in-process.
        engine.dispose()


class DbState(NamedTuple):
    """What is already in a database, as far as seeding is concerned."""

    ledger_entries: int
    encounters: int
    #: Entries whose `prev_hash` is the genesis value. Exactly one in a sound
    #: chain. Two would mean a second chain was started on top of the first.
    genesis_links: int
    verify_ok: bool
    first_bad_index: int | None
    #: Whether every site has exactly the encounter count its spec asks for.
    complete: bool

    @property
    def is_populated(self) -> bool:
        return bool(self.ledger_entries or self.encounters)


def inspect_db(db_path: str, keys_dir: str) -> DbState:
    """Read-only look at an existing database. Appends nothing.

    `init_db` is called because it is idempotent and because the file may exist
    with no tables in it - a volume where the API started once and nothing was
    ever posted. Creating the tables to count zero rows is not a write anyone
    needs to care about; appending a second chain would be.
    """
    from netra.db.engine import init_db

    engine = init_db(db_path)
    try:
        state = _read_state(engine, keys_dir)
    finally:
        engine.dispose()  # see create_sites: Windows holds the file otherwise
    return state


def _read_state(engine, keys_dir: str) -> DbState:
    from sqlmodel import Session, func, select

    from netra.db.models import GENESIS_PREV_HASH, Encounter, LedgerEntry
    from netra.ledger.keys import KeyStore
    from netra.ledger.verify import verify

    with Session(engine) as session:
        entries = session.exec(select(func.count()).select_from(LedgerEntry)).one()
        encounters = session.exec(select(func.count()).select_from(Encounter)).one()
        genesis = session.exec(
            select(func.count())
            .select_from(LedgerEntry)
            .where(LedgerEntry.prev_hash == GENESIS_PREV_HASH)
        ).one()
        complete = all(
            session.exec(
                select(func.count())
                .select_from(Encounter)
                .where(Encounter.site_id == spec.site_id)
            ).one()
            == spec.n
            for spec in SITES
        )
        # The keystore is only a FALLBACK for verify: a signer is resolved from
        # the `devices` table first, so a database seeded under a different
        # keys directory still verifies.
        result = verify(session, KeyStore(keys_dir))

    return DbState(
        ledger_entries=int(entries),
        encounters=int(encounters),
        genesis_links=int(genesis),
        verify_ok=result.ok,
        first_bad_index=result.first_bad_index,
        complete=bool(complete),
    )


def report_already_seeded(db_path: str, state: DbState) -> int:
    """Say what is there and leave it alone. Exit 0 if the chain is sound."""
    print(f"database     {db_path} is already seeded")
    print(f"ledger       {state.ledger_entries} entries, {state.encounters} encounters")

    if not state.verify_ok:
        print(
            f"VERIFY FAILED at index {state.first_bad_index}. Refusing to touch "
            f"this database: the chain is the evidence, and `netra.ledger.tamper` "
            f"breaks it ON PURPOSE for the demo. Re-seed deliberately with "
            f"--force if that is really what you want.",
            file=sys.stderr,
        )
        return 1

    print("verify       ok")
    if not state.complete:
        print(
            "note: the encounter counts do not match SITES, so this was seeded "
            "by a different revision or a run that stopped early. Pass --force "
            "to reset it."
        )
    print(
        "nothing to do - seeding again would append a SECOND copy of the chain, "
        "double every count, and leave the demo reading twice the real figures"
    )
    return 0


def seed(db_path: str, keys_dir: str) -> int:
    """Fill the database through the real app. Returns a process exit code."""
    os.environ["NETRA_DB"] = db_path
    os.environ["NETRA_KEYS_DIR"] = keys_dir

    create_sites(db_path)

    from fastapi.testclient import TestClient

    from netra.api.main import create_app

    rng = random.Random(SEED)
    referable_encounter: str | None = None

    with TestClient(create_app()) as client:
        for spec in SITES:
            # The DEVICE owns device_seq; the server owns ledger seq. It starts
            # at 1 per site because each site has its own capture device.
            for device_seq, case in enumerate(_cases(spec, rng), start=1):
                body = {
                    "image_sha256": _image_hash(spec.site_id, device_seq),
                    "model_version": MODEL_VERSION,
                    "site_id": spec.site_id,
                    "device_seq": device_seq,
                    **case,
                }
                out = _post(client, "/v1/encounters", body)
                # Keep one referable encounter at the demo site to refer from.
                if (
                    referable_encounter is None
                    and spec.site_id == DEMO_SITE
                    and case["prediction_set"] in ([2], [3], [4])
                ):
                    referable_encounter = out["encounter_id"]

            # The audit's `passed` is computed server-side from the counts and
            # the drift flag; it is not ours to assert. Agreement counts are
            # synthetic and labelled as such in the printout.
            _post(
                client,
                f"/v1/sites/{spec.site_id}/audit",
                {
                    "pinned_model_version": MODEL_VERSION,
                    "gradable_k": spec.admitted_n,
                    "gradable_n": spec.n,
                    "agreement_k": max(spec.admitted_n - 3, 0),
                    "agreement_n": spec.admitted_n,
                    "grade_counts": {
                        "0": spec.n - spec.referable_n,
                        "3": spec.referable_n,
                    },
                    "drift_flag": spec.drift,
                },
            )

        if referable_encounter is None:
            raise SystemExit(
                f"no referable encounter was created at {DEMO_SITE}; "
                f"the demo has nothing to refer from"
            )

        # One referral, advanced two steps. Left at `contacted` on purpose: the
        # Referrals view is then a live state machine with moves still
        # available, rather than a finished record with every button disabled.
        ref = _post(client, "/v1/referrals", {"encounter_id": referable_encounter})
        rid = ref["referral_id"]
        _patch(
            client,
            f"/v1/referrals/{rid}",
            {"to_state": "contact_attempted", "channel": "phone", "reason": None},
        )
        _patch(
            client,
            f"/v1/referrals/{rid}",
            {"to_state": "contacted", "channel": None, "reason": None},
        )

        # Everything above went through the ledger. Prove the chain is intact
        # rather than assuming it: a seeded database that fails verify is worse
        # than an empty one, because the demo's headline claim is verify.
        verify = client.get("/v1/ledger/verify").json()
        checkpoint = client.get("/v1/ledger/checkpoint").json()
        depth = client.get("/v1/queue/depth").json()

    print(f"database     {db_path}")
    print(f"keys         {keys_dir}")
    for spec in SITES:
        flag = "  drift flagged" if spec.drift else ""
        floor = "  n < 30, rate suppressed" if spec.n < 30 else ""
        print(
            f"  {spec.site_id}  n={spec.n:3d}  admitted={spec.admitted_n:3d}"
            f"  abstained={spec.abstain_n:2d}{flag}{floor}"
        )
    print(f"referral     {rid} at contacted (from {referable_encounter})")
    print(
        f"ledger       {checkpoint['idx']} entries, head {checkpoint['head_hash'][:16]}..."
    )
    print(f"queue        queued={depth['queued']} synced={depth['synced']}")
    print("agreement counts are SYNTHETIC - they are not a measurement")

    if not verify["ok"]:
        print(
            f"VERIFY FAILED at index {verify['first_bad_index']}",
            file=sys.stderr,
        )
        return 1
    print("verify       ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--db",
        default=os.environ.get("NETRA_DB", "netra.db"),
        help="SQLite path to write (default: $NETRA_DB or netra.db)",
    )
    parser.add_argument(
        "--keys",
        default=os.environ.get("NETRA_KEYS_DIR", "keys"),
        help="device keystore directory (default: $NETRA_KEYS_DIR or keys)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="DELETE an existing database and seed it from scratch",
    )
    args = parser.parse_args(argv)

    db = pathlib.Path(args.db)

    if args.force and db.exists():
        print(f"--force: removing {db} ({db.stat().st_size} bytes)")
        try:
            db.unlink()
        except OSError as exc:
            # Windows refuses to unlink a file another handle still holds, and
            # a half-answered traceback is a bad thing to hand an operator who
            # is resetting a demo.
            print(
                f"could not remove {db}: {exc}. Stop anything using it "
                f"(the API, a sqlite3 shell) and run this again.",
                file=sys.stderr,
            )
            return 3

    # The decision is made on what is IN the database, not on whether the file
    # exists. On Fly the volume is persistent and the API's own `init_db`
    # creates the file on first boot, so "the file is there" says nothing about
    # whether anything has been seeded - and treating it as "already seeded"
    # would leave the demo with an empty ledger.
    if db.exists():
        state = inspect_db(str(db), args.keys)
        if state.is_populated:
            return report_already_seeded(str(db), state)
        print(f"{db} exists but holds no entries; seeding it in place")

    return seed(str(db), args.keys)


if __name__ == "__main__":
    raise SystemExit(main())
