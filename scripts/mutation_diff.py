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
`pack_functions` and runs each function's mutants by the explicit pattern
`pattern()` writes, so no cached verdict is ever trusted.

Two CLIs read the shards' results back:

  mutation_diff.py gate --plan PLAN --source DIR --prefix mutation-diff-shard-
                        [--min 80] [--small 10] [--root ROOT] [--no-annotations]
      Score the diff set: exit 0 pass, 1 fail, 2 unrun or missing results.
  mutation_diff.py compare --plan PLAN --full-source DIR --diff-source DIR
      Per-mutant agreement between a full run and a diff run of the same SHA;
      exit 1 on any killed/not-killed disagreement (timeouts excluded).
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


def _pytest_table(text: str | None):
    if text is None:
        return None
    return tomllib.loads(text).get("tool", {}).get("pytest", {}).get("ini_options")


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
    """Changed files that change how every mutant is run; empty means no trigger."""
    reasons: list[str] = []
    for p in changed_paths:
        name = PurePosixPath(p)
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
                why = "setup.cfg [mutmut] changed"
            elif p == "requirements/mutation-tools.txt" or (
                name.parent == PurePosixPath("scripts")
                and name.name.startswith("mutation_")
                and name.suffix == ".py"
            ):
                hit, why = True, f"{p} changed"
            elif p == CI_YML:
                hit = _mutation_jobs(read("base", p)) != _mutation_jobs(read("head", p))
                why = "ci.yml jobs.mutation* changed"
            elif p == "pyproject.toml":
                hit = _pytest_table(read("base", p)) != _pytest_table(read("head", p))
                why = "pyproject.toml [tool.pytest.ini_options] changed"
            else:
                continue
        except _PARSE_ERRORS:
            hit, why = True, f"{p} unparsable"
        if hit:
            reasons.append(why)
    return reasons


def _is_core_module(p: str) -> bool:
    pp = PurePosixPath(p)
    return (
        str(pp.parent) == CORE_DIR and pp.suffix == ".py" and pp.name != "__init__.py"
    )


def diff_scope(
    changed_paths: list[str],
    read: Callable[[str, str], str | None],
    deps: dict[str, list[str]],
) -> list[str]:
    """Sorted qualified changed functions plus their direct callers."""
    funcs: set[str] = set()
    for p in changed_paths:
        if _is_core_module(p):
            funcs |= {
                qualify(p, k)
                for k in changed_functions(read("base", p), read("head", p))
            }
    return sorted(funcs | direct_callers(deps, funcs))


# --------------------------------------------------------------------------
# Counting and packing (the planner's half)
# --------------------------------------------------------------------------

#: What mutmut appends to a mangled function name to name one of its mutants.
MUTANT_SEP = "__mutmut_"
#: Mutants per diff shard, and the most diff shards one run may ask for.
PER_SHARD = 1500
MAX_SHARDS = 16


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


def mutant_counts(path: str, src: str) -> dict[str, int]:
    """Mangled function -> number of mutants mutmut generates for it.

    mutmut's own generator, so the count is the one `mutmut run` will produce
    for the same source and config (call under `mutmut_config`). A function
    with nothing to mutate (`pass`) is absent, not zero.
    """
    from mutmut.mutation.file_mutation import mutate_file_contents

    out: dict[str, int] = {}
    for name in mutate_file_contents(path, src).mutant_names:
        head, sep, _ = name.rpartition(MUTANT_SEP)
        if sep:
            out[head] = out.get(head, 0) + 1
    return out


