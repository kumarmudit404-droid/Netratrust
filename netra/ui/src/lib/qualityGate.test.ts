/**
 * Tests for THE SEAM.
 *
 * Two jobs here. The first is ordinary: the simulated gate returns a usable
 * result and hashes on-device. The second matters more — `assertGateResult`
 * has to hold for the REAL model too, so these cases are written against the
 * invariants, not against the simulation. When `callQualityGate`'s body is
 * replaced with `infer.py`, every test below should still be the right test.
 */

import { describe, expect, it } from "vitest"
import {
  GateResultError,
  assertGateResult,
  callQualityGate,
  isNoResult,
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
    const r = await callQualityGate(fakeImage())
    expect(r.imageSha256).toBe(FIXTURE_SHA256)
    expect(r.qualityVerdict).toBe("usable")
  })

  it("hashes the bytes it was given, not a placeholder", async () => {
    const a = await callQualityGate(fakeImage("one"))
    const b = await callQualityGate(fakeImage("two"))
    expect(a.imageSha256).not.toEqual(b.imageSha256)
  })

  it("reports that no model is loaded", async () => {
    const r = await callQualityGate(fakeImage())
    expect(r.modelVersion).toContain("simulated")
    expect(r.note).toContain("no model is loaded")
  })

  it("falls back to the first scenario for an unknown key", async () => {
    const r = await callQualityGate(fakeImage(), { simScenarioKey: "nope" })
    expect(r.note).toContain(SCENARIOS[0].key)
  })

  it.each(SCENARIOS.map((s) => s.key))(
    "returns a result that satisfies every invariant for scenario %s",
    async (key) => {
      // No assertion needed beyond this: callQualityGate routes its own output
      // through assertGateResult, so an invariant breach throws.
      const r = await callQualityGate(fakeImage(), { simScenarioKey: key })
      expect(r.qualityVerdict).not.toBeNull()
    },
  )

  it("gives a rejected image no grade and no prediction set", async () => {
    const r = await callQualityGate(fakeImage(), {
      simScenarioKey: "reject-focus",
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
    })
    const wide = await callQualityGate(fakeImage(), {
      simScenarioKey: "usable-wide-same-action",
    })
    expect(spanning.abstain).toBe(true)
    expect(wide.abstain).toBe(false)
  })

  it("names a grade only for a singleton set", async () => {
    const single = await callQualityGate(fakeImage(), {
      simScenarioKey: "usable-referable",
    })
    const wide = await callQualityGate(fakeImage(), {
      simScenarioKey: "usable-wide-same-action",
    })
    expect(single.grade).toBe(3)
    expect(wide.grade).toBeNull()
  })

  it("keeps the score a scaled integer, never a float", async () => {
    const r = await callQualityGate(fakeImage())
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
