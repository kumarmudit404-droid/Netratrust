"""The classical OpenCV channel: WHY an image failed and what to retake.

SPEC.md section 1 is explicit that this is **not the gate**: "Parallel channel:
classical OpenCV reason-codes (focus, exposure, FOV mask) used to explain WHY
an image failed and what to retake. Not the gate itself - no published absolute
Laplacian threshold for fundus images exists."

So every number in here is a RELATIVE, unvalidated heuristic whose only job is
to pick a sentence for the operator. Nothing here may decide usable/reject, and
nothing here may be reported as a measurement. The thresholds below have no
literature behind them and are marked accordingly.

The codes match the three Lane B renders in `VerdictPanel`: `focus`,
`exposure`, `fov_mask`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

CODE_FOCUS = "focus"
CODE_EXPOSURE = "exposure"
CODE_FOV = "fov_mask"

# TODO(review): these cut-points are hand-picked to separate obviously-bad
# frames from plausible ones on APTOS at 512px. No published absolute threshold
# for fundus images exists (SPEC.md section 1), so they are NOT calibrated and
# must never be quoted as a measurement. They only choose which retake
# sentence to show. Fitting them would need a quality-labelled corpus, which
# this build does not have locally - see the EyeQ gap in memory.md.
FOCUS_VARIANCE_FLOOR = 60.0
EXPOSURE_DARK_MEAN = 40.0
EXPOSURE_BRIGHT_MEAN = 200.0
EXPOSURE_CLIPPED_FRACTION = 0.12
FOV_MIN_RETINA_FRACTION = 0.35


@dataclass(frozen=True)
class ReasonCodes:
    """Raw measurements plus the single code to show, if any."""

    laplacian_variance: float
    mean_intensity: float
    clipped_fraction: float
    retina_fraction: float
    #: The one code to render, or None when nothing classical looks wrong.
    code: str | None

    def as_dict(self) -> dict:
        return asdict(self)


def _retina_mask(gray: np.ndarray) -> np.ndarray:
    from netra.models.preprocess import BACKGROUND_CUTOFF

    return gray > BACKGROUND_CUTOFF


def measure(image: np.ndarray) -> ReasonCodes:
    """Measure focus, exposure and field of view on a preprocessed image.

    Focus and exposure are measured **inside the retina mask only**. The black
    surround is perfectly smooth and perfectly dark, so including it drags the
    Laplacian variance and the mean toward zero in proportion to how much
    surround the frame happens to have - which would make the measurement a
    function of the camera's aperture rather than of the image.
    """
    import cv2

    arr = np.asarray(image)
    if arr.ndim == 3:
        gray = cv2.cvtColor(arr[:, :, :3].astype(np.uint8), cv2.COLOR_RGB2GRAY)
    else:
        gray = arr.astype(np.uint8)

    mask = _retina_mask(gray)
    retina_fraction = float(mask.mean())

    if not mask.any():
        # Nothing to measure. Reported as a FOV failure, which is what an
        # all-black frame is, rather than as a zero-variance focus failure.
        return ReasonCodes(0.0, 0.0, 0.0, 0.0, CODE_FOV)

    inside = gray[mask]
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    focus_variance = float(laplacian[mask].var())
    mean_intensity = float(inside.mean())
    clipped = float(((inside <= 2) | (inside >= 253)).mean())

    # Order matters: a clipped or badly framed image also reads as blurred, so
    # the more fundamental fault is reported first and the operator is given
    # one instruction rather than three.
    code: str | None = None
    if retina_fraction < FOV_MIN_RETINA_FRACTION:
        code = CODE_FOV
    elif (
        mean_intensity < EXPOSURE_DARK_MEAN
        or mean_intensity > EXPOSURE_BRIGHT_MEAN
        or clipped > EXPOSURE_CLIPPED_FRACTION
    ):
        code = CODE_EXPOSURE
    elif focus_variance < FOCUS_VARIANCE_FLOOR:
        code = CODE_FOCUS

    return ReasonCodes(
        laplacian_variance=focus_variance,
        mean_intensity=mean_intensity,
        clipped_fraction=clipped,
        retina_fraction=retina_fraction,
        code=code,
    )


def cause_for(image: np.ndarray) -> str | None:
    """The `cause` field for POST /v1/encounters, or None if nothing is wrong.

    Lane B renders `focus`, `exposure` and `fov_mask` with specific retake
    instructions and falls back to the raw code for anything else, so adding a
    fourth code here is safe but will read as a bare string until Lane B adds
    a sentence for it.
    """
    return measure(image).code
