"""Build `data/manifest.csv` for `make_splits.py` from a corpus's own labels.

    python scripts/build_manifest.py --aptos data/aptos/test.csv --out data/manifest.csv

The manifest columns are fixed by `make_splits.py`:
`image_id, patient_id, source, label`.

**APTOS publishes no patient identifier.** The consequences are spelled out in
`netra.models.splits.read_aptos_labels`, which is where the reading now lives
so that this script, `scripts/extend_splits.py` and the Kaggle notebook share
one implementation.

Every filtering step prints its retained fraction, per `.claude/rules/ml.md`:
"reasonable" preprocessing has been documented to silently discard 80-94% of
public corpora, and the only defence is counting out loud.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

# `scripts/` is not a package and this file imports `netra`, so the repo root
# has to be on sys.path when it is run directly as `python scripts/...`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from netra.models.splits import (
    merge_manifest_rows,
    read_aptos_labels,
    write_manifest,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aptos", type=pathlib.Path, action="append", default=[])
    ap.add_argument("--out", required=True, type=pathlib.Path)
    args = ap.parse_args()

    groups = []
    for path in args.aptos:
        try:
            rows, report = read_aptos_labels(path)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        print(f"aptos: read {report['n_rows']} rows from {path}")
        print(f"aptos: dropped {report['dropped_bad_label']} with a label outside 0-4")
        print(f"aptos: dropped {report['dropped_duplicate_id']} duplicate image_ids")
        print(
            f"aptos: retained {report['n_kept']}/{report['n_rows']} = "
            f"{report['retained_fraction']:.4f}"
        )
        groups.append(rows)

    if not groups:
        raise SystemExit("no rows; pass at least one --aptos CSV")
    rows = merge_manifest_rows(groups)
    if not rows:
        raise SystemExit("no rows survived; nothing to write")

    digest = write_manifest(rows, args.out)

    by_label: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for r in rows:
        by_label[r["label"]] = by_label.get(r["label"], 0) + 1
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1

    print(f"\nwrote {args.out} ({len(rows)} rows)")
    print(f"sha256 {digest}")
    print(f"labels {dict(sorted(by_label.items()))}")
    print(f"sources {dict(sorted(by_source.items()))}")
    print("\nNow freeze the splits:")
    print(f"  python scripts/make_splits.py --manifest {args.out} --out data/splits")


if __name__ == "__main__":
    main()
