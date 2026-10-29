/**
 * Binding the queue to the real client, and the write-ahead rule.
 *
 * EVERY mutation is enqueued first and sent second — including when the device
 * is plainly online. Two reasons, both about correctness rather than tidiness:
 *
 * 1. The idempotency key is minted at enqueue, so the key that goes out on the
 *    first attempt is the key that goes out on every retry. "Try, and queue it
 *    if that failed" has to mint the key before the attempt anyway, and then
 *    has two code paths that must agree about it. One path cannot disagree
 *    with itself.
 * 2. Order. A capture taken now must not overtake one taken five minutes ago
 *    that has still to land, or the ledger records them backwards.
 *
 * The cost is a `localStorage` round-trip per action, which at camp volumes is
 * nothing.
 */

import { api } from "../api/client"
import type { EncounterRequest, EncounterResponse } from "../api/types"
import {
  SyncQueue,
  type DrainReport,
  type NewMutation,
  type QueuedMutation,
  type Sender,
} from "./queue"

/** Sends one queued entry through the typed client, with the ENTRY's key. */
export const apiSender: Sender = (entry: QueuedMutation) => {
  switch (entry.kind) {
    case "encounter":
      return api.createEncounter(entry.payload, entry.idempotencyKey)
    case "referral":
      return api.createReferral(entry.payload.encounterId, entry.idempotencyKey)
    case "referralPatch":
      return api.patchReferral(
        entry.payload.referralId,
        entry.payload.body,
        entry.idempotencyKey,
      )
    case "siteAudit":
      return api.siteAudit(
        entry.payload.siteId,
        entry.payload.body,
        entry.idempotencyKey,
      )
  }
}

export interface SubmitResult {
  /** The server's answer, or null when the entry is still queued. */
  response: unknown
  /** True when this action has NOT reached the server yet. */
  queued: boolean
  report: DrainReport
}

/**
 * Enqueue, then try to drain. The action is recorded either way.
 *
 * A `queued: true` result is not an error and must not be shown as one:
 * offline is the normal condition for a screening camp, and the capture has
 * been accepted by the device.
 */
export async function submitOrQueue(
  queue: SyncQueue,
  item: NewMutation,
  send: Sender = apiSender,
): Promise<SubmitResult> {
  const entry = queue.enqueue(item)
  const report = await queue.drain(send)
  const landed = report.applied.find((a) => a.entry.id === entry.id)
  const refused = report.dropped.find((d) => d.entry.id === entry.id)

  if (refused) {
    // A permanent refusal IS an error: the operator has to see that this
    // capture was rejected rather than believe it is waiting to sync.
    throw new Error(refused.reason)
  }

  return {
    response: landed ? landed.response : null,
    queued: !landed,
    report,
  }
}

/** `submitOrQueue` for a capture, typed to the response the screen needs. */
export async function submitEncounter(
  queue: SyncQueue,
  payload: EncounterRequest,
  send: Sender = apiSender,
): Promise<{ response: EncounterResponse | null; queued: boolean }> {
  const result = await submitOrQueue(queue, { kind: "encounter", payload }, send)
  return {
    response: (result.response as EncounterResponse | null) ?? null,
    queued: result.queued,
  }
}

/** The app's single queue. One per device, so one per page. */
export const deviceQueue = new SyncQueue()
