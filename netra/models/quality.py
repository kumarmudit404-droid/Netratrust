"""The image-quality gate: QuickQual.

SPEC.md section 1. Frozen `densenet121.tv_in1k` features at 512px with mean/std
0.5, plus a small SVM head. Published EyeQ test accuracy 0.886, AUC 0.9687,
kappa 0.811 - **those are the paper's numbers on EyeQ, not ours**, and nothing
in this file may be reported as a local measurement until it is measured on a
local split.

Verdict mapping, from `config/thresholds.yaml`:

    p_usable >= quality_gate.usable_min_p   -> usable
    p_usable <= quality_gate.reject_max_p   -> reject
    otherwise                               -> borderline

**If no head is available the gate returns `state="unavailable"` and
`verdict=None`.** It does not guess, and it does not default to `usable`. A
fabricated verdict here is the worst failure this project can have: the gate is
the thing that decides whether a patient's image becomes a grade at all, and
"usable" is the answer that lets an ungradable image through into a referral.

The head is resolved in this order:
 1. `NETRA_QUICKQUAL_SVM` (or the `svm_path` argument) - the released pickle.
 2. A head fitted locally by `fit()` on quality-labelled data.
 3. QuickQual-MEME, the 10-parameter fallback - **not implemented**, see below.
 4. Nothing: `state="unavailable"`.
"""

from __future__ import annotations

import os
import pathlib
import pickle
from dataclasses import dataclass
from typing import Any

import numpy as np

from netra.models import reason_codes
from netra.models.preprocess import IMAGE_SIZE, preprocess, to_model_tensor
from netra.models.thresholds import quality_cutoffs

#: SPEC.md section 1. Frozen - never fine-tuned, so the features are the
#: paper's features and the only fitted part is the small head.
BACKBONE = "densenet121.tv_in1k"

VERDICT_USABLE = "usable"
VERDICT_BORDERLINE = "borderline"
VERDICT_REJECT = "reject"

STATE_OK = "ok"
STATE_UNAVAILABLE = "unavailable"

#: QuickQual-MEME (SPEC.md "Fallback A") is 10 parameters printed in the paper,
#: with nothing to download. The parameters are NOT reproduced here because
#: this build does not have the paper's table to hand, and inventing ten
#: numbers would fabricate a clinical decision rule that looks published.
#: Supply them via NETRA_QUICKQUAL_MEME as 10 comma-separated floats to enable
#: this path. TODO(review): transcribe them from the paper and pin them here.
MEME_ENV = "NETRA_QUICKQUAL_MEME"
MEME_N_PARAMS = 10


@dataclass(frozen=True)
class GateResult:
    """A gate decision, or an explicit refusal to make one."""

    state: str
    #: usable | borderline | reject, or None when state != "ok".
    verdict: str | None
    #: P(usable) as a scaled integer in 0..1000. Integers, not floats: this
    #: value travels into a ledger payload and floats are banned there
    #: (CLAUDE.md). None when no head was available.
    score_milli: int | None
    #: The classical reason code: focus | exposure | fov_mask, or None.
    cause: str | None
    #: Which head answered: pickle | fitted | meme | none.
    head: str
    #: Raw classical measurements, for display and debugging only.
    measurements: dict

    @property
    def is_usable(self) -> bool:
        return self.verdict == VERDICT_USABLE

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "verdict": self.verdict,
            "score_milli": self.score_milli,
            "cause": self.cause,
            "head": self.head,
        }


# ------------------------------------------------------------------ features


class QuickQualFeatures:
    """Frozen densenet121 features: channel-wise mean AND std of the final map.

    QuickQual pools both statistics rather than mean alone - the std is what
    carries blur and exposure information, and a mean-only pooling throws away
    most of the quality signal.

    `pretrained=False` exists so the CPU smoke tests never reach the network.
    Features from a randomly initialised backbone are meaningless, so a head
    fitted on them is a smoke test and nothing more; `pretrained` is recorded
    in `model_version` so such a run cannot be mistaken for a real one.
    """

    def __init__(self, pretrained: bool = True, device: str = "cpu") -> None:
        import timm
        import torch

        self.pretrained = pretrained
        self.device = device
        self.model = timm.create_model(BACKBONE, pretrained=pretrained, num_classes=0)
        self.model.eval().to(device)
        self._torch = torch

    @property
    def version(self) -> str:
        suffix = "tv_in1k" if self.pretrained else "random-init"
        return f"quickqual:{BACKBONE}@{IMAGE_SIZE}:{suffix}"

    def __call__(self, image: np.ndarray) -> np.ndarray:
        """One preprocessed image -> a 1-D feature vector."""
        tensor = to_model_tensor(image).to(self.device)
        with self._torch.no_grad():
            maps = self.model.forward_features(tensor)
        mean = maps.mean(dim=(2, 3))
        std = maps.std(dim=(2, 3))
        return self._torch.cat([mean, std], dim=1).cpu().numpy().ravel()

    def batch(self, images: list[np.ndarray]) -> np.ndarray:
        return np.stack([self(img) for img in images]) if images else np.empty((0, 0))


# ---------------------------------------------------------------- the gate


def _load_pickle_head(path: str | pathlib.Path) -> Any:
    """Load the released SVM.

    SPEC.md "Fallback A" exists because the released pickle may not load under
    scikit-learn 1.9.1. That failure is caught and reported rather than raised,
    so an unloadable pickle degrades to `state="unavailable"` instead of
    taking the whole service down.
    """
    with pathlib.Path(path).open("rb") as fh:
        return pickle.load(fh)


