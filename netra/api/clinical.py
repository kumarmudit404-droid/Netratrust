"""The clinical invariants the API enforces, in one place.

These are server-side checks, not formatting. The front end has its own copy of
the abstention rule in `netra/ui/src/lib/clinical.ts` so it can render; this
module is what decides what gets WRITTEN, and the two must agree. Both read the
same numbers from `config/thresholds.yaml`.
"""

from __future__ import annotations

from netra.api.config import refer_grades

GATE_VERDICTS = ("usable", "borderline", "reject")
VALID_GRADES = (0, 1, 2, 3, 4)


class ClinicalError(ValueError):
    """A request that would violate a clinical invariant. Becomes a 422."""


def is_referable(grade: int, refer: tuple[int, ...]) -> bool:
    return grade in refer


def spans_clinical_actions(prediction_set: list[int], refer: tuple[int, ...]) -> bool:
    """SPEC.md section 3: abstain when the set spans more than one ACTION class.

    Not when the set is merely large. `{0,1}` and `{0,3}` are both size 2 and
    only the second is alarming.
    """
    if len(prediction_set) < 2:
        return False
    return any(is_referable(g, refer) for g in prediction_set) and any(
        not is_referable(g, refer) for g in prediction_set
    )


def single_grade(prediction_set: list[int]) -> int | None:
    """The one grade to record, or None when the set does not justify one.

    Matches `singleGrade` in the UI's clinical.ts: a set of size > 1 records no
    grade even when it does not span actions, because `{2,3,4}` identifies an
    action but not a severity.
    """
    return prediction_set[0] if len(prediction_set) == 1 else None


def decide(
    gate_verdict: str,
    prediction_set: list[int] | None,
    refer: tuple[int, ...] | None = None,
) -> tuple[int | None, bool]:
    """Validate an encounter and return `(dr_grade, abstained)`.

    The first invariant in BUILD_RULES.md: a failed quality gate is NOT a negative DR
    result, it is "no result". A rejected image therefore carries no prediction
    set, no grade, and cannot be called an abstention either - nothing was
    graded, so there was nothing to abstain from.
    """
    refer = refer_grades() if refer is None else refer

    if gate_verdict not in GATE_VERDICTS:
        raise ClinicalError(
            f"gate_verdict must be one of {GATE_VERDICTS}, got {gate_verdict!r}"
        )

    if gate_verdict == "reject":
        if prediction_set is not None:
            raise ClinicalError(
                "a rejected image is 'no result': it cannot carry a prediction set"
            )
        return None, False

    if prediction_set is None:
        # An admitted image that was never graded. Still a recordable fact (the
        # gate ran), but it has no grade and is not an abstention.
        return None, False

    if not prediction_set:
        raise ClinicalError("prediction_set must not be empty; use null for no result")
    if len(set(prediction_set)) != len(prediction_set):
        raise ClinicalError("prediction_set must not repeat a grade")
    bad = [g for g in prediction_set if g not in VALID_GRADES]
    if bad:
        raise ClinicalError(f"prediction_set contains invalid grades {bad}")

    abstained = spans_clinical_actions(prediction_set, refer)
    grade = None if abstained else single_grade(prediction_set)
    return grade, abstained


def is_referable_encounter(
    dr_grade: int | None, abstained: bool, refer: tuple[int, ...] | None = None
) -> bool:
    """Whether a referral may be issued for this encounter.

    No referral is issued from an abstention (SPEC.md section 7): a clinician
    decides. And no referral is issued without a grade, which covers every
    rejected image.
    """
    if abstained or dr_grade is None:
        return False
    refer = refer_grades() if refer is None else refer
    return is_referable(dr_grade, refer)
