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
