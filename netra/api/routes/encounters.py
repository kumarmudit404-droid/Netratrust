"""POST /v1/encounters - record a screening decision.

Two properties of this handler are load-bearing:

1. **The ledger entry is appended BEFORE the response is returned**, in the same
   transaction as the encounter row. They commit together or not at all, so no
   response can describe a decision that is missing from the ledger
   (rules.md section 4.3).
2. **A rejected image is "no result"**, not a negative DR result. It carries no
   prediction set and no grade, and it is not an abstention either - nothing was
   graded, so there was nothing to abstain from (BUILD_RULES.md, invariant 1).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Header, HTTPException, Request, Response
from sqlmodel import Session, select

from netra.api import idempotency
from netra.api.clinical import ClinicalError, decide
from netra.api.deps import get_state
from netra.api.schemas import EncounterRequest, EncounterResponse
from netra.db.models import Device, Encounter, Site
from netra.db.util import new_id, now_iso
from netra.ledger.chain import append
from netra.ledger.keys import KeyStore

router = APIRouter()

ENDPOINT = "POST /v1/encounters"
#: Auto-registered devices are `device-1`, `device-2`, ... in first-seen order.
AUTO_DEVICE_PREFIX = "device-"

#: Upper bound on auto-registration, so the search for a free kid is bounded.
#: Auto-registration is a known gap (see `_resolve_device`), not a feature to
#: scale: a real deployment enrols devices explicitly.
MAX_AUTO_DEVICES = 1000


def _resolve_device(
    session: Session, keystore: KeyStore, site_id: str, kid: str | None
) -> Device:
    """Find, or on first sight register, the capture device for this encounter.

    SPEC.md's frozen request body has no device field - it names image hash,
    gate verdict, cause, prediction set, model version, site and device_seq. So
    the kid travels as an optional `X-Device-Kid` header, which adds no body
    field and breaks no client, and defaults to the single device registered
    for the site.

    Registering on first sight is a KNOWN GAP, not a design: there is no
    enrolment authority and no authentication anywhere in this build, so any
    caller can name a kid. It is recorded in memory.md rather than hidden here.
    """
    if kid:
        device = session.get(Device, kid)
        if device is not None:
            if device.site_id != site_id:
                raise HTTPException(
                    422, f"device {kid!r} is registered to site {device.site_id!r}"
                )
            return device
    else:
        existing = session.exec(
            select(Device).where(Device.site_id == site_id).order_by(Device.kid)
        ).first()
        if existing is not None:
            return existing
        kid = _free_default_kid(session)

    device = Device(
        kid=kid,
        site_id=site_id,
        ed25519_pub=keystore.public_hex(kid),
        registered_at=now_iso(),
    )
    session.add(device)
    session.flush()
    return device


def _free_default_kid(session: Session) -> str:
    """The first unused `device-N`, for a site that has no device yet.

    A single fixed default is not enough once there is more than one site.
    `kid` is the primary key of `devices` and a device belongs to exactly one
    site, so the SECOND site to post an encounter with no `X-Device-Kid` header
    used to collide on `device-1` and fail the INSERT - a 500 on a request that
    is entirely valid. Every test before this one used a single site, which is
    why it stood: `tests/test_encounters.py` now covers two.

    Numbering is per database, not per site, because the kid identifies a
    device and a device is not shared between sites.
    """
    for n in range(1, MAX_AUTO_DEVICES + 1):
        kid = f"{AUTO_DEVICE_PREFIX}{n}"
        if session.get(Device, kid) is None:
            return kid
    raise HTTPException(
        507,
        f"no free auto-registered device kid below {MAX_AUTO_DEVICES}; "
        f"send an explicit X-Device-Kid header",
    )


@router.post("/v1/encounters", response_model=EncounterResponse)
def create_encounter(
    body: EncounterRequest,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    device_kid: str | None = Header(default=None, alias="X-Device-Kid"),
) -> EncounterResponse:
    state = get_state(request)

    try:
        claim = idempotency.begin(
            state.engine, idempotency_key, ENDPOINT, body.model_dump()
        )
    except idempotency.Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except idempotency.FingerprintMismatch as exc:
        raise HTTPException(422, str(exc)) from exc

    if claim.is_replay:
        # At-least-once delivery: the device retried a request we already
        # applied. Replay the stored response; never create a second encounter.
        response.headers["Idempotency-Replayed"] = "true"
        return EncounterResponse(**claim.replay)

    try:
        with Session(state.engine) as session:
            if session.get(Site, body.site_id) is None:
                raise HTTPException(404, f"unknown site {body.site_id!r}")

            try:
                dr_grade, abstained = decide(body.gate_verdict, body.prediction_set)
            except ClinicalError as exc:
                raise HTTPException(422, str(exc)) from exc

            device = _resolve_device(session, state.keystore, body.site_id, device_kid)
            created_at = now_iso()
            encounter = Encounter(
                id=new_id("enc"),
                site_id=body.site_id,
                device_kid=device.kid,
                quality_verdict=body.gate_verdict,
                cause=body.cause,
                image_sha256=body.image_sha256,
                dr_grade=dr_grade,
                abstained=abstained,
                prediction_set=(
                    None
                    if body.prediction_set is None
                    else json.dumps(body.prediction_set, separators=(",", ":"))
                ),
                model_version=body.model_version,
                device_seq=body.device_seq,
                created_at=created_at,
            )
            session.add(encounter)
            session.flush()

            # Append BEFORE returning, in this transaction. No floats: the
            # prediction set is a list of ints and every id is a string.
            entry = append(
                session,
                {
                    "type": "encounter",
                    "encounter_id": encounter.id,
                    "site_id": encounter.site_id,
                    "device_kid": encounter.device_kid,
                    "image_sha256": encounter.image_sha256,
                    "gate_verdict": encounter.quality_verdict,
                    "cause": encounter.cause,
                    "prediction_set": body.prediction_set,
                    "dr_grade": dr_grade,
                    "abstained": abstained,
                    "model_version": encounter.model_version,
                    "device_seq": encounter.device_seq,
                    "created_at": created_at,
                },
                device.kid,
                state.keystore,
            )
            result = EncounterResponse(encounter_id=encounter.id, ledger_idx=entry.seq)
            session.commit()
    except Exception:
        # The work failed, so drop the in-flight claim and let the device retry.
        idempotency.release(state.engine, idempotency_key)
        raise

    idempotency.complete(state.engine, idempotency_key, result.model_dump())
    return result
