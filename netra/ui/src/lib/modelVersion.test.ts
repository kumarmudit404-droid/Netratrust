/**
 * The "unpinned" sentinel must read as a plain fact, not as a failure.
 *
 * Lane A returns `model_version: "unpinned"` for a site that has never passed
 * an audit. A site awaiting its first audit is normal in a screening
 * programme; rendering it as an error would train operators to ignore errors.
 */

import { describe, expect, it } from "vitest"
import {
  UNPINNED_MODEL_VERSION,
  formatModelVersion,
  isUnpinned,
} from "./modelVersion"

describe("formatModelVersion", () => {
  it("the sentinel matches the one Lane A sends", () => {
    expect(UNPINNED_MODEL_VERSION).toBe("unpinned")
  })

  it("renders the sentinel as plain language", () => {
    expect(formatModelVersion("unpinned")).toBe("no audited model yet")
  })

  it("never renders the sentinel as an error or a warning", () => {
    const out = formatModelVersion("unpinned")
    expect(out.toLowerCase()).not.toContain("error")
    expect(out.toLowerCase()).not.toContain("fail")
    expect(out).not.toContain("—")
    expect(out).not.toContain("!")
  })

  it("passes a real pinned version through untouched", () => {
    expect(formatModelVersion("convnext_tiny.in12k_ft_in1k@abc123")).toBe(
      "convnext_tiny.in12k_ft_in1k@abc123",
    )
  })

  it("treats an empty string as unpinned rather than printing nothing", () => {
    expect(formatModelVersion("")).toBe("no audited model yet")
  })
})

describe("isUnpinned picks the treatment", () => {
  it("is true for the sentinel and for empty", () => {
    expect(isUnpinned("unpinned")).toBe(true)
    expect(isUnpinned("")).toBe(true)
  })

  it("is false for a pinned version", () => {
    expect(isUnpinned("convnext_tiny@abc")).toBe(false)
  })
})
