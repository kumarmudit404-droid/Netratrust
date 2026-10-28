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

### 2026-10-27 — Lane B — T-14/T-15: Capture + Grade/Abstain routes built, with the TopNav shell
- what changed: all under `netra/ui`. New `src/lib/clinical.ts` — `REFER_GRADES`
  `[2,3,4]` and `CONFORMAL_CONFIDENCE` 0.9 mirroring `config/thresholds.yaml`, plus
  `spansClinicalActions()` implementing the SPEC §3 abstention rule (spans refer vs
  do-not-refer, **not** set size). New `src/lib/sha256.ts` — the captured image is
  hashed with `crypto.subtle` in the browser and only the hex leaves the component.
  New `src/lib/gateSim.ts` — seven explicit operator-chosen scenarios standing in for
  Lane C's on-device gate. New `src/state/encounter.tsx` — in-memory context for the
  case on screen (no image bytes, no cached clinical state). New
  `src/components/VerdictPanel.tsx` and `PredictionSet.tsx`. `routes/Capture.tsx` and
  `routes/Grade.tsx` built out; `Referrals`, `Sites`, `Ledger` left as routed stubs.
  `main.tsx` wraps the app in `EncounterProvider`. Added vitest config block to
  `vite.config.ts`. Three test files: `formatRate.test.ts`, `clinical.test.ts`,
  `routes/routes.smoke.test.ts`.
- verified: `npm run build` and `npm test` both green — **23 tests, 3 files**. Capture:
  a `reject` renders the "No result — take again" headline, the sentence "This is NOT a
  negative result — the patient has not been screened yet", the reason-code explanation,
  "Take another image" as the primary action, and **no grade block, no prediction set and
  no referral control**; the quieter "Cannot retake" path posts
  `prediction_set: null`. Grade: a reject or null prediction set short-circuits to a
  "no result to show" panel before any grading UI; `{1,2}` and `{0,3}` abstain with "A
  doctor should check this" while `{2,3,4}` does not, which `clinical.test.ts` pins in
  both directions. Confirmed in the built CSS that every token class actually emits
  (`text-abstain`, `border-l-abstain`, `--abstain: #5b4bc4` …) — Tailwind drops unknown
  classes silently, so this was checked rather than assumed. Four defects found and
  fixed during the step: a `style={undefined}` left in `Grade.tsx`; the vitest `test`
  block turned `npm run build` **red** because Vite's `defineConfig` does not type it
  (now imported from `vitest/config`); and in the earlier commit work two
  `.tsbuildinfo` build artifacts had been committed and are now gitignored and untracked.
- unverified / TBD: **no screen has been visually rendered or interacted with.** No DOM
  test library is in Lane B's stack by agreement, so `routes.smoke.test.ts` asserts only
  that modules import and export a component — it cannot assert layout, contrast in
  situ, focus order or that the Reject screen reads as intended to a human. A browser
  pass on `npm run dev` is still owed. The app has still never run against the real API
  (`VITE_USE_MOCK=0` untested, **CORS still a Lane A task**). `gateSim.ts` is a UI driver,
  not a model: no number it produces is a measurement, and it must be deleted when Lane C
  exposes a real gate. `clinical.ts` duplicates `config/thresholds.yaml` values the front
  end cannot read at runtime — flagged `TODO(Lane A)` to serve them from the API.
  `SIM_MODEL_VERSION` is a placeholder, not a trained checkpoint. The abstention queue
  itself (a list of abstained cases) is not built — only the single-case Abstain view.

