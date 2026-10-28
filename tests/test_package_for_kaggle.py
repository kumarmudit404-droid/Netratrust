"""The Kaggle payload: `scripts/package_for_kaggle.py`.

The failure this guards against is specific and expensive. A zip that is
missing one module imports fine on the build box - where the real repo is on
`sys.path` - and fails on Kaggle forty minutes into a nine-hour session, after
the GPU time is already spent. So the payload is unpacked into a clean
directory here and imported in a SUBPROCESS with the repo deliberately off
`sys.path`, which is the only arrangement that can tell the two apart.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "package_for_kaggle.py"


def load_packager():
    spec = importlib.util.spec_from_file_location("_package_for_kaggle", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PKG = load_packager()


# ---------------------------------------------------------- what goes in


def test_the_payload_carries_lane_c_and_the_frozen_splits():
    paths, missing = PKG.collect_paths(REPO)
    shipped = {str(p).replace("\\", "/") for p in paths}
    assert missing == []

    for required in (
        "netra/__init__.py",
        "netra/models/__init__.py",
        "netra/models/train.py",
        "netra/models/dataset.py",
        "netra/models/eyeq.py",
        "netra/models/splits.py",
        "netra/eval/metrics.py",
        "data/splits/train.json",
        "data/splits/calib.json",
        "data/splits/test.json",
        "data/splits/meta.json",
        "config/thresholds.yaml",
        "requirements.txt",
    ):
        assert required in shipped, f"{required} is not in the payload"


def test_no_other_lane_and_no_signing_key_ever_ships():
    """A dataset is uploadable by anyone who can see it. `keys/` cannot travel."""
    paths, _ = PKG.collect_paths(REPO)
    shipped = {str(p).replace("\\", "/") for p in paths}
    for forbidden in ("keys/", "netra/api/", "netra/db/", "netra/ledger/", "netra/ui/"):
        assert not [p for p in shipped if p.startswith(forbidden)], forbidden


def test_compiled_and_binary_junk_is_excluded():
    paths, _ = PKG.collect_paths(REPO)
    shipped = [str(p).replace("\\", "/") for p in paths]
    assert not [p for p in shipped if "__pycache__" in p]
    assert not [p for p in shipped if p.endswith((".pyc", ".pkl", ".pt", ".db"))]


def test_the_repo_as_it_stands_passes_every_check():
    assert PKG.main(["--check", "--quiet"]) == 0


# --------------------------------------------------- the import verification


def test_netra_imports_finds_every_spelling():
    source = (
        "import netra.models.dr\n"
        "from netra.eval import metrics\n"
        "from netra.models.preprocess import preprocess, IMAGE_SIZE\n"
        "import os\n"
        "from collections import Counter\n"
    )
    found = PKG.netra_imports(source)
    assert "netra.models.dr" in found
    assert "netra.eval" in found
    assert "netra.eval.metrics" in found
    assert "netra.models.preprocess" in found
    assert not [f for f in found if f.startswith(("os", "collections"))]


def test_a_payload_that_imports_what_it_does_not_carry_is_refused(tmp_path):
    (tmp_path / "netra" / "models").mkdir(parents=True)
    (tmp_path / "netra" / "__init__.py").write_text("")
    (tmp_path / "netra" / "models" / "__init__.py").write_text("")
    (tmp_path / "netra" / "models" / "thing.py").write_text(
        "from netra.ledger.chain import append\n"
    )
    paths = [
        Path("netra/__init__.py"),
        Path("netra/models/__init__.py"),
        Path("netra/models/thing.py"),
    ]
    problems, _ = PKG.verify_imports_resolve(tmp_path, paths)
    assert len(problems) == 1
    assert "netra.ledger.chain" in problems[0]


def test_an_import_of_a_name_inside_a_shipped_module_resolves(tmp_path):
    """`from netra.eval.metrics import brier` is a name, not a module."""
    (tmp_path / "netra" / "eval").mkdir(parents=True)
    (tmp_path / "netra" / "__init__.py").write_text("")
    (tmp_path / "netra" / "eval" / "__init__.py").write_text("")
    (tmp_path / "netra" / "eval" / "metrics.py").write_text("def brier(): ...\n")
    (tmp_path / "netra" / "eval" / "user.py").write_text(
        "from netra.eval.metrics import brier\n"
    )
    paths = [
        Path("netra/__init__.py"),
        Path("netra/eval/__init__.py"),
        Path("netra/eval/metrics.py"),
        Path("netra/eval/user.py"),
    ]
    problems, _ = PKG.verify_imports_resolve(tmp_path, paths)
    assert problems == []


def test_a_missing_frozen_split_is_refused(tmp_path):
    paths = [Path("data/splits/train.json")]
    (tmp_path / "data" / "splits").mkdir(parents=True)
    (tmp_path / "data" / "splits" / "train.json").write_text("[]")
    problems = PKG.verify_contents(tmp_path, paths)
    assert any("calib.json" in p for p in problems)
    assert any("meta.json" in p for p in problems)


def test_an_empty_split_file_is_refused(tmp_path):
    (tmp_path / "data" / "splits").mkdir(parents=True)
    for name in ("train", "calib", "test", "meta"):
        (tmp_path / "data" / "splits" / f"{name}.json").write_text("")
    paths = [Path(f"data/splits/{n}.json") for n in ("train", "calib", "test", "meta")]
    problems = PKG.verify_contents(tmp_path, paths)
    assert any("train.json is empty" in p for p in problems)


# -------------------------------------------------------------- the zip


def test_the_zip_is_byte_for_byte_reproducible(tmp_path):
    """Two builds of the same tree must hash the same, or provenance is a guess."""
    paths, _ = PKG.collect_paths(REPO)
    first = PKG.build_zip(REPO, paths, tmp_path / "a.zip")
    second = PKG.build_zip(REPO, paths, tmp_path / "b.zip")
    assert first["sha256"] == second["sha256"]
    assert first["n_files"] == len(paths)


def test_the_zip_unpacks_to_the_paths_the_notebook_expects(tmp_path):
    paths, _ = PKG.collect_paths(REPO)
    PKG.build_zip(REPO, paths, tmp_path / "payload.zip")
    with zipfile.ZipFile(tmp_path / "payload.zip") as zf:
        names = zf.namelist()
        assert all("\\" not in n for n in names), "zip entries must use forward slashes"
        zf.extractall(tmp_path / "unpacked")

    root = tmp_path / "unpacked"
    assert (root / "netra" / "models" / "train.py").is_file()
    assert (root / "data" / "splits" / "calib.json").is_file()
    assert (root / "config" / "thresholds.yaml").is_file()


@pytest.mark.parametrize(
    "module",
    [
        "netra.models.splits",
        "netra.models.eyeq",
        "netra.models.dataset",
        "netra.models.preprocess",
        "netra.eval.metrics",
    ],
)
def test_each_module_imports_from_the_unpacked_payload_alone(tmp_path, module):
    """Imported in a subprocess with the repo OFF sys.path.

    Without that isolation this test passes even for a payload missing the
    module, because the real repo would satisfy the import.
    """
    paths, _ = PKG.collect_paths(REPO)
    PKG.build_zip(REPO, paths, tmp_path / "payload.zip")
    root = tmp_path / "unpacked"
    with zipfile.ZipFile(tmp_path / "payload.zip") as zf:
        zf.extractall(root)

    code = (
        "import sys, json, pathlib\n"
        "root = pathlib.Path(sys.argv[1])\n"
        "repo = pathlib.Path(sys.argv[2]).resolve()\n"
        "sys.path = [p for p in sys.path if pathlib.Path(p or '.').resolve() != repo]\n"
        "sys.path.insert(0, str(root))\n"
        "import importlib\n"
        "m = importlib.import_module(sys.argv[3])\n"
        "print(json.dumps({'file': m.__file__}))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, str(root), str(REPO), module],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    resolved = Path(json.loads(proc.stdout.strip().splitlines()[-1])["file"]).resolve()
    assert str(root.resolve()) in str(resolved), (
        f"{module} imported from {resolved}, not from the unpacked payload"
    )


def test_the_frozen_splits_in_the_payload_are_the_committed_ones(tmp_path):
    """A stale split inside the zip is the exact drift ml.md is about."""
    paths, _ = PKG.collect_paths(REPO)
    PKG.build_zip(REPO, paths, tmp_path / "payload.zip")
    with zipfile.ZipFile(tmp_path / "payload.zip") as zf:
        for name in ("train", "calib", "test"):
            packed = json.loads(zf.read(f"data/splits/{name}.json"))
            on_disk = json.loads(
                (REPO / "data" / "splits" / f"{name}.json").read_text()
            )
            assert packed == on_disk
