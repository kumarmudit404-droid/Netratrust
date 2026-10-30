/**
 * Anime.js v4.5.0, vendored.
 *
 * `anime.umd.js` next to this file is the UMD bundle lifted byte-for-byte out
 * of `netra/ui/landing-source.html`, where it was inlined. It is NOT an npm
 * dependency: `SPEC.md` freezes the dependency set, and the landing page's
 * timeline is pinned to this exact build.
 *
 * A UMD wrapper picks its export style at runtime, and this one picks a
 * DIFFERENT branch in each of the two pipelines this repo runs it through:
 *
 *   - under Vite's transform (`npm test`, and dev SSR) `exports` exists, so it
 *     takes the CommonJS branch and the module namespace holds everything;
 *   - in a plain browser context it finds neither `exports` nor `define` and
 *     falls through to assigning `globalThis.anime`.
 *
 * So both are checked, in that order. Picking one and assuming it is how the
 * eye silently fails to animate while `npm run build` stays green;
 * `anime.test.ts` exists because of exactly that.
 *
 * The surface below is only what `eye.ts` calls, and is deliberately loose:
 * hand-writing full types for a vendored bundle would be a second source of
 * truth that no test checks.
 */

import * as bundle from "./anime.umd.js"

export type AnimeTarget = Element | Element[] | NodeListOf<Element> | string

/** Anything Anime.js hands back that has to be reverted on unmount. */
export interface Revertible {
  revert: () => void
  pause: () => void
  complete: () => void
}

export interface AnimeTimeline extends Revertible {
  add: (
    targets: AnimeTarget | unknown,
    params: Record<string, unknown>,
    position?: number,
  ) => AnimeTimeline
  currentTime: number
}

export interface Anime {
  animate: (t: AnimeTarget, params: Record<string, unknown>) => Revertible
  createTimeline: (params?: Record<string, unknown>) => AnimeTimeline
  onScroll: (params: Record<string, unknown>) => unknown
  stagger: (value: number) => unknown
  utils: {
    set: (t: AnimeTarget | unknown, params: Record<string, unknown>) => void
    random: (min: number, max: number) => number
  }
  svg: { createDrawable: (t: AnimeTarget) => unknown }
}

/** A shape is the real thing only if the calls `eye.ts` makes are on it. */
function isAnime(value: unknown): value is Anime {
  const c = value as Partial<Anime> | null
  return (
    !!c &&
    typeof c.animate === "function" &&
    typeof c.createTimeline === "function" &&
    typeof c.onScroll === "function" &&
    !!c.utils &&
    typeof c.utils.set === "function" &&
    !!c.svg &&
    typeof c.svg.createDrawable === "function"
  )
}

const ns = bundle as unknown as { default?: unknown }
const candidates = [ns.default, bundle, (globalThis as { anime?: unknown }).anime]
const resolved = candidates.find(isAnime)

if (!resolved) {
  throw new Error(
    "the vendored anime.umd.js exposed neither module exports nor " +
      "globalThis.anime - the bundle is truncated or its UMD wrapper was edited.",
  )
}

// Re-bound so the exported type is `Anime`, not `Anime | undefined`: the throw
// above narrows the local but not what the module declares.
const anime: Anime = resolved

export default anime
