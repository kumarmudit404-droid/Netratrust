"""Grow the frozen splits to the full APTOS corpus WITHOUT moving any image.

    python scripts/extend_splits.py \
        --search-root /kaggle/input \
        --old-splits data/splits \
        --out-manifest /kaggle/working/manifest_full.csv \
        --out-splits   /kaggle/working/splits_full

Why this exists. The committed splits were frozen over 366 APTOS images -
the 366 rows of one mirror's `test.csv`, which was all a CPU build box could
fetch per-file. 219 training images cannot reach the QWK 0.88-0.92 that
SPEC.md section 2 expects, and the whole corpus (3,662 labelled images) is
already mounted on Kaggle. So the corpus grows there.

Growing is not re-shuffling, and the difference is the whole point:
`netra.models.splits.assign_fold` is a pure function of `(seed, patient_id)`,
so an image's fold does not depend on what else is in the manifest. Every one
of the 366 images that already had a fold keeps it. That is **checked**, not
asserted in prose - `check_preserved()` raises `SplitDrift` and this script
writes nothing if a single image would move or disappear.

What this script will NOT do:
* change the seed (20261027) or the fractions - either re-picks every fold;
* write over `data/splits/` by default - it writes somewhere you name, and you
  commit the result deliberately, because `.claude/rules/ml.md` makes the
  splits a committed artifact and rules.md section 6 makes changing them a
  team decision;
* touch the test split's CONTENTS in any way a reader could not reproduce from
  the seed alone.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

# `scripts/` is not a package and this file imports `netra`, so the repo root
# has to be on sys.path when it is run directly as `python scripts/...`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from netra.models.splits import (
    SEED,
    SplitDrift,
    assign_many,
    check_labels_agree,
    check_preserved,
    find_aptos_label_csvs,
    merge_manifest_rows,
    read_aptos_labels,
    read_manifest_rows,
    read_splits,
    write_manifest,
    write_splits,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--aptos-csv",
        type=pathlib.Path,
        action="append",
        default=[],
        help="an APTOS id_code,diagnosis label file; repeatable",
    )
    ap.add_argument(
        "--search-root",
        type=pathlib.Path,
        default=None,
        help="walk this directory for APTOS label files (e.g. /kaggle/input)",
    )
    ap.add_argument(
        "--old-splits", type=pathlib.Path, default=pathlib.Path("data/splits")
    )
    ap.add_argument("--old-manifest", type=pathlib.Path, default=None)
    ap.add_argument("--out-manifest", type=pathlib.Path, required=True)
    ap.add_argument("--out-splits", type=pathlib.Path, required=True)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would change and write nothing",
    )
    args = ap.parse_args(argv)

    label_files = list(args.aptos_csv)
    if args.search_root:
        discovered = find_aptos_label_csvs(args.search_root)
        print(
            f"searched {args.search_root}: found {len(discovered)} APTOS label file(s)"
        )
        for path in discovered:
            print(f"  {path}")
        label_files += [p for p in discovered if p not in label_files]
    if not label_files:
        print(
            "no APTOS label file found. Pass --aptos-csv, or --search-root at a "
            "directory that holds one (header: id_code,diagnosis).",
            file=sys.stderr,
        )
        return 2

    groups = []
    for path in label_files:
        rows, report = read_aptos_labels(path)
        print(json.dumps(report, indent=2))
        groups.append(rows)
    rows = merge_manifest_rows(groups)
    print(f"\nmerged to {len(rows)} unique images across {len(label_files)} file(s)")

    old_manifest = args.old_manifest
    if old_manifest is None:
        candidate = pathlib.Path("data/manifest.csv")
        old_manifest = candidate if candidate.exists() else None
    if old_manifest is not None:
        try:
            agreement = check_labels_agree(read_manifest_rows(old_manifest), rows)
        except ValueError as exc:
            print(f"\nREFUSING TO WRITE: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(agreement, indent=2))
    else:
        print(
            "no old manifest to compare against (data/manifest.csv is gitignored); "
            "the split-level check below is the one that matters anyway"
        )

    new_splits, patient_fold = assign_many(rows, seed=args.seed)
    old = read_splits(args.old_splits)
    if not old:
        print(
            f"no old splits under {args.old_splits}; nothing to preserve",
            file=sys.stderr,
        )
        return 2

    try:
        preserved = check_preserved(old, new_splits)
    except SplitDrift as exc:
        print(f"\nREFUSING TO WRITE: {exc}", file=sys.stderr)
        return 1

    print("\nevery image that already had a fold still has the same one:")
    print(json.dumps(preserved, indent=2))
    print(
        json.dumps(
            {"new_n_images": {k: len(v) for k, v in new_splits.items()}}, indent=2
        )
    )

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    digest = write_manifest(rows, args.out_manifest)
    meta = write_splits(
        new_splits,
        args.out_splits,
        manifest_sha256=digest,
        seed=args.seed,
        patient_fold=patient_fold,
    )
    print(f"\nwrote {args.out_manifest} (sha256 {digest})")
    print(f"wrote {args.out_splits}/")
    print(json.dumps(meta, indent=2))
    print(
        "\nThese are now the frozen splits for the larger corpus. Commit BOTH "
        "the new data/splits/*.json and the manifest hash in meta.json, in one "
        "commit, with the preservation report above in the message."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
