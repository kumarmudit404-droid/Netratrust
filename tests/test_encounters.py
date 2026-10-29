"""T-04: POST /v1/encounters, and the Idempotency-Key contract.

What this file is actually for:
- the ledger entry exists BEFORE the caller sees a response, and the two commit
  together (so a failed append leaves no encounter behind);
- a rejected image is "no result" and can carry no grade;
- 409 while a key is in flight, 422 when a key is reused with a different body.
"""

from __future__ import annotations

import json

import pytest
from sqlmodel import Session, select

from netra.db.models import Encounter, IdempotencyKey, LedgerEntry
from netra.db.util import now_iso
from netra.ledger.verify import verify
from tests.conftest import TEST_SITE


def body(**over) -> dict:
    out = {
        "image_sha256": "a" * 64,
        "gate_verdict": "usable",
        "cause": None,
        "prediction_set": [2],
        "model_version": "convnext_tiny.in12k_ft_in1k@test",
        "site_id": TEST_SITE,
        "device_seq": 1,
    }
    out.update(over)
    return out


# ------------------------------------------------------------- the happy path


def test_creates_an_encounter_and_returns_the_ledger_index(client):
    res = client.post("/v1/encounters", json=body(), headers={"Idempotency-Key": "k1"})
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["encounter_id"].startswith("enc-")
    assert payload["ledger_idx"] == 1
    # Exactly the two frozen response fields, no extras.
    assert set(payload) == {"encounter_id", "ledger_idx"}


def test_ledger_entry_is_appended_before_the_response(client, engine):
    res = client.post("/v1/encounters", json=body(), headers={"Idempotency-Key": "k1"})
    idx = res.json()["ledger_idx"]
    with Session(engine) as session:
        entry = session.get(LedgerEntry, idx)
        assert entry is not None, (
            "the response named a ledger entry that does not exist"
        )
        stored = json.loads(entry.payload_json)
        assert stored["encounter_id"] == res.json()["encounter_id"]
        assert stored["type"] == "encounter"
        # The chain verifies with the entry in it.
        assert verify(session).ok is True


def test_payload_carries_no_floats(client, engine):
    """A float in a payload breaks the chain silently; assert there are none."""
    client.post("/v1/encounters", json=body(), headers={"Idempotency-Key": "k1"})
    with Session(engine) as session:
        entry = session.get(LedgerEntry, 1)

    def walk(value, path="payload"):
        assert not isinstance(value, float), f"{path} is a float"
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, f"{path}.{k}")
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, f"{path}[{i}]")

    walk(json.loads(entry.payload_json))


def test_abstains_when_the_set_spans_clinical_actions(client, engine):
    res = client.post(
        "/v1/encounters",
        json=body(prediction_set=[0, 3]),
        headers={"Idempotency-Key": "k1"},
    )
    assert res.status_code == 200
    with Session(engine) as session:
        enc = session.get(Encounter, res.json()["encounter_id"])
    assert enc.abstained is True
    assert enc.dr_grade is None


def test_does_not_abstain_when_the_set_stays_in_one_action_class(client, engine):
    """`{0,1}` and `{0,3}` are both size 2 and only the second is alarming."""
    res = client.post(
        "/v1/encounters",
        json=body(prediction_set=[0, 1]),
        headers={"Idempotency-Key": "k1"},
    )
    with Session(engine) as session:
        enc = session.get(Encounter, res.json()["encounter_id"])
    assert enc.abstained is False
    assert enc.dr_grade is None  # a set of two identifies no single severity


def test_records_a_single_grade_for_a_singleton_set(client, engine):
    res = client.post(
        "/v1/encounters",
        json=body(prediction_set=[3]),
        headers={"Idempotency-Key": "k1"},
    )
    with Session(engine) as session:
        enc = session.get(Encounter, res.json()["encounter_id"])
    assert enc.dr_grade == 3
    assert enc.abstained is False


# --------------------------------------------- a reject is "no result"


def test_a_rejected_image_is_recorded_with_no_grade(client, engine):
    res = client.post(
        "/v1/encounters",
        json=body(gate_verdict="reject", cause="focus", prediction_set=None),
        headers={"Idempotency-Key": "k1"},
    )
    assert res.status_code == 200
    with Session(engine) as session:
        enc = session.get(Encounter, res.json()["encounter_id"])
    assert enc.dr_grade is None
    assert enc.prediction_set is None
    # Not an abstention either: nothing was graded, so there was nothing to
    # abstain from.
    assert enc.abstained is False
    assert enc.cause == "focus"


def test_a_rejected_image_may_not_carry_a_prediction_set(client, engine):
    res = client.post(
        "/v1/encounters",
        json=body(gate_verdict="reject", cause="focus", prediction_set=[0]),
        headers={"Idempotency-Key": "k1"},
    )
    assert res.status_code == 422
    assert "no result" in res.json()["detail"]
    # Nothing was written, and in particular no ledger entry.
    with Session(engine) as session:
        assert session.exec(select(Encounter)).all() == []
        assert session.exec(select(LedgerEntry)).all() == []


