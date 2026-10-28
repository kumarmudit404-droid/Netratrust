"""EyeQ label handling: `netra/models/eyeq.py`.

T-08 was blocked because EyeQ publishes labels and no pixels, and its pixels
are EyePACS's ~89 GiB. On Kaggle EyePACS is mounted, so the labels become
reachable - and everything that can go wrong then is a silent mismatch between
28,792 label rows and whatever the mount actually holds.

So these tests are mostly about counting honestly: what a parse drops, what a
mount fails to resolve, and whether a patient can end up in two folds. None of
them touch the network or an image.
"""

from __future__ import annotations

import numpy as np
import pytest

from netra.models import eyeq

TRAIN_HEADER = ",image,quality,DR_grade\n"


def write_labels(path, rows) -> None:
    body = "".join(f"{i},{name},{q},{g}\n" for i, (name, q, g) in enumerate(rows))
    path.write_text(TRAIN_HEADER + body)


def row(name="10_left.jpeg", quality=0, dr=0):
    stem = name.rsplit(".", 1)[0]
    patient, eye = stem.split("_")
    return eyeq.EyeQRow(name, patient, eye, quality, dr)


# ----------------------------------------------------------------- parsing


def test_parses_the_real_eyeq_header(tmp_path):
    path = tmp_path / "Label_EyeQ_train.csv"
    write_labels(path, [("10009_left.jpeg", 0, 0), ("10014_right.jpeg", 2, 3)])
    rows, report = eyeq.parse_label_csv(path)

    assert [r.image for r in rows] == ["10009_left.jpeg", "10014_right.jpeg"]
    assert [r.patient_id for r in rows] == ["10009", "10014"]
    assert [r.eye for r in rows] == ["left", "right"]
    assert [r.quality for r in rows] == [0, 2]
    assert [r.dr_grade for r in rows] == [0, 3]
    assert report["retained_fraction"] == 1.0
    assert report["n_patients"] == 2


def test_the_three_level_scale_collapses_to_gradable_vs_reject():
    """Good and Usable are both gradable. Only Reject is not."""
    assert row(quality=eyeq.QUALITY_GOOD).gradable == 1
    assert row(quality=eyeq.QUALITY_USABLE).gradable == 1
    assert row(quality=eyeq.QUALITY_REJECT).gradable == 0


def test_a_filename_with_no_recoverable_patient_is_dropped_not_guessed(tmp_path):
    """A fabricated patient id would silently break the fold guarantee."""
    path = tmp_path / "labels.csv"
    write_labels(path, [("10_left.jpeg", 0, 0), ("mystery.jpeg", 0, 0)])
    rows, report = eyeq.parse_label_csv(path)
    assert len(rows) == 1
    assert report["dropped_unparseable_name"] == 1
    assert report["retained_fraction"] == 0.5


def test_a_quality_outside_the_published_scale_is_dropped(tmp_path):
    path = tmp_path / "labels.csv"
    write_labels(
        path, [("10_left.jpeg", 0, 0), ("11_left.jpeg", 7, 0), ("12_left.jpeg", "x", 0)]
    )
    rows, report = eyeq.parse_label_csv(path)
    assert len(rows) == 1
    assert report["dropped_bad_quality"] == 2


def test_duplicate_rows_are_dropped_once(tmp_path):
    path = tmp_path / "labels.csv"
    write_labels(path, [("10_left.jpeg", 0, 0), ("10_left.jpeg", 2, 0)])
    rows, report = eyeq.parse_label_csv(path)
    assert len(rows) == 1
    assert report["dropped_duplicate"] == 1


def test_an_empty_or_malformed_csv_raises(tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text(TRAIN_HEADER)
    with pytest.raises(ValueError, match="no rows"):
        eyeq.parse_label_csv(empty)

    wrong = tmp_path / "wrong.csv"
    wrong.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError, match="missing columns"):
        eyeq.parse_label_csv(wrong)


def test_quality_counts_names_all_three_levels_even_at_zero():
    counts = eyeq.quality_counts([row(quality=0), row("11_left.jpeg", 0)])
    assert counts == {"good": 2, "usable": 0, "reject": 0}


# --------------------------------------------------- finding mounted images


def touch_images(directory, names):
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_bytes(b"not-really-an-image")


def test_find_eyepacs_roots_ranks_by_how_many_images_it_holds(tmp_path):
    touch_images(tmp_path / "small", [f"{i}_left.jpeg" for i in range(3)])
    touch_images(tmp_path / "big", [f"{i}_right.jpeg" for i in range(9)])
    found = eyeq.find_eyepacs_roots(tmp_path, min_files=2)
    assert [d.name for d in (d for d, _ in found)] == ["big", "small"]
    assert [n for _, n in found] == [9, 3]


