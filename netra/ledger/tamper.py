"""The tamper demo (SPEC.md section 7, T-17). NOT reachable from the API.

    python -m netra.ledger.tamper --seq 2

Corrupting an entry requires dropping that table's append-only trigger, doing
the UPDATE, and putting the trigger back. That is the honest shape of the
threat: the triggers stop the APPLICATION from rewriting history, but someone
with direct database access can remove them. The hash chain and the Ed25519
signatures are what survive that, and this module exists to show it rather
than assert it.

There is deliberately no endpoint for this. The nine endpoints in SPEC.md are
frozen, and a "corrupt the ledger" route would be a liability in a deployed
build. The demo presenter runs this module while the Ledger view polls
`GET /v1/ledger/verify`.
"""

from __future__ import annotations

import argparse
import json
import sys

from sqlmodel import Session

from netra.db.engine import (
    drop_append_only_triggers,
    init_db,
    install_append_only_triggers,
)
from netra.db.models import LedgerEntry


def corrupt_payload(engine, seq: int, field: str = "tampered_by") -> str:
    """Edit one entry's stored payload in place. Returns the new payload text.

    The edit keeps `payload_hash` and `signature` untouched, which is what a
    naive tamperer does, so verify catches it at check 3 (payload hash).
    """
    with Session(engine) as session:
        entry = session.get(LedgerEntry, seq)
        if entry is None:
            raise SystemExit(f"no ledger entry at seq {seq}")
        payload = json.loads(entry.payload_json)
        payload[field] = "demo"
        new_text = json.dumps(payload, separators=(",", ":"), sort_keys=True)

    drop_append_only_triggers(engine, "ledger")
    try:
        with Session(engine) as session:
            entry = session.get(LedgerEntry, seq)
            entry.payload_json = new_text
            session.add(entry)
            session.commit()
    finally:
        install_append_only_triggers(engine)
    return new_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Corrupt one ledger entry in place.")
    parser.add_argument("--seq", type=int, required=True, help="entry to corrupt")
    parser.add_argument("--db", default=None, help="SQLite path (default: $NETRA_DB)")
    args = parser.parse_args(argv)

    engine = init_db(args.db)
    corrupt_payload(engine, args.seq)

    from netra.ledger.verify import verify

    with Session(engine) as session:
        result = verify(session)
    print(
        f"corrupted seq {args.seq}; verify -> "
        f"ok={result.ok} first_bad_index={result.first_bad_index} ({result.reason})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
