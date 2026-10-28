"""Read `config/thresholds.yaml`. One source of truth for clinical thresholds.

Why a parser and not PyYAML: PyYAML is not pinned in `requirements.txt` (it is
only present transitively, via timm), and rules.md section 1 allows only what
is pinned, with any addition requiring an agreed change to `requirements.txt`
in its own commit. CLAUDE.md also says to prefer a stdlib solution over a
dependency. So this reads the small, flat subset of YAML that
`config/thresholds.yaml` actually uses, and RAISES on anything it does not
recognise rather than guessing - a threshold that is silently misparsed is
worse than one that fails to load.

If the file ever grows block lists, anchors or multi-line strings, pin PyYAML
by agreement and delete this module.
"""

from __future__ import annotations

import pathlib
from typing import Any

#: Resolved from this file's location, not the process CWD: a route handler
#: must read the same thresholds whichever directory uvicorn was started in.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_PATH = REPO_ROOT / "config" / "thresholds.yaml"


class ConfigError(ValueError):
    pass


def _scalar(text: str, where: str) -> Any:
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_scalar(part, where) for part in inner.split(",")]
    if text in ("true", "false"):
        return text == "true"
    if text == "null" or text == "":
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
        raise ConfigError(f"{where}: cannot parse value {text!r}") from exc


def _strip_comment(line: str) -> str:
    """Drop a trailing `#` comment. The file uses no `#` inside a value."""
    return line.split("#", 1)[0].rstrip()


def load(path: str | pathlib.Path | None = None) -> dict[str, Any]:
    """Parse two levels of `key:` mappings with scalar or flow-list leaves."""
    path = pathlib.Path(path or DEFAULT_PATH)
    out: dict[str, Any] = {}
    section: dict[str, Any] | None = None

    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = _strip_comment(raw)
        if not line.strip():
            continue
        where = f"{path}:{lineno}"
        indent = len(line) - len(line.lstrip(" "))
        if ":" not in line:
            raise ConfigError(f"{where}: expected `key: value` or `key:`")
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
                raise ConfigError(f"{where}: indented key outside a section")
            if not value.strip():
                raise ConfigError(f"{where}: nested mappings are not supported")
            section[key] = _scalar(value, where)
        else:
            raise ConfigError(f"{where}: unexpected indent {indent} (expected 0 or 2)")
    return out


# --------------------------------------------------- the values Lane A needs


def refer_grades(path: str | pathlib.Path | None = None) -> tuple[int, ...]:
    """`dr.refer_grades` - moderate NPDR or worse. Mirrored in the UI's clinical.ts."""
    grades = load(path).get("dr", {}).get("refer_grades")
    if not isinstance(grades, list) or not all(isinstance(g, int) for g in grades):
        raise ConfigError("dr.refer_grades must be a list of integers")
    return tuple(grades)
