/**
 * WCAG AA contrast for every token used as TEXT, computed from index.css.
 *
 * The previous browser pass measured these by hand and found `--borderline` at
 * 4.49:1 on `--surface` — just under AA — and fixed it. A hand measurement
 * cannot stop that regressing, so the arithmetic lives here: change a token in
 * index.css and this fails.
 *
 * It is NOT a substitute for looking at the screens. It proves a colour pair
 * is legible in principle; it says nothing about whether the right colour was
 * applied to the right element, which is what `cn()`'s tailwind-merge bug did
 * last time (a `--text` label on a `--text` button, contrast 1:1, invisible).
 * Only a browser catches that.
 */

/// <reference types="node" />
// The node types are referenced for THIS FILE ONLY. tsconfig.app.json sets
// `types: ["vite/client"]`, so node builtins otherwise fail `tsc -b` even in a
// test - the same trap `process.env` hit in live.test.ts. A triple-slash
// reference scopes them here rather than widening the whole app's type
// environment, which would let browser code import `node:fs` and still
// type-check.
//
// `import "./index.css?raw"` was tried first and returns an EMPTY STRING under
// vitest: Vite's CSS pipeline intercepts the request. Hence reading the file.
import { readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

import { describe, expect, it } from "vitest"

const HERE = dirname(fileURLToPath(import.meta.url))
const CSS = readFileSync(join(HERE, "index.css"), "utf-8")

/** Every non-test source file in src, as raw text. `import.meta.glob` DOES
 *  work for TypeScript sources, so the class scan stays Vite-native. */
const SOURCES = import.meta.glob<string>("./**/*.{ts,tsx}", {
  query: "?raw",
  import: "default",
  eager: true,
})

/** Tokens from the first `:root { ... }` block (the light theme). */
function lightTokens(): Record<string, string> {
  const block = CSS.slice(CSS.indexOf(":root {"))
  const body = block.slice(0, block.indexOf("}"))
  const out: Record<string, string> = {}
  for (const [, name, hex] of body.matchAll(/(--[a-z-]+):\s*(#[0-9a-fA-F]{6})/g)) {
    out[name] = hex
  }
  return out
}

function channel(v: number): number {
  const s = v / 255
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}

function luminance(hex: string): number {
  const n = parseInt(hex.slice(1), 16)
  return (
    0.2126 * channel((n >> 16) & 255) +
    0.7152 * channel((n >> 8) & 255) +
    0.0722 * channel(n & 255)
  )
}

function ratio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const tokens = lightTokens()

/** Colours this app paints TEXT and icons with. `--border-subtle` is excluded
 *  deliberately: index.css marks it decorative and it must never carry text. */
const TEXT_TOKENS = [
  "--text",
  "--text-muted",
  "--usable",
  "--borderline",
  "--reject",
  "--abstain",
] as const

/** AA for normal-size text. The caption step is 13px, so the 3:1 large-text
 *  allowance never applies to these. */
const AA_NORMAL = 4.5

describe("index.css parses", () => {
  it("found every token the theme declares", () => {
    for (const t of [...TEXT_TOKENS, "--bg", "--surface", "--border-subtle"]) {
      expect(tokens[t], `${t} missing from :root`).toMatch(/^#[0-9a-f]{6}$/i)
    }
  })
})

describe.each(["--bg", "--surface"])("AA on %s", (surface) => {
  it.each(TEXT_TOKENS)(`%s clears ${AA_NORMAL}:1`, (token) => {
    const r = ratio(tokens[token], tokens[surface])
    // Reported to 2dp so a failure message names the measured value.
    expect(
      Math.round(r * 100) / 100,
      `${token} on ${surface} measured ${r.toFixed(2)}:1`,
    ).toBeGreaterThanOrEqual(AA_NORMAL)
  })
})

describe("the borderline regression specifically", () => {
  it("stays above AA on --surface, where it previously measured 4.49", () => {
    // #9A6700 measured 4.49:1 here and was darkened to #926300.
    const r = ratio(tokens["--borderline"], tokens["--surface"])
    expect(r).toBeGreaterThanOrEqual(AA_NORMAL)
    expect(ratio("#9a6700", tokens["--surface"])).toBeLessThan(AA_NORMAL)
  })
})

describe("--border-subtle is never used as a text colour", () => {
  it("has no text-border-subtle class anywhere in src", () => {
    // Tests are excluded: this file names the class it forbids.
    const offenders = Object.entries(SOURCES)
      .filter(([file]) => !/\.test\.tsx?$/.test(file))
      .filter(([, source]) => /\btext-border-subtle\b/.test(source))
      .map(([file]) => file)
    expect(offenders).toEqual([])
    // It fails AA by a mile, which is why index.css calls it decorative.
    expect(ratio(tokens["--border-subtle"], tokens["--bg"])).toBeLessThan(AA_NORMAL)
  })
})

describe("dark mode's known gap stays declared, not quietly shipped", () => {
  it("the dark block does not redefine the status hues", () => {
    // index.css records that on #0B0F14 the light hues measure 3.83 / 3.95 /
    // 2.92 / 2.97 - all below AA - and are TBD. If someone adds dark values,
    // this fails and they must measure them rather than assume.
    const dark = CSS.slice(CSS.indexOf('[data-theme="dark"]'))
    const body = dark.slice(0, dark.indexOf("}"))
    for (const token of ["--usable", "--borderline", "--reject", "--abstain"]) {
      expect(body, `${token} got a dark value - measure it`).not.toContain(token)
    }
  })
})
