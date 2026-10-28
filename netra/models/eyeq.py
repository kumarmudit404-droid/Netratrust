"""EyeQ: the REAL quality labels, and how they reach the mounted EyePACS images.

SPEC.md section 1 puts QuickQual on EyeQ. EyeQ (Fu et al., MICCAI 2019,
`github.com/HzFu/EyeQ`) publishes two CSVs and no pixels: the images are
EyePACS's, which is ~89 GiB and is why T-08 was blocked on the build box. On
Kaggle EyePACS is already MOUNTED, so the only missing piece there is the
28,792 rows of human quality judgement, which are two small files over HTTP.

This module exists to replace the synthetic stand-in in
`scripts/fit_quality_head.py`. The difference is not cosmetic:

* **Synthetic** labels ask "can densenet tell a Gaussian blur from no Gaussian
  blur". A human never looked at those images.
* **EyeQ** labels are three-level gradability judgements made by ophthalmic
  graders on real clinical captures, including the real failure modes - small
  pupil, media opacity, misaligned flash - that no `cv2.GaussianBlur` produces.

`.claude/rules/ml.md` requires the two to stay in SEPARATE tables, so nothing
here pools them and the provenance sidecar written by the notebook records
which labels a head was fitted on.

The label scale, from the paper:

    0 = Good      gradable
    1 = Usable    gradable, with some degradation
    2 = Reject    ungradable

The head is binary, `gradable vs reject` (`{0,1}` against `{2}`), because that
is the decision the gate actually makes and the setting QuickQual's published
AUC of 0.9687 refers to. The three-way `usable | borderline | reject` verdict
is produced downstream by cutting P(gradable) at the two thresholds in
`config/thresholds.yaml`; it is not three classes in the head.

Patient identity is REAL here, unlike APTOS: an EyePACS filename is
`<patient>_<left|right>.jpeg`, so both eyes of one patient are kept in the
same fold. That is a guarantee the APTOS manifest cannot make.
"""

from __future__ import annotations

import csv
import pathlib
import re
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np

from netra.models.splits import SEED, assign_fold

EYEQ_REPO = "https://raw.githubusercontent.com/HzFu/EyeQ/master/data"
LABEL_URLS = {
    "train": f"{EYEQ_REPO}/Label_EyeQ_train.csv",
    "test": f"{EYEQ_REPO}/Label_EyeQ_test.csv",
}

QUALITY_GOOD = 0
QUALITY_USABLE = 1
QUALITY_REJECT = 2
QUALITY_NAMES = {
    QUALITY_GOOD: "good",
    QUALITY_USABLE: "usable",
    QUALITY_REJECT: "reject",
}
#: The binary head's positive class: gradable.
GRADABLE = (QUALITY_GOOD, QUALITY_USABLE)

#: `12345_left.jpeg`. The prefix is the EyePACS patient id, and it is real.
EYEPACS_NAME = re.compile(r"^(\d+)_(left|right)$", re.IGNORECASE)
IMAGE_EXTENSIONS = (".jpeg", ".jpg", ".png")
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".ipynb_checkpoints"}


class NoEyePACSImages(FileNotFoundError):
    """No directory under the search root looks like EyePACS."""


@dataclass(frozen=True)
class EyeQRow:
    """One human quality judgement, and the patient it belongs to."""

    image: str
    patient_id: str
    eye: str
    quality: int
    dr_grade: int

    @property
    def stem(self) -> str:
        return self.image.rsplit(".", 1)[0]

    @property
    def gradable(self) -> int:
        """1 when a human called this image gradable (Good or Usable)."""
        return int(self.quality in GRADABLE)


# ------------------------------------------------------------------- labels


def fetch_label_csvs(
    dest_dir: pathlib.Path,
    urls: dict[str, str] | None = None,
    timeout: int = 60,
) -> dict[str, pathlib.Path]:
    """Download the two EyeQ CSVs. ~700 KiB total; no images are fetched.

    Kaggle needs **Internet ON** in the notebook settings for this. There is
    no Kaggle dataset of the EyeQ labels we can rely on being attached, and
    vendoring somebody's label file into this repo would make its provenance
    a matter of trust rather than a URL.
    """
    urls = urls or LABEL_URLS
    dest_dir = pathlib.Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, pathlib.Path] = {}
    for name, url in urls.items():
        target = dest_dir / f"Label_EyeQ_{name}.csv"
        if not (target.exists() and target.stat().st_size > 0):
            with urllib.request.urlopen(url, timeout=timeout) as response:
                target.write_bytes(response.read())
        out[name] = target
    return out


