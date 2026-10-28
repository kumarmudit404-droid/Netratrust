/**
 * Verify-result → display state, as a pure function (T-17).
 *
 * The Ledger view's whole job is that `ok:true` and `ok:false` read
 * UNMISTAKABLY differently, because the tamper demo is the moment the project
 * either lands or doesn't. SPEC.md section 7: "A verify button that has only
 * ever returned ok:true does not demonstrate tamper-evidence."
 *
 * The mapping lives here rather than in JSX so both states can be asserted
 * without a browser.
 */

import type { LedgerVerifyResponse } from "./api/types"

export type VerifyDisplay =
  /** Never run in this session. */
  | { kind: "idle" }
  | { kind: "checking" }
  /** Every hash and signature re-checked and matched. */
  | { kind: "ok" }
  /** The server named the first bad entry. This is the demo's payoff state. */
  | { kind: "tampered"; firstBadIndex: number }
  /** ok:false with no index. Lane A always sends one, so this means the
   *  response did not match the contract - reported as itself, not as "fine". */
  | { kind: "failed-without-index" }
  | { kind: "error"; message: string }

export interface VerifyInputs {
  data?: LedgerVerifyResponse
  isFetching: boolean
  isError: boolean
  error?: unknown
  /** False until the operator has pressed Verify at least once. */
  hasRun: boolean
}

export function verifyDisplay(input: VerifyInputs): VerifyDisplay {
  if (!input.hasRun) return { kind: "idle" }
  // A refetch while a previous result is on screen still reads as "checking":
  // during the tamper demo the stale ok:true must not linger as if it were
  // the current answer.
  if (input.isFetching) return { kind: "checking" }
  if (input.isError) {
    return {
      kind: "error",
      message:
        input.error instanceof Error
          ? input.error.message
          : "The API did not respond.",
    }
  }
  if (!input.data) return { kind: "idle" }
  if (input.data.ok) return { kind: "ok" }
  if (typeof input.data.first_bad_index === "number") {
    return { kind: "tampered", firstBadIndex: input.data.first_bad_index }
  }
  return { kind: "failed-without-index" }
}

/** The headline. Short, literal, and never hedged. */
export function verifyHeadline(d: VerifyDisplay): string {
  switch (d.kind) {
    case "idle":
      return "Not verified yet"
    case "checking":
      return "Re-walking the chain…"
    case "ok":
      return "Chain intact"
    case "tampered":
      return `Tampering detected at entry ${d.firstBadIndex}`
    case "failed-without-index":
      return "Chain failed verification"
    case "error":
      return "Could not verify"
  }
}

/** One sentence saying what was actually checked, or actually broken. */
export function verifyExplainer(d: VerifyDisplay): string {
  switch (d.kind) {
    case "idle":
      return "Press Verify to re-walk every entry, recompute its hash and check its Ed25519 signature."
    case "checking":
      return "Recomputing every payload hash and checking every signature."
    case "ok":
      return "Every entry's payload hash, its link to the previous entry and its signature were recomputed and matched."
    case "tampered":
      return `Entry ${d.firstBadIndex} no longer matches its recorded hash. Entries before it verified, so the damage is localised — and it cannot be hidden, because the chain and the signatures do not agree with the edit.`
    case "failed-without-index":
      return "The chain did not verify, but the response named no entry. Treat the ledger as untrusted and check the server."
    case "error":
      return "Verification could not be completed, so the chain's state is unknown. This is not the same as a clean result."
  }
}

/** Maps to a <StatusBadge/> status. `error` and `tampered` are deliberately
 *  different: a failed request is not evidence of tampering. */
export function verifyStatus(
  d: VerifyDisplay,
): "usable" | "reject" | "pending-sync" | "error" {
  switch (d.kind) {
    case "ok":
      return "usable"
    case "tampered":
    case "failed-without-index":
      return "reject"
    case "error":
      return "error"
    default:
      return "pending-sync"
  }
}

/** True for the states that must dominate the screen. */
export function isAlarming(d: VerifyDisplay): boolean {
  return d.kind === "tampered" || d.kind === "failed-without-index"
}

/** One line of the session's verify history, so the ok:true → ok:false
 *  transition is visible as a transition and not just as a current value. */
export interface VerifyHistoryEntry {
  at: number
  ok: boolean
  firstBadIndex: number | null
}

export function describeHistoryEntry(e: VerifyHistoryEntry): string {
  return e.ok
    ? "ok — chain intact"
    : `FAILED — first bad entry ${e.firstBadIndex ?? "unknown"}`
}
