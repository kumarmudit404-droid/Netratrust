"""Build `kaggle_payload.zip`: everything the Kaggle notebook imports, nothing else.

    python scripts/package_for_kaggle.py
    python scripts/package_for_kaggle.py --check      # verify, write nothing

Upload the zip as a Kaggle **Dataset** and attach it to the notebook. Kaggle
unpacks a dataset zip on attach, so the notebook finds `netra/`, `data/` and
`config/` directly under the mount point - no clone, no GitHub token, no
`pip install -e`, and nothing for a private repo to leak.

What goes in, and why only this:

* `netra/models/` and `netra/eval/` - Lane C's code, which is what the
  notebook imports. Both packages import only each other (checked below), so
  `netra/api`, `netra/db`, `netra/ledger` and `netra/ui` are not needed and
  are not shipped. The ledger signing key lives in `keys/` and must never
  travel in a dataset.
* `netra/__init__.py` and the two package `__init__.py` files, without which
  `import netra.models.train` fails on a path that otherwise looks right.
* `data/splits/` - the frozen folds. The run reads them; it never re-picks them.
* `data/manifest.csv` when it exists - it is gitignored, so this is best
  effort. The notebook needs a manifest for `collect()`, and rebuilds the full
  one on Kaggle from the mounted APTOS labels; this copy is what the growth
  step compares against to prove no image was relabelled.
* `config/thresholds.yaml` - `netra/models/thresholds.py` reads it at import
  time of the gate, and a missing file is an unhelpful failure 40 minutes in.
* `requirements.txt` - not installed wholesale on Kaggle (the image already
  has torch), but it is the pinned record of what the numbers were produced
  with, and the notebook prints a drift warning against it.

The verification is the point of this script existing rather than a shell
one-liner: every `netra.*` import inside the payload must resolve to a file
that is also in the payload. A zip that imports something it does not carry
fails on Kaggle after the session has already spent its time.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import pathlib
import sys
import zipfile

REPO = pathlib.Path(__file__).resolve().parents[1]

#: Directories copied whole, minus `EXCLUDE_SUFFIXES` and `EXCLUDE_DIRS`.
PAYLOAD_DIRS = ("netra/models", "netra/eval", "data/splits")
#: Individual files. `required` is False for anything gitignored.
PAYLOAD_FILES: tuple[tuple[str, bool], ...] = (
    ("netra/__init__.py", True),
    ("config/thresholds.yaml", True),
    ("requirements.txt", True),
    ("data/manifest.csv", False),
)
EXCLUDE_DIRS = {"__pycache__", ".ipynb_checkpoints", ".pytest_cache", ".ruff_cache"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".pkl", ".pt", ".db"}

#: A fixed timestamp, so the same tree always produces the same bytes.
ZIP_TIMESTAMP = (2026, 10, 28, 0, 0, 0)


def collect_paths(repo: pathlib.Path) -> tuple[list[pathlib.Path], list[str]]:
    """Every file to ship, repo-relative and sorted. Also returns what is missing."""
    chosen: list[pathlib.Path] = []
    missing: list[str] = []

    for rel in PAYLOAD_DIRS:
        directory = repo / rel
        if not directory.is_dir():
            missing.append(rel)
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            if any(part in EXCLUDE_DIRS for part in path.parts):
                continue
            if path.suffix.lower() in EXCLUDE_SUFFIXES:
                continue
            chosen.append(path.relative_to(repo))

    for rel, required in PAYLOAD_FILES:
        path = repo / rel
        if path.is_file():
            chosen.append(pathlib.Path(rel))
        elif required:
            missing.append(rel)

    return sorted(set(chosen)), missing


def netra_imports(source: str) -> set[str]:
    """Every `netra.*` module name a file imports, however it is written."""
    found: set[str] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "netra":
                    found.add(alias.name)
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.level == 0
            and node.module.split(".")[0] == "netra"
        ):
            found.add(node.module)
            for alias in node.names:
                found.add(f"{node.module}.{alias.name}")
    return found


def verify_imports_resolve(
    repo: pathlib.Path, paths: list[pathlib.Path]
) -> tuple[list[str], dict[str, set[str]]]:
    """Every `netra.*` import in the payload must point inside the payload.

    Returns `(problems, by_file)`. A dotted name may be a module or a name
    inside one, so both readings are accepted - `netra.eval.metrics.brier`
    resolves as long as `netra/eval/metrics.py` is shipped.
    """
    shipped = {str(p).replace("\\", "/") for p in paths}

    def resolves(dotted: str) -> bool:
        parts = dotted.split(".")
        while len(parts) > 1:
            stem = "/".join(parts)
            if f"{stem}.py" in shipped or f"{stem}/__init__.py" in shipped:
                return True
            parts = parts[:-1]
        return False

    problems: list[str] = []
    by_file: dict[str, set[str]] = {}
    for rel in paths:
        if rel.suffix != ".py":
            continue
        source = (repo / rel).read_text(encoding="utf-8")
        try:
            wanted = netra_imports(source)
        except SyntaxError as exc:
            problems.append(f"{rel}: does not parse ({exc})")
            continue
        by_file[str(rel)] = wanted
        unresolved = sorted(d for d in wanted if not resolves(d))
        # `from netra.ledger.chain import append` yields both the module and
        # the name; reporting both says the same thing twice. Keep the
        # shortest unresolvable prefix, which is the module that is missing.
        minimal = [
            d
            for d in unresolved
            if not any(d.startswith(f"{other}.") for other in unresolved)
        ]
        for dotted in minimal:
            problems.append(f"{rel}: imports {dotted}, which is NOT in the payload")
    return problems, by_file


def verify_contents(repo: pathlib.Path, paths: list[pathlib.Path]) -> list[str]:
    """Checks that cost nothing here and cost a Kaggle session otherwise."""
    problems: list[str] = []
    shipped = {str(p).replace("\\", "/") for p in paths}

    for name in ("train", "calib", "test"):
        rel = f"data/splits/{name}.json"
        if rel not in shipped:
            problems.append(f"missing frozen split {rel}")
        elif (repo / rel).stat().st_size == 0:
            problems.append(f"{rel} is empty")
    if "data/splits/meta.json" not in shipped:
        problems.append("missing data/splits/meta.json (the seed and manifest hash)")

    if "config/thresholds.yaml" in shipped:
        sys.path.insert(0, str(repo))
        try:
            from netra.models.thresholds import load

            load(repo / "config" / "thresholds.yaml")
        except Exception as exc:  # noqa: BLE001 - reported as a problem
            problems.append(f"config/thresholds.yaml does not parse: {exc}")

    for rel in ("keys", "netra/api", "netra/db", "netra/ledger", "netra/ui"):
        leaked = [p for p in shipped if p.startswith(f"{rel}/")]
        if leaked:
            problems.append(f"{rel}/ must not ship, but {len(leaked)} file(s) would")

    return problems


def build_zip(repo: pathlib.Path, paths: list[pathlib.Path], out: pathlib.Path) -> dict:
    """Write the zip deterministically: sorted entries, one fixed timestamp."""
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in paths:
            data = (repo / rel).read_bytes()
            total += len(data)
            info = zipfile.ZipInfo(str(rel).replace("\\", "/"), date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
    blob = out.read_bytes()
    return {
        "zip": str(out),
        "n_files": len(paths),
        "uncompressed_bytes": total,
        "zip_bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=pathlib.Path, default=REPO)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument(
        "--check", action="store_true", help="verify the payload and write nothing"
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    repo = args.repo.resolve()
    out = args.out or (repo / "kaggle_payload.zip")

    paths, missing = collect_paths(repo)
    problems = [f"missing required path: {m}" for m in missing]
    import_problems, _ = verify_imports_resolve(repo, paths)
    problems += import_problems
    problems += verify_contents(repo, paths)

    if not args.quiet:
        print(f"payload from {repo}")
        for rel in paths:
            size = (repo / rel).stat().st_size
            print(f"  {str(rel).replace(chr(92), '/'):<44} {size:>9,} B")
        if not (repo / "data" / "manifest.csv").exists():
            print(
                "\nnote: data/manifest.csv is absent (it is gitignored). The "
                "notebook rebuilds the full manifest on Kaggle from the mounted "
                "APTOS labels, so this only costs the relabelling cross-check."
            )

    if problems:
        print("\nREFUSING TO PACKAGE:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    if args.check:
        print(
            f"\nOK: {len(paths)} files, every netra.* import resolves inside the payload"
        )
        return 0

    summary = build_zip(repo, paths, out)
    print(f"\nwrote {summary['zip']}")
    print(f"  {summary['n_files']} files, {summary['zip_bytes']:,} B compressed")
    print(f"  sha256 {summary['sha256']}")
    print(
        "\nNext, on kaggle.com:\n"
        "  1. Datasets -> New Dataset -> upload this zip -> name it `netratrust-code`.\n"
        "  2. In the notebook: Add Input -> your `netratrust-code` dataset,\n"
        "     plus APTOS and an EyePACS mirror (see the notebook's first cell).\n"
        "  3. Settings -> Accelerator: GPU T4 x2, Internet: ON.\n"
        "  4. Run All."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
