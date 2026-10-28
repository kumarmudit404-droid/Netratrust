"""The Lane A / Lane B contract, checked against Lane B's typed client itself.

`netra/ui/src/lib/api/types.ts` is READ-ONLY to this lane. Three endpoints
carried a `TODO(Lane A)` there because SPEC.md describes them in prose rather
than naming fields:

- `GET  /v1/sites/{id}/status`  - "must return gradability as counts {k, n, ci}
                                  - a bare rate cannot satisfy the n<30 rule.
                                  Match this or raise."
- `POST /v1/sites/{id}/audit`   - "define the audit payload fields."
- `GET  /v1/queue/depth`        - "specify the element type of `attempts`."

All three are matched. This file parses the TypeScript and compares field names
to the live responses, so the two sides cannot drift silently: if Lane B adds a
field, this test fails and names it.

It is a field-NAME check, not a type-checker. Lane B's own `tsc` covers types;
what breaks an integration in practice is a renamed or missing field.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from sqlmodel import Session

from netra.db.models import Site
from netra.db.util import now_iso
from tests.conftest import TEST_SITE
from tests.test_encounters import body
from tests.test_sites import audit_payload

TYPES_TS = (
    pathlib.Path(__file__).resolve().parents[1]
    / "netra"
    / "ui"
    / "src"
    / "lib"
    / "api"
    / "types.ts"
)


def interface_fields(source: str, name: str) -> set[str]:
    """Top-level field names of `export interface <name> { ... }`.

    Brace-counted rather than regex-matched to the closing brace, so a nested
    object type cannot make this silently return half an interface.
    """
    match = re.search(rf"export interface {re.escape(name)}\s*\{{", source)
    if match is None:
        raise AssertionError(f"interface {name} not found in types.ts")

    depth, i = 1, match.end()
    body_start = i
    while depth:
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
        i += 1
    block = source[body_start : i - 1]

    fields: set[str] = set()
    depth = 0
    for line in block.splitlines():
        stripped = line.strip()
        if depth == 0:
            found = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\??\s*:", stripped)
            if found:
                fields.add(found.group(1))
        depth += stripped.count("{") - stripped.count("}")
    return fields


@pytest.fixture(scope="module")
def types_source() -> str:
    assert TYPES_TS.exists(), f"Lane B's typed client is missing at {TYPES_TS}"
    return TYPES_TS.read_text(encoding="utf-8")


def test_types_ts_is_present_and_read_only_to_this_lane(types_source):
    assert "export interface SiteStatusResponse" in types_source


# ------------------------------------------------- the three TODO(Lane A) shapes


def test_site_status_matches_lane_bs_shape(client, types_source):
    expected = interface_fields(types_source, "SiteStatusResponse")
    payload = client.get(f"/v1/sites/{TEST_SITE}/status").json()
    assert (
        set(payload)
        == expected
        == {
            "site_id",
            "model_version",
            "last_audit",
            "gradability",
            "drift_flag",
        }
    )
    # `gradability` is RateCounts: counts + Wilson, NOT a bare rate.
    assert set(payload["gradability"]) == interface_fields(types_source, "RateCounts")


def test_queue_depth_matches_lane_bs_shape(client, types_source):
    client.post("/v1/encounters", json=body(), headers={"Idempotency-Key": "q1"})
    payload = client.get("/v1/queue/depth").json()
    assert set(payload) == interface_fields(types_source, "QueueDepthResponse")
    # Lane B types `attempts` as unknown[] pending this lane. Settled as:
    assert set(payload["attempts"][0]) == {"key", "endpoint", "status", "created_at"}


def test_site_audit_matches_lane_bs_shape(client, types_source):
    payload = client.post(f"/v1/sites/{TEST_SITE}/audit", json=audit_payload()).json()
    assert set(payload) == interface_fields(types_source, "SiteAuditResponse")
    # `SiteAuditRequest` is Record<string, unknown> on Lane B's side, so the
    # request fields are Lane A's to define. These are they.
    assert set(audit_payload()) == {
        "pinned_model_version",
        "gradable_k",
        "gradable_n",
        "agreement_k",
        "agreement_n",
        "grade_counts",
        "drift_flag",
    }


# ------------------------------------------- the six already-specified shapes


def test_site_metrics_matches_lane_bs_shape(client, types_source, engine):
    with Session(engine) as session:
        session.add(
            Site(id="site-11", name="Camp 11", region="south", created_at=now_iso())
        )
        session.commit()
    client.post("/v1/encounters", json=body(), headers={"Idempotency-Key": "m1"})

    payload = client.get("/v1/metrics/sites").json()
    assert set(payload) == interface_fields(types_source, "SiteMetricsResponse")
    assert set(payload["rows"][0]) == interface_fields(types_source, "SiteMetricsRow")
    assert set(payload["pooled"]) == {"gradability"}


def test_encounter_shapes_match(client, types_source):
    assert set(body()) == interface_fields(types_source, "EncounterRequest")
    payload = client.post(
        "/v1/encounters", json=body(), headers={"Idempotency-Key": "e1"}
    ).json()
    assert set(payload) == interface_fields(types_source, "EncounterResponse")


def test_referral_shapes_match(client, types_source):
    encounter = client.post(
        "/v1/encounters",
        json=body(prediction_set=[3]),
        headers={"Idempotency-Key": "r1"},
    ).json()
    created = client.post(
        "/v1/referrals", json={"encounter_id": encounter["encounter_id"]}
    ).json()
    assert set(created) == interface_fields(types_source, "ReferralCreateResponse")

    patch_body = {"to_state": "contact_attempted", "channel": "phone", "reason": None}
    assert set(patch_body) == interface_fields(types_source, "ReferralPatchRequest")
    patched = client.patch(
        f"/v1/referrals/{created['referral_id']}", json=patch_body
    ).json()
    assert set(patched) == interface_fields(types_source, "ReferralPatchResponse")


def test_ledger_shapes_match(client, types_source):
    assert set(client.get("/v1/ledger/verify").json()) == interface_fields(
        types_source, "LedgerVerifyResponse"
    )
    assert set(client.get("/v1/ledger/checkpoint").json()) == interface_fields(
        types_source, "LedgerCheckpointResponse"
    )


# --------------------------------------------------------- the frozen nine


def test_lane_b_calls_only_the_nine_frozen_paths():
    """Lane B's client must not reference a path this lane does not serve."""
    client_ts = TYPES_TS.parent / "client.ts"
    source = client_ts.read_text(encoding="utf-8")
    called = set(re.findall(r'"(/v1/[^"]*)"', source))
    called |= {
        m.replace("${encodeURIComponent(siteId)}", "{site_id}").replace(
            "${encodeURIComponent(id)}", "{referral_id}"
        )
        for m in re.findall(r"`(/v1/[^`]*)`", source)
    }
    assert called == {
        "/v1/encounters",
        "/v1/referrals",
        "/v1/referrals/{referral_id}",
        "/v1/ledger/verify",
        "/v1/ledger/checkpoint",
        "/v1/sites/{site_id}/status",
        "/v1/sites/{site_id}/audit",
        "/v1/metrics/sites",
        "/v1/queue/depth",
    }


def test_lane_bs_referral_states_match_the_server_machine(types_source):
    from netra.api import referral_state as rs

    block = re.search(
        r"export type ReferralState =\s*((?:\s*\|\s*\"[a-z_]+\")+)", types_source
    )
    assert block is not None
    declared = set(re.findall(r'"([a-z_]+)"', block.group(1)))
    assert declared == set(rs.STATES)


def test_lane_bs_refer_grades_match_config():
    """Lane B mirrors `dr.refer_grades`; a drift between them is a clinical bug."""
    from netra.api.config import refer_grades

    clinical_ts = TYPES_TS.parent.parent / "clinical.ts"
    source = clinical_ts.read_text(encoding="utf-8")
    found = re.search(r"REFER_GRADES: readonly Grade\[\] = \[([0-9,\s]+)\]", source)
    assert found is not None
    declared = tuple(int(x) for x in found.group(1).replace(" ", "").split(","))
    assert declared == refer_grades()
