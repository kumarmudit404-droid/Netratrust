"""T-07: site status, audit, per-site metrics, queue depth.

Also the integration contract: these four responses are checked field-by-field
against Lane B's typed client in `netra/ui/src/lib/api/types.ts`, which is
read-only to this lane. Three of them carried a `TODO(Lane A)` because SPEC.md
described them in prose; `test_integration.py` pins the agreed shapes.
"""

from __future__ import annotations

from sqlmodel import Session

from netra.db.models import Site
from netra.db.util import now_iso
from netra.eval.metrics import wilson_interval
from tests.conftest import TEST_SITE
from tests.test_encounters import body


def audit_payload(**over) -> dict:
    out = {
        "pinned_model_version": "convnext_tiny.in12k_ft_in1k@abc123",
        "gradable_k": 22,
        "gradable_n": 30,
        "agreement_k": 26,
        "agreement_n": 30,
        "grade_counts": {"0": 12, "1": 6, "2": 7, "3": 3, "4": 2},
        "drift_flag": False,
    }
    out.update(over)
    return out


def post_encounters(client, verdicts_and_sets) -> None:
    for i, (verdict, pset) in enumerate(verdicts_and_sets):
        res = client.post(
            "/v1/encounters",
            json=body(
                gate_verdict=verdict,
                cause="focus" if verdict == "reject" else None,
                prediction_set=pset,
                device_seq=i + 1,
            ),
            headers={"Idempotency-Key": f"e{i}"},
        )
        assert res.status_code == 200, res.text


# ------------------------------------------------- GET /v1/sites/{id}/status


def test_status_returns_counts_and_a_wilson_interval_not_a_bare_rate(client):
    post_encounters(
        client,
        [("usable", [2]), ("usable", [1]), ("reject", None), ("borderline", [0])],
    )
    payload = client.get(f"/v1/sites/{TEST_SITE}/status").json()
    assert payload["gradability"] == {
        "k": 3,  # three admitted
        "n": 4,  # four seen; the reject is in the denominator
        "ci": list(wilson_interval(3, 4)),
    }
    assert set(payload["gradability"]) == {"k", "n", "ci"}


def test_status_of_a_never_audited_site(client):
    payload = client.get(f"/v1/sites/{TEST_SITE}/status").json()
    assert payload["last_audit"] is None
    assert payload["model_version"] == "unpinned"
    assert payload["drift_flag"] is False
    assert payload["gradability"] == {"k": 0, "n": 0, "ci": [0.0, 1.0]}


def test_status_reflects_a_passed_audit(client):
    res = client.post(f"/v1/sites/{TEST_SITE}/audit", json=audit_payload())
    assert res.json()["passed"] is True
    payload = client.get(f"/v1/sites/{TEST_SITE}/status").json()
    assert payload["model_version"] == "convnext_tiny.in12k_ft_in1k@abc123"
    assert payload["last_audit"] is not None
    assert payload["drift_flag"] is False


def test_a_failed_audit_does_not_pin_a_model_version(client):
    """SPEC.md section 6: a site must PASS a local audit before its grades count."""
    client.post(
        f"/v1/sites/{TEST_SITE}/audit", json=audit_payload(gradable_n=10, gradable_k=8)
    )
    payload = client.get(f"/v1/sites/{TEST_SITE}/status").json()
    assert payload["model_version"] == "unpinned"
    assert payload["last_audit"] is not None  # the audit still happened


def test_status_shows_a_drift_flag(client):
    client.post(f"/v1/sites/{TEST_SITE}/audit", json=audit_payload(drift_flag=True))
    assert client.get(f"/v1/sites/{TEST_SITE}/status").json()["drift_flag"] is True


def test_status_of_an_unknown_site_is_a_404(client):
    assert client.get("/v1/sites/site-nope/status").status_code == 404


# -------------------------------------------------- POST /v1/sites/{id}/audit


def test_audit_returns_exactly_the_two_frozen_fields(client):
    payload = client.post(f"/v1/sites/{TEST_SITE}/audit", json=audit_payload()).json()
    assert set(payload) == {"passed", "pinned_model_version"}


def test_audit_fails_below_min_n_for_rate(client):
    """`sites.min_n_for_rate` is 30 in config/thresholds.yaml; 29 is not enough."""
    res = client.post(
        f"/v1/sites/{TEST_SITE}/audit", json=audit_payload(agreement_n=29)
    )
    assert res.json()["passed"] is False


def test_audit_fails_when_drift_is_flagged(client):
    res = client.post(
        f"/v1/sites/{TEST_SITE}/audit", json=audit_payload(drift_flag=True)
    )
    assert res.json()["passed"] is False


def test_audit_refuses_a_numerator_above_its_denominator(client):
    res = client.post(f"/v1/sites/{TEST_SITE}/audit", json=audit_payload(gradable_k=99))
    assert res.status_code == 422


def test_audit_is_appended_to_the_ledger_before_it_returns(client, engine):
    import json

    from sqlmodel import select

    from netra.db.models import LedgerEntry
    from netra.ledger.verify import verify

    client.post(f"/v1/sites/{TEST_SITE}/audit", json=audit_payload())
    with Session(engine) as session:
        payloads = [
            json.loads(e.payload_json) for e in session.exec(select(LedgerEntry)).all()
        ]
        audits = [p for p in payloads if p["type"] == "site_audit"]
        assert len(audits) == 1
        assert audits[0]["passed"] is True
        assert audits[0]["gradable_k"] == 22
        # Counts and strings only; no float survived into the payload.
        assert all(not isinstance(v, float) for v in audits[0].values())
        assert verify(session).ok is True


