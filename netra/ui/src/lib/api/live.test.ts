/**
 * Live integration: the real typed client against the real Lane A API.
 *
 * SKIPPED unless VITE_NETRA_LIVE=1, so the normal `npm test` never depends on a
 * running server. To run it:
 *
 *   # terminal 1, from the repo root
 *   NETRA_DB=... NETRA_KEYS_DIR=... .venv/Scripts/python -m uvicorn netra.api.main:app --port 8000
 *   # terminal 2, from netra/ui  (site-07 must be seeded)
 *   VITE_NETRA_LIVE=1 VITE_API_BASE=http://127.0.0.1:8000 npx vitest run src/lib/api/live.test.ts
 *
 * What this buys that the mock cannot: it proves the SHAPES Lane B compiled
 * against are the shapes Lane A actually sends, that CORS permits the
 * Idempotency-Key header cross-origin, and that a retry really is deduped. A
 * green mock suite proves only that the mock agrees with itself.
 *
 * Run against a SCRATCH database. These tests append to the ledger (which is
 * append-only by design), and the "intact chain" case needs a chain nobody has
 * run `netra.ledger.tamper` against — pointed at a tampered DB it fails, which
 * is the test working, not the test being flaky.
 */

import { describe, expect, it } from "vitest"
import { api } from "./client"
import { callQualityGate } from "@/lib/qualityGate"
import { SyncQueue } from "@/lib/offline/queue"
import { memoryStorage } from "@/lib/offline/storage"
import { apiSender, submitEncounter } from "@/lib/offline/sync"

// Read through `import.meta.env`, not `process.env`: tsconfig.app.json sets
// `types: ["vite/client"]`, so `process` is not declared and `npm run build`
// fails on it. Vite exposes any VITE_-prefixed variable, so the flag is
// VITE_NETRA_LIVE.
const LIVE = import.meta.env.VITE_NETRA_LIVE === "1"
const SITE = import.meta.env.VITE_NETRA_LIVE_SITE ?? "site-07"

/** A distinct hash per run, so re-running does not collide on dedup. */
function hash(seed: string): string {
  const h = [...seed].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 0xffffffff, 7)
  return h.toString(16).padStart(8, "0").repeat(8).slice(0, 64)
}

const run = Date.now().toString(36)

