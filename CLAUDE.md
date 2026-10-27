# NetraTrust

Diabetic-retinopathy screening with an image-quality gate, an abstaining
classifier, per-site monitoring, and a tamper-evident referral ledger.
Read `SPEC.md` before writing code. It is the contract; this file is conventions.

## Commands
- Install: `pip install -r requirements.txt` (versions are pinned; do not bump)
- Test: `pytest -q`
- Lint: `ruff check . && ruff format --check .`
- API: `uvicorn netra.api.main:app --reload --port 8000`
- UI: `streamlit run netra/ui/app.py`
- Verify ledger: `python -m netra.ledger.verify`

## Ownership (do not edit outside your lane)
- `netra/api/`, `netra/ledger/`, `netra/db/` — **Lane A** (Backend & Ledger)
- `netra/ui/` — **Lane B** (Frontend)
- `netra/models/`, `netra/eval/`, `notebooks/` — **Lane C** (ML & Evaluation)
- `SPEC.md`, `requirements.txt` — change only by agreement, in a separate commit

## Clinical invariants (never violate; ask rather than assume)
- A failed quality gate is NOT a negative DR result. It is "no result".
  Never let an ungradable image flow into a grade, a referral, or a metric
  denominator for grading accuracy.
- Abstention thresholds are NEVER tuned on the test split. Tune on calibration
  split only. If you need a threshold, read it from `config/thresholds.yaml`.
- Every clinical decision and referral transition is appended to the ledger
  before it is returned to the caller. No decision exists outside the ledger.
- Ledger payloads are canonicalised with `rfc8785` on BOTH write and verify.
  Floats are banned from ledger payloads: store confidences as strings or
  scaled integers. `rfc8785.dumps({"n": 1.0})` emits `{"n":1}` while
  `json.dumps` emits `{"n":1.0}` — this breaks chains silently.
- Integers above 2^53 raise in `rfc8785`. Timestamps and IDs are strings.
- Never report a bare percentage for n < 30. Report the count and a Wilson
  interval.
- Per-site performance is always a distribution. Never print a mean across
  sites as the headline number.

## Library gotchas verified 2026-10-27 (these will waste your time)
- `brier_score_loss` takes `y_proba=`, NOT `y_prob=`. The old keyword raises
  `TypeError` in scikit-learn 1.9.1.
- `LogisticRegression(penalty=None)` is deprecated; use `C=np.inf`.
- FastAPI route handlers are SYNC `def`, not `async def`. SQLite is blocking;
  async handlers with blocking SQLite is the top time sink.
- Use `lifespan=` context managers. `@app.on_event` is deprecated and mixing
  the two silently disables handlers.
- MAPIE v1 API: `SplitConformalClassifier(estimator, confidence_level,
  conformity_score, prefit=True)` then `fit` -> `conformalize` -> `predict_set`.
  `predict_set` returns a 3-D `(n, n_classes, n_levels)` bool array even for a
  single confidence level.
- The Grad-CAM package is `grad-cam`, import `pytorch_grad_cam`. There is no
  package named `pytorch-grad-cam`.
- Do not add `alibi-detect`, `sdv`, or `puncc`. The first two are Business
  Source License 1.1 (non-OSI); the third pins numpy<2.

## Reporting conventions
- Primary calibration metrics: Brier score and NLL. ECE is secondary and is
  always reported with its binning scheme and bin count.
- Selective prediction: report AUGRC, not AURC. AURC violates monotonicity.
- Risk-coverage curves take a HORIZONTAL reference line at the no-abstention
  risk. Only calibration curves take the y=x diagonal.
- Never place a local split score beside a public leaderboard score.

## Style
- Prefer a stdlib solution over a dependency. Ask before adding any package.
- Keep functions short enough to read without scrolling.
- Write the test with the code, not after.
