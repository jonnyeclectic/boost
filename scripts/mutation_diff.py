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

Pure functions only: the caller supplies file text through `read(rev, path)`
and the dependency map from `mutants/mutmut-stats.json`.
"""

from __future__ import annotations

import ast
import configparser
import tomllib
from collections.abc import Callable
from pathlib import PurePosixPath

import yaml
from mutmut.mutation.file_mutation import compute_function_hashes

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
