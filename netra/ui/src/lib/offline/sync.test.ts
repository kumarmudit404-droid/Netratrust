/**
 * The write-ahead rule: enqueue first, send second, always.
 *
 * `queue.test.ts` covers the queue's own behaviour. This covers the seam the
 * Capture screen actually calls, and the one thing a screen can get wrong —
 * treating "queued" as a failure, or treating a permanent refusal as a queue.
 */

import { describe, expect, it } from "vitest"
import { ApiError } from "../api/errors"
import { SyncQueue } from "./queue"
import { memoryStorage } from "./storage"
import { submitEncounter, submitOrQueue } from "./sync"
import type { EncounterRequest } from "../api/types"

function makeQueue() {
  let n = 0
  return new SyncQueue(memoryStorage(), () => "2026-10-29T00:00:00Z", () => `id-${++n}`)
}

const BODY: EncounterRequest = {
  image_sha256: "a".repeat(64),
  gate_verdict: "usable",
  cause: null,
  prediction_set: [3],
  model_version: "simulated-gate@test",
  site_id: "site-07",
  device_seq: 412,
}

const OFFLINE = () => Promise.reject(new TypeError("Failed to fetch"))
const OK = () => Promise.resolve({ encounter_id: "enc-1", ledger_idx: 125 })

describe("submitEncounter", () => {
  it("returns the server's response when it lands", async () => {
    const queue = makeQueue()
    const { response, queued } = await submitEncounter(queue, BODY, OK)

    expect(queued).toBe(false)
    expect(response).toEqual({ encounter_id: "enc-1", ledger_idx: 125 })
    expect(queue.size()).toBe(0)
  })

  it("reports queued, not failed, when there is no signal", async () => {
    const queue = makeQueue()
    const { response, queued } = await submitEncounter(queue, BODY, OFFLINE)

    // The capture is NOT lost and this is NOT an error. Offline is the normal
    // condition at a screening camp.
    expect(queued).toBe(true)
    expect(response).toBeNull()
    expect(queue.size()).toBe(1)
  })

  it("writes to the queue before sending, so nothing is lost mid-flight", async () => {
    const queue = makeQueue()
    let depthDuringSend = -1
    await submitEncounter(queue, BODY, () => {
      // The entry is already persisted at the moment the request goes out.
      depthDuringSend = queue.size()
      return OK()
    })
    expect(depthDuringSend).toBe(1)
  })

  it("keeps the same key across the first attempt and the replay", async () => {
    const queue = makeQueue()
    const keys: string[] = []
    const capture = (entry: { idempotencyKey: string }) => {
      keys.push(entry.idempotencyKey)
      return Promise.reject(new TypeError("Failed to fetch"))
    }

    await submitEncounter(queue, BODY, capture)
    await queue.drain(capture)

    expect(keys).toHaveLength(2)
    expect(keys[0]).toBe(keys[1])
  })

  it("throws on a permanent refusal rather than pretending it is queued", async () => {
    const queue = makeQueue()
    await expect(
      submitEncounter(queue, BODY, () =>
        Promise.reject(new ApiError(422, "a reject carries no prediction set")),
      ),
    ).rejects.toThrow(/prediction set/)

    // Not pending - it is never going to be accepted - but kept as failed so
    // the operator sees that this capture was refused.
    expect(queue.size()).toBe(0)
    expect(queue.failed()).toHaveLength(1)
  })
})

describe("submitOrQueue preserves order across actions", () => {
  it("a capture taken now cannot overtake one still waiting", async () => {
    const queue = makeQueue()
    // First capture: no signal.
    await submitOrQueue(queue, { kind: "encounter", payload: BODY }, OFFLINE)

    const sent: number[] = []
    const record = (entry: { kind: string; payload: unknown }) => {
      if (entry.kind === "encounter") {
        sent.push((entry.payload as EncounterRequest).device_seq)
      }
      return OK()
    }

    // Second capture, signal is back. The OLDER one must go first.
    await submitOrQueue(
      queue,
      { kind: "encounter", payload: { ...BODY, device_seq: 413 } },
      record,
    )

    expect(sent).toEqual([412, 413])
  })
})