def test_audit_of_an_unknown_site_is_a_404(client):
    assert (
        client.post("/v1/sites/site-nope/audit", json=audit_payload()).status_code
        == 404
    )


def test_audit_payload_rejects_an_unknown_field(client):
    res = client.post(f"/v1/sites/{TEST_SITE}/audit", json=audit_payload(extra=1))
    assert res.status_code == 422


# --------------------------------------------------- GET /v1/metrics/sites


def test_metrics_returns_a_row_per_site_and_a_pooled_reference(client, engine):
    with Session(engine) as session:
        session.add(
            Site(id="site-11", name="Camp 11", region="south", created_at=now_iso())
        )
        session.commit()

    post_encounters(
        client,
        [("usable", [2]), ("reject", None), ("usable", [0, 3]), ("usable", [1])],
    )
    payload = client.get("/v1/metrics/sites").json()

    assert [r["site_id"] for r in payload["rows"]] == ["site-07", "site-11"]
    seven = payload["rows"][0]
    assert seven["gradability"] == {"k": 3, "n": 4, "ci": list(wilson_interval(3, 4))}
    # Abstention's denominator is ADMITTED images, not all images: a rejected
    # image was never graded, so it cannot have abstained.
    assert seven["abstention"] == {"k": 1, "n": 3, "ci": list(wilson_interval(1, 3))}
    assert seven["drift_flag"] is False
    # An empty site still appears, as a row with n = 0.
    assert payload["rows"][1]["gradability"]["n"] == 0


def test_pooled_is_summed_counts_not_a_mean_of_rates(client, engine):
    """SPEC.md: never a mean. With unequal n the two answers differ."""
    with Session(engine) as session:
        session.add(
            Site(id="site-11", name="Camp 11", region="south", created_at=now_iso())
        )
        session.commit()
    post_encounters(client, [("usable", [2]), ("reject", None), ("usable", [1])])

    payload = client.get("/v1/metrics/sites").json()
    pooled = payload["pooled"]["gradability"]
    assert pooled == {"k": 2, "n": 3, "ci": list(wilson_interval(2, 3))}
    # The mean of the per-site rates would be (2/3 + 0/0) -> not 2/3.
    assert set(payload["pooled"]) == {"gradability"}


def test_metrics_never_returns_a_bare_rate(client):
    post_encounters(client, [("usable", [2])])
    payload = client.get("/v1/metrics/sites").json()
    for row in payload["rows"]:
        for field in ("gradability", "abstention"):
            assert set(row[field]) == {"k", "n", "ci"}
            assert "rate" not in row[field]


# ---------------------------------------------------- GET /v1/queue/depth


def test_queue_depth_counts_applied_deliveries(client):
    post_encounters(client, [("usable", [2]), ("usable", [1])])
    payload = client.get("/v1/queue/depth").json()
    assert payload["queued"] == 0
    assert payload["synced"] == 2
    assert set(payload) == {"queued", "synced", "attempts"}


def test_queue_depth_reports_an_in_flight_delivery_as_queued(client, engine):
    from netra.api import idempotency
    from netra.api.routes.encounters import ENDPOINT
    from netra.db.models import IdempotencyKey

    with Session(engine) as session:
        session.add(
            IdempotencyKey(
                key="stuck",
                endpoint=ENDPOINT,
                request_fingerprint=idempotency.fingerprint(body()),
                status="in_flight",
                response_json=None,
                created_at=now_iso(),
            )
        )
        session.commit()
    payload = client.get("/v1/queue/depth").json()
    assert payload["queued"] == 1
    assert payload["synced"] == 0


def test_queue_attempts_carry_a_concrete_shape(client):
    """SPEC.md leaves `attempts:[...]` untyped; Lane A settles it here."""
    post_encounters(client, [("usable", [2])])
    attempts = client.get("/v1/queue/depth").json()["attempts"]
    assert len(attempts) == 1
    assert set(attempts[0]) == {"key", "endpoint", "status", "created_at"}
    assert attempts[0]["status"] == "done"
    assert attempts[0]["endpoint"] == "POST /v1/encounters"


def test_queue_depth_is_empty_on_a_fresh_server(client):
    assert client.get("/v1/queue/depth").json() == {
        "queued": 0,
        "synced": 0,
        "attempts": [],
    }


# ------------------------------------------------ all nine, and only nine


def test_exactly_the_nine_frozen_endpoints_are_registered():
    from netra.api.main import app, contract_routes

    registered = {
        (method, route.path)
        for route in contract_routes(app)
        for method in sorted(route.methods)
        if method != "HEAD"
    }
    assert registered == {
        ("POST", "/v1/encounters"),
        ("POST", "/v1/referrals"),
        ("PATCH", "/v1/referrals/{referral_id}"),
        ("GET", "/v1/ledger/verify"),
        ("GET", "/v1/ledger/checkpoint"),
        ("GET", "/v1/sites/{site_id}/status"),
        ("POST", "/v1/sites/{site_id}/audit"),
        ("GET", "/v1/metrics/sites"),
        ("GET", "/v1/queue/depth"),
    }