def test_a_failed_request_leaves_no_encounter_and_no_ledger_entry(client, engine):
    client.post(
        "/v1/encounters",
        json=body(prediction_set=[9]),
        headers={"Idempotency-Key": "k1"},
    )
    with Session(engine) as session:
        assert session.exec(select(LedgerEntry)).all() == []


def test_unknown_site_is_a_404(client):
    res = client.post("/v1/encounters", json=body(site_id="site-nope"))
    assert res.status_code == 404


def test_rejects_an_unknown_body_field(client):
    res = client.post("/v1/encounters", json=body(sneaky="x"))
    assert res.status_code == 422


def test_rejects_a_bad_image_hash(client):
    res = client.post("/v1/encounters", json=body(image_sha256="not-a-hash"))
    assert res.status_code == 422


# ------------------------------------------------------------- idempotency


def test_a_retry_with_the_same_key_replays_and_creates_nothing_new(client, engine):
    headers = {"Idempotency-Key": "same-key"}
    first = client.post("/v1/encounters", json=body(), headers=headers)
    second = client.post("/v1/encounters", json=body(), headers=headers)
    assert first.json() == second.json()
    assert second.headers.get("Idempotency-Replayed") == "true"
    with Session(engine) as session:
        assert len(session.exec(select(Encounter)).all()) == 1
        assert len(session.exec(select(LedgerEntry)).all()) == 1


def test_409_while_a_key_is_still_in_flight(client, engine):
    """An in-flight claim is a real row, so this is the state a crashed or
    concurrent delivery actually leaves behind."""
    from netra.api import idempotency
    from netra.api.routes.encounters import ENDPOINT

    with Session(engine) as session:
        session.add(
            IdempotencyKey(
                key="in-flight",
                endpoint=ENDPOINT,
                request_fingerprint=idempotency.fingerprint(body()),
                status="in_flight",
                response_json=None,
                created_at=now_iso(),
            )
        )
        session.commit()

    res = client.post(
        "/v1/encounters", json=body(), headers={"Idempotency-Key": "in-flight"}
    )
    assert res.status_code == 409
    assert "in flight" in res.json()["detail"]


def test_422_when_a_key_is_reused_with_a_different_body(client):
    headers = {"Idempotency-Key": "reused"}
    assert (
        client.post("/v1/encounters", json=body(), headers=headers).status_code == 200
    )
    res = client.post("/v1/encounters", json=body(device_seq=2), headers=headers)
    assert res.status_code == 422
    assert "different request" in res.json()["detail"]


def test_422_beats_409_for_a_different_body_while_in_flight(client, engine):
    """A key reused with a different payload is a client bug in either state.
    Answering 409 would invite a retry loop that can never succeed."""
    from netra.api import idempotency
    from netra.api.routes.encounters import ENDPOINT

    with Session(engine) as session:
        session.add(
            IdempotencyKey(
                key="busy",
                endpoint=ENDPOINT,
                request_fingerprint=idempotency.fingerprint(body()),
                status="in_flight",
                response_json=None,
                created_at=now_iso(),
            )
        )
        session.commit()

    res = client.post(
        "/v1/encounters",
        json=body(device_seq=99),
        headers={"Idempotency-Key": "busy"},
    )
    assert res.status_code == 422


def test_no_key_means_no_dedup(client, engine):
    """At-least-once protection is opt-in; without a key a retry duplicates."""
    client.post("/v1/encounters", json=body())
    client.post("/v1/encounters", json=body())
    with Session(engine) as session:
        assert len(session.exec(select(Encounter)).all()) == 2


def test_a_failed_request_releases_its_key_so_a_retry_can_proceed(client, engine):
    headers = {"Idempotency-Key": "will-fail"}
    bad = client.post(
        "/v1/encounters",
        json=body(gate_verdict="reject", prediction_set=[0]),
        headers=headers,
    )
    assert bad.status_code == 422
    with Session(engine) as session:
        assert session.get(IdempotencyKey, "will-fail") is None


# --------------------------------------------------- conventions, not behaviour


def test_no_route_handler_is_async():
    """SQLite is blocking; async handlers over blocking SQLite is the top time sink."""
    import inspect

    from netra.api.main import app, contract_routes

    routes = contract_routes(app)
    assert routes, "no /v1 routes registered"
    for route in routes:
        assert not inspect.iscoroutinefunction(route.endpoint), route.path


def test_the_app_uses_a_lifespan_not_on_event():
    from netra.api.main import app, lifespan

    assert app.router.lifespan_context is not None
    assert lifespan.__name__ == "lifespan"


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_cors_preflight_allows_the_vite_origin_and_the_idempotency_header(
    client, origin
):
    res = client.options(
        "/v1/encounters",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "idempotency-key,content-type",
        },
    )
    assert res.status_code == 200, res.text
    assert res.headers["access-control-allow-origin"] == origin
    allowed = res.headers["access-control-allow-headers"].lower()
    assert "idempotency-key" in allowed
    assert "content-type" in allowed


