"""The DR classifier: `convnext_tiny.in12k_ft_in1k` at 512px, 5 classes.

SPEC.md section 2. This is explicitly **not** the project's contribution - it
is the thing the quality gate protects. Preprocessing is background removal +
resize only (see `netra/models/preprocess.py` for the ablation that settled
that).

Like the quality gate, this refuses rather than guesses: with no checkpoint
loaded, `DRClassifier.available` is False, `model_version` is `"unloaded"`, and
`predict_proba` RAISES. There is no code path that returns a grade from
untrained weights, because a grade from random weights is indistinguishable
from a real one downstream.

Expected QWK on a local APTOS split is 0.88-0.92 (SPEC.md). Anything above
0.95 means a leaked split, and `netra/eval/metrics.py` is where that number
comes from.
"""

from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass

import numpy as np

from netra.models.preprocess import IMAGE_SIZE, preprocess, to_model_tensor

BACKBONE = "convnext_tiny.in12k_ft_in1k"
N_CLASSES = 5
CHECKPOINT_ENV = "NETRA_DR_CHECKPOINT"
UNLOADED = "unloaded"


class ModelNotLoaded(RuntimeError):
    """Raised instead of returning a grade from weights that mean nothing."""


@dataclass(frozen=True)
class DRPrediction:
    """A 5-class distribution, as scaled integers.

    Probabilities are per-mille integers because these values travel into a
    ledger payload and floats are banned there (CLAUDE.md): `rfc8785` emits
    `{"n":1}` for `1.0` while `json.dumps` emits `{"n":1.0}`, which breaks a
    hash chain silently.
    """

    #: P(grade=k) * 1000, one per class, summing to ~1000.
    proba_milli: tuple[int, ...]
    model_version: str

    @property
    def argmax(self) -> int:
        return int(np.argmax(self.proba_milli))

    def as_float(self) -> np.ndarray:
        arr = np.asarray(self.proba_milli, dtype=float)
        return arr / arr.sum()


def build_model(pretrained: bool = True, num_classes: int = N_CLASSES):
    """Create the backbone with a fresh 5-class head.

    `pretrained=False` keeps the CPU smoke tests offline. It is recorded in
    `model_version`, so a smoke run can never be mistaken for a trained one.
    """
    import timm

    return timm.create_model(BACKBONE, pretrained=pretrained, num_classes=num_classes)


def proba_to_milli(proba: np.ndarray) -> tuple[int, ...]:
    """Float probabilities -> integers per mille that still sum to 1000.

    Naive rounding does not sum to 1000 (0.3335 x 3 rounds to 334+334+334=1002
    style drift), so the largest remainder takes the slack. A distribution that
    does not sum to 1000 would look like a bug in whatever reads the ledger.
    """
    proba = np.asarray(proba, dtype=float).ravel()
    total = proba.sum()
    if not np.isfinite(total) or total <= 0:
        raise ValueError("probabilities must be finite and positive")
    scaled = proba / total * 1000.0
    floors = np.floor(scaled).astype(int)
    slack = 1000 - int(floors.sum())
    if slack:
        order = np.argsort(-(scaled - floors))
        for i in order[:slack]:
            floors[i] += 1
    return tuple(int(v) for v in floors)


class DRClassifier:
    """The DR backbone behind an interface that cannot invent a grade."""

    def __init__(
        self,
        checkpoint: str | pathlib.Path | None = None,
        model=None,
        device: str = "cpu",
        pretrained_backbone: bool = False,
        trained: bool = False,
    ) -> None:
        self.device = device
        self.model = model
        self.checkpoint_path: pathlib.Path | None = None
        self.load_error: str | None = None
        #: Only ever True for weights that came from a real training run.
        self.trained = trained

        path = checkpoint or os.environ.get(CHECKPOINT_ENV)
        if self.model is None and path:
            candidate = pathlib.Path(path)
            if candidate.exists():
                try:
                    self._load(candidate, pretrained_backbone)
                except Exception as exc:  # noqa: BLE001 - reported, not raised
                    self.load_error = f"{type(exc).__name__}: {exc}"
                    self.model = None
            else:
                self.load_error = f"no checkpoint at {candidate}"

    def _load(self, path: pathlib.Path, pretrained_backbone: bool) -> None:
        import torch

        # weights_only=False because our own checkpoints carry a `trained`
        # flag and a `meta` dict alongside the tensors, and that flag is the
        # whole safeguard below. Only ever point this at a checkpoint this
        # project wrote.
        payload = torch.load(path, map_location=self.device, weights_only=False)
        if isinstance(payload, dict) and "state_dict" in payload:
            state = payload["state_dict"]
            # HONOUR the flag the writer set. `train.py --smoke` writes
            # `trained: false` after two steps, and without this line that
            # artifact loads and reports itself as a real model - which is
            # exactly the fabricated clinical output this lane must not ship.
            declared = payload.get("trained")
            self.trained = bool(declared) if declared is not None else False
        else:
            state = payload
            # A bare state_dict says nothing about its provenance, so it is
            # assumed untrained rather than assumed good.
            self.trained = False

        model = build_model(pretrained=pretrained_backbone)
        model.load_state_dict(state)
        model.eval().to(self.device)
        self.model = model
        self.checkpoint_path = path

    @property
    def available(self) -> bool:
        return self.model is not None

    @property
    def model_version(self) -> str:
        """Identifies the weights. `untrained` is never silently omitted."""
        if not self.available:
            return UNLOADED
        if not self.trained:
            return f"{BACKBONE}@{IMAGE_SIZE}:untrained"
        stem = self.checkpoint_path.stem if self.checkpoint_path else "in-memory"
        return f"{BACKBONE}@{IMAGE_SIZE}:{stem}"

    def predict_proba(self, image: np.ndarray) -> np.ndarray:
        """Raw float probabilities for one image. Raises if nothing is loaded."""
        if not self.available:
            raise ModelNotLoaded(
                "no DR checkpoint is loaded, so there is no grade to give. "
                f"Set {CHECKPOINT_ENV} to a trained checkpoint. "
                f"({self.load_error or 'no path supplied'})"
            )
        import torch

        processed, _ = preprocess(image)
        tensor = to_model_tensor(processed).to(self.device)
        with torch.no_grad():
            logits = self.model(tensor)
            proba = torch.softmax(logits, dim=1)
        return proba.cpu().numpy().ravel()

    def predict(self, image: np.ndarray) -> DRPrediction:
        """A ledger-safe prediction. Raises if nothing is loaded."""
        proba = self.predict_proba(image)
        return DRPrediction(
            proba_milli=proba_to_milli(proba), model_version=self.model_version
        )
