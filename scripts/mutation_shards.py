#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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
  mutation_shards.py drift --candidate new.json # is a refresh worth a PR?
  mutation_shards.py cache-key                   # hash half of a shard's actions/cache key
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import NamedTuple, cast

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path("boost_cli/core")
WEIGHTS = Path("scripts/mutation_weights.json")

#: "No override is in force", which is a different state from "the override is
#: no file at all" — ``None`` has to stay available as a value, because that is
#: how ``drift`` compares against a checkout with no committed hints.
_UNSET = object()

#: Read the weights from here instead of ``root / WEIGHTS``, while set.
#:
#: ``drift`` has to pack the same source tree twice — once on the committed
#: hints and once on a freshly measured candidate — and score both packs
#: against the candidate. Every loader below resolves the file from ``root``,
#: so without this the only way to ask the second question would be to
#: overwrite the committed file mid-comparison: destructive in a checkout, and
#: in a test a global side effect that leaks into whatever runs next.
_WEIGHTS_OVERRIDE: Path | object | None = _UNSET


@contextlib.contextmanager
def using_weights(path: Path | None):
    """Resolve weights from ``path`` for the duration of the block.

    ``None`` means "no weights file at all", which is how the fallback tiers
    are exercised without deleting anything.

    Restores its predecessor rather than clearing, which is what a context
    manager owes its caller and not an observation about ``drift`` — measured,
    ``drift`` never reaches a depth above one. Resetting to the unset state
    would make the manager safe only at the outermost level, which is the kind
    of contract that holds until the first caller wraps it.
    """
    global _WEIGHTS_OVERRIDE
    previous = _WEIGHTS_OVERRIDE
    _WEIGHTS_OVERRIDE = path
    try:
        yield
    finally:
        _WEIGHTS_OVERRIDE = previous


def weights_path(root: Path) -> Path | None:
    """The weights file in play, or ``None`` for "there is no weights file".

    ``None`` is a value the callers already handle: a missing hints file is the
    ordinary state of a fresh checkout, so every loader below returns empty for
    it rather than raising.
    """
    if _WEIGHTS_OVERRIDE is _UNSET:
        return root / WEIGHTS
    return cast("Path | None", _WEIGHTS_OVERRIDE)


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


def _mapping(data: dict, key: str) -> dict:
    """``data[key]`` when it is a mapping, else ``{}``.

    The top-level ``isinstance(data, dict)`` check is not enough on its own:
    ``{"millis_by_file": []}`` parses, is an object, and then raises
    ``AttributeError: 'list' object has no attribute 'items'`` from inside the
    planner. ``.get(k, {})`` does not cover it either, and ``.get(k) or {}``
    covers only the falsy cases — an explicit ``null`` and an empty list, but
    not ``[1]`` or ``"x"``. Every loader goes through here so the four of them
    cannot drift apart again.
    """
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def load_weights(root: Path) -> dict[str, int]:
    """Real mutant counts, if a previous run left any. Missing file is normal."""
    path = weights_path(root)
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        # A valid JSON document that is not an object — `[]`, `null`, a bare
        # number. Only a *parse* failure was caught above, and `data.get(...)`
        # on a list raises AttributeError straight out of the planner: a crash
        # in a tier whose whole contract is that a corrupt file is survivable.
        # `_mapping` covers the same hazard one level down.
        return {}
    counts = _mapping(data, "mutants_by_file")
    return {k: int(v) for k, v in counts.items() if isinstance(v, int) and v > 0}


def load_symbol_weights(root: Path) -> dict[str, dict[str, int]]:
    """Recorded per-function mutant counts, if a previous run left any.

    Same contract as ``load_weights``: advisory, and a missing or corrupt file
    is normal rather than fatal — a stale hint costs balance, never correctness.
    """
    path = weights_path(root)
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        # A valid JSON document that is not an object — `[]`, `null`, a bare
        # number. Only a *parse* failure was caught above, and `data.get(...)`
        # on a list raises AttributeError straight out of the planner: a crash
        # in a tier whose whole contract is that a corrupt file is survivable.
        # `_mapping` covers the same hazard one level down.
        return {}
    out: dict[str, dict[str, int]] = {}
    for name, syms in _mapping(data, "mutants_by_symbol").items():
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
    path = weights_path(root)
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        # A valid JSON document that is not an object — `[]`, `null`, a bare
        # number. Only a *parse* failure was caught above, and `data.get(...)`
        # on a list raises AttributeError straight out of the planner: a crash
        # in a tier whose whole contract is that a corrupt file is survivable.
        # `_mapping` covers the same hazard one level down.
        return {}
    out: dict[str, dict[str, int]] = {}
    for name, syms in _mapping(data, "millis_by_symbol").items():
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
    path = weights_path(root)
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        # A valid JSON document that is not an object — `[]`, `null`, a bare
        # number. Only a *parse* failure was caught above, and `data.get(...)`
        # on a list raises AttributeError straight out of the planner: a crash
        # in a tier whose whole contract is that a corrupt file is survivable.
        # `_mapping` covers the same hazard one level down.
        return {}
    out = {}
    for name, ms in _mapping(data, "millis_by_file").items():
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
    millis, imputed, use_millis = _millis_basis(root)
    recorded = load_weights(root)

    def weight(root_: Path, path: Path) -> int:
        name = rel_name(root_, path)
        if use_millis:
            return millis.get(name) or imputed.get(name) or line_weight(path)
        return recorded.get(name) or line_weight(path)

    return weight


