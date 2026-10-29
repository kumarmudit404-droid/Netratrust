/**
 * T-19, device side: capture offline, queue locally, replay on reconnect.
 *
 * The server half shipped with T-04 — `idempotency_keys`, 409 while a key is
 * in flight, 422 when a key is reused with a different payload. Nothing new is
 * needed from it and nothing new is asked of it: the nine endpoints in SPEC.md
 * are frozen, and this adds no tenth.
 *
 * THE KEY IS MINTED ONCE, AT ENQUEUE
 * ----------------------------------
 * That single fact is what makes a replay safe, and it is why this module
 * exists rather than a retry loop around `fetch`. `client.ts` mints a fresh
 * UUID per call by default, which is right for a deliberate action — two taps
 * are two events. A REDELIVERY of one action must carry the key that action was
 * given, or the server cannot tell the two apart: a replayed
 * `contact_attempted` would increment `attempt_n` again and the record would
 * read as two real attempts at reaching a patient.
 *
 * SPEC.md section 5: at-least-once delivery with server-side dedup. Never
 * exactly-once. A queued entry can be delivered twice — the second delivery is
 * deduped by its key and returns the first one's stored response.
 *
 * ORDER
 * -----
 * Strict FIFO, one at a time, and the drain STOPS at the first entry that
 * needs retrying rather than skipping past it. A referral transition is only
 * meaningful after the transition before it, so applying entry 3 while entry 2
 * is unsent would write a history that never happened.
 *
 * A queued entry may NOT depend on an id that another queued entry has still
 * to produce: an encounter's id does not exist until the server assigns it, so
 * a referral for a queued encounter cannot be queued. `canEnqueue` refuses
 * that rather than inventing a placeholder-id scheme nobody asked for.
 */

import { ApiError } from "../api/errors"
import type {
  EncounterRequest,
  ReferralPatchRequest,
  SiteAuditRequest,
} from "../api/types"
import { defaultStorage, type QueueStorage } from "./storage"

// ----------------------------------------------------------------- entries

interface Base {
  /** Local id. Identifies the entry on screen and inside the queue. */
  id: string
  /** Minted once, here. Reused on EVERY delivery attempt. */
  idempotencyKey: string
  enqueuedAt: string
  attempts: number
  lastError?: string
}

export type QueuedMutation =
  | (Base & { kind: "encounter"; payload: EncounterRequest })
  | (Base & { kind: "referral"; payload: { encounterId: string } })
  | (Base & {
      kind: "referralPatch"
      payload: { referralId: string; body: ReferralPatchRequest }
    })
  | (Base & {
      kind: "siteAudit"
      payload: { siteId: string; body: SiteAuditRequest }
    })

export type QueuedKind = QueuedMutation["kind"]

/** What `enqueue` is given: the entry without its bookkeeping. */
export type NewMutation =
  | { kind: "encounter"; payload: EncounterRequest }
  | { kind: "referral"; payload: { encounterId: string } }
  | {
      kind: "referralPatch"
      payload: { referralId: string; body: ReferralPatchRequest }
    }
  | { kind: "siteAudit"; payload: { siteId: string; body: SiteAuditRequest } }

/** Sends one entry, with the entry's own key. Supplied by the caller so this
 *  module never imports the live client and stays testable. */
export type Sender = (entry: QueuedMutation) => Promise<unknown>

// --------------------------------------------------------- classification

/** What to do with a failed delivery. */
export type Disposition = "retry" | "retry-offline" | "drop"

/**
 * Decide from the error alone whether an entry is worth sending again.
 *
 * - **409** is a RETRY, and the reason is easy to get backwards: the server
 *   returns it while this very key is still in flight, which means the request
 *   is being applied right now. Dropping it would discard a clinical record
 *   that the server is in the middle of accepting. The next attempt gets the
 *   stored response.
 * - **422** is a DROP. SPEC.md gives it one meaning here — the key was reused
 *   with a different payload — and no number of retries changes a payload. The
 *   clinical 422s (a reject carrying a prediction set, an abstention being
 *   referred) are just as permanent.
 * - **Any other 4xx** is a DROP for the same reason. A 404 for an unknown site
 *   will not start existing because we asked a fifth time.
 * - **5xx, 408, 429** are RETRIES: the server is unwell, not the request.
 * - **Anything that is not an `ApiError`** never reached a server — a `fetch`
 *   TypeError is what being offline looks like. Retry, and stop the drain,
 *   because the next entry would fail the same way.
 */
export function classify(error: unknown): Disposition {
  if (!(error instanceof ApiError)) return "retry-offline"
  if (error.status === 409 || error.status === 408 || error.status === 429) {
    return "retry"
  }
  if (error.status >= 500) return "retry"
  return "drop"
}

// --------------------------------------------------------------- the queue

/** An entry that landed, with whatever the server answered. The caller needs
 *  the response: an encounter's id and ledger index only exist once the server
 *  has assigned them. */
export interface Applied {
  entry: QueuedMutation
  response: unknown
}

export interface DrainReport {
  applied: Applied[]
  /** Removed as permanently unsendable. */
  dropped: { entry: QueuedMutation; reason: string }[]
  /** Left in the queue, still to go. */
  remaining: number
  /** True when the drain stopped because nothing is reaching the server. */
  offline: boolean
}

