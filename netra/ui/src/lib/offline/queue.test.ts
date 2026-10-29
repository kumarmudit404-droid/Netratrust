/**
 * T-19 device-side queue.
 *
 * The three properties that matter, from SPEC.md section 5:
 *  - a capture taken offline is not lost;
 *  - a replay is safe, because it carries the key the action was given;
 *  - order is preserved, because a referral's history must not be written
 *    out of sequence.
 *
 * The sender is a stub throughout. These are tests about the QUEUE; the live
 * client against the live API is `src/lib/api/live.test.ts`.
 */

import { beforeEach, describe, expect, it, vi } from "vitest"
import { ApiError } from "../api/errors"
import {
  SyncQueue,
  classify,
  type NewMutation,
  type QueuedMutation,
} from "./queue"
import { memoryStorage, type QueueStorage } from "./storage"

// A counter rather than crypto.randomUUID, so ids and keys are readable and
// assertions can name them.
function counter(prefix: string) {
  let n = 0
  return () => `${prefix}-${++n}`
}

function makeQueue(storage: QueueStorage = memoryStorage()) {
  return new SyncQueue(storage, () => "2026-10-29T00:00:00Z", counter("id"))
}

function capture(seq: number): NewMutation {
  return {
    kind: "encounter",
    payload: {
      image_sha256: String(seq).padStart(64, "0"),
      gate_verdict: "usable",
      cause: null,
      prediction_set: [0],
      model_version: "simulated-gate@test",
      site_id: "site-07",
      device_seq: seq,
    },
  }
}

/** Offline looks like a `fetch` TypeError: no response ever arrived. */
const OFFLINE = () => Promise.reject(new TypeError("Failed to fetch"))

describe("classify decides what is worth sending again", () => {
  it("retries a 409, because the key is still in flight and IS being applied", () => {
    expect(classify(new ApiError(409, "in flight"))).toBe("retry")
  })

  it("drops a 422: no number of retries changes a payload", () => {
    expect(classify(new ApiError(422, "key reused with a different payload"))).toBe(
      "drop",
    )
  })

  it("drops a 404: an unknown site will not start existing", () => {
    expect(classify(new ApiError(404, "unknown site"))).toBe("drop")
  })

  it("retries a 500, 408 and 429: the server is unwell, not the request", () => {
    expect(classify(new ApiError(500, "boom"))).toBe("retry")
    expect(classify(new ApiError(503, "unavailable"))).toBe("retry")
    expect(classify(new ApiError(408, "timeout"))).toBe("retry")
    expect(classify(new ApiError(429, "slow down"))).toBe("retry")
  })

  it("treats a non-ApiError as offline", () => {
    expect(classify(new TypeError("Failed to fetch"))).toBe("retry-offline")
  })
})

describe("capture while offline", () => {
  let queue: SyncQueue

  beforeEach(() => {
    queue = makeQueue()
  })

  it("keeps the capture instead of losing it", async () => {
    queue.enqueue(capture(1))
    const report = await queue.drain(OFFLINE)

    expect(report.applied).toHaveLength(0)
    expect(report.offline).toBe(true)
    expect(queue.size()).toBe(1)
  })

  it("mints an idempotency key at enqueue, before anything is sent", () => {
    const entry = queue.enqueue(capture(1))
    expect(entry.idempotencyKey).toBeTruthy()
    expect(entry.idempotencyKey).not.toEqual(entry.id)
  })

  it("counts the attempt and records why it failed", async () => {
    queue.enqueue(capture(1))
    await queue.drain(OFFLINE)
    await queue.drain(OFFLINE)

    const [entry] = queue.pending()
    expect(entry.attempts).toBe(2)
    expect(entry.lastError).toContain("Failed to fetch")
  })

  it("holds several captures and reports the depth", async () => {
    queue.enqueue(capture(1))
    queue.enqueue(capture(2))
    queue.enqueue(capture(3))
    await queue.drain(OFFLINE)

    expect(queue.size()).toBe(3)
  })

  it("survives a reload: the queue is in storage, not in the object", async () => {
    const storage = memoryStorage()
    const before = makeQueue(storage)
    before.enqueue(capture(1))
    before.enqueue(capture(2))
    await before.drain(OFFLINE)

    // A new page, a new SyncQueue, the same device storage.
    const after = new SyncQueue(storage)
    expect(after.size()).toBe(2)
    const [first] = after.pending()
    // Narrow the union: `payload` differs per kind.
    expect(first.kind).toBe("encounter")
    if (first.kind === "encounter") {
      expect(first.payload.device_seq).toBe(1)
    }
  })
})

