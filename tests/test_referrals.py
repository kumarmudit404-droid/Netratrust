"""T-05: POST /v1/referrals and PATCH /v1/referrals/{id}.

The state machine is tested from both sides: every legal path walks, and every
illegal move is refused. A machine that only ever gets driven along its happy
path is not a machine, it is a suggestion.
"""

from __future__ import annotations

import itertools
import json

import pytest
from sqlmodel import Session, select

from netra.api import referral_state as rs
from netra.db.models import LedgerEntry, Referral, ReferralEvent
from netra.ledger.verify import verify
from tests.test_encounters import body


def make_encounter(client, **over) -> str:
    res = client.post(
        "/v1/encounters",
        json=body(**over),
        headers={"Idempotency-Key": f"enc-{next(_keys)}"},
    )
    assert res.status_code == 200, res.text
    return res.json()["encounter_id"]


_keys = itertools.count(1)


def issue(client, **over) -> str:
    encounter_id = make_encounter(client, **over)
    res = client.post("/v1/referrals", json={"encounter_id": encounter_id})
    assert res.status_code == 200, res.text
    return res.json()["referral_id"]


def patch(client, referral_id: str, to_state: str, channel=None, reason=None):
    return client.patch(
        f"/v1/referrals/{referral_id}",
        json={"to_state": to_state, "channel": channel, "reason": reason},
    )


# ---------------------------------------------------------------- issuing


def test_issues_a_referral_for_a_referable_grade(client):
    encounter_id = make_encounter(client, prediction_set=[3])
    res = client.post("/v1/referrals", json={"encounter_id": encounter_id})
    assert res.status_code == 200
    payload = res.json()
    assert payload["state"] == "issued"
    assert payload["referral_id"].startswith("ref-")
    assert set(payload) == {"referral_id", "state"}  # exactly the frozen shape


def test_issuing_appends_a_ledger_entry(client, engine):
    referral_id = issue(client, prediction_set=[2])
    with Session(engine) as session:
        entries = session.exec(select(LedgerEntry).order_by(LedgerEntry.seq)).all()
        payloads = [json.loads(e.payload_json) for e in entries]
        issued = [p for p in payloads if p["type"] == "referral_issued"]
        assert len(issued) == 1
        assert issued[0]["referral_id"] == referral_id
        assert verify(session).ok is True


def test_no_referral_from_an_abstention(client):
    """SPEC.md section 7: a clinician decides; no referral is issued from an abstention."""
    encounter_id = make_encounter(client, prediction_set=[0, 3])
    res = client.post("/v1/referrals", json={"encounter_id": encounter_id})
    assert res.status_code == 422
    assert "abstained" in res.json()["detail"]


def test_no_referral_from_a_rejected_image(client):
    """A failed quality gate is not a negative result, and not a referable one."""
    encounter_id = make_encounter(
        client, gate_verdict="reject", cause="focus", prediction_set=None
    )
    res = client.post("/v1/referrals", json={"encounter_id": encounter_id})
    assert res.status_code == 422


def test_no_referral_for_a_non_referable_grade(client):
    """`dr.refer_grades` is [2,3,4]; grade 1 is not referable."""
    encounter_id = make_encounter(client, prediction_set=[1])
    res = client.post("/v1/referrals", json={"encounter_id": encounter_id})
    assert res.status_code == 422


def test_unknown_encounter_is_a_404(client):
    res = client.post("/v1/referrals", json={"encounter_id": "enc-nope"})
    assert res.status_code == 404


def test_a_second_referral_for_one_encounter_is_a_409(client):
    encounter_id = make_encounter(client, prediction_set=[4])
    assert (
        client.post("/v1/referrals", json={"encounter_id": encounter_id}).status_code
        == 200
    )
    second = client.post("/v1/referrals", json={"encounter_id": encounter_id})
    assert second.status_code == 409


def test_a_failed_issue_writes_nothing(client, engine):
    encounter_id = make_encounter(client, prediction_set=[0, 3])
    client.post("/v1/referrals", json={"encounter_id": encounter_id})
    with Session(engine) as session:
        assert session.exec(select(Referral)).all() == []
        payloads = [
            json.loads(e.payload_json) for e in session.exec(select(LedgerEntry)).all()
        ]
        assert not [p for p in payloads if p["type"] != "encounter"]


# ------------------------------------------------------- the state machine


def test_the_whole_happy_path_walks(client, engine):
    referral_id = issue(client, prediction_set=[3])
    assert (
        patch(client, referral_id, "contact_attempted", channel="phone").status_code
        == 200
    )
    assert patch(client, referral_id, "contacted").status_code == 200
    assert patch(client, referral_id, "appointment_offered").status_code == 200
    res = patch(client, referral_id, "examined")
    assert res.status_code == 200
    assert res.json()["state"] == "examined"
    with Session(engine) as session:
        assert session.get(Referral, referral_id).state == "examined"


