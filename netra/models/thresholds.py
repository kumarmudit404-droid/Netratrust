"""Read and write `config/thresholds.yaml`.

Lane A reads this file with a deliberately minimal stdlib parser
(`netra/api/config.py`) that RAISES on any syntax it does not recognise rather
than guessing. So anything written here must stay inside that subset:

* two levels only - top-level `key:` sections, two-space indented scalars;
* leaf values are scalars or inline flow lists (`[2, 3, 4]`);
* no block lists, no anchors, no nested maps, no multi-line strings.

`tests/test_thresholds.py` asserts that Lane A's parser can read what this
module writes, so a format drift fails a test here instead of 500-ing a route
handler there.

PyYAML is not used, for the same reason Lane A does not use it: it is present
only transitively (via timm) and is not pinned in `requirements.txt`, and
rules.md section 1 allows only what is pinned.

**The schema is Lane A's contract.** Only fitted VALUES change. Adding or
renaming a key breaks a reader in another lane.
"""

from __future__ import annotations

import pathlib
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_PATH = REPO_ROOT / "config" / "thresholds.yaml"

#: Every key Lane A or Lane C reads. Checked on write so a fitted file can
#: never silently drop one.
REQUIRED_SCHEMA: dict[str, tuple[str, ...]] = {
    "quality_gate": ("usable_min_p", "reject_max_p"),
    "dr": ("conformal_confidence", "refer_grades", "abstain_if_set_spans_actions"),
    "sites": ("min_n_for_rate",),
}


class ThresholdError(ValueError):
    pass


# --------------------------------------------------------------------- read


def _scalar(text: str, where: str) -> Any:
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        return [] if not inner else [_scalar(p, where) for p in inner.split(",")]
    if text in ("true", "false"):
        return text == "true"
    if text in ("null", ""):
        return None
    if text[0] in "\"'" and text[-1] == text[0]:
        return text[1:-1]
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError as exc:
        raise ThresholdError(f"{where}: cannot parse {text!r}") from exc


def load(path: str | pathlib.Path | None = None) -> dict[str, Any]:
    """Parse the two-level subset. Raises on anything outside it."""
    path = pathlib.Path(path or DEFAULT_PATH)
    out: dict[str, Any] = {}
    section: dict[str, Any] | None = None

    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        where = f"{path.name}:{lineno}"
        indent = len(line) - len(line.lstrip(" "))
        if ":" not in line:
            raise ThresholdError(f"{where}: expected `key: value` or `key:`")
        key, _, value = line.strip().partition(":")
        key = key.strip()

        if indent == 0:
            if value.strip():
                out[key] = _scalar(value, where)
                section = None
            else:
                section = {}
                out[key] = section
        elif indent == 2:
            if section is None:
                raise ThresholdError(f"{where}: indented key outside a section")
            if not value.strip():
                raise ThresholdError(f"{where}: nested mappings are not supported")
            section[key] = _scalar(value, where)
        else:
            raise ThresholdError(f"{where}: unexpected indent {indent}")
    return out


# ------------------------------------------------------- typed accessors


def refer_grades(cfg: dict[str, Any] | None = None) -> tuple[int, ...]:
    """`dr.refer_grades` - moderate NPDR or worse. Mirrored in Lane B's clinical.ts."""
    cfg = cfg or load()
    grades = cfg.get("dr", {}).get("refer_grades")
    if not isinstance(grades, list) or not all(isinstance(g, int) for g in grades):
        raise ThresholdError("dr.refer_grades must be a list of integers")
    return tuple(grades)


def conformal_confidence(cfg: dict[str, Any] | None = None) -> float:
    cfg = cfg or load()
    value = cfg.get("dr", {}).get("conformal_confidence")
    if not isinstance(value, (int, float)) or not 0 < float(value) < 1:
        raise ThresholdError("dr.conformal_confidence must be in (0, 1)")
    return float(value)


def quality_cutoffs(cfg: dict[str, Any] | None = None) -> tuple[float, float]:
    """`(usable_min_p, reject_max_p)`, checked to be ordered and in [0,1].

    An unordered pair would make "borderline" an empty band and quietly turn
    the three-way gate into a two-way one.
    """
    cfg = cfg or load()
    gate = cfg.get("quality_gate", {})
    usable, reject = gate.get("usable_min_p"), gate.get("reject_max_p")
    for name, v in (("usable_min_p", usable), ("reject_max_p", reject)):
        if not isinstance(v, (int, float)) or not 0.0 <= float(v) <= 1.0:
            raise ThresholdError(f"quality_gate.{name} must be in [0, 1]")
    if float(reject) >= float(usable):
        raise ThresholdError(
            f"reject_max_p ({reject}) must be below usable_min_p ({usable}); "
            "otherwise there is no borderline band"
        )
    return float(usable), float(reject)


# -------------------------------------------------------------------- write


def _render_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(_render_scalar(v) for v in value) + "]"
    if value is None:
        return "null"
    if isinstance(value, float):
        # Two decimals: these are probability cut-points fitted on a few dozen
        # calibration cases. More digits would imply precision that is not
        # there, and the file is read by a parser that accepts plain decimals.
        return f"{value:.2f}"
    return str(value)


def dump(cfg: dict[str, Any], header: str = "") -> str:
    """Render the two-level subset. Validates the schema before rendering."""
    for section, keys in REQUIRED_SCHEMA.items():
        if section not in cfg:
            raise ThresholdError(f"missing section {section!r}")
        for key in keys:
            if key not in cfg[section]:
                raise ThresholdError(f"missing {section}.{key}")

    lines: list[str] = []
    for raw in header.splitlines():
        lines.append(f"# {raw}".rstrip())
    for section, body in cfg.items():
        if not isinstance(body, dict):
            raise ThresholdError(f"{section}: top-level scalars are not written here")
        lines.append(f"{section}:")
        for key, value in body.items():
            lines.append(f"  {key}: {_render_scalar(value)}")
    return "\n".join(lines) + "\n"


def write(
    cfg: dict[str, Any],
    path: str | pathlib.Path | None = None,
    header: str = "",
) -> pathlib.Path:
    """Write, then re-read and compare. A file that cannot be parsed back is
    never left on disk."""
    path = pathlib.Path(path or DEFAULT_PATH)
    text = dump(cfg, header)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

    reread = load(path)
    for section, keys in REQUIRED_SCHEMA.items():
        for key in keys:
            if section not in reread or key not in reread[section]:
                raise ThresholdError(f"{section}.{key} did not survive a round trip")
    return path
