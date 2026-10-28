"""Request and response models for the nine frozen endpoints.

These shapes are checked against Lane B's typed client in
`netra/ui/src/lib/api/types.ts`. Where that file carried a `TODO(Lane A)`
because SPEC.md described a response in prose, the shape is settled here and
the reason is recorded. Nothing below adds, renames or removes a field of the
frozen contract.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GateVerdict = Literal["usable", "borderline", "reject"]
ReferralStateName = Literal[
    "issued",
    "contact_attempted",
    "contacted",
    "appointment_offered",
    "examined",
    "abandoned",
]

SHA256_HEX = r"^[0-9a-f]{64}$"
#: ledger seq / ledger_idx stay below 2^53 (rfc8785), and device_seq with them.
MAX_SAFE_INT = 9_007_199_254_740_991


class Strict(BaseModel):
    """Reject unknown fields. A typo in a client becomes a 422, not a silent drop."""

    model_config = ConfigDict(extra="forbid")


class RateCounts(BaseModel):
    """A proportion as counts plus a server-computed Wilson interval.

    Counts travel, not rates: the denominator is what the n < 30 rule needs, and
    the front end never computes a statistic. `ci` comes from
    `netra.eval.metrics.wilson_interval` - the single source for every number
    the team reports.
    """

    k: int
    n: int
    ci: tuple[float, float]


# ------------------------------------------------- POST /v1/encounters


class EncounterRequest(Strict):
    """SPEC.md: image hash, gate verdict, cause, prediction set, model version,
    site, device_seq. `Idempotency-Key` travels as a header, not in the body."""

    image_sha256: str = Field(pattern=SHA256_HEX)
    gate_verdict: GateVerdict
    cause: str | None = None
    prediction_set: list[int] | None = None
    model_version: str = Field(min_length=1)
    site_id: str = Field(min_length=1)
    device_seq: int = Field(ge=0, le=MAX_SAFE_INT)


class EncounterResponse(BaseModel):
    encounter_id: str
    ledger_idx: int


# -------------------------------------------------- POST /v1/referrals


class ReferralCreateRequest(Strict):
    encounter_id: str = Field(min_length=1)


class ReferralCreateResponse(BaseModel):
    referral_id: str
    state: Literal["issued"]


# ------------------------------------------- PATCH /v1/referrals/{id}


class ReferralPatchRequest(Strict):
    to_state: ReferralStateName
    channel: str | None = None  # required for contact_attempted
    reason: str | None = None  # required for abandoned


class ReferralPatchResponse(BaseModel):
    referral_id: str
    state: ReferralStateName
    ledger_idx: int


# --------------------------------------------------- GET /v1/ledger/*


class LedgerVerifyResponse(BaseModel):
    ok: bool
    first_bad_index: int | None


class LedgerCheckpointResponse(BaseModel):
    idx: int
    head_hash: str
    ts: str
    signature: str
    signer_kid: str


# ----------------------------------------------------- /v1/sites/{id}


class SiteStatusResponse(BaseModel):
    """`gradability` is counts + Wilson, never a bare rate (CLAUDE.md, n < 30).

    `model_version` is the version pinned by the most recent PASSED audit. A
    site that has never been audited reports `"unpinned"` rather than null,
    because Lane B's `SiteStatusResponse.model_version` is a non-nullable
    string - and "unpinned" is the honest reading: SPEC.md section 6 says a
    site must pass a local audit before its grades count.
    """

    site_id: str
    model_version: str
    last_audit: str | None
    gradability: RateCounts
    drift_flag: bool


class SiteAuditRequest(Strict):
    """The audit payload SPEC.md section 6 describes but does not enumerate.

    Everything is COUNTS, not rates: this payload is appended to the ledger and
    floats are banned there. `grade_counts` keys are the grades as strings.
    """

    pinned_model_version: str = Field(min_length=1)
    gradable_k: int = Field(ge=0, le=MAX_SAFE_INT)
    gradable_n: int = Field(ge=0, le=MAX_SAFE_INT)
    agreement_k: int = Field(ge=0, le=MAX_SAFE_INT)
    agreement_n: int = Field(ge=0, le=MAX_SAFE_INT)
    grade_counts: dict[str, int] = Field(default_factory=dict)
    drift_flag: bool = False


class SiteAuditResponse(BaseModel):
    passed: bool
    pinned_model_version: str


# ----------------------------------------------- GET /v1/metrics/sites


class SiteMetricsRow(BaseModel):
    site_id: str
    gradability: RateCounts
    abstention: RateCounts
    drift_flag: bool


class SiteMetricsResponse(BaseModel):
    """Per-site distribution rows, never a mean (SPEC.md).

    `pooled` is the forest plot's reference line, not a headline number.
    """

    rows: list[SiteMetricsRow]
    pooled: dict[Literal["gradability"], RateCounts]


# ------------------------------------------------ GET /v1/queue/depth


class QueueAttempt(BaseModel):
    """One delivery attempt the SERVER has seen, newest first.

    SPEC.md gives `attempts:[...]` without an element type; this is the only
    attempt data the server holds - a row of `idempotency_keys`. It is a
    delivery record, not a clinical queue.
    """

    key: str
    endpoint: str
    status: Literal["in_flight", "done"]
    created_at: str


class QueueDepthResponse(BaseModel):
    """`queued` is the SERVER's view of the sync backlog: deliveries accepted
    and not yet applied. It is NOT a count of cases awaiting a specialist, and
    it is not the device's local queue - the server cannot see that.
    SPEC.md section 5 puts the connectivity flag server-side so the figure
    survives a page navigation and a second browser tab."""

    queued: int
    synced: int
    attempts: list[QueueAttempt]
