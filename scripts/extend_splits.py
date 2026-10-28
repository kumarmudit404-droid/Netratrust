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
import csv
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
    check_preserved,
    merge_manifest_rows,
    read_aptos_labels,
    read_manifest_rows,
    read_splits,
    write_manifest,
    write_splits,
)

#: A label file we can read has exactly these two columns in its header.
APTOS_COLUMNS = {"id_code", "diagnosis"}
#: Directory names that are never worth walking on Kaggle.
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".ipynb_checkpoints"}


def find_aptos_label_csvs(root: pathlib.Path, max_depth: int = 4) -> list[pathlib.Path]:
    """Every CSV under `root` whose header is APTOS's `id_code,diagnosis`.

    Found by reading the header, not by guessing at filenames: the mirrors
    disagree about whether the full labels live in `train.csv`, `train_1.csv`
    or `labels.csv`, and a filename match would pick up a submission template.
    """
    root = pathlib.Path(root)
    found: list[pathlib.Path] = []
    if not root.exists():
        return found
    root_depth = len(root.parts)
    for path in sorted(root.rglob("*.csv")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if len(path.parts) - root_depth > max_depth:
            continue
        try:
            with path.open(newline="", encoding="utf-8") as fh:
                header = next(csv.reader(fh), [])
        except (OSError, UnicodeDecodeError):
            continue
        if APTOS_COLUMNS <= {h.strip() for h in header}:
            found.append(path)
    return found


def check_old_manifest_agrees(
    old_manifest: pathlib.Path, rows: list[dict[str, str]]
) -> dict:
    """The new manifest must be a SUPERSET of the old one, with equal labels.

    A relabelled image is not growth. It changes what the old calibration fold
    meant without changing which images are in it, which is exactly the kind of
    drift nothing downstream would notice.
    """
    old_rows = read_manifest_rows(old_manifest)
    new_by_id = {r["image_id"]: r for r in rows}
    missing = [r["image_id"] for r in old_rows if r["image_id"] not in new_by_id]
    relabelled = [
        (r["image_id"], r["label"], new_by_id[r["image_id"]]["label"])
        for r in old_rows
        if r["image_id"] in new_by_id
        and new_by_id[r["image_id"]]["label"] != r["label"]
    ]
    if missing:
        raise SystemExit(
            f"the new label files are missing {len(missing)} image(s) that the "
            f"old manifest has, so this is not a superset: {missing[:5]}"
        )
    if relabelled:
        raise SystemExit(
            f"{len(relabelled)} image(s) changed label between the old manifest "
            f"and the new label files: {relabelled[:5]}"
        )
    return {"n_old_rows": len(old_rows), "missing": 0, "relabelled": 0}


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
        print(json.dumps(check_old_manifest_agrees(old_manifest, rows), indent=2))
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
