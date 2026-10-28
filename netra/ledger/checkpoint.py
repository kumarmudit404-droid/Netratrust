"""Signed checkpoints: the Certificate-Transparency idea without the tree.

A checkpoint is a signature over `(seq, root_hash, created_at)`. An external
party who kept yesterday's checkpoint can prove that history was rewritten,
which a bare chain cannot: a tamperer who holds the database can re-sign every
entry from the edit forwards, but cannot retract a checkpoint someone else
already holds.

SPEC.md section 4 says explicitly: do this (~30 minutes), skip the Merkle tree
(~1 day). At this scale a running chain is sufficient.
"""

from __future__ import annotations

from sqlmodel import Session, select

from netra.db.models import GENESIS_PREV_HASH, Checkpoint
from netra.db.util import now_iso
from netra.ledger.canonical import canonical_bytes
from netra.ledger.chain import current_head
from netra.ledger.keys import SERVER_KID, KeyStore, verify_signature


def signed_bytes(seq: int, root_hash: str, created_at: str) -> bytes:
    """The bytes a checkpoint signature covers.

    Canonical JSON over exactly the three attested fields, so an external
    holder can reconstruct them from the API response alone.
    """
    return canonical_bytes(
        {"created_at": created_at, "root_hash": root_hash, "seq": seq}
    )


def latest(session: Session) -> Checkpoint | None:
    return session.exec(
        select(Checkpoint).order_by(Checkpoint.seq.desc()).limit(1)
    ).first()


def create(
    session: Session, keystore: KeyStore, signer_kid: str = SERVER_KID
) -> Checkpoint:
    """Sign the current head. Does not commit; the caller does."""
    head = current_head(session)
    seq = 0 if head is None else head.seq
    root_hash = GENESIS_PREV_HASH if head is None else head.entry_hash
    created_at = now_iso()

    existing = session.get(Checkpoint, seq)
    if existing is not None:
        # `checkpoints` is append-only, so re-signing the same head would need
        # an UPDATE the triggers refuse. Returning the stored one is also the
        # honest answer: the head has not moved.
        return existing

    checkpoint = Checkpoint(
        seq=seq,
        root_hash=root_hash,
        signer_kid=signer_kid,
        signature=keystore.sign(signer_kid, signed_bytes(seq, root_hash, created_at)),
        created_at=created_at,
    )
    session.add(checkpoint)
    session.flush()
    return checkpoint


def get_or_create(session: Session, keystore: KeyStore) -> Checkpoint:
    """The checkpoint for the current head, signing a new one if the head moved."""
    head = current_head(session)
    head_seq = 0 if head is None else head.seq
    existing = latest(session)
    if existing is not None and existing.seq == head_seq:
        return existing
    return create(session, keystore)


def verify_checkpoint(checkpoint: Checkpoint, pub_hex: str) -> bool:
    """Check a checkpoint signature. Used by the tests and by any external holder."""
    return verify_signature(
        pub_hex,
        checkpoint.signature,
        signed_bytes(checkpoint.seq, checkpoint.root_hash, checkpoint.created_at),
    )