def test_find_eyepacs_roots_ignores_directories_that_are_not_eyepacs(tmp_path):
    """APTOS filenames are hex ids, not `<digits>_<eye>`, and must not match."""
    touch_images(tmp_path / "aptos", [f"e4dcca36ceb{i}.png" for i in range(9)])
    touch_images(tmp_path / "eyepacs", [f"{i}_left.jpeg" for i in range(9)])
    found = eyeq.find_eyepacs_roots(tmp_path, min_files=2)
    assert [d.name for d, _ in found] == ["eyepacs"]


def test_find_eyepacs_roots_on_a_missing_root_is_empty_not_an_error(tmp_path):
    assert eyeq.find_eyepacs_roots(tmp_path / "nothing-here") == []


def test_find_eyepacs_roots_respects_min_files(tmp_path):
    touch_images(tmp_path / "tiny", ["1_left.jpeg"])
    assert eyeq.find_eyepacs_roots(tmp_path, min_files=50) == []


def test_index_and_resolve_report_the_retained_fraction(tmp_path):
    touch_images(tmp_path / "imgs", ["10_left.jpeg", "11_right.jpeg"])
    index = eyeq.index_images([tmp_path / "imgs"])
    rows = [row("10_left.jpeg"), row("11_right.jpeg"), row("99_left.jpeg", 2)]

    matched, report = eyeq.resolve(rows, index)
    assert len(matched) == 2
    assert report["n_unmatched"] == 1
    assert report["retained_fraction"] == pytest.approx(2 / 3)
    assert report["quality_counts"]["good"] == 2


def test_resolve_matches_across_extensions(tmp_path):
    """A resized mirror may ship .png where EyeQ's CSV says .jpeg."""
    touch_images(tmp_path / "imgs", ["10_left.png"])
    index = eyeq.index_images([tmp_path / "imgs"])
    matched, _ = eyeq.resolve([row("10_left.jpeg")], index)
    assert len(matched) == 1
    assert matched[0][1].suffix == ".png"


def test_resolve_on_an_empty_mount_is_zero_not_a_crash():
    matched, report = eyeq.resolve([row()], {})
    assert matched == []
    assert report["retained_fraction"] == 0.0


# ------------------------------------------------------------------- folds


def test_the_published_eyeq_split_is_patient_disjoint(tmp_path):
    """Asserted here because the notebook relies on it instead of re-splitting."""
    fit = [
        (row("10_left.jpeg"), tmp_path / "a"),
        (row("10_right.jpeg"), tmp_path / "b"),
    ]
    evaluate = [(row("20_left.jpeg"), tmp_path / "c")]
    assert eyeq.patient_disjoint({"fit": fit, "eval": evaluate})


def test_patient_disjoint_catches_a_patient_in_two_folds(tmp_path):
    fit = [(row("10_left.jpeg"), tmp_path / "a")]
    evaluate = [(row("10_right.jpeg"), tmp_path / "b")]
    assert not eyeq.patient_disjoint({"fit": fit, "eval": evaluate})


def test_hash_holdout_keeps_both_eyes_of_a_patient_together(tmp_path):
    pairs = []
    for patient in range(200):
        for eye in ("left", "right"):
            pairs.append((row(f"{patient}_{eye}.jpeg"), tmp_path / f"{patient}_{eye}"))
    folds = eyeq.hash_holdout(pairs)
    assert eyeq.patient_disjoint(folds)
    assert folds["fit"] and folds["eval"]
    assert sum(len(v) for v in folds.values()) == 400


def test_hash_holdout_is_reproducible_from_the_seed(tmp_path):
    pairs = [(row(f"{i}_left.jpeg"), tmp_path / str(i)) for i in range(120)]
    first = eyeq.hash_holdout(pairs)
    second = eyeq.hash_holdout(pairs)
    assert [r.image for r, _ in first["fit"]] == [r.image for r, _ in second["fit"]]
    assert first != eyeq.hash_holdout(pairs, seed=1)


# ------------------------------------------------------------------ capping


def test_cap_per_class_bounds_each_class_and_reports_what_it_dropped(tmp_path):
    pairs = [(row(f"{i}_left.jpeg", quality=0), tmp_path / str(i)) for i in range(50)]
    pairs += [
        (row(f"{i}_right.jpeg", quality=2), tmp_path / str(i)) for i in range(50, 60)
    ]

    _capped, report = eyeq.cap_per_class(pairs, per_class=10)
    assert report["quality_counts"] == {"good": 10, "usable": 0, "reject": 10}
    assert report["n_in"] == 60
    assert report["n_out"] == 20
    assert report["retained_fraction"] == pytest.approx(1 / 3)


def test_cap_per_class_with_no_cap_keeps_everything(tmp_path):
    pairs = [(row(f"{i}_left.jpeg"), tmp_path / str(i)) for i in range(7)]
    capped, report = eyeq.cap_per_class(pairs, per_class=None)
    assert len(capped) == 7
    assert report["retained_fraction"] == 1.0


