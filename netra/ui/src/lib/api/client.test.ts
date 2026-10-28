/**
 * The typed client's wire behaviour: which headers actually leave the browser.
 *
 * This exists because the bug it guards against is invisible on screen. A
 * mutation sent without an `Idempotency-Key` works perfectly until the
 * delivery is retried, and then it is applied twice — a second
 * `contact_attempted` reads as a second real contact attempt in a clinical
 * record. Nothing in the UI shows that; only this test does.
 *
 * `fetch` is stubbed rather than mocked at the module boundary so the assertion
 * is about the real request the client builds.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { api } from "./client"

interface Call {
  url: string
  method: string
  headers: Record<string, string>
  body: unknown
}

let calls: Call[] = []

/** RFC 4122 v4, which is what crypto.randomUUID() emits. */
const UUID_V4 =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

beforeEach(() => {
  calls = []
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init: RequestInit) => {
      calls.push({
        url,
        method: init.method ?? "GET",
        headers: (init.headers ?? {}) as Record<string, string>,
        body: init.body ? JSON.parse(init.body as string) : undefined,
      })
      return Promise.resolve({
        ok: true,
        status: 200,
        statusText: "OK",
        json: () => Promise.resolve({}),
      } as Response)
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("every mutating call sends an Idempotency-Key", () => {
  it("createEncounter does", async () => {
    await api.createEncounter({
      image_sha256: "a".repeat(64),
      gate_verdict: "usable",
      cause: null,
      prediction_set: [2],
      model_version: "test",
      site_id: "site-07",
      device_seq: 1,
    })
    expect(calls[0].headers["Idempotency-Key"]).toMatch(UUID_V4)
  })

  it("createReferral does", async () => {
    await api.createReferral("enc-1")
    expect(calls[0].method).toBe("POST")
    expect(calls[0].url).toBe("/v1/referrals")
    expect(calls[0].headers["Idempotency-Key"]).toMatch(UUID_V4)
    expect(calls[0].body).toEqual({ encounter_id: "enc-1" })
  })

  it("patchReferral does", async () => {
    await api.patchReferral("ref-1", {
      to_state: "contact_attempted",
      channel: "phone",
      reason: null,
    })
    expect(calls[0].method).toBe("PATCH")
    expect(calls[0].url).toBe("/v1/referrals/ref-1")
    expect(calls[0].headers["Idempotency-Key"]).toMatch(UUID_V4)
  })

  it("siteAudit does", async () => {
    await api.siteAudit("site-07", { pinned_model_version: "x" })
    expect(calls[0].headers["Idempotency-Key"]).toMatch(UUID_V4)
  })
})

describe("the key is per-action, not per-session", () => {
  it("two deliberate transitions get two different keys", async () => {
    const body = {
      to_state: "contact_attempted" as const,
      channel: "phone",
      reason: null,
    }
    await api.patchReferral("ref-1", body)
    await api.patchReferral("ref-1", body)
    // Two attempts ARE two events; it is the redelivery of one that must be
    // collapsed. Reusing a key here would make the server replay the first
    // response and silently drop the second attempt.
    expect(calls[0].headers["Idempotency-Key"]).not.toBe(
      calls[1].headers["Idempotency-Key"],
    )
  })

  it("an explicit key is honoured, so a retry can reuse one", async () => {
    await api.createReferral("enc-1", "fixed-key")
    await api.createReferral("enc-1", "fixed-key")
    expect(calls[0].headers["Idempotency-Key"]).toBe("fixed-key")
    expect(calls[1].headers["Idempotency-Key"]).toBe("fixed-key")
  })
})

describe("reads do not send a key", () => {
  it("GET endpoints carry no Idempotency-Key and no body", async () => {
    await api.verifyLedger()
    await api.ledgerCheckpoint()
    await api.siteMetrics()
    await api.queueDepth()
    await api.siteStatus("site-07")
    expect(calls).toHaveLength(5)
    for (const call of calls) {
      expect(call.method).toBe("GET")
      expect(call.headers["Idempotency-Key"]).toBeUndefined()
      expect(call.body).toBeUndefined()
    }
  })

  it("site ids are encoded into the path", async () => {
    await api.siteStatus("site 07/x")
    expect(calls[0].url).toBe("/v1/sites/site%2007%2Fx/status")
  })
})

describe("errors carry the server's detail", () => {
  it("a 422 surfaces the detail string, not just the status text", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 422,
          statusText: "Unprocessable Entity",
          json: () =>
            Promise.resolve({ detail: "a rejected image is 'no result'" }),
        } as Response),
      ),
    )
    await expect(api.createReferral("enc-1")).rejects.toMatchObject({
      status: 422,
      message: "a rejected image is 'no result'",
    })
  })
})
