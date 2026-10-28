"""The quality gate, preprocessing, and the reason-code channel.

The assertion that matters most in this file is the negative one: with no head
loaded the gate returns `state="unavailable"` and `verdict=None`. It must not
guess, and above all it must not default to `usable` - "usable" is the answer
that lets an ungradable image through into a grade and then a referral.

All of these run on CPU with `pretrained=False`, so nothing here touches the
network. Features from a random backbone are meaningless, which is exactly why
these are smoke tests and why `model_version` records `random-init`.
"""

from __future__ import annotations

from typing import ClassVar

import numpy as np
import pytest

from netra.models import reason_codes
from netra.models.preprocess import (
    IMAGE_SIZE,
    preprocess,
    remove_background,
    resize,
    to_model_tensor,
)
from netra.models.quality import (
    MEME_ENV,
    STATE_OK,
    STATE_UNAVAILABLE,
    VERDICT_BORDERLINE,
    VERDICT_REJECT,
    VERDICT_USABLE,
    QualityGate,
)

RNG = np.random.default_rng(20261027)


def fundus(
    size: int = 600,
    radius_frac: float = 0.46,
    blur: int = 0,
    brightness: float = 1.0,
    offset: tuple[int, int] = (0, 0),
) -> np.ndarray:
    """A synthetic fundus-like frame: a textured disc on a black surround.

    This is a FIXTURE, not a model of a retina. It exists to exercise crop,
    resize and tensor shapes. No number measured on it is a result.
    """
    import cv2

    img = np.zeros((size, size, 3), dtype=np.uint8)
    yy, xx = np.mgrid[0:size, 0:size]
    cy, cx = size // 2 + offset[0], size // 2 + offset[1]
    disc = (yy - cy) ** 2 + (xx - cx) ** 2 <= (size * radius_frac) ** 2

    texture = RNG.integers(60, 200, size=(size, size, 3), dtype=np.int16)
    texture[..., 0] = np.clip(texture[..., 0] * 1.3, 0, 255)  # fundus is reddish
    img[disc] = texture[disc].astype(np.uint8)

    if blur:
        img = cv2.GaussianBlur(img, (blur * 2 + 1, blur * 2 + 1), 0)
    if brightness != 1.0:
        img = np.clip(img.astype(np.float32) * brightness, 0, 255).astype(np.uint8)
    return img


# ------------------------------------------------------------- preprocessing


def test_background_removal_crops_to_the_retina_and_reports_what_it_kept():
    img = fundus(size=600, radius_frac=0.25)
    cropped, report = remove_background(img)
    assert cropped.shape[0] < 600 and cropped.shape[1] < 600
    assert report.crop_failed is False
    # A disc of radius 0.25*600 spans ~300px of 600, so ~1/4 of the area.
    assert 0.15 < report.retained_fraction < 0.35
    # Inside the tight crop, a circle inscribed in a square is pi/4 ~= 0.785.
    assert 0.6 < report.retina_fraction < 0.9


def test_background_removal_returns_the_original_on_an_all_black_frame():
    """A lens cap must not become a zero-size array three functions later."""
    black = np.zeros((64, 64, 3), dtype=np.uint8)
    cropped, report = remove_background(black)
    assert cropped.shape == black.shape
    assert report.crop_failed is True
    assert report.retina_fraction == 0.0


def test_preprocess_is_background_removal_then_resize_only():
    out, report = preprocess(fundus())
    assert out.shape == (IMAGE_SIZE, IMAGE_SIZE, 3)
    assert out.dtype == np.uint8
    assert report.retained_fraction <= 1.0


def test_resize_handles_both_directions():
    assert resize(fundus(size=900), 512).shape == (512, 512, 3)
    assert resize(fundus(size=200), 512).shape == (512, 512, 3)


def test_grayscale_and_rgba_inputs_are_accepted():
    gray = RNG.integers(0, 255, (80, 80), dtype=np.uint8)
    assert preprocess(gray)[0].shape == (IMAGE_SIZE, IMAGE_SIZE, 3)
    rgba = RNG.integers(0, 255, (80, 80, 4), dtype=np.uint8)
    assert preprocess(rgba)[0].shape == (IMAGE_SIZE, IMAGE_SIZE, 3)


