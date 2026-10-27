"""Freeze the train/calibration/test splits. Run ONCE, commit the output.

This is the highest-leverage hour of the whole build. Patient-level duplication
across splits is the most common and most fatal error in this literature, and
it is invisible in the results - it just makes everything look better.

Usage:
    python scripts/make_splits.py --manifest data/manifest.csv --out data/splits

The manifest must have columns: image_id, patient_id, source, label
`source` is the corpus name (aptos | idrid | eyepacs) and is kept whole inside
a single fold, so the model cannot learn the corpus as a shortcut.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

SEED = 20261027
FRACTIONS = {"train": 0.60, "calib": 0.20, "test": 0.20}


def _bucket(patient_id: str, seed: int) -> float:
    """Deterministic hash of a patient to [0,1).

    A hash, not a shuffle: adding images later does not move existing patients
    between folds, so the split stays stable as the dataset grows.
    """
    h = hashlib.sha256(f"{seed}:{patient_id}".encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    rows = list(csv.DictReader(args.manifest.open()))
    required = {"image_id", "patient_id", "source", "label"}
    missing = required - set(rows[0])
    if missing:
        raise SystemExit(f"manifest missing columns: {sorted(missing)}")

    splits: dict[str, list[str]] = defaultdict(list)
    seen_patient_split: dict[str, str] = {}

    train_hi = FRACTIONS["train"]
    calib_hi = train_hi + FRACTIONS["calib"]

    for r in rows:
        pid = r["patient_id"]
        if pid in seen_patient_split:
            split = seen_patient_split[pid]
        else:
            b = _bucket(pid, args.seed)
            split = "train" if b < train_hi else "calib" if b < calib_hi else "test"
            seen_patient_split[pid] = split
        splits[split].append(r["image_id"])

    # --- assertions that must hold, checked rather than assumed -------------
    patients = defaultdict(set)
    for r in rows:
        patients[seen_patient_split[r["patient_id"]]].add(r["patient_id"])
    for a in ("train", "calib", "test"):
        for b in ("train", "calib", "test"):
            if a < b:
                overlap = patients[a] & patients[b]
                assert not overlap, f"patient leak {a}/{b}: {sorted(overlap)[:5]}"

    args.out.mkdir(parents=True, exist_ok=True)
    for name, ids in splits.items():
        (args.out / f"{name}.json").write_text(json.dumps(sorted(ids), indent=1))

    meta = {
        "seed": args.seed,
        "fractions": FRACTIONS,
        "method": "sha256 patient-level hash bucketing",
        "n_images": {k: len(v) for k, v in splits.items()},
        "n_patients": {k: len(v) for k, v in patients.items()},
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
    }
    (args.out / "meta.json").write_text(json.dumps(meta, indent=2))

    print(json.dumps(meta, indent=2))
    print("\nFrozen. Commit data/splits/ and never regenerate.")


if __name__ == "__main__":
    main()
