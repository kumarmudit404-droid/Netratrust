# NetraTrust — Progress Log

> **Append-only.** Add new entries at the bottom; never edit or delete a past entry. If
> something here turns out wrong, append a correction that references it. This mirrors
> the ledger discipline: history is added to, not rewritten. The source of truth for
> anything technical is `SPEC.md` and `CLAUDE.md`, not this file — this file records
> *what happened*, not what the contract says. Ownership is by lane (A/B/C), not person.

## Entry format
```
### YYYY-MM-DD — <lane> — <short title>
- what changed:
- verified:
- unverified / TBD:
```

---

### 2026-10-27 — Lane A — Starter repo scaffolded
- what changed: created `SPEC.md`, `CLAUDE.md`, `requirements.txt`, `.python-version`,
  `.claude/settings.json` (Stop hook: `pytest -q || exit 2`), `.claude/rules/ml.md`,
  `config/thresholds.yaml`, `.gitignore`, package `__init__.py` files.
- verified: repo tree complete; names removed; ownership is by lane.
- unverified: none.

### 2026-10-27 — Lane C — Metrics module written
- what changed: `netra/eval/metrics.py` — brier (uses `y_proba=`), nll,
  calibration_slope_intercept (`C=np.inf`), ece (returns value + binning desc),
  fit_temperature, risk_coverage, augrc, coverage_at_risk, wilson_interval,
  abstention_report.
- verified: module imports; 2 unit tests pass (`test_metrics.py`); `wilson_interval`
  cross-checked with numpy only.
- unverified: remaining functions not yet unit-tested.

### 2026-10-27 — Lane C — Split script written
- what changed: `scripts/make_splits.py` — SHA-256 patient-level bucketing, seed
  20261027, 60/20/20 train/calib/test, asserts no patient overlap.
- verified: smoke-tested on a synthetic 200-row manifest, no leakage.
- unverified: not yet run on real EyePACS/APTOS manifests.

### 2026-10-27 — Lane A — Config and key tooling
- what changed: `config/thresholds.yaml` (quality gate, conformal 0.90, refer set
  [2,3,4], min n 30); `scripts/gen_device_key.py` (per-device Ed25519, replaces mTLS);
  `tests/test_metrics.py`.
- verified: config parses; key script uses cryptography 50.0.2 API.
- unverified: thresholds are placeholders until fitted on the calibration split.

### 2026-10-27 — all lanes — Grounding docs generated
- what changed: `prd.md`, `architecture.md`, `design.md`, `rules.md`, `tracker.md`,
  `memory.md` written; all member names removed and replaced with lane labels.
- verified: docs consistent with frozen `SPEC.md`; no names remain in the repo.
- unverified / TBD: 42% cataract figure; AIOS/VRSI 2021 statement; RETFound
  gate-approval mode; T4 training times; `NetraTrust build pipeline.pdf` not parsed.

### Status snapshot (end of 2026-10-27)
- Done: scaffold, metrics module, split script, config, key tooling, six grounding docs.
- Not started: DR/quality models trained, API endpoints, ledger implementation, UI.
- Next: Wednesday build — see `tracker.md`.

### 2026-10-27 — Lane B — Front end switched from Streamlit to a Vite + React + TS PWA (docs only)
- what changed: stack decision recorded in the docs; **no code written yet**.
  `design.md` — Streamlit specifics removed (`st.navigation`, `st.fragment`); colour
  tokens, type scale, the seven component states and the n<30 rule kept and re-expressed
  as Tailwind theme tokens (CSS custom properties + `theme.extend`) and React components
  (`<StatusBadge/>`, `<VerdictPanel/>`, `<TopNav/>`, `formatRate`); added Tailwind
  mapping, motion/offline sections. `architecture.md` — UI stack rows replaced with
  Vite/React/TS + Tailwind/shadcn/TanStack Query/Recharts/vite-plugin-pwa/Framer Motion,
  `netra/ui` folder structure expanded, and one line added that the API needs **CORS for
  local dev (Lane A task)**. `CLAUDE.md` — UI command is now
  `cd netra/ui && npm run dev`. `tracker.md` — T-13..T-17 relabelled to the React routes.