### 2026-10-28 — Lane B — First browser pass on T-14/T-15, and SPEC §7 view-list amendment
- what changed (browser pass, commit `435e190`): `npm run dev` was run and the two built
  screens were driven in Chrome for the first time. Four defects, none of which the test
  suite could reach. (1) `src/lib/utils.ts` — `cn()` used bare `twMerge`, which does not
  know our custom `fontSize` scale, so it classified `text-subhead` / `text-caption` as
  text COLOURS and put them in the same conflict group as `text-bg` / `text-abstain`;
  the later class silently won. The "Select fundus image" primary button shipped as
  `--text` on `--text` — **contrast 1:1, the label was invisible**. Fixed with
  `extendTailwindMerge` declaring the five scale steps; new `src/lib/utils.test.ts`
  (5 tests) pins both directions. (2) `routes/Capture.tsx` — the `sr-only`
  `<input type=file>` was still tabbable, so a keyboard user landed on an invisible
  control with no focus ring; now `tabIndex={-1}` + `aria-hidden`. (3) `routes/Grade.tsx`
  — abstain was announced more quietly than reject (13px badge over a paragraph, with
  `<h2>` reading "Abstained" rather than the message) against design.md §1; both Grade
  outcomes now use the VerdictPanel treatment — status icon + 30px display headline +
  status-coloured border. (4) `src/index.css` + `design.md` §2 — `--borderline` `#9A6700`
  measures **4.49:1 on `--surface`**, under AA, and is used at caption size on cards
  (the simulated-gate legend, the "grade is provisional" note), which is exactly what
  index.css's own comment told us not to do; darkened to `#926300` (5.24 on `--bg`,
  4.84 on `--surface`). `routes/Grade.tsx` also now shows the queue-depth pending count
  on the abstain state.
- what changed (amendment, its own commit): `SPEC.md` §7's five views changed from
  "capture + gate verdict; abstention queue; performance dashboard; ledger verification
  + tamper demo; offline queue indicator" to the built IA — **Capture, Grade/Abstain,
  Referrals, Sites (performance), Ledger** — each with a one-line description, plus an
  inline note naming the superseded wording and dated 2026-10-28. Three substantive
  intents from the old wording were preserved as explicit bullets: the Ledger view MUST
  carry the tamper demo (append → corrupt one entry → `verify` returns `ok:false` with
  `first_bad_index`), tracked as T-17; offline/pending-sync visibility is the `<TopNav/>`
  strip fed by `GET /v1/queue/depth`, which **replaces** the standalone "offline queue
  indicator" view; and the abstain state routes to human review and shows the pending
  count from `GET /v1/queue/depth`, with **no** separate abstention-queue view and **no**
  new list endpoint. `tracker.md` T-17 widened to name the tamper demo.
- verified: `npm run build` and `npm test` green after every fix — **28 tests, 4 files**
  (23 before, +5 for `cn`). In Chrome at 1431×840: the Reject screen shows "No result —
  take again", the reason code and score, "Take another image" as the primary action,
  and asserted-by-script **no grade, no prediction set, no referral control**; the
  abstain `{1,2}` screen shows "A doctor should check this." as a 30px `--abstain`
  headline and states the case is routed for specialist review, not a dead end. Focus
  order walked with real Tab presses: nav ×5 → Select fundus image → scenario select →
  Take another image → Cannot retake, with the hidden input skipped and a visible ring
  on each. Contrast re-measured **in situ** against both `--bg` and `--surface` with the
  WCAG 2.1 formula; `--borderline` was the only sub-AA case and is fixed. §7 re-read
  after editing: the only remaining instances of "abstention queue" and "offline queue
  indicator" are inside the deliberate "this replaces…" quotation. The nine-endpoint API
  table and the referral state machine were **not** touched.
- unverified / TBD: the pending count on the abstain state is the **device's unsynced
  record depth**, which is what `GET /v1/queue/depth` returns — it is NOT a count of
  cases awaiting a specialist, and is worded that way on screen and in §7 so no one
  reads a clinical backlog into it. If a true specialist-review backlog is ever wanted
  it needs a Lane A decision, and under the frozen nine there is no endpoint for it.
  Everything on screen is still **mock data** (`VITE_USE_MOCK=1`); the app has still
  never run against the real API and **CORS is still a Lane A task**. Only the light
  theme was looked at — dark-theme status hues remain **TBD — verify**, and the
  `--borderline` change has not been re-measured for dark. Only one viewport (1431×840)
  was checked; no phone/tablet width was exercised, though the camp device is a tablet.
  `Referrals`, `Sites` and `Ledger` are still routed stubs and were not opened.

### 2026-10-28 — Lane A — T-01 build environment
- what changed: `py -3.12 -m venv .venv`; `pip install -r requirements.txt`; `.venv/`
  added to `.gitignore` (it was not listed, so the venv showed as untracked). No pinned
  version was changed.
