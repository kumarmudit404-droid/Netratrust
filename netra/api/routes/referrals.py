"""POST /v1/referrals and PATCH /v1/referrals/{id}.

Every transition writes a `referral_events` row AND a ledger entry, in the same
transaction as the `referrals.state` update. `referrals` is the only mutable
table in the clinical path, and it is mutable precisely because its history is
kept somewhere that is not.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, Response
from sqlmodel import Session, func, select

from netra.api import idempotency, referral_state
from netra.api.clinical import is_referable_encounter
from netra.api.deps import get_state
from netra.api.schemas import (
    ReferralCreateRequest,
    ReferralCreateResponse,
    ReferralPatchRequest,
    ReferralPatchResponse,
)
from netra.db.models import Encounter, Referral, ReferralEvent
from netra.db.util import new_id, now_iso
from netra.ledger.chain import append

router = APIRouter()

CREATE_ENDPOINT = "POST /v1/referrals"
PATCH_ENDPOINT = "PATCH /v1/referrals/{id}"


@router.post("/v1/referrals", response_model=ReferralCreateResponse)
def create_referral(
    body: ReferralCreateRequest,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ReferralCreateResponse:
    state = get_state(request)

    try:
        claim = idempotency.begin(
            state.engine, idempotency_key, CREATE_ENDPOINT, body.model_dump()
        )
    except idempotency.Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except idempotency.FingerprintMismatch as exc:
        raise HTTPException(422, str(exc)) from exc
    if claim.is_replay:
        response.headers["Idempotency-Replayed"] = "true"
        return ReferralCreateResponse(**claim.replay)

    try:
        with Session(state.engine) as session:
            encounter = session.get(Encounter, body.encounter_id)
            if encounter is None:
                raise HTTPException(404, f"unknown encounter {body.encounter_id!r}")

            # No referral from an abstention (SPEC.md section 7: a clinician
            # decides), none without a grade, and so none from a rejected
            # image - a failed gate is "no result", not a negative result.
            if not is_referable_encounter(encounter.dr_grade, encounter.abstained):
                raise HTTPException(
                    422,
                    "encounter is not referable: it has no referable grade, or it "
                    "abstained and a clinician must decide",
                )

            existing = session.exec(
                select(Referral).where(Referral.encounter_id == encounter.id)
            ).first()
            if existing is not None:
                raise HTTPException(
                    409, f"encounter already has referral {existing.id!r}"
                )

            created_at = now_iso()
            referral = Referral(
                id=new_id("ref"),
                encounter_id=encounter.id,
                state=referral_state.ISSUED,
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(referral)
            session.flush()
            session.add(
                ReferralEvent(
                    id=new_id("rev"),
                    referral_id=referral.id,
                    from_state="",
                    to_state=referral_state.ISSUED,
                    created_at=created_at,
                )
            )
            append(
                session,
                {
                    "type": "referral_issued",
                    "referral_id": referral.id,
                    "encounter_id": encounter.id,
                    "site_id": encounter.site_id,
                    "dr_grade": encounter.dr_grade,
                    "state": referral_state.ISSUED,
                    "created_at": created_at,
                },
                encounter.device_kid,
                state.keystore,
            )
            result = ReferralCreateResponse(
                referral_id=referral.id, state=referral_state.ISSUED
            )
            session.commit()
    except Exception:
        idempotency.release(state.engine, idempotency_key)
        raise

    idempotency.complete(state.engine, idempotency_key, result.model_dump())
    return result


@router.patch("/v1/referrals/{referral_id}", response_model=ReferralPatchResponse)
def patch_referral(
    referral_id: str,
    body: ReferralPatchRequest,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ReferralPatchResponse:
    state = get_state(request)

    try:
        claim = idempotency.begin(
            state.engine,
            idempotency_key,
            PATCH_ENDPOINT,
            {"referral_id": referral_id, **body.model_dump()},
        )
    except idempotency.Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except idempotency.FingerprintMismatch as exc:
        raise HTTPException(422, str(exc)) from exc
    if claim.is_replay:
        response.headers["Idempotency-Replayed"] = "true"
        return ReferralPatchResponse(**claim.replay)

    try:
        with Session(state.engine) as session:
            referral = session.get(Referral, referral_id)
            if referral is None:
                raise HTTPException(404, f"unknown referral {referral_id!r}")

            try:
                referral_state.check(
                    referral.state, body.to_state, body.channel, body.reason
                )
            except referral_state.TransitionError as exc:
                raise HTTPException(409, str(exc)) from exc
            except referral_state.TransitionDataError as exc:
                raise HTTPException(422, str(exc)) from exc

            attempt_n = None
            if body.to_state == referral_state.CONTACT_ATTEMPTED:
                attempt_n = _next_attempt(session, referral.id)

            from_state = referral.state
            created_at = now_iso()
            session.add(
                ReferralEvent(
                    id=new_id("rev"),
                    referral_id=referral.id,
                    from_state=from_state,
                    to_state=body.to_state,
                    attempt_n=attempt_n,
                    channel=body.channel,
                    reason=body.reason,
                    created_at=created_at,
                )
            )
            referral.state = body.to_state
            referral.updated_at = created_at
            session.add(referral)

            encounter = session.get(Encounter, referral.encounter_id)
            entry = append(
                session,
                {
                    "type": "referral_transition",
                    "referral_id": referral.id,
                    "encounter_id": referral.encounter_id,
                    "from_state": from_state,
                    "to_state": body.to_state,
                    "attempt_n": attempt_n,
                    "channel": body.channel,
                    "reason": body.reason,
                    "created_at": created_at,
                },
                encounter.device_kid,
                state.keystore,
            )
            result = ReferralPatchResponse(
                referral_id=referral.id, state=body.to_state, ledger_idx=entry.seq
            )
            session.commit()
    except Exception:
        idempotency.release(state.engine, idempotency_key)
        raise

    idempotency.complete(state.engine, idempotency_key, result.model_dump())
    return result


def _next_attempt(session: Session, referral_id: str) -> int:
    """`contact_attempted` is repeatable, so attempts are counted, not assumed."""
    previous = session.exec(
        select(func.count())
        .select_from(ReferralEvent)
        .where(
            ReferralEvent.referral_id == referral_id,
            ReferralEvent.to_state == referral_state.CONTACT_ATTEMPTED,
        )
    ).one()
    return int(previous) + 1
