"""`notebooks/train_kaggle.ipynb` holds invariants no other test covers.

The notebook is the only place either real artifact is produced, and it runs
unattended on somebody else's machine for several hours. The things that make
it safe - it never collects the test split, it stops on a leaked-split QWK, it
reads metrics from `netra/eval/metrics.py` - live in cell source, where an
edit can quietly remove them. So they are asserted here.

These tests read the notebook. They do not execute it; the T4 run is the
execution.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NOTEBOOK = REPO / "notebooks" / "train_kaggle.ipynb"


@pytest.fixture(scope="module")
def nb() -> dict:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def sources(nb: dict, kind: str) -> list[str]:
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == kind]


def code(nb: dict) -> str:
    return "\n".join(sources(nb, "code"))


# ------------------------------------------------------------ it is a notebook


def test_every_code_cell_parses(nb):
    """A syntax error here is only discovered on Kaggle otherwise."""
    for i, source in enumerate(sources(nb, "code")):
        ast.parse(source, filename=f"cell {i}")


def test_it_declares_a_gpu_accelerator_and_a_python_kernel(nb):
    assert nb["metadata"].get("accelerator") == "GPU"
    assert nb["metadata"]["kernelspec"]["name"] == "python3"


def test_no_cell_ships_stored_output(nb):
    """Committed outputs make the diff unreadable and can leak a path."""
    for cell in nb["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            assert cell["execution_count"] is None


# ------------------------------------------------------- the first cell is the run book


def test_the_first_cell_is_the_kaggle_run_book(nb):
    first = sources(nb, "markdown")[0]
    assert nb["cells"][0]["cell_type"] == "markdown"
    for required in (
        "Add Input",
        "netratrust-code",
        "APTOS",
        "EyePACS",
        "GPU T4",
        "Internet",
        "Run All",
        "/kaggle/working/artifacts/",
        "convnext_tiny_aptos.pt",
        "quality_head_eyeq.pkl",
    ):
        assert required in first, f"the run book does not mention {required!r}"


def test_the_run_book_names_both_artifacts_and_where_they_land(nb):
    first = sources(nb, "markdown")[0]
    assert "Output" in first, "it does not say how to get the artifacts off Kaggle"
    assert "package_for_kaggle.py" in first, "it does not say how to build the payload"


def test_the_run_book_states_every_stop_condition(nb):
    # Collapsed, because the run book is wrapped prose and a stop condition
    # that straddles a line break is still documented.
    first = " ".join(sources(nb, "markdown")[0].split())
    for condition in ("0.95", "SplitDrift", "leaked split", "retained fraction"):
        assert condition in first, f"stop condition {condition!r} is not documented"


# ------------------------------------------------- the clinical invariants


def test_the_test_split_is_never_collected(nb):
    """`docs/rules/ml.md`: touched exactly once, at the end - not here."""
    body = code(nb)
    assert "allow_test" not in body, "a cell asks collect() for the test split"
    assert 'collect("test"' not in body
    assert "collect('test'" not in body
    assert 'read_split("test"' not in body


def test_model_selection_cells_only_ever_name_the_calibration_fold(nb):
    body = code(nb)
    assert "calib_examples" in body
    assert "test_examples" not in body, "the notebook built a test fold"


def test_the_leak_alarm_stops_the_run(nb):
    body = code(nb)
    assert "LEAK_ALARM_QWK = 0.95" in body
    assert (
        "best['qwk'] > LEAK_ALARM_QWK" in body or 'best["qwk"] > LEAK_ALARM_QWK' in body
    )
    assert "LEAKED SPLIT" in body, "the message does not say what it means"


def test_the_retained_fraction_gate_is_present_and_is_a_stop(nb):
    body = code(nb)
    assert "MIN_RETAINED = 0.95" in body
    assert 'report["retained_fraction"] < MIN_RETAINED' in body


def test_stops_use_the_named_exception_so_run_all_halts(nb):
    """A warning that prints and continues is not a stop."""
    body = code(nb)
    assert "class Stop(RuntimeError)" in body
    assert body.count("raise Stop(") >= 8
    assert "raise SystemExit(" not in body


def test_it_never_regenerates_a_split_or_calls_train_test_split(nb):
    body = code(nb)
    assert "train_test_split" not in body
    assert "check_preserved" in body, "growth is not checked against the old folds"


def test_metrics_come_from_the_eval_module_not_from_the_cells(nb):
    """`docs/rules/ml.md` forbids computing a metric inline in a notebook."""
    body = code(nb)
    for inline in (
        "cohen_kappa_score",
        "roc_auc_score",
        "accuracy_score",
        "brier_score_loss",
        "log_loss",
    ):
        assert inline not in body, (
            f"{inline} is computed inline; use netra/eval/metrics"
        )


def test_preprocessing_stays_crop_and_resize(nb):
    """A controlled ablation put CLAHE and Ben Graham BELOW plain crop+resize."""
    body = code(nb)
    for banned in ("createCLAHE", "CLAHE", "ben_graham", "addWeighted"):
        assert banned not in body, f"{banned} is not the supported preprocessing path"


# ------------------------------------- real and synthetic stay apart


def test_the_two_heads_never_share_a_filename(nb):
    body = code(nb)
    assert "quality_head_eyeq.pkl" in body
    assert 'QUALITY_HEAD = ARTIFACTS / "quality_head_eyeq.pkl"' in body


def test_the_summary_separates_real_from_synthetic(nb):
    body = code(nb)
    assert "REAL - measured on real data in this run" in body
    assert "SYNTHETIC - separate table, never pooled with the above" in body
    assert "NOT MEASURED - do not quote" in body


def test_the_published_quickqual_numbers_are_labelled_as_the_paper_s(nb):
    """Never place a local split score beside a public number as if equal."""
    body = code(nb)
    assert "0.886" in body
    assert "paper" in body.lower()


# ------------------------------------------------ the old notebook is a pointer


def test_train_dr_notebook_points_at_this_one():
    old = json.loads(
        (REPO / "notebooks" / "train_dr.ipynb").read_text(encoding="utf-8")
    )
    text = "".join("".join(c["source"]) for c in old["cells"])
    assert "train_kaggle.ipynb" in text
    assert not [c for c in old["cells"] if c["cell_type"] == "code"], (
        "the superseded notebook still has runnable cells"
    )
