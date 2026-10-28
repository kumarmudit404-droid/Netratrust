"""`config/thresholds.yaml`: reading, writing, and cross-lane compatibility.

The important test here is `test_lane_a_can_read_what_lane_c_writes`. Lane A
parses this file with a deliberately minimal stdlib parser that RAISES on
unrecognised syntax, so a format drift in Lane C's writer would 500 a route
handler rather than fail anything in Lane C. That is exactly the kind of
cross-lane break a single-lane test suite misses.

`fit_thresholds` is also tested for what it REFUSES to write, because the
failure mode there is not a crash - it is a plausible-looking number that is
worse than the placeholder it replaced.
"""

from __future__ import annotations

import numpy as np
import pytest

from netra.models import thresholds
from netra.models.fit_thresholds import (
    MIN_BORDERLINE_BAND,
    ONE_SIDED_SCORE_FLOOR,
    build_config,
    fit_quality_cutoffs,
    header,
)
from netra.models.fit_thresholds import main as fit_main

SHIPPED = thresholds.DEFAULT_PATH


# -------------------------------------------------------------------- reading


def test_the_shipped_file_parses_and_has_every_required_key():
    cfg = thresholds.load()
    for section, keys in thresholds.REQUIRED_SCHEMA.items():
        assert section in cfg, f"missing section {section}"
        for key in keys:
            assert key in cfg[section], f"missing {section}.{key}"


def test_the_typed_accessors_agree_with_the_file():
    assert thresholds.refer_grades() == (2, 3, 4)
    assert thresholds.conformal_confidence() == pytest.approx(0.90)
    usable, reject = thresholds.quality_cutoffs()
    assert (usable, reject) == (pytest.approx(0.70), pytest.approx(0.30))


def test_quality_cutoffs_refuses_an_unordered_pair(tmp_path):
    """An unordered pair makes the borderline band empty and silently turns a
    three-way gate into a two-way one."""
    path = tmp_path / "t.yaml"
    path.write_text(
        "quality_gate:\n  usable_min_p: 0.30\n  reject_max_p: 0.70\n",
        encoding="utf-8",
    )
    with pytest.raises(thresholds.ThresholdError, match="no borderline band"):
        thresholds.quality_cutoffs(thresholds.load(path))


