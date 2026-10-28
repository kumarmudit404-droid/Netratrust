"""T-06: GET /v1/ledger/verify and GET /v1/ledger/checkpoint.

The endpoint that matters is `verify` returning `ok:false` with the right
`first_bad_index`, because that is what the Ledger view's tamper demo (T-17)
renders. A verify endpoint that has only ever answered `ok:true` demonstrates
nothing, so it is driven against a corrupted chain here too.
"""

from __future__ import annotations

from sqlmodel import Session

from netra.ledger import checkpoint as checkpoint_mod
from netra.ledger.keys import SERVER_KID, KeyStore
from netra.ledger.tamper import corrupt_payload
from tests.conftest import TEST_KID
from tests.test_encounters import body


def post_three(client) -> None:
    for n in (1, 2, 3):
        res = client.post(
            "/v1/encounters",
            json=body(device_seq=n),
            headers={"Idempotency-Key": f"k{n}"},
        )
        assert res.status_code == 200, res.text


# ------------------------------------------------------------------ verify


def test_verify_is_ok_on_an_empty_chain(client):
    res = client.get("/v1/ledger/verify")
    assert res.status_code == 200
    assert res.json() == {"ok": True, "first_bad_index": None}


def test_verify_is_ok_after_real_writes(client):
    post_three(client)
    assert client.get("/v1/ledger/verify").json() == {
        "ok": True,
        "first_bad_index": None,
    }


def test_verify_reports_the_corrupted_index(client, engine):
    """The tamper demo, end to end through the HTTP surface."""
    post_three(client)
    assert client.get("/v1/ledger/verify").json()["ok"] is True

    corrupt_payload(engine, seq=2)

    payload = client.get("/v1/ledger/verify").json()
    assert payload == {"ok": False, "first_bad_index": 2}


def test_verify_response_has_exactly_the_two_frozen_fields(client, engine):
    """The internal `reason` string must not leak into the contract."""
    post_three(client)
    corrupt_payload(engine, seq=1)
    assert set(client.get("/v1/ledger/verify").json()) == {"ok", "first_bad_index"}


def test_verify_detects_a_deleted_entry(client, engine):
    from sqlalchemy import text

    from netra.db.engine import (
        drop_append_only_triggers,
        install_append_only_triggers,
    )

    post_three(client)
    drop_append_only_triggers(engine, "ledger")
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM ledger WHERE seq = 2"))
            conn.commit()
    finally:
        install_append_only_triggers(engine)

    payload = client.get("/v1/ledger/verify").json()
    assert payload["ok"] is False
    assert payload["first_bad_index"] == 3


# -------------------------------------------------------------- checkpoint


def test_checkpoint_on_an_empty_chain_attests_index_zero(client):
    payload = client.get("/v1/ledger/checkpoint").json()
    assert payload["idx"] == 0
    assert payload["head_hash"] == "0" * 64
    assert payload["signer_kid"] == SERVER_KID


def test_checkpoint_shape_is_exactly_the_frozen_five(client):
    post_three(client)
    payload = client.get("/v1/ledger/checkpoint").json()
    assert set(payload) == {"idx", "head_hash", "ts", "signature", "signer_kid"}


def test_checkpoint_attests_the_current_head(client, engine):
    post_three(client)
    payload = client.get("/v1/ledger/checkpoint").json()
    from netra.ledger.chain import current_head

    with Session(engine) as session:
        head = current_head(session)
    assert payload["idx"] == head.seq == 3
    assert payload["head_hash"] == head.entry_hash


def test_the_checkpoint_signature_verifies(client, tmp_path):
    """An external holder must be able to check it from the response alone."""
    post_three(client)
    payload = client.get("/v1/ledger/checkpoint").json()

    from netra.ledger.checkpoint import signed_bytes
    from netra.ledger.keys import verify_signature

    store = KeyStore(tmp_path / "keys")
    pub = store.known_public_hex(payload["signer_kid"])
    assert pub is not None, "the server key should be on disk after signing"
    assert verify_signature(
        pub,
        payload["signature"],
        signed_bytes(payload["idx"], payload["head_hash"], payload["ts"]),
    )


