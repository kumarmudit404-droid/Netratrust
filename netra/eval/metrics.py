"""Evaluation metrics for NetraTrust.

Hand-written on purpose. This module is the single source of every number the
team reports. Generated code passes unit tests while computing metrics on the
wrong split; that failure mode has no automated guard, so this file is written
and reviewed by a human and everything else imports from it.

Verified against scikit-learn 1.9.1 / numpy 2.5.4 conventions on 2026-10-27.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import logit
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, cohen_kappa_score, log_loss

# ---------------------------------------------------------------- calibration


def brier(y_true: np.ndarray, y_proba: np.ndarray, labels=None) -> float:
    """Brier score. NOTE the keyword is `y_proba`, not `y_prob`.

    scikit-learn 1.9.1 raises TypeError on the old `y_prob=` keyword. Coding
    assistants trained on older versions emit it confidently.
    """
    return float(brier_score_loss(y_true, y_proba, labels=labels))


def nll(y_true: np.ndarray, y_proba: np.ndarray, labels=None) -> float:
    """Negative log-likelihood. Strictly proper, like Brier. Report both."""
    return float(log_loss(y_true, y_proba, labels=labels))


def calibration_slope_intercept(
    y_true: np.ndarray, p: np.ndarray, eps: float = 1e-6
) -> tuple[float, float]:
    """Calibration slope and intercept - the metrics clinical reviewers know.

    Present in no library we checked. Slope 1.0 and intercept 0.0 is perfect;
    slope < 1 means over-confident (the usual direction for a neural network).

    Uses C=np.inf rather than penalty=None, which is deprecated and removed in
    scikit-learn 1.10.
    """
    p = np.clip(np.asarray(p, dtype=float), eps, 1 - eps)
    lp = logit(p).reshape(-1, 1)

    slope_model = LogisticRegression(C=np.inf, solver="lbfgs").fit(lp, y_true)
    slope = float(slope_model.coef_[0][0])

    # Intercept is fitted with the linear predictor as a fixed offset.
    inter_model = LogisticRegression(C=np.inf, solver="lbfgs").fit(
        np.zeros_like(lp), y_true
    )
    intercept = float(inter_model.intercept_[0] - np.mean(lp))
    return slope, intercept


def ece(
    y_true: np.ndarray,
    p: np.ndarray,
    n_bins: int = 15,
    strategy: str = "uniform",
) -> tuple[float, str]:
    """Expected calibration error. SECONDARY metric only.

    Returns (value, description) because ECE must never be reported without its
    binning scheme. Measured swing on identical predictions: 0.06695 at 15
    equal-width bins vs 0.07205 at 50 - a 7.6% change from the bin count alone.
    Lead with Brier and NLL; use this as a diagnostic.
    """
    p = np.asarray(p, dtype=float)
    y = np.asarray(y_true)

    if strategy == "uniform":
        edges = np.linspace(0.0, 1.0, n_bins + 1)
    elif strategy == "quantile":
        edges = np.quantile(p, np.linspace(0.0, 1.0, n_bins + 1))
        edges[0], edges[-1] = 0.0, 1.0
    else:
        raise ValueError("strategy must be 'uniform' or 'quantile'")

    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    total = 0.0
    for b in range(n_bins):
        m = idx == b
        if not m.any():
            continue
        total += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(total), f"{n_bins} {strategy} bins"


def fit_temperature(logits: np.ndarray, y_true: np.ndarray) -> float:
    """Temperature scaling. One parameter, so a scalar minimiser beats LBFGS.

    Expected signature of a correct fit: ECE falls substantially while Brier
    barely moves. If Brier moves a lot, something else is wrong.
    """

    def obj(t: float) -> float:
        if t <= 0:
            return 1e9
        z = logits / t
        z = z - z.max(axis=1, keepdims=True)
        proba = np.exp(z) / np.exp(z).sum(axis=1, keepdims=True)
        return log_loss(y_true, proba, labels=list(range(logits.shape[1])))

    res = minimize_scalar(obj, bounds=(0.05, 10.0), method="bounded")
    return float(res.x)


# ------------------------------------------------------- selective prediction


def risk_coverage(
    correct: np.ndarray, confidence: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Risk-coverage curve.

    Returns (coverage, risk). Plot with a HORIZONTAL reference line at the
    no-abstention risk - risk_coverage's reference is NOT the y=x diagonal.
    Only calibration curves take the diagonal.
    """
    order = np.argsort(-np.asarray(confidence, dtype=float))
    c = np.asarray(correct, dtype=float)[order]
    n = len(c)
    k = np.arange(1, n + 1)
    coverage = k / n
    risk = np.cumsum(1.0 - c) / k
    return coverage, risk


