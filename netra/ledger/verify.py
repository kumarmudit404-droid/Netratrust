"""Re-walk the chain, recompute every hash, check every signature.

Run it directly:  `python -m netra.ledger.verify`

Four independent things are checked per entry, because each catches a different
class of tampering:

1. `seq` is contiguous from 1 - catches a DELETED entry.
2. `prev_hash` equals the previous entry's `entry_hash` - catches a REORDER or
   an insertion.
3. `payload_hash` equals SHA-256(rfc8785(payload_json)) - catches an EDITED
   payload. The payload is re-canonicalised rather than re-hashed as stored
   text, so non-canonical bytes are caught too.
4. The signature verifies over the 32-byte `entry_hash` - catches an editor who
   recomputed the hashes but does not hold the device's private key.

`first_bad_index` is the `seq` of the first entry that fails any of these. The
shape `{ok, first_bad_index}` is frozen in SPEC.md.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from sqlmodel import Session, select

from netra.db.models import Device, LedgerEntry
from netra.ledger.canonical import (
    entry_hash,
    payload_hash_of_stored,
)
from netra.ledger.keys import KeyStore, verify_signature


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    first_bad_index: int | None
    reason: str | None = None
    checked: int = 0

    def as_response(self) -> dict:
        """The frozen SPEC.md shape. `reason` is NOT part of the contract."""
        return {"ok": self.ok, "first_bad_index": self.first_bad_index}


def _public_key_hex(session: Session, kid: str, keystore: KeyStore) -> str | None:
    """Resolve a signer's public key: registered device first, then the keystore."""
    device = session.get(Device, kid)
    if device is not None:
        return device.ed25519_pub
    return keystore.known_public_hex(kid)


def verify(session: Session, keystore: KeyStore | None = None) -> VerifyResult:
    """Walk the whole chain. An empty chain is valid."""
    keystore = keystore or KeyStore()
    entries = session.exec(select(LedgerEntry).order_by(LedgerEntry.seq)).all()

    prev_entry_hash = "0" * 64
    for position, entry in enumerate(entries, start=1):
        if entry.seq != position:
            return VerifyResult(
                False,
                entry.seq,
                f"seq is not contiguous: expected {position}, found {entry.seq}",
                position - 1,
            )
        if entry.prev_hash != prev_entry_hash:
            return VerifyResult(
                False,
                entry.seq,
                "prev_hash does not match the previous entry_hash",
                position - 1,
            )

        try:
            recomputed_payload_hash = payload_hash_of_stored(entry.payload_json)
        # A blind catch is correct here: verify must REPORT a corrupted payload,
        # not crash on it. Anything rfc8785 or json raises on these bytes is
        # itself the finding, so narrowing the clause would turn a detected
        # tamper into a 500.
        except Exception as exc:  # noqa: BLE001
            return VerifyResult(
                False, entry.seq, f"payload is not canonicalisable: {exc}", position - 1
            )
        if recomputed_payload_hash != entry.payload_hash:
            return VerifyResult(
                False,
                entry.seq,
                "payload_hash does not match the stored payload",
                position - 1,
            )

        recomputed_entry_hash = entry_hash(entry.prev_hash, entry.payload_hash)
        if recomputed_entry_hash.hex() != entry.entry_hash:
            return VerifyResult(
                False,
                entry.seq,
                "entry_hash does not match prev_hash || payload_hash",
                position - 1,
            )

        pub_hex = _public_key_hex(session, entry.signer_kid, keystore)
        if pub_hex is None:
            return VerifyResult(
                False,
                entry.seq,
                f"unknown signer_kid {entry.signer_kid!r}",
                position - 1,
            )
        if not verify_signature(pub_hex, entry.signature, recomputed_entry_hash):
            return VerifyResult(
                False, entry.seq, "Ed25519 signature does not verify", position - 1
            )

        prev_entry_hash = entry.entry_hash

    return VerifyResult(True, None, None, len(entries))


def main(argv: list[str] | None = None) -> int:
    from netra.db.engine import init_db

    argv = sys.argv[1:] if argv is None else argv
    engine = init_db(argv[0] if argv else None)
    with Session(engine) as session:
        result = verify(session)
    if result.ok:
        print(f"ok: {result.checked} entries verified")
        return 0
    print(
        f"FAILED at index {result.first_bad_index}: {result.reason} "
        f"({result.checked} entries verified before it)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
