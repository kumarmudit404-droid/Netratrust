# NetraTrust — UI Design System

> **Source of truth:** `SPEC.md` §7 (UI) and `CLAUDE.md`. Streamlit **1.66.1**,
> Plotly **7.1.0**, `st.navigation(position="top")`, five views. Colour values and the
> type scale below are design decisions for this document; contrast ratios are measured
> against WCAG 2.1 AA, not estimated.

## Table of contents
1. [Principles](#1-principles)
2. [Colour tokens](#2-colour-tokens)
3. [Typography](#3-typography)
4. [Layout and views](#4-layout-and-views)
5. [Component states](#5-component-states)
6. [The small-n rule](#6-the-small-n-rule)

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
| `--text` | `#111827` | `--bg` | 16.1:1 | body text |
| `--text-muted` | `#4B5563` | `--bg` | 7.6:1 | captions |
| `--usable` | `#1B7F4B` | `--bg` | 4.6:1 | Usable / grade-0 text + icon |
| `--borderline` | `#9A6700` | `--bg` | 4.8:1 | Borderline text |
| `--reject` | `#B42318` | `--bg` | 6.0:1 | Reject / refer text |
| `--abstain` | `#5B4BC4` | `--bg` | 6.3:1 | Abstention text |
| `--border-subtle` | `#D0D5DD` | `--bg` | 1.5:1 *(decorative)* | card borders only |

Dark theme flips `--bg`→`#0B0F14`, `--surface`→`#161B22`, `--text`→`#E6EDF3`; status
hues are lightened to hold ≥ 4.5:1 on the dark background. **TBD — verify** dark ratios
before shipping dark mode.

## 3. Typography
System UI stack (`-apple-system, Segoe UI, Roboto, sans-serif`); 1.25 modular scale.

| Role | Size | Weight |
|---|---|---|
| Display (view title) | 30 px | 700 |
| Section heading | 24 px | 600 |
| Subheading | 20 px | 600 |
| Body | 16 px | 400 |
| Caption / CI label | 13 px | 400 |

Numbers in tables use tabular figures (`font-variant-numeric: tabular-nums`) so columns
align.

## 4. Layout and views
Top navigation via `st.navigation(position="top")`. Five views:
1. **Capture** — image in, large quality verdict (colour token + icon + text label),
   reason line, and a prominent **Recapture** button on Reject.
2. **Grade** — grade or **ABSTAIN**, the 90% prediction set, optional Grad-CAM overlay.
3. **Referrals** — list with current state; actions follow the state machine only.
4. **Sites** — per-site forest plot (gradability/abstention with Wilson intervals), drift
   flags; auto-refresh via `st.fragment(run_every=...)`.
5. **Ledger** — verify button, latest signed checkpoint, chain status.

A server-side connectivity flag drives an **Online / Offline** badge; offline, captures
queue and the queue-depth count is shown.

## 5. Component states
Every status component has seven defined states: Usable, Borderline, Reject, Grade,
Abstain, Pending-sync, Error. Each pairs a colour token with an **icon and a text
label** — colour is never the sole carrier of meaning (colour-blind safe).

## 6. The small-n rule
No bare percentage is rendered for **n < 30**. A single shared formatter
(`format_rate(k, n)`) returns either `"k/n (Wilson lo–hi)"` or, for n < 30,
`"k of n"` with no percentage. Every view calls this formatter; the rule is implemented
once, not re-decided per screen.
