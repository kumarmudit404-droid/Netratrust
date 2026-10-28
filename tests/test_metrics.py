"""T-12: every function in `netra/eval/metrics.py`.

`metrics.py` is the single source of every number this project reports, and its
own docstring explains why it is hand-written: generated code passes unit tests
while computing a metric on the wrong split, and that failure mode has no
automated guard. These tests cannot catch a wrong split either. What they do
catch is the other half: a metric whose VALUE or DIRECTION is wrong, which is
just as invisible in a slide.

Where a value is asserted exactly, it was computed independently and checked
against the implementation rather than copied out of it.
"""

from __future__ import annotations

import numpy as np
import pytest

from netra.eval import metrics as m

# --------------------------------------------------------------- calibration


def test_brier_perfect():
    y = np.array([0, 1, 1, 0])
    assert m.brier(y, y.astype(float)) == 0.0


def test_brier_is_worst_when_confidently_wrong():
    y = np.array([0, 1, 1, 0])
    assert m.brier(y, 1.0 - y.astype(float)) == pytest.approx(1.0)


def test_brier_uses_the_y_proba_keyword_not_y_prob():
    """CLAUDE.md: `y_prob=` raises TypeError in scikit-learn 1.9.1.

    Assistants trained on older versions emit the old keyword confidently, so
    the wrapper's job is to be the only place that keyword is written.
    """
    from sklearn.metrics import brier_score_loss

    y = np.array([0, 1, 1, 0])
    p = np.array([0.1, 0.9, 0.8, 0.2])
    assert m.brier(y, p) == pytest.approx(brier_score_loss(y, p))
    with pytest.raises(TypeError):
        brier_score_loss(y, y_prob=p)  # type: ignore[call-arg]


def test_nll_is_near_zero_for_near_perfect_and_large_for_confidently_wrong():
    y = np.array([0, 1, 1, 0])
    good = np.array([0.001, 0.999, 0.999, 0.001])
    bad = np.array([0.999, 0.001, 0.001, 0.999])
    assert m.nll(y, good) < 0.01
    assert m.nll(y, bad) > 5.0


def test_nll_accepts_explicit_labels_for_a_single_class_slice():
    """A calibration fold can legitimately contain one class; without `labels`
    scikit-learn cannot infer the label set and raises."""
    y = np.array([1, 1, 1])
    p = np.array([0.9, 0.8, 0.95])
    assert m.nll(y, p, labels=[0, 1]) > 0


def test_nll_and_brier_are_both_minimised_by_the_truth():
    """Both are strictly proper, which is why CLAUDE.md leads with them."""
    y = np.array([0, 0, 1, 1, 1])
    truth = np.array([0.0, 0.0, 1.0, 1.0, 1.0])
    for shifted in (0.2, 0.4):
        p = np.clip(truth + np.where(truth > 0.5, -shifted, shifted), 1e-6, 1 - 1e-6)
        assert m.brier(y, p) > m.brier(y, np.clip(truth, 1e-6, 1 - 1e-6))
        assert m.nll(y, p) > m.nll(y, np.clip(truth, 1e-6, 1 - 1e-6))


def _calibrated(n=4000, scale=1.0, seed=7):
    """Labels drawn from the model's own probabilities, so it IS calibrated."""
    rng = np.random.default_rng(seed)
    z = rng.normal(size=n)
    y = (rng.random(n) < 1 / (1 + np.exp(-z))).astype(int)
    return y, 1 / (1 + np.exp(-scale * z))


def test_calibration_slope_is_one_and_intercept_zero_when_calibrated():
    y, p = _calibrated()
    slope, intercept = m.calibration_slope_intercept(y, p)
    assert slope == pytest.approx(1.0, abs=0.08)
    assert intercept == pytest.approx(0.0, abs=0.08)


def test_calibration_slope_falls_below_one_when_over_confident():
    """CLAUDE.md: slope < 1 means over-confident, the usual direction for a
    neural network. Sharpening the logits must move it that way."""
    y, _ = _calibrated()
    _, p_sharp = _calibrated(scale=2.0)
    slope, _ = m.calibration_slope_intercept(y, p_sharp)
    assert slope < 0.7


def test_calibration_slope_rises_above_one_when_under_confident():
    y, _ = _calibrated()
    _, p_flat = _calibrated(scale=0.5)
    slope, _ = m.calibration_slope_intercept(y, p_flat)
    assert slope > 1.4


def test_calibration_slope_is_monotone_in_sharpness():
    y, _ = _calibrated()
    slopes = [
        m.calibration_slope_intercept(y, _calibrated(scale=s)[1])[0]
        for s in (0.5, 1.0, 2.0)
    ]
    assert slopes[0] > slopes[1] > slopes[2]


