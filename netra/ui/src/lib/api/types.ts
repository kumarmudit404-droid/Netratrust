/**
 * Types for the nine frozen endpoints in SPEC.md "API contract".
 *
 * Rules carried over from SPEC.md / CLAUDE.md:
 *  - IDs and timestamps are STRINGS (ints above 2^53 raise in rfc8785).
 *  - `ledger_idx` / `idx` are ints below 2^53, so `number` is safe.
 *  - No floats anywhere near a ledger payload: scores travel as scaled ints
 *    or strings.
 *  - Fundus images are NEVER uploaded. Only the hash, the decisions, metadata.
 *
 * Where SPEC.md describes a response in prose rather than naming fields, the
 * shape below is marked TBD and must be confirmed with Lane A before it is
 * relied on. Nothing here invents a field the contract does not imply.
 */

// ---------------------------------------------------------------- shared

/** Quality-gate verdict. A `reject` is NOT a negative DR result. */
export type GateVerdict = "usable" | "borderline" | "reject"

/** Referral states, exactly as frozen in SPEC.md. Do not add a state. */
export type ReferralState =
  | "issued"
  | "contact_attempted"
  | "contacted"
  | "appointment_offered"
  | "examined"
  | "abandoned"

/** DR severity grade, 5-class. */
export type Grade = 0 | 1 | 2 | 3 | 4

/** A proportion as counts plus a server-computed Wilson interval.
 *  Counts travel, not rates: the denominator is what the n<30 rule needs, and
 *  the front end never computes a statistic (all metrics come from
 *  netra/eval/metrics.py). */
export interface RateCounts {
  k: number
  n: number
  /** Wilson 95% bounds from the server. Absent until Lane A supplies them. */
  ci?: [number, number]
}

// ------------------------------------------- POST /v1/encounters

/** SPEC.md: "image hash, gate verdict, cause, prediction set, model version,
 *  site, device_seq, Idempotency-Key". The Idempotency-Key travels as a
 *  header, not in the body. */
export interface EncounterRequest {
  image_sha256: string
  gate_verdict: GateVerdict
  /** Reason-code from the classical OpenCV channel, e.g. focus / exposure /
   *  fov_mask. Null when the gate admitted the image. */
  cause: string | null
  /** Conformal prediction set. MUST be null when gate_verdict is "reject":
   *  a failed gate is "no result", never a grade. */
  prediction_set: Grade[] | null
  model_version: string
  site_id: string
  device_seq: number
}

export interface EncounterResponse {
  encounter_id: string
  ledger_idx: number
}

// -------------------------------------------- POST /v1/referrals

export interface ReferralCreateRequest {
  encounter_id: string
}

export interface ReferralCreateResponse {
  referral_id: string
  /** SPEC.md fixes this to "issued" on creation. */
  state: Extract<ReferralState, "issued">
}

// ------------------------------------- PATCH /v1/referrals/{id}

export interface ReferralPatchRequest {
  to_state: ReferralState
  /** Required for contact_attempted. */
  channel: string | null
  /** Required for abandoned. */
  reason: string | null
}

export interface ReferralPatchResponse {
  referral_id: string
  state: ReferralState
  ledger_idx: number
}

// ------------------------------------------- GET /v1/ledger/*

export interface LedgerVerifyResponse {
  ok: boolean
  first_bad_index: number | null
}

export interface LedgerCheckpointResponse {
  idx: number
  head_hash: string
  ts: string
  signature: string
  signer_kid: string
}

// --------------------------------------------- GET/POST /v1/sites

/** SPEC.md: "model version, last audit, gradability rate, drift flag".
 *  TBD — verify the exact field names with Lane A. `gradability` is modelled
 *  as counts rather than a bare rate because CLAUDE.md forbids a bare
 *  percentage for n < 30.
 *  TODO(Lane A): GET /v1/sites/{id}/status must return gradability as counts
 *  {k, n, ci} — a bare rate cannot satisfy the n<30 rule. Match this or raise. */
export interface SiteStatusResponse {
  site_id: string
  model_version: string
  /** ISO-8601 string, null until the site has been audited. */
  last_audit: string | null
  gradability: RateCounts
  drift_flag: boolean
}

/** POST /v1/sites/{id}/audit takes an "audit payload" — SPEC.md does not
 *  enumerate its fields. TBD — verify with Lane A before sending one.
 *  TODO(Lane A): define the audit payload fields, then replace this
 *  Record<string, unknown> with the real shape. */
export type SiteAuditRequest = Record<string, unknown>

export interface SiteAuditResponse {
  passed: boolean
  pinned_model_version: string
}

// ------------------------------------- GET /v1/metrics/sites

/** Per-site distribution rows. SPEC.md: "never a mean". `pooled` is the forest
 *  plot's reference line, not a headline number. */
export interface SiteMetricsRow {
  site_id: string
  gradability: RateCounts
  abstention: RateCounts
  drift_flag: boolean
}

export interface SiteMetricsResponse {
  rows: SiteMetricsRow[]
  pooled: { gradability: RateCounts }
}

// ------------------------------------------ GET /v1/queue/depth

/** SPEC.md: `{queued:int, synced:int, attempts:[...]}`. The element type of
 *  `attempts` is not specified. TBD — verify with Lane A.
 *  TODO(Lane A): specify the element type of `attempts`; it is typed
 *  unknown[] until then so no screen can rely on a guessed field. */
export interface QueueDepthResponse {
  queued: number
  synced: number
  attempts: unknown[]
}
