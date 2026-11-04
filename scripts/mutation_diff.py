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

Two CLIs read the shards' results back, and a third reads what the second wrote:

  mutation_diff.py gate --plan PLAN --source DIR --prefix mutation-diff-shard-
                        [--min 80] [--small 10] [--root ROOT] [--no-annotations]
      Score the diff set: exit 0 pass, 1 fail, 2 unrun or missing results.
  mutation_diff.py compare --plan PLAN --full-source DIR --diff-source DIR
                           [--min 80] [--small 10] [--json PATH]
      Per-mutant agreement between a full run and a diff run of the same SHA,
      and the two runs' verdicts over the diff scope. It ends with one line,
      ``shadow evidence: <STATUS> ...``, and exits by that status:
      0 AGREE, 1 DISAGREE or ALARM, 2 INCOMPLETE, 3 VACUOUS (see
      ``evidence_status``). ``--json`` writes the same facts for `evidence`.
  mutation_diff.py evidence --reports DIR --listing PAGE [--listing PAGE ...]
                            --since TIME [--probe-run ID] [--need 5] [--need-schedule 1]
      Count the reports under DIR that meet the bar before the diff gate binds
      (docs/superpowers/plans/2026-10-31-ci-speed.md, Task 7 Step 6), taking
      which reports exist and whose they are from the saved API listing: exit
      0 met, 1 a DISAGREE or ALARM on record, 2 a report unreadable, unread,
      expired or not matching its run, 3 short.
