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

Splitting one file
------------------
A file heavier than an even share is the floor on the critical path all by
itself, and ``store.py`` is 18.4% of every mutant in the repo. Mutant names are
addressable per *function*, though, so such a file is split into one unit per
top-level function and those units are packed independently.

Two properties keep that safe, and ``tests/unit/test_mutation_subfile_shards.py``
asserts both rather than trusting the reading:

* **Patterns stay disjoint.** ``...x_install__mutmut_*`` must not swallow
  ``install_from_path``; anchoring on the ``__mutmut_`` suffix is what prevents
  it. A file whose partition cannot be enumerated exactly — any class with
  methods, any duplicate name — is left whole rather than guessed at.
* **The merge still fails closed.** Every shard writes a ``.meta`` listing every
  key in the file, with ``None`` against the mutants it was not asked to run, so
  the merge unions them and a key is only "unrun" when it is ``None``
  everywhere. A function no shard was assigned therefore reddens the gate, which
  matters because mutmut counts an unrun mutant inside ``total`` and
  ``export-cicd-stats`` drops a file with no ``.meta`` from ``total``
  altogether — either would quietly gate on a subset.

Balance without a chicken-and-egg
---------------------------------
Ideal packing needs each file's mutant count, which you only learn by running
mutmut. Three weights, in order of preference:

1. Recorded **milliseconds**, written by ``weights`` from mutmut's per-mutant
   durations, both per file and per function. Time is what the critical path is
   made of, and it is *not* proportional to count — a ``store.py`` mutant
   re-runs a far larger covering test set than an ``ed25519.py`` one, and a
   survivor runs its tests to completion where a kill exits early.

   Measured, not assumed. Weighting by count balanced the shards to 1.08x of
   ideal *by count* while leaving them **2.24x** apart *by time*. The same
   proxy error repeats inside a file: across ``store.py``'s functions the
   per-mutant cost spans 0.273 s to 3.900 s (14.3x), and ``install`` alone is
   36% of the file's time from 12% of its mutants — so a count-apportioned
   split sent its shard to 8.9 minutes against a 4.8-minute sibling. Both
   levels are therefore weighted on measured time.

   Every weight must share a unit, since milliseconds run to five digits where
   counts run to three and one file weighted in time among files weighted in
   counts would take a shard to itself. A file with no recorded duration is
   therefore **imputed** at the measured mean rate rather than mixed in raw —
   and rather than disabling the tier outright, which proved far too brittle:
   on the first real run exactly one file of 46 came back short.

   (Balancing on time was pointless while a file was indivisible, since the
   floor was the heaviest file either way. Sub-file units are what make it
   worth doing, and the two together are what deliver: splitting alone moved
   the bottleneck from shard 0 to shard 3 rather than removing it.)
2. ``scripts/mutation_weights.json`` — real counts, written by ``weights`` after
   any full run.
3. Non-comment, non-blank lines. Correlates with the real count at r = 0.96,
   but ``store.py`` is ~1.5x denser in mutants than average, so a purely
   line-based split reaches about 3.8x where real counts reach 5.0x.

The weights file is an **optimisation, never a correctness input**: if it is
absent, stale, or missing a file, the planner falls back to lines for whatever
it doesn't know. A stale file costs balance and nothing else, which is why it
needs no freshness gate — unlike every other generated file in this repo.

The bound worth knowing: the largest *unit* is a floor on the slowest shard.
That used to be the largest file — ``store.py``, capping the useful speedup at
about 5.4x — and is now the largest unsplittable file, which lifts the cap to
about 6.0x at six shards. ``plan --explain`` prints the cap, which files were
split, and the resulting per-shard loads.

