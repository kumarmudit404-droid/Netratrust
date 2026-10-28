"""Conformal abstention: MAPIE split-conformal prediction sets.

SPEC.md section 3. MAPIE 1.6.0, `SplitConformalClassifier` with
`conformity_score="lac"`, `prefit=True`.

The rule that matters, and the one that is easy to get wrong:

> **Abstain when the prediction set spans more than one CLINICAL ACTION class,
> not when the set is merely large. `{0,1}` and `{0,3}` are both size 2 and
> only the second is alarming.**

With `dr.refer_grades = [2,3,4]` the two actions are refer and do-not-refer.
`{0,1}` is entirely do-not-refer, so there is a clear action and no abstention.
`{2,3,4}` is entirely refer - also a clear action, even though it is a set of
three and names no single severity. `{0,3}` straddles the line, so a clinician
decides.

**Two corrections to CLAUDE.md's MAPIE note, both verified against the
installed 1.6.0:**

1. CLAUDE.md says `fit -> conformalize -> predict_set`. With `prefit=True`,
   calling `fit()` **raises**: "The fit method must be skipped when the prefit
   parameter is set to True. Use the conformalize method directly after
   instanciation." So the flow is `conformalize -> predict_set`.
2. `predict_set` returns a **tuple** `(point_predictions, sets)`, not a bare
   array. CLAUDE.md's "3-D (n, n_classes, n_levels) bool array" describes the
   SECOND element; the first is a 1-D array of argmax labels.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from netra.models.thresholds import conformal_confidence, refer_grades

N_CLASSES = 5


@dataclass(frozen=True)
class AbstainDecision:
    """What to do with one case."""

    prediction_set: tuple[int, ...]
    abstain: bool
    #: The single grade to record, or None. A set of size > 1 names no single
    #: severity even when it does not span actions, so this stays None there.
    grade: int | None
    #: True when every grade in the set is referable.
    refer: bool
    reason: str

    def as_dict(self) -> dict:
        return {
            "prediction_set": list(self.prediction_set),
            "abstain": self.abstain,
            "grade": self.grade,
            "refer": self.refer,
            "reason": self.reason,
        }


# ------------------------------------------------------------ the clinical rule


def spans_clinical_actions(
    prediction_set: tuple[int, ...] | list[int], refer: tuple[int, ...]
) -> bool:
    """True when the set contains both a referable and a non-referable grade.

    Size is NOT the criterion. This mirrors `spansClinicalActions` in Lane B's
    `netra/ui/src/lib/clinical.ts` and `spans_clinical_actions` in Lane A's
    `netra/api/clinical.py`; all three read `refer_grades` from
    `config/thresholds.yaml`, and `tests/test_abstain.py` pins them against
    each other.
    """
    if len(prediction_set) < 2:
        return False
    has_refer = any(g in refer for g in prediction_set)
    has_not = any(g not in refer for g in prediction_set)
    return has_refer and has_not


def decide(
    prediction_set: tuple[int, ...] | list[int],
    refer: tuple[int, ...] | None = None,
) -> AbstainDecision:
    """Turn a conformal prediction set into a clinical decision."""
    refer = refer_grades() if refer is None else refer
    ordered = tuple(sorted({int(g) for g in prediction_set}))

    if not ordered:
        # An empty set means the conformal threshold excluded every class. It
        # is not a grade of 0 and it is not a confident answer - it is a case
        # nobody should act on automatically.
        return AbstainDecision(
            prediction_set=(),
            abstain=True,
            grade=None,
            refer=False,
            reason="empty prediction set: no class met the conformal threshold",
        )

    if spans_clinical_actions(ordered, refer):
        return AbstainDecision(
            prediction_set=ordered,
            abstain=True,
            grade=None,
            refer=False,
            reason=(
                f"set {list(ordered)} spans refer and do-not-refer; a clinician decides"
            ),
        )

    all_refer = all(g in refer for g in ordered)
    return AbstainDecision(
        prediction_set=ordered,
        abstain=False,
        grade=ordered[0] if len(ordered) == 1 else None,
        refer=all_refer,
        reason=(
            f"set {list(ordered)} is entirely "
            f"{'refer' if all_refer else 'do-not-refer'}"
        ),
    )


# --------------------------------------------------- the MAPIE wrapper


class PrefitProbaEstimator:
    """Wraps already-computed probabilities as a prefit sklearn classifier.

    MAPIE needs an estimator with `predict_proba` and `classes_`. The DR
    backbone is a torch model that has already produced probabilities on the
    calibration fold, so re-running it inside MAPIE would be wasteful and would
    drag torch into the conformal path. This adapter takes the probability
    MATRIX as X and hands it straight back, which makes the conformal step pure
    numpy and testable without a GPU.
    """

    _estimator_type = "classifier"

    def __init__(self, n_classes: int = N_CLASSES) -> None:
        self.classes_ = np.arange(n_classes)
        self.n_features_in_ = n_classes

    def fit(self, X, y=None):
        return self

    def predict_proba(self, X):
        proba = np.asarray(X, dtype=float)
        if proba.ndim != 2 or proba.shape[1] != len(self.classes_):
            raise ValueError(
                f"expected an (n, {len(self.classes_)}) probability matrix, "
                f"got {proba.shape}"
            )
        return proba

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]

    def __sklearn_is_fitted__(self) -> bool:
        return True


class AbstentionWrapper:
    """SplitConformalClassifier plus the clinical-action abstention rule."""

    def __init__(
        self,
        estimator=None,
        confidence_level: float | None = None,
        refer: tuple[int, ...] | None = None,
    ) -> None:
        self.estimator = estimator or PrefitProbaEstimator()
        self.confidence_level = (
            conformal_confidence() if confidence_level is None else confidence_level
        )
        self.refer = refer_grades() if refer is None else refer
        self._mapie = None

    def conformalize(self, X_calib, y_calib) -> AbstentionWrapper:
        """Fit the conformal threshold on the CALIBRATION fold.

        `fit()` is deliberately NOT called: with `prefit=True` MAPIE 1.6.0
        raises if you do. See the module docstring.
        """
        from mapie.classification import SplitConformalClassifier

        self._mapie = SplitConformalClassifier(
            self.estimator,
            confidence_level=self.confidence_level,
            conformity_score="lac",
            prefit=True,
        )
        self._mapie.conformalize(np.asarray(X_calib, dtype=float), np.asarray(y_calib))
        return self

    @property
    def conformalized(self) -> bool:
        return self._mapie is not None

    def prediction_sets(self, X) -> list[tuple[int, ...]]:
        """Conformal sets for each row. Raises if not conformalized."""
        if not self.conformalized:
            raise RuntimeError(
                "conformalize() on the calibration fold before predicting sets"
            )
        _points, sets = self._mapie.predict_set(np.asarray(X, dtype=float))
        # (n, n_classes, n_levels); one level here, so squeeze the last axis.
        included = np.asarray(sets)[:, :, 0]
        classes = np.asarray(self.estimator.classes_)
        return [tuple(int(c) for c in classes[row]) for row in included]

    def decide_many(self, X) -> list[AbstainDecision]:
        return [decide(s, self.refer) for s in self.prediction_sets(X)]

    def coverage_report(self, X, y) -> dict:
        """Empirical coverage and the abstention cost, from metrics.py.

        The coverage cost ALWAYS travels with the accuracy gain - that is what
        `abstention_report` exists to enforce, so this calls it rather than
        reporting a bare abstention rate.
        """
        from netra.eval.metrics import abstention_report

        y = np.asarray(y)
        sets = self.prediction_sets(X)
        decisions = [decide(s, self.refer) for s in sets]

        covered = np.array(
            [int(truth) in s for s, truth in zip(sets, y, strict=True)], dtype=bool
        )
        admitted = np.array([not d.abstain for d in decisions], dtype=bool)
        # Correct only among admitted cases, and only where a single grade was
        # actually recorded; a non-abstained multi-grade set names no severity.
        correct_on_admitted = np.array(
            [
                d.grade == int(truth)
                for d, truth in zip(decisions, y, strict=True)
                if not d.abstain
            ],
            dtype=bool,
        )

        report = abstention_report(admitted, correct_on_admitted)
        report["confidence_level"] = self.confidence_level
        report["empirical_coverage"] = float(covered.mean()) if len(covered) else 0.0
        report["mean_set_size"] = (
            float(np.mean([len(s) for s in sets])) if sets else 0.0
        )
        return report
