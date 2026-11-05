/**
 * Lane B's logic gate for the n<30 rule (design.md section 7, BUILD_RULES.md
 * clinical invariants). This is the rule that, if it regresses, puts a bare
 * percentage on a sample too small to support it.
 */

import { describe, expect, it } from "vitest"
import { MIN_N_FOR_RATE, formatRate, isSmallN } from "./formatRate"

describe("formatRate — the n<30 boundary", () => {
  it("threshold matches config/thresholds.yaml sites.min_n_for_rate", () => {
    expect(MIN_N_FOR_RATE).toBe(30)
  })

  it("n=29 shows counts only, with no percentage", () => {
    // Wilson bounds for k=23,n=29 are supplied but must be ignored below the
    // threshold: the rule is "no bare percentage", and counts are what is safe.
    const out = formatRate(23, 29, [0.6161, 0.9015])
    expect(out).toBe("23 of 29")
    expect(out).not.toContain("%")
    expect(isSmallN(29)).toBe(true)
  })

  it("n=30 shows the rate with its Wilson interval", () => {
    // Full-precision bounds, as the server sends them. A pre-rounded 0.905
    // would render "0.91" — the rounding happens once, here, not upstream.
    const out = formatRate(24, 30, [0.6269395261897256, 0.9049502189759876])
    expect(out).toBe("24/30 (0.63-0.90)")
    expect(isSmallN(30)).toBe(false)
  })

  it("never emits a percentage at any n when the interval is missing", () => {
    // Degraded path: no CI from the server. Counts only — never a bare rate.
    expect(formatRate(24, 30)).toBe("24/30")
    expect(formatRate(24, 30)).not.toContain("%")
    expect(formatRate(23, 29)).toBe("23 of 29")
  })

  it("n=0 reports no data rather than dividing by zero", () => {
    expect(formatRate(0, 0)).toBe("no data")
  })
})

describe("Wilson values cross-checked against netra/eval/metrics.py", () => {
  // Reference values produced by the same algebra as
  // netra/eval/metrics.py::wilson_interval (z = 1.96):
  //   k=24 n=30 -> [0.6269395261897256, 0.9049502189759876]
  //   k=22 n=27 -> [0.6330094349480825, 0.9181941342571468]
  // The front end never computes a statistic; it only renders what it is
  // given. These assertions pin the RENDERING of those server values.
  it("renders the k=24 n=30 interval to two decimals", () => {
    expect(formatRate(24, 30, [0.6269395261897256, 0.9049502189759876])).toBe(
      "24/30 (0.63-0.90)",
    )
  })

  it("renders the k=22 n=27 case as counts, since 27 < 30", () => {
    expect(formatRate(22, 27, [0.6330094349480825, 0.9181941342571468])).toBe(
      "22 of 27",
    )
  })
})
