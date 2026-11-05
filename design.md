# NetraTrust — UI Design System

> **Source of truth:** `SPEC.md` §7 (UI) and `BUILD_RULES.md`. The front end is a custom
> **Vite + React + TypeScript** PWA in `netra/ui` — Tailwind CSS, shadcn/ui, TanStack
> Query, Recharts, vite-plugin-pwa, Framer Motion. Colour values and the type scale
> below are design decisions for this document; contrast ratios are **measured** with
> the WCAG 2.1 relative-luminance formula, not estimated.

## Table of contents
1. [Principles](#1-principles)
2. [Colour tokens](#2-colour-tokens)
3. [Tailwind theme mapping](#3-tailwind-theme-mapping)
4. [Typography](#4-typography)
5. [Layout and views](#5-layout-and-views)
6. [Component states](#6-component-states)
7. [The small-n rule](#7-the-small-n-rule)
8. [Motion and offline](#8-motion-and-offline)

## 1. Principles
- **Clinical, not consumer.** High contrast, no decoration that competes with data.
- **Refusal is a first-class state.** Reject and Abstain are shown as clearly as a grade.
- **Honesty over reassurance.** Uncertainty and small samples are shown, never hidden.

## 2. Colour tokens
Light theme (default). All **text** tokens meet AA (≥ 4.5:1 normal, ≥ 3:1 large).
Tokens marked *decorative* fall below 3:1 and are used only for fills/borders, never
for text.

| Token | Hex | On | Ratio | Use |
|---|---|---|---|---|
| `--bg` | `#FFFFFF` | — | — | page background |
| `--surface` | `#F4F6F8` | — | — | cards |
| `--text` | `#111827` | `--bg` | 17.74:1 | body text |
| `--text-muted` | `#4B5563` | `--bg` | 7.56:1 | captions |
| `--usable` | `#1B7F4B` | `--bg` | 5.02:1 | Usable / grade-0 text + icon |
| `--borderline` | `#926300` | `--bg` | 5.24:1 | Borderline text |
| `--reject` | `#B42318` | `--bg` | 6.57:1 | Reject / refer text |
| `--abstain` | `#5B4BC4` | `--bg` | 6.46:1 | Abstention text |
| `--border-subtle` | `#D0D5DD` | `--bg` | 1.47:1 *(decorative)* | card borders only |

Every status token clears AA on `--surface` at any size: text 16.37, muted 6.98,
usable 4.63, borderline 4.84, reject 6.07, abstain 5.97. `--borderline` was `#9A6700`
and measured 4.49 on `--surface`, a hair under 4.5; because it is used at caption size
on cards (the simulated-gate legend, the "grade is provisional" note), it was darkened
to `#926300` rather than the size caveat being carried. Measured in situ in the browser
on 2026-10-28, not estimated.

Dark theme flips `--bg`→`#0B0F14`, `--surface`→`#161B22`, `--text`→`#E6EDF3`
(16.27:1 on `--bg`, 14.64:1 on `--surface` — both AAA). The light status hues do **not**
survive the flip — measured on `#0B0F14` they are usable 3.83, borderline 3.95, reject
2.92, abstain 2.97, all below 4.5 — so they must be lightened. Replacement dark hues:
**TBD — verify** before shipping dark mode.

## 3. Tailwind theme mapping
Tokens are declared once as CSS custom properties on `:root` in `src/index.css`, then
referenced by Tailwind so a token change propagates everywhere. Never hard-code a hex in
a component.

```css
/* src/index.css */
:root {
  --bg: #FFFFFF;  --surface: #F4F6F8;
  --text: #111827; --text-muted: #4B5563;
  --usable: #1B7F4B; --borderline: #926300;
  --reject: #B42318; --abstain: #5B4BC4;
  --border-subtle: #D0D5DD;
}
:root[data-theme="dark"] {
  --bg: #0B0F14; --surface: #161B22; --text: #E6EDF3;
  /* status hues: TBD — verify (light values fail AA on this background) */
}
```

```ts
// tailwind.config.ts — theme.extend.colors
colors: {
  bg:            "var(--bg)",
  surface:       "var(--surface)",
  text:          { DEFAULT: "var(--text)", muted: "var(--text-muted)" },
  usable:        "var(--usable)",
  borderline:    "var(--borderline)",
  reject:        "var(--reject)",
  abstain:       "var(--abstain)",
  "border-subtle": "var(--border-subtle)",
}
```

| Token | Tailwind utility |
|---|---|
| `--bg` | `bg-bg` |
| `--surface` | `bg-surface` |
| `--text` | `text-text` |
| `--text-muted` | `text-text-muted` |
| `--usable` | `text-usable`, `border-usable` |
| `--borderline` | `text-borderline`, `border-borderline` |
| `--reject` | `text-reject`, `border-reject` |
| `--abstain` | `text-abstain`, `border-abstain` |
| `--border-subtle` | `border-border-subtle` — borders and fills only, **never** `text-` |

shadcn/ui components are generated into `src/components/ui/` and re-themed to these
tokens; the default shadcn slate palette is not used. Recharts series take the same
tokens via the CSS variables, so a chart exported for the demo keeps its contrast.

## 4. Typography
System UI stack (`-apple-system, Segoe UI, Roboto, sans-serif`); 1.25 modular scale.

| Role | Size | Weight | Tailwind |
|---|---|---|---|
| Display (view title) | 30 px | 700 | `text-display font-bold` |
| Section heading | 24 px | 600 | `text-section font-semibold` |
| Subheading | 20 px | 600 | `text-subhead font-semibold` |
| Body | 16 px | 400 | `text-body` |
| Caption / CI label | 13 px | 400 | `text-caption` |

```ts
// tailwind.config.ts — theme.extend.fontSize
fontSize: {
  display: ["30px", { lineHeight: "1.2",  fontWeight: "700" }],
  section: ["24px", { lineHeight: "1.25", fontWeight: "600" }],
  subhead: ["20px", { lineHeight: "1.3",  fontWeight: "600" }],
  body:    ["16px", { lineHeight: "1.5" }],
  caption: ["13px", { lineHeight: "1.45" }],
}
```

Numbers in tables use tabular figures — `tabular-nums` (Tailwind) /
`font-variant-numeric: tabular-nums` — so columns align. 16 px is the floor for anything
a clinician reads; 13 px is for captions and CI labels only.

## 5. Layout and views
Top navigation as a React component (`<TopNav/>`) over a client-side router, with the
five views as routes. Live panels refetch through **TanStack Query**
(`refetchInterval`), not a framework polling primitive.

| Route | View | Content |
|---|---|---|
| `/capture` | **Capture** | image in, large quality verdict (colour token + icon + text label), reason line, and a prominent **Recapture** button on Reject |
| `/grade` | **Grade / Abstain** | grade or **ABSTAIN**, the 90 % prediction set, optional Grad-CAM overlay |
| `/referrals` | **Referrals** | list with current state; actions follow the state machine only |
| `/sites` | **Sites** | per-site forest plot (gradability/abstention with Wilson intervals) in Recharts, drift flags; auto-refresh via TanStack Query `refetchInterval` |
| `/ledger` | **Ledger** | verify button, latest signed checkpoint, chain status |

Per `SPEC.md` §7: the per-site view is a **forest plot of Wilson intervals against the
pooled line** and doubles as the drift monitor — **no violins, no KDE**, which invent
structure at realistic per-site n. The referral funnel keeps its value-and-percent-of-
previous labelling; in Recharts that is an explicit label on each stage rather than a
Plotly `textinfo` string.

A server-side connectivity flag drives an **Online / Offline** badge; offline, captures
queue and the queue-depth count is shown.

## 6. Component states
Every status component has seven defined states: **Usable, Borderline, Reject, Grade,
Abstain, Pending-sync, Error**. Each pairs a colour token with an **icon and a text
label** — colour is never the sole carrier of meaning (colour-blind safe).

Implemented once as a discriminated union plus a single component, so no screen
re-decides a status treatment:

```ts
// src/components/StatusBadge.tsx
export type Status =
  | "usable" | "borderline" | "reject"
  | "grade"  | "abstain"
  | "pending-sync" | "error";
```

| State | Token | Icon | Label |
|---|---|---|---|
| Usable | `--usable` | filled circle | "Usable" |
| Borderline | `--borderline` | half circle | "Borderline — recapture advised" |
| Reject | `--reject` | cross | "No result — take again" |
| Grade | `--text` | bar | "Grade n" |
| Abstain | `--abstain` | diamond | "A doctor should check this" |
| Pending-sync | `--text-muted` | arrows | "Queued — n waiting" |
| Error | `--reject` | triangle | "Error" (with the message, never a bare colour) |

`<StatusBadge/>` and `<VerdictPanel/>` are the only places these treatments exist.
Focus is never removed: interactive elements keep a visible focus ring
(`focus-visible:ring-2`), and Pending-sync is **not** an error state — offline is normal
for this app.

## 7. The small-n rule
No bare percentage is rendered for **n < 30**. A single shared formatter
(`formatRate(k, n)` in `src/lib/formatRate.ts`) returns either `"k/n (Wilson lo–hi)"`
or, for n < 30, `"k of n"` with no percentage. Every view calls this formatter; the rule
is implemented once, not re-decided per screen.

```ts
// src/lib/formatRate.ts
export function formatRate(k: number, n: number): string;
```

The threshold mirrors `config/thresholds.yaml` → `sites.min_n_for_rate: 30`; it is not
hard-coded in a component. Wilson bounds are **computed server-side** and arrive with
the API payload — the front end never computes a statistic, since all metrics come from
`netra/eval/metrics.py`.

## 8. Motion and offline
- **Framer Motion** is used for state transitions only — a verdict appearing, a queue
  item leaving — never for decoration, and never to delay a clinical verdict. Durations
  stay ≤ 200 ms and all motion respects `prefers-reduced-motion`.
- **vite-plugin-pwa** makes the app installable and caches the shell for offline use.
  Captures queue locally while offline and sync is at-least-once with an
  `Idempotency-Key` per event; the queue depth is always visible.
- A fundus image is **never** uploaded: the front end sends the hash, the decisions and
  the metadata only.
