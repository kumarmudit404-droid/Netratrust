---
paths: ["netra/models/**", "netra/eval/**", "notebooks/**"]
---

# ML rules

- Splits come from `data/splits/*.json`. They are frozen and committed. Never
  regenerate them, never re-shuffle, never call `train_test_split` in model or
  eval code.
- Splits are patient-level and source-preserved. One patient never appears in
  two splits; one source corpus never spans two folds.
- All preprocessing statistics are fitted inside the training fold only.
- The test split is touched exactly once, at the end. Thresholds, early
  stopping, and abstention levels are set on the calibration split.
- Every metric comes from `netra/eval/metrics.py`. Do not compute a metric
  inline in a notebook or a route handler and report it.
- Report the retained fraction at every filtering step. "Reasonable"
  preprocessing has been documented to silently discard 80-94% of public
  corpora.
- When reporting gate performance, keep real poor-quality images and synthetic
  degradations in SEPARATE tables. They are different distributions and
  pooling them is a validity error.