def weight_unit(root: Path) -> str:
    """``"ms"`` when :func:`weight_fn` is weighting in milliseconds, else ``""``.

    It exists so a *caller* can label a number it did not compute. `drift`
    printed every load as minutes, but a weight is only milliseconds when
    every mutatable file is covered — a candidate carrying `millis_by_file`
    and no `mutants_by_file` falls back to line counts, and the table then
    read "0 min" directly above a paragraph reporting 660. The decision lives
    in `_millis_basis` and both functions ask it, rather than being written
    out twice and drifting.
    """
    return "ms" if _millis_basis(root)[2] else ""


def _millis_basis(root: Path) -> tuple[dict[str, int], dict[str, int], bool]:
    """``(measured, imputed, use_millis)`` — the time-weighting decision."""
    millis = load_durations(root)
    files = [f for f in source_files(root) if not is_init(f)]
    recorded = load_weights(root)

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
    return millis, imputed, use_millis


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


def rel_name(root: Path, path: Path | Unit) -> str:
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


def _as_path(path: Path | Unit) -> Path:
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


def pack(root: Path, shards: int) -> list[list[Unit]]:
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
            data = json.loads(src.read_text(encoding="utf-8"))
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
        dest.write_text(json.dumps(payload), encoding="utf-8",
                        newline="\n")
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
        if found is not None and json.loads(found.read_text(encoding="utf-8")).get("exit_code_by_key"):
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
        changed = path.read_text(encoding="utf-8").splitlines()

    if not changed:
        print("true")
        return 0
    print("true" if is_relevant(changed) else "false")
    return 0


# --------------------------------------------------------------------------
# cache key: reuse a shard's mutants/ results across pushes of the same PR
# --------------------------------------------------------------------------

# Same list as RELEVANT_PREFIXES, minus boost_cli/ itself. mutmut already
# reuses a source file's own results by content hash (per the module
# docstring's "Balance without a chicken-and-egg" -- mutmut's per-source
# hashing, not re-verified locally against the 3.7.0 pin here), so keying the
# actions/cache entry on boost_cli/ too would just repeat that reuse one
# level up, at the cost of evicting every mutant in the cache -- not just the
# ones in the file that changed -- on every core edit, which is most pushes.
# What mutmut does NOT re-derive on its own is which tests ran, which
# mutmut/pytest built the recorded exit codes, and the gate's own scripts;
# any of those changing must miss the cache and pay the full run, exactly as
# `is_relevant` already says for the scope job.
CACHE_KEY_PREFIXES = tuple(p for p in RELEVANT_PREFIXES if p != "boost_cli/")
CACHE_KEY_EXACT = RELEVANT_EXACT


def cache_key_paths(root: Path) -> list[Path]:
    """Every file whose content can change a shard's cache key.

    Mirrors ``is_relevant``'s own file list, minus ``boost_cli/`` (see
    ``CACHE_KEY_PREFIXES``). A named file or directory that does not exist is
    skipped rather than raising, so a fixture repo that only sets up part of
    the tree still produces a stable key.
    """
    found: set[Path] = set()
    for name in CACHE_KEY_EXACT:
        path = root / name
        if path.is_file():
            found.add(path)
    for prefix in CACHE_KEY_PREFIXES:
        base = root / prefix
        if base.is_dir():
            found.update(f for f in base.rglob("*") if f.is_file())
        elif base.is_file():
            found.add(base)
    return sorted(found)


