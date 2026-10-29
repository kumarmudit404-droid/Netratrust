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

### 2026-10-28 — Lane A — T-03 ledger: hash chain, Ed25519, rfc8785 on write and verify
- what changed: `netra/ledger/canonical.py` (rfc8785 + the float/2^53 guards),
  `keys.py` (Ed25519 keystore, `signer_kid` from day one), `chain.py` (`append`),
  `verify.py` (runnable: `python -m netra.ledger.verify`), `tamper.py` (runnable:
  `python -m netra.ledger.tamper --seq N`), `tests/test_ledger.py` (20 tests).
- shape implemented, exactly as SPEC.md §4 states it: `payload_hash =
  SHA-256(rfc8785(payload))`, `entry_hash = SHA-256(prev_hash ‖ payload_hash)` over the
  RAW 64 bytes (not the hex text), Ed25519 over the 32-byte `entry_hash`. **Note the
  two-step chain:** the brief's shorthand read `SHA-256(prev_hash ‖ rfc8785(payload))`,
  which hashes the payload bytes directly into the chain; SPEC.md chains over
  `payload_hash` instead. SPEC.md wins (rules.md §0) and the test
  `test_entry_hash_matches_the_spec_formula` pins the SPEC form.
- verified: **20 tests pass.** `rfc8785.dumps({"n": 1.0})` was ASSERTED in a test to emit
  `{"n":1}` against `json.dumps`'s `{"n": 1.0}` — the CLAUDE.md warning is now a failing
  test if it ever stops being true. rfc8785 does NOT raise on a float, it silently
  normalises, so `reject_floats` is the guard that actually stops them; it reports the
  path (`payload.sets[1].p`) and lets `bool` through (a subclass of `int` that
  canonicalises to `true`). `MAX_SAFE_INT` boundary tested both sides. Verify
  **re-canonicalises** the stored payload rather than re-hashing the stored text, so
  non-canonical bytes are caught too. Four independent checks per entry: seq contiguity,
  `prev_hash` linkage, payload hash, signature. **The mandatory tamper test passes:**
  three entries appended, the middle one corrupted in place, `verify` returns
  `ok=False, first_bad_index=2` with `checked=1`. Three further tamper shapes are
  pinned: a DELETED entry (caught as a seq gap, reported at index 3), a RE-SIGNED entry
  where the attacker recomputed both hashes (caught because the signature is not the
  registered device's), and an unknown `signer_kid` (reported as such rather than as a
  signature mismatch — `known_public_hex` deliberately does not GENERATE a key for an
  unseen kid). Driven end-to-end outside pytest on a scratch DB: append 3 → `verify`
  prints `ok: 3 entries verified` exit 0 → `tamper --seq 2` → `verify` prints
  `FAILED at index 2: payload_hash does not match the stored payload` exit 1. The tamper
  demo **reinstalls the trigger it drops**, asserted by a test.
- unverified / TBD: **the server signs on the device's behalf.** The private keys live in
  `keys/` on the server, so a signature attests "this server recorded this entry under
  this kid", NOT "this device authored it". True per-device signing needs the device to
  send a signature, and the frozen request body has no field for one — raise it if the
  end-to-end claim matters for the demo. Key ROTATION is unexercised: `signer_kid` is
  stored and resolved per entry, so an old entry stays verifiable after a new key is
  issued, but no rotation has been performed. `KeyStore` CREATES a key on first use so a
  fresh box produces a verifiable chain; that also means a lost `keys/` directory makes
  every existing entry unverifiable. The tamper demo is **not reachable from the API**
  and never will be — the nine endpoints are frozen and a "corrupt the ledger" route in a
  deployed build is a liability; T-17 drives it as a CLI beside the Ledger view.

### 2026-10-28 — Lane A — T-04 POST /v1/encounters, idempotency, and CORS
- what changed: `netra/api/main.py` (app factory, `lifespan=`, CORS),
  `netra/api/deps.py`, `netra/api/schemas.py`, `netra/api/clinical.py`,
  `netra/api/config.py`, `netra/api/idempotency.py`,
  `netra/api/routes/encounters.py`, `tests/test_encounters.py` (24 tests).
- verified: **60 tests pass.** The encounter row and its ledger entry are written in ONE
  transaction and committed together, so a response can never name a ledger entry that
  does not exist — asserted by fetching the returned `ledger_idx` and by asserting that
  a 422 leaves **zero** encounters AND zero ledger entries. A rejected image records
  with `dr_grade=None`, `prediction_set=None` and `abstained=False` (not an abstention —
  nothing was graded); a reject carrying a prediction set is a 422. Abstention matches
  Lane B's `clinical.ts` in both directions: `{0,3}` abstains, `{0,1}` does not, `{3}`
  records grade 3. A test walks the stored payload and asserts **no float anywhere**.
  Idempotency: a retry replays the stored response and creates nothing new (1 encounter,
  1 ledger entry after two POSTs); an in-flight key is **409**; a key reused with a
  different body is **422**, and 422 wins over 409 when both apply; a failed request
  releases its claim so a retry can proceed. Handlers are sync `def` — enforced at app
  construction, not just asserted in a test.
  **Driven against a real uvicorn on :8077, not only TestClient:** the cross-origin
  preflight from `http://localhost:5173` returns `access-control-allow-origin`,
  `allow-methods: GET, POST, PATCH, OPTIONS` and `allow-headers: … Idempotency-Key,
  X-Device-Kid`; a disallowed origin gets no allow-origin header; two POSTs with one key
  produced one encounter with `idempotency-replayed: true` on the second; the stored
  payload came back key-sorted with `"prediction_set":[0,3]` and `"abstained":true`; and
  `python -m netra.ledger.verify` reported `ok: 1 entries verified`.
- what changed (decisions worth knowing):
  1. **`FastAPI 0.162.0` does not flatten `include_router` into `app.routes`** — it
     appends one `fastapi.routing._IncludedRouter` whose real routes hang off
     `.original_router`. A naive `app.routes` scan finds only `/docs` and `/openapi.json`
     and silently checks nothing; `contract_routes()` walks the nesting. This was caught
     because the sync-handler test asserted it had found at least one route.
  2. **`device_kid` travels as an optional `X-Device-Kid` header**, never in the body:
     SPEC.md's frozen body names no device field. It defaults to the site's registered
     device, and registers `device-1` on first sight.
  3. **Thresholds are read from `config/thresholds.yaml` by a ~40-line stdlib parser**
     (`netra/api/config.py`), NOT PyYAML: pyyaml is unpinned (transitive via timm) and
     rules.md §1 allows only what is pinned. The parser raises on any syntax it does not
     recognise rather than guessing, and the file resolves from the repo root so the
     answer does not depend on uvicorn's CWD. If `thresholds.yaml` ever grows block
     lists or anchors, pin PyYAML by agreement and delete the module.
- unverified / TBD: **no authentication anywhere.** Any caller can name an
  `X-Device-Kid` and the server will register it; there is no enrolment authority. The
  stale-claim reclaim (`IN_FLIGHT_TTL_SECONDS = 60`) is **untested against a real
  crash** — only the fresh-claim 409 path is covered. Concurrency is untested: SQLite
  has one writer, and the 409 path is exercised by inserting the in-flight row directly
  rather than by two simultaneous requests. `GET /v1/queue/depth` is not built yet, so
  `idempotency.depth()` is written but unexercised.

### 2026-10-28 — Lane A — T-05 referrals and the state machine
- what changed: `netra/api/referral_state.py` (the machine as a TABLE, not branching),
  `netra/api/routes/referrals.py`, `tests/test_referrals.py` (25 tests).
- verified: **85 tests pass.** The machine is driven from BOTH sides. Legal: the full
  `issued → contact_attempted → contacted → appointment_offered → examined` path walks;
  `contact_attempted` repeats and `attempt_n` counts 1, 2, 3 from the stored events
  rather than from a client-supplied number; `abandoned` is reachable from all four
  non-terminal states, each verified by replaying the prelude. Illegal: skipping a step
  is **409** ("cannot go from 'issued' to 'examined'"), a terminal state accepts nothing
  further (**409**, both `examined` and `abandoned`), `contact_attempted` without a
  channel and `abandoned` without a reason are **422**, an unknown state is refused by
  the frozen `Literal` before the handler sees it, and an unknown referral is 404.
  **Every transition appends a ledger entry** — asserted by reading the payloads back
  and checking the `from_state`/`to_state` sequence, with distinct increasing
  `ledger_idx` values, and `verify` still `ok:true`. A REFUSED transition changes
  nothing: state unchanged, no new ledger entry, still one referral event.
  Clinical gates on issuing: **no referral from an abstention** (422; SPEC.md §7 says a
  clinician decides), none from a rejected image, none for grade 1 (`refer_grades` is
  [2,3,4] read from `config/thresholds.yaml`), 404 for an unknown encounter, 409 for a
  second referral on one encounter, and a failed issue writes neither a referral nor a
  ledger entry. `ruff` clean.
- decisions: **409 vs 422 split.** A structurally impossible move is 409 (the resource
  is not in a state where it makes sense); a permitted move with missing data is 422
  (the request is wrong). SPEC.md fixes neither, so this is a choice — it is consistent
  with the idempotency statuses SPEC.md *does* fix, and `referral_state.check` raises two
  different exception classes so the mapping lives in one place.
  The transition table is **data**, so a new state cannot be slipped in by an `if` in a
  handler; a test asserts the state set is exactly the six frozen names.
- unverified / TBD: `PATCH` honours `Idempotency-Key` (a retry replays, asserted) but
  Lane B's client does NOT send one for `patchReferral` or `createReferral` — only for
  `createEncounter`. So a retried transition from the UI will be applied twice if it is
  a repeatable one (`contact_attempted` would increment `attempt_n` again). Worth a Lane
  B line, but it needs no contract change: the header is already accepted.
  Nothing enforces WHO may advance a referral — there is no auth, so any caller can
  move any referral to `examined`.

### 2026-10-28 — Lane A — T-06 ledger verify and checkpoint endpoints
- what changed: `netra/ledger/checkpoint.py`, `netra/api/routes/ledger.py`,
  `tests/test_ledger_api.py` (15 tests).
