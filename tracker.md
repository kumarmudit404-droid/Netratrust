# NetraTrust — Task Board

> **Window:** Wednesday 2026-10-28 → Friday 2026-10-30. Today is Tuesday 2026-10-27;
> the starter repo is scaffolded (see `memory.md`). Lanes and ownership are from
> `CLAUDE.md`. Scope is from `SPEC.md`, which is **frozen** — no task may add an
> endpoint, a referral state, or a dependency.

## Legend
Status: `todo` · `doing` · `done` · `blocked`. Lanes: A (Backend & Ledger),
B (Frontend), C (ML & Evaluation).

## Fixed checkpoints
- **Wed 18:00** — integration checkpoint: API + UI + a model talk end-to-end on one path.
- **Thu 21:00** — feature freeze: whatever is not integrated is cut; ship the checkpoint
  you have.
- **Fri 12:00** — hard stop; rehearse the 3-minute demo on the deployed URL.

## Tasks

| ID | Task | Lane | Status | Blocked by |
|---|---|---|---|---|
| T-01 | Build env: Python 3.12 venv, `pip install -r requirements.txt`, green `pytest` | A | done | — |
| T-02 | DB tables + append-only triggers (SQLModel) | A | done | T-01 |
| T-03 | Ledger: hash chain + Ed25519 + rfc8785 write/verify | A | done | T-02 |
| T-04 | `POST /v1/encounters` (append-before-return) + CORS + idempotency | A | done | T-03 |
| T-05 | `POST /v1/referrals` + `PATCH /v1/referrals/{id}` state machine | A | done | T-03 |
| T-06 | `GET /v1/ledger/verify` + `/checkpoint` | A | done | T-03 |
| T-07 | Site status, metrics, queue-depth endpoints | A | done | T-02 |
| T-08 | Fit quality gate (QuickQual) on EyeQ; pickle load test | C | doing | UNBLOCKED: EyeQ publishes labels, not pixels, and EyePACS is MOUNTED on Kaggle. `netra/models/eyeq.py` + section 7 of `notebooks/train_kaggle.ipynb` fit the real head. **Needs the GPU run** |
| T-09 | Train DR backbone `convnext_tiny` @512px on Kaggle T4 | C | doing | `notebooks/train_kaggle.ipynb` + `kaggle_payload.zip` ready and driven end to end against a simulated mount. **Needs the GPU run** |
| T-10 | Conformal wrap (MAPIE SplitConformalClassifier) + abstain logic | C | done | tested on synthetic probabilities; conformalise on real ones after T-09 |
| T-11 | Fit thresholds on **calibration split only**; write `thresholds.yaml` | C | doing | fitter built + run; it REFUSED to write (one-sided scores). Placeholders stand — see memory.md |
| T-12 | Unit-test remaining metrics functions | C | done | T-01 |
| T-13 | React PWA scaffold + shell: Vite/TS, Tailwind tokens, shadcn/ui, TanStack Query, vite-plugin-pwa, `<TopNav/>` + five routes, typed API client (mock responder) | B | done | Node (installed) |
| T-14 | Capture route + Reject→recapture screen ("no result — take again") | B | done | T-13 |
| T-15 | Grade/Abstain route + prediction set ("a doctor should check this") | B | done | T-13, T-10 |
| T-16 | Sites route: Recharts forest plot + Wilson intervals (shared `formatRate`) | B | done | — |
| T-17 | Ledger route: verify + checkpoint display + **tamper demo** (append → corrupt one entry → `verify` returns `ok:false` with `first_bad_index`) — SPEC §7. Corrupt step is `python -m netra.ledger.tamper --seq N`, NOT an endpoint | B | done | — |
| T-18 | **Integration checkpoint** (Wed 18:00) | A+B+C | done | T-04, T-13 |
| T-19 | Offline capture queue + sync (idempotency key) — server side T-04; device-side queue, replay and status strip done 2026-10-29 (`netra/ui/src/lib/offline/`) | A+B | done | T-04 |
| T-20 | Grad-CAM overlay (stretch) | C | todo | T-15 |
| T-21 | Deploy to Fly.io (volume for SQLite) | A | doing | T-18 |
| T-22 | **Feature freeze** (Thu 21:00) | all | todo | — |
| T-23 | Rehearse 3-min demo on deployed URL; recorded fallback | all | todo | T-21 |
| T-24 | **Hard stop** (Fri 12:00) | all | todo | — |

