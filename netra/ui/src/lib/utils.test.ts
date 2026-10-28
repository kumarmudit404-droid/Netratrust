import { describe, expect, it } from "vitest"
import { cn } from "./utils"

/**
 * These pin the tailwind-merge configuration, not cosmetics.
 *
 * The default merge treats our custom type-scale steps as text COLOURS, which
 * silently drops whichever of the size/colour pair comes first. The failure is
 * invisible in a unit test of the component and catastrophic on screen: the
 * primary button rendered --text on --text, contrast 1:1.
 */
describe("cn — size and colour never collide", () => {
  it("keeps the button's text colour alongside its type-scale size", () => {
    const out = cn("bg-text text-bg", "h-14 px-6 text-subhead")
    expect(out).toContain("text-bg")
    expect(out).toContain("text-subhead")
  })

  it("keeps a status colour passed after a caption size", () => {
    const out = cn("text-caption font-semibold", "text-abstain")
    expect(out).toContain("text-caption")
    expect(out).toContain("text-abstain")
  })

  it("keeps a caption size passed after a status colour", () => {
    const out = cn("text-abstain", "text-caption")
    expect(out).toContain("text-abstain")
    expect(out).toContain("text-caption")
  })

  it("still collapses two sizes, last one winning", () => {
    expect(cn("text-body", "text-display")).toBe("text-display")
  })

  it("still collapses two colours, last one winning", () => {
    expect(cn("text-usable", "text-reject")).toBe("text-reject")
  })
})