- verified: Python **3.12 was not installed on the build machine** — `py -0` listed only
  3.13 — so 3.12.10 was installed side-by-side via winget (`Python.Python.3.12`) by
  agreement, leaving 3.13 untouched. The first winget attempt failed with
  `0x80072ee7 (ERROR_INTERNET_NAME_NOT_RESOLVED)`; a straight retry succeeded, so it was
  transient DNS, not a bad package. `.venv` reports Python 3.12.10, pip 26.2.2.
  Every pin in `requirements.txt` resolved to a **cp312 wheel** and installed clean
  (exit 0): torch 2.14.1, torchvision 0.29.1, timm 1.0.30, numpy 2.5.4, scipy 1.18.1,
  scikit-learn 1.9.1, mapie 1.6.0, fastapi 0.162.0, starlette 1.6.0, pydantic 2.14.1,
  uvicorn 0.54.0, sqlmodel 0.0.48, sqlalchemy 2.1.6, cryptography 50.0.2, rfc8785 0.1.4,
  httpx 0.28.1, grad-cam 1.5.7 (built from sdist), fhir.resources 8.3.0, pytest 8.4.2,
  ruff 0.17.3. `pytest -q` on the pre-existing suite: **2 passed**.
- unverified / TBD: `.python-version` still says 3.12 and now matches the interpreter,
  but nothing pins the 3.12.x patch level. `pyyaml 6.0.3` arrived **transitively** (via
  timm) and is NOT pinned in `requirements.txt`, so Lane A does not import it — see the
  T-02 entry for the stdlib threshold reader written instead. No GPU was present; torch
  was not exercised beyond import resolution, which is Lane C's concern.

### 2026-10-28 — Lane A — T-02 database tables and append-only triggers
- what changed: `netra/db/models.py` (the seven tables of architecture.md §3 plus a
  documented eighth), `netra/db/engine.py` (engine, `init_db`, trigger install/drop,
  `session_scope`), `netra/db/util.py` (`now_iso`, `new_id` — both STRINGS),
  `tests/conftest.py`, `tests/test_db.py` (14 tests).
- what changed (deliberate deviations, both flagged rather than silent):
  1. **An eighth table, `idempotency_keys`** (`key, endpoint, request_fingerprint,
     status[in_flight|done], response_json, created_at`). architecture.md §3 says
     "Seven tables"; SPEC.md §5 requires server-side idempotent dedup and names no
     table. It stores no clinical fact and adds no endpoint, so the frozen contract is
     untouched. `architecture.md` still reads "Seven tables" and was NOT edited —
     that is a doc change to agree, not a Lane A edit.
  2. **The ledger row carries BOTH doc spellings.** SPEC.md §4 lists `idx, prev_hash,
     payload_hash, payload_json, signer_kid, signature`; architecture.md §3 lists
     `seq, entry_hash, prev_hash, payload, signer_kid, signature, created_at`. The
     table has `seq` (== SPEC's `idx`, and the source of the API's `ledger_idx`/`idx`),
     `prev_hash`, `payload_hash`, `entry_hash`, `payload_json`, `signer_kid`,
     `signature`, `created_at` — every field either doc names, because verification
     needs the payload hash and the chained hash separately.
- verified: **14 tests pass.** The four ledger-bearing tables (`encounters`,
  `referral_events`, `ledger`, `checkpoints`) each refuse UPDATE and DELETE — asserted
  per table, parametrised, with the trigger's own message matched. `RAISE(ABORT, …)`
  surfaces as **`sqlalchemy.exc.IntegrityError`, not `OperationalError`** (the first
  draft asserted the wrong class and failed). `referrals` is asserted MUTABLE on
  purpose: `state` must advance, and its history lives in the append-only
  `referral_events`. Foreign keys are enforced — SQLite has them OFF by default, so
  `make_engine` issues `PRAGMA foreign_keys = ON`; a bad `site_id` now raises. SQLAlchemy
  does NOT order a site INSERT before a device INSERT (no `relationship()` between
  them), so the fixture flushes between the two — found by a real FK failure, not
  predicted. `init_db` is idempotent. `ruff check` and `ruff format --check` clean on
  every file in this step.
- unverified / TBD: the triggers stop the APPLICATION from rewriting history; they do
  not stop anyone with direct database access, who can `DROP TRIGGER`. That is the
  honest threat model and the reason the hash chain and signatures exist — see T-03.
  No migration tooling: schema changes are `create_all` on a fresh file. Concurrency is
  untested beyond SQLite's single-writer default; `aiosqlite` stays banned.
  The repo's **pre-existing** `scripts/` files already fail `ruff check` (3 findings,
  import sorting) — not touched, not this lane's call to fix.