- verified: **100 tests pass.** `GET /v1/ledger/verify` is driven against a CORRUPTED
  chain through the HTTP surface, not only a clean one: three encounters posted, entry 2
  corrupted, endpoint returns exactly `{"ok": false, "first_bad_index": 2}`. A deleted
  entry is reported too (as index 3, where 2 should have been). The response carries
  **exactly the two frozen fields** — the internal `reason` string is asserted NOT to
  leak. `GET /v1/ledger/checkpoint` returns exactly the frozen five
  (`idx, head_hash, ts, signature, signer_kid`), attests the real current head
  (`idx == head.seq`, `head_hash == head.entry_hash`), and **its signature verifies from
  the response alone** — the test reconstructs the signed bytes from the JSON the way an
  external holder would. Claiming `idx + 1` over the same signature fails, which is the
  rewrite a checkpoint exists to catch. Reading twice at an unchanged head returns the
  identical checkpoint (re-signing would need an UPDATE the append-only trigger refuses,
  also asserted); the checkpoint moves when the head moves. An empty chain gives
  `idx: 0` with the genesis hash.
  The headline test is `test_an_old_checkpoint_still_proves_a_rewrite`: entry 3 is
  rewritten, re-chained AND re-signed with the real device key, so `verify` returns
  **ok:true again** — the attack a bare chain cannot catch — and the previously issued
  checkpoint is what exposes it, because it attests a head hash the rewritten chain no
  longer has. That is the Certificate-Transparency argument, now a test rather than a
  claim in a slide.
- decisions: a checkpoint is signed **on read**, not on a timer, and by `SERVER_KID`
  (`server-1`) rather than a device key — a checkpoint attests a server-side fact about
  the chain head, so it is deliberately NOT a `devices` row; verification resolves its
  public key from `keys/server-1.pub`. **No endpoint corrupts the ledger**, and none will:
  the nine are frozen and a "rewrite history" route in a deployed build is a liability.
  T-17 drives `python -m netra.ledger.tamper --seq N` beside the Ledger view.
- unverified / TBD: nobody external actually HOLDS a checkpoint yet — the proof only
  works if a checkpoint is exported and kept off-box, which is a demo-script step, not
  code. No Merkle tree, by SPEC.md §4's explicit instruction. Checkpoint rows accumulate
  one per distinct head that is read; nothing prunes them.