describe("replay on reconnect", () => {
  it("sends everything in order once the network is back", async () => {
    const queue = makeQueue()
    queue.enqueue(capture(1))
    queue.enqueue(capture(2))
    queue.enqueue(capture(3))
    await queue.drain(OFFLINE)

    const sent: number[] = []
    const report = await queue.drain((entry) => {
      if (entry.kind === "encounter") sent.push(entry.payload.device_seq)
      return Promise.resolve({ encounter_id: "enc-x", ledger_idx: 1 })
    })

    expect(sent).toEqual([1, 2, 3])
    expect(report.applied).toHaveLength(3)
    expect(queue.size()).toBe(0)
  })

  it("replays with the SAME key it was given, not a fresh one", async () => {
    const queue = makeQueue()
    const entry = queue.enqueue(capture(1))

    const keys: string[] = []
    const record = (e: QueuedMutation) => {
      keys.push(e.idempotencyKey)
      return Promise.reject(new TypeError("Failed to fetch"))
    }
    await queue.drain(record)
    await queue.drain(record)
    await queue.drain(record)

    // Three deliveries of ONE action must carry one key, or the server
    // cannot dedup them and the record reads as three separate events.
    expect(keys).toEqual([entry.idempotencyKey, entry.idempotencyKey, entry.idempotencyKey])
  })

  it("hands back the server's response, which only exists once it lands", async () => {
    const queue = makeQueue()
    queue.enqueue(capture(1))

    const report = await queue.drain(() =>
      Promise.resolve({ encounter_id: "enc-abc", ledger_idx: 125 }),
    )

    expect(report.applied[0].response).toEqual({
      encounter_id: "enc-abc",
      ledger_idx: 125,
    })
  })

  it("is idempotent: a redelivered entry is accepted and removed once", async () => {
    const queue = makeQueue()
    queue.enqueue(capture(1))

    // First delivery times out on the client but the server APPLIED it. The
    // second delivery is deduped on the key and returns the stored response -
    // which is a success, so the entry leaves the queue.
    let attempt = 0
    const flaky = () => {
      attempt += 1
      if (attempt === 1) return Promise.reject(new TypeError("Failed to fetch"))
      return Promise.resolve({ encounter_id: "enc-abc", ledger_idx: 125 })
    }

    await queue.drain(flaky)
    expect(queue.size()).toBe(1)

    const report = await queue.drain(flaky)
    expect(report.applied).toHaveLength(1)
    expect(queue.size()).toBe(0)
  })

  it("keeps a 409 queued rather than discarding a record being applied", async () => {
    const queue = makeQueue()
    queue.enqueue(capture(1))

    await queue.drain(() => Promise.reject(new ApiError(409, "still in flight")))

    expect(queue.size()).toBe(1)
    expect(queue.failed()).toHaveLength(0)
  })

  it("does not report offline when the server answered 409", async () => {
    const queue = makeQueue()
    queue.enqueue(capture(1))
    const report = await queue.drain(() =>
      Promise.reject(new ApiError(409, "still in flight")),
    )
    // The server is reachable; one entry is mid-flight. Showing "offline"
    // here would be a lie on the status strip.
    expect(report.offline).toBe(false)
  })
})

