"""Appending to the hash chain.

`append` runs inside the CALLER's transaction and does not commit. That is what
makes "every decision is appended to the ledger before it is returned to the
caller" (BUILD_RULES.md, rules.md section 4.3) true rather than aspirational: the
encounter row and its ledger entry commit together or not at all, so no
response can describe a decision that is missing from the ledger.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from netra.db.models import GENESIS_PREV_HASH, LedgerEntry
from netra.db.util import now_iso
from netra.ledger.canonical import (
    MAX_SAFE_INT,
    canonical_bytes,
    entry_hash,
    payload_hash,
)
from netra.ledger.keys import KeyStore


def current_head(session: Session) -> LedgerEntry | None:
    """The highest-`seq` entry, or None on an empty chain."""
    return session.exec(
        select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(1)
    ).first()


def append(
    session: Session,
    payload: dict[str, Any],
    signer_kid: str,
    keystore: KeyStore,
) -> LedgerEntry:
    """Append one entry. Returns the flushed row; the caller commits.

    SPEC.md section 4:
      payload_hash = SHA-256(rfc8785.dumps(payload))
      entry_hash   = SHA-256(prev_hash || payload_hash)
      signature    = Ed25519(entry_hash)   -- the 32-byte hash, not the payload
    """
    head = current_head(session)
    seq = 1 if head is None else head.seq + 1
    if seq > MAX_SAFE_INT:
        raise OverflowError("ledger seq would exceed 2^53-1")
    prev_hash = GENESIS_PREV_HASH if head is None else head.entry_hash

    body = canonical_bytes(payload)  # validates: no floats, no oversized ints
    p_hash = payload_hash(payload)
    e_hash = entry_hash(prev_hash, p_hash)

    entry = LedgerEntry(
        seq=seq,
        prev_hash=prev_hash,
        payload_hash=p_hash,
        entry_hash=e_hash.hex(),
        payload_json=body.decode("utf-8"),
        signer_kid=signer_kid,
        signature=keystore.sign(signer_kid, e_hash),
        created_at=now_iso(),
    )
    session.add(entry)
    session.flush()
    return entry
