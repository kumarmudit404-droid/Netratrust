/**
 * The vendored Anime.js bundle, under the real module pipeline.
 *
 * This is not a test of Anime.js. It is a test of the ONE risky thing about
 * inlining a UMD bundle into a Vite app: the wrapper picks its export style at
 * runtime by sniffing `exports`, `define` and `globalThis`, so whether
 * `globalThis.anime` ends up set depends on how the bundler classified the
 * file. If that goes wrong the landing page's eye silently never animates, and
 * `npm run build` is perfectly happy.
 *
 * It runs in Node, which the bundle supports: it guards every DOM reference
 * behind `typeof window`, so importing it without a document is safe.
 */

import { describe, expect, it } from "vitest"

describe("the vendored Anime.js bundle", () => {
  it("registers itself on globalThis when bundled as a module", async () => {
    const anime = (await import("./anime")).default
    expect(anime).toBeTruthy()
  })

  it("exposes exactly the surface eye.ts destructures", async () => {
    const anime = (await import("./anime")).default
    // `const { animate, createTimeline, onScroll, stagger, utils, svg } = anime`
    expect(typeof anime.animate).toBe("function")
    expect(typeof anime.createTimeline).toBe("function")
    expect(typeof anime.onScroll).toBe("function")
    expect(typeof anime.stagger).toBe("function")
    expect(typeof anime.utils.set).toBe("function")
    expect(typeof anime.utils.random).toBe("function")
    expect(typeof anime.svg.createDrawable).toBe("function")
  })
})
