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
