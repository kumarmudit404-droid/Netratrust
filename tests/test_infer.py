"""The inference entrypoint, and above all its not-available states.

Every test here that matters is a negative one. This module is what the API
will call in place of Lane B's simulated gate, so it is the last place a
fabricated grade could enter the system - and once a grade is in the ledger it
is, by design, there permanently.

Four distinct "no result" situations are each asserted to report themselves
rather than collapse into a guess:

1. the gate head is missing      -> quality_verdict None, model_version unloaded
2. the gate says reject          -> no grade, no prediction set, NOT an abstention
3. admitted, no DR checkpoint    -> no grade, model_version unloaded
4. graded, no conformal fit      -> abstain, because an argmax is not a set
"""

from __future__ import annotations

import numpy as np
import pytest

from netra.models.abstain import AbstentionWrapper, PrefitProbaEstimator
from netra.models.dr import UNLOADED, DRClassifier, ModelNotLoaded
from netra.models.infer import InferenceEngine, InferenceResult, sha256_file
from netra.models.quality import QualityGate
from tests.test_quality import _FakeFeatures, _FixedHead, fundus


@pytest.fixture
def image_file(tmp_path):
    """A real PNG on disk, so hashing and loading are exercised."""
    import cv2

    path = tmp_path / "fundus.png"
    cv2.imwrite(str(path), cv2.cvtColor(fundus(size=256), cv2.COLOR_RGB2BGR))
    return path


def loaded_classifier():
    """A DR classifier with weights present but not trained."""
    from netra.models import dr

    return DRClassifier(model=dr.build_model(pretrained=False))


def conformalized(n_classes: int = 5) -> AbstentionWrapper:
    rng = np.random.default_rng(7)
    proba = rng.dirichlet(np.ones(n_classes), size=300)
    labels = np.array([rng.choice(n_classes, p=row) for row in proba])
    return AbstentionWrapper(PrefitProbaEstimator(n_classes)).conformalize(
        proba, labels
    )


# ------------------------------------------------------------------ hashing


def test_the_image_hash_is_of_the_file_on_disk(image_file):
    import hashlib

    expected = hashlib.sha256(image_file.read_bytes()).hexdigest()
    assert sha256_file(image_file) == expected
    assert len(expected) == 64


def test_the_result_carries_the_hash_and_never_the_pixels(image_file):
    engine = InferenceEngine(
        gate=QualityGate(features=_FakeFeatures(), head=_FixedHead(0.99)),
        classifier=loaded_classifier(),
        abstention=conformalized(),
    )
    result = engine.run(image_file)
    assert result.image_sha256 == sha256_file(image_file)
    # Only the hash, the decisions and the metadata - never image data.
    assert set(result.as_dict()) == {
        "image_sha256",
        "quality_verdict",
        "cause",
        "prediction_set",
        "grade",
        "abstain",
        "model_version",
        "quality_score_milli",
        "note",
    }


# ------------------------------------------- 1. the gate head is missing


def test_no_gate_head_means_no_verdict_and_no_grade(image_file):
    engine = InferenceEngine(
        gate=QualityGate(features=_FakeFeatures(), head=None),
        classifier=loaded_classifier(),
        abstention=conformalized(),
    )
    result = engine.run(image_file)
    assert result.quality_verdict is None, "must not guess a verdict"
    assert result.quality_verdict != "usable", "and must never default to usable"
    assert result.prediction_set is None
    assert result.grade is None
    assert result.model_version == UNLOADED
    assert result.quality_score_milli is None
    assert "unavailable" in result.note


def test_a_missing_gate_cannot_be_posted_as_an_encounter(image_file):
    """Lane A's gate_verdict is not nullable, so there is nothing to post."""
    engine = InferenceEngine(
        gate=QualityGate(features=_FakeFeatures(), head=None),
        classifier=loaded_classifier(),
    )
    result = engine.run(image_file)
    with pytest.raises(ModelNotLoaded, match="no gate_verdict to post"):
        result.as_encounter_body(site_id="site-07", device_seq=1)


# ------------------------------------------------ 2. the gate says reject


def test_a_reject_is_no_result_not_a_grade_and_not_an_abstention(image_file):
    """CLAUDE.md invariant 1. A reject must carry no grade and no prediction
    set, and must not be recorded as an abstention - nothing was graded, so
    there was nothing to abstain from."""
    engine = InferenceEngine(
        gate=QualityGate(features=_FakeFeatures(), head=_FixedHead(0.02)),
        classifier=loaded_classifier(),
        abstention=conformalized(),
    )
    result = engine.run(image_file)
    assert result.quality_verdict == "reject"
    assert result.prediction_set is None
    assert result.grade is None
    assert result.abstain is False
    assert "no grade was computed" in result.note


def test_a_rejected_encounter_body_matches_what_lane_a_accepts(image_file):
    """Lane A returns 422 for a reject carrying a prediction set, so this body
    must send null."""
    engine = InferenceEngine(
        gate=QualityGate(features=_FakeFeatures(), head=_FixedHead(0.02)),
        classifier=loaded_classifier(),
        abstention=conformalized(),
    )
    body = engine.run(image_file).as_encounter_body("site-07", 3)
    assert body["gate_verdict"] == "reject"
    assert body["prediction_set"] is None
    assert set(body) == {
        "image_sha256",
        "gate_verdict",
        "cause",
        "prediction_set",
        "model_version",
        "site_id",
        "device_seq",
    }


