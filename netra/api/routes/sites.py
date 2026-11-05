"""Site status, audit, per-site metrics and queue depth.

Every proportion here travels as COUNTS plus a Wilson interval, never as a bare
rate. Two rules force that: BUILD_RULES.md forbids a bare percentage for n < 30, and
the front end never computes a statistic. The interval comes from
`netra.eval.metrics.wilson_interval` - the single source for every number the
team reports (rules.md section 7).

`GET /v1/metrics/sites` returns per-site rows and a pooled reference line. The
pooled figure is the forest plot's reference, NOT a headline: SPEC.md says
"never a mean", and per-site performance is always a distribution.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, Response
from sqlmodel import Session, func, select

from netra.api import idempotency
from netra.api.deps import get_state
from netra.api.schemas import (
    QueueAttempt,
    QueueDepthResponse,
    RateCounts,
    SiteAuditRequest,
    SiteAuditResponse,
    SiteMetricsResponse,
    SiteMetricsRow,
    SiteStatusResponse,
)
from netra.db.models import Encounter, LedgerEntry, Site
from netra.db.util import now_iso
from netra.eval.metrics import wilson_interval
from netra.ledger.chain import append

router = APIRouter()

AUDIT_ENDPOINT = "POST /v1/sites/{id}/audit"

#: A site that has never passed an audit reports this rather than null: Lane B's
#: `SiteStatusResponse.model_version` is a non-nullable string, and SPEC.md
#: section 6 says a site must pass a local audit before its grades count.
UNPINNED = "unpinned"

AUDIT_TYPE = "site_audit"


def counts(k: int, n: int) -> RateCounts:
    """Counts plus the Wilson interval. The ONLY way a proportion leaves here."""
    lo, hi = wilson_interval(k, n)
    return RateCounts(k=int(k), n=int(n), ci=(lo, hi))


def _gradability(session: Session, site_id: str) -> RateCounts:
    """k = images the gate ADMITTED, n = images the gate saw.

    A rejected image is in the denominator and not the numerator: that is what
    gradability measures. It is never in a denominator for grading ACCURACY -
    a different number, and not one this endpoint reports.
    """
    n = session.exec(
        select(func.count()).select_from(Encounter).where(Encounter.site_id == site_id)
    ).one()
    k = session.exec(
        select(func.count())
        .select_from(Encounter)
        .where(Encounter.site_id == site_id, Encounter.quality_verdict != "reject")
    ).one()
    return counts(int(k), int(n))


def _abstention(session: Session, site_id: str) -> RateCounts:
    """k = admitted images that abstained, n = admitted images.

    The denominator is ADMITTED images, not all images: a rejected image was
    never graded, so it cannot have abstained. Putting rejects in this
    denominator would let a bad camera look like a confident model.
    """
    n = session.exec(
        select(func.count())
        .select_from(Encounter)
        .where(Encounter.site_id == site_id, Encounter.quality_verdict != "reject")
    ).one()
    k = session.exec(
        select(func.count())
        .select_from(Encounter)
        .where(
            Encounter.site_id == site_id,
            Encounter.quality_verdict != "reject",
            Encounter.abstained == True,
        )
    ).one()
    return counts(int(k), int(n))


def _latest_audit(session: Session, site_id: str) -> dict | None:
    """The most recent `site_audit` ledger entry for this site.

    Audit results live in the LEDGER, not in a table of their own. No decision
    exists outside the ledger (BUILD_RULES.md), and an audit result is a decision
    about whether a site's grades count. It also keeps the table count where
    architecture.md section 3 put it.
    """
    import json

    rows = session.exec(select(LedgerEntry).order_by(LedgerEntry.seq.desc())).all()
    for row in rows:
        payload = json.loads(row.payload_json)
        if payload.get("type") == AUDIT_TYPE and payload.get("site_id") == site_id:
            return payload
    return None


@router.get("/v1/sites/{site_id}/status", response_model=SiteStatusResponse)
def site_status(site_id: str, request: Request) -> SiteStatusResponse:
    state = get_state(request)
    with Session(state.engine) as session:
        if session.get(Site, site_id) is None:
            raise HTTPException(404, f"unknown site {site_id!r}")
        audit = _latest_audit(session, site_id)
        return SiteStatusResponse(
            site_id=site_id,
            model_version=(
                audit["pinned_model_version"]
                if audit and audit.get("passed")
                else UNPINNED
            ),
            last_audit=audit["created_at"] if audit else None,
            gradability=_gradability(session, site_id),
            drift_flag=bool(audit["drift_flag"]) if audit else False,
        )


@router.post("/v1/sites/{site_id}/audit", response_model=SiteAuditResponse)
def site_audit(
    site_id: str,
    body: SiteAuditRequest,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> SiteAuditResponse:
    """Record a local audit. The result is appended to the ledger before it returns.

    `passed` is computed, not supplied, from one documented rule:

        passed = gradable_n >= sites.min_n_for_rate
             AND agreement_n >= sites.min_n_for_rate
             AND not drift_flag

    That is deliberately a rule about whether the site is AUDITABLE, not about
    whether it is accurate. `sites.min_n_for_rate` (30) comes from
    `config/thresholds.yaml`; an accuracy or agreement floor is **TBD - verify**
    and needs a clinical decision, so none is invented here. A site that passes
    this means "enough cases to report a rate, and no drift flagged".
    """
    from netra.api.config import load

    state = get_state(request)
    try:
        claim = idempotency.begin(
            state.engine,
            idempotency_key,
            AUDIT_ENDPOINT,
            {"site_id": site_id, **body.model_dump()},
        )
    except idempotency.Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except idempotency.FingerprintMismatch as exc:
        raise HTTPException(422, str(exc)) from exc
    if claim.is_replay:
        response.headers["Idempotency-Replayed"] = "true"
        return SiteAuditResponse(**claim.replay)

    if body.gradable_k > body.gradable_n or body.agreement_k > body.agreement_n:
        idempotency.release(state.engine, idempotency_key)
        raise HTTPException(422, "a numerator cannot exceed its denominator")

    min_n = int(load().get("sites", {}).get("min_n_for_rate", 30))
    passed = (
        body.gradable_n >= min_n and body.agreement_n >= min_n and not body.drift_flag
    )

    try:
        with Session(state.engine) as session:
            if session.get(Site, site_id) is None:
                raise HTTPException(404, f"unknown site {site_id!r}")

            created_at = now_iso()
            # Counts and strings only - no floats in a ledger payload.
            append(
                session,
                {
                    "type": AUDIT_TYPE,
                    "site_id": site_id,
                    "passed": passed,
                    "pinned_model_version": body.pinned_model_version,
                    "gradable_k": body.gradable_k,
                    "gradable_n": body.gradable_n,
                    "agreement_k": body.agreement_k,
                    "agreement_n": body.agreement_n,
                    "grade_counts": {
                        str(g): int(c) for g, c in sorted(body.grade_counts.items())
                    },
                    "drift_flag": body.drift_flag,
                    "min_n_for_rate": min_n,
                    "created_at": created_at,
                },
                _audit_signer(session, site_id),
                state.keystore,
            )
            result = SiteAuditResponse(
                passed=passed, pinned_model_version=body.pinned_model_version
            )
            session.commit()
    except Exception:
        idempotency.release(state.engine, idempotency_key)
        raise

    idempotency.complete(state.engine, idempotency_key, result.model_dump())
    return result


def _audit_signer(session: Session, site_id: str) -> str:
    """Sign an audit with the site's device key, or the server key if it has none."""
    from netra.db.models import Device
    from netra.ledger.keys import SERVER_KID

    device = session.exec(
        select(Device).where(Device.site_id == site_id).order_by(Device.kid)
    ).first()
    return device.kid if device is not None else SERVER_KID