def test_a_wrong_shape_is_refused():
    with pytest.raises(ValueError, match="expected HxWx3"):
        remove_background(np.zeros((4, 4, 2), dtype=np.uint8))


def test_to_model_tensor_uses_mean_std_half_at_512():
    """SPEC.md section 1 specifies mean/std 0.5 for QuickQual at 512px."""
    import torch

    white = np.full((IMAGE_SIZE, IMAGE_SIZE, 3), 255, dtype=np.uint8)
    black = np.zeros((IMAGE_SIZE, IMAGE_SIZE, 3), dtype=np.uint8)
    t_white = to_model_tensor(white)
    assert t_white.shape == (1, 3, IMAGE_SIZE, IMAGE_SIZE)
    assert t_white.dtype == torch.float32
    # (1.0 - 0.5)/0.5 = 1.0 and (0.0 - 0.5)/0.5 = -1.0
    assert torch.allclose(t_white, torch.ones_like(t_white), atol=1e-5)
    assert torch.allclose(to_model_tensor(black), -torch.ones_like(t_white), atol=1e-5)


# -------------------------------------------------------------- reason codes


def test_a_sharp_well_exposed_frame_gets_no_reason_code():
    codes = reason_codes.measure(preprocess(fundus())[0])
    assert codes.code is None
    assert codes.retina_fraction > 0.5


def test_a_heavily_blurred_frame_reads_as_a_focus_problem():
    codes = reason_codes.measure(preprocess(fundus(blur=14))[0])
    assert codes.code == reason_codes.CODE_FOCUS
    assert codes.laplacian_variance < reason_codes.FOCUS_VARIANCE_FLOOR


def test_a_dark_frame_reads_as_an_exposure_problem():
    codes = reason_codes.measure(preprocess(fundus(brightness=0.12))[0])
    assert codes.code == reason_codes.CODE_EXPOSURE
    assert codes.mean_intensity < reason_codes.EXPOSURE_DARK_MEAN


def test_a_blown_out_frame_reads_as_an_exposure_problem():
    codes = reason_codes.measure(preprocess(fundus(brightness=4.0))[0])
    assert codes.code == reason_codes.CODE_EXPOSURE


def test_an_all_black_frame_reads_as_a_field_of_view_problem():
    """Not a focus problem. A black frame has zero variance, but the actual
    fault is that there is no retina in it."""
    codes = reason_codes.measure(np.zeros((128, 128, 3), dtype=np.uint8))
    assert codes.code == reason_codes.CODE_FOV


def test_focus_is_measured_inside_the_retina_mask_only():
    """Otherwise the measurement is a function of how much black surround the
    camera's aperture happens to leave, not of the image."""
    tight = reason_codes.measure(fundus(size=400, radius_frac=0.48))
    loose = reason_codes.measure(fundus(size=400, radius_frac=0.20))
    # Same texture, very different surround. Variance should stay comparable.
    assert loose.laplacian_variance > tight.laplacian_variance * 0.4
    assert loose.retina_fraction < tight.retina_fraction


def test_cause_for_returns_a_code_lane_b_can_render():
    cause = reason_codes.cause_for(preprocess(fundus(blur=14))[0])
    assert cause in {"focus", "exposure", "fov_mask"}


# ----------------------------------------- the gate with no head available


def test_an_unloaded_gate_refuses_to_produce_a_verdict():
    """The single most important assertion in this lane."""
    gate = QualityGate(features=_FakeFeatures(), head=None)
    assert gate.available is False
    assert gate.model_version == "unloaded"

    result = gate(fundus())
    assert result.state == STATE_UNAVAILABLE
    assert result.verdict is None, "an unloaded gate must not guess a verdict"
    assert result.verdict != VERDICT_USABLE, "and must never default to usable"
    assert result.score_milli is None
    assert result.head == "none"
    # The classical measurements are still returned; they are just not a gate.
    assert result.measurements["retina_fraction"] > 0


