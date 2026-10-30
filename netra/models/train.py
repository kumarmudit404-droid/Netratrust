"""Fine-tune the DR backbone. Designed for a Kaggle T4; CPU-smokeable.

    # smoke, on CPU, a couple of steps on a handful of images
    python -m netra.models.train --smoke --images data/aptos/images/calib

    # the real run, on Kaggle (see notebooks/train_kaggle.ipynb)
    python -m netra.models.train --epochs 12 --batch-size 16

There is no GPU on the build box, so a full run never happens here. `--smoke`
exists to prove the loop executes - data loading, forward, loss, backward,
step, and a metric computed from `netra/eval/metrics.py` - not to produce a
model. A smoke checkpoint is written with `trained: false` in its payload so it
can never be mistaken for a real one.

Rules this file obeys and is easy to break:
* **Early stopping and model selection use the CALIBRATION split**, never test.
  `collect()` refuses `test` unless `allow_test=True`, which this script never
  passes.
* Every reported number comes from `netra/eval/metrics.py`.
* Augmentation and normalisation statistics are fixed constants, not fitted on
  the data, so there is nothing to leak across folds.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import time

import numpy as np

from netra.eval import metrics
from netra.models.dataset import collect, load_batch, to_tensors
from netra.models.dr import BACKBONE, N_CLASSES, build_model

SEED = 20261027


def set_seed(seed: int = SEED) -> None:
    import random

    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def evaluate(model, examples, batch_size: int, device: str) -> dict:
    """QWK and accuracy on a fold. Both come from metrics.py.

    Returns `qwk: None` when the fold holds a single grade - kappa is nan there
    and publishing nan as a number is worse than saying "not measurable".
    """
    import torch

    model.eval()
    preds: list[int] = []
    truths: list[int] = []
    with torch.no_grad():
        for start in range(0, len(examples), batch_size):
            chunk = examples[start : start + batch_size]
            images, labels = load_batch(chunk)
            batch, target = to_tensors(images, labels)
            logits = model(batch.to(device))
            preds.extend(logits.argmax(dim=1).cpu().numpy().tolist())
            truths.extend(target.numpy().tolist())

    if not preds:
        return {"n": 0, "qwk": None, "accuracy": None}

    y_true = np.asarray(truths)
    y_pred = np.asarray(preds)
    measurable = len(set(truths)) > 1
    return {
        "n": len(preds),
        "qwk": metrics.quadratic_weighted_kappa(y_true, y_pred, N_CLASSES)
        if measurable
        else None,
        "accuracy": float((y_true == y_pred).mean()),
    }


def train(
    images_dir: pathlib.Path,
    epochs: int = 12,
    batch_size: int = 16,
    lr: float = 3e-4,
    device: str = "cpu",
    smoke: bool = False,
    out: pathlib.Path | None = None,
    pretrained: bool = True,
    limit: int | None = None,
    splits_dir: pathlib.Path | None = None,
    manifest: pathlib.Path | None = None,
) -> dict:
    """Run training. In smoke mode this does 2 steps and stops.

    `splits_dir` and `manifest` default to the committed ones. The Kaggle run
    passes the grown pair written by `netra.models.splits` - still the same
    seed and the same folds for every image that already had one, just more
    of them. Without these arguments that run would train on the grown splits
    it thinks it chose and the 366-image manifest it actually read.
    """
    import torch
    from torch import nn

    set_seed()

    train_examples, train_report = collect(
        "train", images_dir, splits_dir=splits_dir, manifest=manifest, limit=limit
    )
    calib_examples, calib_report = collect(
        "calib", images_dir, splits_dir=splits_dir, manifest=manifest, limit=limit
    )
    # Retained fractions, out loud, before anything is trained.
    print(json.dumps({"train": train_report, "calib": calib_report}, indent=2))
    if not train_examples:
        raise SystemExit(
            f"no training images present under {images_dir}. "
            "Fetch some with scripts/fetch_aptos_images.py --split train"
        )

    # ---- SPEED (4-5x): preprocess every image ONCE and cache it, instead of
    # re-reading + re-cropping + re-resizing all ~2900 images EVERY epoch (the
    # CPU bottleneck that left the GPU idle). Byte-identical output; this only
    # changes WHEN the preprocessing happens, never WHAT it produces.
    import concurrent.futures

    from netra.models.preprocess import load_image, preprocess

    def _build_cache(examples):
        imgs: list = [None] * len(examples)

        def _one(i):
            processed, _ = preprocess(load_image(examples[i].path))
            imgs[i] = processed

        if examples:
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(_one, range(len(examples))))
            X = np.stack(imgs)
        else:
            X = np.empty((0, IMAGE_SIZE, IMAGE_SIZE, 3), dtype=np.uint8)
        y = np.asarray([e.label for e in examples], dtype=np.int64)
        return X, y

    _t0 = time.time()
    train_X, train_y = _build_cache(train_examples)
    calib_X, calib_y = _build_cache(calib_examples)
    print(
        f"cached {len(train_X)} train + {len(calib_X)} calib images once "
        f"in {time.time() - _t0:.1f}s"
    )

    model = build_model(pretrained=pretrained).to(device)

    # NOTE: single GPU on purpose. DataParallel made each step SLOWER here -
    # for a small model (ConvNeXt-tiny) the per-step replicate/scatter/gather
    # overhead outweighs the second GPU. The image cache + AMP are the real
    # speedups and both stay. One T4 at 512px/batch-16 fits comfortably.
    use_cuda = torch.cuda.is_available() and str(device).startswith("cuda")

    optimiser = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    # ---- SPEED: mixed precision (AMP) - ~1.5-2x on T4 tensor cores.
    scaler = torch.cuda.amp.GradScaler(enabled=use_cuda)

    # Inverse-frequency class weights, computed from the TRAIN split only.
    # Plain CrossEntropyLoss collapses to the majority grade on the
    # 327:66:215:36:60 imbalance (QWK 0.0). SPEC-safe: training-internal,
    # no new endpoint/state/dep; weights never touch the test split.
    _counts = np.bincount(
        [ex.label for ex in train_examples], minlength=N_CLASSES
    ).astype(float)
    _counts[_counts == 0] = 1.0
    _class_w = _counts.sum() / (len(_counts) * _counts)
    class_weights = torch.tensor(_class_w, dtype=torch.float32, device=device)
    print(json.dumps({"class_weights": [round(w, 4) for w in _class_w.tolist()]}))
    loss_fn = nn.CrossEntropyLoss(weight=class_weights)

    def _evaluate_cached(model, X, y, batch_size, device):
        """Calibration metrics from the cache. Same numbers as evaluate()."""
        model.eval()
        preds: list[int] = []
        with torch.no_grad():
            for s in range(0, len(X), batch_size):
                b, _ = to_tensors(X[s : s + batch_size], y[s : s + batch_size])
                with torch.cuda.amp.autocast(enabled=use_cuda):
                    logits = model(b.to(device))
                preds.extend(logits.argmax(dim=1).cpu().numpy().tolist())
        if not preds:
            return {"n": 0, "qwk": None, "accuracy": None}
        yt = np.asarray(y)
        yp = np.asarray(preds)
        measurable = len(set(yt.tolist())) > 1
        return {
            "n": len(preds),
            "qwk": metrics.quadratic_weighted_kappa(yt, yp, N_CLASSES)
            if measurable
            else None,
            "accuracy": float((yt == yp).mean()),
        }

    history: list[dict] = []
    best = {"qwk": -2.0, "epoch": -1}
    steps_done = 0
    started = time.time()

    for epoch in range(epochs):
        model.train()
        order = np.random.permutation(len(train_examples))
        epoch_loss = 0.0
        batches = 0

        for start in range(0, len(order), batch_size):
            idx = order[start : start + batch_size]
            batch, target = to_tensors(train_X[idx], train_y[idx])

            optimiser.zero_grad(set_to_none=True)
            with torch.cuda.amp.autocast(enabled=use_cuda):
                logits = model(batch.to(device))
                loss = loss_fn(logits, target.to(device))
            scaler.scale(loss).backward()
            scaler.step(optimiser)
            scaler.update()

            epoch_loss += float(loss.item())
            batches += 1
            steps_done += 1
            if smoke and steps_done >= 2:
                break

        entry = {
            "epoch": epoch,
            "train_loss": epoch_loss / max(batches, 1),
            "steps": steps_done,
        }
        if not smoke:
            # Model selection on CALIBRATION only. Never test.
            entry["calib"] = _evaluate_cached(model, calib_X, calib_y, batch_size, device)
            score = entry["calib"]["qwk"]
            if score is not None and score > best["qwk"]:
                best = {"qwk": score, "epoch": epoch}
                if out:
                    save(model, out, trained=True, meta=entry)
        history.append(entry)
        print(json.dumps(entry))

        if smoke and steps_done >= 2:
            break

    result = {
        "backbone": BACKBONE,
        "epochs_run": len(history),
        "steps": steps_done,
        "seconds": round(time.time() - started, 1),
        "smoke": smoke,
        "pretrained_backbone": pretrained,
        "best_calib": best if not smoke else None,
        "history": history,
        "train_report": train_report,
        "calib_report": calib_report,
    }
    if smoke and out:
        save(model, out, trained=False, meta=result)
    return result


def save(model, path: pathlib.Path, trained: bool, meta: dict | None = None) -> None:
    """Write a checkpoint that declares whether it is real.

    `trained: false` is what stops a 2-step smoke artifact being loaded later
    and reported as a model.
    """
    import torch

    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    state_dict = (
        model.module.state_dict() if hasattr(model, "module") else model.state_dict()
    )
    torch.save(
        {
            "state_dict": state_dict,
            "backbone": BACKBONE,
            "n_classes": N_CLASSES,
            "trained": trained,
            "meta": meta or {},
        },
        path,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--images", type=pathlib.Path, default=pathlib.Path("data/aptos/images/train")
    )
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument(
        "--splits-dir",
        type=pathlib.Path,
        default=None,
        help="frozen splits to read; defaults to the committed data/splits",
    )
    ap.add_argument(
        "--manifest",
        type=pathlib.Path,
        default=None,
        help="manifest to read labels from; defaults to data/manifest.csv",
    )
    ap.add_argument(
        "--smoke",
        action="store_true",
        help="two steps on a handful of images, to prove the loop runs",
    )
    ap.add_argument(
        "--random-init",
        action="store_true",
        help="skip pretrained weights, so the run never touches the network",
    )
    args = ap.parse_args(argv)

    result = train(
        images_dir=args.images,
        epochs=1 if args.smoke else args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        device=args.device,
        smoke=args.smoke,
        out=args.out,
        pretrained=not args.random_init,
        limit=args.limit,
        splits_dir=args.splits_dir,
        manifest=args.manifest,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "history"}, indent=2))
    if args.smoke:
        print("\nSMOKE ONLY - this is not a trained model. Train on Kaggle:")
        print("  notebooks/train_kaggle.ipynb")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
