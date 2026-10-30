"""The DR classifier, the dataset over frozen splits, and the training loop.

Two assertions carry this file:

* an unloaded classifier RAISES rather than returning a grade, and
* a `--smoke` checkpoint reports `model_version` ending `:untrained`.

The second one is not hypothetical. The first version of `DRClassifier._load`
set `trained = True` unconditionally, so a two-step smoke artifact loaded and
reported itself as a real model. That was found by running the smoke and
reading the version string, not by reasoning about it.
"""

from __future__ import annotations

import numpy as np
import pytest

from netra.models import dr
from netra.models.dataset import VALID_SPLITS, collect, read_split
from netra.models.dr import DRClassifier, ModelNotLoaded, proba_to_milli
from tests.test_quality import fundus

# ----------------------------------------------- refusing to invent a grade


def test_an_unloaded_classifier_has_no_model_version(no_model_artifacts):
    clf = DRClassifier(checkpoint=None)
    assert clf.available is False
    assert clf.model_version == dr.UNLOADED


def test_an_unloaded_classifier_raises_instead_of_returning_a_grade(
    no_model_artifacts,
):
    """The single most important assertion here. A grade from random weights is
    indistinguishable from a real one by the time it reaches a referral."""
    clf = DRClassifier(checkpoint=None)
    with pytest.raises(ModelNotLoaded, match="no grade to give"):
        clf.predict(fundus(size=128))
    with pytest.raises(ModelNotLoaded):
        clf.predict_proba(fundus(size=128))


def test_a_missing_checkpoint_path_is_reported_not_silently_ignored(tmp_path):
    clf = DRClassifier(checkpoint=tmp_path / "nope.pt")
    assert clf.available is False
    assert "no checkpoint at" in (clf.load_error or "")


def test_a_corrupt_checkpoint_degrades_to_unloaded(tmp_path):
    bad = tmp_path / "bad.pt"
    bad.write_bytes(b"not a torch checkpoint")
    clf = DRClassifier(checkpoint=bad)
    assert clf.available is False
    assert clf.load_error
    with pytest.raises(ModelNotLoaded):
        clf.predict(fundus(size=128))


def test_the_checkpoint_env_var_is_honoured(monkeypatch, tmp_path):
    monkeypatch.setenv(dr.CHECKPOINT_ENV, str(tmp_path / "absent.pt"))
    clf = DRClassifier()
    assert clf.available is False
    assert "absent.pt" in (clf.load_error or "")


# ------------------------------------------------------ ledger-safe output


def test_proba_to_milli_sums_to_exactly_one_thousand():
    """A distribution that does not sum to 1000 looks like a bug in whatever
    reads the ledger, so the largest remainder takes the slack."""
    for proba in (
        np.array([0.2, 0.2, 0.2, 0.2, 0.2]),
        np.array([1 / 3, 1 / 3, 1 / 3]),
        np.array([0.9999, 0.0001]),
        np.array([0.1234, 0.2345, 0.3456, 0.1234, 0.1731]),
    ):
        milli = proba_to_milli(proba)
        assert sum(milli) == 1000, f"{proba} -> {milli}"
        assert all(isinstance(v, int) for v in milli)


def test_proba_to_milli_keeps_the_ranking():
    milli = proba_to_milli(np.array([0.05, 0.10, 0.60, 0.15, 0.10]))
    assert int(np.argmax(milli)) == 2


def test_proba_to_milli_normalises_unnormalised_input():
    assert sum(proba_to_milli(np.array([2.0, 2.0, 4.0]))) == 1000


def test_proba_to_milli_refuses_a_degenerate_distribution():
    for bad in (np.zeros(5), np.array([np.nan, 1.0]), np.array([-1.0, -1.0])):
        with pytest.raises(ValueError, match="finite and positive"):
            proba_to_milli(bad)


def test_prediction_carries_no_float():
    """Floats are banned from ledger payloads (CLAUDE.md)."""
    prediction = dr.DRPrediction(
        proba_milli=(100, 200, 300, 200, 200), model_version="x"
    )
    assert all(isinstance(v, int) for v in prediction.proba_milli)
    assert prediction.argmax == 2
    assert prediction.as_float().sum() == pytest.approx(1.0)


# --------------------------------------------- the dataset over frozen splits


