/**
 * Typed client for the nine frozen endpoints in SPEC.md.
 *
 * One function per endpoint, no more and no fewer. Adding an endpoint here
 * would break the frozen contract — raise it with Lane A instead.
 *
 * The real API is the DEFAULT. Set VITE_USE_MOCK=1 to serve every call from
 * src/lib/api/mock.ts instead — a fallback for working on screens with no
 * backend running, not the normal path.
 *
 * The default is inverted in code rather than set in a .env file because
 * `.env` is gitignored at the repo root, so a flag written there would switch
 * the mock off on one machine only and silently leave everyone else on fake
 * data.
 *
 * With VITE_API_BASE empty, requests go to a relative /v1 path and the Vite
 * dev server proxies them to http://127.0.0.1:8000 (see vite.config.ts). That
 * makes dev same-origin; set VITE_API_BASE=http://localhost:8000 to bypass the
 * proxy and exercise Lane A's CORS directly, which is what a deployed build
 * will do.
 */

import { ApiError } from "./errors"
import { mock } from "./mock"
import type {
  EncounterRequest,
  EncounterResponse,
  LedgerCheckpointResponse,
  LedgerVerifyResponse,
  QueueDepthResponse,
  ReferralCreateResponse,
  ReferralPatchRequest,
  ReferralPatchResponse,
  SiteAuditRequest,
  SiteAuditResponse,
  SiteMetricsResponse,
  SiteStatusResponse,
} from "./types"

const BASE = import.meta.env.VITE_API_BASE ?? ""
// Opt IN to the mock. Previously this read `!== "0"`, which defaulted every
// developer and every build to fake data unless they knew to turn it off.
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "1"

/** Per-ACTION idempotency key. SPEC.md: at-least-once delivery with server-side
 *  dedup — 409 if the key is still in flight, 422 if reused with a different
 *  payload. Never claim exactly-once.
 *
 *  Every mutating call sends one. Without it the server cannot dedup, and a
 *  retried delivery is applied twice: a repeated `contact_attempted` would
 *  increment `attempt_n` again, which is a clinical record that reads as two
 *  real contact attempts. A fresh UUID per call is correct — two deliberate
 *  actions are two events; it is the REDELIVERY of one action that must be
 *  collapsed. */
function newIdempotencyKey(): string {
  return crypto.randomUUID()
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  headers: Record<string, string> = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const j = (await res.json()) as { detail?: string }
      if (j.detail) detail = j.detail
    } catch {
      // non-JSON error body; keep the status text
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

export const api = {
  /** POST /v1/encounters -> {encounter_id, ledger_idx} */
  createEncounter(
    body: EncounterRequest,
    idempotencyKey: string = newIdempotencyKey(),
  ): Promise<EncounterResponse> {
    if (USE_MOCK) return mock.createEncounter(body)
    return request<EncounterResponse>("POST", "/v1/encounters", body, {
      "Idempotency-Key": idempotencyKey,
    })
  },

  /** POST /v1/referrals -> {referral_id, state:"issued"} */
  createReferral(
    encounterId: string,
    idempotencyKey: string = newIdempotencyKey(),
  ): Promise<ReferralCreateResponse> {
    if (USE_MOCK) return mock.createReferral()
    return request<ReferralCreateResponse>(
      "POST",
      "/v1/referrals",
      { encounter_id: encounterId },
      { "Idempotency-Key": idempotencyKey },
    )
  },

  /** PATCH /v1/referrals/{id} -> {referral_id, state, ledger_idx} */
  patchReferral(
    id: string,
    body: ReferralPatchRequest,
    idempotencyKey: string = newIdempotencyKey(),
  ): Promise<ReferralPatchResponse> {
    if (USE_MOCK) return mock.patchReferral(id, body)
    return request<ReferralPatchResponse>(
      "PATCH",
      `/v1/referrals/${encodeURIComponent(id)}`,
      body,
      { "Idempotency-Key": idempotencyKey },
    )
  },

  /** GET /v1/ledger/verify -> {ok, first_bad_index} */
  verifyLedger(): Promise<LedgerVerifyResponse> {
    if (USE_MOCK) return mock.verifyLedger()
    return request<LedgerVerifyResponse>("GET", "/v1/ledger/verify")
  },

  /** GET /v1/ledger/checkpoint -> signed head */
  ledgerCheckpoint(): Promise<LedgerCheckpointResponse> {
    if (USE_MOCK) return mock.checkpoint()
    return request<LedgerCheckpointResponse>("GET", "/v1/ledger/checkpoint")
  },

  /** GET /v1/sites/{id}/status
   *  TODO(Lane A): response shape is TBD — see SiteStatusResponse in types.ts. */
  siteStatus(siteId: string): Promise<SiteStatusResponse> {
    if (USE_MOCK) return mock.siteStatus(siteId)
    return request<SiteStatusResponse>(
      "GET",
      `/v1/sites/${encodeURIComponent(siteId)}/status`,
    )
  },

  /** POST /v1/sites/{id}/audit -> {passed, pinned_model_version}
   *  Also keyed: a redelivered audit would append a second audit entry to the
   *  ledger and move `last_audit`, so it has the same hazard as a referral. */
  siteAudit(
    siteId: string,
    payload: SiteAuditRequest,
    idempotencyKey: string = newIdempotencyKey(),
  ): Promise<SiteAuditResponse> {
    if (USE_MOCK) return mock.siteAudit()
    return request<SiteAuditResponse>(
      "POST",
      `/v1/sites/${encodeURIComponent(siteId)}/audit`,
      payload,
      { "Idempotency-Key": idempotencyKey },
    )
  },

  /** GET /v1/metrics/sites -> per-site rows, never a mean */
  siteMetrics(): Promise<SiteMetricsResponse> {
    if (USE_MOCK) return mock.siteMetrics()
    return request<SiteMetricsResponse>("GET", "/v1/metrics/sites")
  },

  /** GET /v1/queue/depth -> {queued, synced, attempts}
   *  TODO(Lane A): `attempts` element type is TBD — see QueueDepthResponse. */
  queueDepth(): Promise<QueueDepthResponse> {
    if (USE_MOCK) return mock.queueDepth()
    return request<QueueDepthResponse>("GET", "/v1/queue/depth")
  },
}

export { ApiError }
export const usingMock = USE_MOCK
