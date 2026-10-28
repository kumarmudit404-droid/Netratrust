"""T-03: hash chain, Ed25519, rfc8785 on write and verify.

The mandatory test is `test_tamper_is_detected_and_reports_the_bad_index`:
append three entries, corrupt one, assert verify fails AND names the index. A
verify that has only ever returned ok:true demonstrates nothing.
"""

from __future__ import annotations

import hashlib
import json

import pytest
import rfc8785
from sqlmodel import Session

from netra.db.engine import drop_append_only_triggers, install_append_only_triggers
from netra.db.models import GENESIS_PREV_HASH, LedgerEntry
from netra.ledger import canonical
from netra.ledger.canonical import MAX_SAFE_INT, PayloadError
from netra.ledger.chain import append, current_head
from netra.ledger.keys import KeyStore, public_hex, verify_signature
from netra.ledger.tamper import corrupt_payload
from netra.ledger.verify import verify
from tests.conftest import TEST_KID


def _payload(n: int) -> dict:
    return {
        "type": "test",
        "created_at": f"2026-10-28T09:00:0{n}Z",
        "encounter_id": f"enc-{n}",
        "device_seq": n,
    }


def _append_three(session, keystore) -> list[LedgerEntry]:
    entries = [append(session, _payload(n), TEST_KID, keystore) for n in (1, 2, 3)]
    session.commit()
    return entries


# ------------------------------------------------------------ canonicalisation


def test_floats_are_rejected_not_silently_normalised():
    """rfc8785 turns 1.0 into 1 without complaint; we must refuse it first."""
    assert rfc8785.dumps({"n": 1.0}) == b'{"n":1}'
    assert json.dumps({"n": 1.0}) == '{"n": 1.0}'
    with pytest.raises(PayloadError, match="floats are banned"):
        canonical.canonical_bytes({"score": 0.87})


def test_nested_floats_are_rejected_with_a_path():
    with pytest.raises(PayloadError, match=r"payload\.sets\[1\]\.p"):
        canonical.canonical_bytes({"sets": [{"p": "0.1"}, {"p": 0.2}]})


def test_booleans_survive_the_float_check():
    assert canonical.canonical_bytes({"abstained": True}) == b'{"abstained":true}'


def test_integers_above_2_53_are_rejected():
    with pytest.raises(PayloadError, match="exceeds 2\\^53"):
        canonical.canonical_bytes({"seq": MAX_SAFE_INT + 1})
    canonical.canonical_bytes({"seq": MAX_SAFE_INT})  # the boundary is allowed


def test_canonicalisation_is_key_order_independent():
    a = canonical.payload_hash({"a": "1", "b": "2"})
    b = canonical.payload_hash({"b": "2", "a": "1"})
    assert a == b


def test_entry_hash_matches_the_spec_formula():
    prev = GENESIS_PREV_HASH
    payload = _payload(1)
    p_hash = hashlib.sha256(rfc8785.dumps(payload)).hexdigest()
    assert canonical.payload_hash(payload) == p_hash
    expected = hashlib.sha256(bytes.fromhex(prev) + bytes.fromhex(p_hash)).digest()
    assert canonical.entry_hash(prev, p_hash) == expected
    assert len(expected) == 32  # Ed25519 signs these 32 bytes, not the payload


# -------------------------------------------------------------------- chaining


def test_first_entry_links_to_genesis(session, registered, keystore):
    entry = append(session, _payload(1), TEST_KID, keystore)
    session.commit()
    assert entry.seq == 1
    assert entry.prev_hash == GENESIS_PREV_HASH


def test_each_entry_links_to_the_previous(session, registered, keystore):
    entries = _append_three(session, keystore)
    assert [e.seq for e in entries] == [1, 2, 3]
    assert entries[1].prev_hash == entries[0].entry_hash
    assert entries[2].prev_hash == entries[1].entry_hash
    assert current_head(session).seq == 3


def test_signature_is_over_the_entry_hash_not_the_payload(
    session, registered, keystore
):
    entry = append(session, _payload(1), TEST_KID, keystore)
    session.commit()
    pub = keystore.public_hex(TEST_KID)
    assert verify_signature(pub, entry.signature, bytes.fromhex(entry.entry_hash))
    assert not verify_signature(pub, entry.signature, entry.payload_json.encode())


def test_stored_payload_is_canonical_bytes(session, registered, keystore):
    entry = append(session, _payload(1), TEST_KID, keystore)
    session.commit()
    assert entry.payload_json.encode() == rfc8785.dumps(_payload(1))