def cache_key_hash(root: Path) -> str:
    """A deterministic digest of every file ``cache_key_paths`` names.

    Hashes content, not mtime or git status: a checkout's timestamps are not
    reproducible across machines, but bytes are. Each file's path is folded
    in alongside its content (relative to `root`, POSIX-normalized) so a
    rename or an added/removed file changes the digest even when every
    remaining file's bytes are untouched.
    """
    digest = hashlib.sha256()
    for path in cache_key_paths(root):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def cmd_cache_key(args: argparse.Namespace) -> int:
    """Print the hash half of a mutation shard's ``actions/cache`` key.

    The workflow builds the full key itself (shard index + Python version +
    this hash) -- this script has no reason to know either of the first two,
    and folding them in here would just make the CI YAML a pass-through.
    """
    print(cache_key_hash(Path(args.root)))
    return 0


#: How much worse the committed plan may be, measured against the candidate,
#: before a refresh is worth a pull request. 1.05 is a slowest-shard 5% over
#: the best those same measurements admit — under that, the diff is churn in a
#: 60 KB generated file for a balance nobody would notice.
DRIFT_THRESHOLD = 1.05


def score(root: Path, bins: list[list[Unit]], weights: Path | None) -> list[int]:
    """What ``weights`` says each of these bins costs.

    Separating *which units a shard holds* from *what they cost* is the whole
    point of the comparison: a weights file always reports its own plan as the
    best one going, because that is what the packer optimised it for. The
    number that means anything is the stale plan scored against the measured
    truth.
    """
    with using_weights(weights):
        return [sum(unit_weight(root, u) for u in b) for b in bins]


def _spread(loads: list[int]) -> tuple[float, float]:
    """``(slowest / ideal, slowest / fastest)`` for one scored pack.

    Both are descriptive only. Neither is a verdict on staleness, because a
    current weights file still reports a makespan above the ideal whenever
    some indivisible unit outweighs an even share — which is the ordinary
    state of this repo, not a defect in the hints.

    A shard that drew no work makes the second ratio meaningless rather than
    enormous, so it is reported as infinite and the caller prints ``n/a``.
    Clamping the divisor to 1 instead turned "more shards than units" into a
    measured 300000.00x, a number that reads as a catastrophic imbalance and
    describes an empty bin.
    """
    ideal = sum(loads) / len(loads)
    low = min(loads)
    return max(loads) / ideal, (max(loads) / low) if low else math.inf


def _ratio(value: float) -> str:
    """A slowest/fastest ratio for the report, or ``n/a`` when a shard is empty."""
    return "%.2fx" % value if math.isfinite(value) else "n/a"


def _unusable(candidate: Path, was: dict[str, int], now: dict[str, int],
              present: set[str] | None = None) -> str:
    """Why this candidate must not replace the committed hints, or ``""``.

    The three tiers below are ordered by how badly they fail, and all three
    were reachable: every loader in this file treats an unreadable or
    schema-less weights file as "no weights" and returns ``{}``, which is the
    right answer for a fresh checkout and the wrong one for a file that was
    supposed to be a measurement. With both sides falling back to line counts
    the committed pack looks lopsided — it was optimised for milliseconds —
    and the comparison recommends replacing a good file with an empty one.
    """
    try:
        # JSON is UTF-8 by spec and `cmd_weights` writes it as such, so the
        # encoding is named rather than left to the locale: on a Windows
        # runner the default is cp1252, which raises UnicodeDecodeError — a
        # ValueError, so it would be caught here and reported as "not
        # readable JSON" for a file that is perfectly readable.
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return "candidate %s is not readable JSON (%s)" % (candidate, exc)
    if not isinstance(data, dict):
        return "candidate %s is not an object" % candidate
    if not now:
        return ("candidate %s records no per-file durations, so it cannot be "
                "weighed against the committed hints" % candidate)
    # Coverage must not go backwards. A run that timed fewer files than the
    # committed file did is not a newer measurement of the same thing — it is
    # a partial one, and it still packs to something the comparison scores as
    # an improvement: dropping one shard's worth of durations (63 files to 55)
    # measured 1.235 and reported `moved=true`.
    #
    # Counted over the files that STILL EXIST, which is the whole reason
    # `present` is threaded in. A plain len() comparison makes deleting a
    # module from boost_cli/core a one-way door: every later candidate
    # legitimately times one file fewer, so every later candidate is refused,
    # and the only writer that could clear the condition is the refresh this
    # guard is blocking. Latched off, permanently, with no way back but a
    # hand edit.
    if present is not None:
        was = {k: v for k, v in was.items() if k in present}
        now = {k: v for k, v in now.items() if k in present}
    if len(now) < len(was):
        return ("candidate %s times %d files where the committed hints time "
                "%d — a partial measurement, not a fresher one"
                % (candidate, len(now), len(was)))
    return ""