"""

from __future__ import annotations

import argparse
import ast
import configparser
import contextlib
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import tomllib
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
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
# the non-mapping ci.yml or `jobs`, and the non-table pyproject.toml step,
# raised by the readers below.
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
    doc = yaml.safe_load(text) or {}
    # A list or a scalar at the top has no `.get`: unparsable as a workflow,
    # and a full-run reason, never an AttributeError out of the planner.
    if not isinstance(doc, dict):
        raise ValueError("ci.yml is not a mapping")
    jobs = doc.get("jobs") or {}
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


# --------------------------------------------------------------------------
# Shadow evidence: what one comparison is worth toward binding the diff gate
# --------------------------------------------------------------------------

#: The least a shadow report must compare to count toward the plan's bar
#: (docs/superpowers/plans/2026-10-31-ci-speed.md, Task 7 Step 6). The only
#: report before this (artifact 13127375493, run 41387907117) compared 0
#: mutants over 0 functions and exited 0, which read exactly like agreement.
#: The spec (docs/superpowers/specs/2026-10-31-ci-speed-design.md) estimates a
#: single branch at ~140 mutants and a median train at ~4,000, so 200 is above
#: one small branch and far under a train.
EVIDENCE_MIN_MUTANTS = 200
EVIDENCE_MIN_FUNCTIONS = 3
#: The bar itself, which `evidence` defaults to: this many reports from
#: distinct comparisons, at least EVIDENCE_NEED_SCHEDULE of them from a
#: nightly. A comparison is one pull-request branch or one nightly commit, as
#: the artifact listing names the run (never as the report says), and one
#: scope: under strict up-to-date checks every open PR is re-run after each
#: merge to main, on a new merge commit and over the same functions, so
#: counting distinct GITHUB_SHAs counted one PR once per merge.
EVIDENCE_NEED = 5
EVIDENCE_NEED_SCHEDULE = 1
#: What `compare` writes, and `evidence` refuses any other version of. 2 adds
#: `head_sha` and `scope`; no version-1 report was ever uploaded (the one
#: report on record, artifact 13127375493, predates the JSON).
EVIDENCE_SCHEMA = 2
EVIDENCE_FILE = "mutation-shadow-evidence.json"
#: The artifact ci.yml's `mutation` job uploads the report and JSON as.
EVIDENCE_ARTIFACT = "mutation-shadow-report"
#: A run on this branch is a nightly's (schedule) or a push's; any other
#: branch is a pull request's. The merge queue's branches are neither: a
#: queue run re-tests a PR whose own runs are counted by its branch, so one is
#: read (a DISAGREE in it still stops) and never counted. No merge_group run
#: of ci.yml exists (0 listed on 2026-11-04).
DEFAULT_BRANCH = "main"
QUEUE_BRANCH_PREFIX = "gh-readonly-queue/"

STATUSES = ("AGREE", "VACUOUS", "ALARM", "DISAGREE", "INCOMPLETE")
#: `compare`'s exit code per status. 3 is VACUOUS's own: an uncaught exception
#: exits 1 and argparse exits 2, so a crash can never read as 0 or 3, and
#: nothing that reads 0 as "agreed" can count a report that compared nothing.
COMPARE_EXIT = {"AGREE": 0, "DISAGREE": 1, "ALARM": 1, "INCOMPLETE": 2, "VACUOUS": 3}

# A commit id as GitHub writes one (sha-1 or sha-256). mutation_diff.py cannot
# import ci_proven_tree's: neither module is a package, and the planner side
# must not depend on the API side.
_SHA = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")


def evidence_status(
    *, problems: bool, disagree: int, compared: int, functions: int,
    full_ok: bool, diff_ok: bool,
) -> str:
    """What one comparison says, most serious first.

    INCOMPLETE: a result is missing, so nothing below can be trusted.
    DISAGREE: a mutant killed on one side and not the other.
    ALARM: the per-mutant results agree but the two verdicts over the diff
      scope do not -- a one-sided timeout (excluded from agreement) or a
      skipped-versus-unkilled pair can do that. Bound, the diff gate would
      decide those functions differently from the full gate.
    VACUOUS: everything agrees, over too little to mean anything.
    AGREE: the only status that counts toward the bar.
    """
    if problems:
        return "INCOMPLETE"
    if disagree > 0:
        return "DISAGREE"
    if full_ok != diff_ok:
        return "ALARM"
    if compared < EVIDENCE_MIN_MUTANTS or functions < EVIDENCE_MIN_FUNCTIONS:
        return "VACUOUS"
    return "AGREE"


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
    # a reviewer acts on. Not while the gate is advisory (`--no-annotations`,
    # ci.yml's shadow mode): a warning on every changed function of every PR
    # from a check that decides nothing is noise, and the summary has the list.
    by_function: dict[str, list[str]] = {}
    for key in lost:
        by_function.setdefault(key.rpartition(MUTANT_SEP)[0], []).append(key)
    for q, keys in sorted(by_function.items()) if args.annotate else ():
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


def _plan_base(plan: Any) -> str | None:
    """`sets.diff.base` when it is a commit id (provenance only), else None."""
    spec = (plan.get("sets") or {}).get("diff") if isinstance(plan, dict) else None
    base = spec.get("base") if isinstance(spec, dict) else None
    return base if isinstance(base, str) and _SHA.fullmatch(base) else None


def scope_digest(names: list[str]) -> str:
    """One comparison's identity: sha256 over the mutant names it scored.

    Two reports over the same names compared the same thing, whichever
    commit they ran on, so `evidence` counts them once.
    """
    return hashlib.sha256("\n".join(sorted(set(names))).encode("utf-8")).hexdigest()


def _write_evidence(path: str | None, record: dict[str, Any]) -> None:
    """`compare`'s facts as JSON, for `evidence` to count across runs.

    The GITHUB_* values and SHADOW_HEAD_SHA are recorded, never judged here:
    `evidence` checks each against the artifact listing's `workflow_run`,
    which the run cannot write. SHADOW_HEAD_SHA is the run's head as that
    listing names it -- on a pull request the PR head, where GITHUB_SHA is
    the merge commit, so the two never match there.
    """
    if not path:
        return
    record = {
        "schema": EVIDENCE_SCHEMA, **record,
        "min_mutants": EVIDENCE_MIN_MUTANTS, "min_functions": EVIDENCE_MIN_FUNCTIONS,
        "event": os.environ.get("GITHUB_EVENT_NAME", ""),
        "sha": os.environ.get("GITHUB_SHA", ""),
        "head_sha": os.environ.get("SHADOW_HEAD_SHA", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
    }
    Path(path).write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")


def _status_line(status: str, compared: int, functions: int) -> str:
    bar = f"counts toward the bar only at >= {EVIDENCE_MIN_MUTANTS} over >= {EVIDENCE_MIN_FUNCTIONS}"
    tail = {
        "AGREE": "counts toward the bar",
        "VACUOUS": bar,
        "ALARM": "does not count, and stops the plan until explained",
        "DISAGREE": "does not count, and stops the plan until explained",
        "INCOMPLETE": "does not count: a result is missing",
    }[status]
    return (f"shadow evidence: {status} — compared {compared} mutants over "
            f"{functions} functions ({tail})")


def _scoped(v: Verdict, ok: bool) -> str:
    return "%s (%d/%d)" % ("PASS" if ok else "FAIL", v.killed, v.denominator)


def cmd_compare(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    empty = {"compared_mutants": 0, "compared_functions": 0, "agree": 0, "disagree": 0,
             "excluded_timeouts": 0, "full_scoped": None, "diff_scoped": None,
             "base": _plan_base(plan), "scope": scope_digest([])}
    spec, invalid = validate_plan(plan)
    if spec is None:
        print("mutation diff compare: malformed plan, refusing to compare:")
        for p in invalid:
            print(f"  - {_escape(p)}")
        print(_status_line("INCOMPLETE", 0, 0))
        _write_evidence(args.json, {"status": "INCOMPLETE", **empty})
        return COMPARE_EXIT["INCOMPLETE"]
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

    agree: list[str] = []
    disagree: list[tuple[str, str]] = []
    timeouts: list[str] = []
    for key in sorted(set(diff) | set(full)):
        f, d = name(full, key), name(diff, key)
        # A missing result first: a timeout on one side does not excuse the
        # other side never having run the mutant at all.
        if {f, d} & {"absent", "not checked"}:
            disagree.append((key, f"{key}: full={f} diff={d}"))
        elif "timeout" in (f, d):
            timeouts.append(f"{key}: full={f} diff={d}")
        elif (f == "killed") == (d == "killed"):
            agree.append(key)
        else:
            disagree.append((key, f"{key}: full={f} diff={d}"))

    # What was compared, counted from the comparison itself and not from the
    # plan: an excluded timeout is not compared, and a function the plan
    # names but neither side ran is not one this report says anything about.
    compared = len(agree) + len(disagree)
    compared_functions = len({function_of(k) for k in agree + [k for k, _ in disagree]})

    # Both verdicts over exactly the names the diff gate scores, so a full
    # FAIL that comes from outside the PR's scope (main sits near 87.8% per
    # the spec, so one can) is never read as the diff gate's miss.
    planned = [n for shard in spec["shards"] for n in shard]
    full_v = score({n: full.get(n) for n in planned})
    diff_v = score({n: diff.get(n) for n in planned})
    full_ok = passes(full_v, args.min, args.small)
    diff_ok = passes(diff_v, args.min, args.small)
    status = evidence_status(problems=bool(problems), disagree=len(disagree),
                             compared=compared, functions=compared_functions,
                             full_ok=full_ok, diff_ok=diff_ok)

    print(
        f"agree {len(agree)}, disagree {len(disagree)}, excluded-timeouts {len(timeouts)}"
    )
    for _, line in disagree:
        print(f"  disagree: {_escape(line)}")
    for line in timeouts:
        print(f"  excluded timeout: {_escape(line)}")
    for p in problems:
        print(f"  - {_escape(p)}")
    print(f"scoped verdicts over {len(_functions_of([planned]))} functions: "
          f"full {_scoped(full_v, full_ok)}, diff {_scoped(diff_v, diff_ok)}")
    if status == "ALARM":
        # A status, not a claim that a whole-codebase FAIL implies a diff
        # FAIL: these are both verdicts over the same scoped names.
        one, other = ("FAILS", "PASSES") if diff_ok else ("PASSES", "FAILS")
        what = ("passed what the full gate refuses" if diff_ok
                else "refused what the full gate passes")
        print(f"ALARM: over the diff scope the full run {one} and the diff run {other} "
              f"— bound, the diff gate would have {what} on these same functions")
    print(_status_line(status, compared, compared_functions))
    _write_evidence(args.json, {
        "status": status, "compared_mutants": compared,
        "compared_functions": compared_functions, "agree": len(agree),
        "disagree": len(disagree), "excluded_timeouts": len(timeouts),
        "full_scoped": "PASS" if full_ok else "FAIL",
        "diff_scoped": "PASS" if diff_ok else "FAIL", "base": empty["base"],
        "scope": scope_digest(planned)})
    return COMPARE_EXIT[status]


_DIGEST = re.compile(r"[0-9a-f]{64}")
_RUN_ID = re.compile(r"[0-9]+")


def _evidence_problems(rec: Any) -> list[str]:
    """Every way one stored report is not the shape `compare` writes."""
    if not isinstance(rec, dict):
        return ["not a JSON object"]
    problems = []
    if not (_count(rec.get("schema")) and rec["schema"] == EVIDENCE_SCHEMA):
        problems.append("schema is not %d" % EVIDENCE_SCHEMA)
    if rec.get("status") not in STATUSES:
        problems.append("unknown status")
    problems.extend("%s is not an integer >= 0" % key
                    for key in ("compared_mutants", "compared_functions", "agree",
                                "disagree", "excluded_timeouts")
                    if not (_count(rec.get(key)) and rec[key] >= 0))
    problems.extend("%s is not PASS, FAIL or null" % key
                    for key in ("full_scoped", "diff_scoped")
                    if rec.get(key) not in ("PASS", "FAIL", None))
    problems.extend("%s is not a commit id" % key for key in ("sha", "head_sha")
                    if not isinstance(rec.get(key), str) or not _SHA.fullmatch(rec[key]))
    if not isinstance(rec.get("event"), str):
        problems.append("event is not a string")
    if not isinstance(rec.get("run_id"), str) or not _RUN_ID.fullmatch(rec["run_id"]):
        problems.append("run_id is not a run id")
    if not isinstance(rec.get("scope"), str) or not _DIGEST.fullmatch(rec["scope"]):
        problems.append("scope is not a sha256 digest")
    return problems


def qualifies(rec: dict[str, Any]) -> bool:
    """Does a valid report count toward the bar, judged by TODAY's constants?

    The stored status alone is not trusted: a report written under looser
    thresholds than these could say AGREE over too little.
    """
    return (rec["status"] == "AGREE" and rec["disagree"] == 0
            and rec["compared_mutants"] >= EVIDENCE_MIN_MUTANTS
            and rec["compared_functions"] >= EVIDENCE_MIN_FUNCTIONS
            and rec["full_scoped"] is not None
            and rec["full_scoped"] == rec["diff_scoped"])


#: A fork's entry is never read, so its times are never compared.
_NEVER = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True)
class Listed:
    """One `mutation-shadow-report` artifact as the GitHub API lists it.

    Everything here comes from the API (`GET /actions/artifacts`), which the
    run that uploaded the artifact cannot write -- unlike the report inside.
    """

    artifact_id: int
    run_id: int
    #: `workflow_run.head_repository_id == repository_id`: a fork's run can
    #: upload any JSON it likes, so a fork's artifact is never read.
    same_repo: bool
    expired: bool = False
    created: datetime = _NEVER
    expires: datetime = _NEVER
    branch: str = ""
    head_sha: str = ""


def _when(value: Any) -> datetime | None:
    """An ISO 8601 time, UTC when it names no zone; None when it is not one."""
    if not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value)
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def _listed(art: Any) -> tuple[Listed | None, str]:
    """One listing entry, or why it is not one."""
    run = art.get("workflow_run") if isinstance(art, dict) else None
    if not (isinstance(run, dict) and _count(art.get("id")) and _count(run.get("id"))
            and _count(run.get("repository_id"))):
        return None, "an entry has no artifact id, run id or repository id"
    where = "artifact %d" % art["id"]
    if art.get("name") != EVIDENCE_ARTIFACT:
        return None, "%s is not named %s" % (where, EVIDENCE_ARTIFACT)
    head_repo = run.get("head_repository_id")
    if not (_count(head_repo) and head_repo == run["repository_id"]):
        return Listed(art["id"], run["id"], same_repo=False), ""
    created, expires = _when(art.get("created_at")), _when(art.get("expires_at"))
    if not (created and expires and isinstance(art.get("expired"), bool)
            and isinstance(run.get("head_branch"), str)
            and isinstance(run.get("head_sha"), str) and _SHA.fullmatch(run["head_sha"])):
        return None, "%s is not the shape the API lists" % where
    return Listed(art["id"], run["id"], True, art["expired"], created, expires,
                  run["head_branch"], run["head_sha"]), ""


def _load_listing(paths: list[str]) -> tuple[dict[int, Listed], list[str]]:
    """Every listed artifact by id, from saved pages of the API's listing.

    Also every way those pages are not the whole of one listing: an artifact
    left off a page is a report nobody read, which could be a DISAGREE.
    """
    listed: dict[int, Listed] = {}
    totals: set[int] = set()
    problems: list[str] = []
    for p in paths:
        try:
            page = json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            problems.append("%s: unreadable (%s)" % (p, type(exc).__name__))
            continue
        if not (isinstance(page, dict) and _count(page.get("total_count"))
                and isinstance(page.get("artifacts"), list)):
            problems.append("%s: not a page of the artifact listing" % p)
            continue
        totals.add(page["total_count"])
        for art in page["artifacts"]:
            got, why = _listed(art)
            if got is None:
                problems.append("%s: %s" % (p, why))
            else:
                listed[got.artifact_id] = got
    if len(totals) > 1:
        problems.append("the pages disagree on total_count (%s): list them again"
                        % ", ".join(map(str, sorted(totals))))
    elif totals and len(listed) != min(totals) and not problems:
        problems.append("the pages list %d of %d artifacts: fetch every page"
                        % (len(listed), min(totals)))
    return listed, problems


def _subject(item: Listed) -> tuple[str, str] | None:
    """What a counted report is a comparison of, from the listing alone.

    A pull request's branch -- every re-run of it after a merge to main is
    the same PR again -- or a nightly's commit. None for a merge-queue run.
    """
    if item.branch == DEFAULT_BRANCH:
        return ("nightly commit", item.head_sha)
    if item.branch.startswith(QUEUE_BRANCH_PREFIX):
        return None
    return ("branch", item.branch)


def _mismatch(rec: dict[str, Any], item: Listed) -> list[str]:
    """Every way a report disagrees with the run the listing says uploaded it."""
    wrong = []
    if rec["run_id"] != str(item.run_id):
        wrong.append("run_id %s, listed run %d" % (rec["run_id"], item.run_id))
    if rec["head_sha"] != item.head_sha:
        wrong.append("head_sha %s, listed %s" % (rec["head_sha"][:12], item.head_sha[:12]))
    on_main = item.branch == DEFAULT_BRANCH
    if rec["event"] == "schedule" and not (on_main and rec["sha"] == item.head_sha):
        wrong.append("says schedule, but its run is not on %s's listed commit" % DEFAULT_BRANCH)
    if rec["event"] in ("pull_request", "merge_group") and on_main:
        wrong.append("says %s, but its run is on %s" % (rec["event"], DEFAULT_BRANCH))
    return wrong


def _now() -> datetime:
    """The clock expiry is judged by; a seam for the tests."""
    return datetime.now(UTC)


def _days(span: timedelta) -> str:
    return "%.1f days" % (span.total_seconds() / 86400)


def cmd_evidence(args: argparse.Namespace) -> int:
    """Count downloaded shadow reports against the bar (module docstring).

    The listing decides which reports exist and whose they are; a file only
    says what its comparison found. So a fork's artifact is never read, a
    listed report that was not downloaded or has expired is an unknown (it
    could have been a DISAGREE), and so is a window that opened longer ago
    than a report is kept. Every line starts with `evidence`, and every value
    from a report or branch name goes through `_escape`: none may begin a
    workflow command.
    """
    root = Path(args.reports)
    if not root.is_dir():
        print(f"evidence: {_escape(str(root))} is not a directory")
        return 2
    since = _when(args.since)
    if since is None:
        print(f"evidence: --since {_escape(args.since)} is not an ISO 8601 time")
        return 2
    listed, listing_problems = _load_listing(args.listing)
    for p in listing_problems:
        print(f"evidence: listing: {_escape(p)}")
    unknown, read, stops = len(listing_problems), 0, 0
    files = {p.parent.name: p for p in root.glob("*/" + EVIDENCE_FILE)}
    kept: timedelta | None = None
    # (is a nightly, created, artifact id, subject, scope) of each qualifying report
    candidates: list[tuple[bool, datetime, int, tuple[str, str], str]] = []
    for item in sorted(listed.values(), key=lambda i: (i.created, i.artifact_id)):
        path = files.pop(str(item.artifact_id), None)
        where = "artifact %d (run %d)" % (item.artifact_id, item.run_id)
        if not item.same_repo:
            print(f"evidence: {where}: from another repository -- not read")
            continue
        if item.created < since:
            print(f"evidence: {where}: from before --since -- not read")
            continue
        span = item.expires - item.created
        kept = span if kept is None else min(kept, span)
        if item.expired:
            print(f"evidence: {where}: expired before it was read -- it could have been "
                  "a DISAGREE")
            unknown += 1
            continue
        if path is None:
            print(f"evidence: {where}: listed, but no {item.artifact_id}/{EVIDENCE_FILE} "
                  "was downloaded")
            unknown += 1
            continue
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"evidence: {where}: unreadable ({type(exc).__name__})")
            unknown += 1
            continue
        problems = _evidence_problems(rec)
        if problems:
            print(f"evidence: {where}: malformed ({'; '.join(problems)})")
            unknown += 1
            continue
        wrong = _mismatch(rec, item)
        if wrong:
            print(f"evidence: {where}: does not match its listed run "
                  f"({_escape('; '.join(wrong))})")
            unknown += 1
            continue
        read += 1
        if rec["status"] in ("DISAGREE", "ALARM"):
            stops += 1
        subject = _subject(item)
        if not qualifies(rec):
            verdict = "does not count"
        elif item.run_id in args.probe_run:
            verdict = "the Step 7 probe -- never counted"
        elif subject is None:
            verdict = "a merge-queue run -- never counted"
        else:
            verdict = "qualifies"
            candidates.append((rec["event"] == "schedule", item.created, item.artifact_id,
                               subject, rec["scope"]))
        what = "merge queue" if subject is None else "%s %s" % (
            subject[0], subject[1][:12] if subject[0] == "nightly commit" else subject[1])
        print("evidence: %s: %s, %d mutants over %d functions, %s run of %s -- %s" % (
            where, rec["status"], rec["compared_mutants"], rec["compared_functions"],
            _escape(rec["event"]) or "?", _escape(what), verdict))
    for name in sorted(files):
        print(f"evidence: {_escape(name)}/{EVIDENCE_FILE}: not in the listing -- "
              "list again, or remove it")
        unknown += 1
    now = _now()
    if kept is not None and now - since >= kept:
        print(f"evidence: the window opened {_days(now - since)} ago and a report is kept "
              f"{_days(kept)}: one from its start may be gone from the listing, and could "
              "have been a DISAGREE")
        unknown += 1
    # Nightlies first, so a nightly whose scope a PR's report shares is the
    # one kept; then oldest first. A report counts only when both its subject
    # and its scope are new.
    subjects: set[tuple[str, str]] = set()
    scopes: set[str] = set()
    counted = nightly = 0
    for is_nightly, _, artifact_id, subject, scope in sorted(
            candidates, key=lambda c: (not c[0], c[1], c[2])):
        if subject in subjects or scope in scopes:
            same = subject[0] if subject in subjects else "scope"
            print(f"evidence: artifact {artifact_id}: the same {same} as a report already "
                  "counted -- counted once")
            continue
        subjects.add(subject)
        scopes.add(scope)
        counted += 1
        nightly += is_nightly
    print(f"evidence: {counted} of {args.need} AGREE reports from distinct comparisons "
          f"({nightly} of {args.need_schedule} from schedule); {read} read, "
          f"{unknown} unreadable or unknown, {stops} DISAGREE or ALARM")
    if stops:
        return 1
    if unknown:
        return 2
    return 0 if counted >= args.need and nightly >= args.need_schedule else 3


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    def thresholds(p: argparse.ArgumentParser) -> None:
        # One definition for `gate` and `compare`, so the scoped verdicts the
        # comparison reports are the ones the diff gate would give.
        p.add_argument("--min", type=float, default=80.0, help="minimum kill %%")
        p.add_argument("--small", type=int, default=10,
                       help="below this many mutants, every one must be killed")

    g = sub.add_parser("gate", help="score the diff set's shard results")
    g.add_argument("--plan", required=True)
    g.add_argument("--source", required=True, help="dir holding <prefix><i>/ artifacts")
    g.add_argument("--prefix", required=True)
    thresholds(g)
    g.add_argument("--root", default=str(ROOT),
                   help="head checkout, for annotation line numbers")
    g.add_argument("--no-annotations", dest="annotate", action="store_false",
                   help="print no ::warning annotations (the summary still lists survivors)")

    c = sub.add_parser("compare", help="diff run vs full run, per in-scope mutant")
    c.add_argument("--plan", required=True)
    c.add_argument("--full-source", required=True)
    c.add_argument("--diff-source", required=True)
    c.add_argument("--full-prefix", default="mutation-full-shard-")
    c.add_argument("--diff-prefix", default="mutation-diff-shard-")
    thresholds(c)
    c.add_argument("--json", default=None,
                   help="also write the report's facts here, for `evidence`")

    e = sub.add_parser("evidence", help="count downloaded shadow reports against the bar")
    e.add_argument("--reports", required=True,
                   help="dir holding <artifact id>/%s files" % EVIDENCE_FILE)
    e.add_argument("--listing", action="append", required=True, metavar="PAGE",
                   help="a saved page of the API's %s artifact listing; repeat per page"
                   % EVIDENCE_ARTIFACT)
    e.add_argument("--since", required=True,
                   help="when collection began (PR 4's merged_at), ISO 8601; never moved")
    e.add_argument("--probe-run", type=int, action="append", default=[], metavar="RUN_ID",
                   help="the Step 7 probe's run: read (a DISAGREE stops), never counted")
    e.add_argument("--need", type=int, default=EVIDENCE_NEED)
    e.add_argument("--need-schedule", type=int, default=EVIDENCE_NEED_SCHEDULE)

    args = ap.parse_args(argv)
    if args.cmd == "gate":
        return cmd_gate(args)
    if args.cmd == "evidence":
        return cmd_evidence(args)
    return cmd_compare(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