def test_the_meme_fallback_refuses_rather_than_improvising_parameters(monkeypatch):
    """SPEC.md's Fallback A is 10 published parameters. They are not in this
    repo, and ten invented numbers would look published."""
    monkeypatch.setenv(MEME_ENV, "0.1,0.2,0.3")
    gate = QualityGate(features=_FakeFeatures(), head=None)
    assert gate.available is False
    assert "not implemented" in (gate.load_error or "")
    assert gate(fundus()).verdict is None


def test_an_unloadable_pickle_degrades_instead_of_raising(tmp_path):
    """SPEC.md expects the released pickle may not load under scikit-learn
    1.9.1. That must not take the service down."""
    bad = tmp_path / "head.pkl"
    bad.write_bytes(b"not a pickle at all")
    gate = QualityGate(features=_FakeFeatures(), head=None, svm_path=bad)
    assert gate.available is False
    assert gate.load_error and "Error" in gate.load_error
    assert gate(fundus()).state == STATE_UNAVAILABLE


# ------------------------------------------------- the three-way verdict band


class _FakeFeatures:
    """A stand-in extractor, so band logic is tested without a 28 MB backbone."""

    pretrained = False
    version = "fake-features"

    def __call__(self, image):
        return np.array([float(np.asarray(image).mean())])

    def batch(self, images):
        return np.stack([self(i) for i in images]) if images else np.empty((0, 1))


class _FixedHead:
    """A head that returns a chosen P(usable)."""

    classes_: ClassVar[list[int]] = [0, 1]

    def __init__(self, p: float) -> None:
        self.p = p

    def predict_proba(self, X):
        return np.tile([[1 - self.p, self.p]], (len(X), 1))


@pytest.mark.parametrize(
    ("p", "expected"),
    [
        (0.95, VERDICT_USABLE),
        (0.70, VERDICT_USABLE),  # boundary is inclusive
        (0.69, VERDICT_BORDERLINE),
        (0.31, VERDICT_BORDERLINE),
        (0.30, VERDICT_REJECT),  # boundary is inclusive
        (0.02, VERDICT_REJECT),
    ],
)
def test_the_verdict_band_follows_thresholds_yaml(p, expected):
    gate = QualityGate(features=_FakeFeatures(), head=_FixedHead(p))
    result = gate(fundus())
    assert result.state == STATE_OK
    assert result.verdict == expected
    assert result.score_milli == round(p * 1000)


def test_the_score_is_a_scaled_integer_not_a_float():
    """It travels into a ledger payload, where floats are banned (CLAUDE.md)."""
    result = QualityGate(features=_FakeFeatures(), head=_FixedHead(0.873))(fundus())
    assert isinstance(result.score_milli, int)
    assert result.score_milli == 873


def test_a_usable_verdict_carries_no_cause():
    """A cause is a retake instruction; an admitted image has nothing to retake."""
    result = QualityGate(features=_FakeFeatures(), head=_FixedHead(0.99))(fundus())
    assert result.verdict == VERDICT_USABLE
    assert result.cause is None


def test_a_rejected_verdict_carries_the_classical_cause():
    gate = QualityGate(features=_FakeFeatures(), head=_FixedHead(0.05))
    result = gate(fundus(blur=14))
    assert result.verdict == VERDICT_REJECT
    assert result.cause == reason_codes.CODE_FOCUS


def test_the_model_version_records_which_head_answered():
    gate = QualityGate(features=_FakeFeatures(), head=_FixedHead(0.9))
    assert gate.model_version == "fake-features+fitted"


# ---------------------------------------------------- fitting the small head


def test_fit_needs_both_classes():
    gate = QualityGate(features=_FakeFeatures(), head=None)
    with pytest.raises(ValueError, match="both usable and unusable"):
        gate.fit([fundus(), fundus()], [1, 1])


def test_fit_refuses_mismatched_lengths():
    gate = QualityGate(features=_FakeFeatures(), head=None)
    with pytest.raises(ValueError, match="differ in length"):
        gate.fit([fundus()], [1, 0])


