#!/usr/bin/env python3
"""Split the mutation gate across parallel CI shards, and merge the results back.

The gate runs ~10.5k mutants over ``boost_cli/core`` and is the single longest
job in CI — roughly 26 minutes against ~9 for the next-slowest, so it alone sets
how long a PR (and therefore a release) waits.

mutmut's ``run`` accepts fnmatch patterns over mutant names
(``boost_cli.core.lockfile.x__skeleton__mutmut_1``), and each source file owns a
separate ``mutants/<path>.meta`` results file. Sharding *by file* therefore
produces disjoint outputs that merge by picking each file from the shard that
owned it — no per-mutant reconciliation.

Balance without a chicken-and-egg
---------------------------------
Ideal packing needs each file's mutant count, which you only learn by running
mutmut. Two weights, in order of preference:

1. ``scripts/mutation_weights.json`` — real counts, written by ``weights`` after
   any full run.
2. Non-comment, non-blank lines. Correlates with the real count at r = 0.96,
   but ``store.py`` is ~1.5x denser in mutants than average, so a purely
   line-based split reaches about 3.8x where real counts reach 5.0x.

The weights file is an **optimisation, never a correctness input**: if it is
absent, stale, or missing a file, the planner falls back to lines for whatever
it doesn't know. A stale file costs balance and nothing else, which is why it
needs no freshness gate — unlike every other generated file in this repo.

The bound worth knowing: one file can't be split, so the largest file is a floor
on the slowest shard. ``store.py`` is ~18% of all mutants, which caps the useful
speedup at about 5.4x no matter how many runners you add. ``plan --explain``
prints that cap.

Usage
-----
  mutation_shards.py plan --shards N --index I   # patterns for one shard
  mutation_shards.py plan --shards N --explain   # the whole split + speedup cap
  mutation_shards.py merge --shards N --into mutants results/*  # rebuild results
  mutation_shards.py weights --from mutants      # refresh the balance hints
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path("boost_cli/core")
WEIGHTS = Path("scripts/mutation_weights.json")


def line_weight(path: Path) -> int:
    """Non-comment, non-blank lines — the fallback stand-in for a mutant count.

    Never returns 0: a file with no code still costs a process spawn, and a
    0-weight file would make the packing order ambiguous between runs.
    """
    n = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                n += 1
    return max(n, 1)


def load_weights(root: Path) -> Dict[str, int]:
    """Real mutant counts, if a previous run left any. Missing file is normal."""
    path = root / WEIGHTS
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except ValueError:
        return {}
    counts = data.get("mutants_by_file", {})
    return {k: int(v) for k, v in counts.items() if isinstance(v, int) and v > 0}


def weight_fn(root: Path):
    """Prefer recorded mutant counts; fall back to lines per-file, not all-or-nothing."""
    recorded = load_weights(root)

    def weight(root_: Path, path: Path) -> int:
        return recorded.get(rel_name(root_, path)) or line_weight(path)

    return weight


def source_files(root: Path) -> List[Path]:
    """Every mutatable file, RECURSIVELY.

    mutmut walks ``source_paths`` with ``os.walk``, so a subpackage
    (``boost_cli/core/rag/bm25.py``) is mutated even though it is not a direct
    child. A non-recursive glob here would be worse than it sounds: those
    mutants would be assigned to no shard, merge would not notice them missing,
    and ``mutmut export-cicd-stats`` drops a file with no .meta from ``total``
    altogether — so the score would be computed over a subset and the required
    check would report PASS. That is fail-OPEN, the exact opposite of what the
    rest of this file guarantees, which is why the layout is asserted at merge.
    """
    return sorted((root / SOURCE).rglob("*.py"))


def rel_name(root: Path, path: Path) -> str:
    """Key files by their path under the source root, not by basename.

    ``core/util.py`` and ``core/rag/util.py`` are different files with the same
    name; keying on ``path.name`` would silently conflate them.
    """
    return path.relative_to(root / SOURCE).as_posix()


def is_init(path: Path) -> bool:
    return path.name == "__init__.py"


def pack(root: Path, shards: int) -> List[List[Path]]:
    """Longest-processing-time-first bin packing.

    Deterministic: every shard runs this and selects its own index, so they all
    have to agree. Ties break on the relative path, never on dict or glob order.

    ``__init__.py`` files are excluded — see ``pattern_for``: mutmut rewrites
    their mutant names so no pattern can address them. They are checked
    separately at merge instead of being silently ignored.
    """
    files = [f for f in source_files(root) if not is_init(f)]
    if not files:
        raise SystemExit("mutation_shards: no source files under %s" % SOURCE)
    weight = weight_fn(root)
    weighted = sorted(((weight(root, f), rel_name(root, f), f) for f in files),
                      key=lambda t: (-t[0], t[1]))

    bins: List[List[Path]] = [[] for _ in range(shards)]
    load = [0] * shards
    for w, _name, f in weighted:
        i = load.index(min(load))
        bins[i].append(f)
        load[i] += w
    return bins


def pattern_for(root: Path, path: Path):
    """`boost_cli/core/rag/bm25.py` -> `boost_cli.core.rag.bm25.*`

    Returns None for ``__init__.py``. mutmut's ``get_mutant_name`` does
    ``mutant_name.replace(".__init__.", ".")``, so a mutant of
    ``boost_cli/core/__init__.py`` is named ``boost_cli.core.<fn>__mutmut_1`` —
    a pattern of ``boost_cli.core.__init__.*`` can never match it, and the only
    pattern that would (``boost_cli.core.*``) would swallow every other module
    in the package. There is no correct pattern, so these are excluded and
    verified to contribute nothing instead.
    """
    if is_init(path):
        return None
    rel = path.relative_to(root / SOURCE).with_suffix("").as_posix()
    # as_posix(), not str(): on Windows str(Path("boost_cli/core")) is
    # "boost_cli\\core", so replacing "/" would be a no-op and the pattern
    # would come out as "boost_cli\\core.lockfile.*" — matching nothing.
    return "%s.%s.*" % (SOURCE.as_posix().replace("/", "."), rel.replace("/", "."))


def cmd_plan(args: argparse.Namespace) -> int:
    root = Path(args.root)
    bins = pack(root, args.shards)

    if args.explain:
        weight = weight_fn(root)
        loads = [sum(weight(root, f) for f in b) for b in bins]
        total = sum(loads)
        recorded = load_weights(root)
        print("files       : %d" % len(source_files(root)))
        print("weights     : %s" % ("%d real mutant counts from %s"
                                    % (len(recorded), WEIGHTS) if recorded
                                    else "lines of code (no %s yet)" % WEIGHTS))
        print("total weight: %d" % total)
        print("ideal shard : %d" % (total // args.shards))
        print("largest file: %d  (floor on the slowest shard)"
              % max(weight(root, f) for f in source_files(root) if not is_init(f)))
        print("speedup cap : %.2fx" % (total / max(loads)))
        for i, (b, ld) in enumerate(zip(bins, loads)):
            print("  shard %d: weight %5d, %2d files" % (i, ld, len(b)))
        return 0

    if args.index is None:
        raise SystemExit("mutation_shards plan: --index is required without --explain")
    if not 0 <= args.index < args.shards:
        raise SystemExit("mutation_shards plan: --index %d out of range for %d shards"
                         % (args.index, args.shards))
    patterns = [pattern_for(root, f) for f in bins[args.index]]
    print(" ".join(p for p in patterns if p))
    return 0


def shard_meta(parent: Path, prefix: str, shard: int, name: str):
    """Locate one file's .meta inside shard `shard`'s downloaded artifact.

    Shards are addressed by name (``<parent>/<prefix><index>/``) rather than by
    argument position, so a mis-ordered download can't silently attribute one
    shard's results to another file. Both artifact layouts are accepted: whether
    the upload kept ``boost_cli/core/`` or flattened to the .meta files alone
    depends on the glob used, and that is not worth a build failure.
    """
    base = parent / ("%s%d" % (prefix, shard))
    for candidate in (base / SOURCE / (name + ".meta"), base / (name + ".meta")):
        if candidate.exists():
            return candidate
    return None


def cmd_merge(args: argparse.Namespace) -> int:
    """Collect each file's .meta from the shard that owned it.

    Fails closed on purpose. A missing or still-unrun file is NOT silently
    dropped: mutmut counts a ``None`` exit code as "not checked" and
    mutation_gate.py divides by ``total - skipped``, so a partial merge would
    quietly lower the score rather than error. We would rather say which shard
    is missing than let the gate pass or fail for the wrong reason.
    """
    root = Path(args.root)
    bins = pack(root, args.shards)
    owner: Dict[str, int] = {}
    for i, b in enumerate(bins):
        for f in b:
            owner[rel_name(root, f)] = i

    into = Path(args.into)
    dest_dir = into / SOURCE
    dest_dir.mkdir(parents=True, exist_ok=True)

    problems: List[str] = []
    merged: List[Tuple[str, int, int]] = []
    for name, shard in sorted(owner.items()):
        src = shard_meta(Path(args.source), args.prefix, shard, name)
        if src is None:
            problems.append("%s: no results from shard %d under %s/%s%d"
                            % (name, shard, args.source, args.prefix, shard))
            continue
        data = json.loads(src.read_text())
        codes = data.get("exit_code_by_key", {})
        unrun = sum(1 for v in codes.values() if v is None)
        if unrun:
            problems.append("%s: %d/%d mutants unrun in shard %d"
                            % (name, unrun, len(codes), shard))
            continue
        dest = dest_dir / (name + ".meta")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        merged.append((name, len(codes), shard))

    # Every mutatable file must be accounted for. Without this, a file the
    # planner failed to enumerate is not merely unmerged — mutmut's
    # export-cicd-stats skips a path with no .meta, dropping it from `total`
    # rather than counting it unkilled, so the gate would pass on a subset.
    # This is the backstop for any future layout drift (a new subpackage, a
    # widened source_paths) that this file's own globbing might miss.
    planned = set(owner)
    for f in source_files(root):
        name = rel_name(root, f)
        if name in planned:
            continue
        if not is_init(f):
            problems.append("%s: mutatable but assigned to no shard (planner missed it)"
                            % name)
            continue
        # __init__.py has no addressable pattern (see pattern_for). That is only
        # safe while it generates nothing; if it ever does, say so loudly rather
        # than quietly leaving those mutants untested.
        found = None
        for shard in range(args.shards):
            found = shard_meta(Path(args.source), args.prefix, shard, name)
            if found is not None:
                break
        if found is not None and json.loads(found.read_text()).get("exit_code_by_key"):
            problems.append(
                "%s now generates mutants, but mutmut rewrites its mutant names so no "
                "shard pattern can address them. Move the code out of __init__.py, or "
                "run the gate unsharded." % name)

    total = sum(n for _, n, _ in merged)
    print("merged %d files, %d mutants, from %d shards"
          % (len(merged), total, args.shards))
    if problems:
        print("\nmutation_shards: INCOMPLETE — refusing to gate on partial results:")
        for p in problems:
            print("  - %s" % p)
        return 1
    return 0


# Anything that can change what the unit suite does to a mutant in
# boost_cli/core. Deliberately wider than "boost_cli/core/" alone:
#
#   boost_cli/**   setup.cfg's `also_copy` copies the whole package into
#                  mutants/, and the tests import it — a change in commands/
#                  or cli.py can flip a core mutant from survived to killed.
#   tests/**       a new assertion kills a survivor without touching source.
#   setup.cfg      mutmut's own config: source_paths, test selection, also_copy.
#   pyproject.toml pytest configuration and the packaging metadata under it.
#   requirements/mutation-tools.txt  pins pytest+mutmut; the kill count is
#                  defined relative to those versions.
#   scripts/mutation_*.py, .github/workflows/ci.yml  the gate itself.
#
# Everything else — docs, the roadmap boards, other workflows, README — cannot
# move the score, and those are 38% of this repo's merged pull requests.
RELEVANT_PREFIXES = (
    "boost_cli/",
    "tests/",
    "requirements/mutation-tools.txt",
    "scripts/mutation_gate.py",
    "scripts/mutation_shards.py",
    ".github/workflows/ci.yml",
)
RELEVANT_EXACT = ("setup.cfg", "pyproject.toml")


def is_relevant(changed: List[str]) -> bool:
    """True when the mutation score could differ from the base commit's."""
    for name in changed:
        name = name.strip()
        if not name:
            continue
        if name in RELEVANT_EXACT:
            return True
        if name.endswith("conftest.py"):
            return True
        for prefix in RELEVANT_PREFIXES:
            if name.startswith(prefix):
                return True
    return False