describe.skipIf(!LIVE)("live Lane A API", () => {
  it("POST /v1/encounters returns an encounter id and a ledger index", async () => {
    const res = await api.createEncounter({
      image_sha256: hash(`${run}-a`),
      gate_verdict: "usable",
      cause: null,
      prediction_set: [3],
      model_version: `lane-b-live@${run}`,
      site_id: SITE,
      device_seq: 1,
    })
    expect(res.encounter_id).toMatch(/^enc-/)
    expect(typeof res.ledger_idx).toBe("number")
    expect(res.ledger_idx).toBeGreaterThan(0)
    // Exactly the two frozen fields.
    expect(Object.keys(res).sort()).toEqual(["encounter_id", "ledger_idx"])
  })

  it("a retry with the same key is deduped server-side", async () => {
    const body = {
      image_sha256: hash(`${run}-dedup`),
      gate_verdict: "usable" as const,
      cause: null,
      prediction_set: [2] as (0 | 1 | 2 | 3 | 4)[],
      model_version: `lane-b-live@${run}`,
      site_id: SITE,
      device_seq: 2,
    }
    const key = `lane-b-${run}-dedup`
    const first = await api.createEncounter(body, key)
    const second = await api.createEncounter(body, key)
    // At-least-once delivery with server-side dedup: the same key must not
    // create a second encounter or a second ledger entry.
    expect(second).toEqual(first)
  })

  it("a rejected image carrying a prediction set is refused with a 422", async () => {
    await expect(
      api.createEncounter({
        image_sha256: hash(`${run}-reject`),
        gate_verdict: "reject",
        cause: "focus",
        // The clinical invariant: a failed gate is "no result", never a grade.
        prediction_set: [0],
        model_version: `lane-b-live@${run}`,
        site_id: SITE,
        device_seq: 3,
      }),
    ).rejects.toMatchObject({ status: 422 })
  })

  it("a referral issues for a referable grade and advances through the machine", async () => {
    const enc = await api.createEncounter({
      image_sha256: hash(`${run}-ref`),
      gate_verdict: "usable",
      cause: null,
      prediction_set: [4],
      model_version: `lane-b-live@${run}`,
      site_id: SITE,
      device_seq: 4,
    })
    const created = await api.createReferral(enc.encounter_id)
    expect(created.state).toBe("issued")

    const patched = await api.patchReferral(created.referral_id, {
      to_state: "contact_attempted",
      channel: "phone",
      reason: null,
    })
    expect(patched.state).toBe("contact_attempted")
    expect(typeof patched.ledger_idx).toBe("number")
  })

  it("an abstention cannot be referred", async () => {
    const enc = await api.createEncounter({
      image_sha256: hash(`${run}-abstain`),
      gate_verdict: "usable",
      cause: null,
      // {0,3} spans clinical actions -> abstain -> a clinician decides.
      prediction_set: [0, 3],
      model_version: `lane-b-live@${run}`,
      site_id: SITE,
      device_seq: 5,
    })
    await expect(api.createReferral(enc.encounter_id)).rejects.toMatchObject({
      status: 422,
    })
  })

  it("GET /v1/ledger/verify reports an intact chain", async () => {
    const res = await api.verifyLedger()
    expect(Object.keys(res).sort()).toEqual(["first_bad_index", "ok"])
    expect(res.ok).toBe(true)
    expect(res.first_bad_index).toBeNull()
  })

  it("GET /v1/ledger/checkpoint returns a signed head of the frozen shape", async () => {
    const res = await api.ledgerCheckpoint()
    expect(Object.keys(res).sort()).toEqual([
      "head_hash",
      "idx",
      "signature",
      "signer_kid",
      "ts",
    ])
    expect(res.head_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(res.signature).toMatch(/^[0-9a-f]{128}$/)
  })

  it("GET /v1/metrics/sites sends counts and Wilson bounds, not bare rates", async () => {
    const res = await api.siteMetrics()
    expect(Array.isArray(res.rows)).toBe(true)
    const row = res.rows.find((r) => r.site_id === SITE)!
    expect(row).toBeDefined()
    for (const field of [row.gradability, row.abstention]) {
      expect(Object.keys(field).sort()).toEqual(["ci", "k", "n"])
      expect(field.ci![0]).toBeLessThanOrEqual(field.ci![1])
    }
    expect(Object.keys(res.pooled)).toEqual(["gradability"])
  })

  it("GET /v1/sites/{id}/status sends gradability as counts", async () => {
    const res = await api.siteStatus(SITE)
    expect(Object.keys(res).sort()).toEqual([
      "drift_flag",
      "gradability",
      "last_audit",
      "model_version",
      "site_id",
    ])
    expect(Object.keys(res.gradability).sort()).toEqual(["ci", "k", "n"])
    // Non-nullable string; "unpinned" until an audit passes.
    expect(typeof res.model_version).toBe("string")
  })

  // --------------------------------------------- the whole path, in one test

  it("the full capture path: gate -> encounter -> ledger -> referral -> advance", async () => {
    // T-18. Everything else in this file tests one endpoint. This walks the
    // path the operator walks, through the same seam the real model will plug
    // into, so the integration checkpoint is a test and not a transcript.
    const before = await api.ledgerCheckpoint()

    // 1. Capture. The gate hashes on-device; the bytes never leave.
    const gate = await callQualityGate(
      new File([`live-${run}`], "fundus.png", { type: "image/png" }),
      { simScenarioKey: "usable-referable" },
    )
    expect(gate.qualityVerdict).toBe("usable")
    expect(gate.grade).toBe(3)

    // 2. Record it. The ledger entry is appended BEFORE this returns.
    const enc = await api.createEncounter({
      image_sha256: gate.imageSha256,
      gate_verdict: gate.qualityVerdict!,
      cause: gate.cause,
      prediction_set: gate.predictionSet,
      model_version: gate.modelVersion,
      site_id: SITE,
      device_seq: 9100,
    })
    expect(enc.ledger_idx).toBe(before.idx + 1)

    // 3. The chain still verifies with the new entry in it.
    expect((await api.verifyLedger()).ok).toBe(true)

    // 4. A referable grade can be referred, and the referral advances.
    const ref = await api.createReferral(enc.encounter_id)
    expect(ref.state).toBe("issued")
    const attempted = await api.patchReferral(ref.referral_id, {
      to_state: "contact_attempted",
      channel: "phone",
      reason: null,
    })
    expect(attempted.state).toBe("contact_attempted")

    // 5. An illegal jump is refused: issued -> examined skips three states.
    await expect(
      api.patchReferral(ref.referral_id, {
        to_state: "examined",
        channel: null,
        reason: null,
      }),
    ).rejects.toMatchObject({ status: 409 })

    // 6. The head moved, and every transition above is in it.
    const after = await api.ledgerCheckpoint()
    expect(after.idx).toBeGreaterThan(before.idx)
    expect(after.head_hash).not.toEqual(before.head_hash)
    expect((await api.verifyLedger()).ok).toBe(true)
  })

  // ------------------------------------- T-19: the device queue, for real

  it("a capture queued offline replays onto the real ledger", async () => {
    // The stubs in queue.test.ts prove the queue's logic. This proves the
    // thing that actually matters: the key it minted is a key THIS server
    // accepts, and the replay lands one entry.
    const queue = new SyncQueue(memoryStorage())
    const before = await api.ledgerCheckpoint()

    const offline = () => Promise.reject(new TypeError("Failed to fetch"))
    const first = await submitEncounter(
      queue,
      {
        image_sha256: hash(`${run}-queued`),
        gate_verdict: "usable",
        cause: null,
        prediction_set: [0],
        model_version: `lane-b-live@${run}`,
        site_id: SITE,
        device_seq: 9200,
      },
      offline,
    )
    expect(first.queued).toBe(true)
    expect(queue.size()).toBe(1)

    // Signal comes back. Replay through the REAL client.
    const report = await queue.drain(apiSender)
    expect(report.applied).toHaveLength(1)
    expect(queue.size()).toBe(0)

    const after = await api.ledgerCheckpoint()
    expect(after.idx).toBe(before.idx + 1)
    expect((await api.verifyLedger()).ok).toBe(true)
  })

  it("delivering one queued entry twice is deduped by the server", async () => {
    // At-least-once delivery, never exactly-once (SPEC.md section 5). The
    // guard is the key, and this is the test that it is really the server
    // enforcing it rather than the queue being careful.
    const queue = new SyncQueue(memoryStorage())
    const entry = queue.enqueue({
      kind: "encounter",
      payload: {
        image_sha256: hash(`${run}-replay`),
        gate_verdict: "usable",
        cause: null,
        prediction_set: [0],
        model_version: `lane-b-live@${run}`,
        site_id: SITE,
        device_seq: 9201,
      },
    })

    const firstDelivery = await apiSender(entry)
    const beforeSecond = await api.ledgerCheckpoint()
    const secondDelivery = await apiSender(entry)

    // Same response, and no second encounter or ledger entry.
    expect(secondDelivery).toEqual(firstDelivery)
    expect((await api.ledgerCheckpoint()).idx).toBe(beforeSecond.idx)
  })

  it("GET /v1/queue/depth sends the attempt shape Lane A settled on", async () => {
    const res = await api.queueDepth()
    expect(Object.keys(res).sort()).toEqual(["attempts", "queued", "synced"])
    expect(res.synced).toBeGreaterThan(0)
    // `attempts` is QueueAttempt[] now that Lane A has settled the element
    // type, so this reads the fields rather than casting to a bag of unknowns.
    const attempt = res.attempts[0]
    expect(Object.keys(attempt).sort()).toEqual([
      "created_at",
      "endpoint",
      "key",
      "status",
    ])
    expect(attempt.endpoint).toMatch(/^(GET|POST|PATCH) \/v1\//)
    expect(["in_flight", "done"]).toContain(attempt.status)
  })
})
