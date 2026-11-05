"""Fit the gate and conformal thresholds, and write `config/thresholds.yaml`.

    python -m netra.models.fit_thresholds --images data/aptos/images/calib

**The calibration split only.** `docs/rules/ml.md`: "The test split is
touched exactly once, at the end. Thresholds, early stopping, and abstention
levels are set on the calibration split." `dataset.collect` refuses
`split="test"` unless `allow_test=True`, and this module never passes it. There
is no flag here that will let you fit on test.

What gets fitted, and what does not:

* `quality_gate.usable_min_p` / `reject_max_p` - the two cut-points of the
  three-way gate. Fitted from the gate's score distribution on calibration
  images, by quantile. Fitting these needs a QUALITY-LABELLED corpus to be
  meaningful; with no labels available this falls back to quantiles of the
  score distribution, which is a shape-preserving placeholder and NOT a
  calibrated decision boundary. It is marked provisional in the file header.
* `dr.conformal_confidence` - **not fitted.** It is a policy choice (how much
  coverage the programme wants), not something to read off data, and SPEC.md
  fixes it at 0.90. Re-fitting it on calibration data would be choosing the
  guarantee to flatter the model.
* `dr.refer_grades`, `dr.abstain_if_set_spans_actions`, `sites.min_n_for_rate` -
  **not fitted.** These are clinical and reporting policy. `refer_grades` in
  particular is mirrored in Lane A and Lane B, and moving it silently would be
  a cross-lane clinical change.

So this module fits two numbers and refuses to touch the other four. Everything
it writes carries the split, the n, and the date in the file header, so a later
reader can tell what the values are worth.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib

import numpy as np

from netra.models import thresholds
from netra.models.dataset import collect
from netra.models.preprocess import load_image, preprocess
from netra.models.quality import QualityGate, QuickQualFeatures

CALIB_SPLIT = "calib"

#: Quantile placeholders used when no quality labels exist. The bottom decile
#: of scores becomes "reject", the top 40% becomes "usable". These are a SHAPE,
#: not a calibrated boundary - see the module docstring.
PROVISIONAL_REJECT_QUANTILE = 0.10
PROVISIONAL_USABLE_QUANTILE = 0.60

#: Narrowest borderline band worth writing. A band thinner than this means the
#: score distribution is degenerate - every image scored almost the same - and
#: the quantiles are measuring noise, not quality. Writing it would REPLACE
#: sensible placeholders with a worse number that merely looks fitted, so the
#: run refuses instead. Seen for real: a random-init backbone on 20 images
#: produced usable_min_p 0.42 / reject_max_p 0.40.
MIN_BORDERLINE_BAND = 0.10

#: Quantile cut-points only mean something if the calibration set CONTAINS
#: unusable images. If the lowest decile already scores above this, the
#: distribution is one-sided and the quantiles would carve a "reject" band out
#: of the usable population - inventing a boundary where the data has none.
#: Seen for real: a head fitted on synthetic blur scores every real APTOS image
#: at ~1.0, giving usable_min_p 0.95 / reject_max_p 0.85 - a gate that rejects
#: nothing, which is strictly worse than the placeholder it would replace.
ONE_SIDED_SCORE_FLOOR = 0.50


def gate_scores(
    gate: QualityGate, images_dir: pathlib.Path, limit: int | None = None
) -> tuple[np.ndarray, dict]:
    """P(usable) for every calibration image present. Returns (scores, report)."""
    examples, report = collect(CALIB_SPLIT, images_dir, limit=limit)
    scores: list[float] = []
    for example in examples:
        processed, _ = preprocess(load_image(example.path))
        # Go through the gate's own feature + head path, so the fitted
        # cut-points are on exactly the scale the gate will produce later.
        scores.append(gate._p_usable(gate.features(processed)))
    return np.asarray(scores, dtype=float), report


def fit_quality_cutoffs(
    scores: np.ndarray,
    reject_quantile: float = PROVISIONAL_REJECT_QUANTILE,
    usable_quantile: float = PROVISIONAL_USABLE_QUANTILE,
) -> tuple[float, float]:
    """Two cut-points from the calibration score distribution.

    Returns `(usable_min_p, reject_max_p)` with `reject_max_p < usable_min_p`
    guaranteed, because an unordered pair collapses the three-way gate into a
    two-way one and `thresholds.quality_cutoffs` refuses it on read.
    """
    if scores.size == 0:
        raise ValueError("no calibration scores; nothing to fit")
    reject = float(np.quantile(scores, reject_quantile))
    usable = float(np.quantile(scores, usable_quantile))
    # Round to the two decimals the file stores, THEN enforce the ordering, so
    # the written values are the ones that were checked.
    reject, usable = round(reject, 2), round(usable, 2)
    if reject >= usable:
        # Degenerate distribution (e.g. every score identical). Keep a band
        # rather than writing a file that will not load.
        reject = max(0.0, min(usable - 0.05, usable))
        reject = round(reject, 2)
    return usable, reject


def build_config(
    usable_min_p: float,
    reject_max_p: float,
    existing: dict | None = None,
) -> dict:
    """The full config: two fitted values, four carried over unchanged."""
    existing = existing or thresholds.load()
    return {
        "quality_gate": {
            "usable_min_p": usable_min_p,
            "reject_max_p": reject_max_p,
        },
        "dr": {
            # Policy, not fitted. Carried over exactly.
            "conformal_confidence": existing["dr"]["conformal_confidence"],
            "refer_grades": existing["dr"]["refer_grades"],
            "abstain_if_set_spans_actions": existing["dr"][
                "abstain_if_set_spans_actions"
            ],
        },
        # Reporting policy, not fitted.
        "sites": {"min_n_for_rate": existing["sites"]["min_n_for_rate"]},
    }


def header(
    n: int,
    source: str,
    provisional: bool,
    report: dict | None = None,
) -> str:
    today = datetime.date.today().isoformat()
    lines = [
        "Frozen on CALIBRATION split only. Never tune on test.",
        "Changes require a ledger note + commit.",
        "",
        f"quality_gate cut-points fitted {today} on {source}, n={n}.",
    ]
    if provisional:
        lines += [
            "",
            "TODO(review): these two cut-points are PROVISIONAL. They are quantiles",
            "of the gate's score distribution, not a boundary fitted against quality",
            "LABELS - no quality-labelled corpus was available locally (EyeQ's labels",
            "reference EyePACS, which is 89 GiB and out of scope). They preserve the",
            "shape of the three-way band so the pipeline runs end to end; they are not",
            "a calibrated clinical threshold and must not be quoted as one.",
        ]
    lines += [
        "",
        "dr.* and sites.min_n_for_rate are POLICY and are not fitted here:",
        "conformal_confidence is the coverage the programme asks for (SPEC.md: 0.90),",
        "refer_grades is clinical and is mirrored in Lane A and Lane B, and",
        "min_n_for_rate is a reporting rule.",
    ]
    if report:
        lines += ["", f"calibration retained: {json.dumps(report)}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--images",
        type=pathlib.Path,
        default=pathlib.Path("data/aptos/images/calib"),
        help="directory of CALIBRATION images",
    )
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument(
        "--svm",
        type=pathlib.Path,
        default=None,
        help="a QuickQual SVM head; without one the gate has no scores to fit on",
    )
    ap.add_argument(
        "--random-init",
        action="store_true",
        help="random backbone weights, so the run never touches the network",
    )
    ap.add_argument("--dry-run", action="store_true", help="print, do not write")
    args = ap.parse_args(argv)

    gate = QualityGate(
        features=QuickQualFeatures(pretrained=not args.random_init),
        svm_path=args.svm,
    )
    if not gate.available:
        # No head means no scores, and inventing cut-points without them would
        # be fabricating a clinical threshold. Say so and change nothing.
        print(
            "the quality gate has no head loaded, so there are no scores to fit "
            f"cut-points on ({gate.load_error or 'no SVM supplied'}).\n"
            "config/thresholds.yaml is LEFT UNCHANGED. Supply --svm, or fit a head "
            "on a quality-labelled corpus first."
        )
        return 2

    scores, report = gate_scores(gate, args.images, args.limit)
    print(json.dumps({"calibration": report}, indent=2))
    if scores.size == 0:
        print(
            f"no calibration images under {args.images}; nothing fitted and "
            "config/thresholds.yaml is LEFT UNCHANGED."
        )
        return 2

    usable_min_p, reject_max_p = fit_quality_cutoffs(scores)
    band = round(usable_min_p - reject_max_p, 4)
    config = build_config(usable_min_p, reject_max_p)

    print(
        json.dumps(
            {
                "n_scores": int(scores.size),
                "score_quantiles": {
                    q: round(float(np.quantile(scores, q)), 4)
                    for q in (0.0, 0.1, 0.5, 0.6, 0.9, 1.0)
                },
                "fitted": config["quality_gate"],
                "carried_over": config["dr"] | config["sites"],
            },
            indent=2,
        )
    )

    low_decile = float(np.quantile(scores, 0.10))
    if low_decile > ONE_SIDED_SCORE_FLOOR:
        print(
            f"\nREFUSING TO WRITE: the calibration scores are one-sided - the "
            f"10th percentile is {low_decile:.3f}, above {ONE_SIDED_SCORE_FLOOR}. "
            "Essentially every calibration image reads as usable, so quantiles "
            "would carve a reject band out of the usable population and invent a "
            "boundary the data does not contain.\n"
            "Fitting these two cut-points needs a calibration set holding BOTH "
            "usable and unusable images, judged by a human - i.e. a "
            "quality-labelled corpus. EyeQ would be it, and its labels reference "
            "EyePACS (~89 GiB), which is out of scope here.\n"
            "config/thresholds.yaml is LEFT UNCHANGED."
        )
        return 3

    if band < MIN_BORDERLINE_BAND:
        # Refuse rather than regress the file. A 0.02-wide borderline band is
        # not a calibrated gate, it is a flat score distribution.
        print(
            f"\nREFUSING TO WRITE: the fitted borderline band is {band:.2f} wide "
            f"(usable_min_p {usable_min_p}, reject_max_p {reject_max_p}), under the "
            f"{MIN_BORDERLINE_BAND} minimum. The gate's scores are too tightly "
            "clustered for these quantiles to mean anything - usually a backbone "
            "with random weights, too few images, or a head that separates "
            "nothing.\n"
            "config/thresholds.yaml is LEFT UNCHANGED, which keeps the existing "
            "placeholders rather than replacing them with a worse number that "
            "merely looks fitted."
        )
        return 3

    if args.dry_run:
        print("\n--dry-run: nothing written")
        print(
            thresholds.dump(
                config, header(int(scores.size), "aptos calib", True, report)
            )
        )
        return 0

    path = thresholds.write(
        config,
        args.out,
        header(int(scores.size), "aptos calib", provisional=True, report=report),
    )
    print(f"\nwrote {path}")
    print("the TEST split was not read.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