def pattern(qualified: str) -> str:
    """The `mutmut run` argument that selects exactly this function's mutants.

    Anchored on mutmut's suffix, so `x_install` cannot swallow
    `x_install_from_path`.
    """
    return qualified + MUTANT_SEP + "*"


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
) -> list[list[str]]:
    """Pack qualified functions into `min(cap, ceil(total / per_shard))` shards.

    Longest-processing-time first on `count * ms_per_mutant` (the mean for an
    unmeasured function), ties broken by name, so the same scope always packs
    the same way. A bin can come back empty when one function outweighs the
    shard size — a function cannot be split — and the planner drops those.
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
    for f in sorted(live, key=lambda f: (-weight[f], f)):
        i = load.index(min(load))
        bins[i].append(f)
        load[i] += weight[f]
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


def _functions_of(shards: list[list[str]]) -> list[str]:
    return [p[: -len(MUTANT_SEP + "*")] for shard in shards for p in shard]


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

    * `shards` is a list of non-empty lists of `<qualified>__mutmut_*` strings
      (an empty shard is one the planner never emits, see mutation_plan.py);
    * `mutants` is an int >= 0, and is 0 exactly when there are no shards, so
      a `0` can't make the shortfall check vacuous;
    * `functions` is a list of strings;
    * `counts`, when present (the planner always writes it), maps exactly the
      shards' functions to positive ints that sum to `mutants`.
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
    if not shards_ok:
        problems.append(f"`shards` is {shards!r}, not a list")
    else:
        for i, shard in enumerate(shards):
            if not isinstance(shard, list) or not shard:
                problems.append(f"shard {i} is {shard!r}, not a non-empty list")
                shards_ok = False
                continue
            for pat in shard:
                if not isinstance(pat, str) or not pat.endswith(MUTANT_SEP + "*"):
                    problems.append(f"shard {i}: {pat!r} is not a function pattern")
                    shards_ok = False

    mutants = spec.get("mutants")
    if not _count(mutants) or mutants < 0:
        problems.append(f"`mutants` is {mutants!r}, not an integer >= 0")
    elif isinstance(shards, list) and (mutants == 0) != (not shards):
        problems.append(f"`mutants` is {mutants} but {len(shards)} shards are planned")

    functions = spec.get("functions")
    if not isinstance(functions, list) or not all(isinstance(f, str) for f in functions):
        problems.append(f"`functions` is {functions!r}, not a list of strings")

    if "counts" in spec:
        counts = spec["counts"]
        if not isinstance(counts, dict) or not all(
            isinstance(k, str) and _count(v) and v > 0 for k, v in counts.items()
        ):
            problems.append("`counts` is not an object of positive integers")
        elif shards_ok and set(counts) != set(_functions_of(shards)):
            problems.append("`counts` names different functions than the shards run")
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
    so its keys are read from that shard's `.meta` only: every other shard
    reports them `None`, having been asked to run something else. Only keys
    with the function's exact `__mutmut_` prefix are taken, so out-of-scope
    functions of the same file — `None` in every diff shard — are never read.

    `spec` must have passed `validate_plan`.
    """
    codes: dict[str, int | None] = {}
    problems: list[str] = []
    per_function = spec.get("counts") or {}
    for index, shard in enumerate(spec["shards"]):
        if not (source / f"{prefix}{index}").is_dir():
            problems.append(f"shard {index}: no artifact at {source}/{prefix}{index}")
            continue
        for pat in shard:
            q = pat[: -len(MUTANT_SEP + "*")]
            path, _ = split_qualified(q)
            meta = ms.shard_meta(source, prefix, index, _core_rel(path))
            if meta is None:
                problems.append(f"shard {index}: no {path}.meta for {q}")
                continue
            mine = {
                k: v for k, v in _read_codes(meta).items() if k.startswith(q + MUTANT_SEP)
            }
            if not mine:
                problems.append(f"shard {index}: no mutants of {q} (planned, never run)")
            elif q in per_function and len(mine) < per_function[q]:
                # Exact per function: a total alone hides one function's
                # shortfall behind another's surplus.
                problems.append(
                    f"{q}: planner counted {per_function[q]} mutants; shards hold {len(mine)}"
                )
            codes.update(mine)
    # `<`, not `!=`: a surplus is still scored in full, and making it an error
    # needs Task 7 to prove the planner and the shards mutate the same tree.
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
    g.add_argument("--no-annotations", dest="annotate", action="store_false",
                   help="print no ::warning annotations (the summary still lists survivors)")

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