def test_verify_is_true_for_an_untouched_chain(session, registered, keystore):
    _append_three(session, keystore)
    result = verify(session, keystore)
    assert result.ok is True
    assert result.first_bad_index is None
    assert result.checked == 3


def test_verify_accepts_an_empty_chain(session, registered, keystore):
    assert verify(session, keystore).ok is True


def test_verify_rejects_an_unknown_signer(session, keystore):
    """No `registered` fixture: the device's public key was never stored."""
    append(session, _payload(1), "device-never-registered", keystore)
    session.commit()
    store = KeyStore(keystore.dir / "empty")
    result = verify(session, store)
    assert result.ok is False
    assert result.first_bad_index == 1
    assert "unknown signer_kid" in result.reason


# -------------------------------------------------------- the mandatory tamper test


def test_tamper_is_detected_and_reports_the_bad_index(
    session, registered, keystore, engine
):
    """MANDATORY (SPEC.md section 7 / T-17).

    Append three, corrupt the middle one, assert verify fails and names index 2.
    """
    _append_three(session, keystore)
    assert verify(session, keystore).ok is True

    corrupt_payload(engine, seq=2)

    with Session(engine) as fresh:
        result = verify(fresh, keystore)
    assert result.ok is False
    assert result.first_bad_index == 2
    assert "payload_hash" in result.reason
    # Entry 1 verified before the failure, so the report localises the damage.
    assert result.checked == 1


def test_tamper_demo_leaves_the_triggers_reinstalled(
    session, registered, keystore, engine
):
    """The demo drops a trigger to do its UPDATE; it must put it back."""
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    _append_three(session, keystore)
    corrupt_payload(engine, seq=2)
    with engine.connect() as conn, pytest.raises(IntegrityError, match="append-only"):
        conn.execute(text("UPDATE ledger SET created_at = 'rewritten'"))


def test_a_resigned_entry_still_breaks_the_chain(session, registered, keystore, engine):
    """A tamperer who recomputes the hashes AND re-signs with another key fails.

    This is the case the signature exists for: the payload hash and entry hash
    are internally consistent, so checks 3 and 4 pass on the edited entry
    itself. It is caught because the NEXT entry's prev_hash no longer matches,
    and because the signature is under a key that is not the registered device's.
    """
    entries = _append_three(session, keystore)
    attacker = KeyStore(keystore.dir / "attacker")

    new_payload = dict(_payload(2))
    new_payload["encounter_id"] = "enc-swapped"
    new_p_hash = canonical.payload_hash(new_payload)
    new_e_hash = canonical.entry_hash(entries[1].prev_hash, new_p_hash)

    drop_append_only_triggers(engine, "ledger")
    try:
        with Session(engine) as s:
            row = s.get(LedgerEntry, 2)
            row.payload_json = canonical.canonical_bytes(new_payload).decode()
            row.payload_hash = new_p_hash
            row.entry_hash = new_e_hash.hex()
            row.signature = attacker.sign(TEST_KID, new_e_hash)
            s.add(row)
            s.commit()
    finally:
        install_append_only_triggers(engine)

    with Session(engine) as fresh:
        result = verify(fresh, keystore)
    assert result.ok is False
    # Caught on entry 2 itself: the signature is not the registered device's.
    assert result.first_bad_index == 2
    assert "signature" in result.reason


def test_deleting_an_entry_is_detected_as_a_seq_gap(
    session, registered, keystore, engine
):
    _append_three(session, keystore)
    from sqlalchemy import text

    drop_append_only_triggers(engine, "ledger")
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM ledger WHERE seq = 2"))
            conn.commit()
    finally:
        install_append_only_triggers(engine)

    with Session(engine) as fresh:
        result = verify(fresh, keystore)
    assert result.ok is False
    assert result.first_bad_index == 3  # entry 3 now sits where 2 should be
    assert "contiguous" in result.reason


# ------------------------------------------------------------------- keystore


def test_keystore_persists_so_a_chain_survives_a_restart(tmp_path):
    first = KeyStore(tmp_path / "k")
    pub = first.public_hex("device-9")
    second = KeyStore(tmp_path / "k")
    assert second.public_hex("device-9") == pub
    assert (tmp_path / "k" / "device-9.pub").read_bytes().decode() == pub


def test_known_public_hex_does_not_create_a_key(tmp_path):
    store = KeyStore(tmp_path / "k")
    assert store.known_public_hex("never-seen") is None
    assert not (tmp_path / "k" / "never-seen.pem").exists()


def test_public_hex_is_the_raw_32_byte_key(keystore):
    pub = keystore.public_hex("device-1")
    assert len(bytes.fromhex(pub)) == 32
    assert pub == public_hex(keystore.private_key("device-1").public_key())
