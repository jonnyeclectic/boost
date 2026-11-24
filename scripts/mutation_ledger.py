#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The mutation survivor ledger: stop re-proving known survivors on full runs.

Design, the reversals it asks for and why each guard exists:
docs/superpowers/specs/2026-11-24-mutation-survivor-ledger.md. In one line: a
green, unledgered whole-codebase run on ``main`` records which mutants
survived (or timed out) in which unchanged functions; a later PR or push full
run leaves those out of its shards, and ``mutation_shards.py merge --plan``
merges each back in as the constant ``CARRIED_EXIT``, which mutmut reads as
"survived". Carrying a row never adds a kill. A carried row can only be stale
in one direction: a test that now kills it gets no credit until the next
ledger is written.

**Nothing here runs until the owner opts in.** The repository variable
``MUTATION_LEDGER`` is a comma-separated list of tokens, and each one switches
on one thing:

``write``         a green whole-codebase run writes and self-checks a ledger
``pull_request``  PR runs read it
``push``          push runs to main read it -- including the one whose
                  success ``publish.yml`` releases from

Unset, empty or anything else: no run writes or reads a ledger. Every command
below re-checks its own token, so a workflow ``if:`` is only ever a shortcut.

Subcommands
-----------
  find      (the ``mutation-ledger`` job; stdlib only) which whole-codebase
            run's ledger this run may read, or why none
  stamp     record the generator key and machinery digest in a plan (planner, .venv)
  apply     rewrite a plain full set as a ledgered one, or say why not (planner, .venv)
  write     build a ledger from a green run's merged results (``mutation``, .venv)
  selfcheck plan this commit against the fresh ledger, simulate its shards,
            run the real merge, and check nothing moved (``mutation``, .venv)

