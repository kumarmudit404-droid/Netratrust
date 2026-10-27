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
| T-01 | Build env: Python 3.12 venv, `pip install -r requirements.txt`, green `pytest` | A | todo | — |
| T-02 | DB tables + append-only triggers (SQLModel) | A | todo | T-01 |
| T-03 | Ledger: hash chain + Ed25519 + rfc8785 write/verify | A | todo | T-02 |
| T-04 | `POST /v1/encounters` (append-before-return) | A | todo | T-03 |
| T-05 | `POST /v1/referrals` + `PATCH /v1/referrals/{id}` state machine | A | todo | T-03 |
| T-06 | `GET /v1/ledger/verify` + `/checkpoint` | A | todo | T-03 |
| T-07 | Site status, metrics, queue-depth endpoints | A | todo | T-02 |
| T-08 | Fit quality gate (QuickQual) on EyeQ; pickle load test | C | todo | T-01 |
| T-09 | Train DR backbone `convnext_tiny` @512px on Kaggle T4 | C | todo | split frozen |
| T-10 | Conformal wrap (MAPIE SplitConformalClassifier) + abstain logic | C | todo | T-09 |
| T-11 | Fit thresholds on **calibration split only**; write `thresholds.yaml` | C | todo | T-10 |
| T-12 | Unit-test remaining metrics functions | C | todo | T-01 |
| T-13 | React PWA scaffold + shell: Vite/TS, Tailwind tokens, shadcn/ui, TanStack Query, vite-plugin-pwa, `<TopNav/>` + five routes, typed API client (mock responder) | B | done | Node (installed) |
| T-14 | Capture route + Reject→recapture screen ("no result — take again") | B | todo | T-13 |
| T-15 | Grade/Abstain route + prediction set ("a doctor should check this") | B | todo | T-13, T-10 |
| T-16 | Sites route: Recharts forest plot + Wilson intervals (shared `formatRate`) | B | todo | T-07 |
| T-17 | Ledger route: verify + checkpoint display | B | todo | T-06 |
| T-18 | **Integration checkpoint** (Wed 18:00) | A+B+C | todo | T-04, T-13 |
| T-19 | Offline capture queue + sync (idempotency key) | A | todo | T-04 |
| T-20 | Grad-CAM overlay (stretch) | C | todo | T-15 |
| T-21 | Deploy to Fly.io (volume for SQLite) | A | todo | T-18 |
| T-22 | **Feature freeze** (Thu 21:00) | all | todo | — |
| T-23 | Rehearse 3-min demo on deployed URL; recorded fallback | all | todo | T-21 |
| T-24 | **Hard stop** (Fri 12:00) | all | todo | — |

## Critical path
`T-01 → T-02 → T-03 → T-04 → T-18 → T-21 → T-23`. The two real risks sit off this path:
- **T-09** (model training) may not finish by the freeze → ship the checkpoint you have.
- **Evaluation drift** — re-picking a split/threshold after seeing test results. No hook
  catches it; review diffs to `config/thresholds.yaml` and `netra/eval/` at every merge.

## Pre-agreed cut list (drop in this order if behind at Wed 18:00)
1. Grad-CAM (T-20) 2. Offline sync (T-19) 3. Dark mode (design.md §2)
4. Audit endpoint polish (T-07). Never cut: quality gate, abstention, ledger verify.
