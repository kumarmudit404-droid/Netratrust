/**
 * Import-time smoke test.
 *
 * No DOM renderer is in Lane B's stack, so this cannot assert what a screen
 * looks like. What it does catch is the failure that `npm run build` can miss
 * and a human reviewer reads straight past: a module that throws on import —
 * a bad named export, a circular import, a typo'd path.
 */

import { describe, expect, it } from "vitest"

describe("every route module imports and exports a component", () => {
  const routes = {
    Capture: () => import("./Capture"),
    Grade: () => import("./Grade"),
    Referrals: () => import("./Referrals"),
    Sites: () => import("./Sites"),
    Ledger: () => import("./Ledger"),
  }

  for (const [name, load] of Object.entries(routes)) {
    it(`${name} has a default export that is a function`, async () => {
      const mod = await load()
      expect(typeof mod.default).toBe("function")
    })
  }
})

describe("shared components and libs import cleanly", () => {
  it("StatusBadge exposes all seven states", async () => {
    const { STATUS } = await import("@/components/StatusBadge")
    expect(Object.keys(STATUS).sort()).toEqual(
      ["abstain", "borderline", "error", "grade", "pending-sync", "reject", "usable"].sort(),
    )
  })

  it("VerdictPanel and PredictionSet import", async () => {
    expect(typeof (await import("@/components/VerdictPanel")).VerdictPanel).toBe("function")
    expect(typeof (await import("@/components/PredictionSet")).PredictionSet).toBe("function")
  })

  it("the API client exposes exactly the nine frozen endpoints", async () => {
    const { api } = await import("@/lib/api/client")
    expect(Object.keys(api).sort()).toEqual(
      [
        "createEncounter",
        "createReferral",
        "patchReferral",
        "verifyLedger",
        "ledgerCheckpoint",
        "siteStatus",
        "siteAudit",
        "siteMetrics",
        "queueDepth",
      ].sort(),
    )
  })
})