Usage
-----
  mutation_shards.py plan --shards N --index I   # patterns for one shard
  mutation_shards.py plan --shards N --explain   # the whole split + speedup cap
  mutation_shards.py merge --shards N --into mutants results/*  # rebuild results
  mutation_shards.py weights --source mutants    # refresh the balance hints
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path("boost_cli/core")
WEIGHTS = Path("scripts/mutation_weights.json")


def line_weight(path: Path) -> int:
    """Non-comment, non-blank lines — the fallback stand-in for a mutant count.

    Never returns 0: a file with no code still costs a process spawn, and a
    0-weight file would make the packing order ambiguous between runs.
    """
    n = 0
    with open(_as_path(path), encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                n += 1
    return max(n, 1)


def load_weights(root: Path) -> dict[str, int]:
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


def load_symbol_weights(root: Path) -> dict[str, dict[str, int]]:
    """Recorded per-function mutant counts, if a previous run left any.

    Same contract as ``load_weights``: advisory, and a missing or corrupt file
    is normal rather than fatal — a stale hint costs balance, never correctness.
    """
    path = root / WEIGHTS
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except ValueError:
        return {}
    out: dict[str, dict[str, int]] = {}
    for name, syms in (data.get("mutants_by_symbol") or {}).items():
        if isinstance(syms, dict):
            out[name] = {s: int(v) for s, v in syms.items()
                         if isinstance(v, int) and v > 0}
    return out


def load_symbol_durations(root: Path) -> dict[str, dict[str, int]]:
    """Recorded per-FUNCTION run time in milliseconds, if a previous run left any.

    The share basis that matters inside a split file. Mutant count is a poor
    proxy for time *within* a file as much as across the repo: measured over
    ``store.py``, per-mutant cost ranges 0.273 s to 3.900 s across its functions
    — a 14.3x spread — and ``install`` alone is 36% of the file's time from 12%
    of its mutants. Apportioning by count therefore under-weights it badly, and
    a shard that drew it ran 8.9 minutes against a 4.8-minute sibling.
    """
    path = root / WEIGHTS
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except ValueError:
        return {}
    out: dict[str, dict[str, int]] = {}
    for name, syms in (data.get("millis_by_symbol") or {}).items():
        if isinstance(syms, dict):
            out[name] = {s: int(v) for s, v in syms.items()
                         if isinstance(v, (int, float)) and v > 0}
    return out


def load_durations(root: Path) -> dict[str, int]:
    """Recorded per-file RUN TIME in milliseconds, if a previous run left any.

    Time is the quantity the critical path is actually made of, and it is not
    proportional to mutant count: measured throughput across this repo spans
    3.39 to 14.19 mutants/second, because a ``store.py`` mutant re-runs a far
    larger covering test set than an ``ed25519.py`` one, and a survivor runs its
    tests to completion where a kill exits early.

    Balancing on seconds was pointless while a file was indivisible — the floor
    was the heaviest single file either way, which is why the planner shipped
    counting mutants. Sub-file units remove that floor, so time-weighting now
    changes the answer.
    """
    path = root / WEIGHTS
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except ValueError:
        return {}
    out = {}
    for name, ms in (data.get("millis_by_file") or {}).items():
        if isinstance(ms, (int, float)) and ms > 0:
            out[name] = int(ms)
    return out


def weight_fn(root: Path):
    """Weight one file, preferring the most faithful signal available.

    Milliseconds are used only when EVERY mutatable file has a recorded
    duration, and otherwise not at all. That is not caution for its own sake:
    milliseconds run to five digits where counts and line totals run to three,
    so one file weighted in milliseconds among files weighted in counts would
    outweigh the whole rest of the repo and take a shard to itself. Counts and
    lines are interchangeable per-file because they share a scale; time is not,
    so it is all-or-nothing.
    """
    millis = load_durations(root)
    recorded = load_weights(root)
    files = [f for f in source_files(root) if not is_init(f)]

    # A file with no recorded duration is IMPUTED from the measured mean rate
    # (milliseconds per mutant across everything that was measured) rather than
    # disabling time-weighting for the whole repo. Requiring a complete record
    # was too brittle to be useful: on the first real run exactly one file of 46
    # came back short, which under an all-or-nothing rule would have silently
    # dropped the planner back to counting mutants. Imputing keeps every weight
    # in the same unit, which is the property that actually matters.
    imputed: dict[str, int] = {}
    if millis:
        measured_ms = sum(millis[n] for n in millis if n in recorded)
        measured_mutants = sum(recorded[n] for n in millis if n in recorded)
        rate = (measured_ms / measured_mutants) if measured_mutants else 0
        for f in files:
            name = rel_name(root, f)
            if name in millis:
                continue
            # Prefer its mutant count at the measured rate; fall back to lines
            # scaled the same way when even the count is unknown.
            basis = recorded.get(name) or line_weight(f)
            imputed[name] = max(round(basis * rate), 1) if rate else 0
    use_millis = bool(millis) and all(
        rel_name(root, f) in millis or imputed.get(rel_name(root, f))
        for f in files)

    def weight(root_: Path, path: Path) -> int:
        name = rel_name(root_, path)
        if use_millis:
            return millis.get(name) or imputed.get(name) or line_weight(path)
        return recorded.get(name) or line_weight(path)

    return weight


def source_files(root: Path) -> list[Path]:
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
    return _as_path(path).relative_to(root / SOURCE).as_posix()


def is_init(path: Path) -> bool:
    return _as_path(path).name == "__init__.py"


class Unit(NamedTuple):
    """One schedulable slice of work: a whole file, or one function in it.

    ``symbol is None`` means the whole file, which is what every file was before
    sub-file splitting existed and what all but the largest still are.
    """

    path: Path
    symbol: str | None = None

    @property
    def name(self) -> str:
        """The file's basename, so a Unit reads like the Path it replaced."""
        return self.path.name


def _as_path(path) -> Path:
    """Accept a Unit wherever a Path is expected.

    ``pack`` returns Units now, but the identity helpers below are about the
    *file* and are called with both. Unwrapping in one place keeps every caller
    from having to know which it is holding.
    """
    return path.path if isinstance(path, Unit) else path


def top_level_symbols(path: Path) -> list[str]:
    """The function names a file's mutants can be addressed by, or [].

    mutmut generates one ``x_<name>__mutmut_<n>`` per *function*, so the set of
    top-level functions is the complete partition of a module's mutants — but
    only when nothing else in the module can carry one. Returning [] disables
    splitting for that file, which is always safe: it just stays whole.

    Bails out on any class with a method body. mutmut mangles a method's name
    differently from a plain function, and guessing wrong would produce a
    pattern that matches nothing — leaving those mutants unrun, which merge
    would then (correctly, but unhelpfully) turn into a red build. A file we
    cannot partition provably is a file we do not split.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
        elif isinstance(node, ast.ClassDef) and any(
                isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                for m in node.body):
            return []
    # Duplicate names (a conditional redefinition) would make two units share
    # one pattern, so both shards would run the same mutants and one would
    # overwrite the other's results.
    if len(names) != len(set(names)):
        return []
    return names


def symbol_weight(path: Path, symbols: list[str]) -> dict[str, int]:
    """Per-function weight, by body size — the same stand-in ``line_weight`` uses.

    Recorded per-symbol mutant counts are preferred when a previous run left
    them (see ``cmd_weights``); this is the bootstrap, so the first split is
    already roughly balanced rather than waiting on a measured run.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return {}
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name in symbols:
            out[node.name] = max((node.end_lineno or node.lineno) - node.lineno, 1)
    return out


def units_for(root: Path, path: Path, ceiling: int) -> list[Unit]:
    """Split `path` into per-function units when it alone exceeds `ceiling`.

    ``ceiling`` is the ideal per-shard load. A file lighter than that can never
    be the critical path on its own, so splitting it only adds scheduling noise;
    a file heavier than it *is* the floor until it is split. That is the whole
    finding this implements — store.py is 18.4% of all mutants, so with six
    shards no packing of whole files can beat it.
    """
    weight = weight_fn(root)(root, path)
    if weight <= ceiling:
        return [Unit(path)]
    symbols = top_level_symbols(path)
    if len(symbols) < 2:
        return [Unit(path)]        # nothing to split it into
    return [Unit(path, s) for s in symbols]


def unit_weight(root: Path, unit: Unit) -> int:
    """Weight of one unit: the file's whole weight, or this function's share.

    A share, deliberately, rather than an independently-recorded figure: the
    file's weight already carries whichever unit ``weight_fn`` chose
    (milliseconds, mutant counts or lines), so apportioning it keeps every unit
    in the bin-packer commensurable no matter which tier is in play. Recording
    per-symbol times directly would reintroduce exactly the scale-mixing that
    ``weight_fn`` refuses.

    The share itself is taken from the best measurement available, in the same
    order of preference the file-level weights use: recorded per-function
    milliseconds, then recorded per-function mutant counts, then function body
    size to bootstrap a sensible first split before anything has been measured.

    Time first is not a refinement, it is the point. Count is as poor a proxy
    for time *within* a file as across the repo — 14.3x between the cheapest and
    dearest function of ``store.py`` — so a count-apportioned split leaves the
    shard holding ``install`` running nearly twice its siblings.
    """
    file_weight = weight_fn(root)(root, unit.path)
    if unit.symbol is None:
        return file_weight
    name = rel_name(root, unit.path)
    recorded = (load_symbol_durations(root).get(name)
                or load_symbol_weights(root).get(name, {}))
    shares = recorded or symbol_weight(unit.path, top_level_symbols(unit.path))
    total = sum(shares.values())
    if not total:
        return max(file_weight, 1)
    return max(file_weight * shares.get(unit.symbol, 1) // total, 1)


def pack(root: Path, shards: int) -> list[list[Path]]:
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

    # One file heavier than an even share is the floor on the critical path, so
    # the ceiling for "worth splitting" is that even share. Computed from whole
    # files first, which is the quantity the floor is measured against.
    total = sum(weight(root, f) for f in files)
    ceiling = max(total // max(shards, 1), 1)

    work: list[Unit] = []
    for f in files:
        work.extend(units_for(root, f, ceiling))

    weighted = sorted(((unit_weight(root, u), rel_name(root, u.path),
                        u.symbol or "", u) for u in work),
                      key=lambda t: (-t[0], t[1], t[2]))

    bins: list[list[Unit]] = [[] for _ in range(shards)]
    load = [0] * shards
    for w, _name, _sym, u in weighted:
        i = load.index(min(load))
        bins[i].append(u)
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
    unit = path if isinstance(path, Unit) else Unit(path)
    if is_init(unit.path):
        return None
    rel = unit.path.relative_to(root / SOURCE).with_suffix("").as_posix()
    # as_posix(), not str(): on Windows str(Path("boost_cli/core")) is
    # "boost_cli\\core", so replacing "/" would be a no-op and the pattern
    # would come out as "boost_cli\\core.lockfile.*" — matching nothing.
    dotted = "%s.%s" % (SOURCE.as_posix().replace("/", "."), rel.replace("/", "."))
    if unit.symbol is None:
        return "%s.*" % dotted
    # mutmut mangles `install` to `x_install` and `_install_rule` to
    # `x__install_rule`, then appends `__mutmut_<n>`. Anchoring on that suffix
    # rather than trailing straight off the name is what keeps `install` from
    # swallowing `install_from_path`: the next characters after the name must be
    # `__mutmut_`, which `_from_path...` is not.
    return "%s.x_%s__mutmut_*" % (dotted, unit.symbol)


def cmd_plan(args: argparse.Namespace) -> int:
    root = Path(args.root)
    bins = pack(root, args.shards)

    if args.explain:
        loads = [sum(unit_weight(root, u) for u in b) for b in bins]
        total = sum(loads)
        recorded = load_weights(root)
        split = sorted({rel_name(root, u.path) for b in bins for u in b
                        if u.symbol is not None})
        if split:
            print("split files : %s" % ", ".join(split))
        print("files       : %d" % len(source_files(root)))
        # Name the tier actually in play. Reporting "mutant counts" while
        # packing on milliseconds sends anyone reading this to the wrong file.
        durations = load_durations(root)
        if durations:
            unit = "ms"
            print("weights     : measured run time — %d files timed, %d imputed"
                  % (len(durations),
                     len([f for f in source_files(root) if not is_init(f)])
                     - len(durations)))
        elif recorded:
            unit = "mutants"
            print("weights     : %d real mutant counts from %s"
                  % (len(recorded), WEIGHTS))
        else:
            unit = "lines"
            print("weights     : lines of code (no %s yet)" % WEIGHTS)
        print("total weight: %d %s" % (total, unit))
        print("ideal shard : %d %s" % (total // args.shards, unit))
        heaviest = max(unit_weight(root, u) for b in bins for u in b)
        print("largest unit: %d  (floor on the slowest shard)" % heaviest)
        print("speedup cap : %.2fx" % (total / max(loads)))
        for i, (b, ld) in enumerate(zip(bins, loads, strict=True)):
            print("  shard %d: weight %5d, %2d units" % (i, ld, len(b)))
        return 0

    if args.index is None:
        raise SystemExit("mutation_shards plan: --index is required without --explain")
    if not 0 <= args.index < args.shards:
        raise SystemExit("mutation_shards plan: --index %d out of range for %d shards"
                         % (args.index, args.shards))
    patterns = [pattern_for(root, u) for u in bins[args.index]]
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
    # A file may now be owned by SEVERAL shards, one per function, so the owner
    # map is file -> {shards}. For a whole-file unit that set has one member and
    # the logic below reduces to what it always did.
    owner: dict[str, set] = {}
    for i, b in enumerate(bins):
        for u in b:
            owner.setdefault(rel_name(root, u), set()).add(i)

    into = Path(args.into)
    dest_dir = into / SOURCE
    dest_dir.mkdir(parents=True, exist_ok=True)

    problems: list[str] = []
    merged: list[tuple[str, int, int]] = []
    for name, shards in sorted(owner.items()):
        # Union every owning shard's results for this file. Each shard writes a
        # .meta containing EVERY key in the file — with `None` against the
        # mutants it was not asked to run — so a key is only genuinely unrun
        # when it is None in all of them. That is what makes this fail closed:
        # a function that no shard was assigned stays None everywhere and is
        # reported below, exactly as a dropped whole file already was.
        codes: dict[str, object] = {}
        extras: dict[str, dict[str, object]] = {}
        missing = []
        for shard in sorted(shards):
            src = shard_meta(Path(args.source), args.prefix, shard, name)
            if src is None:
                missing.append(shard)
                continue
            data = json.loads(src.read_text())
            for key, value in (data.get("exit_code_by_key") or {}).items():
                if codes.get(key) is None:
                    codes[key] = value
            # Carry the parallel per-key maps mutmut writes, so a merged .meta
            # is shaped exactly like an unsharded one.
            for field in ("type_check_error_by_key", "durations_by_key",
                          "estimated_durations_by_key"):
                bucket = extras.setdefault(field, {})
                for key, value in (data.get(field) or {}).items():
                    if bucket.get(key) is None:
                        bucket[key] = value
        if missing:
            problems.append("%s: no results from shard%s %s under %s/%s*"
                            % (name, "" if len(missing) == 1 else "s",
                               ", ".join(str(s) for s in missing),
                               args.source, args.prefix))
            continue
        unrun = sorted(k for k, v in codes.items() if v is None)
        if unrun:
            problems.append(
                "%s: %d/%d mutants unrun across shard(s) %s — first: %s"
                % (name, len(unrun), len(codes),
                   ", ".join(str(s) for s in sorted(shards)), unrun[0]))
            continue
        dest = dest_dir / (name + ".meta")
        dest.parent.mkdir(parents=True, exist_ok=True)
        payload = {"exit_code_by_key": codes}
        for field in ("type_check_error_by_key", "durations_by_key",
                      "estimated_durations_by_key"):
            payload[field] = extras.get(field, {})
        dest.write_text(json.dumps(payload))
        merged.append((name, len(codes), min(shards)))

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


def is_relevant(changed: list[str]) -> bool:
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
    millis: dict[str, int] = {}
    by_symbol: dict[str, dict[str, int]] = {}
    millis_by_symbol: dict[str, dict[str, int]] = {}
    for meta in sorted(src.rglob("*.py.meta")):
        data = json.loads(meta.read_text())
        codes = data.get("exit_code_by_key", {})
        if codes:
            rel = meta.relative_to(src).as_posix()
            name = rel[: -len(".meta")]
            counts[name] = len(codes)
            # Real time spent on this file, which is what the critical path is
            # made of. mutmut records per-mutant durations in SECONDS as floats
            # (measured range here: 0.24 to 7.93 per mutant); milliseconds are
            # stored so the figure survives as an int without losing the small
            # ones. A file is only time-weighted when every one of its mutants
            # has a duration, so a partial record cannot understate a file and
            # win itself extra work.
            durations = data.get("durations_by_key") or {}
            values = [v for v in durations.values()
                      if isinstance(v, (int, float)) and v >= 0]
            if len(values) == len(codes) and values:
                millis[name] = max(round(sum(values) * 1000), 1)
            # Attribute each mutant to the function it belongs to, so a split
            # file balances on measured counts rather than on body size. Keys
            # look like `boost_cli.core.store.x_install__mutmut_3`.
            tally: dict[str, int] = {}
            times: dict[str, float] = {}
            for key in codes:
                head, sep, _n = key.rpartition("__mutmut_")
                if not sep:
                    continue
                symbol = head.rsplit(".", 1)[-1]
                if not symbol.startswith("x_"):
                    continue
                symbol = symbol[2:]
                tally[symbol] = tally.get(symbol, 0) + 1
                spent = durations.get(key)
                if isinstance(spent, (int, float)) and spent >= 0:
                    times[symbol] = times.get(symbol, 0.0) + spent
            if tally:
                by_symbol[name] = tally
            # Only when every mutant of the file was timed, for the same reason
            # the file-level figure is: a partial record understates a function
            # and wins its shard extra work.
            if times and name in millis:
                millis_by_symbol[name] = {s: max(round(v * 1000), 1)
                                          for s, v in times.items()}
    if not counts:
        print("mutation_shards: no .meta results under %s — nothing to record" % src)
        return 1
    out = root / WEIGHTS
    out.write_text(json.dumps(
        {"_comment": "Advisory shard-balance hints; see scripts/mutation_shards.py. "
                     "Stale entries cost balance, never correctness.",
         "mutants_by_file": counts,
         "mutants_by_symbol": by_symbol,
         "millis_by_file": millis,
         "millis_by_symbol": millis_by_symbol},
        indent=2, sort_keys=True) + "\n")
    print("wrote %s: %d files, %d mutants, %d with per-symbol counts, "
          "%d timed, %d with per-symbol times"
          % (out, len(counts), sum(counts.values()), len(by_symbol),
             len(millis), len(millis_by_symbol)))
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