interface Stored {
  pending: QueuedMutation[]
  failed: { entry: QueuedMutation; reason: string }[]
}

const EMPTY: Stored = { pending: [], failed: [] }

export class SyncQueue {
  private draining = false
  private readonly listeners = new Set<() => void>()

  constructor(
    private readonly storage: QueueStorage = defaultStorage(),
    private readonly clock: () => string = () => new Date().toISOString(),
    private readonly newId: () => string = () => crypto.randomUUID(),
  ) {}

  // ------------------------------------------------------------- reading

  private load(): Stored {
    const raw = this.storage.read()
    if (!raw) return { ...EMPTY, pending: [], failed: [] }
    try {
      const parsed = JSON.parse(raw) as Partial<Stored>
      return {
        pending: Array.isArray(parsed.pending) ? parsed.pending : [],
        failed: Array.isArray(parsed.failed) ? parsed.failed : [],
      }
    } catch {
      // Corrupt or from an older shape. Losing the queue is bad; refusing to
      // start is worse, and there is nothing to migrate from a bad parse.
      return { pending: [], failed: [] }
    }
  }

  private save(state: Stored): void {
    this.storage.write(JSON.stringify(state))
    // Tell the status strip. Polling storage on a timer would work and would
    // also make the count lag behind the capture that caused it.
    for (const listener of this.listeners) listener()
  }

  /** Called after every change. Returns its own unsubscriber. */
  subscribe(listener: () => void): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  /** Pending entries, oldest first. */
  pending(): QueuedMutation[] {
    return this.load().pending
  }

  /** Entries the server refused permanently. Shown, never retried. */
  failed(): { entry: QueuedMutation; reason: string }[] {
    return this.load().failed
  }

  /** How many captures are waiting. This is the number the strip shows. */
  size(): number {
    return this.load().pending.length
  }

  // ------------------------------------------------------------- writing

  /**
   * Whether this can be queued at all.
   *
   * A referral or a transition names an id the server assigned, so the thing
   * it names must already exist. Queueing one against an encounter that is
   * itself still queued would send a reference to an id that was never issued.
   */
  canEnqueue(item: NewMutation): boolean {
    if (item.kind === "encounter" || item.kind === "siteAudit") return true
    const queuedKinds = new Set(this.pending().map((e) => e.kind))
    return !queuedKinds.has("encounter")
  }

  enqueue(item: NewMutation): QueuedMutation {
    const entry = {
      ...item,
      id: this.newId(),
      // Minted HERE, once. See the module docstring.
      idempotencyKey: this.newId(),
      enqueuedAt: this.clock(),
      attempts: 0,
    } as QueuedMutation

    const state = this.load()
    this.save({ ...state, pending: [...state.pending, entry] })
    return entry
  }

  /** Forget a permanently-refused entry the operator has acknowledged. */
  discardFailed(id: string): void {
    const state = this.load()
    this.save({
      ...state,
      failed: state.failed.filter((f) => f.entry.id !== id),
    })
  }

  clear(): void {
    this.save({ pending: [], failed: [] })
  }

  // ------------------------------------------------------------ draining

  /**
   * Replay pending entries in order until one cannot be sent.
   *
   * Re-entrancy is refused rather than queued: `online` can fire while a drain
   * started by the interval is still running, and two drains would deliver the
   * same entry twice. The server would dedup it on the key, so this is a
   * politeness, not a correctness fix — but it keeps `attempts` honest.
   */
  async drain(send: Sender): Promise<DrainReport> {
    const report: DrainReport = {
      applied: [] as Applied[],
      dropped: [],
      remaining: this.size(),
      offline: false,
    }
    if (this.draining) return report
    this.draining = true

    try {
      // Re-read each time: the entry is removed from storage as soon as it is
      // applied, so an interrupted drain never replays what already landed.
      for (;;) {
        const [entry] = this.load().pending
        if (!entry) break

        try {
          const response = await send(entry)
          this.remove(entry.id)
          report.applied.push({ entry, response })
          continue
        } catch (error) {
          const disposition = classify(error)
          const reason = error instanceof Error ? error.message : String(error)

          if (disposition === "drop") {
            this.remove(entry.id)
            this.pushFailed(entry, reason)
            report.dropped.push({ entry, reason })
            // A poison entry must never block the queue, so carry on.
            continue
          }

          // Transient. Count the attempt, leave it at the FRONT, and stop:
          // sending entry 2 before entry 1 would write a history that did not
          // happen.
          this.bumpAttempt(entry.id, reason)
          report.offline = disposition === "retry-offline"
          break
        }
      }
    } finally {
      this.draining = false
    }

    report.remaining = this.size()
    return report
  }

  private remove(id: string): void {
    const state = this.load()
    this.save({ ...state, pending: state.pending.filter((e) => e.id !== id) })
  }

  private pushFailed(entry: QueuedMutation, reason: string): void {
    const state = this.load()
    this.save({ ...state, failed: [...state.failed, { entry, reason }] })
  }

  private bumpAttempt(id: string, reason: string): void {
    const state = this.load()
    this.save({
      ...state,
      pending: state.pending.map((e) =>
        e.id === id ? { ...e, attempts: e.attempts + 1, lastError: reason } : e,
      ),
    })
  }
}
