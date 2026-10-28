"""Growing the corpus must move nothing. `netra/models/splits.py`.

The committed splits were frozen over 366 APTOS images; the Kaggle run grows
them to the full 3,662. `.claude/rules/ml.md` forbids re-shuffling, and the
only thing that makes growth distinguishable from a re-shuffle is that every
image which already had a fold still has the SAME fold afterwards.

That is not a comment here. `test_every_committed_id_is_reproduced_by_the_pure_function`
checks it against the real `data/splits/*.json` using nothing but the seed, so
it holds whatever the manifest grows to.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from netra.models import splits as S

REPO = Path(__file__).resolve().parents[1]
FROZEN = REPO / "data" / "splits"
EXTEND = REPO / "scripts" / "extend_splits.py"


def rows_for(ids_and_labels):
    return [
        {"image_id": i, "patient_id": i, "source": "aptos", "label": lab}
        for i, lab in ids_and_labels
    ]


# ------------------------------------------------ the pure bucketing function


def test_bucket_is_in_the_unit_interval_and_deterministic():
    for pid in ("a", "patient-1", "e4dcca36ceb4"):
        first = S.bucket(pid)
        assert 0.0 <= first < 1.0
        assert first == S.bucket(pid)


def test_bucket_depends_on_the_seed():
    assert S.bucket("abc", seed=1) != S.bucket("abc", seed=2)


def test_assign_fold_only_ever_returns_a_real_fold():
    folds = {S.assign_fold(f"p{i}") for i in range(500)}
    assert folds <= set(S.SPLIT_NAMES)
    assert folds == set(S.SPLIT_NAMES), "500 patients should reach all three folds"


def test_assign_fold_ignores_everything_except_seed_and_patient():
    """The growth guarantee, stated as a property of the function itself."""
    alone = S.assign_fold("patient-42")
    small, _ = S.assign_many(rows_for([("patient-42", "0")]))
    big, _ = S.assign_many(
        rows_for([(f"p{i}", "0") for i in range(999)] + [("patient-42", "0")])
    )
    in_small = next(n for n, ids in small.items() if "patient-42" in ids)
    in_big = next(n for n, ids in big.items() if "patient-42" in ids)
    assert alone == in_small == in_big


def test_a_patients_images_stay_together():
    rows = [
        {
            "image_id": f"img{p}_{i}",
            "patient_id": f"pat{p}",
            "source": "x",
            "label": "0",
        }
        for p in range(80)
        for i in range(3)
    ]
    splits, patient_fold = S.assign_many(rows)
    for name, ids in splits.items():
        for image_id in ids:
            assert patient_fold[image_id.split("_")[0].replace("img", "pat")] == name


# --------------------------------------------------------- check_preserved


def test_check_preserved_accepts_pure_growth():
    old = {"train": ["a"], "calib": ["b"], "test": ["c"]}
    new = {"train": ["a", "d"], "calib": ["b"], "test": ["c", "e"]}
    report = S.check_preserved(old, new)
    assert report["moved"] == 0
    assert report["n_added"] == 2
    assert report["added_per_fold"] == {"train": 1, "calib": 0, "test": 1}


def test_check_preserved_refuses_a_moved_image():
    old = {"train": ["a"], "calib": ["b"], "test": []}
    new = {"train": [], "calib": ["b", "a"], "test": []}
    with pytest.raises(S.SplitDrift, match="change fold"):
        S.check_preserved(old, new)


def test_check_preserved_refuses_a_dropped_image():
    """A shrink is as invisible downstream as a move, so it is refused too."""
    old = {"train": ["a", "b"], "calib": [], "test": []}
    new = {"train": ["a"], "calib": [], "test": []}
    with pytest.raises(S.SplitDrift, match="had a fold and now have none"):
        S.check_preserved(old, new)


def test_check_preserved_refuses_a_reseeded_split():
    """The realistic accident: someone re-runs the splitter with a new seed."""
    rows = rows_for([(f"p{i}", "0") for i in range(300)])
    old, _ = S.assign_many(rows, seed=S.SEED)
    new, _ = S.assign_many(rows, seed=S.SEED + 1)
    with pytest.raises(S.SplitDrift):
        S.check_preserved(old, new)


# --------------------------------------------------- against the REAL splits


def frozen_available() -> bool:
    return all((FROZEN / f"{n}.json").exists() for n in S.SPLIT_NAMES)


@pytest.mark.skipif(not frozen_available(), reason="data/splits not frozen yet")
def test_every_committed_id_is_reproduced_by_the_pure_function():
    """The guarantee the Kaggle run relies on, checked on the committed data.

    Needs no manifest (which is gitignored): APTOS has no patient id, so
    `patient_id == image_id` and the fold follows from the seed alone.
    """
    committed = S.read_splits(FROZEN)
    checked = 0
    for name, ids in committed.items():
        for image_id in ids:
            assert S.assign_fold(image_id) == name, (
                f"{image_id} is committed to {name} but the seed puts it in "
                f"{S.assign_fold(image_id)}"
            )
            checked += 1
    assert checked == 366, f"expected the 366 frozen APTOS images, saw {checked}"


@pytest.mark.skipif(not frozen_available(), reason="data/splits not frozen yet")
def test_growing_the_committed_splits_preserves_all_366(tmp_path):
    """Simulate the Kaggle growth with synthetic extra ids and check the report."""
    committed = S.read_splits(FROZEN)
    existing = [i for ids in committed.values() for i in ids]
    grown_rows = rows_for(
        [(i, "0") for i in existing] + [(f"grown{i:05d}", "1") for i in range(3296)]
    )
    grown, _ = S.assign_many(grown_rows)
    report = S.check_preserved(committed, grown)
    assert report["n_preserved"] == 366
    assert report["n_added"] == 3296
    assert report["moved"] == 0


# ------------------------------------------------------ the script end to end


def write_aptos_csv(path: Path, pairs) -> None:
    path.write_text("id_code,diagnosis\n" + "".join(f"{i},{v}\n" for i, v in pairs))


def run_extend(args, expect: int = 0):
    proc = subprocess.run(
        [sys.executable, str(EXTEND), *map(str, args)],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert proc.returncode == expect, proc.stdout + proc.stderr
    return proc.stdout + proc.stderr


def test_extend_splits_writes_a_superset_that_moves_nothing(tmp_path):
    old_dir = tmp_path / "old"
    old_dir.mkdir()
    first = [(f"img{i:04d}", str(i % 5)) for i in range(60)]
    old_splits, _ = S.assign_many(rows_for(first))
    for name, ids in old_splits.items():
        (old_dir / f"{name}.json").write_text(json.dumps(sorted(ids), indent=1))

    manifest = tmp_path / "old_manifest.csv"
    S.write_manifest(rows_for(first), manifest)

    csv_path = tmp_path / "labels.csv"
    grown = first + [(f"img{i:04d}", "0") for i in range(60, 400)]
    write_aptos_csv(csv_path, grown)

    run_extend(
        [
            "--aptos-csv",
            csv_path,
            "--old-splits",
            old_dir,
            "--old-manifest",
            manifest,
            "--out-manifest",
            tmp_path / "m.csv",
            "--out-splits",
            tmp_path / "new",
        ]
    )
    new = S.read_splits(tmp_path / "new")
    assert sum(len(v) for v in new.values()) == 400
    S.check_preserved(old_splits, new)  # raises if anything moved


def test_extend_splits_refuses_a_relabelled_image(tmp_path):
    """Growth may add rows. It may not change what an existing row means."""
    old_dir = tmp_path / "old"
    old_dir.mkdir()
    first = [(f"img{i:04d}", "0") for i in range(40)]
    old_splits, _ = S.assign_many(rows_for(first))
    for name, ids in old_splits.items():
        (old_dir / f"{name}.json").write_text(json.dumps(sorted(ids), indent=1))
    manifest = tmp_path / "old_manifest.csv"
    S.write_manifest(rows_for(first), manifest)

    csv_path = tmp_path / "labels.csv"
    write_aptos_csv(csv_path, [("img0000", "4")] + first[1:])

    out = run_extend(
        [
            "--aptos-csv",
            csv_path,
            "--old-splits",
            old_dir,
            "--old-manifest",
            manifest,
            "--out-manifest",
            tmp_path / "m.csv",
            "--out-splits",
            tmp_path / "new",
        ],
        expect=1,
    )
    assert "changed label" in out
    assert not (tmp_path / "new").exists(), "it wrote splits despite refusing"


def test_extend_splits_dry_run_writes_nothing(tmp_path):
    old_dir = tmp_path / "old"
    old_dir.mkdir()
    first = [(f"img{i:04d}", "0") for i in range(40)]
    old_splits, _ = S.assign_many(rows_for(first))
    for name, ids in old_splits.items():
        (old_dir / f"{name}.json").write_text(json.dumps(sorted(ids), indent=1))
    manifest = tmp_path / "old_manifest.csv"
    S.write_manifest(rows_for(first), manifest)
    csv_path = tmp_path / "labels.csv"
    write_aptos_csv(csv_path, first + [("extra0", "1")])

    run_extend(
        [
            "--aptos-csv",
            csv_path,
            "--old-splits",
            old_dir,
            "--old-manifest",
            manifest,
            "--out-manifest",
            tmp_path / "m.csv",
            "--out-splits",
            tmp_path / "new",
            "--dry-run",
        ]
    )
    assert not (tmp_path / "m.csv").exists()
    assert not (tmp_path / "new").exists()


def load_extend_module():
    """Import `scripts/extend_splits.py`, which is a script and not a package."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_extend_splits", EXTEND)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_find_aptos_label_csvs_matches_on_the_header_not_the_name(tmp_path):
    """A filename match would pick up `sample_submission.csv`. A header match does not."""
    (tmp_path / "a").mkdir()
    write_aptos_csv(tmp_path / "a" / "weird_name.csv", [("x", "0")])
    (tmp_path / "sample_submission.csv").write_text("id_code,prediction\nx,0\n")
    (tmp_path / "notes.txt").write_text("id_code,diagnosis")

    found = load_extend_module().find_aptos_label_csvs(tmp_path)
    assert [p.name for p in found] == ["weird_name.csv"]


def test_find_aptos_label_csvs_on_a_missing_root_is_empty_not_an_error(tmp_path):
    """On a box with no /kaggle/input this must return [], not explode."""
    assert load_extend_module().find_aptos_label_csvs(tmp_path / "nope") == []