def cmd_scope(args: argparse.Namespace) -> int:
    """Print `true`/`false`: can the mutation score have changed?

    Fails SAFE. An empty or unreadable file list means we could not prove the
    score is unchanged, so we say `true` and do the work. The expensive outcome
    is a wasted 26 minutes; the cheap-looking one is a gate that silently stops
    gating.
    """
    if args.changed == "-":
        changed = sys.stdin.read().splitlines()
    else:
        path = Path(args.changed)
        if not path.exists():
            print("true")
            return 0
        changed = path.read_text().splitlines()

    if not changed:
        print("true")
        return 0
    print("true" if is_relevant(changed) else "false")
    return 0


def cmd_weights(args: argparse.Namespace) -> int:
    """Record real mutant counts so the next split balances better.

    Purely advisory (see the module docstring), so this never fails a build:
    it writes what it can find and reports what it found.
    """
    root = Path(args.root)
    src = Path(args.source) / SOURCE
    counts = {}
    for meta in sorted(src.rglob("*.py.meta")):
        codes = json.loads(meta.read_text()).get("exit_code_by_key", {})
        if codes:
            rel = meta.relative_to(src).as_posix()
            counts[rel[: -len(".meta")]] = len(codes)
    if not counts:
        print("mutation_shards: no .meta results under %s — nothing to record" % src)
        return 1
    out = root / WEIGHTS
    out.write_text(json.dumps(
        {"_comment": "Advisory shard-balance hints; see scripts/mutation_shards.py. "
                     "Stale entries cost balance, never correctness.",
         "mutants_by_file": counts},
        indent=2, sort_keys=True) + "\n")
    print("wrote %s: %d files, %d mutants" % (out, len(counts), sum(counts.values())))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(ROOT), help="repo root (default: this checkout)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="print the fnmatch patterns for one shard")
    p.add_argument("--shards", type=int, required=True)
    p.add_argument("--index", type=int)
    p.add_argument("--explain", action="store_true", help="print the whole split instead")
    p.set_defaults(func=cmd_plan)

    m = sub.add_parser("merge", help="merge per-shard .meta results for the gate")
    m.add_argument("--shards", type=int, required=True)
    m.add_argument("--into", default="mutants")
    m.add_argument("--source", default="shard-results",
                   help="parent dir holding one downloaded artifact per shard")
    m.add_argument("--prefix", default="mutation-shard-",
                   help="artifact name prefix; the shard index is appended")
    m.set_defaults(func=cmd_merge)

    s = sub.add_parser("scope", help="can the mutation score have changed?")
    s.add_argument("--changed", default="-",
                   help="file of changed paths, one per line ('-' for stdin)")
    s.set_defaults(func=cmd_scope)

    w = sub.add_parser("weights", help="record real mutant counts to improve balance")
    w.add_argument("--source", default="mutants", help="a mutants/ tree from a full run")
    w.set_defaults(func=cmd_weights)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