def test_the_dataset_refuses_a_split_that_is_not_one_of_the_three():
    with pytest.raises(ValueError, match="split must be one of"):
        read_split("validation")


def test_the_test_split_requires_an_explicit_opt_in(tmp_path):
    """rules.md: the test split is touched exactly once, at the end. An
    accidental split="test" in a training script is the mistake that cannot be
    undone afterwards."""
    with pytest.raises(PermissionError, match="touched exactly once"):
        collect("test", tmp_path)


def test_the_frozen_splits_are_readable_and_named():
    for name in VALID_SPLITS:
        ids = read_split(name)
        assert ids and all(isinstance(i, str) for i in ids)


def test_collect_reports_the_retained_fraction_when_images_are_absent(tmp_path):
    """The failure this report exists to catch: a 219-id split silently
    becoming a 0-image experiment."""
    examples, report = collect("train", tmp_path / "empty")
    assert examples == []
    assert report["n_in_split"] > 0
    assert report["n_present"] == 0
    assert report["retained_fraction"] == 0.0
    assert report["missing_image_file"] == report["n_in_split"]


# ---------------------------------------------------- the model, on CPU


def test_build_model_produces_a_five_class_head():
    model = dr.build_model(pretrained=False)
    assert model.num_classes == dr.N_CLASSES


def test_a_forward_pass_runs_on_cpu_and_gives_one_row_per_class():
    """CPU smoke of the real backbone at 512px with random weights. The VALUES
    are meaningless, which is why nothing here asserts a grade."""
    import torch

    model = dr.build_model(pretrained=False).eval()
    batch = torch.zeros(2, 3, 512, 512)
    with torch.no_grad():
        logits = model(batch)
    assert logits.shape == (2, dr.N_CLASSES)
    assert torch.isfinite(logits).all()


def test_an_in_memory_model_is_reported_as_untrained_unless_told_otherwise():
    model = dr.build_model(pretrained=False)
    clf = DRClassifier(model=model)
    assert clf.available is True
    assert clf.model_version.endswith(":untrained")
    # It will predict, because weights are present - but the version string is
    # what stops the output being read as clinical.
    prediction = clf.predict(fundus(size=128))
    assert sum(prediction.proba_milli) == 1000
    assert prediction.model_version.endswith(":untrained")


def test_a_smoke_checkpoint_round_trips_as_untrained(tmp_path):
    """The defect that was actually shipped and then fixed: `_load` set
    trained=True unconditionally, so a two-step artifact looked real."""
    from netra.models.train import save

    path = tmp_path / "smoke.pt"
    save(dr.build_model(pretrained=False), path, trained=False)
    clf = DRClassifier(checkpoint=path)
    assert clf.available is True
    assert clf.trained is False
    assert clf.model_version == f"{dr.BACKBONE}@512:untrained"


def test_a_checkpoint_marked_trained_reports_its_name(tmp_path):
    from netra.models.train import save

    path = tmp_path / "convnext-epoch7.pt"
    save(dr.build_model(pretrained=False), path, trained=True)
    clf = DRClassifier(checkpoint=path)
    assert clf.trained is True
    assert clf.model_version == f"{dr.BACKBONE}@512:convnext-epoch7"


def test_a_bare_state_dict_is_assumed_untrained(tmp_path):
    """Provenance-free weights get the cautious reading, not the generous one."""
    import torch

    path = tmp_path / "bare.pt"
    torch.save(dr.build_model(pretrained=False).state_dict(), path)
    clf = DRClassifier(checkpoint=path)
    assert clf.available is True
    assert clf.trained is False
    assert clf.model_version.endswith(":untrained")


# ------------------------------------------------------------ training loop


def test_evaluate_returns_none_qwk_for_a_single_grade_fold():
    """kappa is nan on one grade, and publishing nan as a number is worse than
    saying it is not measurable."""
    from netra.models.train import evaluate

    model = dr.build_model(pretrained=False).eval()
    # No files are read: an empty example list exercises the n=0 branch.
    result = evaluate(model, [], batch_size=2, device="cpu")
    assert result == {"n": 0, "qwk": None, "accuracy": None}


def test_train_refuses_when_no_training_images_are_present(tmp_path):
    from netra.models.train import train

    with pytest.raises(SystemExit, match="no training images"):
        train(images_dir=tmp_path / "nothing", epochs=1, smoke=True, pretrained=False)