@router.get("/v1/metrics/sites", response_model=SiteMetricsResponse)
def site_metrics(request: Request) -> SiteMetricsResponse:
    """Per-site rows plus a pooled reference line. Never a mean across sites."""
    state = get_state(request)
    with Session(state.engine) as session:
        sites = session.exec(select(Site).order_by(Site.id)).all()
        rows = [
            SiteMetricsRow(
                site_id=site.id,
                gradability=_gradability(session, site.id),
                abstention=_abstention(session, site.id),
                drift_flag=bool(
                    (_latest_audit(session, site.id) or {}).get("drift_flag")
                ),
            )
            for site in sites
        ]
        # Pooled = summed counts, which is the correct denominator for the
        # forest plot's reference line. It is NOT the mean of the per-site
        # rates, and the two differ whenever sites have unequal n.
        pooled_k = sum(r.gradability.k for r in rows)
        pooled_n = sum(r.gradability.n for r in rows)
    return SiteMetricsResponse(
        rows=rows, pooled={"gradability": counts(pooled_k, pooled_n)}
    )


@router.get("/v1/queue/depth", response_model=QueueDepthResponse)
def queue_depth(request: Request) -> QueueDepthResponse:
    """The SERVER's view of the sync backlog.

    `queued` counts deliveries accepted and not yet applied; `synced` counts
    those applied. This is NOT a count of cases awaiting a specialist, and it is
    not the device's local queue - the server cannot see that. SPEC.md section 5
    puts the connectivity flag server-side so the figure survives a page
    navigation and a second browser tab, and that is what this serves.
    """
    state = get_state(request)
    with Session(state.engine) as session:
        queued, synced, attempts = idempotency.depth(session)
    return QueueDepthResponse(
        queued=queued,
        synced=synced,
        attempts=[
            QueueAttempt(
                key=a.key,
                endpoint=a.endpoint,
                status=a.status,
                created_at=a.created_at,
            )
            for a in attempts
        ],
    )
