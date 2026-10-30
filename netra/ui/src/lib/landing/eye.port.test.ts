/**
 * Guards the port of `netra/ui/landing-source.html` against drift.
 *
 * The brief for this page was "port it as-is": the animations, theme, colours,
 * fonts, SVGs and timeline are not ours to change. Three of the four ported
 * artifacts can be pinned to the source exactly, and are. The fourth, the
 * stylesheet, had its SELECTORS rewritten on purpose (see `landing.css`), so
 * what is pinned there is every declaration - the colours and fonts - rather
 * than the selectors around them.
 *
 * The second half of the file is a static read of `eye.ts`. No DOM library is
 * in Lane B's stack, so the teardown cannot be executed here; what IS checkable
 * is that every listener in the module goes through the tracker that
 * `destroy()` drains, and that nothing re-introduces a document-wide lookup.
 * That is weaker than running it, and it is the failure mode that matters:
 * a listener added directly is invisible in review and leaks for the whole
 * session. The live check is the StrictMode double-mount in dev plus the
 * browser pass in `demo/RUNBOOK.md`.
 */

import { readFileSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

const UI = join(__dirname, "..", "..", "..")
const read = (p: string) => readFileSync(join(UI, p), "utf8")

const source = read("landing-source.html")
/** The regions of the source each artifact was lifted from. */
const sourceStyle = source.split("<style>")[1].split("</style>")[0]
const sourceBody = source.split("<body>")[1].split("<script>")[0]
const sourceAnime = source.split("</script>")[0].split("<script>")[1]

describe("the ported artifacts still match landing-source.html", () => {
  it("landingMarkup.html is the source's <body>, byte for byte", () => {
    expect(read("src/routes/landingMarkup.html").replace(/\r\n/g, "\n")).toBe(
      sourceBody.replace(/\r\n/g, "\n").replace(/^\n+|\n+$/g, "") + "\n",
    )
  })

  it("anime.umd.js is the inlined bundle, byte for byte", () => {
    const vendored = read("src/vendor/anime.umd.js").replace(/\r\n/g, "\n")
    const inlined = sourceAnime.replace(/\r\n/g, "\n")
    // The vendored copy drops only the blank lines the <script> tag sat on.
    expect(vendored.trim()).toBe(inlined.trim())
    expect(vendored).toContain("@version v4.5.0")
  })

  it("every declaration in the source stylesheet survives in landing.css", () => {
    const css = read("src/landing.css")
    // Declarations, not selectors: the selectors were deliberately scoped.
    const declarations = (block: string) =>
      block
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .split(/[{}]/)
        .flatMap((chunk) => chunk.split(";"))
        .map((d) => d.trim().replace(/\s+/g, " "))
        // `:(?!:)` keeps `body::before` out: it is a selector, and the
        // split above cannot tell it from a `property: value` pair.
        .filter((d) => /^[-a-z]+\s*:(?!:)\s*\S/.test(d))

    const wanted = declarations(sourceStyle)
    expect(wanted.length).toBeGreaterThan(200)
    const have = new Set(declarations(css))
    const missing = wanted.filter((d) => !have.has(d))
    expect(missing, "declarations lost or altered in the port").toEqual([])
  })

  it("scopes the page-level selectors the five other routes share", () => {
    const css = read("src/landing.css")
    // `html`/`body` cannot nest, so they key off the mounted class instead.
    expect(css).toContain("html.landing-active {")
    expect(css).toContain("body.landing-active {")
    // Nothing may be left at the top level that would reach /capture.
    const topLevel = css
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .split("\n")
      .filter((l) => /^[^\s@}][^{]*\{/.test(l))
      .map((l) => l.split("{")[0].trim())
    for (const selector of topLevel) {
      for (const part of selector.split(",")) {
        expect(
          part.trim(),
          `"${part.trim()}" is not scoped and will restyle the other routes`,
        ).toMatch(/^(\.landing|html\.landing-active|body\.landing-active)/)
      }
    }
  })
})

describe("the eye's teardown can actually reach everything", () => {
  const eye = read("src/lib/landing/eye.ts")

  it("registers every listener through the tracked helper", () => {
    // The one permitted `addEventListener` is inside `on()` itself.
    const direct = [...eye.matchAll(/^.*\baddEventListener\(.*$/gm)].map((m) =>
      m[0].trim(),
    )
    expect(direct).toEqual(["target.addEventListener(type, handler, opts)"])
    expect(eye).toContain("listeners.push(() => target.removeEventListener")
  })

  it("clears every timer handle it declares", () => {
    const declared = [...eye.matchAll(/let (\w+): ReturnType<typeof setTimeout>/g)].map(
      (m) => m[1],
    )
    expect(declared.sort()).toEqual(["blinkT", "doubleBlinkT", "rsT", "sacT"])
    const cleared = /for \(const t of \[([^\]]+)\]\) if \(t\) clearTimeout\(t\)/.exec(eye)
    expect(cleared, "destroy() no longer clears a list of timers").toBeTruthy()
    const names = cleared![1].split(",").map((s) => s.trim())
    for (const handle of declared) {
      expect(names, `${handle} is never cleared on unmount`).toContain(handle)
    }
  })

  it("reverts the timelines and cancels the pointer RAF", () => {
    // `tl` owns the onScroll observer; reverting it is what detaches the
    // scroll listener Anime.js attached outside our tracker.
    expect(eye).toMatch(/for \(const t of \[tl, blinkTl, introTl\]\)/)
    expect(eye).toContain("cancelAnimationFrame(pointerRaf)")
    expect(eye).toContain("pointerRaf = requestAnimationFrame(")
  })

  it("never reaches outside its root for an element", () => {
    expect(eye).not.toContain("document.querySelector")
    expect(eye).not.toContain("document.getElementById")
    expect(eye).toContain("root.querySelector")
  })

  it("hands back a destroy function rather than running forever", () => {
    expect(eye).toContain("export function mountEye(root: HTMLElement): () => void")
    expect(eye).toContain("return function destroy()")
    // The source's debug handle is fine, but it must not outlive the route.
    expect(eye).toContain("delete (window as unknown as { __eye?: unknown }).__eye")
  })
})
