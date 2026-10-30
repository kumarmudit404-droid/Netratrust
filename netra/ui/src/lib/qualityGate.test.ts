/**
 * Tests for THE SEAM, now that it calls the real model.
 *
 * Three jobs. The invariant tests are unchanged and were always written
 * against the invariants rather than against the simulation, which is why
 * they needed nothing when `infer.py` was plugged in - that was the point of
 * writing them that way.
 *
 * What is new is the sidecar path, with `fetch` stubbed: the snake_case ->
 * camelCase mapping, the hash cross-check, and the two cases that must NOT
 * become a simulated verdict - a sidecar that answers but cannot grade, and a
 * model that breaks an invariant.
 *
 * The simulation is now only the fallback, so every test that means to
 * exercise it passes `forceSimulated`. Without that the result would depend on
 * whether a sidecar happened to be running on the machine running the suite.
 */

import { afterEach, describe, expect, it, vi } from "vitest"
import {
  GateResultError,
  assertGateResult,
  callQualityGate,
  isNoResult,
  isSimulatedGate,
  type GateResult,
} from "./qualityGate"
import { SCENARIOS } from "./gateSim"

/** The hash the capture screen must produce for these bytes.
 *  `printf 'netratrust' | sha256sum` — a real value, so a test that compares
 *  against it is comparing against something true. */
const FIXTURE = "netratrust"
const FIXTURE_SHA256 =
  "edcd0de240f0dc9e30a54aa489ea4ab7e1df8dcfbe760fd85d04397da1fb4144"

function fakeImage(body = FIXTURE): File {
  return new File([body], "fundus.png", { type: "image/png" })
}

describe("callQualityGate is the only gate entrypoint", () => {
  it("hashes the image on-device and returns a verdict", async () => {
    const r = await callQualityGate(fakeImage(), { forceSimulated: true })
    expect(r.imageSha256).toBe(FIXTURE_SHA256)
    expect(r.qualityVerdict).toBe("usable")
  })

  it("hashes the bytes it was given, not a placeholder", async () => {
    const a = await callQualityGate(fakeImage("one"), { forceSimulated: true })
    const b = await callQualityGate(fakeImage("two"), { forceSimulated: true })
    expect(a.imageSha256).not.toEqual(b.imageSha256)
  })

  it("says out loud that a simulated result is not a measurement", async () => {
    const r = await callQualityGate(fakeImage(), { forceSimulated: true })
    expect(r.modelVersion).toContain("simulated")
    expect(isSimulatedGate(r)).toBe(true)
    expect(r.note).toContain("SIMULATED")
    expect(r.note).toContain("not a measurement")
  })

  it("falls back to the first scenario for an unknown key", async () => {
    const r = await callQualityGate(fakeImage(), {
      simScenarioKey: "nope",
      forceSimulated: true,
    })
    expect(r.note).toContain(SCENARIOS[0].key)
  })

  it.each(SCENARIOS.map((s) => s.key))(
    "returns a result that satisfies every invariant for scenario %s",
    async (key) => {
      // No assertion needed beyond this: callQualityGate routes its own output
      // through assertGateResult, so an invariant breach throws.
      const r = await callQualityGate(fakeImage(), {
        simScenarioKey: key,
        forceSimulated: true,
      })
      expect(r.qualityVerdict).not.toBeNull()
    },
  )

  it("gives a rejected image no grade and no prediction set", async () => {
    const r = await callQualityGate(fakeImage(), {
      simScenarioKey: "reject-focus",
      forceSimulated: true,
    })
    expect(r.qualityVerdict).toBe("reject")
    expect(r.predictionSet).toBeNull()
    expect(r.grade).toBeNull()
    expect(r.cause).toBe("focus")
    expect(isNoResult(r)).toBe(true)
  })

  it("abstains only when the set spans a clinical action boundary", async () => {
    // {1,2} crosses refer / do-not-refer. {2,3,4} is wide but one action.
    const spanning = await callQualityGate(fakeImage(), {
      simScenarioKey: "usable-abstain",
      forceSimulated: true,
    })
    const wide = await callQualityGate(fakeImage(), {
      simScenarioKey: "usable-wide-same-action",
      forceSimulated: true,
    })
    expect(spanning.abstain).toBe(true)
    expect(wide.abstain).toBe(false)
  })

  it("names a grade only for a singleton set", async () => {
    const single = await callQualityGate(fakeImage(), {
      simScenarioKey: "usable-referable",
      forceSimulated: true,
    })
    const wide = await callQualityGate(fakeImage(), {
      simScenarioKey: "usable-wide-same-action",
      forceSimulated: true,
    })
    expect(single.grade).toBe(3)
    expect(wide.grade).toBeNull()
  })

  it("keeps the score a scaled integer, never a float", async () => {
    const r = await callQualityGate(fakeImage(), { forceSimulated: true })
    expect(Number.isInteger(r.qualityScoreMilli)).toBe(true)
  })
})