## Demo
`demo/RUNBOOK.md` — the 3-minute path, the exact commands, what to say, a
troubleshooting table and three fallbacks.
`demo/MODEL_LANDING.md` — the mechanical checklist for when T-08/T-09's
artifacts arrive: drop → fit_thresholds (**calib split only**) → conformalize →
verify → swap the one UI seam → re-run all gates. Checklist only; nothing in it
has been run, because no artifact exists. It stops being mechanical at the swap
itself: `infer.py` is Python and the gate runs on-device, so the real
implementation is in-browser ONNX/WASM or a local sidecar, and **neither is
built**. **Re-seed with
`scripts/seed_dev.py --force` before every run**: rehearsals and the test
suites append to the ledger, so `site-07` drifts off the runbook's table. The
reset is safe with the API running.

## T-18 — what the integration checkpoint actually proved (2026-10-29)
Backend + front end run together; the model is still simulated behind ONE seam.
- `scripts/seed_dev.py` seeds four sites, 117 encounters, four audits and one
  referral THROUGH the real endpoints, so the seeded chain verifies. Run it
  before any demo: `POST /v1/encounters` 404s on an unknown site and the UI
  posts to `site-07`.
- Full path driven against uvicorn :8000 + Vite :5173: capture (hash on device)
  -> encounter at ledger idx 125 -> verify ok -> referral issued -> four
  transitions -> head 124 -> 130 -> verify still ok. Illegal transitions 409.
- Tamper demo against the LIVE API: `ok:true` -> `python -m netra.ledger.tamper
  --seq 60` -> `ok:false first_bad_index 60` -> restored.
- Lane B's typed client against live Lane A: 11/11 (`VITE_NETRA_LIVE=1`),
  including the whole path in one test, cross-origin, and dedup on retry.
- **Not covered:** no DOM/browser pass. The Chrome extension is not connected
  (same blocker as 2026-10-28), so no screen has been seen rendering. Route
  modules are served and transform cleanly, and the data layer is tested, but
  "it looks right" is unverified. **TBD — verify before the demo.**

## T-21 — ready to ship, not shipped
`Dockerfile` + `fly.toml` + `.dockerignore` are in. One command deploys:
`fly deploy` (after a one-time `fly launch --no-deploy --copy-config` and
`fly volumes create netra_data --size 1 --region bom`). One machine, because a
Fly volume attaches to one and SQLite has one writer. `NETRA_DB` **and**
`NETRA_KEYS_DIR` live under `/data`: lose the Ed25519 keys and every existing
entry fails verify with `unknown signer_kid`. The image installs the eleven
packages the API imports at `requirements.txt`'s pins rather than the whole
file — torch is not in it and `netra/models` is not copied.

## T-19 — device-side offline queue (done 2026-10-29)
`netra/ui/src/lib/offline/`. Capture with no signal, queue on the device,
replay on reconnect. No new endpoint: it runs entirely on T-04's
`idempotency_keys`.
- **The key is minted at enqueue, once**, and reused on every delivery. That is
  the whole design: a replayed `contact_attempted` carrying a fresh key would
  increment `attempt_n` again and read as two real attempts to reach a patient.
- Every mutation is written to the queue BEFORE it is sent, even when online —
  one code path, so the first attempt and the retry cannot disagree about the
  key, and a new capture cannot overtake an older unsent one.