def test_every_transition_appends_a_ledger_entry(client, engine):
    referral_id = issue(client, prediction_set=[3])
    seen = []
    for to_state, kwargs in [
        ("contact_attempted", {"channel": "phone"}),
        ("contacted", {}),
        ("appointment_offered", {}),
        ("examined", {}),
    ]:
        res = patch(client, referral_id, to_state, **kwargs)
        seen.append(res.json()["ledger_idx"])

    assert seen == sorted(set(seen)), "ledger indices must be distinct and increasing"
    with Session(engine) as session:
        payloads = [
            json.loads(e.payload_json)
            for e in session.exec(select(LedgerEntry).order_by(LedgerEntry.seq)).all()
        ]
        transitions = [p for p in payloads if p["type"] == "referral_transition"]
        assert [p["to_state"] for p in transitions] == [
            "contact_attempted",
            "contacted",
            "appointment_offered",
            "examined",
        ]
        assert [p["from_state"] for p in transitions] == [
            "issued",
            "contact_attempted",
            "contacted",
            "appointment_offered",
        ]
        assert verify(session).ok is True


def test_contact_attempted_is_repeatable_and_counts_attempts(client, engine):
    referral_id = issue(client, prediction_set=[3])
    for expected in (1, 2, 3):
        res = patch(client, referral_id, "contact_attempted", channel="phone")
        assert res.status_code == 200, res.text
        with Session(engine) as session:
            events = session.exec(
                select(ReferralEvent)
                .where(ReferralEvent.referral_id == referral_id)
                .where(ReferralEvent.to_state == "contact_attempted")
            ).all()
        assert max(e.attempt_n for e in events) == expected


def test_abandoned_is_reachable_from_every_non_terminal_state(client):
    for prelude in (
        [],
        [("contact_attempted", {"channel": "phone"})],
        [("contact_attempted", {"channel": "phone"}), ("contacted", {})],
        [
            ("contact_attempted", {"channel": "phone"}),
            ("contacted", {}),
            ("appointment_offered", {}),
        ],
    ):
        referral_id = issue(client, prediction_set=[3])
        for to_state, kwargs in prelude:
            assert patch(client, referral_id, to_state, **kwargs).status_code == 200
        res = patch(client, referral_id, "abandoned", reason="moved away")
        assert res.status_code == 200, res.text
        assert res.json()["state"] == "abandoned"


@pytest.mark.parametrize("to_state", ["contacted", "appointment_offered", "examined"])
def test_skipping_a_step_is_a_409(client, to_state):
    referral_id = issue(client, prediction_set=[3])
    res = patch(client, referral_id, to_state)
    assert res.status_code == 409
    assert "cannot go from 'issued'" in res.json()["detail"]


@pytest.mark.parametrize("terminal", ["examined", "abandoned"])
def test_a_terminal_state_accepts_nothing_further(client, terminal):
    referral_id = issue(client, prediction_set=[3])
    if terminal == "examined":
        patch(client, referral_id, "contact_attempted", channel="phone")
        patch(client, referral_id, "contacted")
        patch(client, referral_id, "appointment_offered")
        patch(client, referral_id, "examined")
    else:
        patch(client, referral_id, "abandoned", reason="declined")
    res = patch(client, referral_id, "contact_attempted", channel="phone")
    assert res.status_code == 409
    assert "terminal" in res.json()["detail"]


def test_contact_attempted_without_a_channel_is_a_422(client):
    referral_id = issue(client, prediction_set=[3])
    res = patch(client, referral_id, "contact_attempted")
    assert res.status_code == 422
    assert "channel" in res.json()["detail"]


def test_abandoned_without_a_reason_is_a_422(client):
    referral_id = issue(client, prediction_set=[3])
    res = patch(client, referral_id, "abandoned")
    assert res.status_code == 422
    assert "reason" in res.json()["detail"]


def test_an_unknown_state_is_rejected_by_the_schema(client):
    referral_id = issue(client, prediction_set=[3])
    res = client.patch(
        f"/v1/referrals/{referral_id}",
        json={"to_state": "escalated", "channel": None, "reason": None},
    )
    assert res.status_code == 422  # not in the frozen Literal


def test_unknown_referral_is_a_404(client):
    res = patch(client, "ref-nope", "contacted")
    assert res.status_code == 404


def test_a_refused_transition_changes_nothing(client, engine):
    referral_id = issue(client, prediction_set=[3])
    with Session(engine) as session:
        before = len(session.exec(select(LedgerEntry)).all())
    assert patch(client, referral_id, "examined").status_code == 409
    with Session(engine) as session:
        assert session.get(Referral, referral_id).state == "issued"
        assert len(session.exec(select(LedgerEntry)).all()) == before
        assert (
            len(
                session.exec(
                    select(ReferralEvent).where(
                        ReferralEvent.referral_id == referral_id
                    )
                ).all()
            )
            == 1  # just the issuing event
        )


# ------------------------------------------- the table, not the handler


def test_the_state_machine_adds_no_state():
    assert set(rs.STATES) == {
        "issued",
        "contact_attempted",
        "contacted",
        "appointment_offered",
        "examined",
        "abandoned",
    }


def test_abandoned_is_the_only_extra_target_of_every_non_terminal_state():
    for state in rs.STATES:
        if state in rs.TERMINAL:
            assert rs.TRANSITIONS[state] == frozenset()
        else:
            assert "abandoned" in rs.TRANSITIONS[state]


def test_a_patch_retry_replays(client):
    referral_id = issue(client, prediction_set=[3])
    headers = {"Idempotency-Key": "patch-once"}
    payload = {"to_state": "contact_attempted", "channel": "phone", "reason": None}
    first = client.patch(f"/v1/referrals/{referral_id}", json=payload, headers=headers)
    second = client.patch(f"/v1/referrals/{referral_id}", json=payload, headers=headers)
    assert first.json() == second.json()
    assert second.headers.get("Idempotency-Replayed") == "true"
