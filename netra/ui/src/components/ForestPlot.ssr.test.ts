/**
 * Server-renders <ForestPlot/> and asserts on the real output.
 *
 * No DOM library is in Lane B's stack, and this adds none — `react-dom/server`
 * is already a dependency. What it buys over the import-time smoke test is
 * real: a bad Recharts child, an invalid prop combination or a crash inside
 * render surfaces here, and so does a percentage leaking into the markup.
 *
 * It cannot assert layout or contrast. Those still need a human browser pass.
 */

import { describe, expect, it } from "vitest"
import type { ForestPoint } from "@/lib/forest"

// Recharts is a large module graph; the first transform dominates the run.
const TIMEOUT = { timeout: 30000 }

async function render(
  points: ForestPoint[],
  pooled: number | null,
): Promise<string> {
  const { renderToStaticMarkup } = await import("react-dom/server")
  const { createElement } = await import("react")
  const { ForestPlot } = await import("./ForestPlot")
  return renderToStaticMarkup(
    createElement(ForestPlot, {
      points,
      pooled,
      pooledLabel: "pooled 305/412 (0.70-0.78)",
      xLabel: "proportion admitted (0–1), with 95% Wilson interval",
    }),
  )
}

async function pointsFor(k: number, n: number, ci?: [number, number]) {
  const { toForestPoints } = await import("@/lib/forest")
  return toForestPoints(
    [
      {
        site_id: "site-02",
        gradability: { k, n, ci },
        abstention: { k: 0, n },
        drift_flag: false,
      },
    ],
    "gradability",
  )
}

describe("ForestPlot renders", () => {
  it("produces markup for a well-powered site", TIMEOUT, async () => {
    const html = await render(await pointsFor(140, 203, [0.623, 0.7493]), 0.74)
    expect(html.length).toBeGreaterThan(0)
  })

  it("says so plainly when there is nothing to plot", TIMEOUT, async () => {
    const html = await render([], null)
    expect(html).toContain("No site has enough data to plot yet.")
  })

  // NOTE: under SSR, Recharts' ResponsiveContainer measures zero width and
  // renders an EMPTY container, so the plot body - markers, axes, labels - is
  // not in this markup. Asserting "no % in the chart markup" would therefore
  // pass while testing nothing (and in fact matched ResponsiveContainer's own
  // `width:100%` inline style). The figures-to-text assertion belongs on the
  // tooltip below, which does render.
  it("renders an empty container under SSR, by design", TIMEOUT, async () => {
    const html = await render(await pointsFor(140, 203, [0.623, 0.7493]), 0.74)
    expect(html).toContain("recharts-responsive-container")
  })

  it("does not throw with or without a pooled line", TIMEOUT, async () => {
    await expect(render(await pointsFor(140, 203), 0.74)).resolves.toBeTypeOf("string")
    await expect(render(await pointsFor(140, 203), null)).resolves.toBeTypeOf("string")
  })
})

describe("ForestTooltip turns a point into text", () => {
  async function tip(k: number, n: number, ci?: [number, number], drift = false) {
    const { renderToStaticMarkup } = await import("react-dom/server")
    const { createElement } = await import("react")
    const { ForestTooltip } = await import("./ForestPlot")
    const { toForestPoints } = await import("@/lib/forest")
    const [point] = toForestPoints(
      [
        {
          site_id: "site-02",
          gradability: { k, n, ci },
          abstention: { k: 0, n },
          drift_flag: drift,
        },
      ],
      "gradability",
    )
    return renderToStaticMarkup(
      createElement(ForestTooltip, { active: true, payload: [{ payload: point }] }),
    )
  }

  it("shows counts and the interval at n >= 30, with no percentage", TIMEOUT, async () => {
    const html = await tip(140, 203, [0.623, 0.7493])
    expect(html).toContain("140/203 (0.62-0.75)")
    expect(html).not.toContain("%")
  })

  it("shows counts only below n = 30, and says why", TIMEOUT, async () => {
    const html = await tip(22, 27, [0.633, 0.9182])
    expect(html).toContain("22 of 27")
    expect(html).toContain("n below 30")
    expect(html).not.toContain("%")
  })

  it("names a drift flag in words, not by colour alone", TIMEOUT, async () => {
    expect(await tip(140, 203, [0.623, 0.7493], true)).toContain("drift flagged")
  })

  it("renders nothing when inactive", TIMEOUT, async () => {
    const { renderToStaticMarkup } = await import("react-dom/server")
    const { createElement } = await import("react")
    const { ForestTooltip } = await import("./ForestPlot")
    expect(renderToStaticMarkup(createElement(ForestTooltip, {}))).toBe("")
  })
})
