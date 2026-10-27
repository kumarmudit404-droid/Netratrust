/**
 * Typed client for the nine frozen endpoints in SPEC.md.
 *
 * One function per endpoint, no more and no fewer. Adding an endpoint here
 * would break the frozen contract — raise it with Lane A instead.
 *
 * Set VITE_USE_MOCK=1 to serve every call from src/lib/api/mock.ts so screens
 * work before the backend is up.
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
const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "0"

/** Per-event idempotency key. SPEC.md: at-least-once delivery with server-side
 *  dedup — 409 if the key is still in flight, 422 if reused with a different
 *  payload. Never claim exactly-once. */
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
  createReferral(encounterId: string): Promise<ReferralCreateResponse> {
    if (USE_MOCK) return mock.createReferral()
    return request<ReferralCreateResponse>("POST", "/v1/referrals", {
      encounter_id: encounterId,
    })
  },

  /** PATCH /v1/referrals/{id} -> {referral_id, state, ledger_idx} */
  patchReferral(
    id: string,
    body: ReferralPatchRequest,
  ): Promise<ReferralPatchResponse> {
    if (USE_MOCK) return mock.patchReferral(id, body)
    return request<ReferralPatchResponse>(
      "PATCH",
      `/v1/referrals/${encodeURIComponent(id)}`,
      body,
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
   *  TODO(Lane A): request payload is TBD — see SiteAuditRequest in types.ts. */
  siteAudit(siteId: string, payload: SiteAuditRequest): Promise<SiteAuditResponse> {
    if (USE_MOCK) return mock.siteAudit()
    return request<SiteAuditResponse>(
      "POST",
      `/v1/sites/${encodeURIComponent(siteId)}/audit`,
      payload,
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
