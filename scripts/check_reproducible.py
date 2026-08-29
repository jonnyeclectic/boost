#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Build the project twice and report which release artifacts match.

    python3 scripts/check_reproducible.py
    python3 scripts/check_reproducible.py --source-date-epoch 1700000000
    python3 scripts/check_reproducible.py --skip-normalize   # show the raw gap

``docs/verifying-releases.md`` states that boost's wheel is reproducible and
its sdist is normalized to match — this is the script that keeps that a
measurement rather than an assertion. It builds the project twice with
``SOURCE_DATE_EPOCH`` pinned to the same value both times (the tip commit's
timestamp by default, matching what ``publish.yml`` actually releases), runs
each sdist through ``scripts/normalize_sdist.py`` — the same fix the release
pipeline applies, so this checks the pipeline that will actually ship rather
than the raw ``build`` output — and diffs the two output directories by
sha256. ``--skip-normalize`` reruns without that step, to show the gap it
closes.

Every artifact ``build`` writes is compared, by filename; a file present on
only one side counts as a mismatch rather than being silently ignored.

Exit codes:

* ``0`` — every artifact matched: reproducible, on this measurement.
* ``1`` — at least one artifact differed: not reproducible, and the report
  above names which one.
* ``2`` — nothing was actually verified (``build`` is not installed, the build
  itself failed, or it produced no artifacts). This is deliberately distinct
  from both ``0`` and a plain crash: a gate that reads "could not check" as
  "passed" is exactly the failure mode this project has hit before with its
  own CI controls (see the roadmap history on silent no-ops) — piping this
  script's exit code into a boolean check must not launder a 2 into a pass.

Stdlib only, no import of the ``build`` package at module load time — it
degrades to exit 2 with an explanation when that package is not installed,
rather than crashing on import.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MATCH, DIFFER = "match", "differ"


def build_available() -> bool:
    """Whether the ``build`` package can actually be imported right now."""
    return importlib.util.find_spec("build") is not None


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tip_epoch() -> int:
    """The committed timestamp of HEAD — what ``publish.yml`` builds from."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%ct"],
        cwd=ROOT, check=True, capture_output=True, text=True)
    return int(result.stdout.strip())


def build_once(outdir: Path, epoch: int, *, python: str = sys.executable) -> None:
    """One ``python -m build`` into *outdir*, pinned to *epoch*.

    ``--no-isolation`` on purpose: the point is to compare two runs of the
    *same* pinned toolchain (this is what makes the check runnable offline,
    including in a sandbox with no PyPI access), not to re-resolve the build
    backend from the network on every call. ``publish.yml`` pins the same
    toolchain a different way — ``requirements/release-tools.txt`` plus an
    exact-pinned ``[build-system].requires`` — so an isolated build there
    resolves to the identical versions this uses directly.
    """
    env = dict(os.environ)
    env["SOURCE_DATE_EPOCH"] = str(epoch)
    subprocess.run(
        [python, "-m", "build", "--no-isolation", "--outdir", str(outdir),
         str(ROOT)],
        check=True, capture_output=True, text=True, env=env,
    )


def normalize_sdists(outdir: Path, epoch: int) -> None:
    """Apply scripts/normalize_sdist.py to every sdist in *outdir*."""
    spec = importlib.util.spec_from_file_location(
        "normalize_sdist", ROOT / "scripts" / "normalize_sdist.py")
    if spec is None or spec.loader is None:
        raise ImportError("could not load scripts/normalize_sdist.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for sdist in sorted(outdir.glob("*.tar.gz")):
        mod.normalize(sdist, epoch)


def compare_dirs(a: Path, b: Path) -> dict[str, str]:
    """``{filename: MATCH|DIFFER}`` for every artifact built into *a* or *b*.

    Compares by filename rather than position, so a build that silently wrote
    a different set of files (not just different bytes) is still caught: a
    name present on only one side is reported as ``DIFFER``.
    """
    names = sorted({p.name for p in a.iterdir()} | {p.name for p in b.iterdir()})
    report = {}
    for name in names:
        fa, fb = a / name, b / name
        if not (fa.is_file() and fb.is_file()):
            report[name] = DIFFER
            continue
        report[name] = MATCH if sha256_of(fa) == sha256_of(fb) else DIFFER
    return report


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source-date-epoch", type=int, default=None,
                    help="defaults to the tip commit's timestamp "
                         "(git log -1 --format=%%ct)")
    ap.add_argument("--python", default=sys.executable,
                    help="interpreter to build with (default: this one)")
    ap.add_argument("--skip-normalize", action="store_true",
                    help="report the raw `python -m build` output, without "
                         "applying normalize_sdist.py first")
    args = ap.parse_args(argv)

    if not build_available():
        print("check_reproducible: the `build` package is not importable "
              "here — install requirements/release-tools.txt. SKIPPED "
              "(nothing was verified).", file=sys.stderr)
        return 2

    epoch = (args.source_date_epoch if args.source_date_epoch is not None
            else _tip_epoch())

    with tempfile.TemporaryDirectory(prefix="boost-repro-") as tmp:
        out_a, out_b = Path(tmp) / "a", Path(tmp) / "b"
        out_a.mkdir()
        out_b.mkdir()
        try:
            build_once(out_a, epoch, python=args.python)
            build_once(out_b, epoch, python=args.python)
        except subprocess.CalledProcessError as exc:
            print(f"check_reproducible: build failed: {exc.stderr}",
                 file=sys.stderr)
            return 2

        if not args.skip_normalize:
            normalize_sdists(out_a, epoch)
            normalize_sdists(out_b, epoch)

        report = compare_dirs(out_a, out_b)

    if not report:
        print("check_reproducible: neither build produced any artifacts. "
              "SKIPPED (nothing was verified).", file=sys.stderr)
        return 2

    ok = True
    for name, verdict in sorted(report.items()):
        print(f"{verdict:>6}  {name}")
        if verdict != MATCH:
            ok = False

    print()
    print(f"SOURCE_DATE_EPOCH={epoch}")
    print("REPRODUCIBLE" if ok else "NOT REPRODUCIBLE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