### 2026-10-28 — Lane A — T-07 site status, audit, per-site metrics, queue depth; and the Lane B glue
- what changed: `netra/api/routes/sites.py` (all four endpoints), `tests/test_sites.py`
  (21 tests), `tests/test_integration.py` (11 tests against Lane B's typed client).
- **Lane B's three `TODO(Lane A)` shapes are MATCHED, not approximated.** `types.ts` is
  read-only to this lane and `test_integration.py` parses it and compares field names to
  the live responses, so the two sides cannot drift silently:
  1. `GET /v1/sites/{id}/status` returns `gradability` as **`{k, n, ci}`** — counts plus
     a Wilson interval, never a bare rate — exactly as their `RateCounts` and their
     TODO asked.
  2. `GET /v1/queue/depth`'s `attempts` element type is settled as
     **`{key, endpoint, status, created_at}`** (their `unknown[]` can now be typed).
  3. `POST /v1/sites/{id}/audit`'s payload is settled as **`pinned_model_version,
     gradable_k, gradable_n, agreement_k, agreement_n, grade_counts, drift_flag`** — all
     counts, because the payload is appended to the ledger and floats are banned there.
  The other six shapes are pinned the same way, plus three cross-lane checks: Lane B's
  client calls **only** the nine frozen paths, their `ReferralState` union equals the
  server's state set, and their `REFER_GRADES` equals `dr.refer_grades` from
  `config/thresholds.yaml`.
- one place where the shape could NOT be matched exactly, and what was done instead:
  `SiteStatusResponse.model_version` is a **non-nullable** string on Lane B's side, but a
  site that has never passed an audit has no pinned version. Rather than make them
  change the type, status returns the sentinel **`"unpinned"`**, which is the honest
  reading of SPEC.md §6 ("a site must pass a local audit before its grades count"). If
  Lane B would rather have `string | null`, that is a types.ts change and their call.
- verified: **132 tests pass**, `ruff check` and `ruff format --check` clean on every
  Lane A file. Denominators are asserted explicitly because they are the easy thing to
  get quietly wrong: **gradability** is k = admitted / n = all images the gate saw (the
  reject IS in the denominator); **abstention** is k = abstained / n = ADMITTED images
  only (a rejected image was never graded, so it cannot have abstained — putting rejects
  here would let a bad camera look like a confident model). `pooled` is **summed counts,
  not a mean of rates**, and a test states why the two differ at unequal n. An empty site
  still returns a row with n = 0 rather than vanishing. A test asserts **exactly the nine
  frozen endpoints are registered** — no tenth.
  Audit `passed` is COMPUTED, from one documented rule: `gradable_n >= min_n_for_rate AND
  agreement_n >= min_n_for_rate AND not drift_flag`, with `min_n_for_rate` (30) read from
  `config/thresholds.yaml`. A failed audit still gets ledgered but does NOT pin a model
  version (asserted). A numerator above its denominator is a 422.
  **Driven live through all nine endpoints on uvicorn :8078**, not only TestClient: three
  encounters (grade 3 / abstain {0,3} / reject) → referral issued → transitioned
  (`ledger_idx` 5, because the issue was 4) → `verify ok:true` → signed checkpoint at
  idx 5 under `server-1` → status `unpinned` then `convnext_tiny@live` after the audit
  passed → metrics with two site rows and a pooled line → queue depth `synced: 3` with
  three typed attempts. Then the **T-17 tamper demo against the running server**:
  `python -m netra.ledger.tamper --seq 3` and `GET /v1/ledger/verify` immediately
  returned `{"ok":false,"first_bad_index":3}` with no restart — which is the sequence the
  Ledger view needs.
- unverified / TBD: **the audit pass rule contains no accuracy or agreement floor.** It
  says "this site has enough cases to report a rate and no drift flagged", NOT "this site
  is accurate". A real floor on gate-vs-human agreement is **TBD — verify** and needs a
  clinical decision; none was invented. `_latest_audit` scans ledger entries newest-first
  and parses JSON in Python — fine at demo scale, O(n) per request, and it will need an
  index or a projection table if the ledger grows. `drift_flag` is whatever the auditor
  submitted; nothing computes drift. Nothing authenticates an auditor. `grade_counts` is
  stored in the ledger but no endpoint returns it — SPEC.md's status row does not name it.

### 2026-10-28 — Lane B — Idempotency keys on every mutation, and the "unpinned" sentinel
- what changed: `src/lib/api/client.ts` — `createReferral`, `patchReferral` and
  `siteAudit` now send an `Idempotency-Key` header (a fresh `crypto.randomUUID()` per
  call, overridable), matching what `createEncounter` already did. New
  `src/lib/modelVersion.ts` renders Lane A's `"unpinned"` sentinel as the plain phrase
  **"no audited model yet"**, with `isUnpinned()` so screens pick a muted treatment and
  never the error treatment. New `src/lib/api/client.test.ts` (10 tests) and
  `src/lib/modelVersion.test.ts` (7 tests). `vite.config.ts` gained `test.env =
  { VITE_USE_MOCK: "0" }`.
- `siteAudit` was keyed too, beyond the two asked for: a redelivered audit appends a
  SECOND `site_audit` entry to the ledger and moves `last_audit`, which is the identical
  hazard Lane A flagged for referrals. Flagged rather than done silently.
- verified: `npm run build` and `npm test` green — **44 tests, 6 files** (28 before,
  +16). The header assertions are real wire assertions: `fetch` is stubbed and the test
  inspects the request the client actually builds, including method, URL and body. Two
  deliberate `patchReferral` calls are asserted to get **different** keys — two contact
  attempts ARE two events, and reusing a key would make the server replay the first
  response and silently drop the second attempt. An explicit key is asserted to pass
  through, so a genuine retry can reuse one. GET endpoints are asserted to send **no**
  key and no body. A 422 is asserted to surface the server's `detail` string.
- `vite.config.ts` needed `test.env = { VITE_USE_MOCK: "0" }` or the client's USE_MOCK
  branch short-circuits every call and a header assertion **can never fail** — the test
  would have passed while sending nothing. Found by writing the test and watching it
  pass too easily.
- unverified / TBD: the key is fresh per call, so a double-CLICK still produces two
  events; nothing debounces the buttons. TanStack Query mutations default to `retry: 0`,
  so no automatic retry re-runs `mutationFn` with a new key — if a retry policy is ever
  added, the key must be hoisted out of the mutationFn or the protection is lost. No
  screen renders `model_version` yet; the formatter lands with T-16.

### 2026-10-28 — Lane B — Mock switched off; real API is now the default
- what changed: `src/lib/api/client.ts` — `USE_MOCK` inverted from
  `import.meta.env.VITE_USE_MOCK !== "0"` to `=== "1"`. The real API is now the DEFAULT
  and the mock responder is **opt-in**. `.env.example` rewritten to say so; a local
  `netra/ui/.env` sets `VITE_API_BASE=` and `VITE_USE_MOCK=0`.
- why the default moved in CODE rather than in a `.env` file: the repo root
  `.gitignore` line `.env` matches `netra/ui/.env` too (`git check-ignore -v` confirms),
  so a flag written there switches the mock off on **one machine only** and silently
  leaves every other developer and every build on fake data. Inverting the default is
  the only version of "mock off" that is committed.
- verified: `npm run build` and `npm test` green, **44 tests**. With `VITE_API_BASE`
  empty the client requests a relative `/v1/...`, which the Vite dev server proxies to
  `http://127.0.0.1:8000` — confirmed live: `curl http://localhost:5173/v1/queue/depth`
  returned `{"queued":0,"synced":0,"attempts":[]}` from the real uvicorn. Note the proxy
  answers on **localhost:5173 but not 127.0.0.1:5173** — Vite binds localhost only
  without `--host`, which is a five-minute debugging trap worth knowing.
  Because dev goes through the proxy it is **same-origin**, so this path does NOT
  exercise Lane A's CORS; setting `VITE_API_BASE=http://localhost:8000` does, and that
  is what a deployed build will do.
- **BLOCKED — the browser pass cannot run in this session.** The Claude-in-Chrome
  extension is not connected (`list_connected_browsers` returns `[]`), so no view can be
  rendered, screenshotted, tab-walked or contrast-checked in situ. Recorded rather than
  worked around; substituted with (a) logic tests, and (b) grepping the BUILT CSS for
  every token class a new component uses, because Tailwind drops unknown classes
  silently — the check that caught a 1:1-contrast invisible button in the last pass.
  A human browser pass at 1280 and 375 is still owed on Sites and Ledger.

### 2026-10-28 — Lane B — T-16 Sites view: per-site forest plot
- what changed: `src/lib/forest.ts` (data shaping) + `forest.test.ts` (12 tests),
  `src/components/ForestPlot.tsx` (Recharts ScatterChart + ErrorBar + ReferenceLine) +
  `ForestPlot.ssr.test.ts` (8 tests), `src/routes/Sites.tsx` (was a stub).
  `queries.ts` gained `refetchInterval` on `useSiteStatus`. `mock.ts` now returns
  `model_version: "unpinned"` and `last_audit: null` for **site-11**, and
  `drift_flag: true` for site-07, so both branches are visible against the mock.
- design decisions, each traceable to a rule rather than taste:
  - **Two panels, not one chart with two series.** Gradability gets the pooled dashed
    reference line because Lane A sends pooled counts for it. Abstention gets **none**,
    and the screen says why on the card: averaging the per-site abstention rates would
    be exactly the mean SPEC.md forbids. Inventing that line was the easy wrong move.
  - **Ordered by n, not by rate.** Ranking sites by a proportion invites reading the top
    row as "the worst site" when the gap is sampling noise. Small-n sites sort last and
    are marked `n<30`.
  - **Denominators are stated in prose on each card** — gradability counts rejects in
    the denominator; abstention counts admitted images only, because a rejected image
    was never graded. These are the two numbers easiest to misread.
  - A site with **n = 0 is not plotted at zero**; it stays in the counts table and a
    line below the table names it. Plotting it would put a fake 0% on the chart.
- verified: `npm run build` and `npm test` green — **64 tests, 8 files** (44 before).
  The error-bar offsets are asserted to **reconstruct the server's interval exactly**
  (`est - lowOffset == ci[0]`), and negative offsets are clamped so an inconsistent
  server interval cannot render as a backwards spike. `pooledEstimate` is asserted to be
  summed counts (258/348 = 0.7414) and **not** the mean of the per-site rates (0.7727) —
  the two differ, which is the point. Every point label goes through `formatRate`, and
  `ForestTooltip` is server-rendered and asserted to print "140/203 (0.62-0.75)" at
  n≥30, "22 of 27" plus "n below 30" below it, and **no "%" at either n**. Drift is
  named in words ("drift flagged"), not carried by colour alone.
  Built-CSS check (Tailwind drops unknown classes silently): `border-l-reject`,
  `text-borderline`, `animate-spin`, `.tabular`, `decoration-border-subtle`,
  `focus-visible:ring-offset-surface`, `sm:grid-cols-2` and `xl:grid-cols-2` all emit
  real rules, and the `@media(min-width:1280px)` block is present.
- a test that looked strong and tested nothing, now fixed: under SSR Recharts'
  `ResponsiveContainer` measures zero width and renders an **empty** container, so the
  plot body is absent from the markup. "No % in the chart markup" therefore passed
  while asserting nothing — and worse, it initially FAILED by matching
  ResponsiveContainer's own `width:100%` inline style. The figures-to-text assertion was
  moved to `ForestTooltip`, which does render, and the SSR limitation is written into
  the test file so no one re-adds the vacuous version.
- unverified / TBD: **no screen was rendered in a browser** — the Chrome extension is
  not connected this session, so layout, the plot's visual correctness, focus order and
  in-situ contrast on this view are all still owed. SSR proves only that it does not
  throw. Recharts took the bundle from **369 kB to 776 kB** (gzip 118 → 231 kB), over
  Vite's 500 kB warning; acceptable for a pinned-stack demo but it is the obvious
  code-splitting target if the camp tablet's first load matters.
  `TODO(review)` in `src/lib/forest.ts`: a plotted marker is a visual proportion even at
  n<30. design.md §7 forbids a bare PERCENTAGE, and a point shown with its wide Wilson
  interval is the honest alternative that rule prefers, so small-n sites are plotted,
  flagged and labelled "k of n" — but if the team wants them suppressed entirely from
  the plot, that is a one-line change in `toForestPoints`.

### 2026-10-28 — Lane B — T-17 Ledger view: verify, checkpoint, and the tamper demo
- what changed: `src/lib/ledgerState.ts` (verify result → display state, as a pure
  function) + `ledgerState.test.ts` (16 tests), `src/routes/Ledger.tsx` (was a stub).
  `queries.ts`: `useLedgerVerify({enabled, pollMs})` with `staleTime: 0, gcTime: 0`, and
  `useCheckpoint` now polls.
- how the demo is carried, given there is **no corrupt endpoint**: a prominent "Verify
  the chain" button, a **"Re-check every 3s" toggle** so the flip happens on screen
  while the presenter runs `python -m netra.ledger.tamper --seq 2`, and a **session
  history list** so `ok:true → ok:false` is visible as a TRANSITION rather than as a
  value that might always have been false. The screen also prints the raw
  `first_bad_index = N` and the literal `ok: false · first_bad_index: N` on a badge, so
  what is on stage matches what the endpoint returned. A card states plainly that no
  endpoint corrupts the ledger and why, and gives the exact CLI.
- verified: `npm run build` and `npm test` green — **80 tests, 9 files** (64 before).
  The ok:false path is tested at least as hard as ok:true: `first_bad_index` reaches the
  headline (asserted for 2 and for 7), **index 0 is treated as a real index** (a falsy
  check there would silently downgrade a real detection), and `ok:false` with a null
  index is its own `failed-without-index` state rather than being read as fine. A
  **failed request is NOT dressed as tampering** — different state, different status,
  `isAlarming` false — and its explainer is asserted to contain "not the same as a clean
  result". A refetch over a stale `ok:true` renders as "checking", so during the demo a
  stale pass cannot linger looking current. The ok explainer is asserted NOT to contain
  "secure" or "guarantee": it says what was recomputed, and claims nothing more.
  Built-CSS check: `border-l-usable`, `border-l-reject`, `border-l-border-subtle`,
  `text-usable`, `accent-text`, `break-all`, `sm:col-span-2`, `lg:grid-cols-2` and
  Capture's arbitrary `lg:grid-cols-[minmax(...)]` all emit real rules.
- note on an earlier greps-lie moment: `grep` for escaped-colon Tailwind selectors from
  bash reported `lg:grid-cols-2` MISSING twice because of backslash handling in the
  shell, not because the class was absent. Verified with a Python `str.find` instead —
  all present. Worth knowing before someone "fixes" a class that was never broken.
- unverified / TBD: **not rendered in a browser** (extension not connected this
  session), so the alarm state's visual weight, the checkbox's focus ring and layout at
  phone width are unconfirmed. The checkpoint's signature is **displayed, not verified**
  client-side — the UI shows what the server signed and does not re-check it, so the
  "an outside party can prove a rewrite" claim is made in prose on the card and is not
  something this screen demonstrates. Verifying it in the browser would need the Ed25519
  public key and WebCrypto, and is not in the frozen contract.

### 2026-10-28 — Lane B — Real-API smoke: the typed client against live Lane A
- what changed: `src/lib/api/live.test.ts` — 10 integration tests that drive the REAL
  typed client against a running Lane A API. **Skipped unless `NETRA_LIVE=1`**, so
  `npm test` never depends on a server (verified: a normal run reports
  `9 passed | 1 skipped`, `80 passed | 10 skipped`). Run with
  `NETRA_LIVE=1 VITE_API_BASE=http://127.0.0.1:8000 npx vitest run src/lib/api/live.test.ts`.
- verified: **10/10 pass against live uvicorn on :8000**, with `VITE_API_BASE` set so
  the requests are **cross-origin** and therefore actually exercise Lane A's CORS rather
  than the same-origin Vite proxy. Confirmed through the client, not curl:
  `POST /v1/encounters` returns `encounter_id` + a numeric `ledger_idx` with exactly the
  two frozen fields; a **retry with the same Idempotency-Key returns the identical
  response** (server-side dedup, so the header added earlier today demonstrably works
  over the wire); a reject carrying a prediction set is **422**; a grade-4 encounter
  issues a referral and advances `issued → contact_attempted`; an abstention `{0,3}`
  **cannot be referred** (422); `verify` returns `{ok:true, first_bad_index:null}`;
  `checkpoint` returns the frozen five with a 64-hex head hash and 128-hex signature;
  `metrics/sites` and `sites/{id}/status` send `{k,n,ci}` with `ci[0] <= ci[1]` and no
  bare rate; `queue/depth` sends `{key,endpoint,status,created_at}` attempts.
  This is what the mock cannot prove: a green mock suite only shows the mock agrees
  with itself.
- **the T-17 tamper transition was driven end to end through Lane B's client.** Before:
  the client's `verifyLedger()` returned ok:true. Then Lane A's CLI was run against the
  same database — `python -m netra.ledger.tamper --seq 2` — and with **no server restart**
  the client observed `{"ok":false,"first_bad_index":2}`. `ledgerState.verifyDisplay`
  maps exactly that to `{kind:"tampered", firstBadIndex:2}` → headline "Tampering
  detected at entry 2", which is unit-tested. So every link in the demo is verified
  except the pixels. No Lane A file was written; the CLI was only invoked.
- unverified / TBD: the live tests **mutate the ledger they run against** (append-only,
  by design) so they are not idempotent across runs in the "verify is ok:true" sense —
  run them against a scratch DB, not a demo DB you care about. They need `site-07`
  seeded; there is no endpoint to create a site, so seeding stays a Lane A step.

### 2026-10-28 — Lane B — CORRECTION: commit 4594b34 was committed RED
- what happened: `src/lib/api/live.test.ts` read its flag from `process.env`, but
  `tsconfig.app.json` sets `types: ["vite/client"]`, so `process` is not declared and
  **`npm run build` failed with two TS2591 errors**. I ran `npm test` (green) before
  committing and did NOT run `npm run build`, so 4594b34 broke the "both gates green"
  rule. Caught on the next build, one commit later.
- the fix: read `import.meta.env.VITE_NETRA_LIVE` instead, so the flag goes through the
  same mechanism as every other env var the client reads and needs no tsconfig change
  or new dependency. The flag is therefore **`VITE_NETRA_LIVE=1`**, not `NETRA_LIVE=1`.
- re-verified after the rename: `npm run build` clean, `npm test` 92 passed / 10 skipped,
  and the live suite **10/10 against a freshly seeded database**. It is not vacuous:
  pointed at the database still tampered from the T-17 demo it correctly reported
  1 failure — "GET /v1/ledger/verify reports an intact chain" — which is the assertion
  doing its job. The test file now says to run it against a scratch DB and explains that
  failure mode, so nobody files it as flaky.
- lesson recorded rather than quietly fixed: a test-only file can break the BUILD,
  because `tsc -b` type-checks `src/**` including tests. `npm test` passing says nothing
  about `npm run build`. Both gates, every commit.

### 2026-10-28 — Lane B — Referrals view wired to the state machine (stretch item 6)
- what changed: `src/lib/referralMachine.ts` (the frozen machine as a table) +
  `referralMachine.test.ts` (14 tests), `src/routes/Referrals.tsx` (was the last stub),
  `src/state/encounter.tsx` gained `referralState`, and `Grade.tsx` now stores
  `res.state` alongside `res.referral_id` when it issues one.
- the honest limitation, stated ON SCREEN rather than hidden: **there is no list
  endpoint** in the frozen nine, so this view can only show the referral raised in THIS
  session, tracked from the create and patch RESPONSES. The empty state says so and
  points at the ledger as the durable record. No new endpoint was invented, and none is
  needed.
- verified: `npm run build` and `npm test` green — **92 passed / 10 skipped, 11 files**
  (80 before, +12). The machine is asserted against the contract in both directions:
  exactly the forward move plus `abandoned` from each live state; `contact_attempted`
  appears as a target of ITSELF (repeatable); terminal states offer nothing; **no skip**
  is ever offered (`issued` never reaches `contacted` or `examined`); and every offered
  target is one of the frozen six. `canSubmit` gates on the required field —
  `contact_attempted` needs a channel (whitespace does not count), `abandoned` needs a
  reason — and a move the machine forbids can never submit however well filled in.
  `abandoned` is asserted to sit **off** the happy path (`pathIndex` null) so it is never
  rendered as "step 5 of 5", which would read as a successful outcome.
  Built-CSS check: `border-l-text`, `border-l-usable`, `text-usable`, `opacity-60`,
  `max-w-sm`, `border-dashed` all emit.
- `TODO(review)` in `src/lib/referralMachine.ts`: it mirrors
  `netra/api/referral_state.py`. The SERVER is authoritative and 409s an illegal move
  regardless; duplicating the table client-side only stops the UI offering a button that
  is guaranteed to fail. If the two disagree, the server wins and the client file is the
  bug — `live.test.ts` walks the real machine, which is what would catch the drift.
- unverified / TBD: not rendered in a browser. The progress list is a flex-wrapped
  `<ol>` with five items, which is the most likely thing to look wrong at 375px, and it
  has not been seen. Advancing a referral needs the case still in memory — a page reload
  clears it and the view returns to its empty state, which is correct given there is no
  GET for a referral but will surprise anyone who reloads mid-demo.

### 2026-10-28 — Lane B — Empty and error states (stretch item 7)
- what changed: `src/routes/Sites.tsx` gained an explicit **zero-sites** state. Without
  it a fresh server renders two empty plots plus a table whose only row is
  "Pooled — no data", which reads as broken rather than as empty. It also says that no
  endpoint creates a site, so registering one is a server-side step.
- audited rather than assumed: Capture, Grade and Referrals already had `role="alert"`
  error blocks with a `<StatusBadge status="error">`; Sites and Ledger have
  loading/error/empty paths from their own tasks; `<TopNav/>` already treats an offline
  queue as `pending-sync`, never as an error. No further gaps found, so nothing was
  padded.
- verified: `npm run build` and `npm test` green — 92 passed / 10 skipped.

### 2026-10-28 — Lane B — Unattended run summary
Backlog worked top to bottom. Both gates (`npm run build`, `npm test`) green at every
commit except one, which is recorded and fixed below.

**Commits, in order (all Lane B, `netra/ui` only, no attribution footer):**
1. `98b0c14` — Idempotency-Key on every mutation; the "unpinned" sentinel rendered plainly.
2. `d3313e8` — default to the real API; the mock responder becomes opt-in.
3. `bd6f2e1` — **T-16** Sites view, per-site Wilson forest plot.
4. `7b8d595` — **T-17** Ledger view: verify, checkpoint, tamper demo.
5. `4594b34` — live integration tests for the typed client against the real API.
   **This one was committed RED** (see 8443b4f).
6. `8443b4f` — fix the build that 4594b34 broke.
7. `88180f8` — Referrals view driven by the frozen state machine (stretch 6).
8. `0f4ccd9` — explicit zero-sites state (stretch 7).

**Tests:** 28 → **92 passing, 10 skipped** across 11 files. The 10 skipped are the live
suite, which needs `VITE_NETRA_LIVE=1` and a running API.

**The one red commit, stated plainly:** `4594b34` passed `npm test` but failed
`npm run build` — `live.test.ts` used `process.env` and `tsconfig.app.json` declares
only `vite/client` types, so `tsc -b` raised TS2591 twice. I had not run the build
before committing. Fixed one commit later in `8443b4f` by reading
`import.meta.env.VITE_NETRA_LIVE`. The lesson is general: `tsc -b` type-checks tests, so
a test-only file can break the build, and `npm test` green says nothing about it.

**`TODO(review)` markers left in the code (2):**
- `src/lib/forest.ts` — a plotted marker is a visual proportion even at n<30. design.md
  §7 forbids a bare PERCENTAGE; a point with its wide Wilson interval is the honest
  alternative, so small-n sites are plotted, flagged and labelled "k of n". One line in
  `toForestPoints` suppresses them entirely if the team prefers that.
- `src/lib/referralMachine.ts` — it mirrors `netra/api/referral_state.py`. The server is
  authoritative; the client copy only avoids offering buttons guaranteed to 409. If they
  disagree, the server wins and the client is the bug.

**Skipped, with reasons:**
- **Backlog item 4, the browser pass — BLOCKED, not done.** The Claude-in-Chrome
  extension is not connected (`list_connected_browsers` → `[]`), so nothing was
  rendered, screenshotted, tab-walked or contrast-measured in situ, at either 1280 or
  375. **No screenshots exist.** Substituted with: SSR of `ForestPlot`/`ForestTooltip`
  via `react-dom/server` (already a dependency — no DOM library added), and a built-CSS
  check that every token class used actually emits a rule, since Tailwind drops unknown
  classes silently. That combination catches crashes and missing styles; it cannot catch
  layout, overflow, focus order or contrast. **A human browser pass is still owed on
  Sites, Ledger and Referrals.**
- **Backlog item 5's screenshot** — same cause. The rest of item 5 was done more
  thoroughly than asked: see the real-API entry above, 10/10 live tests cross-origin,
  plus the tamper transition observed through the client as
  `{"ok":false,"first_bad_index":2}`.
- **Stretch item 8** — already satisfied by work done in items 2 and 3 rather than
  skipped: `forest.test.ts` (12 cases) covers Sites rate formatting including the n<30
  boundary and the pooled-is-not-a-mean property; `ledgerState.test.ts` (16) and
  `ForestPlot.ssr.test.ts` (8) cover Ledger state rendering and figures-to-text. No
  filler tests were added on top.

**Final `VITE_USE_MOCK` state:** the committed default in `src/lib/api/client.ts` is
**the real API** — the mock is opt-in via `VITE_USE_MOCK=1`. The local, gitignored
`netra/ui/.env` is set to **`VITE_USE_MOCK=0`** with `VITE_API_BASE=` empty, i.e. the
real API through the Vite dev proxy, matching the committed default. Anyone running
`npm run dev` needs uvicorn on :8000, or must set `VITE_USE_MOCK=1`.

**Servers:** both stopped (uvicorn :8000 and Vite :5173; no listeners remain). Nothing
deployed, nothing pushed.

### 2026-10-28 — Lane B — Browser pass attempted and BLOCKED; static checks instead
- **The browser pass did NOT happen. There are no screenshots.** Sites, Ledger and
  Referrals have still never been rendered. The Chrome extension reported "not
  connected" and `list_connected_browsers` returned `[]`; the cause was concrete —
  `Get-Process chrome` returned **0 processes**, so Chrome was not running for the
  extension to attach to. Raised with the team, who chose static checks only for this
  session. Everything in the brief that needs a viewport is therefore still owed:
  horizontal scroll at 1280/375, focus rings in situ, the forest plot actually
  rendering, intervals bracketing their markers visually, the counts table scrolling,
  the progress `<ol>` wrapping at 375px, and the Ledger alarm state's visual weight.
- what changed instead:
  1. `src/lib/api/mock.ts` — `verifyLedger` now honours **`?tamper=2`** and returns
     `{ok:false, first_bad_index:2}`. The mock has no ledger to corrupt, and against the
     real API that state comes from the tamper CLI, so this exists purely to make the
     Ledger view's ok:false state reviewable with no backend. It lives ONLY inside the
     mock responder, which is itself opt-in via `VITE_USE_MOCK=1`, so it cannot affect a
     build talking to the real API — and it is **not an endpoint**.
     `src/lib/api/mockTamper.test.ts` (4 tests) pins the parse: `?tamper=0` is a REAL
     index, and `?tamper=` / `abc` / `-1` / `1.5` are rubbish → null. The first draft
     returned **0 for a bare `?tamper=`** because `Number("")` is 0, which would have
     rendered "Tampering detected at entry 0" — a fabricated finding. Caught by the test.
  2. `src/contrast.test.ts` (16 tests) — the WCAG arithmetic the last browser pass did
     BY HAND is now a regression guard, parsed from `index.css` itself. Measured, all
     clearing AA 4.5:1 on both surfaces: `--text` 17.74/16.37, `--text-muted` 7.56/6.98,
     `--usable` 5.02/4.63, `--borderline` 5.24/4.84, `--reject` 6.57/6.07, `--abstain`
     6.46/5.97 (--bg / --surface). It also pins the specific regression — the old
     `#9A6700` is asserted to FAIL on `--surface` (4.49) while the current `#926300`
     passes — asserts `text-border-subtle` appears nowhere in non-test source (it
     measures 1.47:1 and index.css calls it decorative), and asserts the dark block does
     **not** redefine the status hues, so dark mode's known sub-AA gap cannot be shipped
     by accident.
  3. `src/routes/Sites.tsx` — the forest plot's x-axis label was
     `"proportion admitted (0–1), with 95% Wilson interval"`, roughly 290px of 13px text
     inside a plot area that is only about 233px wide at 375px once the 78px y-axis and
     gutters are taken off. Shortened to `"proportion (0–1)"`, and the pooled
     `ReferenceLine` label from `"pooled 305/412 (0.70-0.78)"` to just `"pooled"`; the
     counts moved into the card's footer prose, which wraps, and the exact figures were
     already in the counts table. **This fix is INFERRED from arithmetic, not observed** —
     it removes a likely clip but has not been seen to.
- **two things that would have been caught only in a browser, and still would be:**
  the contrast test proves a colour PAIR is legible, not that the right colour reached
  the right element — the invisible-button bug in the last pass was `cn()` merging
  `--text` onto `--text`, which this cannot see; and nothing here renders a chart, so
  Recharts could still draw nothing and every gate would stay green.
- verified: `npm run build` clean, `npm test` **112 passed / 10 skipped, 13 files**
  (96 before). `VITE_USE_MOCK` restored to **0** in the gitignored `netra/ui/.env`,
  matching the committed default; the dev server and the API are both stopped (no
  listeners on 5173 or 8000).
- a repeat of the lesson from 8443b4f, caught pre-commit this time: `contrast.test.ts`
  first used `node:fs` + `__dirname` and broke `npm run build` with TS2307/TS2304,
  because `tsconfig.app.json` sets `types: ["vite/client"]` and `tsc -b` checks tests.
  `import "./index.css?raw"` was tried as the Vite-native fix and returns an **empty
  string** under vitest (the CSS pipeline intercepts it). Resolved with a
  `/// <reference types="node" />` scoped to that one file, rather than adding `"node"`
  to tsconfig — which would let browser code import `node:fs` and still type-check.

### 2026-10-28 — Lane C — Preflight, real APTOS labels, frozen splits
- what changed: `scripts/build_manifest.py`, `scripts/fetch_aptos_images.py`,
  `tests/test_splits.py` (10 tests), and the **frozen splits** in `data/splits/`.
- data acquisition, actual result: `data/` was empty and the `kaggle` python package is
  not installed, but a `kaggle` EXECUTABLE is on PATH (from the system 3.13) and **its
  credentials work**. So this did not fall back to synthetic. `kaggle` is deliberately
  NOT added to `requirements.txt`: it is invoked as a subprocess, never imported, and
  rules.md §1 governs imports.
- **what is real and what is not.** Real: 366 APTOS images with real 5-class labels from
  `mariaherrerot/aptos2019` (`test.csv`, sha256 `ddb19e46…`, 6879 bytes), distribution
  `{0:199, 1:30, 2:87, 3:17, 4:33}`. Frozen splits from it: **train 219 / calib 75 /
  test 72**, seed 20261027, manifest sha256 `3f18c901…`. NOT real: the full APTOS corpus
  (3662 train images) was not downloaded — the mirror is 8.6 GiB, the backbone trains on
  Kaggle, and per-file fetching gets what a CPU box can actually use. EyeQ was not
  obtained at all: its labels reference **EyePACS** images, which the brief forbids
  downloading (~89 GiB), so the quality gate has no real quality-labelled corpus here.
- **APTOS publishes no patient identifier.** It ships `id_code, diagnosis` only, so
  `build_manifest.py` sets `patient_id = image_id` and the patient-level guarantee in
  `.claude/rules/ml.md` is **VACUOUS for this corpus** — `n_patients == n_images` in
  `meta.json` for that reason, not because the splitter failed. If two APTOS rows are
  one patient's two eyes they can land in different folds and nothing here would catch
  it. Recorded loudly because it is invisible in results.
  `TODO(review)`: `make_splits.py`'s docstring and ml.md both claim a source corpus is
  "kept whole inside a single fold", but the code buckets on `patient_id` alone and
  never reads `source`. With one corpus this is moot. It was NOT changed: altering the
  bucketing would re-pick the splits, which rules.md §6 makes a stop-and-ask.
- verified: **142 tests pass** (132 before, +10), ruff clean on `scripts/` and the new
  test. The split invariants are tested rather than asserted in prose: three images per
  patient always land together; splits are disjoint AND cover every input image (nothing
  lost or invented); the hash bucketing is deterministic; **adding 50 new patients moves
  no existing image** (the reason a hash beats a shuffle — a shuffle silently
  recontaminates any threshold already fitted on the old calibration fold); a different
  seed gives a different split (guards a seed that is read but ignored); fractions land
  within 3 points at n=2000; a manifest missing a column is refused. The committed
  splits are also checked directly for disjointness and for a meta that records the seed
  and the manifest hash, with the manifest-hash check skipped where `data/manifest.csv`
  is absent (it is gitignored).
- `fetch_aptos_images.py` **refuses to fetch the test split** — the test split is touched
  once, at the end — and prints the retained fraction, per ml.md. Two real quirks found
  by running it: the CLI mirrors the remote directory under `-p` (payload lands at
  `<out>/test_images/test_images/<id>.png.zip`, not `<out>/<id>.png`) and it zips
  single-file downloads. The first version silently retained 0/4 because of it.

### 2026-10-28 — Lane C — CORRECTION: reverted a cross-lane formatting change
- `ruff format scripts` in the previous commit also reformatted
  **`scripts/gen_device_key.py`**, which is Lane A tooling. The change was pure import
  sorting with no behaviour change, but Lane A's own T-02 entry explicitly recorded
  leaving those three pre-existing ruff findings alone as "not this lane's call to fix".
  Silently overriding that crosses a lane boundary and contradicts a recorded decision,
  so it is reverted to its committed state. Lane C's ruff invocations are now scoped to
  the files this lane owns, not to `scripts/` wholesale.

### 2026-10-28 — Lane C — T-12 unit tests for every metrics.py function
- what changed: `tests/test_metrics.py` rewritten from 2 tests to **38**, covering
  `brier`, `nll`, `calibration_slope_intercept`, `ece`, `fit_temperature`,
  `risk_coverage`, `augrc`, `coverage_at_risk`, `wilson_interval` and
  `abstention_report`. `metrics.py` itself was **not touched** — altering a metric's
  definition is the evaluation-drift failure rules.md §6 makes a stop-and-ask, and
  nothing here needed it.
- the metrics were CHARACTERISED before being asserted, so the expected values are
  measured rather than assumed. Results, all in the textbook direction:
  `calibration_slope_intercept` on calibrated data gives slope **0.971**, intercept
  **0.014**; sharpening the logits ×2 drops the slope to **0.485** (CLAUDE.md:
  slope < 1 means over-confident, the usual direction for a neural network) and
  flattening ×0.5 raises it to **1.940**. `fit_temperature` returns **1.053** on
  already-calibrated logits and recovers **3.159** from 3× logits and **0.351** from
  ⅓× — it inverts the scale it was given. So the hand-rolled intercept is sound and
  there was nothing to flag.
- values asserted exactly, each hand-computed first and then confirmed against the
  implementation: `risk_coverage` on four cases gives coverage `[.25,.5,.75,1]` and risk
  `[0,0,⅓,.5]`; `augrc` = **0.125** on that curve; `coverage_at_risk` at target 0.3 is
  **0.5**; `wilson_interval(24,30)` = **[0.6269395261897256, 0.9049502189759876]** —
  which is byte-for-byte the pair Lane B's `formatRate` test renders as
  "24/30 (0.63-0.90)", so the two lanes are now pinned to the same arithmetic from
  opposite ends.
- the tests assert PROPERTIES where an exact value would be dataset-specific:
  `metrics.py` documents a 7.6% ECE swing from the bin count alone, measured on another
  corpus, so the test asserts only that 15 and 50 bins disagree. `fit_temperature`'s
  documented signature — "ECE falls substantially while Brier barely moves" — is
  asserted directly: ECE at least halves and Brier shifts under 0.10.
- edge cases that would otherwise return something misleading: `wilson_interval(0,0)`
  is `(0,1)` (claims nothing rather than dividing by zero); `abstention_report` with
  nothing admitted returns **NaN** accuracy, not 0.0, because 0.0 reads as "it got
  everything wrong"; `coverage_at_risk` returns 0.0 for an unreachable target, i.e.
  refusing every case, which is the honest answer; `calibration_slope_intercept`
  survives p exactly 0 and 1 (logit(0) is -inf and the eps clip is what saves it);
  coverage + abstention_rate is asserted to sum to 1 across every admit count.
- verified: **178 tests pass** (142 before, +36), ruff clean on this lane's files.

### 2026-10-28 — Lane C — Quality gate (QuickQual), preprocessing, reason codes
- what changed: `netra/models/preprocess.py`, `netra/models/reason_codes.py`,
  `netra/models/thresholds.py`, `netra/models/quality.py`, `tests/test_quality.py`
  (31 tests).
- **the gate refuses rather than guesses.** With no head loaded it returns
  `state="unavailable"`, `verdict=None`, `score_milli=None`,
  `model_version="unloaded"` — and the test asserts explicitly that it does not
  default to `usable`, because "usable" is the one answer that lets an ungradable
  image through into a grade and then a referral. Three ways to end up headless are
  each covered: no pickle at all; an **unloadable** pickle (SPEC.md expects the
  released one may not load under scikit-learn 1.9.1, so the failure is caught and
  reported, not raised); and `NETRA_QUICKQUAL_MEME` set.
- **QuickQual-MEME is NOT implemented.** SPEC.md's Fallback A is 10 parameters printed
  in the paper, and this build does not have that table. Ten invented numbers would be
  a fabricated decision rule that *looks* published, so the code refuses with a message
  naming what is missing. `TODO(review)` in `quality.py`: transcribe and pin them.
- preprocessing is **background removal + resize ONLY**, with the ablation in the
  docstring so nobody re-adds CLAHE: Ben Graham 0.8260 and CLAHE 0.8238 both measured
  BELOW plain crop+resize 0.8310. `CropReport` carries the retained fraction at every
  call, per ml.md. An all-black frame (a lens cap) returns the ORIGINAL with
  `crop_failed=True` rather than a zero-size array that explodes three functions later.
- reason codes are explicitly **not the gate** (SPEC.md §1: no published absolute
  Laplacian threshold for fundus images exists). They pick a retake sentence only. Focus
  and exposure are measured **inside the retina mask**, because the black surround is
  perfectly smooth and perfectly dark — including it makes the measurement a function of
  the camera's aperture rather than of the image, which a test pins. An all-black frame
  reports `fov_mask`, not `focus`: zero variance is true but the actual fault is that
  there is no retina. `TODO(review)`: the four cut-points are uncalibrated and marked as
  such in the module.
- **a new library gotcha, not in CLAUDE.md:** `SVC(probability=True)` is **deprecated in
  scikit-learn 1.9 and removed in 1.11** — it emits a FutureWarning now and would be a
  hard failure on the next bump. Replaced with
  `CalibratedClassifierCV(SVC(), ensemble=False, method="sigmoid")`, which is the same
  Platt scaling SVC ran internally, so the head stays calibrated — which matters because
  the gate thresholds are probability cut-points. Below 4 examples in the smallest class
  there is nothing to cross-validate, so it fits a bare SVC and `_p_usable` squashes
  `decision_function` instead; that path is explicitly NOT calibrated and says so.
- `thresholds.py` reads AND writes `config/thresholds.yaml` inside the same two-level
  subset Lane A's parser accepts, and `write()` re-reads what it wrote and fails rather
  than leaving an unparseable file on disk. `quality_cutoffs()` refuses an unordered
  pair, which would silently collapse the three-way gate into a two-way one.
- verified: **209 tests pass** (178 before, +31), ruff clean. The real densenet121 at
  512px is CPU-smoked with `pretrained=False` (so it never touches the network) and the
  pooled feature vector is asserted to be **2048-d** — 1024 channels of mean
  concatenated with 1024 of std, since QuickQual pools both and std is what carries blur.
  `to_model_tensor` is asserted to produce exactly ±1.0 for white/black at mean/std 0.5.
  The three-way band is parametrised across both inclusive boundaries (0.70 → usable,
  0.69 → borderline, 0.30 → reject). A usable verdict is asserted to carry **no** cause.
- unverified / TBD: features from a random-init backbone are **meaningless**, so no
  number from these smoke tests is a measurement; `model_version` records `random-init`
  so such a run cannot be mistaken for a real one. The gate has **never been fitted on
  real quality labels** — EyeQ was unobtainable (its labels reference EyePACS, which the
  brief forbids downloading), so there is no local quality-labelled corpus at all. The
  published EyeQ figures (0.886 / 0.9687 / 0.811) are the paper's, on EyeQ, and are
  flagged in the module as not ours.

### 2026-10-28 — Lane C — DR classifier, dataset over frozen splits, training loop, Kaggle notebook
- what changed: `netra/eval/metrics.py` gained `quadratic_weighted_kappa`;
  `netra/models/dr.py`, `netra/models/dataset.py`, `netra/models/train.py`,
  `notebooks/train_dr.ipynb` (15 cells), `tests/test_dr.py` (22 tests) and 4 more
  metrics tests.
- **a real defect, found by running the smoke rather than by reasoning.**
  `train.py --smoke` correctly wrote `trained: false` into the checkpoint, but
  `DRClassifier._load` set `self.trained = True` unconditionally — so a **two-step
  artifact loaded and reported `model_version` as a real checkpoint name**. That is
  precisely the fabricated clinical output this lane must not ship. `_load` now honours
  the flag, a bare `state_dict` with no provenance is assumed **untrained** rather than
  assumed good, and three tests pin it. Caught by printing the version string after the
  smoke, which is why the smoke was worth running end to end.
- the classifier refuses rather than guesses: unloaded → `available=False`,
  `model_version="unloaded"`, and `predict`/`predict_proba` **raise `ModelNotLoaded`**.
  There is no code path returning a grade from absent weights. A corrupt or missing
  checkpoint degrades to unloaded with the reason recorded, not an exception at import.
- probabilities leave as **per-mille integers summing to exactly 1000**, because they
  travel into a ledger payload where floats are banned — `rfc8785` emits `{"n":1}` for
  `1.0` while `json.dumps` emits `{"n":1.0}`, which breaks a chain silently. Naive
  rounding does not sum to 1000, so the largest remainder takes the slack; four
  distributions are asserted to sum exactly.
- `dataset.py` reads splits and **never creates them**: no shuffle, no ratio argument,
  no `train_test_split`. `collect("test", ...)` **raises `PermissionError`** unless
  `allow_test=True` is passed explicitly, which neither `train.py` nor the notebook ever
  does — an accidental `split="test"` is the mistake that cannot be undone afterwards.
  Every `collect()` returns the retained fraction, and that report immediately earned
  itself: the first smoke run pointed `--images` at the calib directory and the report
  showed `train: 0/219 present, retained 0.0` instead of silently training on nothing.
- **CPU smoke, actually run:** 2 optimiser steps on 6 real APTOS images at 512px with
  `--random-init`, train_loss 1.947, **3.1 seconds**, checkpoint written and reloaded.
  The real `convnext_tiny` forward pass is asserted to give `(2, 5)` finite logits.
  No full training run happened locally and none should — that is the Kaggle T4 job.
- `notebooks/train_dr.ipynb` carries the five ml.md rules at the top, **re-checks split
  disjointness rather than trusting it**, asserts `retained_fraction > 0.95` before
  training, selects on calibration only, deliberately does NOT collect the test split,
  and draws the 0.95 line on the QWK plot as a leaked-split alarm rather than a target.
  All 15 cells are validated as parseable Python.
- **a claim of mine that was wrong, and is corrected in the code.** I wrote that passing
  `labels=range(5)` to kappa protects against a fold missing a grade "silently computing
  over a smaller matrix". It does not: the quadratic weights are `(i-j)^2/(k-1)^2`, so
  widening the label set scales every weight by one constant which cancels in
  `1 - sum(wO)/sum(wE)`. Measured both ways on a fold missing grades 3 and 4:
  **0.8571428571428572 either way**. The docstring now says so, and the test asserts the
  invariance plus the fact that a single-grade fold returns **nan** with or without the
  argument — so callers must check for nan rather than trust the parameter.
- verified: **236 tests pass** (209 before, +27), ruff clean on this lane's files.

### 2026-10-28 — Lane C — Conformal abstention (MAPIE), and two corrections to CLAUDE.md
- what changed: `netra/models/abstain.py`, `tests/test_abstain.py` (30 tests).
- **two things CLAUDE.md gets wrong about MAPIE 1.6.0, both verified against the
  installed version and now pinned by tests:**
  1. CLAUDE.md says `fit -> conformalize -> predict_set`. With `prefit=True`, calling
     `fit()` **raises**: *"The fit method must be skipped when the prefit parameter is
     set to True. Use the conformalize method directly after instanciation."* The correct
     flow is **`conformalize -> predict_set`**. A test calls `fit()` deliberately and
     asserts the raise, so nobody "fixes" the wrapper by adding the call CLAUDE.md implies.
  2. `predict_set` returns a **tuple** `(point_predictions, sets)`, not a bare array.
     CLAUDE.md's "3-D `(n, n_classes, n_levels)` bool array" describes the SECOND element;
     the first is a 1-D array of argmax labels. Asserted as `(10,)` and `(10, 5, 1)`
     with `dtype == bool`. Both are CLAUDE.md edits for the team — it is a root doc.
- the abstention rule is SPEC.md §3's, and **size is not the criterion**. Parametrised in
  both directions: `{0,1}` size 2 → no abstention; `{0,3}` size 2 → abstain; `{2,3,4}`
  size 3 → **no** abstention (entirely refer, so a clear action), though `grade` stays
  None since it names no single severity, matching Lane B's `singleGrade`. An **empty**
  set abstains and is explicitly NOT read as grade 0 — that would turn "we do not know"
  into "no retinopathy".
- **the three lanes are pinned against each other.** One test imports Lane A's
  `spans_clinical_actions` and asserts agreement across seven sets; another parses Lane
  B's `clinical.ts` and asserts its `REFER_GRADES` equals `dr.refer_grades`. A drift
  between any two is a clinical bug no single-lane test would catch.
- verified: **266 tests pass**, ruff and ruff-format clean (see the correction below).
  The conformal guarantee is measured, not assumed: empirical coverage **0.90 ± 0.06**
  on 600 held-out exchangeable cases at `confidence_level=0.90`, and 0.80 gives mean set
  sizes no larger than 0.95. `coverage_report` routes through
  `metrics.abstention_report`, so the coverage cost always travels with the accuracy.
- unverified / TBD: all of this ran on **synthetic probabilities** whose labels were
  drawn from them — the only way to make coverage meaningful with no trained model.
  Nothing has been conformalised on real DR probabilities; that is the Kaggle step, and
  `notebooks/train_dr.ipynb` §6 refuses weights not marked `trained`.

### 2026-10-28 — Lane C — CORRECTION: commit ed2ed99 was mis-verified
- **`ed2ed99` landed with a ruff error and a commit message I had not verified.** It
  carried `C401` in `abstain.py`, its message claimed "pytest -q: 266 passed" at a point
  where pytest had **not run**, and the memory entry above was **never appended** — the
  commit contains only the two source files.
- cause: I chained lint, format, test, the memory append, `git add` and `git commit`
  into one `cmd1; cmd2; cmd3 && cmd4 && ...` line. The `&&` guard did not hold the way I
  read it, so the later steps ran without the earlier ones having passed, and the
  interleaved output made it look as though they had. Tests were in fact green at that
  tree, but I had not seen them be green.
- fixed here: `C401` resolved (`set(...)` → a set comprehension), ruff and ruff-format
  clean, **266 passed confirmed by running pytest on its own**, and the missing entry
  appended above.
- lesson: do not chain a verification gate and a commit in one shell line. Run the gates
  as their own commands, read the output, then commit. A commit message is a claim, and
  an unverified claim in the history is worse than a red commit someone can see.

### 2026-10-28 — Lane C — Threshold fitting on the calibration split, and why it refused to write
- what changed: `netra/models/fit_thresholds.py`, `scripts/fit_quality_head.py`,
  `tests/test_thresholds.py` (22 tests). **`config/thresholds.yaml` is UNCHANGED** —
  see below; that is the result, not an omission.
- what it fits and what it refuses to touch: only `quality_gate.usable_min_p` and
  `reject_max_p`. `dr.conformal_confidence` is the coverage the programme ASKS for
  (SPEC.md fixes 0.90) and re-fitting it on calibration data would be choosing the
  guarantee to flatter the model; `dr.refer_grades`,
  `dr.abstain_if_set_spans_actions` and `sites.min_n_for_rate` are clinical or
  reporting policy, and `refer_grades` is mirrored in Lane A and Lane B so moving it
  silently would be a cross-lane clinical change. Two fitted, four carried over, tested.
- **it ran, and then refused to write — twice, for two different real reasons.**
  1. With a **random-init** backbone on 20 calib images the quantiles gave
     `usable_min_p 0.42 / reject_max_p 0.40` — a borderline band **0.02 wide**. Added
     `MIN_BORDERLINE_BAND = 0.10`: a band that thin is measuring noise, not quality.
  2. With the **real pretrained densenet121** (weights downloaded, ~32 MB) and a head
     fitted on synthetic degradations, it gave `0.95 / 0.85` — which PASSES the band
     guard and is still useless: a gate that rejects nothing. The cause is structural,
     not numerical. The calibration split holds **only real images**, and a head trained
     to tell blur from no-blur scores them all ≈1.0 (10th percentile **0.852**). So the
     score distribution is **one-sided by construction** and quantiles would carve a
     "reject" band out of the usable population — inventing a boundary the data does not
     contain. Added `ONE_SIDED_SCORE_FLOOR = 0.50`.
  Both constants carry the observed numbers in their comments, and the run now exits 3
  with an explanation and leaves the file alone — verified by `diff` against a
  pre-run copy: **identical**.
- the honest conclusion: **these two cut-points cannot be fitted in this build.** Doing
  it needs a calibration set containing both usable and unusable images judged by a
  human, i.e. a quality-labelled corpus. EyeQ is that corpus and its labels reference
  EyePACS (~89 GiB), which is out of scope. The shipped 0.70/0.30 placeholders stay,
  and `TODO(review)` is in the header the fitter WOULD have written plus in
  `quality.py`. Writing 0.95/0.85 would have looked like progress and been a regression.
- `scripts/fit_quality_head.py` fits a stand-in head from **synthetic** degradations
  (blur, under-exposure, clipped FOV — the three faults the reason-code channel names)
  of real calibration images, 24 positive + 24 negative. It prints, and its docstring
  states, that a human never judged these images and that any gate number measured with
  it belongs in the **synthetic table**, never pooled with real poor-quality images
  (`.claude/rules/ml.md`). Without any head the gate refuses to produce a verdict, so
  this is what makes the end-to-end path exercisable at all.
- **the cross-lane contract is now tested.** `thresholds.py` writes only the two-level
  subset Lane A's parser accepts, `write()` re-reads and fails rather than leaving an
  unparseable file, and three tests import **Lane A's own parser** to assert it can read
  what Lane C writes, that both parse the shipped file identically, and that both read
  the same `refer_grades`. A format drift would otherwise 500 a route handler and break
  nothing in Lane C.
- a floating-point trap my own test caught: `0.95 - 0.85` is `0.09999999999999998`, so
  the band guard rounds to 4dp **before** comparing — without that round, that pair
  would be rejected for a reason that has nothing to do with quality.
- verified: **288 tests pass** (266 before, +22). ruff and ruff-format clean on this
  lane's files, checked as their own commands this time.

### 2026-10-28 — Lane C — T-07 inference entrypoint (`netra/models/infer.py`)
- what changed: `netra/models/infer.py`, `tests/test_infer.py` (15 tests). This is what
  the API will call in place of Lane B's simulated `gateSim.ts`.
- it returns the model-side fields of the frozen `POST /v1/encounters` body —
  `image_sha256, gate_verdict, cause, prediction_set, model_version, site_id,
  device_seq` — and `as_encounter_body()` is **validated against Lane A's own
  `EncounterRequest` pydantic model** in a test, so the shape cannot drift from the
  contract. The image hash is computed here; the pixels never leave (SPEC.md).
- **four distinct not-available states, each reported as itself rather than guessed:**
  1. gate head missing → `quality_verdict: null`, `model_version: "unloaded"`, and
     `as_encounter_body()` **raises** rather than posting a half-formed encounter
     (Lane A's `gate_verdict` is not nullable).
  2. gate says reject → verdict `reject`, no grade, no prediction set, and
     `abstain: false` — a reject is "no result", NOT an abstention, because nothing was
     graded. Lane A returns 422 for a reject carrying a prediction set, so the body
     sends `null`; asserted.
  3. admitted but no DR checkpoint → real verdict kept (the gate genuinely ran and that
     is a recordable fact), grade absent, `model_version: "unloaded"`.
  4. graded but **no conformal calibration** → **abstains**. An argmax is not a
     prediction set, and a prediction set is what this project reports, so it refuses to
     quietly emit a top-1 grade.
- `model_version` is `"unloaded"` unless **both** halves are real, and is deliberately
  not a partial string: a caller writing it into a ledger needs to know the whole
  pipeline was real, not half of it. Untrained weights keep their `:untrained` suffix all
  the way through.
- **driven for real on an actual APTOS image**, not only in tests. With nothing loaded:
  `quality_verdict: null`, `model_version: "unloaded"`, note "quality gate unavailable",
  and the CLI prints that no grade was produced and none was invented. With the
  synthetic gate head loaded and the real pretrained densenet121: `quality_verdict:
  "usable"`, `quality_score_milli: 961`, grade still `null` and `model_version` still
  `"unloaded"` because no DR checkpoint exists. That is the correct behaviour end to end.
- verified: **303 tests pass** (288 before, +15), ruff and ruff-format clean, each run as
  its own command.

### 2026-10-28 — Lane C — Unattended run summary
Backlog worked in order, all seven steps. **303 tests pass** (178 at the start of this
lane's work; +125). Lane C touched only `netra/models`, `netra/eval`, `notebooks`,
`scripts`, `data/splits`, `tests/*` for its own modules, plus `tracker.md`/`memory.md`.
`netra/api`, `netra/ui`, `netra/db` and `netra/ledger` were **not modified** — only
imported read-only in cross-lane tests.

**Commits, in order:**
1. `4b2982e` — real APTOS labels, frozen patient-level splits, split invariant tests.
2. `0b31a4f` — revert: restore Lane A's `gen_device_key.py` formatting (cross-lane slip).
3. `72984e6` — **T-12** every function in `metrics.py` covered (38 tests).
4. `2eb11a3` — QuickQual quality gate that refuses rather than guesses.
5. `acf2df2` — DR backbone, frozen-split dataset, CPU-smokeable trainer, Kaggle notebook.
6. `ed2ed99` — conformal abstention (**mis-verified, see 7**).
7. `4345d1a` — fix C401 + record what `ed2ed99` got wrong.
8. `212c326` — threshold fitter that ran and then refused to write.
9. `7c4e2c8` — **T-07** inference entrypoint that never invents a grade.

**What is REAL vs SYNTHETIC — the thing to read before quoting any number:**
- **Real:** 366 APTOS images with real 5-class labels (`mariaherrerot/aptos2019`,
  sha256 `ddb19e46…`); frozen splits train 219 / calib 75 / test 72 at seed 20261027;
  83 real images on disk (75 calib + 8 train); real pretrained `densenet121.tv_in1k`
  weights; real `convnext_tiny` forward/backward passes on CPU.
- **Synthetic:** the quality head (fitted on blur / under-exposure / clipped-FOV
  degradations of real images — a human never judged them); every conformal coverage
  number (synthetic probabilities whose labels were drawn from them); the fundus
  fixtures in `tests/test_quality.py`.
- **Not measured at all:** DR accuracy or QWK, gate accuracy, abstention rate on real
  data. **No trained DR checkpoint exists.** No number in this lane is a result.

**`TODO(review)` markers left (5):**
- `scripts/make_splits.py` behaviour, recorded in memory: its docstring and ml.md claim a
  source corpus is kept whole in one fold, but it buckets on `patient_id` only. Moot with
  one corpus; changing it would re-pick the splits, which rules.md §6 makes a stop-and-ask.
- `netra/models/quality.py` — QuickQual-MEME's 10 published parameters are not
  transcribed, so that fallback refuses rather than improvising them.
- `netra/models/reason_codes.py` — the four classical cut-points are uncalibrated; no
  published absolute Laplacian threshold for fundus images exists (SPEC.md §1).
- `netra/models/fit_thresholds.py` header text — the cut-points it would write are
  provisional quantiles, not a boundary fitted against quality labels.
- `netra/models/abstain.py` / `netra/eval/metrics.py` — see the two CLAUDE.md corrections
  below; those are root-doc edits for the team, not Lane C's to make.

**Three documented errors found in the project's own docs, each now pinned by a test:**
1. CLAUDE.md: MAPIE's flow is **not** `fit -> conformalize -> predict_set`. With
   `prefit=True`, `fit()` **raises**; it is `conformalize -> predict_set`.
2. CLAUDE.md: `predict_set` returns a **tuple** `(points, sets)`; the 3-D bool array is
   the second element.
3. A claim **I** wrote and then disproved: `labels=range(5)` does not protect kappa
   against a fold missing a grade — the constant weight factor cancels, measured
   identical (0.8571428571428572) both ways.

**New library gotcha not in CLAUDE.md:** `SVC(probability=True)` is deprecated in
scikit-learn 1.9 and **removed in 1.11**. Replaced with
`CalibratedClassifierCV(SVC(), ensemble=False, method="sigmoid")`.

**What still needs the Kaggle GPU run (T-09), in order:**
1. Run `notebooks/train_dr.ipynb` on a T4 → a real checkpoint with `trained: true`.
2. Conformalise on the **calibration** fold with real probabilities (notebook §6).
3. Re-run `python -m netra.models.fit_thresholds` — it will still refuse the quality
   cut-points without a quality-labelled corpus, which is correct.
4. Touch the **test** split exactly once, at the very end. Expect QWK 0.88–0.92;
   above 0.95 means a leaked split.

**Deliberately not done:** no full local training (no GPU, and the brief forbids it);
EyePACS never downloaded; the 8.6 GiB APTOS mirror never pulled in full (per-file
fetching got 83 images, which is what a CPU box can use); `config/thresholds.yaml`
unchanged; `requirements.txt` unchanged (the `kaggle` CLI is a subprocess, never an
import, so it was not added).

**Process lesson worth keeping:** `ed2ed99` landed with a ruff error and a commit message
claiming a pytest count that had not been observed, because lint/test/commit were chained
into one shell line and the `&&` guard did not hold as read. Every later commit ran its
gates as separate commands. A commit message is a claim; an unverified claim in history
is worse than a visible red commit.

### 2026-10-28 — Lane C — one Kaggle run, both real artifacts (T-08 + T-09)
Goal: make a single T4 session produce the DR checkpoint **and** the real QuickQual
head, and package everything Kaggle needs. **402 tests pass** (303 at the start of this
session, +99). Lane C touched only `netra/models`, `netra/eval`, `notebooks`, `scripts`,
`tests/*` for its own modules, plus `tracker.md`/`memory.md` and one `.gitignore` line
for its own build artifact. `netra/api`, `netra/ui`, `netra/db`, `netra/ledger`
unmodified — `scripts/gen_device_key.py` was touched once by a blanket `ruff --fix` and
reverted immediately, the same slip `0b31a4f` recorded.

**Team decision taken before any code: the corpus grows.** The committed splits covered
366 images (the 366 rows of one mirror's `test.csv` — all a CPU box could fetch per
file). 219 training images cannot reach the QWK 0.88–0.92 SPEC.md §2 expects, and the
full 3,662 are mounted on Kaggle. `rules.md` §6 makes a split change a stop-and-ask, so
it was asked. Answer: extend at the same seed.

**Why growing is not the re-shuffling `.claude/rules/ml.md` forbids, and how that is
proven rather than claimed.** `assign_fold` is a pure function of `(seed, patient_id)`,
so an image's fold does not depend on what else is in the manifest. Verified before
writing anything: the pure function reproduces **all 366** committed assignments, and
`tests/test_split_growth.py` pins that using the committed splits alone (no manifest —
it is gitignored, and APTOS has no patient id so `patient_id == image_id`). The refactor
that moved the arithmetic into `netra/models/splits.py` reproduces `data/manifest.csv`
and all three split files **byte-identically**. `check_preserved()` raises `SplitDrift`
on a moved, dropped or re-seeded image; `check_labels_agree()` raises on a relabelled
one — a relabelled image changes what the old calibration fold MEANS without changing
which images are in it, which nothing downstream would notice.

**T-08 was unblocked by reading the blocker correctly.** EyeQ publishes 28,792 human
gradability judgements and no pixels; the 89 GiB was always EyePACS, which is MOUNTED on
Kaggle. So the labels are two 700 KiB CSVs over HTTP and nothing else is downloaded.
Verified against the real files: `,image,quality,DR_grade`; quality 0=Good 1=Usable
2=Reject; train 12,543 rows / 8,614 patients, test 16,249 / 12,048, and the two are
**patient-disjoint (0 overlap)** — so the published split is used rather than one we
invent. Head is binary Good+Usable vs Reject, which is the decision the gate makes and
the setting QuickQual's published 0.886/0.9687/0.811 refers to. Patient identity is REAL
here (`<patient>_<left|right>`), unlike APTOS.

**Five bugs found by building, not by reading:**
1. `notebooks/train_dr.ipynb` pointed `IMAGES_DIR` at `train_images/train_images` while
   the committed splits came from a mirror storing files under `test_images/test_images`
   → `retained_fraction: 0.0` and an assertion ~40 min into a session. That notebook is
   now a pointer to `train_kaggle.ipynb`.
2. `train()` ignored `splits_dir`/`manifest` entirely — a grown run would have trained on
   the grown splits it thought it chose and the 366-image manifest it actually read, with
   every extra id counted as a missing manifest row. Now parameters, with a test.
3. `collect()` looked only for `<id>.png`; several APTOS mirrors ship `.jpg`.
4. `find_aptos_label_csvs` lived in `scripts/`, which is NOT in the payload — the
   notebook could not have imported it. Moved into `netra/models/splits.py`.
5. The payload zip on disk went stale mid-session and surfaced as an `AttributeError`
   three cells into the dry run. A Kaggle Dataset is versioned by hand, so cell 1 now
   checks the payload exposes what the notebook imports and says to rebuild.

**What was actually run, and what was not.** The notebook was driven **end to end**
against a simulated `/kaggle/input` — a freshly built payload zip, the real 366 APTOS
labels, the real EyeQ CSVs over the network, synthetic pixels, only the training call
stubbed by a real `trained: true` checkpoint. Every cell ran; both artifacts landed. No
GPU here, so **no number in this lane is still a result**: no DR QWK, no gate accuracy,
no abstention rate on real data. The 0.6667 gate accuracy the dry run printed is on
random-init densenet features over synthetic pixels and means nothing.

**Design choices worth keeping:**
- Nothing is hardcoded to a Kaggle mount. APTOS labels are found by their
  `id_code,diagnosis` **header** (a filename match picks up `sample_submission.csv`),
  the APTOS image directory by asking which one holds the ids in the frozen splits, and
  EyePACS by the `<patient>_<left|right>` filename shape. Candidates are printed.
- All eleven stop conditions raise a named `Stop`, not a warning. A warning that prints
  and continues is not a stop.
- `scripts/package_for_kaggle.py` parses every `netra.*` import out of the payload with
  `ast` and refuses to write if one does not resolve inside it — that failure otherwise
  costs 40 minutes of a 9-hour session. It also refuses to ship `keys/` or another
  lane's code. The zip is byte-for-byte reproducible, so its sha256 identifies the code
  a run used. The test that matters unpacks the real zip and imports five modules in a
  **subprocess with the repo off `sys.path`**; without that isolation it passes for a
  payload that is missing the module.
- `QuickQualFeatures.batch` gained a `batch_size` defaulting to 1 (no existing caller
  changes), and a test proves batching does not move the numbers — if it did, a head
  fitted in a batched run would not match the gate that serves single images.

**Still open after the GPU run:** commit `artifacts/splits_full/` and
`manifest_full.csv`; re-run `fit_thresholds` with both real artifacts in place (the
quality cut-points should now be fittable against real EyeQ labels rather than refused);
then the **test** split, once, and only then.

### 2026-10-29 — Lane A + Lane B — T-18 integration checkpoint, T-21 deploy prep, and the gate seam
- what changed: one session covering BOTH Lane A and Lane B, by instruction, while
  Lane C's Kaggle run is still training. Nothing under `netra/models/`,
  `netra/eval/` or `config/thresholds.yaml` was touched.
  - **`netra/ui/src/lib/qualityGate.ts` — THE SEAM (new).** `callQualityGate()` is
    now the only way the front end gets a verdict; `Capture.tsx` no longer reaches
    into `SCENARIOS` or hashes the file itself. `GateResult` is field-for-field
    equivalent to `netra.models.infer.InferenceResult` (camelCase vs snake_case),
    so the swap is a rename, not a redesign. `assertGateResult` enforces the
    invariants on the way out and guards the REAL model too: a reject carries no
    prediction set and no grade, `[]` is refused rather than read as a graded empty
    set, and the score stays a scaled integer. The `// TODO: swap for real
    infer.py` sits on the one line that has to change. 23 tests.
  - **`netra/api/routes/encounters.py` — a real bug fixed.** With no `X-Device-Kid`
    header the handler auto-registers a device, and the default kid was the fixed
    string `device-1`. The SECOND site to auto-register therefore tried to INSERT a
    primary key the first already held: `UNIQUE constraint failed: devices.kid`, a
    500 on a valid request. Every earlier test used one site, and `conftest`'s
    `registered` fixture pre-registers a device for it, so no test ever triggered a
    second auto-registration. Kids are now the first free `device-N`. Six new tests
    across two deviceless sites; three fail on the old code.
  - **`scripts/seed_dev.py` (new).** Four sites, 117 encounters, four audits, one
    referral at `contacted` — created through the REAL endpoints via `TestClient`,
    never by INSERTing rows, so the seeded chain verifies and the script checks that
    it does before exiting 0. site-12 has n=12 ON PURPOSE: the n<30 rule cannot be
    demonstrated if every site clears the floor. site-21 is drift-flagged, so its
    audit fails and it stays `unpinned`. Refuses an existing DB without `--force`.
  - **`Dockerfile` + `fly.toml` + `.dockerignore` (new, T-21).** Node builds the SPA,
    python serves it behind the API, one machine. The image does NOT
    `pip install -r requirements.txt`: `netra/api` imports no model code, so it
    installs the eleven packages it does import at requirements.txt's own pins
    (verified by importing `netra.api.main` and reading `sys.modules`). torch is
    absent and `netra/models` is not copied. `requirements.txt` was NOT edited.
  - **`netra/api/main.py` — env-gated SPA mount.** `NETRA_UI_DIR` unset leaves the
    app as exactly the frozen nine. `SpaFiles` is an ASGI wrapper, not a route,
    because `tests/test_sites.py` pins the `/v1` routes at nine and that test is
    right. It falls back to `index.html` itself — `StaticFiles(html=True)` does NOT
    do SPA fallback, it looks for `404.html` — while keeping `/v1/typo` a 404
    instead of 200-with-HTML.
  - **`netra/ui/vite.config.ts`** — `testTimeout: 30s`. `npm test` was RED on HEAD
    with a clean tree: `routes.smoke.test.ts` imports Sites, which pulls Recharts,
    and transforming it cold took 7039ms against a 5000ms default. Green on a
    re-run once the cache was warm, i.e. the gate reported on `node_modules/.vite`
    rather than on the code.
  - **`types.ts` / `client.ts`** — the three `TODO(Lane A)` shapes were settled on
    2026-10-28 and pinned by `tests/test_integration.py`; the comments saying they
    were TBD were retired. `SiteAuditRequest` is now the real seven fields instead
    of `Record<string, unknown>`, and `attempts` is `QueueAttempt[]`.
- verified: `pytest -q` **436 passed**. `npm run build` green (`tsc -b` included).
  `npm test` **135 passed**, green from a cold Vite cache. Live suite **11/11**
  against uvicorn :8000 with `VITE_NETRA_LIVE=1`, including one test that walks the
  whole path through the seam. End to end against uvicorn :8000 + Vite :5173:
  encounter at ledger idx 125 -> verify ok -> referral -> four transitions -> head
  124 to 130 -> verify still ok; terminal-state transition 409. Tamper demo on the
  LIVE API: `ok:true` -> `tamper --seq 60` -> `ok:false first_bad_index 60` ->
  restored. Deployed shape exercised on :8001 against the real `dist/`: shell, five
  deep links, assets, PWA manifest, service worker, API, `/v1/typo` 404 text/plain,
  and `/../../etc/passwd` serving the shell rather than a file.
- unverified / TBD: **no browser/DOM pass.** The Chrome extension reports "not
  connected", the same blocker as 2026-10-28, so not one screen has been SEEN
  rendering in this session. The data layer is tested and every route module is
  served and transforms cleanly, but layout, contrast in situ and the forest plot's
  appearance are unverified — **TBD, verify before the demo.** **The deploy has not
  been run**: `fly.toml`'s `app = "netratrust"` and `primary_region = "bom"` are
  guesses, no Fly app or volume exists, and the image has never been built — Docker
  was not invoked, so the Dockerfile is reviewed and tested-by-parsing only. The
  quality gate is still SIMULATED; nothing here loads a Lane C artifact.
  `scripts/gen_device_key.py` carries one pre-existing `ruff` I001 finding, left
  untouched as it predates this session.