def test_the_encounter_body_validates_against_lane_as_schema(image_file):
    """Pydantic is the real arbiter of the frozen request shape, so use it."""
    from netra.api.schemas import EncounterRequest

    engine = InferenceEngine(
        gate=QualityGate(features=_FakeFeatures(), head=_FixedHead(0.99)),
        classifier=loaded_classifier(),
        abstention=conformalized(),
    )
    body = engine.run(image_file).as_encounter_body("site-07", 12)
    parsed = EncounterRequest(**body)
    assert parsed.site_id == "site-07"
    assert parsed.device_seq == 12
    assert parsed.gate_verdict in {"usable", "borderline", "reject"}


# ---------------------------------------- 3. admitted, no DR checkpoint


def test_admitted_but_unloaded_dr_gives_a_verdict_and_no_grade(image_file):
    """The gate ran, so its verdict is real and worth recording. The grade is
    absent and model_version says so."""
    engine = InferenceEngine(
        gate=QualityGate(features=_FakeFeatures(), head=_FixedHead(0.99)),
        classifier=DRClassifier(checkpoint=None),
        abstention=conformalized(),
    )
    result = engine.run(image_file)
    assert result.quality_verdict == "usable"
    assert result.grade is None
    assert result.prediction_set is None
    assert result.model_version == UNLOADED
    assert "no DR checkpoint" in result.note
    # It can still be posted: a gate verdict with no grade is a real fact.
    body = result.as_encounter_body("site-07", 1)
    assert body["prediction_set"] is None
    assert body["model_version"] == UNLOADED


# ------------------------------------- 4. graded, no conformal calibration


def test_without_conformal_calibration_the_engine_abstains(image_file):
    """An argmax is not a prediction set, and a prediction set is what this
    project reports. So it abstains rather than quietly reporting a top-1."""
    engine = InferenceEngine(
        gate=QualityGate(features=_FakeFeatures(), head=_FixedHead(0.99)),
        classifier=loaded_classifier(),
        abstention=None,
    )
    result = engine.run(image_file)
    assert result.quality_verdict == "usable"
    assert result.abstain is True
    assert result.grade is None
    assert result.prediction_set is None
    assert "no conformal calibration" in result.note


def test_an_unconformalized_wrapper_is_treated_as_absent(image_file):
    engine = InferenceEngine(
        gate=QualityGate(features=_FakeFeatures(), head=_FixedHead(0.99)),
        classifier=loaded_classifier(),
        abstention=AbstentionWrapper(PrefitProbaEstimator(5)),  # never fitted
    )
    result = engine.run(image_file)
    assert result.abstain is True
    assert result.prediction_set is None


# ------------------------------------------------- the full path, on CPU


def test_the_full_path_produces_a_prediction_set(image_file):
    engine = InferenceEngine(
        gate=QualityGate(features=_FakeFeatures(), head=_FixedHead(0.99)),
        classifier=loaded_classifier(),
        abstention=conformalized(),
    )
    result = engine.run(image_file)
    assert result.quality_verdict == "usable"
    assert result.prediction_set is not None
    assert all(0 <= g < 5 for g in result.prediction_set)
    # The weights are untrained, so the version string must say so.
    assert ":untrained" in result.model_version
    assert isinstance(result, InferenceResult)


def test_the_model_version_is_unloaded_unless_both_halves_are_real(image_file):
    """Not a partial string: a caller writing this into a ledger needs to know
    the whole pipeline was real, not half of it."""
    gate_only = InferenceEngine(
        gate=QualityGate(features=_FakeFeatures(), head=_FixedHead(0.99)),
        classifier=DRClassifier(checkpoint=None),
    )
    assert gate_only.model_version == UNLOADED

    both = InferenceEngine(
        gate=QualityGate(features=_FakeFeatures(), head=_FixedHead(0.99)),
        classifier=loaded_classifier(),
    )
    assert both.model_version != UNLOADED
    assert "|" in both.model_version


def test_the_quality_score_is_an_integer_not_a_float(image_file):
    """It travels into a ledger payload, where floats break the chain."""
    engine = InferenceEngine(
        gate=QualityGate(features=_FakeFeatures(), head=_FixedHead(0.873)),
        classifier=loaded_classifier(),
        abstention=conformalized(),
    )
    result = engine.run(image_file)
    assert isinstance(result.quality_score_milli, int)
    assert result.quality_score_milli == 873


def test_a_missing_image_file_raises_rather_than_returning_a_result(tmp_path):
    engine = InferenceEngine(
        gate=QualityGate(features=_FakeFeatures(), head=_FixedHead(0.9)),
        classifier=loaded_classifier(),
    )
    with pytest.raises(FileNotFoundError):
        engine.run(tmp_path / "nope.png")


def test_the_cli_reports_unloaded_without_inventing_anything(image_file, capsys):
    """With nothing on disk the CLI must print an unloaded result, not a grade."""
    import json

    from netra.models.infer import main

    assert main([str(image_file), "--random-init"]) == 0
    printed = json.loads(capsys.readouterr().out.split("\nmodel_version")[0])
    assert printed["model_version"] == UNLOADED
    assert printed["grade"] is None
    assert printed["prediction_set"] is None