``apply`` never fails the planner: anything unexpected leaves the plain plan
and a reason that starts ``ledger not used:``. ``find`` always exits 0.
``write`` and ``selfcheck`` exit 1 on any doubt; the workflow runs them
continue-on-error, so a ledger failure never changes a run's conclusion.
"""
from __future__ import annotations

import argparse
import bisect
import contextlib
import fnmatch
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, filename: str, *, register: bool = False):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / filename)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s beside %s" % (filename, __file__))
    module = importlib.util.module_from_spec(spec)
    if register:
        sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ms = _load("mutation_shards", "mutation_shards.py")


def _diff():
    """``mutation_diff``, lazily: it imports PyYAML, which ``find`` must not need."""
    return sys.modules.get("mutation_diff") or _load("mutation_diff", "mutation_diff.py",
                                                     register=True)


KIND = "mutation-survivor-ledger"
SCHEMA = 1
ARTIFACT = "mutation-ledger"
#: The label that keeps a pull request's attempt-1 runs plain.
NO_LEDGER_LABEL = "mutation-no-ledger"
#: The repository variable's tokens (see the module docstring).
WRITE, PULL_REQUEST, PUSH = "write", "pull_request", "push"
TOKENS = (WRITE, PULL_REQUEST, PUSH)
READ_EVENTS = (PULL_REQUEST, PUSH)
WHOLE_CODEBASE_EVENTS = ("schedule", "workflow_dispatch")
MAIN = "main"
#: A ledger older than this is not used. An idle nightly inherits a real run
#: up to 7 days old (ci_proven_tree.MAX_INHERIT_AGE), so a quiet week must not
#: switch the ledger off; 14 is that week plus a week of missing nightlies,
#: by when nightly-watch.yml has been alarming for twelve days.
MAX_LEDGER_AGE = timedelta(days=14)
#: The mutate step's ``timeout-minutes`` in ci.yml, which a ledgered pack must
#: clear by ``mutation_shards.headroom_report`` exactly as the committed one does.
STEP_TIMEOUT_MINUTES = 190
MUTANT_SEP = "__mutmut_"
CARRIED_STATUSES = ("survived", "timeout")
MUTATED_TREE = "mutated-tree-"
INHERITED_TREE = "inherited-tree-"

_HASH = re.compile(r"[0-9a-f]{12}")
_SHA = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
_WHEN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_GLOB = re.compile(r"[*?\[\]]")


class LedgerError(Exception):
    """Why a ledger cannot be used or written. The message is the reason a log shows."""


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _iso(when: datetime) -> str:
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _when(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value)
    except ValueError:
        return None
    return when if when.tzinfo is not None else None


def tokens(value: str | None) -> set[str]:
    """The known tokens of ``MUTATION_LEDGER``; anything else is ignored, never guessed at."""
    return {t.strip() for t in (value or "").split(",")} & set(TOKENS)


def module_of(rel: str) -> str:
    """``rag/bm25.py`` -> ``boost_cli.core.rag.bm25``."""
    return "%s.%s" % (ms.SOURCE.as_posix().replace("/", "."), rel[: -len(".py")].replace("/", "."))


def number_of(key: str) -> int:
    return int(key.rpartition(MUTANT_SEP)[2])


def function_of(key: str) -> str:
    return key.rpartition(MUTANT_SEP)[0]


# --------------------------------------------------------------------------
# what mutmut generated, read from .meta
# --------------------------------------------------------------------------

def read_meta(mutants: Path) -> dict[str, dict[str, Any]]:
    """Every non-``__init__`` file's keys, codes, hashes and durations under ``mutants``.

    The planner's own stats run leaves a ``.meta`` for every mutatable file
    (mutmut's ``create_mutants_for_file`` saves every key, with every
    function's hash, before it runs anything), and so does every shard and
    the merge. So no mutant is regenerated to learn what exists.
    ``__init__.py`` is left out exactly as ``pack`` leaves it out: the merge
    checks separately that it generates nothing.
    """
    root = mutants / ms.SOURCE
    out: dict[str, dict[str, Any]] = {}
    for meta in sorted(root.rglob("*.py.meta")):
        rel = meta.relative_to(root).as_posix()[: -len(".meta")]
        if Path(rel).name == "__init__.py":
            continue
        data = json.loads(meta.read_text(encoding="utf-8"))
        codes = data.get("exit_code_by_key") or {}
        hashes = data.get("hash_by_function_name") or {}
        durations = data.get("durations_by_key") or {}
        if not all(isinstance(d, dict) for d in (codes, hashes, durations)):
            raise LedgerError("%s is not shaped like a mutmut .meta" % meta)
        module = module_of(rel)
        for key in codes:
            if not (isinstance(key, str) and key.startswith(module + ".")
                    and re.fullmatch(r".+%s[1-9][0-9]*" % MUTANT_SEP, key)):
                raise LedgerError("%s lists %r, not a mutant of %s" % (meta, key, module))
        out[rel] = {"codes": codes, "hashes": hashes, "durations": durations}
    if not out:
        raise LedgerError("no .meta under %s" % root)
    return out


def functions_of(meta: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """qualified function -> its file, mangled name, hash and keys (in mutant order)."""
    out: dict[str, dict[str, Any]] = {}
    for rel, data in meta.items():
        module = module_of(rel)
        for key in data["codes"]:
            q = function_of(key)
            entry = out.setdefault(q, {"file": rel, "mangled": q[len(module) + 1:],
                                       "keys": []})
            entry["keys"].append(key)
        for entry in out.values():
            if entry["file"] == rel:
                entry["hash"] = data["hashes"].get(entry["mangled"])
    for entry in out.values():
        entry["keys"].sort(key=number_of)
    return out


# --------------------------------------------------------------------------
# the key and the machinery digest (need mutation_diff, so the .venv)
# --------------------------------------------------------------------------

def generator_key(root: Path) -> dict[str, str]:
    """What identifies a mutant across runs: the generator, the parser, Python, mutmut's settings.

    Never anything about the tests (see the design's "The key identifies a
    mutant, never the tests"). Read in the planner, in the environment
    tests/unit/test_mutation_plan.py pins equal to the shards'.
    """
    from importlib import metadata

    md = _diff()

    def text(name: str) -> str | None:
        path = root / name
        return path.read_text(encoding="utf-8") if path.exists() else None

    settings = {"setup.cfg [mutmut]": md._mutmut_section(text("setup.cfg")),
                "pyproject.toml [tool.mutmut]": md._mutmut_table(text("pyproject.toml"))}
    return {"mutmut": metadata.version("mutmut"), "libcst": metadata.version("libcst"),
            "python": "%d.%d" % sys.version_info[:2],
            "config": hashlib.sha256(json.dumps(settings, sort_keys=True, default=str)
                                     .encode("utf-8")).hexdigest()}


def machinery_digest(root: Path) -> str:
    """sha256 over every ``scripts/mutation_*.py``, the mutation toolchain pins and
    ci.yml's ``jobs.mutation*``: a ledger is used only under the machinery that
    wrote it, and so self-checked it."""
    md = _diff()
    h = hashlib.sha256()
    for path in sorted((root / "scripts").glob("mutation_*.py")):
        h.update(b"%s\0" % path.name.encode("utf-8"))
        h.update(path.read_bytes() + b"\0")
    h.update((root / "requirements/mutation-tools.txt").read_bytes() + b"\0")
    jobs = md._mutation_jobs((root / md.CI_YML).read_text(encoding="utf-8"))
    h.update(json.dumps(jobs, sort_keys=True, default=str).encode("utf-8"))
    return h.hexdigest()


# --------------------------------------------------------------------------
# the ledgered plan
# --------------------------------------------------------------------------

def check_ledger(ledger: Any) -> dict[str, Any]:
    """The ledger if it is shaped as ``write`` writes one, else LedgerError."""
    if not isinstance(ledger, dict) or ledger.get("kind") != KIND or ledger.get("schema") != SCHEMA:
        raise LedgerError("not a schema-%d %s" % (SCHEMA, KIND))
    source = ledger.get("source")
    if not isinstance(source, dict) or _int(source.get("run_id")) is None:
        raise LedgerError("the ledger names no source run")
    if source.get("event") not in WHOLE_CODEBASE_EVENTS or source.get("branch") != MAIN:
        raise LedgerError("the ledger's source is not a whole-codebase run on main")
    if _when(source.get("created_at")) is None:
        raise LedgerError("the ledger's source has no usable created_at")
    functions = ledger.get("functions")
    if not isinstance(functions, dict):
        raise LedgerError("the ledger has no functions")
    for q, f in functions.items():
        nums = [*(f.get("survived") or []), *(f.get("timeout") or [])] if isinstance(f, dict) else None
        if (not isinstance(q, str) or nums is None
                or not (isinstance(f.get("hash"), str) and _HASH.fullmatch(f["hash"]))
                or (_int(f.get("mutants")) or 0) < 1
                or not all(_int(x) is not None and x >= 0 for x in (f.get("ms_rerun"),
                                                                     f.get("ms_carried")))
                or not all(_int(n) is not None and n >= 1 for n in nums)
                or len(set(nums)) != len(nums)):
            raise LedgerError("the ledger's entry for %r is malformed" % (q,))
    return ledger


def carried_functions(funcs: dict[str, dict[str, Any]], ledger: dict[str, Any],
                      keep: set[str]) -> dict[str, list[str]]:
    """qualified -> the names it carries: unchanged hash and mutant count, not kept back.

    A carried number with no mutant at this commit means the ledger does not
    describe this generator's output, so the whole ledger is refused.
    """
    out: dict[str, list[str]] = {}
    for q, entry in sorted(ledger["functions"].items()):
        nums = sorted([*(entry.get("survived") or []), *(entry.get("timeout") or [])])
        here = funcs.get(q)
        if not nums or here is None or q in keep:
            continue
        if here["hash"] != entry["hash"] or len(here["keys"]) != entry["mutants"]:
            continue
        names = ["%s%s%d" % (q, MUTANT_SEP, n) for n in nums]
        generated = set(here["keys"])
        missing = [n for n in names if n not in generated]
        if missing:
            raise LedgerError("the ledger carries %s, which is not generated here although "
                              "%s's hash and count match" % (missing[0], q))
        out[q] = names
    return out


class _Unit:
    """One packable slice: a selector (pattern) or a run of exact names."""

    __slots__ = ("names", "pattern", "sort", "weight")

    def __init__(self, sort: str, weight: float, pattern: str | None = None,
                 names: list[str] | None = None):
        self.sort, self.weight, self.pattern, self.names = sort, weight, pattern, names or []

    @property
    def anchor(self) -> bool:
        # A file pattern or an exact name selects clean-run tests; a bin of
        # function patterns alone selects none and pays the whole-suite clean
        # run (mutation_shards.FIXED_MINUTES' 11.3-min function-only preamble).
        return bool(self.names) or (self.pattern is not None and self.pattern.endswith(".*")
                                    and MUTANT_SEP not in self.pattern
                                    and not self.pattern.endswith(".x%s*" % ms.METHODS))

    def selectors(self) -> list[str]:
        return list(self.names) if self.names else [self.pattern or ""]


def selector_keys(selectors: list[str], keys: list[str]) -> list[str]:
    """The keys ``selectors`` match, read structurally (``keys`` sorted).

    Every selector a ledgered plan writes is either an exact name or a literal
    followed by one ``*``; for those, fnmatch is exactly "equal" or "starts
    with", so a sorted list and bisect answer without fnmatching 54k keys
    against thousands of patterns. Any other shape raises: it is not one this
    planner writes. ``tests/unit/test_mutation_ledger.py`` cross-checks this
    against ``fnmatch.fnmatchcase`` itself.
    """
    out: list[str] = []
    for sel in selectors:
        literal = sel[:-1] if sel.endswith("*") else sel
        if not literal or _GLOB.search(literal):
            raise LedgerError("%r is not an exact name or a literal prefix" % (sel,))
        if literal is sel:
            i = bisect.bisect_left(keys, sel)
            if i < len(keys) and keys[i] == sel:
                out.append(sel)
            continue
        i = bisect.bisect_left(keys, literal)
        while i < len(keys) and keys[i].startswith(literal):
            out.append(keys[i])
            i += 1
    return out


def partition_problems(shards: list[list[str]], carried: list[str], keys: list[str]) -> list[str]:
    """Every generated key covered exactly once, by a shard's selectors or the carried list."""
    seen: dict[str, int] = {}
    problems: list[str] = []
    for i, shard in enumerate(shards):
        hit = selector_keys(shard, keys)
        if not hit:
            problems.append("shard %d matches no mutant (mutmut asserts on that)" % i)
        for k in hit:
            seen[k] = seen.get(k, 0) + 1
    known = set(keys)
    for k in carried:
        if k not in known:
            problems.append("carried %s is not generated" % k)
        seen[k] = seen.get(k, 0) + 1
    over = sorted(k for k, n in seen.items() if n > 1)
    gap = sorted(k for k in keys if k not in seen)
    if over:
        problems.append("%d mutants are selected twice, first %s" % (len(over), over[0]))
    if gap:
        problems.append("%d mutants are selected by nothing, first %s" % (len(gap), gap[0]))
    return problems


def pack_units(units: list[_Unit], shards: int, max_names: int) -> list[list[_Unit]]:
    """Longest-first into ``shards`` bins, by time, never past ``max_names`` names a bin.

    Two constraints, not one: a bin is chosen by load among the bins with room
    for the unit's names, and a named unit too big for any bin's room is split
    across the bins with the most room (exact names split anywhere). The
    caller has already made the total fit ``shards * max_names``. Then every
    bin is given an anchor (see ``_Unit.anchor``) by moving the lightest
    anchor from a bin that holds more than one. Deterministic: ties break on
    the unit's sort key and the bin index.
    """
    bins: list[list[_Unit]] = [[] for _ in range(shards)]
    load = [0.0] * shards
    names = [0] * shards
    for u in sorted(units, key=lambda u: (-u.weight, u.sort)):
        n = len(u.names)
        room = [i for i in range(shards) if names[i] + n <= max_names]
        if room:
            i = min(room, key=lambda i: (load[i], i))
            bins[i].append(u)
            load[i] += u.weight
            names[i] += n
            continue
        rest = list(u.names)
        per = u.weight / n
        while rest:
            i = min((i for i in range(shards) if names[i] < max_names),
                    key=lambda i: (load[i], -(max_names - names[i]), i))
            take = rest[: max_names - names[i]]
            rest = rest[len(take):]
            bins[i].append(_Unit(u.sort + "#%d" % len(rest), per * len(take), names=take))
            load[i] += per * len(take)
            names[i] += len(take)
    for i in range(shards):
        if any(u.anchor for u in bins[i]):
            continue
        donors = [j for j in range(shards) if sum(u.anchor for u in bins[j]) > 1]
        if not donors:
            raise LedgerError("shard %d would hold only function patterns" % i)
        j = max(donors, key=lambda j: (sum(u.anchor for u in bins[j]), -j))
        unit = min((u for u in bins[j] if u.anchor), key=lambda u: (u.weight, u.sort))
        if len(unit.names) + names[i] > max_names:
            raise LedgerError("shard %d would hold only function patterns" % i)
        bins[j].remove(unit)
        bins[i].append(unit)
        names[j] -= len(unit.names)
        names[i] += len(unit.names)
    return bins


def ledgered_full(root: Path, meta: dict[str, dict[str, Any]], ledger: dict[str, Any], *,
                  keep: set[str], shards: int, max_names: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """The full set with the ledger's survivors left out, and what was carried.

    Raises LedgerError, saying why, whenever the plan would not be sound or
    would not run: then the caller keeps the plain plan. Never returns a set
    that carries nothing (that is the plain plan's job).
    """
    funcs = functions_of(meta)
    keys = sorted(k for f in funcs.values() for k in f["keys"])
    carried = carried_functions(funcs, ledger, keep)
    if not carried:
        raise LedgerError("nothing to carry: no function with a recorded survivor is "
                          "unchanged and outside the diff scope")
    known = ledger["functions"]
    total_ms = sum(f["ms_rerun"] + f["ms_carried"] for f in known.values())
    total_n = sum(f["mutants"] for f in known.values())
    mean = total_ms / total_n if total_n else 1.0

    def full_ms(q: str) -> float:
        f = known.get(q)
        if f is not None and f["mutants"] == len(funcs[q]["keys"]):
            return float(f["ms_rerun"] + f["ms_carried"])
        return mean * len(funcs[q]["keys"])

    # Over the name budget: un-carry the functions whose survivors are
    # cheapest to re-run until the named mutants fit. Always sound, only slower.
    uncarried = 0
    budget = shards * max_names

    def named() -> int:
        return sum(len(funcs[q]["keys"]) - len(c) for q, c in carried.items())

    for q in sorted(carried, key=lambda q: (known[q]["ms_carried"], q)):
        if named() <= budget:
            break
        del carried[q]
        uncarried += 1
    if not carried:
        raise LedgerError("nothing left to carry under the name budget")

    carried_names = {n for c in carried.values() for n in c}
    by_file: dict[str, list[str]] = {}
    for q, f in funcs.items():
        by_file.setdefault(f["file"], []).append(q)
    files = sorted(ms.rel_name(root, p) for p in ms.source_files(root) if not ms.is_init(p))
    even = sum(full_ms(q) for q in funcs) / shards
    units: list[_Unit] = []
    for rel in files:
        module = module_of(rel)
        qs = sorted(by_file.get(rel, []))
        weight = sum((known[q]["ms_rerun"] if q in carried else full_ms(q)) for q in qs)
        if not any(q in carried for q in qs):
            if weight <= even or len(qs) < 2:
                units.append(_Unit(rel, weight, pattern=module + ".*"))
            else:
                units.extend(_Unit("%s:%s" % (rel, funcs[q]["mangled"]), full_ms(q),
                                   pattern="%s%s*" % (q, MUTANT_SEP)) for q in qs)
            continue
        for q in qs:
            if q not in carried:
                units.append(_Unit("%s:%s" % (rel, funcs[q]["mangled"]), full_ms(q),
                                   pattern="%s%s*" % (q, MUTANT_SEP)))
                continue
            rest = [k for k in funcs[q]["keys"] if k not in carried_names]
            if not rest:
                continue
            w = float(known[q]["ms_rerun"])
            # Balance: a named function heavier than an even share is cut into
            # pieces, so one function does not set the slowest shard.
            pieces = max(1, min(len(rest), math.ceil(w / even) if even else 1))
            step = math.ceil(len(rest) / pieces)
            for p in range(0, len(rest), step):
                chunk = rest[p:p + step]
                units.append(_Unit("%s:%s:%06d" % (rel, funcs[q]["mangled"], p),
                                   w * len(chunk) / len(rest), names=chunk))
    bins = pack_units(units, shards, max_names)
    plan_shards = [sorted(s for u in b for s in u.selectors()) for b in bins]
    if any(not s for s in plan_shards):
        raise LedgerError("the pack left a shard empty")
    widest = max(sum(len(u.names) for u in b) for b in bins)
    if widest > max_names:
        raise LedgerError("a shard names %d mutants, over %d" % (widest, max_names))
    problems = partition_problems(plan_shards, sorted(carried_names), keys)
    if problems:
        raise LedgerError("the ledgered pack is not a partition: " + "; ".join(problems[:3]))
    loads = [round(sum(u.weight for u in b)) for b in bins]
    safe, lines = ms.headroom_report(loads, STEP_TIMEOUT_MINUTES)
    if not safe:
        raise LedgerError("the ledgered pack fails headroom: " + lines[-1])
    timeouts = sum(len(known[q].get("timeout") or []) for q in carried)
    stats = {"carried": len(carried_names), "carried_survived": len(carried_names) - timeouts,
             "carried_timeouts": timeouts,
             "carried_ms": sum(known[q]["ms_carried"] for q in carried),
             "functions_carried": len(carried), "uncarried": uncarried,
             "max_names": widest, "slowest_tail_minutes": round(
                 ms.tail_minutes(max(loads)), 1),
             # The model's median job time per shard (mutation_shards.runner_minutes):
             # what the run's wall clock is made of, to compare with the first real run.
             "shard_minutes": [round(ms.runner_minutes(x), 1) for x in loads]}
    return {"shards": plan_shards, "mutants": len(keys),
            "carried": sorted(carried_names)}, stats


# --------------------------------------------------------------------------
# stamp / apply (the planner)
# --------------------------------------------------------------------------

def _read_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path | str, data: Any, indent: int | None = 1) -> None:
    """Whole or not at all: a plan half-written would fail every shard's ``patterns``."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=indent) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def stamp(plan: dict[str, Any], root: Path) -> dict[str, Any]:
    """The plan, with the generator key and machinery digest the writer will copy."""
    plan["generator"] = {"key": generator_key(root), "machinery": machinery_digest(root)}
    return plan


def eligibility(plan: dict[str, Any], env: dict[str, str]) -> str | None:
    """Why this plan may not be ledgered, or None. Python's own check, on top of the workflow's."""
    event = env.get("GITHUB_EVENT_NAME", "")
    if event not in READ_EVENTS:
        return "a %s run never reads a ledger" % (event or "?")
    if event not in tokens(env.get("MUTATION_LEDGER")):
        return "the repository variable MUTATION_LEDGER does not name %s" % event
    if env.get("GITHUB_RUN_ATTEMPT") != "1":
        attempt = re.sub(r"[^0-9]", "", env.get("GITHUB_RUN_ATTEMPT", ""))[:6]
        return "a re-run never uses a ledger (attempt %s)" % (attempt or "?")
    if plan.get("ledger_eligible") is not True:
        return "this plan is not eligible (a full-run trigger, or a plan that never says)"
    if plan.get("gate_set") != "full" or "advisory" in plan:
        return "the plan does not gate on a plain full set"
    full = (plan.get("sets") or {}).get("full")
    if not isinstance(full, dict) or "carried" in full:
        return "the plan has no plain full set"
    return None


def apply(plan: dict[str, Any], *, root: Path, ledger_path: Path | None, run_id: str,
          mutants: Path, env: dict[str, str], now: datetime,
          key: dict[str, str] | None = None, machinery: str | None = None,
          max_names: int | None = None) -> dict[str, Any]:
    """The plan, ledgered if every check passes; otherwise plain with ``ledger not used:``.

    ``sets.full`` is left byte-for-byte as it was unless the ledger is used,
    so the merge's "a plan that carries nothing is the committed pack" check
    holds for every plan this returns.
    """
    def plain(why: str) -> dict[str, Any]:
        plan["ledger"] = {"used": False, "why": why}
        plan.setdefault("reasons", []).append("ledger not used: " + why)
        return plan

    try:
        why = eligibility(plan, env)
        if why:
            return plain(why)
        if ledger_path is None or not ledger_path.is_file():
            return plain("no ledger was downloaded (see the mutation-ledger job)")
        if not re.fullmatch(r"[1-9][0-9]{0,19}", run_id or ""):
            return plain("the mutation-ledger job named no run")
        ledger = check_ledger(_read_json(ledger_path))
        source = ledger["source"]
        if source["run_id"] != int(run_id):
            return plain("the ledger is run %d's, not run %s's, which the reader chose"
                         % (source["run_id"], run_id))
        written = _when(source["created_at"])
        if written is None:     # check_ledger already refused this; mypy cannot know
            return plain("the ledger's source has no usable created_at")
        age = now - written
        if not timedelta(minutes=-5) <= age <= MAX_LEDGER_AGE:
            return plain("the ledger was written %.0f h ago, outside 0-%d days"
                         % (age.total_seconds() / 3600, MAX_LEDGER_AGE.days))
        key = key if key is not None else generator_key(root)
        if ledger.get("key") != key:
            return plain("the generator key differs (%s)" % ", ".join(
                k for k in sorted(set(key) | set(ledger.get("key") or {}))
                if (ledger.get("key") or {}).get(k) != key.get(k)))
        machinery = machinery if machinery is not None else machinery_digest(root)
        if ledger.get("machinery") != machinery:
            return plain("the mutation machinery changed since the ledger was written")
        diff = (plan.get("sets") or {}).get("diff")
        keep = set(diff.get("functions") or []) if isinstance(diff, dict) else set()
        shards = len(plan["sets"]["full"]["shards"])
        full, stats = ledgered_full(root, read_meta(mutants), ledger, keep=keep, shards=shards,
                                    max_names=(max_names if max_names is not None
                                               else _diff().MAX_NAMES))
    except Exception as exc:    # ledger trouble never fails the planner: it plans plain
        return plain("%s: %s" % (type(exc).__name__, exc))
    full["ledger"] = {"used": True, "run_id": source["run_id"], "event": source["event"],
                      "created_at": source["created_at"], "head_sha": source.get("head_sha"),
                      "age_hours": round(age.total_seconds() / 3600, 1), **stats}
    plan["sets"]["full"] = full
    plan["ledger"] = {"used": True}
    plan.setdefault("reasons", []).append(
        "ledgered: %d survivors in %d functions carried from whole-codebase run %d "
        "(%s, %.0f h old), %d un-carried for the name cap; %d shards, at most %d names"
        % (stats["carried"], stats["functions_carried"], source["run_id"], source["event"],
           full["ledger"]["age_hours"], stats["uncarried"], shards, stats["max_names"]))
    return plan


# --------------------------------------------------------------------------
# write / selfcheck (the `mutation` job of a green whole-codebase run)
# --------------------------------------------------------------------------

def build(meta: dict[str, dict[str, Any]], plan: dict[str, Any], env: dict[str, str],
          now: datetime, status_of: Callable[[Any], str]) -> dict[str, Any]:
    """A ledger from a green, plain, whole-codebase run's merged results."""
    if env.get("GITHUB_EVENT_NAME") not in WHOLE_CODEBASE_EVENTS:
        raise LedgerError("only a schedule or workflow_dispatch run writes a ledger")
    if env.get("GITHUB_REF") != "refs/heads/" + MAIN:
        raise LedgerError("only a run on main writes a ledger")
    if WRITE not in tokens(env.get("MUTATION_LEDGER")):
        raise LedgerError("the repository variable MUTATION_LEDGER does not name write")
    full = (plan.get("sets") or {}).get("full")
    if plan.get("gate_set") != "full" or not isinstance(full, dict) or "carried" in full:
        raise LedgerError("the run's plan is not a plain full plan")
    generator = plan.get("generator")
    if not isinstance(generator, dict) or not isinstance(generator.get("key"), dict) \
            or not isinstance(generator.get("machinery"), str):
        raise LedgerError("the plan carries no generator stamp")
    run_id = _int(int(env["GITHUB_RUN_ID"])) if env.get("GITHUB_RUN_ID", "").isdigit() else None
    if run_id is None:
        raise LedgerError("no GITHUB_RUN_ID")
    functions: dict[str, Any] = {}
    killed = denominator = 0
    for q, f in sorted(functions_of(meta).items()):
        data = meta[f["file"]]
        if not isinstance(f.get("hash"), str) or not _HASH.fullmatch(f["hash"]):
            raise LedgerError("%s has no function hash in its .meta" % q)
        entry = {"hash": f["hash"], "mutants": len(f["keys"]), "ms_rerun": 0, "ms_carried": 0,
                 "survived": [], "timeout": []}
        for k in f["keys"]:
            code = data["codes"][k]
            if code is None:
                raise LedgerError("%s is unrun in the merged results" % k)
            status = status_of(code)
            if status != "skipped":
                denominator += 1
            killed += status == "killed"
            spent = data["durations"].get(k)
            ms_ = round(spent * 1000) if isinstance(spent, (int, float)) and spent >= 0 else 0
            if status in CARRIED_STATUSES:
                entry[status].append(number_of(k))
                entry["ms_carried"] += ms_
            else:
                entry["ms_rerun"] += ms_
        functions[q] = entry
    return {"kind": KIND, "schema": SCHEMA,
            "source": {"run_id": run_id, "run_attempt": _int(int(env.get("GITHUB_RUN_ATTEMPT", "0")
                                                                 or 0)),
                       "event": env["GITHUB_EVENT_NAME"], "branch": MAIN,
                       "head_sha": env.get("GITHUB_SHA", ""), "created_at": _iso(now)},
            "key": generator["key"], "machinery": generator["machinery"],
            "score": {"killed": killed, "denominator": denominator},
            "functions": functions}


_PREFIX = "mutation-full-shard-"


def simulate_shards(meta: dict[str, dict[str, Any]], shards: list[list[str]], out: Path) -> None:
    """Each shard's ``.meta``, as mutmut would leave it, for a plan run over ``meta``'s results.

    A key is run (its code and duration) only when one of the shard's
    selectors fnmatches it, as mutmut's own filter does (``fnmatch``), so
    this does not lean on ``selector_keys`` -- the reading it is checking.
    """
    for i, shard in enumerate(shards):
        match = re.compile("|".join("(?:%s)" % fnmatch.translate(s) for s in shard))
        d = out / ("%s%d" % (_PREFIX, i))
        d.mkdir(parents=True)
        for rel, data in meta.items():
            ran = {k for k in data["codes"] if match.match(k)}
            dest = d / (rel + ".meta")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps({
                "exit_code_by_key": {k: (c if k in ran else None) for k, c in data["codes"].items()},
                "hash_by_function_name": data["hashes"],
                "type_check_error_by_key": {},
                "durations_by_key": {k: v for k, v in data["durations"].items() if k in ran},
                "estimated_durations_by_key": {}}), encoding="utf-8")


def selfcheck(root: Path, meta: dict[str, dict[str, Any]], ledger: dict[str, Any],
              plan: dict[str, Any], status_of: Callable[[Any], str], *, max_names: int,
              merge: Callable[[argparse.Namespace], int] | None = None) -> list[str]:
    """Problems found by running tonight's commit as a ledgered PR run would, or [].

    Plans this commit against the ledger just written (every function is
    unchanged, so the most it can carry), simulates the shards that plan
    names over tonight's real results, runs the real ``merge --plan`` with its
    injection, and checks that every row came back with tonight's verdict --
    carried ones as exactly ``CARRIED_EXIT`` -- and that killed and the
    denominator did not move (the carried rows are tonight's own survivors
    and timeouts, none of them killed). A plain nightly runs none of the
    ledgered planner or the plan-derived merge otherwise, so this is where a
    bug there shows, a day before any PR or push could lean on it.
    """
    merge = merge or ms.cmd_merge
    shards = len(plan["sets"]["full"]["shards"])
    full, stats = ledgered_full(root, meta, check_ledger(ledger), keep=set(), shards=shards,
                                max_names=max_names)
    full["ledger"] = {"used": True, "run_id": ledger["source"]["run_id"]}
    problems: list[str] = []
    want = {k: c for data in meta.values() for k, c in data["codes"].items()}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        simulate_shards(meta, full["shards"], work / "shards")
        _write_json(work / "plan.json", {"gate_set": "full", "sets": {"full": full}})
        args = argparse.Namespace(root=str(root), shards=shards, into=str(work / "merged"),
                                  source=str(work / "shards"), prefix=_PREFIX,
                                  plan=str(work / "plan.json"), set="full")
        with contextlib.redirect_stdout(sys.stderr):
            rc = merge(args)
        if rc != 0:
            return ["merge --plan refused the ledgered dry run (exit %d)" % rc]
        got = {k: c for data in read_meta(work / "merged").values()
               for k, c in data["codes"].items()}
    carried = set(full["carried"])
    if set(got) != set(want):
        problems.append("the merge returned %d keys, not %d" % (len(got), len(want)))
    wrong = sorted(k for k in want if got.get(k) != (ms.CARRIED_EXIT if k in carried else want[k]))
    if wrong:
        problems.append("%d rows came back changed, first %s" % (len(wrong), wrong[0]))
    if status_of(ms.CARRIED_EXIT) != "survived":
        problems.append("the installed mutmut does not read %d as survived" % ms.CARRIED_EXIT)

    def score(codes: dict[str, Any]) -> tuple[int, int]:
        statuses = [status_of(c) for c in codes.values()]
        return (sum(s == "killed" for s in statuses), sum(s != "skipped" for s in statuses))

    if score(got) != score(want):
        problems.append("killed/denominator moved from %d/%d to %d/%d" % (*score(want), *score(got)))
    if not problems:
        print("selfcheck: ledgered dry run of this commit carried %d rows from %d functions "
              "into %d shards (at most %d names, slowest tail %.1f min); merge --plan gave "
              "back every verdict, %d/%d killed" % (stats["carried"], stats["functions_carried"],
                                                     shards, stats["max_names"],
                                                     stats["slowest_tail_minutes"], *score(got)))
    return problems


# --------------------------------------------------------------------------
# find (the `mutation-ledger` job): stdlib only
# --------------------------------------------------------------------------

API_ROOT = "https://api.github.com/repos/"
PER_PAGE = 100
TIMEOUT = 15


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect, so the token goes to api.github.com and nowhere else."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def make_api(repo: str, token: str) -> Callable[[str], Any]:
    http = urllib.request.build_opener(_NoRedirect)

    def api(path: str) -> Any:
        req = urllib.request.Request(  # noqa: S310  API_ROOT is a literal https prefix
            API_ROOT + repo + "/" + path,
            headers={"Authorization": "Bearer " + token,
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28",
                     "User-Agent": "boost-mutation-ledger"})
        with http.open(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())

    return api


def _page(listing: Any, key: str) -> list[dict[str, Any]]:
    """One page of ``key``, or ValueError when the body is not one, or when it is truncated."""
    items = listing.get(key) if isinstance(listing, dict) else None
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise ValueError("the response has no %s list" % key)
    total = listing.get("total_count")
    if _int(total) is not None and total > len(items):
        raise ValueError("the %s listing is longer than one page" % key)
    return items


def _owned(item: dict[str, Any], run_id: int, path: tuple[str, ...]) -> bool:
    owner: Any = item
    for k in path:
        owner = owner.get(k) if isinstance(owner, dict) else None
    return owner is None or owner == run_id


class Found:
    def __init__(self, run_id: int | None, reason: str, created_at: str = ""):
        self.run_id, self.reason, self.created_at = run_id, reason, created_at


def find(api: Callable[[str], Any], env: dict[str, str], now: datetime) -> Found:
    """Which whole-codebase run's ledger this run may read, or why none (design: "Reader").

    Walks completed ``schedule`` and ``workflow_dispatch`` runs of ci.yml on
    main from the last ``MAX_LEDGER_AGE`` days, newest first. A run whose
    ``mutation`` job (latest attempt) is not green stops the walk: no ledger
    is used past a red whole-codebase verdict. A run with exactly one
    ``inherited-tree-`` marker and nothing else is an idle night and is
    stepped over. Any other run is real, and its ledger -- exactly one,
    unexpired -- is the answer or there is none: the walk never reaches past a
    real run to an older ledger. Two markers, any malformed listing, any API
    error: no ledger.
    """
    event = env.get("GITHUB_EVENT_NAME", "")
    if event not in READ_EVENTS:
        return Found(None, "a %s run never reads a ledger" % (re.sub(r"[^a-z_]", "", event) or "?"))
    if event not in tokens(env.get("MUTATION_LEDGER")):
        return Found(None, "the repository variable MUTATION_LEDGER does not name %s" % event)
    if env.get("GITHUB_RUN_ATTEMPT") != "1":
        return Found(None, "a re-run never uses a ledger")
    try:
        if event == PULL_REQUEST:
            number = env.get("PR_NUMBER", "")
            if not number.isdigit():
                return Found(None, "no pull request number")
            labels = api("pulls/%s" % number).get("labels")
            if not isinstance(labels, list):
                raise ValueError("the pull request has no labels list")
            if any(isinstance(lab, dict) and lab.get("name") == NO_LEDGER_LABEL for lab in labels):
                return Found(None, "the pull request carries the label %s" % NO_LEDGER_LABEL)
        floor = now - MAX_LEDGER_AGE
        runs: list[tuple[datetime, int, dict[str, Any]]] = []
        for whole in WHOLE_CODEBASE_EVENTS:
            listing = api("actions/workflows/ci.yml/runs?branch=%s&event=%s&status=completed"
                          "&created=%%3E%%3D%s&per_page=%d"
                          % (MAIN, whole, floor.date().isoformat(), PER_PAGE))
            for run in _page(listing, "workflow_runs"):
                when, ident = _when(run.get("created_at")), _int(run.get("id"))
                if run.get("event") != whole or run.get("head_branch") != MAIN \
                        or when is None or ident is None:
                    raise ValueError("a %s window listing returned a run it did not ask for"
                                     % whole)
                if when >= floor:
                    runs.append((when, ident, run))
        for when, ident, run in sorted(runs, key=lambda t: (t[0], t[1]), reverse=True):
            where = "whole-codebase run %d (%s, %s)" % (ident, run["event"], _iso(when))
            jobs = [j for j in _page(api("actions/runs/%d/jobs?filter=latest&per_page=%d"
                                         % (ident, PER_PAGE)), "jobs")
                    if j.get("name") == "mutation"]
            if len(jobs) != 1 or not _owned(jobs[0], ident, ("run_id",)):
                return Found(None, "%s lists %d mutation jobs" % (where, len(jobs)))
            if jobs[0].get("status") != "completed" or jobs[0].get("conclusion") != "success":
                return Found(None, "%s is red (mutation: %s), and no ledger is used past a "
                             "red whole-codebase run" % (where, re.sub(
                                 r"[^a-z_]", "", str(jobs[0].get("conclusion"))) or "?"))
            artifacts = _page(api("actions/runs/%d/artifacts?per_page=%d" % (ident, PER_PAGE)),
                              "artifacts")
            if not all(_owned(a, ident, ("workflow_run", "id")) for a in artifacts):
                raise ValueError("run %d's artifact listing holds another run's artifact" % ident)
            names = [a.get("name") for a in artifacts]
            markers = [n for n in names if isinstance(n, str)
                       and n.startswith((MUTATED_TREE, INHERITED_TREE))]
            ledgers = [a for a in artifacts if a.get("name") == ARTIFACT]
            if len(markers) > 1:
                return Found(None, "%s carries %d markers, so what it was is ambiguous"
                             % (where, len(markers)))
            if not ledgers and len(markers) == 1 and markers[0].startswith(INHERITED_TREE):
                continue        # an idle night: it mutated nothing, and inherits an older run
            if len(ledgers) != 1 or ledgers[0].get("expired") is not False:
                return Found(None, "the newest real %s wrote no usable ledger (%d found%s)"
                             % (where, len(ledgers), ", expired" if len(ledgers) == 1 else ""))
            return Found(ident, "ledger of %s" % where, _iso(when))
        return Found(None, "no green real whole-codebase run on main in the last %d days"
                     % MAX_LEDGER_AGE.days)
    except Exception as exc:    # any failure is "no ledger", never a failed job
        return Found(None, "the API could not be read (%s)" % type(exc).__name__)


# --------------------------------------------------------------------------
# the CLI
# --------------------------------------------------------------------------

def _one_line(text: str) -> str:
    return re.sub(r"[\r\n]", " ", text)[:500]


def _now() -> datetime:
    return datetime.now(UTC)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find", help="which run's ledger this run may read (always exits 0)")
    f.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    s = sub.add_parser("stamp", help="record the generator key and machinery digest in a plan")
    s.add_argument("--plan", required=True)
    s.add_argument("--root", default=str(ROOT))
    a = sub.add_parser("apply", help="ledger a plain full plan in place, or say why not")
    a.add_argument("--plan", required=True)
    a.add_argument("--ledger", default="")
    a.add_argument("--run-id", default="")
    a.add_argument("--meta", default="mutants", help="the planner's mutants/ tree")
    a.add_argument("--root", default=str(ROOT))
    w = sub.add_parser("write", help="build a ledger from a green run's merged results")
    w.add_argument("--meta", default="mutants")
    w.add_argument("--plan", required=True)
    w.add_argument("--out", required=True)
    c = sub.add_parser("selfcheck", help="dry-run tonight's commit as a ledgered run would")
    c.add_argument("--meta", default="mutants")
    c.add_argument("--plan", required=True)
    c.add_argument("--ledger", required=True)
    c.add_argument("--root", default=str(ROOT))
    args = ap.parse_args(argv)
    env = dict(os.environ)

    if args.cmd == "find":
        repo = env.get("GITHUB_REPOSITORY", "")
        api = make_api(repo, env.get("GITHUB_TOKEN", ""))
        found = find(api, env, _now())
        print("mutation-ledger: %s" % _one_line(found.reason))
        if args.github_output:
            with open(args.github_output, "a", encoding="utf-8") as out:
                out.write("run_id=%s\nreason=%s\ncreated_at=%s\n" % (
                    found.run_id or "", _one_line(found.reason), found.created_at))
        return 0
    if args.cmd == "stamp":
        try:
            _write_json(args.plan, stamp(_read_json(args.plan), Path(args.root)))
        except Exception as exc:    # an unstamped plan only means no ledger is written
            print("::warning::mutation_ledger stamp: %s: %s"
                  % (type(exc).__name__, _one_line(str(exc))))
        return 0
    if args.cmd == "apply":
        plan = _read_json(args.plan)     # unreadable: exit 1 and the file untouched
        plan = apply(plan, root=Path(args.root),
                     ledger_path=Path(args.ledger) if args.ledger else None,
                     run_id=args.run_id, mutants=Path(args.meta), env=env, now=_now())
        _write_json(args.plan, plan)
        print("mutation_ledger apply: %s" % _one_line(plan["reasons"][-1]))
        return 0

    md = _diff()
    try:
        meta = read_meta(Path(args.meta))
        plan = _read_json(args.plan)
        if args.cmd == "write":
            ledger = build(meta, plan, env, _now(), md.status_of)
            _write_json(args.out, ledger, indent=None)
            carried = sum(len(f["survived"]) + len(f["timeout"]) for f in ledger["functions"].values())
            print("mutation_ledger write: %d functions, %d carried survivors and timeouts, "
                  "run %d" % (len(ledger["functions"]), carried, ledger["source"]["run_id"]))
            return 0
        problems = selfcheck(Path(args.root), meta, _read_json(args.ledger), plan, md.status_of,
                             max_names=md.MAX_NAMES)
    except (LedgerError, OSError, ValueError, KeyError, TypeError) as exc:
        problems = ["%s: %s" % (type(exc).__name__, exc)]
    for p in problems:
        print("::warning::mutation_ledger %s: %s" % (args.cmd, _one_line(p)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