- **409 is a RETRY, not a drop.** The server returns it while that key is in
  flight, i.e. the request is being applied. 422 and the other 4xx are drops,
  kept in a `failed` list and shown, because a silently dropped capture is the
  worst outcome available.
- The drain STOPS at the first retryable entry rather than skipping it. 36
  tests, plus two live ones against the running API.

## T-21 — deploy prep: one real bug found without Docker
Docker CLI 29.7.2 is installed on this machine but **no daemon is reachable**,
so the image has still never been built. Static checks caught the first
failure anyway: the image ships `scripts/seed_dev.py`, which seeds through
`fastapi.testclient`, and `starlette.testclient` raises on import without
`httpx`/`httpx2` — both only EXTRAS of starlette and fastapi. `fly ssh console
-C "python scripts/seed_dev.py"` would have died on an import inside a
container. Fixed; `httpx==0.28.1` was already pinned in `requirements.txt`.
`fly.toml`'s `app` and `primary_region` are marked **SET THIS BEFORE LAUNCH**.

## T-21 — the single-origin shape, walked against a fresh volume (2026-10-30)
Re-ran the deploy dry-run on an **empty** volume rather than the existing
`netra.db`, which is the state a first `fly deploy` actually starts from. The
shape holds: single origin, `NETRA_UI_DIR` set, no Vite proxy; every built
asset serves with the right content type; a hard refresh on `/sites` gets the
shell; `/v1/typo` is still a text 404; seeding worked **while that server held
the database file** (the `fly ssh console -C` case); the whole demo path ran,
including dedup returning `Idempotency-Replayed: true` with no second entry,
the tamper to `ok:false` at 60 with every read still answering, and `--force`
resetting in place back to `ok:true` without restarting the server. Lane B's
typed client: 13/13 against it.
- **The one real bug, and it was upstream of the shape:** `netra/ui/.env` was
  in the Docker build context, where `vite build` reads it. **Git and Docker
  disagree about one pattern** — git matches a slashless `.gitignore` pattern
  at every level, so the file is untracked and invisible in review, while
  Docker matches each `.dockerignore` pattern against the whole relative path,
  so a bare `.env` covered only the context root. `.env.example` invites
  `VITE_USE_MOCK=1` for working with no backend; left on through a build it
  ships a front end whose grades, ledger indices and Wilson intervals are all
  invented by `src/lib/api/mock.ts`, with every screen rendering and nothing
  erroring. Fixed with `**/.env` (root pattern kept alongside — no daemon here
  to prove `**` matches zero directories). Pinned by four tests, one of which
  exists only to stop the other three going vacuous.
- The image has **still never been built.** Everything above is a real server
  and a real bundle, but not a real container.

## Lane C — what the one Kaggle run has to do (T-08 + T-09)
`python scripts/package_for_kaggle.py` → upload `kaggle_payload.zip` as a Kaggle
Dataset → attach it with an APTOS dataset and an EyePACS mirror → T4 + Internet on →
Run All on `notebooks/train_kaggle.ipynb`. Its first cell is the run book. One session
produces **both** `convnext_tiny_aptos.pt` (`trained: true`) and
`quality_head_eyeq.pkl` (real human EyeQ labels, superseding the synthetic head), plus
the grown splits to commit. Re-run `package_for_kaggle.py` and upload a new dataset
version after any code change — the notebook stops at cell 1 on a stale payload.

## Critical path
`T-01 → T-02 → T-03 → T-04 → T-18 → T-21 → T-23`. The two real risks sit off this path:
- **T-09** (model training) may not finish by the freeze → ship the checkpoint you have.
- **Evaluation drift** — re-picking a split/threshold after seeing test results. No hook
  catches it; review diffs to `config/thresholds.yaml` and `netra/eval/` at every merge.

## Pre-agreed cut list (drop in this order if behind at Wed 18:00)
1. Grad-CAM (T-20) 2. Offline sync (T-19) 3. Dark mode (design.md §2)
4. Audit endpoint polish (T-07). Never cut: quality gate, abstention, ledger verify.
