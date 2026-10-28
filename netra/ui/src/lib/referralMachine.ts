/**
 * The referral state machine, exactly as frozen at the end of SPEC.md's API
 * contract. Used only to decide WHICH ACTIONS TO OFFER.
 *
 *   issued
 *     → contact_attempted (attempt_n, channel)   [repeatable]
 *     → contacted
 *     → appointment_offered
 *     → examined        (terminal, success)
 *     | abandoned(reason)   (terminal, from any non-terminal state)
 *
 * SPEC.md section 7, Referrals view: "actions follow the state machine at the
 * end of the API contract and nothing else." So this is a table, not branching
 * inside a component, and no screen may offer a transition that is not in it.
 *
 * TODO(review): this mirrors `netra/api/referral_state.py`. The SERVER is
 * authoritative and rejects an illegal move with a 409 regardless of what this
 * file says — duplicating it here only stops the UI offering a button that is
 * guaranteed to fail. If the two ever disagree, the server wins and this file
 * is the bug. `src/lib/api/live.test.ts` walks the real machine, which is what
 * would catch a drift.
 */

import type { ReferralState } from "./api/types"

export const TERMINAL: readonly ReferralState[] = ["examined", "abandoned"]

/** Forward moves only; `abandoned` is added to every non-terminal state below. */
const FORWARD: Record<ReferralState, readonly ReferralState[]> = {
  issued: ["contact_attempted"],
  // Repeatable: another attempt is contact_attempted → itself, and the server
  // increments attempt_n from the events it has stored.
  contact_attempted: ["contact_attempted", "contacted"],
  contacted: ["appointment_offered"],
  appointment_offered: ["examined"],
  examined: [],
  abandoned: [],
}

export function isTerminal(state: ReferralState): boolean {
  return TERMINAL.includes(state)
}

/** Every state reachable from `state`, in the order to present them. */
export function allowedTransitions(state: ReferralState): ReferralState[] {
  if (isTerminal(state)) return []
  return [...FORWARD[state], "abandoned"]
}

/** `contact_attempted` needs a channel; `abandoned` needs a reason. */
export function requiresChannel(to: ReferralState): boolean {
  return to === "contact_attempted"
}

export function requiresReason(to: ReferralState): boolean {
  return to === "abandoned"
}

/** Whether the UI should let the operator submit this move yet. */
export function canSubmit(
  from: ReferralState,
  to: ReferralState,
  channel: string,
  reason: string,
): boolean {
  if (!allowedTransitions(from).includes(to)) return false
  if (requiresChannel(to) && !channel.trim()) return false
  if (requiresReason(to) && !reason.trim()) return false
  return true
}

const LABELS: Record<ReferralState, string> = {
  issued: "Issued",
  contact_attempted: "Contact attempted",
  contacted: "Contacted",
  appointment_offered: "Appointment offered",
  examined: "Examined",
  abandoned: "Abandoned",
}

export function stateLabel(state: ReferralState): string {
  return LABELS[state]
}

/** The action wording, written as what the operator just did. */
const ACTIONS: Record<ReferralState, string> = {
  issued: "Re-issue",
  contact_attempted: "Record a contact attempt",
  contacted: "Mark as contacted",
  appointment_offered: "Record an appointment offer",
  examined: "Mark as examined",
  abandoned: "Abandon this referral",
}

export function actionLabel(to: ReferralState): string {
  return ACTIONS[to]
}

/** The happy path, for the progress indicator. `abandoned` is not on it. */
export const HAPPY_PATH: readonly ReferralState[] = [
  "issued",
  "contact_attempted",
  "contacted",
  "appointment_offered",
  "examined",
]

/** How far along the happy path a state sits, or null if it is off it. */
export function pathIndex(state: ReferralState): number | null {
  const i = HAPPY_PATH.indexOf(state)
  return i === -1 ? null : i
}
