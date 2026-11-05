"""Reading a frozen split off a mount: `netra/models/dataset.py`.

Two failures these cover, both of which look like success until you read the
numbers. The first is pointing `images_dir` at a directory that does not hold
the corpus - `collect()` then returns a handful of examples and a
`retained_fraction` nobody looked at. The second is a mirror that ships `.jpg`
where the committed splits were built against `.png`.
"""

from __future__ import annotations

import csv
import json

import pytest

from netra.models import dataset


def write_split(directory, name, ids):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.json").write_text(json.dumps(sorted(ids)))


def write_manifest(path, ids, label="0"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["image_id", "patient_id", "source", "label"])
        w.writeheader()
        for i in ids:
            w.writerow(
                {"image_id": i, "patient_id": i, "source": "aptos", "label": label}
            )


def touch(directory, names):
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_bytes(b"x")


# ------------------------------------------------------- extension handling


def test_resolve_image_path_prefers_png_then_jpg(tmp_path):
    touch(tmp_path, ["a.jpg", "b.png", "b.jpg"])
    assert dataset.resolve_image_path(tmp_path, "a").name == "a.jpg"
    assert dataset.resolve_image_path(tmp_path, "b").name == "b.png"
    assert dataset.resolve_image_path(tmp_path, "missing") is None


def test_collect_finds_a_mirror_that_ships_jpg(tmp_path):
    """The committed splits were built against .png; a mirror may not agree."""
    ids = ["img0", "img1"]
    splits = tmp_path / "splits"
    write_split(splits, "calib", ids)
    manifest = tmp_path / "manifest.csv"
    write_manifest(manifest, ids)
    images = tmp_path / "images"
    touch(images, ["img0.jpg", "img1.jpeg"])

    examples, report = dataset.collect(
        "calib", images, splits_dir=splits, manifest=manifest
    )
    assert report["retained_fraction"] == 1.0
    assert sorted(e.path.name for e in examples) == ["img0.jpg", "img1.jpeg"]


def test_collect_reports_a_partial_mount_rather_than_shrinking_quietly(tmp_path):
    ids = [f"img{i}" for i in range(10)]
    splits = tmp_path / "splits"
    write_split(splits, "calib", ids)
    manifest = tmp_path / "manifest.csv"
    write_manifest(manifest, ids)
    images = tmp_path / "images"
    touch(images, ["img0.png", "img1.png"])

    examples, report = dataset.collect(
        "calib", images, splits_dir=splits, manifest=manifest
    )
    assert len(examples) == 2
    assert report["n_in_split"] == 10
    assert report["missing_image_file"] == 8
    assert report["retained_fraction"] == pytest.approx(0.2)


# -------------------------------------------------------- finding the mount


def test_find_images_dir_picks_the_directory_that_holds_the_split(tmp_path):
    ids = [f"img{i}" for i in range(30)]
    touch(tmp_path / "wrong", [f"other{i}.png" for i in range(30)])
    touch(tmp_path / "right" / "nested", [f"{i}.png" for i in ids])

    found = dataset.find_images_dir(ids, tmp_path, min_hits=20)
    assert [d.name for d, _ in found] == ["nested"]
    assert found[0][1] == 30


def test_find_images_dir_ranks_a_fuller_mount_first(tmp_path):
    ids = [f"img{i}" for i in range(40)]
    touch(tmp_path / "partial", [f"{i}.png" for i in ids[:25]])
    touch(tmp_path / "full", [f"{i}.png" for i in ids])

    found = dataset.find_images_dir(ids, tmp_path, min_hits=20)
    assert [d.name for d, _ in found] == ["full", "partial"]
    assert [n for _, n in found] == [40, 25]


def test_find_images_dir_ignores_a_directory_below_min_hits(tmp_path):
    ids = [f"img{i}" for i in range(30)]
    touch(tmp_path / "scraps", [f"{i}.png" for i in ids[:3]])
    assert dataset.find_images_dir(ids, tmp_path, min_hits=20) == []


def test_find_images_dir_on_a_missing_root_is_empty_not_an_error(tmp_path):
    assert dataset.find_images_dir(["a"], tmp_path / "nope") == []


def test_find_images_dir_with_no_ids_is_empty(tmp_path):
    assert dataset.find_images_dir([], tmp_path) == []


def test_find_images_dir_skips_checkpoint_and_cache_directories(tmp_path):
    ids = [f"img{i}" for i in range(30)]
    touch(tmp_path / ".ipynb_checkpoints", [f"{i}.png" for i in ids])
    assert dataset.find_images_dir(ids, tmp_path, min_hits=20) == []


# --------------------------------------------------------- the test split


def test_collect_still_refuses_the_test_split_without_the_explicit_flag(tmp_path):
    """`docs/rules/ml.md`: touched exactly once, at the end."""
    write_split(tmp_path / "splits", "test", ["img0"])
    with pytest.raises(PermissionError, match="exactly once"):
        dataset.collect("test", tmp_path / "images", splits_dir=tmp_path / "splits")