def test_cors_allows_patch_for_the_referrals_endpoint(client):
    res = client.options(
        "/v1/encounters",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PATCH",
        },
    )
    assert "PATCH" in res.headers["access-control-allow-methods"]


def test_an_unlisted_origin_is_not_allowed(client):
    res = client.options(
        "/v1/encounters",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in res.headers


# ------------------------------------------------------- device registration


#: Two sites that have NO pre-registered device. `conftest.registered` gives
#: TEST_SITE one, so TEST_SITE never auto-registers and cannot collide - which
#: is exactly why the bug below survived every earlier test.
BARE_SITE_A = "site-98"
BARE_SITE_B = "site-99"


@pytest.fixture
def bare_sites(client, engine):
    """Two deviceless sites, so both auto-register on their first encounter."""
    from netra.db.models import Site

    with Session(engine) as session:
        for site_id in (BARE_SITE_A, BARE_SITE_B):
            session.add(
                Site(
                    id=site_id,
                    name=f"Camp {site_id}",
                    region="test",
                    created_at=now_iso(),
                )
            )
        session.commit()
    return client


def test_two_deviceless_sites_can_both_post(bare_sites):
    """Regression: the second one used to be a 500 on a valid request.

    With no `X-Device-Kid` header the handler auto-registers a device for the
    site. The default kid was the fixed string `device-1`, so the second site
    to auto-register tried to INSERT a primary key the first already held and
    SQLite raised `UNIQUE constraint failed: devices.kid`.

    This surfaced in `scripts/seed_dev.py`, which is the first thing in the
    repo to write more than one site.
    """
    first = bare_sites.post(
        "/v1/encounters",
        json=body(site_id=BARE_SITE_A),
        headers={"Idempotency-Key": "s1"},
    )
    assert first.status_code == 200, first.text

    second = bare_sites.post(
        "/v1/encounters",
        json=body(site_id=BARE_SITE_B),
        headers={"Idempotency-Key": "s2"},
    )
    assert second.status_code == 200, second.text


def test_each_site_gets_its_own_auto_registered_device(bare_sites, engine):
    from netra.db.models import Device

    bare_sites.post(
        "/v1/encounters",
        json=body(site_id=BARE_SITE_A),
        headers={"Idempotency-Key": "s1"},
    )
    bare_sites.post(
        "/v1/encounters",
        json=body(site_id=BARE_SITE_B),
        headers={"Idempotency-Key": "s2"},
    )

    with Session(engine) as session:
        devices = session.exec(select(Device)).all()
    by_site = {d.site_id: d.kid for d in devices}

    # A device belongs to exactly one site, so the two must differ.
    assert by_site[BARE_SITE_A] != by_site[BARE_SITE_B]
    assert len({d.kid for d in devices}) == len(devices)


def test_a_sites_second_encounter_reuses_its_device(bare_sites, engine):
    from netra.db.models import Device

    for i, key in enumerate(("a", "b", "c"), start=1):
        res = bare_sites.post(
            "/v1/encounters",
            json=body(site_id=BARE_SITE_A, device_seq=i),
            headers={"Idempotency-Key": key},
        )
        assert res.status_code == 200, res.text

    with Session(engine) as session:
        kids = session.exec(
            select(Device.kid).where(Device.site_id == BARE_SITE_A)
        ).all()
    assert len(kids) == 1


def test_a_kid_registered_to_another_site_is_a_422(bare_sites, engine):
    from netra.db.models import Device

    bare_sites.post(
        "/v1/encounters",
        json=body(site_id=BARE_SITE_A),
        headers={"Idempotency-Key": "s1"},
    )
    with Session(engine) as session:
        kid = session.exec(
            select(Device.kid).where(Device.site_id == BARE_SITE_A)
        ).first()

    res = bare_sites.post(
        "/v1/encounters",
        json=body(site_id=BARE_SITE_B),
        headers={"Idempotency-Key": "s2", "X-Device-Kid": kid},
    )
    assert res.status_code == 422, res.text
    assert BARE_SITE_A in res.json()["detail"]


def test_a_multi_site_chain_still_verifies(bare_sites, engine):
    """Entries signed by two different devices must still form one valid chain."""
    bare_sites.post(
        "/v1/encounters",
        json=body(site_id=BARE_SITE_A),
        headers={"Idempotency-Key": "s1"},
    )
    bare_sites.post(
        "/v1/encounters",
        json=body(site_id=BARE_SITE_B),
        headers={"Idempotency-Key": "s2"},
    )

    with Session(engine) as session:
        result = verify(session)
    assert result.ok, result.reason
    assert result.checked == 2
