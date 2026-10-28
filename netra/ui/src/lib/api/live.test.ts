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

  it("GET /v1/queue/depth sends the attempt shape Lane A settled on", async () => {
    const res = await api.queueDepth()
    expect(Object.keys(res).sort()).toEqual(["attempts", "queued", "synced"])
    expect(res.synced).toBeGreaterThan(0)
    const attempt = res.attempts[0] as Record<string, unknown>
    expect(Object.keys(attempt).sort()).toEqual([
      "created_at",
      "endpoint",
      "key",
      "status",
    ])
  })
})
