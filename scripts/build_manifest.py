"""Build `data/manifest.csv` for `make_splits.py` from a corpus's own labels.

    python scripts/build_manifest.py --aptos data/aptos/test.csv --out data/manifest.csv

The manifest columns are fixed by `make_splits.py`:
`image_id, patient_id, source, label`.

**APTOS publishes no patient identifier.** It ships `id_code, diagnosis` and
nothing else, so `patient_id` is set to the image id. That makes the
patient-level guarantee in `.claude/rules/ml.md` VACUOUS for this corpus: the
splitter cannot keep a patient's images together because it cannot tell which
images share a patient. This is recorded rather than papered over — if two
APTOS rows are the same patient's two eyes, they can land in different folds
and nothing here would catch it. A corpus that does publish patient ids (IDRiD,
EyePACS) must pass the real one.

Every filtering step prints its retained fraction, per `.claude/rules/ml.md`:
"reasonable" preprocessing has been documented to silently discard 80-94% of
public corpora, and the only defence is counting out loud.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

VALID_LABELS = {"0", "1", "2", "3", "4"}


def read_aptos(path: Path) -> list[dict[str, str]]:
    """APTOS `id_code,diagnosis` -> manifest rows, counting what is dropped."""
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    if not rows:
        raise SystemExit(f"{path} has no rows")
    required = {"id_code", "diagnosis"}
    missing = required - set(rows[0])
    if missing:
        raise SystemExit(f"{path} missing columns: {sorted(missing)}")

    kept: list[dict[str, str]] = []
    dropped_label = 0
    dropped_dupe = 0
    seen: set[str] = set()
    for r in rows:
        image_id = r["id_code"].strip()
        label = r["diagnosis"].strip()
        if label not in VALID_LABELS:
            dropped_label += 1
            continue
        if image_id in seen:
            dropped_dupe += 1
            continue
        seen.add(image_id)
        kept.append(
            {
                "image_id": image_id,
                # No patient id exists in APTOS. See the module docstring.
                "patient_id": image_id,
                "source": "aptos",
                "label": label,
            }
        )

    print(f"aptos: read {len(rows)} rows from {path}")
    print(f"aptos: dropped {dropped_label} with a label outside 0-4")
    print(f"aptos: dropped {dropped_dupe} duplicate image_ids")
    print(f"aptos: retained {len(kept)}/{len(rows)} = {len(kept) / len(rows):.4f}")
    return kept


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aptos", type=Path, action="append", default=[])
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    rows: list[dict[str, str]] = []
    for path in args.aptos:
        rows.extend(read_aptos(path))

    if not rows:
        raise SystemExit("no rows; pass at least one --aptos CSV")

    # image_id must be globally unique across corpora, or a split lookup is
    # ambiguous. Prefix-free corpora are not guaranteed, so this is checked.
    ids = [r["image_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate image_id across corpora; prefix them by source")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["image_id", "patient_id", "source", "label"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["image_id"]))

    digest = hashlib.sha256(args.out.read_bytes()).hexdigest()
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