def parse_label_csv(path: pathlib.Path) -> tuple[list[EyeQRow], dict]:
    """EyeQ's `,image,quality,DR_grade` -> rows, counting everything dropped.

    The leading unnamed column is pandas' index; it is ignored. A filename
    that is not `<digits>_<left|right>` has no recoverable patient id and is
    dropped rather than given a fabricated one - a wrong patient id would
    silently break the patient-level fold guarantee.
    """
    path = pathlib.Path(path)
    with path.open(newline="", encoding="utf-8") as fh:
        raw = list(csv.DictReader(fh))
    if not raw:
        raise ValueError(f"{path} has no rows")
    missing = {"image", "quality"} - set(raw[0])
    if missing:
        raise ValueError(f"{path} missing columns: {sorted(missing)}")

    rows: list[EyeQRow] = []
    dropped_name = 0
    dropped_quality = 0
    dropped_dupe = 0
    seen: set[str] = set()
    for r in raw:
        image = r["image"].strip()
        stem = image.rsplit(".", 1)[0]
        match = EYEPACS_NAME.match(stem)
        if match is None:
            dropped_name += 1
            continue
        try:
            quality = int(r["quality"])
        except (TypeError, ValueError):
            dropped_quality += 1
            continue
        if quality not in QUALITY_NAMES:
            dropped_quality += 1
            continue
        if stem in seen:
            dropped_dupe += 1
            continue
        seen.add(stem)
        try:
            dr_grade = int(r.get("DR_grade", -1))
        except (TypeError, ValueError):
            dr_grade = -1
        rows.append(
            EyeQRow(
                image=image,
                patient_id=match.group(1),
                eye=match.group(2).lower(),
                quality=quality,
                dr_grade=dr_grade,
            )
        )

    report = {
        "file": str(path),
        "n_rows": len(raw),
        "dropped_unparseable_name": dropped_name,
        "dropped_bad_quality": dropped_quality,
        "dropped_duplicate": dropped_dupe,
        "n_kept": len(rows),
        "retained_fraction": len(rows) / len(raw),
        "n_patients": len({r.patient_id for r in rows}),
        "quality_counts": quality_counts(rows),
    }
    return rows, report


def quality_counts(rows: list[EyeQRow]) -> dict[str, int]:
    counts = Counter(QUALITY_NAMES[r.quality] for r in rows)
    return {name: int(counts.get(name, 0)) for name in QUALITY_NAMES.values()}


# ------------------------------------------------- finding the mounted images


def find_eyepacs_roots(
    search_root: pathlib.Path, min_files: int = 50, max_depth: int = 6
) -> list[tuple[pathlib.Path, int]]:
    """Directories holding EyePACS-named images, most populated first.

    EyePACS is mounted on Kaggle under a slug this notebook cannot know in
    advance - the resized mirrors, the competition archive and the
    preprocessed variants all lay out differently. So the mount is DISCOVERED
    by filename shape (`<digits>_<left|right>.<ext>`) rather than hardcoded,
    and the candidates are printed so a human can see which one was used.
    """
    search_root = pathlib.Path(search_root)
    counts: dict[pathlib.Path, int] = defaultdict(int)
    if not search_root.exists():
        return []
    root_depth = len(search_root.parts)
    for path in search_root.rglob("*"):
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if len(path.parts) - root_depth > max_depth:
            continue
        if EYEPACS_NAME.match(path.stem):
            counts[path.parent] += 1
    return sorted(
        ((d, n) for d, n in counts.items() if n >= min_files),
        key=lambda pair: (-pair[1], str(pair[0])),
    )


def index_images(roots: list[pathlib.Path]) -> dict[str, pathlib.Path]:
    """`{stem: path}` over the given directories. First root wins a collision."""
    index: dict[str, pathlib.Path] = {}
    for root in roots:
        root = pathlib.Path(root)
        if not root.exists():
            continue
        for path in sorted(root.iterdir()):
            if path.suffix.lower() in IMAGE_EXTENSIONS and path.is_file():
                index.setdefault(path.stem, path)
    return index


