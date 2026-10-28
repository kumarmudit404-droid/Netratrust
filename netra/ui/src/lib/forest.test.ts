/**
 * The forest plot's data shaping — the place a per-site chart goes wrong
 * quietly: a zero-n site plotted at 0.0, an interval that does not bracket its
 * estimate, a pooled line that is secretly a mean of rates, or a bare
 * percentage leaking past the n<30 rule.
 */

import { describe, expect, it } from "vitest"
import {
  driftingSites,
  emptyRows,
  pooledEstimate,
  toForestPoints,
} from "./forest"
import type { SiteMetricsRow } from "./api/types"

/** Shapes mirror GET /v1/metrics/sites. Wilson bounds as the server sends them. */
const ROWS: SiteMetricsRow[] = [
  {
    site_id: "site-02",
    gradability: { k: 140, n: 203, ci: [0.623, 0.7493] },
    abstention: { k: 31, n: 203, ci: [0.1097, 0.2086] },
    drift_flag: false,
  },
  {
    site_id: "site-07",
    gradability: { k: 22, n: 27, ci: [0.633, 0.9182] },
    abstention: { k: 6, n: 27, ci: [0.1061, 0.4076] },
    drift_flag: true,
  },
  {
    site_id: "site-03",
    gradability: { k: 96, n: 118, ci: [0.7338, 0.8735] },
    abstention: { k: 14, n: 118, ci: [0.072, 0.1893] },
    drift_flag: false,
  },
  {
    site_id: "site-99",
    gradability: { k: 0, n: 0, ci: [0, 1] },
    abstention: { k: 0, n: 0, ci: [0, 1] },
    drift_flag: false,
  },
]

describe("toForestPoints", () => {
  it("drops a site with n=0 rather than plotting it at zero", () => {
    const points = toForestPoints(ROWS, "gradability")
    expect(points.map((p) => p.site_id)).not.toContain("site-99")
    // It is still accounted for, in the table.
    expect(emptyRows(ROWS, "gradability").map((r) => r.site_id)).toEqual(["site-99"])
  })

  it("orders well-powered sites first and small-n sites last", () => {
    const points = toForestPoints(ROWS, "gradability")
    expect(points.map((p) => p.site_id)).toEqual(["site-02", "site-03", "site-07"])
    // site-07 is last because n=27 < 30, not because its rate is highest.
    expect(points[2].smallN).toBe(true)
    expect(points[0].smallN).toBe(false)
  })

  it("the error bar offsets reconstruct the server's interval exactly", () => {
    const [first] = toForestPoints(ROWS, "gradability")
    const [lowOffset, highOffset] = first.xErr
    expect(first.est - lowOffset).toBeCloseTo(0.623, 10)
    expect(first.est + highOffset).toBeCloseTo(0.7493, 10)
  })

  it("never emits a negative offset, even if an interval does not bracket est", () => {
    const broken: SiteMetricsRow[] = [
      {
        site_id: "site-x",
        // Deliberately inconsistent: lower bound above the point estimate.
        gradability: { k: 5, n: 100, ci: [0.4, 0.9] },
        abstention: { k: 0, n: 100, ci: [0, 0.1] },
        drift_flag: false,
      },
    ]
    const [p] = toForestPoints(broken, "gradability")
    expect(p.xErr[0]).toBeGreaterThanOrEqual(0)
    expect(p.xErr[1]).toBeGreaterThanOrEqual(0)
  })

  it("labels every point through formatRate, so no bare percentage appears", () => {
    for (const p of toForestPoints(ROWS, "gradability")) {
      expect(p.label).not.toContain("%")
    }
    const small = toForestPoints(ROWS, "gradability").find((p) => p.smallN)!
    // n=27 -> counts only, no interval, no percentage.
    expect(small.label).toBe("22 of 27")
    const big = toForestPoints(ROWS, "gradability").find((p) => p.site_id === "site-02")!
    expect(big.label).toBe("140/203 (0.62-0.75)")
  })

  it("carries the drift flag onto the point", () => {
    const points = toForestPoints(ROWS, "gradability")
    expect(points.find((p) => p.site_id === "site-07")!.driftFlag).toBe(true)
    expect(points.find((p) => p.site_id === "site-02")!.driftFlag).toBe(false)
  })

  it("shapes the abstention measure with its own denominator", () => {
    const points = toForestPoints(ROWS, "abstention")
    const seven = points.find((p) => p.site_id === "site-07")!
    // Abstention's denominator is ADMITTED images, which the server computes.
    // The front end just renders what it is given.
    expect(seven.k).toBe(6)
    expect(seven.n).toBe(27)
    expect(seven.label).toBe("6 of 27")
  })

  it("falls back to a zero-width bar when the server sends no interval", () => {
    const noCi: SiteMetricsRow[] = [
      {
        site_id: "site-y",
        gradability: { k: 50, n: 100 },
        abstention: { k: 5, n: 100 },
        drift_flag: false,
      },
    ]
    const [p] = toForestPoints(noCi, "gradability")
    expect(p.xErr).toEqual([0, 0])
    // And the label degrades to counts, never to a bare percentage.
    expect(p.label).toBe("50/100")
  })
})

describe("pooledEstimate", () => {
  it("is summed counts, not the mean of the per-site rates", () => {
    // Summed: (140+22+96)/(203+27+118) = 258/348 = 0.7414...
    // Mean of rates: (0.6897 + 0.8148 + 0.8136)/3 = 0.7727... — different, and
    // what SPEC.md means by "never a mean".
    const pooled = pooledEstimate({ k: 258, n: 348, ci: [0.6928, 0.7852] })!
    expect(pooled).toBeCloseTo(0.7414, 4)
    expect(pooled).not.toBeCloseTo(0.7727, 3)
  })

  it("is null when there is nothing to pool, so no line is drawn", () => {
    expect(pooledEstimate({ k: 0, n: 0 })).toBeNull()
    expect(pooledEstimate(undefined)).toBeNull()
  })
})

describe("driftingSites", () => {
  it("names the flagged sites", () => {
    expect(driftingSites(ROWS)).toEqual(["site-07"])
  })

  it("is empty when nothing is flagged", () => {
    expect(driftingSites([ROWS[0]])).toEqual([])
  })
})
