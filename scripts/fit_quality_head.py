"""Fit a QuickQual head from SYNTHETIC degradations of calibration images.

    python scripts/fit_quality_head.py --images data/aptos/images/calib --out keys/qq.pkl

**This is a stand-in, and the head it produces is not a measured quality
model.** It exists because there is no quality-labelled corpus available
locally: EyeQ's labels reference EyePACS, which is ~89 GiB and out of scope for
this build. Without any head at all the gate correctly refuses to produce a
verdict, which means nothing downstream can be exercised end to end.

How the labels are made: each calibration image is kept as a positive
("usable") and a degraded copy is made as a negative. The degradations are
blur, under-exposure and a clipped field of view - the three faults the
classical reason-code channel names.

Two things this must never be confused with:

* It is **not** a gate fitted on real quality judgements. A human never looked
  at these images. The decision boundary reflects "can densenet features tell a
  Gaussian blur from no Gaussian blur", which is a far easier problem than
  real-world gradability.
* Any gate performance measured with it belongs in the SYNTHETIC table.
  `docs/rules/ml.md`: "keep real poor-quality images and synthetic
  degradations in SEPARATE tables. They are different distributions and
  pooling them is a validity error."

The head is written with a `synthetic` marker in its filename by default, so a
later reader cannot mistake the artifact for a released QuickQual pickle.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import pickle
import sys

import numpy as np

# `scripts/` is not a package, so the repo root has to go on sys.path.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from netra.models.dataset import collect
from netra.models.preprocess import load_image
from netra.models.quality import QualityGate, QuickQualFeatures

SEED = 20261027


def degrade(image: np.ndarray, kind: str, rng: np.random.Generator) -> np.ndarray:
    """One of the three faults the reason-code channel can explain."""
    import cv2

    if kind == "blur":
        k = int(rng.integers(9, 25)) * 2 + 1
        return cv2.GaussianBlur(image, (k, k), 0)
    if kind == "dark":
        factor = float(rng.uniform(0.08, 0.20))
        return np.clip(image.astype(np.float32) * factor, 0, 255).astype(np.uint8)
    if kind == "clipped":
        # Blank most of the frame, so the retina fraction collapses.
        out = image.copy()
        h = out.shape[0]
        out[: int(h * 0.62)] = 0
        return out
    raise ValueError(f"unknown degradation {kind!r}")


def build_training_set(
    images_dir: pathlib.Path, split: str, limit: int | None
) -> tuple[list[np.ndarray], list[int], dict]:
    examples, report = collect(split, images_dir, limit=limit)
    rng = np.random.default_rng(SEED)
    kinds = ("blur", "dark", "clipped")

    images: list[np.ndarray] = []
    labels: list[int] = []
    for i, example in enumerate(examples):
        raw = load_image(example.path)
        images.append(raw)
        labels.append(1)
        images.append(degrade(raw, kinds[i % len(kinds)], rng))
        labels.append(0)
    return images, labels, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--images", type=pathlib.Path, default=pathlib.Path("data/aptos/images/calib")
    )
    ap.add_argument("--split", default="calib", choices=["train", "calib"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument(
        "--out",
        type=pathlib.Path,
        default=pathlib.Path("data/quality_head_synthetic.pkl"),
    )
    ap.add_argument(
        "--random-init",
        action="store_true",
        help="random backbone weights, so the run never touches the network",
    )
    args = ap.parse_args(argv)

    images, labels, report = build_training_set(args.images, args.split, args.limit)
    print(json.dumps({"source_split": report}, indent=2))
    if not images:
        print(f"no images under {args.images}; nothing fitted", flush=True)
        return 2

    pretrained = not args.random_init
    gate = QualityGate(features=QuickQualFeatures(pretrained=pretrained), head=None)
    gate.fit(images, labels)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("wb") as fh:
        pickle.dump(gate.head, fh)

    print(
        json.dumps(
            {
                "n_positive": int(sum(labels)),
                "n_negative": int(len(labels) - sum(labels)),
                "backbone_pretrained": pretrained,
                "head": type(gate.head).__name__,
                "out": str(args.out),
            },
            indent=2,
        )
    )
    print(
        "\nSYNTHETIC head. A human never judged these images. Any gate number "
        "measured with it belongs in the synthetic table, never pooled with real "
        "poor-quality images (docs/rules/ml.md)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
