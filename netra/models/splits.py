"""How the frozen splits are MADE. `netra/models/dataset.py` is how they are read.

`docs/rules/ml.md` says the splits are frozen and committed, never
regenerated and never re-shuffled. That rule is about not moving an image
between folds; it is not a rule against the corpus growing. The distinction
matters, so it is spelled out here and enforced by `check_preserved()`:

* **Re-shuffling** reassigns images that already had a fold. It silently
  re-contaminates every threshold already fitted on the old calibration fold,
  and nothing downstream can tell. This is what the rule forbids.
* **Growing** adds new images and leaves every existing assignment alone.
  `assign_fold()` is a pure function of `(seed, patient_id)` - a hash, not a
  shuffle - so an image's fold does not depend on which other images are in
  the manifest. `scripts/make_splits.py` has said so since it was written.

The second is only safe because the first is CHECKED, not assumed: anything
that grows the corpus must pass the old split files through
`check_preserved()` and get a clean report before writing a new one.

This module is importable (the notebook and the scripts both use it) and holds
the single copy of the bucketing arithmetic, so there is no second
implementation to drift.
"""

from __future__ import annotations

import csv
import hashlib
import json
import pathlib
from collections.abc import Iterable, Mapping, Sequence

#: Frozen 2026-10-27 with the first manifest. Changing it re-picks every fold.
SEED = 20261027
FRACTIONS: dict[str, float] = {"train": 0.60, "calib": 0.20, "test": 0.20}
SPLIT_NAMES: tuple[str, ...] = ("train", "calib", "test")
MANIFEST_COLUMNS: tuple[str, ...] = ("image_id", "patient_id", "source", "label")
VALID_LABELS = frozenset("01234")


class SplitDrift(RuntimeError):
    """An image that already had a fold would be moved to a different one."""


def bucket(patient_id: str, seed: int = SEED) -> float:
    """Deterministic hash of a patient to [0, 1).

    Depends on nothing but the seed and the patient id - not on the manifest,
    its order, or its size. That independence IS the growth guarantee.
    """
    digest = hashlib.sha256(f"{seed}:{patient_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def assign_fold(
    patient_id: str,
    seed: int = SEED,
    fractions: Mapping[str, float] | None = None,
) -> str:
    """Which fold a patient belongs to. Pure; no state, no shuffle."""
    fractions = fractions or FRACTIONS
    train_hi = fractions["train"]
    calib_hi = train_hi + fractions["calib"]
    b = bucket(patient_id, seed)
    if b < train_hi:
        return "train"
    return "calib" if b < calib_hi else "test"


