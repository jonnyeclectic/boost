#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Which boost_cli/core functions did a PR change, and what forces a full mutation run?

The diff-scoped mutation gate mutates only the functions a PR touched plus their
direct callers. "Touched" is decided with mutmut's own per-function hash
(`compute_function_hashes`), not a line diff, so a comment or blank-line edit is
not a change and a method edit uses the same mangled name (`xǁClassǁmethod`)
that mutmut keys its mutants by.

Scope covers function bodies only: an edit to module-level code (a constant, an
import) names no function and so adds nothing; the nightly full run is the
backstop for those.

The scope functions are pure: the caller supplies file text through
`read(rev, path)` and the dependency map from `mutants/mutmut-stats.json`.
`mutation_plan.py diff` is that caller; it packs the scope with
`pack_functions` and names every mutant a shard runs exactly, as
`mutant_names` lists them, so no cached verdict is ever trusted.

Two CLIs read the shards' results back:

  mutation_diff.py gate --plan PLAN --source DIR --prefix mutation-diff-shard-
                        [--min 80] [--small 10] [--root ROOT]
      Score the diff set: exit 0 pass, 1 fail, 2 unrun or missing results.
      The required `mutation` check on a pull request or merge-queue entry.
  mutation_diff.py compare --plan PLAN --full-source DIR --diff-source DIR
      Per-mutant agreement between a full run and a diff run of the same SHA;
      exit 1 on any killed/not-killed disagreement (timeouts excluded). A
      manual tool: ci.yml ran it on every PR while the diff gate was in shadow,
      as the evidence for letting it bind, and no longer runs it. It is how to
      re-check that evidence -- for example a nightly's full shards against a
      diff run of the same SHA (without a `full` set in the plan, it scores
      whatever full shards it finds under --full-source).
