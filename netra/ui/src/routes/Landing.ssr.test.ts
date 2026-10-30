/**
 * Server-renders the landing route and asserts on the real output.
 *
 * `useEffect` does not run under `renderToStaticMarkup`, so the eye never
 * mounts here. That is the point: what this checks is the half of the page
 * that must work whether or not Anime.js, the canvas, or JavaScript at all
 * arrive - the copy, the anatomy panel, the HUD, and the eight buttons that
 * are the only way into the app from the front door.
 *
 * It cannot assert the animation, the teardown or the layout. The teardown is
 * covered statically by `eye.port.test.ts`; the animation and layout still
 * need a human browser pass, as `demo/RUNBOOK.md` says.
 */

import { describe, expect, it } from "vitest"

const TIMEOUT = { timeout: 30000 }

async function render(): Promise<string> {
  const { renderToStaticMarkup } = await import("react-dom/server")
  const { createElement } = await import("react")
  const { MemoryRouter } = await import("react-router-dom")
  const Landing = (await import("./Landing")).default
  return renderToStaticMarkup(
    createElement(MemoryRouter, { initialEntries: ["/"] }, createElement(Landing)),
  )
}

describe("the landing route renders the ported page", () => {
  it("keeps the elements the scroll timeline and the HUD read", TIMEOUT, async () => {
    const html = await render()
    // Every id/class `eye.ts` looks up. A rename in the markup would leave the
    // page rendering and the eye throwing on mount.
    for (const hook of [
      'id="rig"',
      'id="sway"',
      'id="glow"',
      'id="floor"',
      'id="track"',
      'id="labels"',
      'id="lab-list"',
      'id="lab-hint"',
      'id="hud"',
      'id="hud-state"',
      'id="hud-bar"',
      'id="cue"',
      'id="disintegration"',
      'class="stage"',
      'class="hud"',
      'class="cue"',
    ]) {
      expect(html, `${hook} is gone from the landing markup`).toContain(hook)
    }
  })

  it("renders the decoration the theme is built from", TIMEOUT, async () => {
    const html = await render()
    expect(html).toContain('class="workshop"')
    expect(html).toContain('class="medical-cross"')
    expect(html).toContain('class="gear gear-a"')
    expect(html).toContain('class="gear gear-b"')
    expect(html).toContain('class="defs"')
    // Four <svg> blocks ship in the static markup: two gears, the medical
    // cross and the gradient/clip-path defs. The eye's own SVG is generated.
    expect(html.match(/<svg/g)).toHaveLength(4)
  })

  it("is wrapped in .landing, so its stylesheet cannot reach the other routes", TIMEOUT, async () => {
    const html = await render()
    expect(html.startsWith('<div class="landing"')).toBe(true)
  })
})

describe("the landing page's buttons are the way into the app", () => {
  it("carries a data-route AND an href on every button", TIMEOUT, async () => {
    const html = await render()
    const buttons = [...html.matchAll(/<a\b[^>]*\bdata-route="[^"]*"[^>]*>/g)].map(
      (m) => m[0],
    )
    expect(buttons.length).toBe(8)
    for (const a of buttons) {
      const route = /data-route="([^"]*)"/.exec(a)?.[1]
      const href = /href="([^"]*)"/.exec(a)?.[1]
      // The href is the fallback: if the click handler never attaches, or JS
      // is gone entirely, the button is still a working link. It must point
      // at the same place the router would.
      expect(href, `no href on ${a}`).toBe(route)
    }
  })

  it("points only at routes that exist", TIMEOUT, async () => {
    const html = await render()
    const { LANDING_ROUTES } = await import("./Landing")
    const routes = new Set(
      [...html.matchAll(/data-route="([^"]*)"/g)].map((m) => m[1]),
    )
    expect(routes.size).toBeGreaterThan(0)
    for (const route of routes) {
      expect(LANDING_ROUTES as readonly string[], `${route} is not a route`).toContain(
        route,
      )
    }
  })

  it("declares the same five routes the router mounts", TIMEOUT, async () => {
    const { LANDING_ROUTES } = await import("./Landing")
    // SPEC.md's five screens. "/" is the landing itself and is not in the list.
    expect([...LANDING_ROUTES].sort()).toEqual(
      ["/capture", "/grade", "/ledger", "/referrals", "/sites"].sort(),
    )
  })
})