- verified: all nine contrast ratios in `design.md` §2 recomputed from the hex values
  with the WCAG relative-luminance formula. Every AA verdict in the table is unchanged,
  but the printed numbers were slightly off and are now the measured values (e.g.
  `--text` 16.1 → 17.74, `--reject` 6.0 → 6.57, `--usable` 4.6 → 5.02). Two findings
  recorded in the doc: `--borderline` on `--surface` is **4.49**, marginally under AA for
  normal text, so status text is not placed on `--surface` below large-text size; and the
  light status hues measure 2.92–3.95 on the dark background, i.e. they fail AA and must
  be lightened. No Streamlit reference remains in the four docs except two deliberate
  contract notes. Lane respected — nothing under `netra/api`, `netra/ledger`,
  `netra/db`, `netra/models`, `netra/eval` or `notebooks` was read or touched.
- unverified / TBD: **`SPEC.md` §7 still names Streamlit 1.66.1, Plotly 7.1.0,
  `st.navigation` and `st.fragment`.** SPEC.md is frozen and was deliberately not
  edited, so the contract is now stale on the UI stack and needs a team amendment in its
  own commit. `requirements.txt` still pins `streamlit==1.66.1` and `plotly==7.1.0` —
  also not touched (agreement-only file). Dark-theme status hues are **TBD — verify**.
  `netra/ui/package.json` does not exist yet, so no front-end dependency is pinned and
  `npm run dev` / `npm run build` do not yet run. Node/npm availability on this machine
  is unconfirmed. T-13's `blocked by` is still `T-01` (the Python venv), which the React
  scaffold does not actually depend on — left as-is pending your call.

### 2026-10-27 — all lanes — SPEC.md §7 amended by agreement: UI stack is now a React PWA
- what changed: **contract amendment, approved by the team.** `SPEC.md` §7 — the stack
  sentence now reads "Custom front end in `netra/ui`: Vite + React + TypeScript PWA —
  Tailwind CSS, shadcn/ui, TanStack Query, Recharts, vite-plugin-pwa, Framer Motion",
  with an inline note that it superseded Streamlit 1.66.1 + Plotly 7.1.0 on 2026-10-27.
  Two framework-mechanism references in the same section were de-branded with it:
  the funnel bullet lost `go.Funnel` / `textinfo="value+percent previous"` and now reads
  "each stage labelled with its value and percent of the previous stage"; the live-panel
  bullet lost `st.fragment(run_every=...)` and now reads "poll the API on an interval".
  `requirements.txt` — `streamlit==1.66.1` and `plotly==7.1.0` removed, replaced by a
  comment pointing at `netra/ui/package.json`. `design.md` — the temporary "open
  contract note" removed. `tracker.md` — T-13 `blocked by` repointed from T-01 to
  "Node (installed)". `netra/ui/__init__.py` deleted. New `pyproject.toml` excludes
  `netra/ui` from ruff (`extend-exclude`) and pytest (`norecursedirs`, `testpaths`).
  `.gitignore` — added `netra/ui/node_modules/`, `dist/`, `dev-dist/`.
- verified: what §7 had to keep is intact and unedited — the five views, the forest plot
  of Wilson intervals against the pooled line with the no-violins/no-KDE rule, the
  value-and-percent-of-previous funnel labelling, and "Images are never uploaded" (which
  lives at the end of the API contract section and was not touched). The nine-endpoint
  API table and the referral state machine were **not** touched. No `streamlit`,
  `plotly`, `st.navigation`, `st.fragment` or `go.Funnel` reference remains anywhere in
  the repo. `netra/ui` is now empty of Python.
- unverified / TBD: **the amendment is not committed.** The repo is not a git repository
  (`git rev-parse` fails), and no commit was made — so "its own commit" could not be
  honoured. The amendment is staged on disk as a self-contained changeset
  (`SPEC.md` + `requirements.txt`) awaiting `git init`. Nothing has verified that the
  remaining Python deps still resolve after the two removals — `pip install -r
  requirements.txt` has still never been run (T-01 is open; Python 3.12 is not
  installed). Dark-theme status hues remain **TBD — verify**.