def test_a_tampered_signature_does_not_verify(client, tmp_path):
    post_three(client)
    payload = client.get("/v1/ledger/checkpoint").json()

    from netra.ledger.checkpoint import signed_bytes
    from netra.ledger.keys import verify_signature

    store = KeyStore(tmp_path / "keys")
    pub = store.known_public_hex(payload["signer_kid"])
    assert not verify_signature(
        pub,
        payload["signature"],
        # Claim a longer chain than was signed - the rewrite a checkpoint
        # exists to catch.
        signed_bytes(payload["idx"] + 1, payload["head_hash"], payload["ts"]),
    )


def test_reading_twice_at_an_unchanged_head_returns_the_same_checkpoint(client):
    post_three(client)
    first = client.get("/v1/ledger/checkpoint").json()
    second = client.get("/v1/ledger/checkpoint").json()
    assert first == second


def test_the_checkpoint_moves_when_the_head_moves(client):
    post_three(client)
    before = client.get("/v1/ledger/checkpoint").json()
    client.post(
        "/v1/encounters", json=body(device_seq=9), headers={"Idempotency-Key": "k9"}
    )
    after = client.get("/v1/ledger/checkpoint").json()
    assert after["idx"] == before["idx"] + 1
    assert after["head_hash"] != before["head_hash"]


def test_an_old_checkpoint_still_proves_a_rewrite(client, engine, keystore):
    """The whole point of a checkpoint, asserted rather than left in prose.

    A tamperer with the database can recompute the hashes and re-sign from the
    edit forwards, which makes `verify` pass again. What they cannot do is
    retract the checkpoint an external party already holds: it attests a head
    hash the rewritten chain no longer has.
    """
    from sqlalchemy import text

    from netra.db.engine import (
        drop_append_only_triggers,
        install_append_only_triggers,
    )
    from netra.db.models import LedgerEntry
    from netra.ledger import canonical
    from netra.ledger.verify import verify

    post_three(client)
    held = client.get("/v1/ledger/checkpoint").json()

    with Session(engine) as session:
        prev_hash = session.get(LedgerEntry, 3).prev_hash

    # Rewrite entry 3 AND re-chain it properly, so the chain stays sound. The
    # device key is in the same keystore the app signs with, which is the
    # strongest version of this attack: a fully valid forged entry.
    forged = {"type": "encounter", "encounter_id": "enc-forged"}
    forged_payload_hash = canonical.payload_hash(forged)
    forged_entry_hash = canonical.entry_hash(prev_hash, forged_payload_hash)

    drop_append_only_triggers(engine, "ledger")
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE ledger SET payload_json=:p, payload_hash=:ph, "
                    "entry_hash=:eh, signature=:sg WHERE seq=3"
                ),
                {
                    "p": canonical.canonical_bytes(forged).decode(),
                    "ph": forged_payload_hash,
                    "eh": forged_entry_hash.hex(),
                    "sg": keystore.sign(TEST_KID, forged_entry_hash),
                },
            )
            conn.commit()
    finally:
        install_append_only_triggers(engine)

    with Session(engine) as session:
        assert verify(session, keystore).ok is True, (
            "a re-signed, re-chained entry makes the chain self-consistent again - "
            "this is exactly the attack a bare chain cannot catch"
        )
        new_head_hash = session.get(LedgerEntry, 3).entry_hash

    # verify now says ok, and the held checkpoint is what catches the rewrite.
    assert client.get("/v1/ledger/verify").json()["ok"] is True
    assert held["head_hash"] != new_head_hash


def test_checkpoints_table_stays_append_only(client, engine):
    """Re-signing an existing head would need an UPDATE the triggers refuse."""
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    post_three(client)
    client.get("/v1/ledger/checkpoint")
    with engine.connect() as conn, pytest.raises(IntegrityError, match="append-only"):
        conn.execute(text("UPDATE checkpoints SET root_hash = 'x'"))


def test_checkpoint_module_verifier_agrees_with_the_endpoint(client, engine, tmp_path):
    post_three(client)
    client.get("/v1/ledger/checkpoint")
    store = KeyStore(tmp_path / "keys")
    with Session(engine) as session:
        row = checkpoint_mod.latest(session)
    assert checkpoint_mod.verify_checkpoint(row, store.known_public_hex(row.signer_kid))
