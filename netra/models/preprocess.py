"""Background removal + resize. Nothing else.

This is the whole preprocessing pipeline, and the restriction is a measured
result, not a style choice. SPEC.md section 2: a controlled ablation found Ben
Graham (0.8260) and CLAHE (0.8238) both BELOW plain background-removal + resize
(0.8310). Resolution is what pays: 128->512 buys +0.164 kappa, 512->1024 buys
+0.013 for 4x the compute. So: crop the black surround, resize to 512, stop.

Do not add CLAHE, Ben Graham, gamma, or colour normalisation here. If someone
wants to try one, it belongs in an ablation with its own number, not in the
default path.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: SPEC.md section 2: both the gate and the backbone run at 512.
IMAGE_SIZE = 512

#: A pixel is "retina" if any channel exceeds this. Fundus surrounds are pure
#: black from the camera's aperture mask, so a low cut is enough and a high one
#: would start eating dark retina near the edge.
BACKGROUND_CUTOFF = 10


@dataclass(frozen=True)
class CropReport:
    """What the crop did, so the retained fraction can be reported out loud.

    `.claude/rules/ml.md` requires the retained fraction at every filtering
    step: "reasonable" preprocessing has been documented to silently discard
    80-94% of public corpora.
    """

    height: int
    width: int
    cropped_height: int
    cropped_width: int
    #: Fraction of the ORIGINAL frame kept by the crop.
    retained_fraction: float
    #: Fraction of the cropped frame that is above the background cutoff. A
    #: full fundus disc inscribed in a square is pi/4 ~= 0.785.
    retina_fraction: float
    #: True when nothing looked like retina and the original was returned.
    crop_failed: bool


def _to_hwc_uint8(image: np.ndarray) -> np.ndarray:
    arr = np.asarray(image)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    if arr.ndim != 3 or arr.shape[2] not in (3, 4):
        raise ValueError(f"expected HxWx3 or HxWx4, got {arr.shape}")
    arr = arr[:, :, :3]
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return arr


def remove_background(image: np.ndarray) -> tuple[np.ndarray, CropReport]:
    """Crop to the retina's bounding box. Returns (cropped, report).

    On an image where nothing clears the cutoff - an all-black frame, a lens
    cap - this returns the ORIGINAL rather than a zero-size array, and says so
    in `crop_failed`. A silent empty crop downstream is far worse than a frame
    that the gate then rejects on its own merits.
    """
    arr = _to_hwc_uint8(image)
    h, w = arr.shape[:2]
    mask = arr.max(axis=2) > BACKGROUND_CUTOFF

    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    if rows.size == 0 or cols.size == 0:
        return arr, CropReport(h, w, h, w, 1.0, 0.0, True)

    top, bottom = int(rows[0]), int(rows[-1]) + 1
    left, right = int(cols[0]), int(cols[-1]) + 1
    cropped = arr[top:bottom, left:right]
    ch, cw = cropped.shape[:2]
    retina = float(mask[top:bottom, left:right].mean())
    return cropped, CropReport(
        height=h,
        width=w,
        cropped_height=ch,
        cropped_width=cw,
        retained_fraction=(ch * cw) / (h * w),
        retina_fraction=retina,
        crop_failed=False,
    )


def resize(image: np.ndarray, size: int = IMAGE_SIZE) -> np.ndarray:
    """Square resize with OpenCV, area-averaging down and linear up."""
    import cv2

    arr = _to_hwc_uint8(image)
    h, w = arr.shape[:2]
    interpolation = cv2.INTER_AREA if (h > size or w > size) else cv2.INTER_LINEAR
    return cv2.resize(arr, (size, size), interpolation=interpolation)


def preprocess(
    image: np.ndarray, size: int = IMAGE_SIZE
) -> tuple[np.ndarray, CropReport]:
    """The one supported path: remove background, then resize. Nothing else."""
    cropped, report = remove_background(image)
    return resize(cropped, size), report


def to_model_tensor(image: np.ndarray, mean: float = 0.5, std: float = 0.5):
    """HWC uint8 -> 1x3xHxW float tensor, normalised.

    QuickQual specifies mean/std 0.5 at 512px (SPEC.md section 1), which is
    also what the DR backbone is trained with here, so one function serves
    both and they cannot drift apart.
    """
    import torch

    arr = _to_hwc_uint8(image).astype(np.float32) / 255.0
    arr = (arr - mean) / std
    return torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).contiguous()


def load_image(path) -> np.ndarray:
    """Read an image file as RGB HWC uint8."""
    import cv2

    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(f"could not read an image at {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