def assign_many(
    rows: Iterable[Mapping[str, str]],
    seed: int = SEED,
    fractions: Mapping[str, float] | None = None,
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Manifest rows -> (`{fold: sorted image_ids}`, `{patient_id: fold}`)."""
    splits: dict[str, list[str]] = {name: [] for name in SPLIT_NAMES}
    patient_fold: dict[str, str] = {}
    for row in rows:
        pid = row["patient_id"]
        fold = patient_fold.get(pid)
        if fold is None:
            fold = assign_fold(pid, seed, fractions)
            patient_fold[pid] = fold
        splits[fold].append(row["image_id"])
    return {name: sorted(ids) for name, ids in splits.items()}, patient_fold


def read_splits(directory: pathlib.Path) -> dict[str, list[str]]:
    """Read `{fold}.json` for every fold present. Missing folds are omitted."""
    directory = pathlib.Path(directory)
    out: dict[str, list[str]] = {}
    for name in SPLIT_NAMES:
        path = directory / f"{name}.json"
        if path.exists():
            out[name] = json.loads(path.read_text())
    return out


def check_preserved(
    old: Mapping[str, Sequence[str]],
    new: Mapping[str, Sequence[str]],
) -> dict:
    """Assert that growing the corpus moved nothing. Raises `SplitDrift` if it did.

    Also refuses a shrink: an image that HAD a fold and is now in none of them
    has been dropped, and a dropped calibration image is as invisible a change
    as a moved one.
    """
    old_fold = {i: name for name, ids in old.items() for i in ids}
    new_fold = {i: name for name, ids in new.items() for i in ids}

    moved = sorted(i for i, f in old_fold.items() if new_fold.get(i, f) != f)
    dropped = sorted(i for i in old_fold if i not in new_fold)
    if moved:
        detail = ", ".join(f"{i}: {old_fold[i]}->{new_fold[i]}" for i in moved[:5])
        raise SplitDrift(
            f"{len(moved)} image(s) would change fold, which re-contaminates "
            f"anything already fitted on the old calibration fold: {detail}"
        )
    if dropped:
        raise SplitDrift(
            f"{len(dropped)} image(s) had a fold and now have none: {dropped[:5]}"
        )

    added = sorted(i for i in new_fold if i not in old_fold)
    return {
        "n_old": len(old_fold),
        "n_new": len(new_fold),
        "n_preserved": len(old_fold),
        "n_added": len(added),
        "added_per_fold": {
            name: sum(1 for i in added if new_fold[i] == name) for name in SPLIT_NAMES
        },
        "moved": 0,
        "dropped": 0,
    }


# ------------------------------------------------------------------ manifests


def read_aptos_labels(path: pathlib.Path) -> tuple[list[dict[str, str]], dict]:
    """APTOS `id_code,diagnosis` -> manifest rows, counting what is dropped.

    **APTOS publishes no patient identifier.** It ships `id_code, diagnosis`
    and nothing else, so `patient_id` is set to the image id. That makes the
    patient-level guarantee in `docs/rules/ml.md` VACUOUS for this corpus:
    the splitter cannot keep a patient's images together because it cannot tell
    which images share a patient. Recorded rather than papered over. A corpus
    that does publish patient ids (IDRiD, EyePACS) must pass the real one.

    Returns `(rows, report)`; the report carries the retained fraction, per
    `docs/rules/ml.md`.
    """
    path = pathlib.Path(path)
    with path.open(newline="", encoding="utf-8") as fh:
        raw = list(csv.DictReader(fh))
    if not raw:
        raise ValueError(f"{path} has no rows")
    missing = {"id_code", "diagnosis"} - set(raw[0])
    if missing:
        raise ValueError(f"{path} missing columns: {sorted(missing)}")

    kept: list[dict[str, str]] = []
    dropped_label = 0
    dropped_dupe = 0
    seen: set[str] = set()
    for r in raw:
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
                "patient_id": image_id,  # see the docstring
                "source": "aptos",
                "label": label,
            }
        )
    report = {
        "file": str(path),
        "n_rows": len(raw),
        "dropped_bad_label": dropped_label,
        "dropped_duplicate_id": dropped_dupe,
        "n_kept": len(kept),
        "retained_fraction": len(kept) / len(raw),
    }
    return kept, report


def merge_manifest_rows(
    groups: Iterable[Sequence[Mapping[str, str]]],
) -> list[dict[str, str]]:
    """Concatenate label-file outputs, dropping ids already seen.

    The APTOS mirrors overlap: `train.csv` and `test.csv` of one split mirror
    are disjoint, but the competition's full `train.csv` is a SUPERSET of a
    mirror's `test.csv`. So "already seen" is normal here and is counted, not
    treated as an error - but a repeated id carrying a DIFFERENT label is a
    real contradiction and raises rather than silently keeping one of them.
    """
    out: list[dict[str, str]] = []
    by_id: dict[str, dict[str, str]] = {}
    for group in groups:
        for row in group:
            prior = by_id.get(row["image_id"])
            if prior is None:
                by_id[row["image_id"]] = dict(row)
                out.append(by_id[row["image_id"]])
            elif prior["label"] != row["label"]:
                raise ValueError(
                    f"{row['image_id']} has label {prior['label']} in one file "
                    f"and {row['label']} in another; refusing to pick one"
                )
    return sorted(out, key=lambda r: r["image_id"])


def write_manifest(rows: Sequence[Mapping[str, str]], path: pathlib.Path) -> str:
    """Write the manifest and return its sha256, which goes into `meta.json`."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(MANIFEST_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest()


#: A label file we can read has these two columns in its header.
APTOS_COLUMNS = frozenset({"id_code", "diagnosis"})
#: Directory names never worth walking on a Kaggle mount.
SKIP_DIRS = frozenset({".git", "__pycache__", "node_modules", ".ipynb_checkpoints"})


def find_aptos_label_csvs(root: pathlib.Path, max_depth: int = 4) -> list[pathlib.Path]:
    """Every CSV under `root` whose header is APTOS's `id_code,diagnosis`.

    Found by reading the header, not by guessing at filenames: the mirrors
    disagree about whether the full labels live in `train.csv`, `train_1.csv`
    or `labels.csv`, and a filename match would pick up `sample_submission.csv`,
    whose second column is a prediction rather than a diagnosis.
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


def check_labels_agree(
    old_rows: Sequence[Mapping[str, str]], new_rows: Sequence[Mapping[str, str]]
) -> dict:
    """The new manifest must be a SUPERSET of the old one, with equal labels.

    A relabelled image is not growth. It changes what the old calibration fold
    MEANS without changing which images are in it, which is exactly the kind
    of drift nothing downstream would notice.
    """
    new_by_id = {r["image_id"]: r for r in new_rows}
    missing = [r["image_id"] for r in old_rows if r["image_id"] not in new_by_id]
    relabelled = [
        (r["image_id"], r["label"], new_by_id[r["image_id"]]["label"])
        for r in old_rows
        if r["image_id"] in new_by_id
        and new_by_id[r["image_id"]]["label"] != r["label"]
    ]
    if missing:
        raise ValueError(
            f"the new label files are missing {len(missing)} image(s) the old "
            f"manifest has, so this is not a superset: {missing[:5]}"
        )
    if relabelled:
        raise ValueError(
            f"{len(relabelled)} image(s) changed label between the old manifest "
            f"and the new label files: {relabelled[:5]}"
        )
    return {"n_old_rows": len(old_rows), "missing": 0, "relabelled": 0}


def read_manifest_rows(path: pathlib.Path) -> list[dict[str, str]]:
    with pathlib.Path(path).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if rows:
        missing = set(MANIFEST_COLUMNS) - set(rows[0])
        if missing:
            raise ValueError(f"manifest missing columns: {sorted(missing)}")
    return rows


def write_splits(
    splits: Mapping[str, Sequence[str]],
    out_dir: pathlib.Path,
    manifest_sha256: str,
    seed: int = SEED,
    fractions: Mapping[str, float] | None = None,
    patient_fold: Mapping[str, str] | None = None,
) -> dict:
    """Write `{fold}.json` + `meta.json` in the committed format. Returns meta."""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, ids in splits.items():
        (out_dir / f"{name}.json").write_text(json.dumps(sorted(ids), indent=1))

    n_patients = {name: 0 for name in SPLIT_NAMES}
    for fold in (patient_fold or {}).values():
        n_patients[fold] += 1

    meta = {
        "seed": seed,
        "fractions": dict(fractions or FRACTIONS),
        "method": "sha256 patient-level hash bucketing",
        "n_images": {k: len(v) for k, v in splits.items()},
        "n_patients": n_patients
        if patient_fold
        else {k: len(v) for k, v in splits.items()},
        "manifest_sha256": manifest_sha256,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    return meta