def test_cap_per_class_never_moves_a_patient_across_the_fold_boundary(tmp_path):
    """Capping runs INSIDE a fold, so disjointness must survive it."""
    pairs = []
    for patient in range(100):
        for eye in ("left", "right"):
            pairs.append(
                (row(f"{patient}_{eye}.jpeg", quality=patient % 3), tmp_path / "x")
            )
    folds = eyeq.hash_holdout(pairs)
    capped = {name: eyeq.cap_per_class(v, per_class=5)[0] for name, v in folds.items()}
    assert eyeq.patient_disjoint(capped)


def test_labels_for_is_the_binary_target():
    pairs = [(row(quality=0), None), (row(quality=1), None), (row(quality=2), None)]
    assert list(eyeq.labels_for(pairs)) == [1, 1, 0]


# ---------------------------------------------------------------- reporting


def test_gate_report_numbers_all_come_from_metrics_and_carry_an_interval():
    from netra.eval import metrics

    y = np.array([1, 1, 0, 0, 1, 0])
    p = np.array([0.9, 0.8, 0.1, 0.2, 0.3, 0.6])
    report = eyeq.gate_report(y, p)

    assert report["n"] == 6
    assert report["n_correct"] == 4
    assert report["accuracy"] == pytest.approx(4 / 6)
    assert report["accuracy_ci"] == metrics.wilson_interval(4, 6)
    proba = np.column_stack([1 - p, p])
    assert report["brier"] == pytest.approx(metrics.brier(y, proba, labels=[0, 1]))
    assert report["nll"] == pytest.approx(metrics.nll(y, proba, labels=[0, 1]))
    assert report["n_positive"] == 3


def test_gate_report_on_a_perfect_head_is_one_not_an_error():
    report = eyeq.gate_report(np.array([1, 0]), np.array([1.0, 0.0]))
    assert report["accuracy"] == 1.0
    assert report["brier"] == pytest.approx(0.0)


def test_verdict_report_counts_ungradable_images_admitted_as_usable():
    """The failure that matters: an ungradable image becoming a grade."""

    class FakeGate:
        usable_min_p = 0.70
        reject_max_p = 0.30

        def verdict_from_p(self, p):
            if p >= self.usable_min_p:
                return "usable"
            return "reject" if p <= self.reject_max_p else "borderline"

    y = np.array([1, 1, 0, 0, 0])
    p = np.array([0.95, 0.50, 0.10, 0.80, 0.45])
    report = eyeq.verdict_report(FakeGate(), p, y)

    assert report["by_true_label"]["gradable"] == {
        "usable": 1,
        "borderline": 1,
        "reject": 0,
    }
    assert report["by_true_label"]["reject"] == {
        "usable": 1,
        "borderline": 1,
        "reject": 1,
    }
    assert report["ungradable_admitted_as_usable"] == 1
    assert report["cutoffs"] == {"usable_min_p": 0.70, "reject_max_p": 0.30}


# -------------------------------------------------------- the feature pass


def test_features_for_paths_skips_an_unreadable_file_and_says_so(tmp_path):
    """Three bad JPEGs in a 28k mount must not end a nine-hour session."""

    class FakeFeatures:
        def batch(self, images, batch_size=1):
            return np.stack([np.full(4, float(img.mean())) for img in images])

    good = tmp_path / "ok.png"
    bad = tmp_path / "broken.png"
    import cv2

    cv2.imwrite(str(good), np.full((32, 32, 3), 200, dtype=np.uint8))
    bad.write_bytes(b"not an image")

    X, kept, report = eyeq.features_for_paths(
        FakeFeatures(),
        [good, bad, good],
        batch_size=2,
        progress_every=0,
        log=lambda *_: None,
    )
    assert kept == [0, 2]
    assert X.shape == (2, 4)
    assert report["n_unreadable"] == 1
    assert report["retained_fraction"] == pytest.approx(2 / 3)
    assert "broken.png" in report["first_failures"][0]


def test_features_for_paths_on_nothing_returns_an_empty_report():
    class FakeFeatures:
        def batch(self, images, batch_size=1):  # pragma: no cover - never called
            raise AssertionError("should not be called")

    X, kept, report = eyeq.features_for_paths(FakeFeatures(), [], progress_every=0)
    assert kept == []
    assert X.shape == (0, 0)
    assert report["retained_fraction"] == 0.0


def test_label_urls_point_at_the_published_repository():
    """A vendored label file would make provenance a matter of trust."""
    assert eyeq.LABEL_URLS["train"].endswith("/data/Label_EyeQ_train.csv")
    assert eyeq.LABEL_URLS["test"].endswith("/data/Label_EyeQ_test.csv")
    assert all(
        u.startswith("https://raw.githubusercontent.com/HzFu/EyeQ/")
        for u in eyeq.LABEL_URLS.values()
    )
