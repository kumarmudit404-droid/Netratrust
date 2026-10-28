"""Dataset over a frozen split. Reads splits; never creates them.

`.claude/rules/ml.md`: "Splits come from `data/splits/*.json`. They are frozen
and committed. Never regenerate them, never re-shuffle, never call
`train_test_split` in model or eval code." So this module takes a split NAME
and refuses anything else - there is no shuffle, no ratio argument, and no way
to ask it for a split that is not on disk.

Loading the **test** split requires `allow_test=True`, passed explicitly. The
test split is touched exactly once, at the end, and an accidental
`split="test"` in a training script is precisely the mistake that is invisible
afterwards.
"""

from __future__ import annotations

import csv
import json
import pathlib
from dataclasses import dataclass

import numpy as np

from netra.models.preprocess import IMAGE_SIZE, load_image, preprocess

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_SPLITS = REPO_ROOT / "data" / "splits"
DEFAULT_MANIFEST = REPO_ROOT / "data" / "manifest.csv"
VALID_SPLITS = ("train", "calib", "test")

#: Tried in order for a given image id. The APTOS mirrors disagree: the
#: competition archive ships `.png`, several resized mirrors ship `.jpg`.
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
SKIP_DIRS = {"__pycache__", ".ipynb_checkpoints", "node_modules", ".git"}


@dataclass(frozen=True)
class Example:
    image_id: str
    label: int
    source: str
    path: pathlib.Path


class SplitNotAvailable(FileNotFoundError):
    pass


def read_manifest(path: pathlib.Path | None = None) -> dict[str, dict[str, str]]:
    path = pathlib.Path(path or DEFAULT_MANIFEST)
    if not path.exists():
        raise SplitNotAvailable(f"no manifest at {path}; run scripts/build_manifest.py")
    with path.open(newline="", encoding="utf-8") as fh:
        return {r["image_id"]: r for r in csv.DictReader(fh)}


def read_split(name: str, splits_dir: pathlib.Path | None = None) -> list[str]:
    if name not in VALID_SPLITS:
        raise ValueError(f"split must be one of {VALID_SPLITS}, got {name!r}")
    path = pathlib.Path(splits_dir or DEFAULT_SPLITS) / f"{name}.json"
    if not path.exists():
        raise SplitNotAvailable(f"no frozen split at {path}")
    return json.loads(path.read_text())


def find_images_dir(
    image_ids: list[str],
    search_root: pathlib.Path,
    min_hits: int = 20,
    max_depth: int = 6,
) -> list[tuple[pathlib.Path, int]]:
    """Directories under `search_root` holding files named for these ids.

    The Kaggle mount point for APTOS depends on which dataset was attached,
    and the mirrors lay out differently (`train_images/train_images/`,
    `images/`, a flat root). Rather than hardcode one and fail with
    `retained_fraction: 0.0` after a long walk, the directory is DISCOVERED by
    asking which one actually contains the ids in the frozen splits, and the
    candidates are returned with their hit counts so a human can see the
    choice. Most hits first.
    """
    wanted = set(image_ids)
    if not wanted:
        return []
    search_root = pathlib.Path(search_root)
    if not search_root.exists():
        return []

    root_depth = len(search_root.parts)
    hits: dict[pathlib.Path, int] = {}
    for path in search_root.rglob("*"):
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if len(path.parts) - root_depth > max_depth:
            continue
        if path.stem in wanted:
            hits[path.parent] = hits.get(path.parent, 0) + 1
    return sorted(
        ((d, n) for d, n in hits.items() if n >= min_hits),
        key=lambda pair: (-pair[1], str(pair[0])),
    )


def resolve_image_path(images_dir: pathlib.Path, image_id: str) -> pathlib.Path | None:
    """The first existing `<images_dir>/<image_id><ext>`, or None."""
    for extension in IMAGE_EXTENSIONS:
        candidate = images_dir / f"{image_id}{extension}"
        if candidate.exists():
            return candidate
    return None


def collect(
    name: str,
    images_dir: pathlib.Path,
    splits_dir: pathlib.Path | None = None,
    manifest: pathlib.Path | None = None,
    allow_test: bool = False,
    limit: int | None = None,
) -> tuple[list[Example], dict]:
    """Examples for a split whose image files are actually present.

    Returns `(examples, report)`. The report carries the retained fraction,
    because a split of 75 ids with 4 images on disk silently becomes a 4-image
    experiment otherwise - the exact failure `.claude/rules/ml.md` warns about.
    """
    if name == "test" and not allow_test:
        raise PermissionError(
            "the test split is touched exactly once, at the end "
            "(.claude/rules/ml.md). Pass allow_test=True only for that run."
        )

    ids = read_split(name, splits_dir)
    rows = read_manifest(manifest)
    images_dir = pathlib.Path(images_dir)

    examples: list[Example] = []
    missing_file = 0
    missing_row = 0
    for image_id in ids:
        row = rows.get(image_id)
        if row is None:
            missing_row += 1
            continue
        path = resolve_image_path(images_dir, image_id)
        if path is None:
            missing_file += 1
            continue
        examples.append(
            Example(
                image_id=image_id,
                label=int(row["label"]),
                source=row["source"],
                path=path,
            )
        )
        if limit is not None and len(examples) >= limit:
            break

    labels = [e.label for e in examples]
    report = {
        "split": name,
        "n_in_split": len(ids),
        "n_present": len(examples),
        "retained_fraction": len(examples) / len(ids) if ids else 0.0,
        "missing_image_file": missing_file,
        "missing_manifest_row": missing_row,
        "label_counts": {
            str(k): int(v)
            for k, v in zip(*np.unique(labels, return_counts=True), strict=True)
        }
        if labels
        else {},
    }
    return examples, report


def load_batch(
    examples: list[Example], size: int = IMAGE_SIZE
) -> tuple[np.ndarray, np.ndarray]:
    """Preprocess a list of examples into (N,H,W,3) uint8 and (N,) int labels."""
    images, labels = [], []
    for example in examples:
        processed, _ = preprocess(load_image(example.path), size)
        images.append(processed)
        labels.append(example.label)
    if not images:
        return np.empty((0, size, size, 3), dtype=np.uint8), np.empty((0,), dtype=int)
    return np.stack(images), np.asarray(labels, dtype=int)


def to_tensors(images: np.ndarray, labels: np.ndarray):
    """(N,H,W,3) uint8 -> a normalised NCHW float tensor plus a label tensor."""
    import torch

    from netra.models.preprocess import to_model_tensor

    if len(images) == 0:
        return torch.empty(0), torch.empty(0, dtype=torch.long)
    batch = torch.cat([to_model_tensor(img) for img in images], dim=0)
    return batch, torch.from_numpy(np.asarray(labels, dtype=np.int64))
