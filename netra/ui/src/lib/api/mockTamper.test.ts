/**
 * The mock's `?tamper=N` affordance. It exists so the Ledger view's ok:false
 * state can be designed and reviewed without a backend; against the real API
 * that state comes from the tamper CLI. Parsing it wrongly would make the
 * review screen lie, so the parse is pinned.
 */

import { describe, expect, it } from "vitest"
import { tamperedSeq } from "./mock"

describe("tamperedSeq", () => {
  it("is null with no param, so the default stays ok:true", () => {
    expect(tamperedSeq("")).toBeNull()
    expect(tamperedSeq("?other=1")).toBeNull()
  })

  it("reads an index", () => {
    expect(tamperedSeq("?tamper=2")).toBe(2)
    expect(tamperedSeq("?tamper=17")).toBe(17)
  })

  it("treats 0 as a real index", () => {
    // Entry 0 is a legitimate first_bad_index; a falsy check would drop it.
    expect(tamperedSeq("?tamper=0")).toBe(0)
  })

  it("ignores rubbish rather than rendering NaN as an index", () => {
    expect(tamperedSeq("?tamper=abc")).toBeNull()
    expect(tamperedSeq("?tamper=")).toBeNull()
    expect(tamperedSeq("?tamper=-1")).toBeNull()
    expect(tamperedSeq("?tamper=1.5")).toBeNull()
  })
})