### 2026-10-27 — Lane B — T-13 React PWA scaffolded in netra/ui; npm run build green
- what changed: new front end under `netra/ui`, nothing else touched.
  Config — `package.json` (own deps, Python untouched), `tsconfig.json` +
  `tsconfig.app.json` + `tsconfig.node.json` (strict, `@/*` → `src/*`),
  `vite.config.ts` (React plugin, vite-plugin-pwa `autoUpdate`, dev proxy `/v1` →
  `127.0.0.1:8000`), `tailwind.config.ts`, `postcss.config.js`, `components.json`
  (shadcn), `index.html`, `.env.example`, `public/favicon.svg`.
  Tokens — `src/index.css` declares all nine `design.md` §2 colour tokens as CSS custom
  properties with their measured ratios in a comment; `tailwind.config.ts` maps them to
  `theme.extend.colors` and the five-step type scale to `theme.extend.fontSize`. No hex
  is hard-coded in a component. Global `:focus-visible` ring and a
  `prefers-reduced-motion` block.
  shadcn/ui — `components.json` + `cn()` (clsx + tailwind-merge) + CVA primitives
  `ui/button.tsx` (44 px min touch target) and `ui/card.tsx`, themed to our tokens
  rather than the default slate palette.
  API — `src/lib/api/{types,client,mock,queries,errors}.ts`: one typed function per
  endpoint for exactly the nine frozen endpoints, `Idempotency-Key` header on
  `POST /v1/encounters`, and an in-memory mock responder behind `VITE_USE_MOCK`
  (default on) so screens work before the backend exists.
  Components/routes — `StatusBadge.tsx` holding all seven `design.md` §6 states as a
  discriminated union (each pairing token + icon + text label), `TopNav.tsx` with the
  five routes and the queue/connectivity strip, `App.tsx` routing, `main.tsx` with the
  TanStack Query provider. `Capture` and `Grade` are placeholders for T-14/T-15;
  `Referrals`, `Sites`, `Ledger` are routed stubs.
- verified: `npm run build` **green** — `tsc -b` clean under `strict`, Vite 6.4.5 built
  1640 modules, PWA service worker generated (`dist/sw.js`, 7 precache entries). Ran it
  three times across the fixes. Three real defects found and fixed: `@types/node` was
  missing so `tsc -b` failed on `node:url` (added as a devDependency); three lucide icon
  names in `StatusBadge` do not exist in the installed version — `XCircle` →
  `CircleX`, `AlertTriangle` → `TriangleAlert`, and there is no `CircleHalf` so
  borderline uses `Contrast`; and the PWA manifest pointed at `icon-192.png` /
  `icon-512.png`, which do not exist, now pointing at the real `favicon.svg`.
  The nine Wilson intervals in the mock were initially written by hand, then recomputed
  with the same formula as `netra/eval/metrics.py::wilson_interval` and replaced, so no
  fabricated statistic ships even in demo data. Lane respected: every file written is
  under `netra/ui`, plus the four root docs and three root config files you approved
  (`SPEC.md`, `requirements.txt`, `pyproject.toml`, `.gitignore`, `CLAUDE.md`,
  `design.md`, `architecture.md`, `tracker.md`).
- unverified / TBD: the app has **never been run against the real API** — every screen
  is on mock data, and `VITE_USE_MOCK=0` is untested. **CORS is still not implemented**
  (Lane A, T-?) so the first real call will fail until it is. Three response shapes in
  `types.ts` are marked TBD because `SPEC.md` describes them in prose, not fields:
  `GET /v1/sites/{id}/status` (SPEC says "gradability rate", modelled as counts + Wilson
  because a bare rate cannot satisfy the n<30 rule), the `POST /v1/sites/{id}/audit`
  payload, and the element type of `attempts` in `GET /v1/queue/depth` — all need Lane A
  confirmation. `pyproject.toml`'s ruff/pytest excludes are **unverified by execution**
  because pytest is still not installed (T-01 open, Python 3.12 absent). No front-end
  unit-test runner exists — `npm run build` is the only gate, since vitest is not in the
  agreed stack. Raster PWA icons are **TBD — verify**. Dark-theme status hues remain
  **TBD — verify**. `recharts@2.15.4` warns that 2.x is no longer active and suggests
  v3; left on 2.x and not bumped.