def test_fitting_on_the_fake_extractor_produces_a_usable_gate():
    """A real fit on CPU, just with a 1-D stand-in feature so it is instant."""
    sharp = [fundus(size=256) for _ in range(6)]
    dark = [fundus(size=256, brightness=0.1) for _ in range(6)]
    gate = QualityGate(features=_FakeFeatures(), head=None)
    gate.fit(sharp + dark, [1] * 6 + [0] * 6)

    assert gate.available is True
    assert gate.head_kind == "fitted"
    result = gate(sharp[0])
    assert result.state == STATE_OK
    assert result.verdict in {VERDICT_USABLE, VERDICT_BORDERLINE, VERDICT_REJECT}


# --------------------------------------------- the real backbone, on CPU


def test_the_real_densenet_extractor_runs_on_cpu_untrained():
    """CPU smoke of the actual backbone at 512px, with random weights.

    `pretrained=False` keeps this offline. The feature VALUES are meaningless -
    that is why `version` says `random-init` - but the shape, the pooling and
    the 512px path are real.
    """
    from netra.models.quality import QuickQualFeatures

    features = QuickQualFeatures(pretrained=False)
    vector = features(preprocess(fundus())[0])
    assert vector.ndim == 1
    # densenet121's final map is 1024 channels; mean and std are concatenated.
    assert vector.shape[0] == 2048
    assert np.isfinite(vector).all()
    assert "random-init" in features.version


# ------------------------------- batched features and fitting from features


def test_batched_features_equal_one_at_a_time_features():
    """Batching is a speed change, not a numerical one. Proven, not assumed.

    `netra/models/eyeq.py` pushes thousands of images through the backbone on
    a T4, where one-at-a-time wastes most of the card. If batching moved the
    numbers, a head fitted in a batched run would not match the gate that
    serves single images at inference time.
    """
    from netra.models.quality import QuickQualFeatures

    features = QuickQualFeatures(pretrained=False)
    images = [preprocess(fundus(brightness=b))[0] for b in (1.0, 0.5, 0.2)]

    one_at_a_time = features.batch(images, batch_size=1)
    batched = features.batch(images, batch_size=3)

    assert one_at_a_time.shape == batched.shape == (3, 2048)
    assert np.allclose(one_at_a_time, batched, atol=1e-4)


def test_batch_defaults_to_one_so_existing_callers_are_unchanged():
    from netra.models.quality import QuickQualFeatures

    features = QuickQualFeatures(pretrained=False)
    images = [preprocess(fundus())[0]]
    assert features.batch(images).shape == (1, 2048)
    assert features.batch([]).shape == (0, 0)


def test_fit_features_fits_the_same_head_as_fit():
    """`fit()` now delegates, so the two paths must agree."""
    from netra.models.quality import QualityGate, QuickQualFeatures

    raw = [fundus(brightness=b) for b in (1.0, 0.95, 0.9, 0.1, 0.12, 0.15)]
    labels = [1, 1, 1, 0, 0, 0]

    # ONE extractor for both gates: two `pretrained=False` instances get
    # different random weights, so sharing it is what makes this a comparison
    # of the two fitting paths rather than of two different backbones.
    extractor = QuickQualFeatures(pretrained=False)

    via_images = QualityGate(features=extractor, head=None)
    via_images.fit(raw, labels)

    X = extractor.batch([preprocess(img)[0] for img in raw], batch_size=2)
    via_features = QualityGate(features=extractor, head=None)
    via_features.fit_features(X, labels)

    probe = preprocess(fundus())[0]
    assert via_images._p_usable(extractor(probe)) == pytest.approx(
        via_features._p_usable(extractor(probe))
    )


def test_fit_features_refuses_a_single_class():
    """A one-class head would answer every image the same way, confidently."""
    from netra.models.quality import QualityGate, QuickQualFeatures

    gate = QualityGate(features=QuickQualFeatures(pretrained=False), head=None)
    with pytest.raises(ValueError, match="both usable and unusable"):
        gate.fit_features(np.zeros((4, 8)), [1, 1, 1, 1])


def test_fit_features_refuses_mismatched_lengths():
    from netra.models.quality import QualityGate, QuickQualFeatures

    gate = QualityGate(features=QuickQualFeatures(pretrained=False), head=None)
    with pytest.raises(ValueError, match="differ in length"):
        gate.fit_features(np.zeros((4, 8)), [1, 0, 1])