class QualityGate:
    """QuickQual, with an explicit unavailable state."""

    def __init__(
        self,
        features: QuickQualFeatures | None = None,
        head: Any | None = None,
        svm_path: str | pathlib.Path | None = None,
        cutoffs: tuple[float, float] | None = None,
        pretrained: bool = True,
    ) -> None:
        self.features = features or QuickQualFeatures(pretrained=pretrained)
        self.usable_min_p, self.reject_max_p = cutoffs or quality_cutoffs()
        self.head = head
        self.head_kind = "fitted" if head is not None else "none"
        self.load_error: str | None = None

        if self.head is None:
            path = svm_path or os.environ.get("NETRA_QUICKQUAL_SVM")
            if path and pathlib.Path(path).exists():
                try:
                    self.head = _load_pickle_head(path)
                    self.head_kind = "pickle"
                except Exception as exc:  # noqa: BLE001 - reported, not raised
                    # Including the scikit-learn version skew SPEC.md warns about.
                    self.load_error = f"{type(exc).__name__}: {exc}"

        if self.head is None and os.environ.get(MEME_ENV):
            self.load_error = (
                f"{MEME_ENV} is set but QuickQual-MEME is not implemented: its "
                f"{MEME_N_PARAMS} published parameters are not transcribed in "
                "netra/models/quality.py. Refusing to improvise them."
            )

    @property
    def available(self) -> bool:
        return self.head is not None

    @property
    def model_version(self) -> str:
        if not self.available:
            return "unloaded"
        return f"{self.features.version}+{self.head_kind}"

    def fit(self, images: list[np.ndarray], usable: list[int]) -> QualityGate:
        """Fit the small head on quality labels (1 = usable, 0 = not).

        Features are frozen, so this fits only the head - which is the whole
        point of QuickQual and why it is viable on CPU.
        """
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.svm import SVC

        if len(images) != len(usable):
            raise ValueError("images and labels differ in length")
        if len(set(usable)) < 2:
            raise ValueError(
                "need both usable and unusable examples to fit a quality head"
            )
        processed = [preprocess(img)[0] for img in images]
        X = self.features.batch(processed)
        y = np.asarray(usable)

        # NOT `SVC(probability=True)`: deprecated in scikit-learn 1.9 and
        # removed in 1.11, which this build would hit as a hard failure on the
        # next bump. `CalibratedClassifierCV(..., ensemble=False)` is the
        # replacement the deprecation names, and it is the same Platt scaling
        # SVC was doing internally - so the head stays calibrated, which
        # matters because the gate thresholds are PROBABILITY cut-points.
        smallest_class = int(min(np.bincount(y)[np.bincount(y) > 0]))
        base = SVC(kernel="rbf", random_state=20261027)
        if smallest_class >= 4:
            self.head = CalibratedClassifierCV(
                base, ensemble=False, cv=min(3, smallest_class), method="sigmoid"
            )
        else:
            # Too few per class to cross-validate a calibrator. Fit the bare
            # SVC; `_p_usable` squashes its decision_function instead. That is
            # NOT calibrated, and a head fitted on this little data should not
            # be trusted for cut-points anyway.
            self.head = base
        self.head.fit(X, y)
        self.head_kind = "fitted"
        self.load_error = None
        return self

    def _p_usable(self, feature_vector: np.ndarray) -> float:
        row = feature_vector.reshape(1, -1)
        if hasattr(self.head, "predict_proba"):
            proba = self.head.predict_proba(row)[0]
            classes = list(getattr(self.head, "classes_", [0, 1]))
            return float(proba[classes.index(1)]) if 1 in classes else float(proba[-1])
        # A decision_function-only head (e.g. an SVC without probability) is
        # squashed rather than thresholded at 0, so the three-way band still
        # has something continuous to cut.
        score = float(np.asarray(self.head.decision_function(row)).ravel()[0])
        return float(1.0 / (1.0 + np.exp(-score)))

    def verdict_from_p(self, p_usable: float) -> str:
        if p_usable >= self.usable_min_p:
            return VERDICT_USABLE
        if p_usable <= self.reject_max_p:
            return VERDICT_REJECT
        return VERDICT_BORDERLINE

    def __call__(self, image: np.ndarray) -> GateResult:
        """Grade one raw image's quality. Never raises on an unavailable head."""
        processed, _crop = preprocess(image)
        codes = reason_codes.measure(processed)

        if not self.available:
            # No verdict. The classical measurements are still returned,
            # because they are honest and useful, but they are NOT a gate.
            return GateResult(
                state=STATE_UNAVAILABLE,
                verdict=None,
                score_milli=None,
                cause=codes.code,
                head="none",
                measurements=codes.as_dict(),
            )

        p = self._p_usable(self.features(processed))
        verdict = self.verdict_from_p(p)
        return GateResult(
            state=STATE_OK,
            verdict=verdict,
            # round() on a numpy float returns a Python int, which is what a
            # ledger payload needs - verified, not assumed.
            score_milli=round(p * 1000),
            # A cause only means something when the image was not admitted.
            cause=codes.code if verdict != VERDICT_USABLE else None,
            head=self.head_kind,
            measurements=codes.as_dict(),
        )
