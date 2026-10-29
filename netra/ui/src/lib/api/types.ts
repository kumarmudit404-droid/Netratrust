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
 * shape was agreed with Lane A and is pinned from the server side by
 * `tests/test_integration.py`, which parses these interfaces and compares the
 * field names to live responses. Nothing here invents a field the contract
 * does not imply.
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
  /** Wilson 95% bounds, computed server-side by
   *  `netra.eval.metrics.wilson_interval` - the single source for every number
   *  this team reports. Lane A sends it on every rate; it stays optional so a
   *  renderer degrades to the bare counts instead of throwing, which is the
   *  safer failure for a clinical screen. */
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
 *
 *  SETTLED with Lane A. `gradability` is counts, not a bare rate, because
 *  CLAUDE.md forbids a bare percentage for n < 30 and the denominator is what
 *  that rule needs. `model_version` is the non-nullable sentinel "unpinned"
 *  until an audit passes — see modelVersion.ts.
 *
 *  `tests/test_integration.py` parses this interface and compares its field
 *  names to the live response, so the two sides cannot drift silently. */
export interface SiteStatusResponse {
  site_id: string
  model_version: string
  /** ISO-8601 string, null until the site has been audited. */
  last_audit: string | null
  gradability: RateCounts
  drift_flag: boolean
}

/** POST /v1/sites/{id}/audit — the payload SPEC.md section 6 describes but
 *  does not enumerate. SETTLED with Lane A, and everything is COUNTS rather
 *  than rates because this payload is appended to the ledger, where floats are
 *  banned.
 *
 *  `passed` is NOT sent: the server computes it from
 *  `gradable_n >= min_n && agreement_n >= min_n && !drift_flag`, so a client
 *  cannot assert that a site passed its own audit. */
export interface SiteAuditRequest {
  pinned_model_version: string
  /** Images the gate admitted, over images it saw. */
  gradable_k: number
  gradable_n: number
  /** Gate-vs-human agreement, over cases a human also read. */
  agreement_k: number
  agreement_n: number
  /** Grade histogram, keyed by the grade as a string. Optional. */
  grade_counts?: Record<string, number>
  /** Optional; defaults to false server-side. A flagged site cannot pass. */
  drift_flag?: boolean
}

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

/** One delivery attempt the SERVER has seen, newest first.
 *
 *  SETTLED with Lane A: this is a row of `idempotency_keys`, which is the only
 *  attempt data the server holds. It is a DELIVERY record, not a clinical
 *  queue — nothing here is a case waiting for a specialist. */
export interface QueueAttempt {
  key: string
  endpoint: string
  status: "in_flight" | "done"
  created_at: string
}

/** SPEC.md: `{queued:int, synced:int, attempts:[...]}`.
 *
 *  `queued` is the server's view of the sync backlog — deliveries accepted and
 *  not yet applied. It is NOT the device's local queue, which the server cannot
 *  see, and NOT a count of cases a clinician has still to read. SPEC.md
 *  section 5 puts the connectivity flag server-side so this figure survives a
 *  page navigation and a second browser tab. */
export interface QueueDepthResponse {
  queued: number
  synced: number
  attempts: QueueAttempt[]
}