"""

from __future__ import annotations

import argparse
import ast
import configparser
import contextlib
import importlib.util
import json
import math
import os
import re
import sys
import tomllib
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

# mutmut is imported inside the functions that use it, never here. The unit
# suite loads this module in every `tests` cell, and those install
# requirements/test-tools.txt, which has PyYAML but not mutmut: a module-level
# import made the whole test file a collection error there. Plan validation,
# packing, scoring arithmetic and the full-run triggers need only the stdlib
# and PyYAML; the tests that reach mutmut skip without it, and run in
# `mutation-plan`, whose venv is requirements/mutation-tools.txt.

ROOT = Path(__file__).resolve().parent.parent


def _load_shards():
    """Import ``mutation_shards`` from beside this file (``scripts/`` is no package)."""
    spec = importlib.util.spec_from_file_location(
        "mutation_shards", Path(__file__).resolve().parent / "mutation_shards.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load mutation_shards.py beside %s" % __file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ms = _load_shards()

CORE_DIR = "boost_cli/core"
# Specific parse failures only; a bare except would hide real bugs. ValueError is
# the non-mapping `jobs` case raised above.
_PARSE_ERRORS = (
    configparser.Error,
    tomllib.TOMLDecodeError,
    yaml.YAMLError,
    ValueError,
)
CI_YML = ".github/workflows/ci.yml"
#: File names that change how every test runs, wherever they sit: a conftest,
#: and each config file pytest's rootdir search accepts besides pyproject.toml
#: and setup.cfg (which have their own, table-level triggers below).
PYTEST_FILES = ("conftest.py", "pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml")
#: The test tree's shared support: imported by conftest.py or by tests across
#: the suite, so an edit reaches every test the way a conftest edit does.
TEST_SUPPORT = PurePosixPath("tests")
TEST_FIXTURE_BUILDER = "tests/make_fixture.py"


def changed_functions(base_src: str | None, head_src: str | None) -> set[str]:
    """Mangled keys new in head, or whose AST hash differs. Deleted ones are excluded."""
    if head_src is None:
        return set()
    from mutmut.mutation.file_mutation import compute_function_hashes

    head = compute_function_hashes(head_src)
    base = compute_function_hashes(base_src) if base_src is not None else {}
    return {k for k, h in head.items() if base.get(k) != h}


def qualify(path: str, mangled: str) -> str:
    """`boost_cli/core/store.py`, `x_install` -> `boost_cli.core.store.x_install`."""
    return ".".join(PurePosixPath(path).with_suffix("").parts) + "." + mangled


def direct_callers(deps: dict[str, list[str]], funcs: set[str]) -> set[str]:
    """Union of `deps[f]` (mutmut: callee key -> caller values), minus `funcs`.

    Real stats keys are already qualified the way `qualify` writes them, e.g.
    `boost_cli.core.config.x__cached` -> [`boost_cli.core.config.x_get`, ...].
    """
    out: set[str] = set()
    for f in funcs:
        out.update(deps.get(f, ()))
    return out - funcs


def _mutmut_section(text: str | None) -> dict[str, str] | None:
    if text is None:
        return None
    cp = configparser.ConfigParser(interpolation=None)
    cp.read_string(text)
    return dict(cp["mutmut"]) if cp.has_section("mutmut") else None


def _toml_table(text: str | None, *keys: str):
    """`text`'s table at `keys`, None when absent; ValueError when a step is no table.

    A `tool` or `tool.pytest` that is a string or a number would otherwise
    raise AttributeError out of the planner; it is an unparsable config, and
    `full_run_reasons` says so.
    """
    if text is None:
        return None
    node: Any = tomllib.loads(text)
    for key in keys:
        if not isinstance(node, dict):
            raise ValueError("pyproject.toml: %s is not a table" % ".".join(keys))
        node = node.get(key)
        if node is None:
            return None
    return node


def _pytest_table(text: str | None):
    return _toml_table(text, "tool", "pytest", "ini_options")


def _pytest_native_table(text: str | None):
    # pytest 9 reads its options from [tool.pytest] itself (native TOML
    # types), beside the older [tool.pytest.ini_options]; compared without
    # that subtable, which has its own trigger and label -- so a table holding
    # ini_options alone reads as absent, not as an empty [tool.pytest].
    table = _toml_table(text, "tool", "pytest")
    if not isinstance(table, dict):
        return table
    return {k: v for k, v in table.items() if k != "ini_options"} or None


def _mutmut_table(text: str | None):
    # mutmut 3.8.0 (configuration.py) returns [tool.mutmut] when the table
    # exists and then never reads setup.cfg, so it is the same trigger as
    # setup.cfg [mutmut]: a `do_not_mutate` added here narrows every run,
    # the nightly's included.
    return _toml_table(text, "tool", "mutmut")


def _mutation_jobs(text: str | None):
    if text is None:
        return None
    jobs = (yaml.safe_load(text) or {}).get("jobs") or {}
    if not isinstance(jobs, dict):
        raise ValueError("ci.yml `jobs` is not a mapping")
    return {k: v for k, v in jobs.items() if k.startswith("mutation")}


def full_run_reasons(
    changed_paths: list[str], read: Callable[[str, str], str | None]
) -> list[str]:
    """Changed files that change how every mutant is run; empty means no trigger.

    Also the changes the diff scope cannot see and would otherwise pass with
    0 shards: a file in a subpackage of boost_cli/core (mutmut's source_paths
    is recursive, the scope reads boost_cli/core/*.py only); any conftest.py
    or pytest config file (`PYTEST_FILES`), each of which changes how every
    test runs, the reason [tool.pytest.ini_options] and [tool.pytest] are
    triggers; and the test tree's shared support, `tests/_*.py` and
    `tests/make_fixture.py`, which reach every test the way a conftest does.
    """
    reasons: list[str] = []
    for p in changed_paths:
        name = PurePosixPath(p)
        if name.name in PYTEST_FILES:
            reasons.append(f"{p} changed")
            continue
        if p == TEST_FIXTURE_BUILDER or (
            name.parent == TEST_SUPPORT and name.name.startswith("_") and name.suffix == ".py"
        ):
            reasons.append(f"test support changed: {p}")
            continue
        if (name.suffix == ".py" and PurePosixPath(CORE_DIR) in name.parents
                and str(name.parent) != CORE_DIR):
            reasons.append(f"core subpackage file changed: {p}")
            continue
        if _is_core_module(p):
            # compute_function_hashes swallows SyntaxError and returns {}, which
            # would read as "no function changed" and fail open. Say so instead.
            for rev in ("base", "head"):
                src = read(rev, p)
                if src is None:
                    continue
                try:
                    ast.parse(src)
                except (SyntaxError, ValueError):
                    reasons.append(f"unparsable source: {p} ({rev})")
            continue
        try:
            if p == "setup.cfg":
                hit = _mutmut_section(read("base", p)) != _mutmut_section(
                    read("head", p)
                )
                found = ["setup.cfg [mutmut] changed"] if hit else []
            elif p == "requirements/mutation-tools.txt" or (
                name.parent == PurePosixPath("scripts")
                and name.name.startswith("mutation_")
                and name.suffix == ".py"
            ):
                found = [f"{p} changed"]
            elif p == CI_YML:
                hit = _mutation_jobs(read("base", p)) != _mutation_jobs(read("head", p))
                found = ["ci.yml jobs.mutation* changed"] if hit else []
            elif p == "pyproject.toml":
                base, head = read("base", p), read("head", p)
                found = [
                    f"pyproject.toml [{table}] changed"
                    for table, of in (("tool.pytest.ini_options", _pytest_table),
                                      ("tool.pytest", _pytest_native_table),
                                      ("tool.mutmut", _mutmut_table))
                    if of(base) != of(head)
                ]
            else:
                continue
        except _PARSE_ERRORS:
            found = [f"{p} unparsable"]
        reasons.extend(found)
    return reasons


def _is_core_module(p: str) -> bool:
    pp = PurePosixPath(p)
    return (
        str(pp.parent) == CORE_DIR and pp.suffix == ".py" and pp.name != "__init__.py"
    )


def changed_scope(
    changed_paths: list[str], read: Callable[[str, str], str | None]
) -> set[str]:
    """Qualified functions of boost_cli/core/*.py new or changed at head.

    The half of the scope that needs no stats; deleted ones are excluded.
    """
    funcs: set[str] = set()
    for p in changed_paths:
        if _is_core_module(p):
            funcs |= {
                qualify(p, k)
                for k in changed_functions(read("base", p), read("head", p))
            }
    return funcs


def diff_scope(
    changed_paths: list[str],
    read: Callable[[str, str], str | None],
    deps: dict[str, list[str]],
) -> list[str]:
    """Sorted qualified changed functions plus their direct callers."""
    funcs = changed_scope(changed_paths, read)
    return sorted(funcs | direct_callers(deps, funcs))


# --------------------------------------------------------------------------
# Counting and packing (the planner's half)
# --------------------------------------------------------------------------

#: What mutmut appends to a mangled function name to name one of its mutants.
MUTANT_SEP = "__mutmut_"
#: Mutants per diff shard, and the most diff shards one run may ask for.
PER_SHARD = 1500
MAX_SHARDS = 16
#: The most mutant names one diff shard may pass to `mutmut run`. A hard cap,
#: where PER_SHARD is only the sizing target: packing balances measured time,
#: so without it one cheap-per-mutant bin could take far more names than
#: PER_SHARD. The longest name in boost_cli/core today is 72 bytes, so 1500
#: of them is ~110 KB of argv against a Linux runner's 2 MB ARG_MAX. It also
#: bounds mutmut's own filter, which fnmatches every key of every file against
#: every name it was given: 1500 names x 51,182 keys measured 12.3 s.
MAX_NAMES = 1500
#: One exact mutant name: `<qualified>__mutmut_<n>`, all on one line.
_MUTANT_NAME = re.compile(r"[^\r\n]+%s[1-9][0-9]*" % re.escape(MUTANT_SEP))


def split_qualified(qualified: str) -> tuple[str, str]:
    """`boost_cli.core.store.xǁA.Bǁm` -> (`boost_cli/core/store.py`, `xǁA.Bǁm`).

    The inverse of `qualify`. A plain `rpartition(".")` would cut a nested
    class's key (`xǁA.Bǁm`) in half, so a method key splits on its `.xǁ`.
    """
    i = qualified.find(".x" + ms.METHODS)
    if i >= 0:
        module, mangled = qualified[:i], qualified[i + 1 :]
    else:
        module, _, mangled = qualified.rpartition(".")
    return module.replace(".", "/") + ".py", mangled


@contextlib.contextmanager
def mutmut_config(root: Path) -> Iterator[None]:
    """Load mutmut's config from `root`'s setup.cfg for the duration, then put back.

    `mutate_file_contents` reads `config().do_not_mutate_patterns`, and mutmut
    caches its config process-wide from whatever cwd the first call ran in —
    outside a directory with a `[mutmut]` section it raises instead. The
    previous config is restored because the unit suite also runs *inside*
    mutmut, where that global belongs to the run doing the mutating.
    """
    from mutmut import configuration as mutmut_configuration
    from mutmut.utils.file_utils import change_cwd

    previous = mutmut_configuration._config
    mutmut_configuration._config = None
    try:
        with change_cwd(root):
            mutmut_configuration.config()
        yield
    finally:
        mutmut_configuration._config = previous


def mutant_names(path: str, src: str) -> dict[str, list[str]]:
    """Mangled function -> the exact names of the mutants mutmut generates for it.

    mutmut's own generator, so the names are the keys `mutmut run` will
    produce for the same source and config (call under `mutmut_config`), each
    qualified the way mutmut keys its results (`qualify`). A function with
    nothing to mutate (`pass`) is absent, not an empty list.

    The shards pass these names, not a `<function>__mutmut_*` glob: mutmut
    picks the clean run's tests by looking each name's function up in
    `tests_by_mangled_function_name`, and a glob is fnmatched against those
    keys -- which carry no `__mutmut_` suffix, so it matches none and the clean
    run falls back to the whole unit suite (mutmut 3.8.0,
    `tests_for_mutant_names`).
    """
    from mutmut.mutation.file_mutation import mutate_file_contents

    out: dict[str, list[str]] = {}
    for name in mutate_file_contents(path, src).mutant_names:
        head, sep, _ = name.rpartition(MUTANT_SEP)
        if sep:
            out.setdefault(head, []).append(qualify(path, name))
    return out


def mutant_counts(path: str, src: str) -> dict[str, int]:
    """Mangled function -> number of mutants mutmut generates for it (see `mutant_names`)."""
    return {f: len(names) for f, names in mutant_names(path, src).items()}


def ms_per_mutant(root: Path, functions: list[str]) -> dict[str, float]:
    """Measured milliseconds per mutant for the functions a previous run timed.

    `mutation_weights.json` records a function's total time and its mutant
    count from the same full run, so the ratio is that run's per-mutant cost —
    which ranges 14x across one file (see `load_symbol_durations`). Methods are
    not recorded there and fall back to the mean in `pack_functions`.
    """
    durations = ms.load_symbol_durations(root)
    recorded = ms.load_symbol_weights(root)
    out: dict[str, float] = {}
    for q in functions:
        path, mangled = split_qualified(q)
        if not mangled.startswith("x_"):
            continue
        try:
            rel = PurePosixPath(path).relative_to(CORE_DIR).as_posix()
        except ValueError:
            continue
        spent = durations.get(rel, {}).get(mangled[2:])
        count = recorded.get(rel, {}).get(mangled[2:])
        if spent and count:
            out[q] = spent / count
    return out


def pack_functions(
    counts: dict[str, int],
    ms_per_mutant: dict[str, float],
    per_shard: int = PER_SHARD,
    cap: int = MAX_SHARDS,
    max_names: int = MAX_NAMES,
) -> list[list[str]]:
    """Pack qualified functions into `min(cap, ceil(total / per_shard))` shards.

    Longest-processing-time first on `count * ms_per_mutant` (the mean for an
    unmeasured function), ties broken by name, so the same scope always packs
    the same way. A bin can come back empty when one function outweighs the
    shard size — a function cannot be split — and the planner drops those.

    A function goes only to a bin it fits in by mutant count (`max_names`,
    or any empty bin); when none has room a bin is added, up to `cap`. Past
    `cap` it goes to the least-loaded bin regardless, and that bin is over
    `max_names` -- which the planner refuses, rather than hand a shard more
    names than its argv was sized for.
    """
    live = {f: n for f, n in counts.items() if n > 0}
    total = sum(live.values())
    if total == 0:
        return []
    k = min(cap, math.ceil(total / per_shard))
    mean = (sum(ms_per_mutant.values()) / len(ms_per_mutant)) if ms_per_mutant else 1.0
    weight = {f: n * ms_per_mutant.get(f, mean) for f, n in live.items()}
    bins: list[list[str]] = [[] for _ in range(k)]
    load = [0.0] * k
    size = [0] * k
    for f in sorted(live, key=lambda f: (-weight[f], f)):
        n = live[f]
        room = [i for i in range(len(bins)) if not bins[i] or size[i] + n <= max_names]
        if not room and len(bins) < cap:
            bins.append([])
            load.append(0.0)
            size.append(0)
            room = [len(bins) - 1]
        i = min(room or range(len(bins)), key=lambda i: (load[i], i))
        bins[i].append(f)
        load[i] += weight[f]
        size[i] += n
    return bins


# --------------------------------------------------------------------------
# Scoring (the gate's half)
# --------------------------------------------------------------------------


@dataclass
class Verdict:
    killed: int
    denominator: int
    unrun: list[str] = field(default_factory=list)
    survivors: list[str] = field(default_factory=list)
    timeouts: list[str] = field(default_factory=list)


def status_of(code: int | None) -> str:
    """mutmut's status name for an exit code, without growing its defaultdict.

    Indexing `status_by_exit_code` with an unknown code inserts it; reading the
    factory instead gives the same answer ("suspicious") and leaves mutmut's
    table as it was.
    """
    from mutmut.stats import status_by_exit_code

    if code in status_by_exit_code:
        return status_by_exit_code[code]
    factory = status_by_exit_code.default_factory
    return factory() if factory is not None else "suspicious"


def score(codes: dict[str, int | None]) -> Verdict:
    """Count exactly as `mutation_gate.py` does: killed / (total - skipped).

    `mutation_gate.py` scores mutmut's export-cicd-stats, where `killed` is the
    `"killed"` status alone (exit 1 and 3) and the denominator is every mutant
    but the `"skipped"` ones (34). So no tests (5/33), suspicious, timeouts,
    segfaults and `caught by type check` (37) all count against the score.
    The one deliberate difference: a `None` ("not checked") is not scored at
    all but reported as unrun, and `passes` fails closed on it.
    """
    v = Verdict(killed=0, denominator=0)
    for key in sorted(codes):
        code = codes[key]
        if code is None:
            v.unrun.append(key)
            continue
        status = status_of(code)
        if status == "skipped":
            continue
        v.denominator += 1
        if status == "killed":
            v.killed += 1
        elif status == "survived":
            v.survivors.append(key)
        elif status == "timeout":
            v.timeouts.append(key)
    return v


def passes(v: Verdict, min_pct: float = 80.0, small: int = 10) -> bool:
    """>= `min_pct` killed; below `small` mutants, every one must be killed.

    The small rule exists because one equivalent mutant out of three reads as
    66.7%. Nothing to score (zero denominator, nothing unrun) is a pass.
    """
    if v.unrun:
        return False
    if v.denominator == 0:
        return True
    if v.denominator < small:
        return v.killed == v.denominator
    return 100 * v.killed >= min_pct * v.denominator


def def_line(src: str, mangled: str) -> int | None:
    """Line of the `def` that mutmut keys as `mangled`, walking as mutmut does."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    from mutmut.mutation.trampoline_templates import mangle_function_name

    def visit(stmts: list[ast.stmt], class_name: str) -> int | None:
        for node in stmts:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                key = mangle_function_name(name=node.name, class_name=class_name or None)
                if key == mangled:
                    return node.lineno
            elif isinstance(node, ast.ClassDef):
                found = visit(
                    node.body,
                    node.name if not class_name else f"{class_name}.{node.name}",
                )
                if found is not None:
                    return found
        return None

    return visit(tree.body, "")


def _core_rel(path: str) -> str:
    """`boost_cli/core/store.py` -> `store.py`, the name `shard_meta` takes."""
    return PurePosixPath(path).relative_to(CORE_DIR).as_posix()


def _read_codes(meta: Path) -> dict[str, Any]:
    return json.loads(meta.read_text(encoding="utf-8")).get("exit_code_by_key") or {}


def function_of(name: str) -> str:
    """`boost_cli.core.m.x_a__mutmut_3` -> `boost_cli.core.m.x_a`."""
    return name.rpartition(MUTANT_SEP)[0]


def _functions_of(shards: list[list[str]]) -> list[str]:
    """Every function the shards run, once each, in the order first named."""
    return list(dict.fromkeys(function_of(n) for shard in shards for n in shard))


def _count(value: Any) -> bool:
    # `True` is an int to isinstance; a count of True is a bug, not a 1.
    return isinstance(value, int) and not isinstance(value, bool)


def validate_plan(plan: Any) -> tuple[dict[str, Any] | None, list[str]]:
    """The plan's `diff` set if it is well-formed, else every way it is not.

    Scoring trusts this shape completely, and every malformed shape it used
    to accept scored as a pass: `{}` and `shards: null` read as an empty
    scope, and a `mutants` that is not an integer switched off the only check
    that notices a shard which ran part of a function (1 of N keys present
    scored 1/1 killed, PASS). So nothing is scored until all of it holds:

    * `shards` is a list of non-empty lists of exact mutant names,
      `<qualified>__mutmut_<n>` (an empty shard is one the planner never
      emits, see mutation_plan.py), no name twice and every function's names
      in one shard, since the gate reads a function from that shard alone;
    * `mutants` is an int >= 0, and is 0 exactly when there are no shards, so
      a `0` can't make the shortfall check vacuous;
    * `functions` is a list of strings;
    * `counts` maps exactly the shards' functions to positive ints, each the
      number of names the shards carry for it, that sum to `mutants`.
      Required, because the planner always writes it, and without it a total
      alone would let one function's shortfall hide behind another's surplus.
    """
    if not isinstance(plan, dict):
        return None, ["the plan is not a JSON object"]
    sets = plan.get("sets")
    if not isinstance(sets, dict):
        return None, ["`sets` is not an object"]
    if "diff" not in sets:
        return None, ["the plan has no `sets.diff` to score"]
    spec = sets["diff"]
    if not isinstance(spec, dict):
        return None, ["`sets.diff` is not an object"]

    problems: list[str] = []
    shards = spec.get("shards")
    shards_ok = isinstance(shards, list)
    owner: dict[str, int] = {}  # function -> the one shard that runs it
    named: dict[str, int] = {}  # function -> how many of its mutants are named
    seen: set[str] = set()
    if not shards_ok:
        problems.append(f"`shards` is {shards!r}, not a list")
    else:
        for i, shard in enumerate(shards):
            if not isinstance(shard, list) or not shard:
                problems.append(f"shard {i} is {shard!r}, not a non-empty list")
                shards_ok = False
                continue
            for name in shard:
                if not isinstance(name, str) or not _MUTANT_NAME.fullmatch(name):
                    problems.append(f"shard {i}: {name!r} is not an exact mutant name")
                    shards_ok = False
                    continue
                if name in seen:
                    problems.append(f"shard {i}: {name} is named twice")
                    shards_ok = False
                    continue
                seen.add(name)
                q = function_of(name)
                if owner.setdefault(q, i) != i:
                    problems.append(f"shard {i}: {q} is split across shards {owner[q]} and {i}")
                    shards_ok = False
                named[q] = named.get(q, 0) + 1

    mutants = spec.get("mutants")
    if not _count(mutants) or mutants < 0:
        problems.append(f"`mutants` is {mutants!r}, not an integer >= 0")
    elif isinstance(shards, list) and (mutants == 0) != (not shards):
        problems.append(f"`mutants` is {mutants} but {len(shards)} shards are planned")

    functions = spec.get("functions")
    if not isinstance(functions, list) or not all(isinstance(f, str) for f in functions):
        problems.append(f"`functions` is {functions!r}, not a list of strings")

    if "counts" not in spec:
        problems.append("`counts` is missing (the planner always writes it)")
    else:
        counts = spec["counts"]
        if not isinstance(counts, dict) or not all(
            isinstance(k, str) and _count(v) and v > 0 for k, v in counts.items()
        ):
            problems.append("`counts` is not an object of positive integers")
        elif shards_ok and set(counts) != set(named):
            problems.append("`counts` names different functions than the shards run")
        elif shards_ok and any(counts[q] != named[q] for q in counts):
            problems.append("`counts` disagrees with the names the shards run: " + ", ".join(
                f"{q} counted {counts[q]}, named {named[q]}"
                for q in sorted(counts) if counts[q] != named[q]))
        elif _count(mutants) and sum(counts.values()) != mutants:
            problems.append(
                f"`counts` sums to {sum(counts.values())}, but `mutants` is {mutants}"
            )
    return (None if problems else spec), problems


def collect_diff(
    spec: dict[str, Any], source: Path, prefix: str
) -> tuple[dict[str, int | None], list[str]]:
    """In-scope exit codes from the diff shards, and every reason they are incomplete.

    Each function belongs to exactly one shard (the planner packed it there),
    so its mutants are read from that shard's `.meta` only: every other shard
    reports them `None`, having been asked to run something else. Exactly the
    names the plan lists are read, so out-of-scope functions of the same file
    -- `None` in every diff shard -- never are.

    Per function, the shard's keys must be exactly the planned names. One
    missing is a mutant never run. One extra is a mutant mutmut generated that
    the planner never named, so the shard did not run it either: the planner
    and the shard disagree about the function, and its score would be a
    subset's. A total alone hides one function's shortfall behind another's
    surplus, so both checks are per function.

    `spec` must have passed `validate_plan`.
    """
    codes: dict[str, int | None] = {}
    problems: list[str] = []
    for index, shard in enumerate(spec["shards"]):
        if not (source / f"{prefix}{index}").is_dir():
            problems.append(f"shard {index}: no artifact at {source}/{prefix}{index}")
            continue
        planned: dict[str, list[str]] = {}
        for name in shard:
            planned.setdefault(function_of(name), []).append(name)
        for q, names in planned.items():
            path, _ = split_qualified(q)
            meta = ms.shard_meta(source, prefix, index, _core_rel(path))
            if meta is None:
                problems.append(f"shard {index}: no {path}.meta for {q}")
                continue
            held = {
                k: v for k, v in _read_codes(meta).items() if k.startswith(q + MUTANT_SEP)
            }
            if not held:
                problems.append(f"shard {index}: no mutants of {q} (planned, never run)")
                continue
            missing = [n for n in names if n not in held]
            extra = sorted(set(held) - set(names))
            if missing:
                problems.append(
                    f"{q}: planner counted {len(names)} mutants; shards hold "
                    f"{len(names) - len(missing)} of them, missing {', '.join(missing[:3])}"
                )
            if extra:
                problems.append(
                    f"{q}: shard {index} holds {len(extra)} mutants the planner never "
                    f"named: {', '.join(extra[:3])}"
                )
            codes.update({n: held[n] for n in names if n in held})
    # Implied by the per-function checks above; kept so the plan's own total
    # is checked against what was read, whatever the shards' layout.
    if len(codes) < spec["mutants"]:
        problems.append(
            f"planner counted {spec['mutants']} mutants; shards hold {len(codes)}"
        )
    return codes, problems


def _escape(message: str) -> str:
    """Workflow-command *data* escaping, for anything printed that a PR controls.

    Mutant keys and paths come from PR-controlled file names. Unescaped, a
    newline in one starts a new stdout line, which the runner would read as a
    workflow command of the PR's choosing.
    """
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    """Workflow-command *property* escaping: data escaping plus `:` and `,`.

    Without it a core file named `a,line=9.py` rewrites the annotation's own
    `line=` property.
    """
    return _escape(value).replace(":", "%3A").replace(",", "%2C")


def cmd_gate(args: argparse.Namespace) -> int:
    spec, invalid = validate_plan(json.loads(Path(args.plan).read_text(encoding="utf-8")))
    if spec is None:
        print("mutation diff gate: INCOMPLETE — malformed plan, refusing to score:")
        for p in invalid:
            print(f"  - {_escape(p)}")
        return 2
    codes, problems = collect_diff(spec, Path(args.source), args.prefix)
    v = score(codes)
    lost = {
        k: status_of(c)
        for k, c in sorted(codes.items())
        if c is not None and status_of(c) not in ("killed", "skipped")
    }
    pct = 100.0 * v.killed / v.denominator if v.denominator else 100.0
    line = (
        "mutation diff gate: %d/%d killed (%.1f%%) over %d functions — "
        "survived %d, timeout %d, other unkilled %d, unrun %d"
        % (
            v.killed,
            v.denominator,
            pct,
            len(spec.get("functions") or []),
            len(v.survivors),
            len(v.timeouts),
            len(lost) - len(v.survivors) - len(v.timeouts),
            len(v.unrun),
        )
    )
    print(line)

    # One annotation per function that lost mutants, at its `def` in the head
    # source — the function is the unit mutmut regenerated, so it is the unit
    # a reviewer acts on.
    by_function: dict[str, list[str]] = {}
    for key in lost:
        by_function.setdefault(key.rpartition(MUTANT_SEP)[0], []).append(key)
    for q, keys in sorted(by_function.items()):
        path, mangled = split_qualified(q)
        try:
            src = (Path(args.root) / path).read_text(encoding="utf-8")
        except OSError:
            src = ""
        where = def_line(src, mangled) or 1
        names = ", ".join(f"{k} ({lost[k]})" for k in keys[:3])
        print(
            "::warning file=%s,line=%d::%s"
            % (
                _escape_property(path),
                where,
                _escape(f"{q}: {len(keys)} mutants not killed: {names}"),
            )
        )

    if problems:
        verdict, rc = "INCOMPLETE — refusing to gate on partial results", 2
    elif v.unrun:
        verdict, rc = f"INCOMPLETE — {len(v.unrun)} in-scope mutants unrun", 2
    elif passes(v, args.min, args.small):
        verdict, rc = "PASS", 0
    elif v.denominator < args.small:
        verdict, rc = f"FAIL — fewer than {args.small} mutants, so every one must be killed", 1
    else:
        verdict, rc = f"FAIL — {pct:.1f}% < {args.min:.1f}% minimum", 1
    print(f"mutation diff gate: {verdict}")
    for p in problems:
        print(f"  - {_escape(p)}")
    for k in v.unrun[:20]:
        print(f"  - unrun: {_escape(k)}")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        body = [f"### Mutation (diff scope): {verdict}", "", line, ""]
        body += [f"- `{_escape(k)}` — {status}" for k, status in lost.items()]
        body += [f"- {_escape(p)}" for p in problems]
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("\n".join(body) + "\n")
    return rc


def _collect_full(
    plan: dict[str, Any], source: Path, prefix: str, files: set[str]
) -> tuple[dict[str, Any], list[str]]:
    """Union each file's codes across every full shard: first non-None wins.

    The same rule `mutation_shards.py merge` applies, because a full shard
    writes every key of every file and `None` against the ones it did not own.
    """
    full = (plan.get("sets") or {}).get("full")
    if full is not None:
        indexes = list(range(len(full.get("shards") or [])))
    else:
        indexes = sorted(
            int(d.name[len(prefix) :])
            for d in source.glob(prefix + "*")
            if d.is_dir() and d.name[len(prefix) :].isdigit()
        )
    problems = [] if indexes else [f"no full shards under {source}/{prefix}*"]
    codes: dict[str, Any] = {}
    for i in indexes:
        if not (source / f"{prefix}{i}").is_dir():
            problems.append(f"full shard {i}: no artifact at {source}/{prefix}{i}")
            continue
        for rel in sorted(files):
            meta = ms.shard_meta(source, prefix, i, rel)
            if meta is None:
                continue
            for k, c in _read_codes(meta).items():
                if codes.get(k) is None:
                    codes[k] = c
    return codes, problems


def cmd_compare(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    spec, invalid = validate_plan(plan)
    if spec is None:
        print("mutation diff compare: malformed plan, refusing to compare:")
        for p in invalid:
            print(f"  - {_escape(p)}")
        return 2
    diff, problems = collect_diff(spec, Path(args.diff_source), args.diff_prefix)
    functions = _functions_of(spec["shards"])
    files = {_core_rel(split_qualified(q)[0]) for q in functions}
    full_all, full_problems = _collect_full(
        plan, Path(args.full_source), args.full_prefix, files
    )
    problems += full_problems
    prefixes = tuple(q + MUTANT_SEP for q in functions)
    full = {k: c for k, c in full_all.items() if k.startswith(prefixes)}

    def name(side: dict[str, Any], key: str) -> str:
        return "absent" if key not in side else status_of(side[key])

    agree, disagree, timeouts = [], [], []
    for key in sorted(set(diff) | set(full)):
        f, d = name(full, key), name(diff, key)
        # A missing result first: a timeout on one side does not excuse the
        # other side never having run the mutant at all.
        if {f, d} & {"absent", "not checked"}:
            disagree.append(f"{key}: full={f} diff={d}")
        elif "timeout" in (f, d):
            timeouts.append(f"{key}: full={f} diff={d}")
        elif (f == "killed") == (d == "killed"):
            agree.append(key)
        else:
            disagree.append(f"{key}: full={f} diff={d}")

    print(
        f"agree {len(agree)}, disagree {len(disagree)}, excluded-timeouts {len(timeouts)}"
    )
    for line in disagree:
        print(f"  disagree: {_escape(line)}")
    for line in timeouts:
        print(f"  excluded timeout: {_escape(line)}")
    for p in problems:
        print(f"  - {_escape(p)}")
    if problems:
        return 2
    return 1 if disagree else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gate", help="score the diff set's shard results")
    g.add_argument("--plan", required=True)
    g.add_argument("--source", required=True, help="dir holding <prefix><i>/ artifacts")
    g.add_argument("--prefix", required=True)
    g.add_argument("--min", type=float, default=80.0, help="minimum kill %%")
    g.add_argument("--small", type=int, default=10,
                   help="below this many mutants, every one must be killed")
    g.add_argument("--root", default=str(ROOT),
                   help="head checkout, for annotation line numbers")

    c = sub.add_parser("compare", help="diff run vs full run, per in-scope mutant")
    c.add_argument("--plan", required=True)
    c.add_argument("--full-source", required=True)
    c.add_argument("--diff-source", required=True)
    c.add_argument("--full-prefix", default="mutation-full-shard-")
    c.add_argument("--diff-prefix", default="mutation-diff-shard-")

    args = ap.parse_args(argv)
    if args.cmd == "gate":
        return cmd_gate(args)
    return cmd_compare(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
