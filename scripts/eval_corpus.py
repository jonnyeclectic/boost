#!/usr/bin/env python3
"""Materialise the Tier 1 eval corpus at the exact commits it was measured on.

WHY THIS EXISTS. `tests/eval/taps.txt` used to pin repository NAMES. Tapping is
a shallow clone of whatever the default branch points at, so the corpus the
required `eval` gate scores against was a moving target: the list was written
recording **743** entries and the same 20 repos later resolved to **3,843**, a
5.2x growth nobody caused by editing a file. `affaan-m/ECC` alone is 1,616 of
them, so one third-party repository can move the gate's number by itself.

That is not academic. Measured on a clean 20-tap install, BM25 scores recall@10
**0.912** against a floor of **0.85** — a margin of +0.062. Unpinned growth
spends that margin quietly, and the first thing anyone would see is a required
gate failing on a pull request that touched nothing to do with retrieval.

So each row now carries a commit SHA, and this script checks each clone out at
it. `boost tap` still does the cloning (the corpus must be built the way a user
builds one); pinning is a step applied after, because the alternative — teaching
`boost tap` to pin — would add a CLI surface for a test-harness problem.

Usage:
  python3 scripts/eval_corpus.py --ensure          # tap + pin every row
  python3 scripts/eval_corpus.py --list            # print "repo sha" rows
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
TAPS = ROOT / "tests" / "eval" / "taps.txt"

_SHA = re.compile(r"[0-9a-f]{40}")


def parse_taps(text: str) -> List[Tuple[str, Optional[str]]]:
    """Rows of ``owner/repo [sha]``, comments and blank lines dropped.

    An absent SHA parses as ``None`` rather than an error so the format stays
    backward compatible, but a SHA that is *present and malformed* is fatal: a
    typo silently degrading to "unpinned" would reintroduce the exact drift this
    file exists to stop, while still looking pinned to a reader.
    """
    rows: List[Tuple[str, Optional[str]]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        repo = parts[0]
        if len(parts) == 1:
            rows.append((repo, None))
            continue
        sha = parts[1]
        if not _SHA.fullmatch(sha):
            raise SystemExit(
                "tests/eval/taps.txt: %s is pinned to %r, which is not a "
                "40-character commit SHA" % (repo, sha))
        rows.append((repo, sha))
    return rows


def _run(path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(path), *args],
                          capture_output=True, text=True)


def has_commit(path: Path, sha: str) -> bool:
    """True when ``sha`` names a commit already present in ``path``.

    ``^{commit}`` matters: `cat-file -e` succeeds for any object, so a tree or
    blob SHA would otherwise report as present and then fail at checkout.
    """
    return _run(path, "cat-file", "-e", "%s^{commit}" % sha).returncode == 0


def _fetch(path: Path, sha: str) -> subprocess.CompletedProcess:
    # Shallow: the corpus needs the tree at one commit, not the history to it.
    return _run(path, "fetch", "--quiet", "--depth", "1", "origin", sha)


def pin_clone(path: Path, sha: str) -> None:
    """Check ``path`` out at ``sha``, fetching the commit first if it is absent."""
    if not has_commit(path, sha):
        _fetch(path, sha)
    if not has_commit(path, sha):
        raise SystemExit(
            "%s: commit %s is not reachable — the pin in tests/eval/taps.txt is "
            "stale, or the repository rewrote history" % (path.name, sha))
    res = _run(path, "checkout", "--quiet", "--detach", sha)
    if res.returncode != 0:
        raise SystemExit("%s: could not check out %s: %s"
                         % (path.name, sha, res.stderr.strip()))


def _ensure() -> int:
    """Tap every row, pin it, and rebuild its cache from the pinned tree."""
    sys.path.insert(0, str(ROOT))
    from boost_cli.core import catalog, registry  # noqa: PLC0415

    rows = parse_taps(TAPS.read_text(encoding="utf-8"))
    total = 0
    for repo, sha in rows:
        try:
            tap = registry.get(repo)
        except Exception:
            tap = registry.add(repo)
        if sha:
            pin_clone(tap.path, sha)
        # Always after pinning: `boost tap` built the cache from the default
        # branch, so an unrebuilt cache would describe a tree we just replaced.
        entries = catalog.rebuild_tap(tap)
        total += len(entries)
        print("  %-44s %s  %5d entries"
              % (repo, (sha or "unpinned")[:7], len(entries)))
    print("corpus: %d entries across %d taps" % (total, len(rows)))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="eval_corpus.py", description=__doc__)
    p.add_argument("--ensure", action="store_true",
                   help="tap and pin every row, then rebuild its cache")
    p.add_argument("--list", action="store_true",
                   help="print the parsed rows and exit")
    args = p.parse_args(argv)
    if args.list:
        for repo, sha in parse_taps(TAPS.read_text(encoding="utf-8")):
            print("%s %s" % (repo, sha or ""))
        return 0
    if args.ensure:
        return _ensure()
    p.error("provide --ensure or --list")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
