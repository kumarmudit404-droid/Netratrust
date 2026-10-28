/**
 * In-memory mock responder so Lane B screens work before the backend is up.
 *
 * This is a DEMO AID, not a model of the backend. It deliberately does not
 * reimplement the ledger, the hash chain or the state machine — those live in
 * Lane A and duplicating them here would create a second source of truth.
 * Enabled by VITE_USE_MOCK=1.
 */

import { ApiError } from "./errors"
import type {
  EncounterRequest,
  EncounterResponse,
  LedgerCheckpointResponse,
  LedgerVerifyResponse,
  QueueDepthResponse,
  ReferralCreateResponse,
  ReferralPatchRequest,
  ReferralPatchResponse,
  SiteAuditResponse,
  SiteMetricsResponse,
  SiteStatusResponse,
} from "./types"

const MODEL_VERSION = "convnext_tiny.in12k_ft_in1k@mock"

let ledgerIdx = 1042
const nextLedgerIdx = () => ++ledgerIdx

/** Short pseudo-hex, for display only. Not a real hash. */
function fakeHex(len: number): string {
  let out = ""
  while (out.length < len) out += Math.floor(Math.random() * 16).toString(16)
  return out.slice(0, len)
}

const delay = (ms = 180) => new Promise((r) => setTimeout(r, ms))

/** `?tamper=2` -> 2. Anything else (or no DOM) -> null. See verifyLedger. */
export function tamperedSeq(search?: string): number | null {
  const raw =
    search ??
    (typeof window === "undefined" ? "" : window.location.search)
  const value = new URLSearchParams(raw).get("tamper")
  // Digits only. `Number("")` is 0, so a bare `?tamper=` would otherwise
  // render as "Tampering detected at entry 0" - a fabricated finding.
  if (value === null || !/^\d+$/.test(value)) return null
  return Number(value)
}

export const mock = {
  async createEncounter(body: EncounterRequest): Promise<EncounterResponse> {
    await delay()
    // Mirrors the clinical invariant the API enforces: a rejected image is
    // "no result" and can carry no prediction set.
    if (body.gate_verdict === "reject" && body.prediction_set !== null) {
      throw new ApiError(422, "a rejected image cannot carry a prediction set")
    }
    return { encounter_id: `enc-${fakeHex(8)}`, ledger_idx: nextLedgerIdx() }
  },

  async createReferral(): Promise<ReferralCreateResponse> {
    await delay()
    return { referral_id: `ref-${fakeHex(8)}`, state: "issued" }
  },

  async patchReferral(
    id: string,
    body: ReferralPatchRequest,
  ): Promise<ReferralPatchResponse> {
    await delay()
    return { referral_id: id, state: body.to_state, ledger_idx: nextLedgerIdx() }
  },

  async verifyLedger(): Promise<LedgerVerifyResponse> {
    await delay()
    // Against the real API the ok:false state comes from running
    // `python -m netra.ledger.tamper --seq N`. The mock has no ledger to
    // corrupt, so `?tamper=2` simulates the result for designing and
    // reviewing that screen. It exists ONLY inside the mock responder, which
    // is itself opt-in via VITE_USE_MOCK=1, so it can never affect a build
    // talking to the real API - and it is not an endpoint.
    const seq = tamperedSeq()
    if (seq !== null) return { ok: false, first_bad_index: seq }
    return { ok: true, first_bad_index: null }
  },

  async checkpoint(): Promise<LedgerCheckpointResponse> {
    await delay()
    return {
      idx: ledgerIdx,
      head_hash: fakeHex(64),
      ts: new Date().toISOString(),
      signature: fakeHex(128),
      signer_kid: "device-1",
    }
  },

  async siteStatus(siteId: string): Promise<SiteStatusResponse> {
    await delay()
    // site-11 has never passed an audit, so it exercises Lane A's "unpinned"
    // sentinel and the "no audited model yet" rendering. Without one such
    // site in the mock, that branch is only ever seen against the real API.
    const unaudited = siteId === "site-11"
    // n = 27 on purpose: below min_n_for_rate (30), so the n<30 rule is
    // exercised by default rather than only in an edge case.
    return {
      site_id: siteId,
      model_version: unaudited ? "unpinned" : MODEL_VERSION,
      last_audit: unaudited ? null : new Date().toISOString(),
      gradability: { k: 22, n: 27, ci: [0.633, 0.9182] },
      drift_flag: siteId === "site-07",
    }
  },

  async siteAudit(): Promise<SiteAuditResponse> {
    await delay()
    return { passed: true, pinned_model_version: MODEL_VERSION }
  },

  async siteMetrics(): Promise<SiteMetricsResponse> {
    await delay()
    return {
      rows: [
        {
          site_id: "site-02",
          gradability: { k: 140, n: 203, ci: [0.623, 0.7493] },
          abstention: { k: 31, n: 203, ci: [0.1097, 0.2086] },
          drift_flag: false,
        },
        {
          site_id: "site-03",
          gradability: { k: 96, n: 118, ci: [0.7338, 0.8735] },
          abstention: { k: 14, n: 118, ci: [0.072, 0.1893] },
          drift_flag: false,
        },
        {
          site_id: "site-07",
          gradability: { k: 22, n: 27, ci: [0.633, 0.9182] },
          abstention: { k: 6, n: 27, ci: [0.1061, 0.4076] },
          drift_flag: true,
        },
        {
          site_id: "site-11",
          gradability: { k: 47, n: 64, ci: [0.6152, 0.827] },
          abstention: { k: 9, n: 64, ci: [0.0758, 0.2462] },
          drift_flag: false,
        },
      ],
      pooled: { gradability: { k: 305, n: 412, ci: [0.6959, 0.7803] } },
    }
  },

  async queueDepth(): Promise<QueueDepthResponse> {
    await delay()
    return { queued: 14, synced: 388, attempts: [] }
  },
}