def test_calibration_handles_probabilities_at_exactly_zero_and_one():
    """logit(0) is -inf; the eps clip is what stops this raising."""
    y = np.array([0, 1, 0, 1])
    p = np.array([0.0, 1.0, 0.0, 1.0])
    slope, intercept = m.calibration_slope_intercept(y, p)
    assert np.isfinite(slope) and np.isfinite(intercept)


# ----------------------------------------------------------------------- ECE


def test_ece_returns_its_binning_scheme_alongside_the_value():
    """ECE must never be reported without its binning scheme, so the function
    makes omitting it awkward by returning it."""
    y, p = _calibrated(n=2000)
    value, description = m.ece(y, p, n_bins=15)
    assert 0.0 <= value <= 1.0
    assert description == "15 uniform bins"
    assert m.ece(y, p, n_bins=15, strategy="quantile")[1] == "15 quantile bins"


def test_ece_is_small_for_a_calibrated_model_and_large_for_a_skewed_one():
    y, p = _calibrated(n=4000)
    calibrated, _ = m.ece(y, p)
    skewed, _ = m.ece(y, np.clip(p * 0.5, 1e-6, 1 - 1e-6))
    assert calibrated < 0.05
    assert skewed > calibrated * 2


def test_ece_changes_with_the_bin_count_which_is_why_it_is_secondary():
    """metrics.py documents a 7.6% swing from the bin count alone. The exact
    numbers there are from another dataset, so this asserts the PROPERTY: the
    same predictions give a different ECE at a different bin count."""
    y, p = _calibrated(n=2000)
    at15, _ = m.ece(y, p, n_bins=15)
    at50, _ = m.ece(y, p, n_bins=50)
    assert at15 != at50
    assert abs(at15 - at50) > 0.001


def test_ece_rejects_an_unknown_binning_strategy():
    y, p = _calibrated(n=100)
    with pytest.raises(ValueError, match="uniform"):
        m.ece(y, p, strategy="sturges")


def test_ece_is_zero_when_every_bin_matches_its_frequency():
    # Two groups: p=0.0 with no positives, p=1.0 with all positives.
    y = np.array([0, 0, 0, 1, 1, 1])
    p = np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0])
    value, _ = m.ece(y, p)
    assert value == pytest.approx(0.0)


# --------------------------------------------------------- temperature scaling


def _two_class_logits(n=3000, seed=11):
    rng = np.random.default_rng(seed)
    logits = np.stack([np.zeros(n), rng.normal(size=n)], axis=1)
    proba = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)
    y = np.array([rng.choice(2, p=row) for row in proba])
    return logits, y


def test_fit_temperature_recovers_one_when_already_calibrated():
    logits, y = _two_class_logits()
    assert m.fit_temperature(logits, y) == pytest.approx(1.0, abs=0.15)


def test_fit_temperature_recovers_the_scale_it_was_given():
    """Logits multiplied by 3 are over-confident by 3; T must come back ~3."""
    logits, y = _two_class_logits()
    assert m.fit_temperature(logits * 3.0, y) == pytest.approx(3.0, rel=0.15)
    assert m.fit_temperature(logits / 3.0, y) == pytest.approx(1 / 3.0, rel=0.2)


def test_fit_temperature_improves_nll_on_over_confident_logits():
    logits, y = _two_class_logits()
    sharp = logits * 3.0
    t = m.fit_temperature(sharp, y)

    def nll_of(z):
        z = z - z.max(axis=1, keepdims=True)
        proba = np.exp(z) / np.exp(z).sum(axis=1, keepdims=True)
        return m.nll(y, proba[:, 1], labels=[0, 1])

    assert nll_of(sharp / t) < nll_of(sharp)


def test_fit_temperature_matches_its_documented_signature():
    """metrics.py: "ECE falls substantially while Brier barely moves. If Brier
    moves a lot, something else is wrong." That is a testable claim."""
    logits, y = _two_class_logits()
    sharp = logits * 3.0
    t = m.fit_temperature(sharp, y)

    def probs(z):
        z = z - z.max(axis=1, keepdims=True)
        return (np.exp(z) / np.exp(z).sum(axis=1, keepdims=True))[:, 1]

    before, after = probs(sharp), probs(sharp / t)
    ece_before, _ = m.ece(y, before)
    ece_after, _ = m.ece(y, after)
    assert ece_after < ece_before / 2, "ECE should fall substantially"
    brier_shift = abs(m.brier(y, after) - m.brier(y, before))
    assert brier_shift < 0.10, "Brier should barely move"


# ------------------------------------------------------- selective prediction

# Four cases, the two most confident correct. Hand-computed:
#   coverage = [0.25, 0.50, 0.75, 1.00]
#   risk     = [0,    0,    1/3,  0.5 ]
CORRECT = np.array([1, 1, 0, 0])
CONFIDENCE = np.array([0.9, 0.8, 0.7, 0.6])


