/**
 * The tamper demo's two states, pinned in both directions.
 *
 * SPEC.md section 7: "A verify button that has only ever returned ok:true does
 * not demonstrate tamper-evidence." So the ok:false path is tested at least as
 * hard as the ok:true one, including the index actually reaching the headline.
 */

import { describe, expect, it } from "vitest"
import {
  describeHistoryEntry,
  isAlarming,
  verifyDisplay,
  verifyExplainer,
  verifyHeadline,
  verifyStatus,
} from "./ledgerState"

const base = { isFetching: false, isError: false, hasRun: true }

describe("verifyDisplay", () => {
  it("is idle before the operator has run it", () => {
    expect(verifyDisplay({ ...base, hasRun: false })).toEqual({ kind: "idle" })
  })

  it("is ok for ok:true", () => {
    expect(
      verifyDisplay({ ...base, data: { ok: true, first_bad_index: null } }),
    ).toEqual({ kind: "ok" })
  })

  it("carries first_bad_index through for ok:false", () => {
    expect(
      verifyDisplay({ ...base, data: { ok: false, first_bad_index: 2 } }),
    ).toEqual({ kind: "tampered", firstBadIndex: 2 })
  })

  it("treats index 0 as a real index, not as absent", () => {
    // A falsy-check bug here would silently downgrade a real detection.
    expect(
      verifyDisplay({ ...base, data: { ok: false, first_bad_index: 0 } }),
    ).toEqual({ kind: "tampered", firstBadIndex: 0 })
  })

  it("reports ok:false with no index as its own state, never as fine", () => {
    const d = verifyDisplay({ ...base, data: { ok: false, first_bad_index: null } })
    expect(d).toEqual({ kind: "failed-without-index" })
    expect(isAlarming(d)).toBe(true)
  })

  it("shows checking while a refetch is in flight, even over a stale ok", () => {
    // During the tamper demo a stale ok:true must not linger looking current.
    expect(
      verifyDisplay({
        ...base,
        isFetching: true,
        data: { ok: true, first_bad_index: null },
      }),
    ).toEqual({ kind: "checking" })
  })

  it("distinguishes a failed request from a tampered chain", () => {
    const d = verifyDisplay({
      ...base,
      isError: true,
      error: new Error("Failed to fetch"),
    })
    expect(d.kind).toBe("error")
    // A dead API is NOT evidence of tampering, and must not be dressed as it.
    expect(isAlarming(d)).toBe(false)
    expect(verifyStatus(d)).toBe("error")
    expect(verifyStatus({ kind: "tampered", firstBadIndex: 2 })).toBe("reject")
  })
})

describe("the two demo states read unmistakably differently", () => {
  const ok = verifyDisplay({ ...base, data: { ok: true, first_bad_index: null } })
  const bad = verifyDisplay({ ...base, data: { ok: false, first_bad_index: 2 } })

  it("the headlines share no wording", () => {
    expect(verifyHeadline(ok)).toBe("Chain intact")
    expect(verifyHeadline(bad)).toBe("Tampering detected at entry 2")
    expect(verifyHeadline(ok)).not.toEqual(verifyHeadline(bad))
  })

  it("the bad headline names the index, because the demo turns on it", () => {
    expect(verifyHeadline(bad)).toContain("2")
    expect(verifyHeadline({ kind: "tampered", firstBadIndex: 7 })).toContain("7")
  })

  it("only one of them is alarming, and they take different statuses", () => {
    expect(isAlarming(ok)).toBe(false)
    expect(isAlarming(bad)).toBe(true)
    expect(verifyStatus(ok)).toBe("usable")
    expect(verifyStatus(bad)).toBe("reject")
  })

  it("the ok explainer does not overclaim", () => {
    const text = verifyExplainer(ok)
    // It says what was checked, not "the ledger is secure".
    expect(text).toContain("recomputed")
    expect(text.toLowerCase()).not.toContain("secure")
    expect(text.toLowerCase()).not.toContain("guarantee")
  })

  it("the tampered explainer localises the damage and names the index", () => {
    const text = verifyExplainer(bad)
    expect(text).toContain("Entry 2")
    expect(text).toContain("before it verified")
  })

  it("an error explainer refuses to read as a clean result", () => {
    expect(verifyExplainer({ kind: "error", message: "x" })).toContain(
      "not the same as a clean result",
    )
  })

  it("every state has a headline and an explainer", () => {
    const all = [
      { kind: "idle" } as const,
      { kind: "checking" } as const,
      { kind: "ok" } as const,
      { kind: "tampered", firstBadIndex: 1 } as const,
      { kind: "failed-without-index" } as const,
      { kind: "error", message: "x" } as const,
    ]
    for (const d of all) {
      expect(verifyHeadline(d).length).toBeGreaterThan(0)
      expect(verifyExplainer(d).length).toBeGreaterThan(0)
    }
  })
})

describe("history makes the transition visible", () => {
  it("describes an ok and a failed check differently", () => {
    expect(describeHistoryEntry({ at: 1, ok: true, firstBadIndex: null })).toBe(
      "ok — chain intact",
    )
    expect(describeHistoryEntry({ at: 2, ok: false, firstBadIndex: 2 })).toBe(
      "FAILED — first bad entry 2",
    )
  })

  it("says unknown rather than null when no index came back", () => {
    expect(describeHistoryEntry({ at: 3, ok: false, firstBadIndex: null })).toBe(
      "FAILED — first bad entry unknown",
    )
  })
})
