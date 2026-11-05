"""Conformal abstention and the clinical-action rule.

The rule under test is SPEC.md section 3's, and the whole point is that SIZE is
not the criterion: `{0,1}` and `{0,3}` are both size 2 and only the second is
alarming. Both directions are asserted, and the rule is also checked against
Lane A's and Lane B's copies so the three cannot drift.
"""

from __future__ import annotations

import numpy as np
import pytest

from netra.models.abstain import (
    AbstainDecision,
    AbstentionWrapper,
    PrefitProbaEstimator,
    decide,
    spans_clinical_actions,
)
from netra.models.thresholds import refer_grades

REFER = (2, 3, 4)


# ------------------------------------------------- the rule, in both directions


@pytest.mark.parametrize(
    ("prediction_set", "spans"),
    [
        ((0, 1), False),  # both do-not-refer - size 2, not alarming
        ((0, 3), True),  # straddles the line - size 2, alarming
        ((1, 2), True),
        ((2, 3, 4), False),  # all refer - size 3, still a clear action
        ((0, 1, 2), True),
        ((3,), False),
        ((0,), False),
        ((), False),
    ],
)
def test_spans_clinical_actions_ignores_set_size(prediction_set, spans):
    assert spans_clinical_actions(prediction_set, REFER) is spans


def test_the_two_size_two_sets_from_the_spec_differ():
    """SPEC.md names these two explicitly, so they get their own test."""
    assert decide((0, 1), REFER).abstain is False
    assert decide((0, 3), REFER).abstain is True


def test_a_singleton_set_records_that_grade():
    for grade in range(5):
        decision = decide((grade,), REFER)
        assert decision.abstain is False
        assert decision.grade == grade
        assert decision.refer is (grade in REFER)


def test_an_all_refer_set_does_not_abstain_but_records_no_single_grade():
    """`{2,3,4}` identifies an action but not a severity. Matches Lane B's
    `singleGrade`, which returns null for any set of size > 1."""
    decision = decide((2, 3, 4), REFER)
    assert decision.abstain is False
    assert decision.refer is True
    assert decision.grade is None


def test_an_all_do_not_refer_set_does_not_abstain_and_does_not_refer():
    decision = decide((0, 1), REFER)
    assert decision.abstain is False
    assert decision.refer is False
    assert decision.grade is None


def test_an_empty_set_abstains_and_is_not_read_as_grade_zero():
    """An empty set means no class met the threshold. Reading it as grade 0
    would turn "we do not know" into "no retinopathy"."""
    decision = decide((), REFER)
    assert decision.abstain is True
    assert decision.grade is None
    assert decision.refer is False
    assert "empty prediction set" in decision.reason


def test_the_decision_deduplicates_and_sorts():
    decision = decide([3, 3, 2], REFER)
    assert decision.prediction_set == (2, 3)


def test_every_decision_carries_a_reason():
    for prediction_set in [(), (0,), (0, 1), (0, 3), (2, 3, 4)]:
        assert decide(prediction_set, REFER).reason


def test_the_decision_dict_is_ledger_safe():
    """No floats: this travels into a ledger payload (BUILD_RULES.md)."""
    payload = decide((0, 3), REFER).as_dict()
    assert all(not isinstance(v, float) for v in payload.values())
    assert payload["prediction_set"] == [0, 3]
    assert all(isinstance(g, int) for g in payload["prediction_set"])


# ------------------------------------------ the three lanes must not drift


def test_refer_grades_comes_from_thresholds_yaml():
    assert refer_grades() == (2, 3, 4)


def test_lane_a_and_lane_c_agree_on_the_abstention_rule():
    """Lane A enforces this server-side; Lane C decides it. A disagreement
    would let an abstained case be referred, or vice versa."""
    from netra.api.clinical import spans_clinical_actions as lane_a

    for prediction_set in [
        [0, 1],
        [0, 3],
        [1, 2],
        [2, 3, 4],
        [0],
        [4],
        [0, 1, 2, 3, 4],
    ]:
        assert spans_clinical_actions(tuple(prediction_set), REFER) is lane_a(
            prediction_set, REFER
        ), f"lanes disagree on {prediction_set}"


def test_lane_b_declares_the_same_refer_grades():
    """Lane B mirrors `refer_grades` in TypeScript because the browser cannot
    read the YAML at runtime. A drift there is a clinical bug."""
    import pathlib
    import re

    clinical_ts = (
        pathlib.Path(__file__).resolve().parents[1]
        / "netra"
        / "ui"
        / "src"
        / "lib"
        / "clinical.ts"
    )
    source = clinical_ts.read_text(encoding="utf-8")
    found = re.search(r"REFER_GRADES: readonly Grade\[\] = \[([0-9,\s]+)\]", source)
    assert found is not None
    declared = tuple(int(x) for x in found.group(1).replace(" ", "").split(","))
    assert declared == refer_grades()


# ------------------------------------------------------- the MAPIE wrapper


def synthetic_proba(n=400, n_classes=5, sharpness=6.0, seed=20261027):
    """Probabilities whose labels really are drawn from them, so conformal
    coverage is meaningful rather than arbitrary."""
    rng = np.random.default_rng(seed)
    logits = rng.normal(size=(n, n_classes)) * sharpness
    proba = np.exp(logits - logits.max(axis=1, keepdims=True))
    proba /= proba.sum(axis=1, keepdims=True)
    labels = np.array([rng.choice(n_classes, p=row) for row in proba])
    return proba, labels


def test_the_prefit_estimator_hands_probabilities_straight_back():
    proba, _ = synthetic_proba(n=10)
    estimator = PrefitProbaEstimator(5)
    assert np.allclose(estimator.predict_proba(proba), proba)
    assert estimator.predict(proba).tolist() == proba.argmax(axis=1).tolist()
    assert estimator.__sklearn_is_fitted__() is True


