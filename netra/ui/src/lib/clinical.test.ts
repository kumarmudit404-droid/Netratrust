/**
 * Guards the abstention rule. If this regresses, the UI either hides a
 * genuinely ambiguous case or cries abstain on a harmless one.
 */

import { describe, expect, it } from "vitest"
import { REFER_GRADES, isReferable, singleGrade, spansClinicalActions } from "./clinical"
import type { Grade } from "./api/types"

describe("referable grades mirror config/thresholds.yaml dr.refer_grades", () => {
  it("is [2,3,4] — moderate NPDR or worse", () => {
    expect([...REFER_GRADES]).toEqual([2, 3, 4])
  })

  it("classifies each grade", () => {
    expect([0, 1, 2, 3, 4].map((g) => isReferable(g as Grade))).toEqual([
      false, false, true, true, true,
    ])
  })
})

describe("spansClinicalActions — size is never the trigger", () => {
  it("{0,1} does not abstain: both are do-not-refer", () => {
    expect(spansClinicalActions([0, 1])).toBe(false)
  })

  it("{0,3} abstains: it spans refer and do-not-refer", () => {
    expect(spansClinicalActions([0, 3])).toBe(true)
  })

  it("{2,3,4} does not abstain despite being the largest set: all refer", () => {
    expect(spansClinicalActions([2, 3, 4])).toBe(false)
  })

  it("{1,2} abstains — the boundary case that matters clinically", () => {
    expect(spansClinicalActions([1, 2])).toBe(true)
  })

  it("a singleton never abstains, and an empty set never does", () => {
    expect(spansClinicalActions([3])).toBe(false)
    expect(spansClinicalActions([])).toBe(false)
  })
})

describe("singleGrade", () => {
  it("returns the grade only for a singleton set", () => {
    expect(singleGrade([2])).toBe(2)
    expect(singleGrade([0, 1])).toBeNull()
    expect(singleGrade([])).toBeNull()
  })
})