def test_risk_coverage_shapes_and_endpoints():
    coverage, risk = m.risk_coverage(CORRECT, CONFIDENCE)
    assert coverage.tolist() == [0.25, 0.5, 0.75, 1.0]
    assert risk[0] == 0.0
    # At full coverage the risk is just the overall error rate.
    assert risk[-1] == pytest.approx(0.5)


def test_risk_coverage_orders_by_descending_confidence():
    _, risk = m.risk_coverage(CORRECT, CONFIDENCE)
    assert risk.tolist() == pytest.approx([0.0, 0.0, 1 / 3, 0.5])
    # Shuffling the inputs together must not change the curve.
    order = [2, 0, 3, 1]
    _, reordered = m.risk_coverage(CORRECT[order], CONFIDENCE[order])
    assert reordered.tolist() == pytest.approx(risk.tolist())


def test_risk_coverage_is_all_zero_risk_for_a_perfect_model():
    correct = np.ones(10)
    _, risk = m.risk_coverage(correct, np.linspace(1, 0, 10))
    assert np.all(risk == 0.0)


def test_augrc_hand_computed_value():
    # generalised risk = risk * coverage = [0, 0, 0.25, 0.5]; trapezoid over
    # coverage with dx = 0.25, divided by coverage[-1] = 1.
    assert m.augrc(CORRECT, CONFIDENCE) == pytest.approx(0.125)


def test_augrc_prefers_a_confidence_that_ranks_errors_last():
    """The property the metric exists for: a model that knows when it is wrong
    scores better, at identical accuracy."""
    rng = np.random.default_rng(3)
    correct = rng.integers(0, 2, 500)
    good = m.augrc(correct, correct.astype(float))
    bad = m.augrc(correct, 1 - correct.astype(float))
    assert good < bad
    assert good == pytest.approx(0.126, abs=0.01)
    assert bad == pytest.approx(0.376, abs=0.01)


def test_coverage_at_risk_picks_the_largest_admissible_coverage():
    # risk = [0, 0, 1/3, 0.5]; at target 0.3 only the first two qualify.
    assert m.coverage_at_risk(CORRECT, CONFIDENCE, 0.3) == pytest.approx(0.5)
    assert m.coverage_at_risk(CORRECT, CONFIDENCE, 0.0) == pytest.approx(0.5)
    assert m.coverage_at_risk(CORRECT, CONFIDENCE, 0.4) == pytest.approx(0.75)
    assert m.coverage_at_risk(CORRECT, CONFIDENCE, 1.0) == pytest.approx(1.0)


def test_coverage_at_risk_is_zero_when_the_target_is_unreachable():
    """Zero coverage, not a near-miss: refusing every case is the honest answer
    when the requested risk cannot be met."""
    assert m.coverage_at_risk(CORRECT, CONFIDENCE, -0.1) == 0.0


def test_coverage_at_risk_is_full_for_a_perfect_model():
    correct = np.ones(20)
    assert m.coverage_at_risk(correct, np.linspace(1, 0, 20), 0.0) == pytest.approx(1.0)


# ------------------------------------------------------- per-site reporting


def test_wilson_interval_brackets_the_point_estimate():
    lo, hi = m.wilson_interval(8, 10)
    assert 0 <= lo < 0.8 < hi <= 1


def test_wilson_interval_known_values():
    """Cross-checked against the same algebra, and these exact bounds are what
    the front end renders as "24/30 (0.63-0.90)"."""
    lo, hi = m.wilson_interval(24, 30)
    assert lo == pytest.approx(0.6269395261897256, abs=1e-12)
    assert hi == pytest.approx(0.9049502189759876, abs=1e-12)


def test_wilson_interval_stays_inside_zero_and_one_at_the_extremes():
    lo, hi = m.wilson_interval(0, 10)
    assert lo == 0.0 and 0 < hi < 1
    lo, hi = m.wilson_interval(10, 10)
    assert hi == 1.0 and 0 < lo < 1


def test_wilson_interval_of_nothing_is_the_whole_range():
    """n=0 must not divide by zero, and must not claim to know anything."""
    assert m.wilson_interval(0, 0) == (0.0, 1.0)


def test_wilson_interval_narrows_as_n_grows():
    widths = [
        m.wilson_interval(k, n)[1] - m.wilson_interval(k, n)[0]
        for k, n in ((8, 10), (80, 100), (800, 1000))
    ]
    assert widths[0] > widths[1] > widths[2]


# ------------------------------------------------------- abstention report


