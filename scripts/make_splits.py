"""Freeze the train/calibration/test splits. Run ONCE, commit the output.

Patient-level duplication across splits is the most common and most fatal
error in this literature, and it is invisible in the results - it just makes
everything look better. That is why this is a separate frozen step and not
something the training code does for itself.

Usage:
    python scripts/make_splits.py --manifest data/manifest.csv --out data/splits

The manifest must have columns: image_id, patient_id, source, label
`source` is the corpus name (aptos | idrid | eyepacs) and is kept whole inside
a single fold, so the model cannot learn the corpus as a shortcut.

The bucketing itself lives in `netra/models/splits.py`, so the notebook, this
script and `scripts/extend_splits.py` all share one implementation and cannot
drift apart. A hash, not a shuffle: adding images later does not move existing
patients between folds, so the split stays stable as the dataset grows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from collections import defaultdict

# `scripts/` is not a package and this file imports `netra`, so the repo root
# has to be on sys.path when it is run directly as `python scripts/...`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from netra.models.splits import (
    FRACTIONS,
    MANIFEST_COLUMNS,
    SEED,
    SPLIT_NAMES,
    assign_many,
    read_manifest_rows,
    write_splits,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    try:
        rows = read_manifest_rows(args.manifest)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not rows:
        raise SystemExit(f"{args.manifest} has no rows")
    missing = set(MANIFEST_COLUMNS) - set(rows[0])
    if missing:
        raise SystemExit(f"manifest missing columns: {sorted(missing)}")

    splits, patient_fold = assign_many(rows, seed=args.seed)

    # --- assertions that must hold, checked rather than assumed -------------
    patients: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        patients[patient_fold[r["patient_id"]]].add(r["patient_id"])
    for a in SPLIT_NAMES:
        for b in SPLIT_NAMES:
            if a < b:
                overlap = patients[a] & patients[b]
                assert not overlap, f"patient leak {a}/{b}: {sorted(overlap)[:5]}"

    digest = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    meta = write_splits(
        splits,
        args.out,
        manifest_sha256=digest,
        seed=args.seed,
        patient_fold=patient_fold,
    )

    print(json.dumps(meta, indent=2))
    print("\nFrozen. Commit data/splits/ and never regenerate.")
    print(f"(fractions {FRACTIONS}; growing the corpus is scripts/extend_splits.py)")


if __name__ == "__main__":
    main()
