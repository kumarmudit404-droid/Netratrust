"""Fetch a BOUNDED sample of APTOS images for the named split(s).

    python scripts/fetch_aptos_images.py --split calib --limit 80

Why bounded: the full APTOS mirror is ~8.6 GiB and the DR backbone trains on
Kaggle, not here (SPEC.md section 2, and there is no GPU on this box). What a
local sample is actually for is fitting the quality gate, fitting thresholds on
the CALIBRATION split, and proving the loops run on CPU. None of that needs the
whole corpus, and downloading it anyway would burn the build window.

It fetches per-file, so it only ever pulls images that belong to the split you
name - which is also the only way to keep the test split untouched while
working on calibration.

Requires the `kaggle` CLI on PATH and credentials. `kaggle` is deliberately NOT
added to `requirements.txt`: it is a developer tool invoked as a subprocess,
not something the application imports, and rules.md section 1 allows only
pinned imports.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

DATASET = "mariaherrerot/aptos2019"
#: Where the mirror keeps the files this script knows how to ask for.
REMOTE_DIR = "test_images/test_images"


def fetch_one(image_id: str, dest: Path) -> tuple[bool, str]:
    """Download one PNG. Returns (ok, note). Never raises on a single failure."""
    target = dest / f"{image_id}.png"
    if target.exists() and target.stat().st_size > 0:
        return True, "cached"
    proc = subprocess.run(
        [
            "kaggle",
            "datasets",
            "download",
            DATASET,
            "-f",
            f"{REMOTE_DIR}/{image_id}.png",
            "-p",
            str(dest),
            "--force",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip().splitlines()[-1:][0][:120]

    # The CLI MIRRORS THE REMOTE DIRECTORY under -p, so the payload lands at
    # <dest>/test_images/test_images/<id>.png.zip and not at <dest>/<id>.png.
    # It also zips single-file downloads. Both were found by running it.
    staged = dest / REMOTE_DIR
    for candidate in (
        staged / f"{image_id}.png.zip",
        dest / f"{image_id}.png.zip",
    ):
        if candidate.exists():
            import zipfile

            with zipfile.ZipFile(candidate) as zf:
                member = next((m for m in zf.namelist() if m.endswith(".png")), None)
                if member is None:
                    return False, "zip contained no png"
                target.write_bytes(zf.read(member))
            candidate.unlink()
            break
    else:
        for candidate in (staged / f"{image_id}.png", dest / f"{image_id}.png"):
            if candidate.exists() and candidate != target:
                target.write_bytes(candidate.read_bytes())
                candidate.unlink()
                break

    return (target.exists(), "ok" if target.exists() else "no png in payload")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="calib", choices=["train", "calib", "test"])
    ap.add_argument("--limit", type=int, default=80)
    ap.add_argument("--splits-dir", type=Path, default=Path("data/splits"))
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.split == "test":
        # rules.md: the test split is touched exactly once, at the end.
        print(
            "refusing to fetch the test split: it is touched exactly once, at the "
            "end (docs/rules/ml.md). Fit on calib.",
            file=sys.stderr,
        )
        return 2

    split_file = args.splits_dir / f"{args.split}.json"
    if not split_file.exists():
        print(f"no {split_file}; freeze the splits first", file=sys.stderr)
        return 2
    ids = json.loads(split_file.read_text())[: args.limit]

    dest = args.out or Path("data/aptos/images") / args.split
    dest.mkdir(parents=True, exist_ok=True)

    ok = 0
    failures: list[tuple[str, str]] = []
    for i, image_id in enumerate(ids, 1):
        good, note = fetch_one(image_id, dest)
        if good:
            ok += 1
        else:
            failures.append((image_id, note))
        if i % 10 == 0 or i == len(ids):
            print(f"  {i}/{len(ids)} requested, {ok} present", flush=True)

    # Retained fraction, out loud, per docs/rules/ml.md.
    print(f"\n{args.split}: {ok}/{len(ids)} = {ok / max(len(ids), 1):.4f} retained")
    if failures:
        print(f"{len(failures)} failed, first few:")
        for image_id, note in failures[:5]:
            print(f"  {image_id}: {note}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