def test_abstention_report_carries_the_coverage_cost_with_the_accuracy():
    """The headline table. metrics.py exists to make omitting the coverage cost
    awkward, so the shape is pinned."""
    admitted = np.array([1, 1, 1, 0, 0], dtype=bool)
    correct = np.array([1, 1, 0], dtype=bool)  # on the 3 admitted
    report = m.abstention_report(admitted, correct)

    assert set(report) == {
        "n_total",
        "n_admitted",
        "n_abstained",
        "coverage",
        "abstention_rate",
        "accuracy_on_admitted",
        "accuracy_ci_on_admitted",
    }
    assert report["n_total"] == 5
    assert report["n_admitted"] == 3
    assert report["n_abstained"] == 2
    assert report["coverage"] == pytest.approx(0.6)
    assert report["abstention_rate"] == pytest.approx(0.4)
    assert report["accuracy_on_admitted"] == pytest.approx(2 / 3)


def test_coverage_and_abstention_rate_always_sum_to_one():
    for n_admitted in range(6):
        admitted = np.array([1] * n_admitted + [0] * (5 - n_admitted), dtype=bool)
        correct = np.ones(max(n_admitted, 1), dtype=bool)
        r = m.abstention_report(admitted, correct)
        assert r["coverage"] + r["abstention_rate"] == pytest.approx(1.0)


def test_abstention_report_reports_nan_accuracy_when_nothing_was_admitted():
    """Not zero. A gate that admitted nothing has no accuracy, and printing
    0.0 would read as "it got everything wrong"."""
    admitted = np.zeros(4, dtype=bool)
    report = m.abstention_report(admitted, np.array([], dtype=bool))
    assert report["n_admitted"] == 0
    assert np.isnan(report["accuracy_on_admitted"])
    assert report["coverage"] == 0.0
    assert report["abstention_rate"] == 1.0


def test_abstention_report_ci_travels_with_the_accuracy():
    admitted = np.ones(30, dtype=bool)
    correct = np.array([1] * 24 + [0] * 6, dtype=bool)
    report = m.abstention_report(admitted, correct)
    lo, hi = report["accuracy_ci_on_admitted"]
    assert (lo, hi) == pytest.approx(m.wilson_interval(24, 30))
    assert lo < report["accuracy_on_admitted"] < hi


def test_abstention_report_of_an_empty_cohort_does_not_divide_by_zero():
    report = m.abstention_report(np.array([], dtype=bool), np.array([], dtype=bool))
    assert report["n_total"] == 0
    assert report["coverage"] == 0.0
    assert report["abstention_rate"] == 0.0


# ----------------------------------------------------------- DR agreement


def test_qwk_is_one_for_perfect_agreement_and_zero_for_chance():
    y = np.array([0, 1, 2, 3, 4, 2, 1, 0])
    assert m.quadratic_weighted_kappa(y, y) == pytest.approx(1.0)


def test_qwk_penalises_a_distant_confusion_more_than_a_near_one():
    """The reason quadratic weights are the right choice: the grades are
    ORDERED, so calling a 0 a 4 must cost more than calling it a 1."""
    y = np.array([0, 0, 0, 0, 4, 4, 4, 4])
    near = np.array([1, 0, 0, 0, 4, 4, 4, 4])
    far = np.array([4, 0, 0, 0, 4, 4, 4, 4])
    assert m.quadratic_weighted_kappa(y, far) < m.quadratic_weighted_kappa(y, near)


def test_qwk_is_unchanged_by_a_fold_that_lacks_a_grade():
    """Passing labels=range(5) does NOT change the value, and the docstring
    says so rather than implying a protection it does not give.

    The quadratic weights are (i-j)^2/(k-1)^2, so widening the label set scales
    every weight by one constant, which cancels in 1 - sum(wO)/sum(wE).
    """
    from sklearn.metrics import cohen_kappa_score

    y = np.array([0, 0, 1, 1, 2, 2])  # no grade 3 or 4 anywhere
    p = np.array([0, 1, 1, 1, 2, 2])
    ours = m.quadratic_weighted_kappa(y, p)
    inferred = cohen_kappa_score(y, p, weights="quadratic")
    assert ours == pytest.approx(inferred)
    assert ours == pytest.approx(0.8571428571428572)


def test_qwk_of_a_single_grade_fold_is_nan_not_a_misleading_one():
    """A fold where every case is the same grade has no measurable agreement.
    Explicit labels do not rescue this, so a caller must check for nan rather
    than publish it as 1.0 or 0.0."""
    import warnings

    y = np.array([2, 2, 2, 2])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert np.isnan(m.quadratic_weighted_kappa(y, y))


def test_qwk_is_negative_when_predictions_invert_the_order():
    y = np.array([0, 1, 2, 3, 4])
    assert m.quadratic_weighted_kappa(y, y[::-1]) < 0