describe("order is preserved", () => {
  it("stops at the first unsendable entry instead of skipping past it", async () => {
    const queue = makeQueue()
    queue.enqueue(capture(1))
    queue.enqueue(capture(2))
    queue.enqueue(capture(3))

    const sent: number[] = []
    const failSecond = (entry: QueuedMutation) => {
      if (entry.kind !== "encounter") return Promise.resolve({})
      if (entry.payload.device_seq === 2) {
        return Promise.reject(new ApiError(503, "unavailable"))
      }
      sent.push(entry.payload.device_seq)
      return Promise.resolve({})
    }

    await queue.drain(failSecond)

    // 3 must NOT have been sent: it would have landed before 2.
    expect(sent).toEqual([1])
    expect(queue.pending().map((e) => e.id)).toEqual(["id-3", "id-5"])
  })

  it("resumes from where it stopped, still in order", async () => {
    const queue = makeQueue()
    queue.enqueue(capture(1))
    queue.enqueue(capture(2))
    await queue.drain(OFFLINE)

    const sent: number[] = []
    await queue.drain((entry) => {
      if (entry.kind === "encounter") sent.push(entry.payload.device_seq)
      return Promise.resolve({})
    })

    expect(sent).toEqual([1, 2])
  })

  it("a poison entry is dropped and does not block the rest", async () => {
    const queue = makeQueue()
    queue.enqueue(capture(1))
    queue.enqueue(capture(2))

    const sent: number[] = []
    const report = await queue.drain((entry) => {
      if (entry.kind !== "encounter") return Promise.resolve({})
      if (entry.payload.device_seq === 1) {
        return Promise.reject(new ApiError(422, "key reused"))
      }
      sent.push(entry.payload.device_seq)
      return Promise.resolve({})
    })

    expect(report.dropped).toHaveLength(1)
    expect(sent).toEqual([2])
    expect(queue.size()).toBe(0)
    // Kept for the operator to see. A silently dropped capture is the worst
    // outcome available: the record is gone and nobody knows.
    expect(queue.failed()).toHaveLength(1)
    expect(queue.failed()[0].reason).toContain("key reused")
  })

  it("refuses to queue a referral while an encounter is still queued", () => {
    const queue = makeQueue()
    queue.enqueue(capture(1))

    // The encounter has no server-assigned id yet, so there is nothing for a
    // referral to point at.
    expect(queue.canEnqueue({ kind: "referral", payload: { encounterId: "enc-?" } })).toBe(
      false,
    )
    expect(queue.canEnqueue(capture(2))).toBe(true)
  })

  it("allows a referral once the encounters have drained", async () => {
    const queue = makeQueue()
    queue.enqueue(capture(1))
    await queue.drain(() => Promise.resolve({}))

    expect(
      queue.canEnqueue({ kind: "referral", payload: { encounterId: "enc-1" } }),
    ).toBe(true)
  })
})

describe("the queue does not make things worse when it breaks", () => {
  it("treats corrupt storage as an empty queue rather than throwing", () => {
    const queue = new SyncQueue(memoryStorage("{not json"))
    expect(queue.pending()).toEqual([])
    expect(queue.size()).toBe(0)
  })

  it("ignores a stored shape it does not recognise", () => {
    const queue = new SyncQueue(memoryStorage('{"pending":"nope"}'))
    expect(queue.pending()).toEqual([])
  })

  it("refuses a second concurrent drain, so one entry is not sent twice", async () => {
    const queue = makeQueue()
    queue.enqueue(capture(1))

    let inFlight = 0
    let maxInFlight = 0
    const slow = () => {
      inFlight += 1
      maxInFlight = Math.max(maxInFlight, inFlight)
      return new Promise((resolve) => {
        setTimeout(() => {
          inFlight -= 1
          resolve({})
        }, 10)
      })
    }

    // `online` firing during an interval-driven drain is exactly this.
    await Promise.all([queue.drain(slow), queue.drain(slow)])
    expect(maxInFlight).toBe(1)
  })

  it("keeps working when storage silently refuses to write", async () => {
    // Site data blocked: reads come back empty, writes vanish. The app must
    // still accept a capture and still try to send it.
    const blocked: QueueStorage = { read: () => null, write: () => {} }
    const queue = new SyncQueue(blocked, () => "t", counter("id"))

    const entry = queue.enqueue(capture(1))
    expect(entry.idempotencyKey).toBeTruthy()
    const report = await queue.drain(() => Promise.resolve({}))
    // Nothing persisted, so nothing to drain - but no throw, and the caller
    // still got an entry with a key it can send directly.
    expect(report.applied).toHaveLength(0)
  })

  it("clear empties both lists", async () => {
    const queue = makeQueue()
    queue.enqueue(capture(1))
    await queue.drain(() => Promise.reject(new ApiError(422, "no")))
    expect(queue.failed()).toHaveLength(1)

    queue.clear()
    expect(queue.size()).toBe(0)
    expect(queue.failed()).toHaveLength(0)
  })

  it("discardFailed forgets one acknowledged refusal", async () => {
    const queue = makeQueue()
    queue.enqueue(capture(1))
    await queue.drain(() => Promise.reject(new ApiError(422, "no")))
    const [failure] = queue.failed()

    queue.discardFailed(failure.entry.id)
    expect(queue.failed()).toHaveLength(0)
  })
})

describe("the sender is given the entry's own key", () => {
  it("passes the key through to the client call", async () => {
    const queue = makeQueue()
    const entry = queue.enqueue({
      kind: "referralPatch",
      payload: {
        referralId: "ref-1",
        body: { to_state: "contact_attempted", channel: "phone", reason: null },
      },
    })

    const send = vi.fn().mockResolvedValue({})
    await queue.drain(send)

    expect(send).toHaveBeenCalledOnce()
    expect(send.mock.calls[0][0].idempotencyKey).toBe(entry.idempotencyKey)
    expect(send.mock.calls[0][0].payload.referralId).toBe("ref-1")
  })
})