def test_quality_cutoffs_refuses_a_probability_outside_zero_one(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_text(
        "quality_gate:\n  usable_min_p: 1.40\n  reject_max_p: 0.30\n", encoding="utf-8"
    )
    with pytest.raises(thresholds.ThresholdError, match=r"must be in \[0, 1\]"):
        thresholds.quality_cutoffs(thresholds.load(path))


def test_conformal_confidence_must_be_a_probability(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_text("dr:\n  conformal_confidence: 1.0\n", encoding="utf-8")
    with pytest.raises(thresholds.ThresholdError, match=r"must be in \(0, 1\)"):
        thresholds.conformal_confidence(thresholds.load(path))


def test_refer_grades_must_be_integers(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_text("dr:\n  refer_grades: [2.5, 3]\n", encoding="utf-8")
    with pytest.raises(thresholds.ThresholdError, match="list of integers"):
        thresholds.refer_grades(thresholds.load(path))


def test_the_reader_refuses_syntax_outside_the_supported_subset(tmp_path):
    """Matching Lane A's parser: raise rather than guess."""
    nested = tmp_path / "nested.yaml"
    nested.write_text("dr:\n  inner:\n    deep: 1\n", encoding="utf-8")
    with pytest.raises(thresholds.ThresholdError, match="nested mappings"):
        thresholds.load(nested)

    deep = tmp_path / "deep.yaml"
    deep.write_text("dr:\n    conformal_confidence: 0.9\n", encoding="utf-8")
    with pytest.raises(thresholds.ThresholdError, match="unexpected indent"):
        thresholds.load(deep)


def test_comments_and_blank_lines_are_ignored(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_text(
        "# a comment\n\ndr:\n  conformal_confidence: 0.9  # trailing\n",
        encoding="utf-8",
    )
    assert thresholds.load(path)["dr"]["conformal_confidence"] == pytest.approx(0.9)


# -------------------------------------------------------------------- writing


def sample_config() -> dict:
    return {
        "quality_gate": {"usable_min_p": 0.72, "reject_max_p": 0.28},
        "dr": {
            "conformal_confidence": 0.90,
            "refer_grades": [2, 3, 4],
            "abstain_if_set_spans_actions": True,
        },
        "sites": {"min_n_for_rate": 30},
    }


def test_write_then_read_round_trips(tmp_path):
    path = tmp_path / "out.yaml"
    thresholds.write(sample_config(), path, header="fitted in a test")
    back = thresholds.load(path)
    assert back["quality_gate"]["usable_min_p"] == pytest.approx(0.72)
    assert back["dr"]["refer_grades"] == [2, 3, 4]
    assert back["dr"]["abstain_if_set_spans_actions"] is True
    assert back["sites"]["min_n_for_rate"] == 30


def test_booleans_and_flow_lists_render_in_the_supported_form():
    text = thresholds.dump(sample_config())
    assert "abstain_if_set_spans_actions: true" in text
    assert "refer_grades: [2, 3, 4]" in text
    # No block lists; Lane A's parser cannot read them.
    assert "\n  - " not in text


def test_dump_refuses_to_drop_a_key_another_lane_reads():
    broken = sample_config()
    del broken["dr"]["refer_grades"]
    with pytest.raises(thresholds.ThresholdError, match="missing dr.refer_grades"):
        thresholds.dump(broken)

    no_section = sample_config()
    del no_section["sites"]
    with pytest.raises(thresholds.ThresholdError, match="missing section 'sites'"):
        thresholds.dump(no_section)


def test_the_header_is_rendered_as_comments(tmp_path):
    path = tmp_path / "out.yaml"
    thresholds.write(sample_config(), path, header="line one\nline two")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# line one\n# line two\n")


# ------------------------------------------------ the cross-lane contract


def test_lane_a_can_read_what_lane_c_writes(tmp_path):
    """The break this file exists to prevent: Lane C writes, Lane A 500s."""
    from netra.api.config import load as lane_a_load

    path = tmp_path / "thresholds.yaml"
    thresholds.write(sample_config(), path, header=header(42, "aptos calib", True))

    lane_a = lane_a_load(path)
    assert lane_a["quality_gate"]["usable_min_p"] == pytest.approx(0.72)
    assert lane_a["dr"]["refer_grades"] == [2, 3, 4]
    assert lane_a["dr"]["abstain_if_set_spans_actions"] is True
    assert lane_a["sites"]["min_n_for_rate"] == 30


def test_lane_a_and_lane_c_parse_the_shipped_file_identically():
    from netra.api.config import load as lane_a_load

    assert lane_a_load(SHIPPED) == thresholds.load(SHIPPED)


def test_lane_a_reads_the_same_refer_grades():
    from netra.api.config import refer_grades as lane_a_refer

    assert lane_a_refer() == thresholds.refer_grades()


# ------------------------------------------------------- fitting cut-points


def test_fit_quality_cutoffs_returns_an_ordered_pair():
    scores = np.linspace(0.0, 1.0, 101)
    usable, reject = fit_quality_cutoffs(scores)
    assert reject < usable
    assert 0.0 <= reject <= 1.0 and 0.0 <= usable <= 1.0


def test_fit_quality_cutoffs_keeps_a_band_on_a_flat_distribution():
    """Every score identical: the quantiles collapse, but the pair must still
    be ordered or the written file will not load."""
    usable, reject = fit_quality_cutoffs(np.full(50, 0.5))
    assert reject < usable


def test_fit_quality_cutoffs_refuses_an_empty_score_array():
    with pytest.raises(ValueError, match="nothing to fit"):
        fit_quality_cutoffs(np.array([]))


def test_build_config_carries_policy_over_untouched():
    """Only two numbers are fitted. The other four are clinical or reporting
    policy and moving them silently would be a cross-lane change."""
    existing = thresholds.load()
    cfg = build_config(0.8, 0.2, existing)
    assert cfg["quality_gate"] == {"usable_min_p": 0.8, "reject_max_p": 0.2}
    assert cfg["dr"]["refer_grades"] == existing["dr"]["refer_grades"]
    assert cfg["dr"]["conformal_confidence"] == existing["dr"]["conformal_confidence"]
    assert cfg["sites"]["min_n_for_rate"] == existing["sites"]["min_n_for_rate"]


def test_the_header_marks_provisional_values_as_such():
    text = header(30, "aptos calib", provisional=True)
    assert "TODO(review)" in text
    assert "PROVISIONAL" in text
    assert "CALIBRATION split only" in text
    assert "TODO(review)" not in header(30, "aptos calib", provisional=False)


# --------------------------------------- what the fitter REFUSES to write


def test_fitting_without_a_head_changes_nothing(tmp_path, monkeypatch):
    """No head means no scores. Inventing cut-points without them would be
    fabricating a clinical threshold."""
    monkeypatch.delenv("NETRA_QUICKQUAL_SVM", raising=False)
    before = SHIPPED.read_bytes()
    code = fit_main(
        [
            "--images",
            str(tmp_path / "none"),
            "--random-init",
            "--out",
            str(tmp_path / "written.yaml"),
        ]
    )
    assert code == 2
    assert not (tmp_path / "written.yaml").exists()
    assert SHIPPED.read_bytes() == before, "the shipped file must be untouched"


def test_the_guards_are_set_where_the_real_failures_were_seen():
    """Both constants exist because a run produced a bad number, not in theory:
    a random-init backbone gave a 0.02-wide band, and a head fitted on
    synthetic blur scored every real image ~1.0 (10th percentile 0.852)."""
    assert MIN_BORDERLINE_BAND == pytest.approx(0.10)
    assert ONE_SIDED_SCORE_FLOOR == pytest.approx(0.50)
    # 0.95 / 0.85 is the pair the one-sided guard rejected. Note the rounding:
    # 0.95 - 0.85 is 0.09999999999999998 in binary floating point, so the
    # production guard rounds the band to 4dp BEFORE comparing. Without that
    # round, this pair would be rejected by the band guard for a reason that
    # has nothing to do with quality.
    band = round(0.95 - 0.85, 4)
    assert band >= MIN_BORDERLINE_BAND, (
        "that pair passes the band guard, which is exactly why the one-sided "
        "guard is also needed"
    )
    assert 0.852 > ONE_SIDED_SCORE_FLOOR