def resolve(
    rows: list[EyeQRow], index: dict[str, pathlib.Path]
) -> tuple[list[tuple[EyeQRow, pathlib.Path]], dict]:
    """Pair each label with a file on disk. Reports the retained fraction.

    Expect this to be well below 1.0 on a partial mount, and that is the
    number to look at before anything else: EyeQ's train rows come from the
    EyePACS **train** set and its test rows from the EyePACS **test** set, so
    a mirror carrying only one of the two resolves roughly half the labels.
    `.claude/rules/ml.md` requires the fraction out loud at every such step.
    """
    matched: list[tuple[EyeQRow, pathlib.Path]] = []
    unmatched = 0
    for row in rows:
        path = index.get(row.stem)
        if path is None:
            unmatched += 1
            continue
        matched.append((row, path))
    report = {
        "n_labels": len(rows),
        "n_resolved": len(matched),
        "n_unmatched": unmatched,
        "retained_fraction": len(matched) / len(rows) if rows else 0.0,
        "n_patients": len({r.patient_id for r, _ in matched}),
        "quality_counts": quality_counts([r for r, _ in matched]),
    }
    return matched, report


# ------------------------------------------------------------------- folds


def patient_disjoint(groups: dict[str, list[tuple[EyeQRow, pathlib.Path]]]) -> bool:
    """True when no patient appears in two of the named groups."""
    seen: dict[str, str] = {}
    for name, pairs in groups.items():
        for row, _ in pairs:
            if seen.setdefault(row.patient_id, name) != name:
                return False
    return True


def hash_holdout(
    pairs: list[tuple[EyeQRow, pathlib.Path]], seed: int = SEED
) -> dict[str, list[tuple[EyeQRow, pathlib.Path]]]:
    """Patient-level fit/eval folds from the same hash the APTOS splits use.

    Only needed when the mount cannot resolve EyeQ's own published test rows.
    It is the same `assign_fold` - a hash of `(seed, patient_id)`, not a
    shuffle - so it is reproducible from the seed and stable as the mount
    grows. `train` becomes `fit`; `calib` and `test` together become `eval`,
    because this is one binary head with no third fold to spend.
    """
    out: dict[str, list[tuple[EyeQRow, pathlib.Path]]] = {"fit": [], "eval": []}
    for row, path in pairs:
        fold = assign_fold(f"eyepacs:{row.patient_id}", seed)
        out["fit" if fold == "train" else "eval"].append((row, path))
    return out


def cap_per_class(
    pairs: list[tuple[EyeQRow, pathlib.Path]],
    per_class: int | None,
    seed: int = SEED,
) -> tuple[list[tuple[EyeQRow, pathlib.Path]], dict]:
    """Cap each quality class at `per_class`, sampling without replacement.

    A T4 session is 9 hours and 28,792 images at 512px is not the best use of
    them, so the run is bounded. The cap is applied INSIDE a fold that is
    already patient-disjoint, so capping cannot move a patient across folds.
    The discarded fraction is reported, like every other filter here.
    """
    if per_class is None:
        return list(pairs), {
            "per_class": None,
            "n_in": len(pairs),
            "n_out": len(pairs),
            "retained_fraction": 1.0,
        }

    rng = np.random.default_rng(seed)
    by_class: dict[int, list[int]] = defaultdict(list)
    for i, (row, _) in enumerate(pairs):
        by_class[row.quality].append(i)

    keep: list[int] = []
    for quality in sorted(by_class):
        idx = np.asarray(by_class[quality])
        if len(idx) > per_class:
            idx = rng.choice(idx, size=per_class, replace=False)
        keep.extend(int(i) for i in idx)
    keep.sort()
    out = [pairs[i] for i in keep]
    return out, {
        "per_class": per_class,
        "n_in": len(pairs),
        "n_out": len(out),
        "retained_fraction": len(out) / len(pairs) if pairs else 0.0,
        "quality_counts": quality_counts([r for r, _ in out]),
    }


def labels_for(pairs: list[tuple[EyeQRow, pathlib.Path]]) -> np.ndarray:
    """The binary target the head is fitted on: 1 = gradable, 0 = reject."""
    return np.asarray([row.gradable for row, _ in pairs], dtype=int)


# -------------------------------------------------------------- feature pass