describe("assertGateResult holds the real model to the same invariants", () => {
  const ok: GateResult = {
    imageSha256: FIXTURE_SHA256,
    qualityVerdict: "usable",
    cause: null,
    predictionSet: [3],
    grade: 3,
    abstain: false,
    modelVersion: "convnext_tiny_aptos@v1",
    qualityScoreMilli: 874,
    note: "",
  }

  it("passes a well-formed result through unchanged", () => {
    expect(assertGateResult(ok)).toBe(ok)
  })

  it("refuses a reject that carries a prediction set", () => {
    expect(() =>
      assertGateResult({
        ...ok,
        qualityVerdict: "reject",
        predictionSet: [0],
        grade: null,
      }),
    ).toThrow(GateResultError)
  })

  it("refuses a reject that carries a grade", () => {
    expect(() =>
      assertGateResult({
        ...ok,
        qualityVerdict: "reject",
        predictionSet: null,
        grade: 0,
      }),
    ).toThrow(/no grade/)
  })

  it("refuses a result from a gate that never ran", () => {
    expect(() =>
      assertGateResult({ ...ok, qualityVerdict: null }),
    ).toThrow(/no result to report/)
  })

  it("refuses an empty prediction set", () => {
    expect(() =>
      assertGateResult({ ...ok, predictionSet: [], grade: null }),
    ).toThrow(/empty prediction set/)
  })

  it("refuses a float score", () => {
    expect(() => assertGateResult({ ...ok, qualityScoreMilli: 0.874 })).toThrow(
      /scaled integer/,
    )
  })

  it("allows a null score — a gate that could not score is not a zero", () => {
    expect(() =>
      assertGateResult({ ...ok, qualityScoreMilli: null }),
    ).not.toThrow()
  })

  it("treats a null verdict as no result", () => {
    expect(
      isNoResult({ ...ok, qualityVerdict: null, predictionSet: null, grade: null }),
    ).toBe(true)
  })
})

