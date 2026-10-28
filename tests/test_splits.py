"""The split invariants from `.claude/rules/ml.md`.

Patient-level duplication across splits is described in that file as the most
common and most fatal error in this literature, and the reason it is fatal is
that it is INVISIBLE in the results - it just makes every number better. So it
gets a test rather than a comment.

These run `scripts/make_splits.py` as a subprocess on temporary manifests, and
also check the real frozen splits committed under `data/splits/`.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "make_splits.py"
FROZEN = REPO / "data" / "splits"
SPLIT_NAMES = ("train", "calib", "test")


def write_manifest(path: Path, rows: list[tuple[str, str, str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["image_id", "patient_id", "source", "label"])
        w.writerows(rows)


def run_splits(manifest: Path, out: Path, seed: int | None = None) -> dict:
    cmd = [sys.executable, str(SCRIPT), "--manifest", str(manifest), "--out", str(out)]
    if seed is not None:
        cmd += ["--seed", str(seed)]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=REPO)
    assert proc.returncode == 0, proc.stderr
    return json.loads((out / "meta.json").read_text())


def load(out: Path) -> dict[str, list[str]]:
    return {n: json.loads((out / f"{n}.json").read_text()) for n in SPLIT_NAMES}


def synthetic_rows(n_patients: int, imgs_per_patient: int = 3) -> list[tuple[str, ...]]:
    rows = []
    for p in range(n_patients):
        for i in range(imgs_per_patient):
            rows.append((f"img{p:04d}_{i}", f"pat{p:04d}", "synthetic", str(p % 5)))
    return rows


# ------------------------------------------------------------ the core invariant


def test_a_patients_images_never_span_two_splits(tmp_path):
    """The whole point. Every patient has 3 images; all 3 must land together."""
    manifest = tmp_path / "m.csv"
    write_manifest(manifest, synthetic_rows(200, imgs_per_patient=3))
    run_splits(manifest, tmp_path / "out")
    splits = load(tmp_path / "out")

    owner: dict[str, str] = {}
    for name, ids in splits.items():
        for image_id in ids:
            patient = image_id.split("_")[0].replace("img", "pat")
            if patient in owner:
                assert owner[patient] == name, (
                    f"{patient} appears in both {owner[patient]} and {name}"
                )
            owner[patient] = name
    assert len(owner) == 200


def test_the_three_splits_are_disjoint_and_cover_everything(tmp_path):
    manifest = tmp_path / "m.csv"
    rows = synthetic_rows(150)
    write_manifest(manifest, rows)
    meta = run_splits(manifest, tmp_path / "out")
    splits = load(tmp_path / "out")

    all_ids = [i for ids in splits.values() for i in ids]
    assert len(all_ids) == len(set(all_ids)), "an image appears in two splits"
    assert set(all_ids) == {r[0] for r in rows}, "an image was lost or invented"
    assert sum(meta["n_images"].values()) == len(rows)


def test_the_hash_bucketing_is_deterministic(tmp_path):
    """A hash, not a shuffle: the same manifest and seed give the same split."""
    manifest = tmp_path / "m.csv"
    write_manifest(manifest, synthetic_rows(120))
    run_splits(manifest, tmp_path / "a")
    run_splits(manifest, tmp_path / "b")
    assert load(tmp_path / "a") == load(tmp_path / "b")


def test_adding_images_does_not_move_existing_patients(tmp_path):
    """Why a hash was chosen over a shuffle: the split is stable as data grows.

    A shuffle-based split silently reassigns everyone when the corpus grows,
    which re-contaminates any threshold already fitted on the old calibration
    fold.
    """
    first = synthetic_rows(100)
    manifest_a = tmp_path / "a.csv"
    write_manifest(manifest_a, first)
    run_splits(manifest_a, tmp_path / "outa")
    before = load(tmp_path / "outa")

    grown = first + [
        (f"imgnew{p:04d}_0", f"patnew{p:04d}", "synthetic", "0") for p in range(50)
    ]
    manifest_b = tmp_path / "b.csv"
    write_manifest(manifest_b, grown)
    run_splits(manifest_b, tmp_path / "outb")
    after = load(tmp_path / "outb")

    for name in SPLIT_NAMES:
        kept = [i for i in after[name] if not i.startswith("imgnew")]
        assert sorted(kept) == sorted(before[name]), f"{name} moved existing images"


def test_a_different_seed_gives_a_different_split(tmp_path):
    """Guards against a seed that is read but ignored."""
    manifest = tmp_path / "m.csv"
    write_manifest(manifest, synthetic_rows(200))
    run_splits(manifest, tmp_path / "s1", seed=20261027)
    run_splits(manifest, tmp_path / "s2", seed=1)
    assert load(tmp_path / "s1") != load(tmp_path / "s2")


def test_fractions_are_approximately_respected_at_scale(tmp_path):
    manifest = tmp_path / "m.csv"
    write_manifest(manifest, synthetic_rows(2000, imgs_per_patient=1))
    meta = run_splits(manifest, tmp_path / "out")
    n = sum(meta["n_patients"].values())
    assert n == 2000
    # Hash bucketing is unbiased but not exact; 3 points of slack at n=2000.
    for name, want in (("train", 0.60), ("calib", 0.20), ("test", 0.20)):
        got = meta["n_patients"][name] / n
        assert abs(got - want) < 0.03, f"{name} at {got:.3f}, expected ~{want}"


def test_a_manifest_missing_a_column_is_refused(tmp_path):
    manifest = tmp_path / "m.csv"
    with manifest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["image_id", "label"])  # no patient_id, no source
        w.writerow(["img0", "0"])
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(manifest),
            "--out",
            str(tmp_path / "o"),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert proc.returncode != 0
    assert "missing columns" in (proc.stdout + proc.stderr)


# ------------------------------------------- the real frozen splits on disk


def frozen_available() -> bool:
    return all((FROZEN / f"{n}.json").exists() for n in SPLIT_NAMES)


@pytest.mark.skipif(not frozen_available(), reason="data/splits not frozen yet")
def test_the_committed_splits_are_disjoint_and_non_empty():
    splits = load(FROZEN)
    for name in SPLIT_NAMES:
        assert splits[name], f"{name} is empty"
    all_ids = [i for ids in splits.values() for i in ids]
    assert len(all_ids) == len(set(all_ids)), "the committed splits overlap"


@pytest.mark.skipif(not frozen_available(), reason="data/splits not frozen yet")
def test_the_committed_meta_records_the_seed_and_the_manifest_hash():
    meta = json.loads((FROZEN / "meta.json").read_text())
    assert meta["seed"] == 20261027
    assert len(meta["manifest_sha256"]) == 64
    assert meta["fractions"] == {"train": 0.60, "calib": 0.20, "test": 0.20}
    # n_patients == n_images would be a red flag for a corpus WITH patient ids;
    # for APTOS it is expected, because APTOS publishes none. See
    # scripts/build_manifest.py.
    assert set(meta["n_images"]) == set(SPLIT_NAMES)


@pytest.mark.skipif(
    not (REPO / "data" / "manifest.csv").exists(),
    reason="data/manifest.csv is gitignored; only present where it was built",
)
def test_the_committed_splits_still_match_the_manifest_they_came_from():
    """Catches splits regenerated from a different manifest and committed."""
    import hashlib

    meta = json.loads((FROZEN / "meta.json").read_text())
    digest = hashlib.sha256((REPO / "data" / "manifest.csv").read_bytes()).hexdigest()
    assert digest == meta["manifest_sha256"], (
        "data/manifest.csv no longer hashes to the manifest the frozen splits "
        "were built from - the splits are stale or the manifest was rebuilt"
    )