def features_for_paths(
    features,
    paths: list[pathlib.Path],
    batch_size: int = 32,
    progress_every: int = 512,
    log=print,
) -> tuple[np.ndarray, list[int], dict]:
    """Run the frozen backbone over image files. Returns `(X, kept_idx, report)`.

    An unreadable file is SKIPPED and counted rather than raising: a 28k-image
    mount with three truncated JPEGs should not lose a nine-hour session. The
    indices that survived come back, so the caller drops the same rows from
    its labels and the two can never fall out of step.
    """
    from netra.models.preprocess import load_image, preprocess

    blocks: list[np.ndarray] = []
    kept: list[int] = []
    unreadable: list[str] = []
    buffer: list[np.ndarray] = []
    buffer_idx: list[int] = []

    def flush() -> None:
        if not buffer:
            return
        blocks.append(features.batch(buffer, batch_size=len(buffer)))
        kept.extend(buffer_idx)
        buffer.clear()
        buffer_idx.clear()

    for i, path in enumerate(paths):
        try:
            processed, _ = preprocess(load_image(path))
        except Exception as exc:  # noqa: BLE001 - counted, not fatal
            unreadable.append(f"{path.name}: {type(exc).__name__}")
            continue
        buffer.append(processed)
        buffer_idx.append(i)
        if len(buffer) >= batch_size:
            flush()
        if progress_every and (i + 1) % progress_every == 0:
            log(f"  features: {i + 1}/{len(paths)} read, {len(kept)} usable")
    flush()

    X = np.concatenate(blocks, axis=0) if blocks else np.empty((0, 0))
    report = {
        "n_requested": len(paths),
        "n_featurised": len(kept),
        "n_unreadable": len(unreadable),
        "retained_fraction": len(kept) / len(paths) if paths else 0.0,
        "first_failures": unreadable[:5],
    }
    return X, kept, report


# ---------------------------------------------------------------- reporting


def gate_report(y_true: np.ndarray, p_gradable: np.ndarray) -> dict:
    """The REAL-label gate table. Every number comes from `netra/eval/metrics.py`.

    `.claude/rules/ml.md` forbids computing a metric inline, so accuracy is the
    only thing counted here and it is reported as a count with the Wilson
    interval `metrics.wilson_interval` returns - never as a bare percentage,
    per CLAUDE.md.

    Thresholded at 0.5 because this is the HEAD's own accuracy. The gate's
    three-way verdict uses the two cut-points in `config/thresholds.yaml` and
    is a different question, reported separately.
    """
    from netra.eval import metrics

    y_true = np.asarray(y_true, dtype=int)
    p = np.asarray(p_gradable, dtype=float)
    predicted = (p >= 0.5).astype(int)
    correct = int((predicted == y_true).sum())
    n = len(y_true)
    proba = np.column_stack([1.0 - p, p])
    return {
        "n": n,
        "n_correct": correct,
        "accuracy": correct / n if n else float("nan"),
        "accuracy_ci": metrics.wilson_interval(correct, n),
        "brier": metrics.brier(y_true, proba, labels=[0, 1]),
        "nll": metrics.nll(y_true, proba, labels=[0, 1]),
        "kappa": metrics.quadratic_weighted_kappa(y_true, predicted, n_classes=2),
        "n_positive": int(y_true.sum()),
        "n_negative": int(n - y_true.sum()),
    }


def verdict_report(gate, p_gradable: np.ndarray, y_true: np.ndarray) -> dict:
    """How the three-way verdict falls out, per true label.

    A reject that the gate calls `usable` is the failure that matters - it is
    the one that lets an ungradable image become a grade - so it is counted
    separately rather than averaged into an accuracy.
    """
    verdicts = [gate.verdict_from_p(float(p)) for p in np.asarray(p_gradable)]
    y_true = np.asarray(y_true, dtype=int)
    table: dict[str, dict[str, int]] = {}
    for truth, name in ((1, "gradable"), (0, "reject")):
        mask = y_true == truth
        counts = Counter(v for v, m in zip(verdicts, mask, strict=True) if m)
        table[name] = {
            k: int(counts.get(k, 0)) for k in ("usable", "borderline", "reject")
        }
    return {
        "cutoffs": {
            "usable_min_p": gate.usable_min_p,
            "reject_max_p": gate.reject_max_p,
        },
        "by_true_label": table,
        "ungradable_admitted_as_usable": table["reject"]["usable"],
    }