def _emit_drift(args: argparse.Namespace, report: str,
                moved: bool, cost: float | None) -> int:
    """Write the report everywhere it was asked for. Always returns 0.

    EVERY return path of ``cmd_drift`` goes through here, and that is the
    point. The three guard paths used to print to stdout and return, leaving
    ``--summary-md`` unwritten — while the workflow step's next command was an
    unguarded ``cat "$RUNNER_TEMP/drift.md" >> "$GITHUB_STEP_SUMMARY"``. As the
    last command in the step, its exit status IS the step's: a missing file
    turned "keeping the committed hints", a *designed* outcome, into a red job
    on `main`. The same change had just added this workflow to
    ci-failure-issue.yml's watch list, so it would also have filed an issue —
    for a workflow whose header says "A FAILURE HERE BLOCKS NOTHING".

    Writing the reason into the step summary is the other half: it is what a
    maintainer reads to find out why no PR appeared, and stdout alone is
    buried in a collapsed log group.
    """
    # `newline="\n"` as well as the encoding, and for the same class of
    # reason: text mode translates "\n" to the platform separator on write, so
    # on a Windows runner the file would hold CRLF while `sys.stdout.write`
    # below emits LF, and the artifact a maintainer reads would differ byte for
    # byte from the log beside it. These two are one report written twice, so
    # they must agree; `$GITHUB_OUTPUT` is parsed line by line and has no
    # reason to carry a carriage return either.
    if args.summary_md:
        Path(args.summary_md).write_text(report, encoding="utf-8", newline="\n")
    sys.stdout.write(report)
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8", newline="\n") as fh:
            fh.write("moved=%s\n" % ("true" if moved else "false"))
            if cost is not None:
                fh.write("makespan=%.3f\n" % cost)
    return 0