def augrc(correct: np.ndarray, confidence: np.ndarray) -> float:
    """Area under the generalised risk-coverage curve.

    Report this INSTEAD of AURC. Traub et al., NeurIPS 2024 show AURC violates
    monotonicity: it can improve while both accuracy and failure-detection
    AUROC get worse. Saying "we moved off AURC because of a 2024 result" is a
    cheap and genuine credibility gain.
    """
    coverage, risk = risk_coverage(correct, confidence)
    generalised = risk * coverage
    return float(np.trapezoid(generalised, coverage) / coverage[-1])


def coverage_at_risk(
    correct: np.ndarray, confidence: np.ndarray, target_risk: float
) -> float:
    """Largest coverage whose selective risk stays at or below target_risk."""
    coverage, risk = risk_coverage(correct, confidence)
    ok = risk <= target_risk
    return float(coverage[ok].max()) if ok.any() else 0.0


# ------------------------------------------------------------ DR agreement


def quadratic_weighted_kappa(
    y_true: np.ndarray, y_pred: np.ndarray, n_classes: int = 5
) -> float:
    """Quadratic weighted kappa - the headline DR grading metric.

    Added for the DR backbone (SPEC.md section 2 quotes an expected 0.88-0.92 on
    a local APTOS split). It lives here because every reported number comes from
    this module; computing it inline in a notebook is what rules.md section 7
    forbids.

    Quadratic weights are what make this the right metric for DR: the grades are
    ORDERED, so confusing 0 with 4 must cost more than confusing 0 with 1.

    `labels` is passed explicitly for an explicit 5x5 matrix, NOT because it
    changes the number. It does not: the weights are (i-j)^2/(k-1)^2, so adding
    empty classes scales every weight by the same constant and that constant
    cancels in 1 - sum(w*O)/sum(w*E). Measured both ways on a fold missing
    grades 3 and 4: 0.8571428571428572 either way. A fold containing a SINGLE
    grade returns nan with or without it, so callers must handle that rather
    than rely on this argument to prevent it.

    SPEC.md: anything above 0.95 on a local split means a leaked split.
    """
    return float(
        cohen_kappa_score(
            y_true, y_pred, weights="quadratic", labels=list(range(n_classes))
        )
    )


# ------------------------------------------------- per-site reporting helpers


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Use this everywhere a proportion is reported.

    Never print a bare percentage for n < 30; print the count and this interval.
    """
    if n == 0:
        return (0.0, 1.0)
    phat = k / n
    d = 1 + z**2 / n
    centre = (phat + z**2 / (2 * n)) / d
    half = z * np.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def abstention_report(
    gate_admitted: np.ndarray,
    correct_on_admitted: np.ndarray,
) -> dict:
    """The headline table. Coverage cost ALWAYS travels with the accuracy gain.

    A result that shows the specificity gain without the abstention rate beside
    it is not reportable. This function makes omitting it awkward.
    """
    n = len(gate_admitted)
    admitted = int(gate_admitted.sum())
    abstained = n - admitted
    lo, hi = wilson_interval(int(correct_on_admitted.sum()), max(admitted, 1))
    return {
        "n_total": n,
        "n_admitted": admitted,
        "n_abstained": abstained,
        "coverage": admitted / n if n else 0.0,
        "abstention_rate": abstained / n if n else 0.0,
        "accuracy_on_admitted": (
            float(correct_on_admitted.mean()) if admitted else float("nan")
        ),
        "accuracy_ci_on_admitted": (lo, hi),
    }