def test_the_prefit_estimator_refuses_a_wrongly_shaped_matrix():
    estimator = PrefitProbaEstimator(5)
    with pytest.raises(ValueError, match="probability matrix"):
        estimator.predict_proba(np.zeros((4, 3)))


def test_predicting_before_conformalizing_raises():
    """The conformal threshold comes from the calibration fold. Without it
    there is no valid set to return."""
    wrapper = AbstentionWrapper(PrefitProbaEstimator(5))
    assert wrapper.conformalized is False
    with pytest.raises(RuntimeError, match="conformalize"):
        wrapper.prediction_sets(np.zeros((2, 5)))


def test_the_wrapper_reads_the_confidence_level_from_thresholds_yaml():
    wrapper = AbstentionWrapper(PrefitProbaEstimator(5))
    assert wrapper.confidence_level == pytest.approx(0.90)


def test_conformalize_then_predict_set_without_calling_fit():
    """BUILD_RULES.md says fit -> conformalize -> predict_set. With prefit=True,
    MAPIE 1.6.0 RAISES on fit(). This pins the corrected flow."""
    proba, labels = synthetic_proba()
    wrapper = AbstentionWrapper(PrefitProbaEstimator(5)).conformalize(
        proba[:200], labels[:200]
    )
    assert wrapper.conformalized is True
    sets = wrapper.prediction_sets(proba[200:230])
    assert len(sets) == 30
    for prediction_set in sets:
        assert all(0 <= g < 5 for g in prediction_set)


def test_calling_fit_under_prefit_is_what_mapie_refuses():
    """Documents the trap directly, so nobody 'fixes' the wrapper by adding
    the fit() call BUILD_RULES.md implies."""
    from mapie.classification import SplitConformalClassifier

    proba, labels = synthetic_proba(n=50)
    mapie = SplitConformalClassifier(
        PrefitProbaEstimator(5),
        confidence_level=0.90,
        conformity_score="lac",
        prefit=True,
    )
    with pytest.raises(ValueError, match="skipped when the prefit"):
        mapie.fit(proba, labels)


def test_predict_set_returns_a_tuple_whose_second_element_is_3d():
    """BUILD_RULES.md describes a 3-D bool array; it is the SECOND element of a
    tuple, not the return value."""
    from mapie.classification import SplitConformalClassifier

    proba, labels = synthetic_proba()
    mapie = SplitConformalClassifier(
        PrefitProbaEstimator(5),
        confidence_level=0.90,
        conformity_score="lac",
        prefit=True,
    )
    mapie.conformalize(proba[:200], labels[:200])
    out = mapie.predict_set(proba[200:210])
    assert isinstance(out, tuple) and len(out) == 2
    points, sets = out
    assert points.shape == (10,)
    assert sets.shape == (10, 5, 1)
    assert sets.dtype == bool


def test_empirical_coverage_is_near_the_requested_confidence_level():
    """The conformal guarantee, measured. At 90% the true label should fall in
    the set about 90% of the time on exchangeable data."""
    proba, labels = synthetic_proba(n=1200)
    wrapper = AbstentionWrapper(PrefitProbaEstimator(5)).conformalize(
        proba[:600], labels[:600]
    )
    report = wrapper.coverage_report(proba[600:], labels[600:])
    assert report["empirical_coverage"] == pytest.approx(0.90, abs=0.06)
    assert report["confidence_level"] == pytest.approx(0.90)


def test_a_lower_confidence_level_gives_smaller_sets():
    """Monotonicity: asking for less coverage must not ask for more classes."""
    proba, labels = synthetic_proba(n=1000)
    sizes = []
    for level in (0.80, 0.95):
        wrapper = AbstentionWrapper(
            PrefitProbaEstimator(5), confidence_level=level
        ).conformalize(proba[:500], labels[:500])
        report = wrapper.coverage_report(proba[500:], labels[500:])
        sizes.append(report["mean_set_size"])
    assert sizes[0] <= sizes[1]


def test_the_coverage_report_carries_the_abstention_cost():
    """metrics.abstention_report exists to make omitting the coverage cost
    awkward, so the wrapper must route through it rather than reporting a bare
    abstention rate."""
    proba, labels = synthetic_proba(n=800)
    wrapper = AbstentionWrapper(PrefitProbaEstimator(5)).conformalize(
        proba[:400], labels[:400]
    )
    report = wrapper.coverage_report(proba[400:], labels[400:])
    for key in (
        "n_total",
        "n_admitted",
        "n_abstained",
        "coverage",
        "abstention_rate",
        "accuracy_on_admitted",
        "accuracy_ci_on_admitted",
    ):
        assert key in report
    assert report["coverage"] + report["abstention_rate"] == pytest.approx(1.0)


def test_decide_many_returns_one_decision_per_row():
    proba, labels = synthetic_proba(n=300)
    wrapper = AbstentionWrapper(PrefitProbaEstimator(5)).conformalize(
        proba[:150], labels[:150]
    )
    decisions = wrapper.decide_many(proba[150:170])
    assert len(decisions) == 20
    assert all(isinstance(d, AbstainDecision) for d in decisions)
    # On deliberately ambiguous data at least one case should abstain; if none
    # does, the rule is not being exercised at all.
    ambiguous = np.full((40, 5), 0.2)
    wrapper2 = AbstentionWrapper(PrefitProbaEstimator(5)).conformalize(
        np.full((60, 5), 0.2), np.arange(60) % 5
    )
    assert any(d.abstain for d in wrapper2.decide_many(ambiguous))