def cmd_drift(args: argparse.Namespace) -> int:
    """Has the committed balance hint decayed enough to be worth replacing?

    Advisory like everything else in this file, so it never fails: it answers
    the question and leaves the decision to whoever reads it.

    The comparison is deliberately asymmetric. Both packs are scored against
    the CANDIDATE's weights, because the candidate is the measurement and the
    committed file is the belief being tested. Scoring each plan against its
    own weights would compare two self-reports and always find them equal.
    """
    root = Path(args.root)
    candidate = Path(args.candidate)
    if not candidate.exists():
        return _emit_drift(
            args,
            "mutation_shards: no candidate at %s — nothing to compare\n"
            % candidate, moved=False, cost=None)

    committed = weights_path(root)
    with using_weights(committed):
        old_bins = pack(root, args.shards)
        was = load_durations(root)
    with using_weights(candidate):
        new_bins = pack(root, args.shards)
        now = load_durations(root)

    # Refuse before comparing, because every loader here treats an unreadable
    # or schema-less file as "no weights" and returns {} — so a corrupt
    # candidate scores BOTH packs on line counts, the committed pack is
    # genuinely lopsided in that unit, and `moved` comes back true. Measured
    # on the real 66-file tree: `{not json`, `{}` and `[]` each reported a
    # refresh "worth it" at 1.438, and a file carrying only `mutants_by_file`
    # at 1.588 — which the workflow would then commit over the real
    # measurements. A
    # balance hint is advisory, but replacing a good one with an empty one is
    # not an advisory outcome.
    present = {rel_name(root, f) for f in source_files(root) if not is_init(f)}
    why = _unusable(candidate, was, now, present)
    if why:
        return _emit_drift(
            args,
            "mutation_shards: %s — keeping the committed hints\n" % why,
            moved=False, cost=None)

    old = score(root, old_bins, candidate)
    new = score(root, new_bins, candidate)
    old_makespan, old_ratio = _spread(old)
    new_makespan, new_ratio = _spread(new)

    # The verdict is the two plans against EACH OTHER, not either against a
    # flat ideal. A perfectly current weights file still scores above 1.0
    # whenever an indivisible unit is heavier than an even share, so flooring
    # the absolute number declared a refresh "worth it" on weights that had
    # not drifted at all. `test_identical_weights_do_not_move` is that case:
    # its two weights files are byte-identical and the best pack its own
    # measurements admit still reads 1.200 against a flat ideal, comfortably
    # over the 1.05 floor. The stale plan beside it reads 1.800, and the
    # ratio between the two — 1.5 — is what actually separates them.
    cost = max(old) / max(max(new), 1)
    moved = cost >= args.threshold

    added = sorted(set(now) - set(was))
    gone = sorted(set(was) - set(now))

    # A load is only minutes when the candidate's weights put EVERY mutatable
    # file in milliseconds; otherwise `weight_fn` is counting mutants or lines
    # and "min" is a lie. The table read "0 min" above a paragraph reporting
    # 660 min for a candidate carrying `millis_by_file` and no
    # `mutants_by_file`, because the imputation rate needs both.
    with using_weights(candidate):
        in_millis = weight_unit(root) == "ms"

    def load(value: int) -> str:
        return "%.0f min" % (value / 60000.0) if in_millis else "%d units" % value

    def minutes(ms: int) -> float:
        return ms / 60000.0

    lines = [
        "| plan built from | slowest shard | fastest shard | slowest/fastest | slowest/ideal |",
        "| --- | --- | --- | --- | --- |",
        "| committed `%s` | %s | %s | %s | %.3f |"
        % (WEIGHTS.as_posix(), load(max(old)), load(min(old)),
           _ratio(old_ratio), old_makespan),
        "| the candidate | %s | %s | %s | %.3f |"
        % (load(max(new)), load(min(new)), _ratio(new_ratio), new_makespan),
        "",
        "Both rows are scored against the **candidate's** measured times. The "
        "second is the best split those measurements admit — not necessarily "
        "1.000, because a unit heavier than an even share is a floor on the "
        "slowest shard no packer can get under. The number that decides is the "
        "ratio between them: the committed plan costs **%.3fx** the measured "
        "best." % cost,
        "",
        "Recorded total: %.0f min committed, %.0f min measured (%s), over "
        "%d timed files against %d."
        % (minutes(sum(was.values())), minutes(sum(now.values())),
           ("%+.0f%%" % (100.0 * (sum(now.values()) / sum(was.values()) - 1.0))
            if sum(was.values()) else "no committed total to compare"),
           len(was), len(now)),
    ]
    if added:
        lines.append("")
        lines.append("Files measured for the first time: %s." % ", ".join(
            "`%s`" % f for f in added))
    if gone:
        lines.append("")
        lines.append("Files no longer measured: %s." % ", ".join(
            "`%s`" % f for f in gone))

    lines.append("")
    lines.append("verdict: %s (threshold %.2f)"
                 % ("refresh is worth it" if moved else "close enough, no PR",
                    args.threshold))
    return _emit_drift(args, "\n".join(lines) + "\n", moved=moved, cost=cost)


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
        data = json.loads(meta.read_text(encoding="utf-8"))
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
    # `--out` exists because the obvious way to get the data somewhere else is
    # a trap: this subcommand writes the file IN PLACE and prints only a
    # summary, so `weights --source mutants > new.json` overwrites the
    # committed hints and puts the summary line — not the data — in new.json.
    #
    # An empty `--out` is refused rather than treated as absent. `--out ""` is
    # what an unset shell variable expands to (`--out "$OUT"`), and falling
    # back to the default there overwrites the committed hints — precisely the
    # accident the flag was added to prevent, now with the user believing they
    # had redirected it.
    if args.out is not None and not args.out.strip():
        print("mutation_shards: --out was given an empty path; refusing to "
              "fall back to %s" % (root / WEIGHTS))
        return 1
    out = Path(args.out) if args.out else root / WEIGHTS
    out.write_text(json.dumps(
        {"_comment": "Advisory shard-balance hints; see scripts/mutation_shards.py. "
                     "Stale entries cost balance, never correctness.",
         "mutants_by_file": counts,
         "mutants_by_symbol": by_symbol,
         "millis_by_file": millis,
         "millis_by_symbol": millis_by_symbol},
        indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
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
    w.add_argument("--out", help="write the hints here instead of in place "
                                 "(a plain `> file` captures the summary, not the data)")
    w.set_defaults(func=cmd_weights)

    d = sub.add_parser("drift", help="is the committed balance hint worth replacing?")
    d.add_argument("--candidate", required=True,
                   help="a freshly measured mutation_weights.json to compare against")
    d.add_argument("--shards", type=int, default=6)
    d.add_argument("--threshold", type=float, default=DRIFT_THRESHOLD,
                   help="slowest-shard cost over the measured best, above which "
                        "a refresh is worth a pull request (default: %(default)s)")
    d.add_argument("--summary-md", help="also write the Markdown report here")
    d.add_argument("--github-output",
                   help="append `moved=` and `makespan=` to this file ($GITHUB_OUTPUT)")
    d.set_defaults(func=cmd_drift)

    k = sub.add_parser("cache-key", help="hash half of a shard's actions/cache key")
    k.set_defaults(func=cmd_cache_key)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