describe("the sidecar path: the real model, with fetch stubbed", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  /** A sidecar that answers `body` with `status`. */
  function sidecar(body: unknown, status = 200) {
    const fetchMock = vi.fn(async () => ({
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    }))
    vi.stubGlobal("fetch", fetchMock)
    return fetchMock
  }

  /** What `netra/sidecar` actually returned for a good fundus image on
   *  2026-10-30, with the real artifacts loaded. Copied from the response,
   *  so the mapping below is tested against a true shape. */
  const REAL_USABLE = {
    image_sha256: FIXTURE_SHA256,
    quality_verdict: "usable",
    cause: null,
    prediction_set: [0],
    grade: 0,
    abstain: false,
    model_version:
      "quickqual:densenet121.tv_in1k@512:tv_in1k+pickle|convnext_tiny.in12k_ft_in1k@512:convnext_tiny_aptos",
    quality_score_milli: 997,
    note: "set [0] is entirely do-not-refer",
  }

  /** And for a deliberately blurred one. This is the clinical case. */
  const REAL_REJECT = {
    image_sha256: FIXTURE_SHA256,
    quality_verdict: "reject",
    cause: "focus",
    prediction_set: null,
    grade: null,
    abstain: false,
    model_version: "quickqual:densenet121.tv_in1k@512:tv_in1k+pickle",
    quality_score_milli: 29,
    note: "image rejected by the quality gate; no grade was computed",
  }

  it("maps the sidecar's snake_case result field for field", async () => {
    sidecar(REAL_USABLE)
    const r = await callQualityGate(fakeImage())
    expect(r.imageSha256).toBe(FIXTURE_SHA256)
    expect(r.qualityVerdict).toBe("usable")
    expect(r.predictionSet).toEqual([0])
    expect(r.grade).toBe(0)
    expect(r.abstain).toBe(false)
    expect(r.qualityScoreMilli).toBe(997)
    expect(r.modelVersion).toContain("convnext_tiny")
    expect(r.note).toBe("set [0] is entirely do-not-refer")
    // The whole point: this is not labelled simulated.
    expect(isSimulatedGate(r)).toBe(false)
  })

  it("sends the bytes to the sidecar, not to the /v1 API", async () => {
    const fetchMock = sidecar(REAL_USABLE)
    await callQualityGate(fakeImage())
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      { method: string; body: unknown },
    ]
    expect(url).toContain("/gate")
    expect(url).not.toContain("/v1")
    // Loopback. A fundus image must not leave the device.
    expect(url).toMatch(/^http:\/\/(127\.0\.0\.1|localhost)/)
    expect(init.method).toBe("POST")
  })

  it("carries a real reject through as no result", async () => {
    sidecar(REAL_REJECT)
    const r = await callQualityGate(fakeImage())
    expect(r.qualityVerdict).toBe("reject")
    expect(r.predictionSet).toBeNull()
    expect(r.grade).toBeNull()
    expect(r.cause).toBe("focus")
    expect(isNoResult(r)).toBe(true)
    expect(isSimulatedGate(r)).toBe(false)
  })

  it("refuses a real model that returns a graded reject", async () => {
    // assertGateResult guards the model, not just the simulation. This is the
    // breach that would otherwise reach POST /v1/encounters and come back a
    // 422 the operator cannot read.
    sidecar({ ...REAL_REJECT, prediction_set: [0], grade: 0 })
    await expect(callQualityGate(fakeImage())).rejects.toThrow(GateResultError)
  })

  it("refuses a result whose hash is not the hash of these bytes", async () => {
    sidecar({ ...REAL_USABLE, image_sha256: "0".repeat(64) })
    await expect(callQualityGate(fakeImage())).rejects.toThrow(
      /hashed different bytes/,
    )
  })

  it("reports a sidecar that answers but cannot grade, and does NOT simulate", async () => {
    sidecar({ error: "cannot identify image file" }, 422)
    const r = await callQualityGate(fakeImage())
    expect(r.qualityVerdict).toBeNull()
    expect(r.predictionSet).toBeNull()
    expect(isNoResult(r)).toBe(true)
    // A gate that ran and failed is a real answer. Substituting a scenario
    // here would turn a failure into a verdict.
    expect(isSimulatedGate(r)).toBe(false)
    expect(r.note).toContain("cannot identify image file")
  })

  it("falls back to the labelled simulation when the sidecar is not running", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed")
      }),
    )
    const r = await callQualityGate(fakeImage())
    // A demo must never hard-fail...
    expect(r.qualityVerdict).not.toBeNull()
    // ...and must never quietly claim a measurement either.
    expect(isSimulatedGate(r)).toBe(true)
    expect(r.note).toContain("unreachable")
    expect(r.note).toContain("not a measurement")
  })

  it("still hashes on-device when it falls back", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed")
      }),
    )
    const r = await callQualityGate(fakeImage())
    expect(r.imageSha256).toBe(FIXTURE_SHA256)
  })
})
