#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Gate: the required-status-check list must match the jobs that actually run.

Branch protection is configured in the GitHub UI, so the list of required checks
existed only as prose in CONTRIBUTING.md — and it drifted. Jobs were added to CI
that were never added to the list, so a PR could merge to `main` with them red,
and `main` cuts a PyPI release on every merge.

`.github/required-checks.txt` is now the source of truth and this script keeps it
honest. It fails when:

  * a required name is not a job that runs on ``pull_request`` (removed, renamed,
    or never existed),
  * a check name is **ambiguous** — the same name produced by more than one
    workflow. GitHub matches required checks by name, so a duplicate cannot be
    required unambiguously. Three names collided here when this was written
    (``lint`` in ci/markdownlint/theme-lint, ``audit`` in lighthouse/pip-audit,
    ``analyze`` in codeql/sonarcloud), which is why the prose list saying
    "require `lint`" was not actually implementable, or
  * a required name comes from a workflow with no ``merge_group:`` trigger. The
    merge queue evaluates required checks against its own temporary
    ``gh-readonly-queue/*`` ref rather than against the pull request, so such a
    check never reports there and every enqueued PR waits forever. Nothing is
    broken until the queue is switched on — which is a repo Setting, invisible
    from the tree — so this is checked ahead of time rather than discovered
    afterwards, or
  * a required name comes from a workflow whose ``pull_request:`` trigger is
    narrowed by ``paths:``/``paths-ignore:`` or by a ``types:`` list that omits
    the ordinary open/push events. This is the failure mode that actually bricks
    a repository: when a PR touches no matching path GitHub creates no check run
    at all, so branch protection waits for a status that is never coming and the
    PR can never merge. It is not hypothetical — the first version of this list
    required ``validate``, ``markdown-lint``, ``theme-lint`` and ``vale``, all
    four of which are path-filtered, and this gate passed it, or
  * a required name is not a check its job actually reports. GitHub never
    reports a matrix job under its bare name, only one check per leg —
    ``tests (ubuntu-latest, 3.13)`` — so the matrix is expanded here the way
    GitHub expands it (axes in key order, ``exclude`` then ``include``) and a
    required leg must be one of the results. Before this, any ``job
    (anything)`` passed as long as ``job`` existed, so dropping 3.12 from the
    matrix or renaming macos-latest would have left required legs that never
    report — every PR waiting on "Expected — waiting for status" — with this
    gate still green. Requiring the bare name of a matrix job, or a leg of a job
    with no matrix, fails for the same reason. A job whose check names cannot
    be worked out — a matrix built by ``fromJSON(...)``, a ``name:`` using any
    expression but ``${{ matrix.KEY }}`` — fails when something requires it,
    rather than being guessed at, or
  * a required check is advisory: its job-level ``continue-on-error`` is
    literal ``true``, or ``${{ matrix.KEY == 'VALUE' }}`` true for that leg.
    GitHub lets the run pass when such a job fails, and publish.yml releases
    on a successful ci run, so a required check must be one that can fail its
    run. That one expression form is the only one evaluated; any other
    ``continue-on-error`` on a job something requires fails closed, or
  * a required name is not a check a reusable-workflow call reports. A job
    that calls one reports only ``caller / callee job``, never its own name,
    so requiring the bare caller fails, and so does ``job / x`` for a job that
    calls nothing. A callee in this repository (``uses: ./...`` or ``$/...``) is read like
    any workflow, so the callee job must exist and must not be advisory; one
    in another repository cannot be read from here, and any ``caller / job``
    is accepted for it.

Job-level ``if:`` is not modelled: every leg counts as reporting on every pull
request, whatever its job's ``if:`` says.

The triggers are read line by line (the regexes below) and the jobs with
PyYAML. ``make lint`` gets it from the requirements/lint-tools.txt lock (as
xenon's dependency, not one of its own) and the suite that runs this script
against the real tree from requirements/test-tools.txt. If it cannot be
imported the gate exits rather than skipping the matrix check;
``--print-api``, ``--print-ruleset`` and ``--verify-remote`` read only the
required list and do not need it.

PyYAML reads YAML 1.1, and GitHub does not type every unquoted value the same
way, so a matrix value or ``name:`` the two may read or print differently is
refused rather than guessed at — quoting it is the fix (see
:class:`Unquoted`). ``include``/``exclude`` likewise never compare values of
different types.

It refuses to report success if it parsed no jobs at all, so a parser that
silently stops matching fails the gate instead of passing it vacuously.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
CONFIG = ROOT / ".github" / "required-checks.txt"

# `main` is protected TWICE: by a classic branch protection and by a repository
# ruleset. They are independent objects with independent lists, and applying the
# file to one leaves the other untouched — which is how the ruleset came to be
# missing `bdd`, `evals` and `onnx-inference` while this script reported the
# config clean. It was checking the file against the *workflows*, and emitting a
# payload for the classic endpoint only; nothing here had ever heard of a
# ruleset.
#
# Which mechanism actually binds is the part that made the gap expensive rather
# than untidy. The classic protection sets `enforce_admins: false`, so it does
# not apply to the identity that merges here; the ruleset carries
# `bypass_actors: []`, so it applies to everyone. The three checks missing from
# the ruleset were therefore the three that nothing enforced — among them
# `evals`, the retrieval-quality floor, and `onnx-inference`, whose entry in
# required-checks.txt says in as many words that the failure it catches is
# silent.
GITHUB_API = "https://api.github.com"
REPO = "jonnyeclectic/boost"
BRANCH = "main"
# GitHub Actions' app id. A ruleset records which app must produce each context;
# leaving it out lets any app satisfy a check by name, which is a weaker gate
# than the one the file describes.
ACTIONS_APP_ID = 15368

# Any `${{ ... }}` expression, and the one kind a job's `name:` may use here:
# `${{ matrix.KEY }}`, which GitHub substitutes per leg instead of appending
# the `(v1, v2)` suffix.
_EXPR = re.compile(r"\$\{\{.*?\}\}", re.S)
_NAME_MATRIX_REF = re.compile(r"\$\{\{\s*matrix\.([A-Za-z_][\w-]*)\s*\}\}")
# The only job-level continue-on-error expression evaluated — the form ci.yml's
# tests job uses to make its 3.15 cells advisory.
_COE_MATRIX_EQ = re.compile(r"\$\{\{\s*matrix\.([A-Za-z_][\w-]*)\s*==\s*'([^']*)'\s*\}\}")
# A string GitHub's loose `==` can cast to a number: "any legal JSON number".
_JSON_NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")
# The plain scalars PyYAML and GitHub type alike and print alike (see
# Unquoted): the six spellings of a boolean, and an integer written plainly in
# at most 15 digits.
_GH_BOOLS = {"true": True, "True": True, "TRUE": True,
             "false": False, "False": False, "FALSE": False}
_PLAIN_INT = re.compile(r"0|-?[1-9][0-9]{0,14}")
# The YAML 1.2 core schema's numbers. A plain scalar PyYAML keeps as a string
# — `1e3`, `09`, `0o17`, `1.0e3` — but that matches one of these is a number
# to a YAML 1.2 reader.
_CORE_NUMBER = re.compile(
    r"[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+"
    r"|[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?"
    r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN)")
# What a call to a reusable workflow in another repository reports after
# `caller / `: its jobs cannot be read from here, so any job name is accepted.
ANY_JOB = "<any job>"
# actions/runner JobNameBuilder: a longer leg name is cut to 97 + "...".
MAX_CHECK_NAME = 100
# "the top-level caller workflow and up to nine levels of reusable workflows"
# (docs.github.com, Reuse workflows > Nesting reusable workflows). Deeper is a
# cycle or an error either way.
MAX_CALL_DEPTH = 9
# The `  pull_request:` trigger line itself, capturing any same-line remainder.
_PR_TRIGGER = re.compile(r"^  pull_request:\s*(.*)$")
# The `  merge_group:` trigger. Presence is all that matters — unlike
# pull_request there is nothing to narrow it with that would apply here.
_MG_TRIGGER = re.compile(r"^  merge_group:\s*(.*)$")

# How a workflow's pull_request trigger behaves.
PR_NONE = "none"          # no pull_request trigger at all
PR_ALWAYS = "always"      # fires on every PR — safe to require
PR_FILTERED = "filtered"  # fires only on some PRs — NEVER safe to require


def has_merge_group(header_lines: list[str]) -> bool:
    """Does this workflow declare a ``merge_group:`` trigger?

    Same narrow, stdlib-only parsing as everything else here: a top-level
    trigger key sits at exactly two spaces of indent inside the ``on:`` block.
    """
    return any(_MG_TRIGGER.match(line) for line in header_lines)


def pull_request_state(header_lines: list[str]) -> str:
    """Classify the ``pull_request:`` trigger in a workflow header.

    Returns one of :data:`PR_NONE`, :data:`PR_ALWAYS`, :data:`PR_FILTERED`.

    Stdlib-only and deliberately narrow, like the rest of this gate: find the
    ``  pull_request:`` line, then take the more-indented lines that follow it
    as its block. A ``paths:``/``paths-ignore:`` key means the trigger only
    fires when the PR touches matching files. A ``types:`` list means it only
    fires on the listed activity types — which is fine if it still covers the
    ordinary ``opened``/``synchronize`` pair, and disqualifying otherwise
    (``types: [labeled]`` is used here for the opt-in eval and fuzz jobs).
    """
    for i, line in enumerate(header_lines):
        match = _PR_TRIGGER.match(line)
        if not match:
            continue
        block = [match.group(1)] if match.group(1).strip() else []
        for nxt in header_lines[i + 1:]:
            if not nxt.strip() or nxt.lstrip().startswith("#"):
                continue
            if len(nxt) - len(nxt.lstrip()) <= 2:
                break  # dedented back to a sibling trigger
            block.append(nxt)
        text = "\n".join(block)
        if re.search(r"^\s*paths(-ignore)?\s*:", text, re.M):
            return PR_FILTERED
        # Covers both inline (`types: [opened, synchronize]`) and block
        # (`types:\n  - labeled`) forms — either way the names land in `text`.
        if (re.search(r"^\s*types\s*:", text, re.M)
                and not ("opened" in text and "synchronize" in text)):
            return PR_FILTERED
        return PR_ALWAYS
    return PR_NONE


class Unexpandable(ValueError):
    """A matrix, job name or continue-on-error this gate will not guess at."""


class Unquoted(NamedTuple):
    """A plain scalar that PyYAML and GitHub's workflow reader do not read alike.

    PyYAML is YAML 1.1, and GitHub types an unquoted value its own way. Per the
    review that found the gap — a reading of actions/runner's YamlObjectReader
    and NumberContextData, not a live run — only true/True/TRUE/false/False/
    FALSE are booleans there (``yes`` stays a string), ``010`` is ten rather
    than eight, ``1e3`` is a number rather than a string, ``1_000`` a string
    rather than a number, and numbers print with 15 significant digits (``8.0``
    as ``8``). So such a value keeps its text here and is refused wherever it
    would be printed into a check name: requiring the spelling this gate made
    up would pass and then never report. Quoting the value ends the argument.
    """

    text: str       # as written
    yaml11: object  # what PyYAML made of it

    def __repr__(self) -> str:
        return self.text


def _github_loader(yaml: Any) -> Any:
    """PyYAML's SafeLoader, leaving as :class:`Unquoted` every plain scalar it
    and GitHub may read differently."""
    base = yaml.SafeLoader

    def boolean(loader: Any, node: Any) -> object:
        if node.value in _GH_BOOLS:
            return _GH_BOOLS[node.value]
        return Unquoted(node.value, base.construct_yaml_bool(loader, node))

    def integer(loader: Any, node: Any) -> object:
        if _PLAIN_INT.fullmatch(node.value):
            return int(node.value)
        return Unquoted(node.value, base.construct_yaml_int(loader, node))

    def as_written(construct: Any) -> Any:
        # Floats print differently (8.0 here, 8 there); timestamps are not a
        # YAML 1.2 type at all.
        return lambda loader, node: Unquoted(node.value, construct(loader, node))

    def string(loader: Any, node: Any) -> object:
        value = base.construct_yaml_str(loader, node)
        if node.style is None and _CORE_NUMBER.fullmatch(value):
            return Unquoted(value, value)
        return value

    class Loader(base):
        pass

    for tag, construct in (("bool", boolean), ("int", integer),
                           ("float", as_written(base.construct_yaml_float)),
                           ("timestamp", as_written(base.construct_yaml_timestamp)),
                           ("str", string)):
        Loader.add_constructor("tag:yaml.org,2002:" + tag, construct)
    return Loader


def _render(value: object) -> str:
    """A matrix value as GitHub prints it in a check name: booleans lowercase."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _scalar(value: object, where: str) -> object:
    """A matrix value this gate can print as GitHub does: a string, boolean or integer."""
    if isinstance(value, Unquoted):
        raise Unexpandable("%s is the unquoted %s, which PyYAML loads as %r and GitHub "
                           "may read or print differently — quote it"
                           % (where, value.text, value.yaml11))
    if isinstance(value, str) and "${{" in value:
        raise Unexpandable("%s is the expression %s" % (where, value.strip()))
    if not isinstance(value, str | int):
        raise Unexpandable("%s is %r, a %s, and only strings, booleans and integers are "
                           "printed into check names here — quote it"
                           % (where, value, type(value).__name__))
    return value


def _same(a: object, b: object, where: str) -> bool:
    """Does matrix value ``a`` match ``b``, as include/exclude compare them?

    GitHub turns each entry into ``matrix['KEY'] == 'VALUE'``, whose ``==``
    compares strings ignoring case; other values of one type compare with
    ``==``. Across types — ``"3"`` and ``3``, ``true`` and ``1`` — GitHub's
    rule is not modelled, so this refuses.
    """
    if type(a) is not type(b):
        raise Unexpandable("%s compares %r with %r, values of different types, and how "
                           "GitHub matches those is not modelled here — quote both"
                           % (where, a, b))
    if isinstance(a, str) and isinstance(b, str):
        return a.casefold() == b.casefold()
    return a == b


def _entries(value: object, where: str) -> list[dict[str, object]]:
    """``include``/``exclude``: a list of mappings of scalars, or nothing."""
    if value is None:
        return []
    if isinstance(value, str):
        raise Unexpandable("%s is the expression %s" % (where, value.strip()))
    if not isinstance(value, list) or not all(isinstance(e, dict) for e in value):
        raise Unexpandable("%s is not a list of mappings" % where)
    return [{str(k): _scalar(v, "%s.%s" % (where, k)) for k, v in e.items()}
            for e in value]


def expand_matrix(matrix: object) -> list[dict[str, object]]:
    """Every combination GitHub runs for a ``strategy.matrix``, in its order."""
    return [combo for combo, _ in expand_legs(matrix)]


def expand_legs(matrix: object) -> list[tuple[dict[str, object], list[object]]]:
    """``(combination, the values its check name prints)`` for every leg.

    The rules are docs.github.com's ("Running variations of jobs in a
    workflow", and the ``jobs.<job_id>.strategy.matrix`` reference):

      * the axes multiply in key order, the first key varying slowest;
      * an ``exclude`` entry removes every combination it partially matches,
        and runs before ``include``, so ``include`` can add one back;
      * an ``include`` entry extends each remaining *original* combination
        that agrees with it on every original key it names — its new keys may
        overwrite ones an earlier ``include`` added, never an original value —
        and becomes a combination of its own when it extends none.

    A leg's check name prints its axis values only: what an ``include`` adds
    to a leg is not in its name (actions/runner MatrixBuilder names the leg
    before adding the extras; pytest-dev/pluggy run 41711073433 reports
    ``test (windows-py310)`` for a leg its include extends with three more
    keys). A leg an ``include`` entry adds on its own prints every value, the
    axis keys first.

    Raises :class:`Unexpandable` for anything computed at run time, an
    ``exclude`` naming a key that is not an axis, an entry key that differs
    from an axis only in case (GitHub matches keys ignoring case), and a
    comparison between values of different types.
    """
    if isinstance(matrix, str):
        raise Unexpandable("its matrix is the expression %s" % matrix.strip())
    if not isinstance(matrix, dict):
        raise Unexpandable("its matrix is not a mapping")
    axes: dict[str, list[object]] = {}
    for key, values in matrix.items():
        if key in ("include", "exclude"):
            continue
        if isinstance(values, str):
            raise Unexpandable("matrix.%s is the expression %s" % (key, values.strip()))
        if not isinstance(values, list) or not values:
            raise Unexpandable("matrix.%s is not a non-empty list" % key)
        axes[str(key)] = [_scalar(v, "matrix.%s" % key) for v in values]
    exclude = _entries(matrix.get("exclude"), "matrix.exclude")
    include = _entries(matrix.get("include"), "matrix.include")
    for entry in exclude:
        stray = [k for k in entry if k not in axes]
        if stray:
            raise Unexpandable("matrix.exclude names %s, which is not one of its axes"
                               % stray[0])
    folded = {k.casefold(): k for k in axes}
    for entry in include:
        for k in entry:
            if k not in axes and k.casefold() in folded:
                raise Unexpandable("matrix.include names %s, which differs from the axis "
                                   "%s only in case — spell it as the axis"
                                   % (k, folded[k.casefold()]))

    original = [dict(zip(axes, combo, strict=True))
                for combo in itertools.product(*axes.values())] if axes else []
    original = [c for c in original if not any(
        all(_same(c[k], v, "matrix.exclude") for k, v in e.items()) for e in exclude)]
    legs = [(combo, list(combo.values())) for combo in original]
    for entry in include:
        extended = False
        for combo in original:
            if all(_same(combo[k], v, "matrix.include")
                   for k, v in entry.items() if k in axes):
                combo.update((k, v) for k, v in entry.items() if k not in axes)
                extended = True
        if not extended:
            ordered = [k for k in axes if k in entry] + [k for k in entry if k not in axes]
            legs.append((dict(entry), [entry[k] for k in ordered]))
    return legs


def _matrix_key(combo: dict[str, object], key: str) -> str | None:
    """The key ``matrix.KEY`` reads in this leg, or None when the leg has none.

    GitHub looks context properties up ignoring case (an OrdinalIgnoreCase
    index in actions/runner's DictionaryContextData, per the same review), so
    ``matrix.PYTHON`` reads the axis ``python``.
    """
    hits = [k for k in combo if k.casefold() == key.casefold()]
    if len(hits) > 1:
        raise Unexpandable("matrix.%s could be any of %s, keys that differ only in case"
                           % (key, ", ".join(hits)))
    return hits[0] if hits else None


def check_names(display: str, matrix: object, has_matrix: bool) -> dict[str, dict[str, object]]:
    """``{check name: matrix combination}`` for every check one job reports.

    Without a matrix that is the job's name alone. With one, it is a check per
    leg: ``display (v1, v2, ...)``, values in combination order — unless
    ``name:`` uses ``${{ matrix.KEY }}``, which GitHub substitutes per leg in
    place of the suffix. Any other expression in the name is not evaluated.
    """
    combos = expand_legs(matrix) if has_matrix else [({}, [])]
    if not combos:
        raise Unexpandable("its matrix expands to no legs at all")
    leftover = _EXPR.search(_NAME_MATRIX_REF.sub("", display))
    if leftover:
        raise Unexpandable("its name uses %s, which is not evaluated here"
                           % leftover.group(0))
    # split() alternates literal text and captured keys: odd indexes are keys.
    parts = _NAME_MATRIX_REF.split(display)
    refs = parts[1::2]
    legs: dict[str, dict[str, object]] = {}
    for combo, shown in combos:
        subs: dict[str, str] = {}
        for ref in refs:
            found = _matrix_key(combo, ref)
            if found is None:
                raise Unexpandable("its name uses matrix.%s, which %s" % (
                    ref, "a leg does not define" if has_matrix else "it has no matrix to supply"))
            subs[ref] = _render(combo[found])
        if refs:
            name = "".join(subs[p] if i % 2 else p for i, p in enumerate(parts))
        elif has_matrix:
            # GitHub skips an empty value's segment, and a leg with no
            # non-empty value reports under the bare name.
            segments = [text for text in map(_render, shown) if text]
            name = "%s (%s)" % (display, ", ".join(segments)) if segments else display
        else:
            name = display
        if has_matrix and len(name) > MAX_CHECK_NAME:
            # GitHub cuts it to 97 characters and "...", so two legs can share
            # one check name; refuse rather than model the cut.
            raise Unexpandable("its leg %r is longer than the %d characters GitHub "
                               "keeps of a check name" % (name, MAX_CHECK_NAME))
        if name in legs:
            # Several check runs under one name: requiring it would accept
            # whichever reported, and which combination it stands for — and so
            # whether it is advisory — has no single answer.
            raise Unexpandable("two of its legs both report as %r" % name)
        legs[name] = combo
    return legs


def _as_number(value: object) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, bool | int | float):
        return float(value)
    if isinstance(value, str) and _JSON_NUMBER.fullmatch(value):
        return float(value)
    return math.nan


def leg_is_advisory(continue_on_error: object, combo: dict[str, object]) -> bool:
    """Does job-level ``continue-on-error`` let this leg fail without failing the run?

    Evaluates literal booleans and exactly one expression,
    ``${{ matrix.KEY == 'VALUE' }}``, with GitHub's loose ``==`` from its
    expressions reference: strings compare ignoring case, and mismatched types
    are cast to numbers (null 0, booleans 1/0, a string its JSON-number value or
    NaN, the empty string 0). ``KEY`` is looked up ignoring case, as GitHub
    does. Anything else raises :class:`Unexpandable` — this is deliberately
    not an expression evaluator.
    """
    if continue_on_error is None or continue_on_error is False:
        return False
    if continue_on_error is True:
        return True
    eq = (_COE_MATRIX_EQ.fullmatch(continue_on_error.strip())
          if isinstance(continue_on_error, str) else None)
    if eq is None:
        raise Unexpandable(
            "its continue-on-error is %r, and the only expression evaluated here is "
            "${{ matrix.KEY == 'VALUE' }}" % (continue_on_error,))
    key, literal = eq.groups()
    found = _matrix_key(combo, key)
    value = None if found is None else combo[found]
    if isinstance(value, str):
        return value.casefold() == literal.casefold()
    if literal[:1] in tuple("0123456789+-. \t") and not _JSON_NUMBER.fullmatch(literal):
        # Number-shaped but not a plain JSON number: GitHub's ParseNumber also
        # takes ' 3', '+3', '010', '0x3' and '0o3', and a guess here could
        # call an advisory leg blocking.
        raise Unexpandable("its continue-on-error compares matrix.%s, a %s, with '%s', "
                           "which is not a plain number — not modelled here"
                           % (key, type(value).__name__, literal))
    return _as_number(value) == _as_number(literal)


# NamedTuple rather than a dataclass: the tests load this file through
# importlib without registering it in sys.modules, and a dataclass resolves its
# string annotations through sys.modules[cls.__module__].
class Job(NamedTuple):
    """One job, as the check names it reports."""

    job_id: str
    display: str                  # its `name:` as written, or the job id
    has_matrix: bool
    continue_on_error: object
    # check name -> the matrix combination behind it ({} without a matrix).
    # Empty when `why` says the names could not be worked out.
    legs: dict[str, dict[str, object]]
    why: str
    uses: str | None              # the reusable workflow it calls, if any


def read_job(job_id: str, spec: object) -> Job:
    spec = spec if isinstance(spec, dict) else {}
    name = spec.get("name")
    display = job_id if name is None else name if isinstance(name, str) else repr(name)
    uses = spec.get("uses")
    strategy = spec.get("strategy")
    has_matrix = isinstance(strategy, str) or (
        isinstance(strategy, dict) and "matrix" in strategy)
    legs: dict[str, dict[str, object]] = {}
    why = ""
    try:
        if not isinstance(name, str | None):
            _scalar(name, "its name")  # says why, for an Unquoted or a non-scalar
            raise Unexpandable("its name is %r, not a string — quote it" % (name,))
        if isinstance(strategy, str):
            raise Unexpandable("its strategy is the expression %s" % strategy.strip())
        matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
        legs = check_names(display, matrix, has_matrix)
    except Unexpandable as exc:
        why = str(exc)
    return Job(job_id, display, has_matrix, spec.get("continue-on-error"), legs, why,
               uses if isinstance(uses, str) else None)


def _load_yaml(path: Path) -> object:
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit(
            "required-checks: PyYAML is not importable (%s). It is how matrix jobs "
            "are expanded into the check names GitHub reports, and this gate fails "
            "rather than skip that — install requirements/lint-tools.txt" % exc) from exc
    try:
        loader = _github_loader(yaml)(path.read_text(encoding="utf-8"))
        try:
            return loader.get_single_data()
        finally:
            loader.dispose()
    except yaml.YAMLError as exc:
        raise SystemExit("required-checks: %s is not valid YAML (%s)"
                         % (path.name, exc)) from exc


def parse_workflow(path: Path) -> tuple[str, bool, dict[str, Job]]:
    """``(pull_request_state, has_merge_group, {job_id: Job})``, jobs in file order."""
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        jobs_at = next(i for i, line in enumerate(lines) if line.rstrip() == "jobs:")
    except StopIteration:
        return PR_NONE, False, {}

    on_pr = pull_request_state(lines[:jobs_at])
    on_mg = has_merge_group(lines[:jobs_at])

    doc = _load_yaml(path)
    raw = doc.get("jobs") if isinstance(doc, dict) else None
    jobs: dict[str, Job] = {}
    for job_id, spec in (raw.items() if isinstance(raw, dict) else ()):
        if isinstance(job_id, Unquoted):
            # `on:` as a job id: PyYAML reads YAML 1.1, where it is a boolean.
            raise SystemExit("required-checks: job id %s in %s is unquoted, and PyYAML "
                             "loads it as %r — quote it"
                             % (job_id.text, path.name, job_id.yaml11))
        if not isinstance(job_id, str):
            raise SystemExit("required-checks: a job id in %s loaded as %r, not "
                             "as a string — quote it" % (path.name, job_id))
        jobs[job_id] = read_job(job_id, spec)
    return on_pr, on_mg, jobs


class Checks(NamedTuple):
    """Every check name the workflows report, and on which triggers."""

    by_name: dict[str, list[str]]   # check name -> workflow files reporting it
    on_pr: set[str]                 # reported on every pull request
    filtered: dict[str, str]        # reported on SOME pull requests -> narrowing file
    on_mg: set[str]                 # reported on a merge-queue ref
    # check name -> the job run(s) behind it: (workflow, job, matrix combination)
    legs: dict[str, list[tuple[str, Job, dict[str, object]]]]
    jobs: list[tuple[str, Job]]     # every job, for explaining a name nothing reports
    reports: dict[tuple[str, str], list[str]]  # (workflow, job id) -> its check names
    # A job whose check names could not be worked out reports names nobody can
    # list, so it is held to its raw `name:` against other such jobs, and to
    # its shape against every name another workflow reports.
    opaque: dict[str, list[str]]


Run = tuple[str, Job, dict[str, object]]


def _reports(workflow: str, job: Job, parsed: dict[str, tuple[str, bool, dict[str, Job]]],
             depth: int = 0) -> list[tuple[str, list[Run]]]:
    """``(check name, [the job run behind it])`` for every check ``job`` reports.

    A job that calls a reusable workflow reports none under its own name, only
    ``caller / callee`` — for each check of a callee in this repository (read
    like any workflow, so its legs and continue-on-error count), or
    ``caller / <any job>`` for one elsewhere, whose jobs cannot be read here.
    A remote callee's job leaves no run to judge: callers cannot set
    continue-on-error ("Supported keywords for jobs that call a reusable
    workflow", docs.github.com).
    """
    if job.uses is None:
        return [(name, [(workflow, job, combo)]) for name, combo in job.legs.items()]
    # `./` and `$/` (docs.github.com's recommended same-repository spelling)
    # both name a file in this repository, which can be read.
    if not job.uses.startswith(("./", "$/")):
        return [("%s / %s" % (name, ANY_JOB), []) for name in job.legs]
    target = PurePosixPath(job.uses[2:])
    if target.parent != PurePosixPath(".github/workflows") or target.name not in parsed:
        raise Unexpandable("the reusable workflow %s is not a file in "
                           ".github/workflows" % job.uses)
    if depth >= MAX_CALL_DEPTH:
        raise Unexpandable("the reusable workflow %s is called more than %d levels "
                           "deep — past GitHub's limit, or a cycle"
                           % (job.uses, MAX_CALL_DEPTH))
    out: list[tuple[str, list[Run]]] = []
    for callee in parsed[target.name][2].values():
        if callee.why:
            raise Unexpandable("job `%s` of the reusable workflow %s cannot be "
                               "worked out: %s" % (callee.job_id, job.uses, callee.why))
        inner = _reports(target.name, callee, parsed, depth + 1)
        out += [("%s / %s" % (name, sub), runs) for name in job.legs for sub, runs in inner]
    return out


def collect() -> Checks:
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    if not files:
        raise SystemExit("required-checks: no workflow files found under %s" % WORKFLOWS)
    parsed = {path.name: parse_workflow(path) for path in files}
    c = Checks(by_name={}, on_pr=set(), filtered={}, on_mg=set(), legs={}, jobs=[],
               reports={}, opaque={})
    for path in files:
        runs_on_pr, runs_on_mg, jobs = parsed[path.name]
        for job in jobs.values():
            try:
                reported = [] if job.why else _reports(path.name, job, parsed)
            except Unexpandable as exc:
                job, reported = job._replace(legs={}, why=str(exc)), []
            c.jobs.append((path.name, job))
            c.reports[(path.name, job.job_id)] = [name for name, _ in reported]
            if job.why:
                c.opaque.setdefault(job.display, []).append(path.name)
            for name, runs in reported:
                c.by_name.setdefault(name, []).append(path.name)
                c.legs.setdefault(name, []).extend(runs)
                if runs_on_pr == PR_ALWAYS:
                    c.on_pr.add(name)
                elif runs_on_pr == PR_FILTERED:
                    c.filtered[name] = path.name
                if runs_on_mg:
                    c.on_mg.add(name)
    if not c.jobs:
        # Every workflow parsed to zero jobs: the format changed and this gate
        # would otherwise pass by finding no problems. Fail instead.
        raise SystemExit("required-checks: parsed 0 jobs from %d workflow files — "
                         "the parser is broken, not the config" % len(files))
    return c


def read_config() -> list[str]:
    if not CONFIG.exists():
        raise SystemExit("required-checks: missing %s" % CONFIG)
    out = []
    for raw in CONFIG.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            out.append(line)
    if not out:
        raise SystemExit("required-checks: %s lists no checks" % CONFIG)
    return out


def _candidates(required: str) -> list[str]:
    """``required`` itself, then each ``caller / <any job>`` it could stand for."""
    parts = required.split(" / ")
    return [required] + [" / ".join([*parts[:i], ANY_JOB])
                         for i in range(len(parts) - 1, 0, -1)]


def resolve(required: str, on_pr: set[str]) -> tuple[bool, str]:
    """Is ``required`` a check name in ``on_pr``, and which one?

    Called against the names that run on every PR, the conditionally-triggered
    ones and the merge-queue ones, so each failure gets its own message. The
    names are already matrix-expanded, so a leg resolves only if the matrix
    produces it — ``tests (ubuntu-latest, 3.9)`` no longer rides on ``tests``
    — and a call to a reusable workflow is already ``caller / callee``, so
    ``lint / anything`` no longer rides on ``lint``.
    """
    for name in _candidates(required):
        if name in on_pr:
            return True, name
    return False, ""


def workflows_for(required: str, by_name: dict[str, list[str]]) -> list[str]:
    """Which workflow file(s) produce ``required``; empty when none does.

    Accepts the same spellings :func:`resolve` does, so an error message can
    name the file to edit instead of leaving the reader to grep for it.
    """
    for name in _candidates(required):
        if name in by_name:
            return by_name[name]
    return []


def _shaped(name: str, display: str) -> bool:
    """Is ``name`` shaped like a check of a job displayed as ``display``?"""
    if "${{" in display:
        parts = _EXPR.split(display)
        return re.fullmatch(".*".join(map(re.escape, parts)), name) is not None
    return name == display or (name.startswith(display + " (") and name.endswith(")"))


def _could_be(required: str, job: Job) -> bool:
    """Is ``required`` shaped like one of ``job``'s names, reported or not?"""
    if job.uses is not None:
        head, sep, _ = required.partition(" / ")
        return bool(sep) and _shaped(head, job.display)
    return _shaped(required, job.display)


def unreported(required: str, checks: Checks) -> str:
    """Why nothing reports ``required`` — naming the job it was meant for."""
    head, sep, _ = required.partition(" / ")
    for workflow, job in checks.jobs:
        where = "`%s` in %s" % (job.job_id, workflow)
        names = ", ".join(checks.reports[(workflow, job.job_id)])
        if job.uses is not None and not sep and _shaped(required, job.display):
            return ("required check %r is the bare name of %s, which calls the "
                    "reusable workflow %s — GitHub reports such a job only as "
                    "`caller / callee job`, never under its own name, so this would "
                    "never report" % (required, where, job.uses))
        if not _could_be(required, job):
            if sep and job.uses is None and _shaped(head, job.display):
                return ("required check %r is written as `caller / job`, but %s calls "
                        "no reusable workflow: it reports as %s and nothing else, so "
                        "this would never report" % (required, where, names or job.display))
            continue
        if job.why:
            return ("required check %r looks like %s, whose check names cannot be "
                    "worked out: %s. The gate fails closed rather than guess — "
                    "make that static, or drop the check" % (required, where, job.why))
        if job.uses is not None:
            return ("required check %r is not one of the checks %s reports through "
                    "%s, so it would never report and every PR would wait on it "
                    "forever. They are: %s" % (required, where, job.uses, names))
        if not job.has_matrix:
            return ("required check %r is written as a matrix leg, but %s has no "
                    "matrix: it reports as %r and nothing else, so this would "
                    "never report" % (required, where, job.display))
        if required == job.display:
            return ("required check %r is the bare name of %s, a matrix job — "
                    "GitHub never reports a matrix job under its bare name, only "
                    "one check per leg, so this would never report. Require the "
                    "legs instead: %s" % (required, where, names))
        return ("required check %r is not one of the %d legs %s expands to, so it "
                "would never report and every PR would wait on it forever. Its "
                "legs are: %s" % (required, len(job.legs), where, names))
    return "required check %r is not a job that runs on pull_request" % required


def ambiguities(checks: Checks) -> list[str]:
    """A message per check name more than one workflow can report.

    GitHub matches required checks by name, so such a name cannot be required
    unambiguously — whether or not it is required today.
    """
    def clash(name: str, where: list[str]) -> str:
        return ("check name %r is produced by %d workflows (%s) — GitHub matches "
                "required checks by name, so this one cannot be required "
                "unambiguously" % (name, len(where), ", ".join(where)))

    problems = [clash(n, w) for n, w in sorted(checks.by_name.items()) if len(w) > 1]
    problems += [clash(n, w) for n, w in sorted(checks.opaque.items()) if len(w) > 1]
    for workflow, job in checks.jobs:
        if not job.why:
            continue
        for name, where in sorted(checks.by_name.items()):
            others = [w for w in where if w != workflow]
            if others and _could_be(name, job):
                problems.append(
                    "check name %r is produced by %s, and `%s` in %s may report it "
                    "too — its check names cannot be worked out (%s), and GitHub "
                    "matches required checks by name, so this one cannot be "
                    "required unambiguously"
                    % (name, ", ".join(others), job.job_id, workflow, job.why))
    for wild, callers in sorted(checks.by_name.items()):
        if not wild.endswith(" / " + ANY_JOB):
            continue
        for name, where in sorted(checks.by_name.items()):
            others = [w for w in where if w not in callers]
            if others and name != wild and name.startswith(wild[:-len(ANY_JOB)]):
                problems.append(
                    "check name %r is produced by %s, and %r in %s may report it too: "
                    "that calls a reusable workflow outside this repository, whose "
                    "jobs cannot be listed here. GitHub matches required checks by "
                    "name, so this one cannot be required unambiguously"
                    % (name, ", ".join(others), wild, ", ".join(callers)))
    return problems


def advisory_problem(required: str, checks: Checks) -> str | None:
    """A message if ``required`` comes from a leg allowed to fail its run."""
    key = next((n for n in _candidates(required) if n in checks.legs), required)
    for workflow, job, combo in checks.legs.get(key, []):
        where = "`%s` in %s" % (job.job_id, workflow)
        try:
            if leg_is_advisory(job.continue_on_error, combo):
                return ("required check %r is advisory: %s sets job-level "
                        "continue-on-error %r, which is true for it, and GitHub "
                        "lets the run pass when such a job fails. A required check "
                        "must be able to fail its run — publish.yml releases on a "
                        "successful ci run — so make it blocking or drop it from "
                        "the list" % (required, where, job.continue_on_error))
        except Unexpandable as exc:
            return ("required check %r cannot be checked: %s — %s. The gate fails "
                    "closed rather than guess whether it is advisory"
                    % (required, where, exc))
    return None


def classic_payload(required: list[str]) -> dict:
    """The `PUT /branches/{branch}/protection` body for this required list."""
    return {
        "required_status_checks": {"strict": True, "contexts": list(required)},
        # Deliberately null: the repo's working model is parallel loop/*
        # branches self-merging, so requiring reviews would deadlock it.
        "required_pull_request_reviews": None,
        "enforce_admins": False,
        "restrictions": None,
    }


def ruleset_rule(required: list[str]) -> dict:
    """The `required_status_checks` RULE for a repository ruleset.

    Shaped differently from the classic payload on purpose — this is not a
    stylistic variant of the same thing. A ruleset names each context as an
    object carrying the app that must produce it, and spells `strict` as
    `strict_required_status_checks_policy`. Hand-translating between the two
    forms is exactly the step that got skipped.
    """
    return {
        "type": "required_status_checks",
        "parameters": {
            "strict_required_status_checks_policy": True,
            "required_status_checks": [
                {"context": c, "integration_id": ACTIONS_APP_ID} for c in required
            ],
        },
    }


def drift(required: list[str], remote: list[str]) -> tuple[list[str], list[str]]:
    """``(missing, extra)`` — how a live mechanism disagrees with the file.

    Order-insensitive and duplicate-tolerant: GitHub returns contexts in its own
    order, and a list that merely sorts differently is not drift.
    """
    want, have = set(required), set(remote)
    return sorted(want - have), sorted(have - want)


def _api(path: str, token: str) -> object:
    import urllib.request
    req = urllib.request.Request(  # noqa: S310  GITHUB_API is a hardcoded https constant
        GITHUB_API + path,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "boost-check-required-checks"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310  same
        return json.load(resp)


def ruleset_contexts(detail: dict) -> tuple[bool, list[str]]:
    """``(has_rule, contexts)`` for one ruleset's required-status-checks rule.

    ``has_rule`` is returned separately from an empty list because the two mean
    opposite things: a ruleset with no such rule requires nothing at all, which
    is a much louder problem than one whose list has drifted.
    """
    for rule in detail.get("rules", []):
        if rule.get("type") == "required_status_checks":
            params = rule.get("parameters") or {}
            return True, [c.get("context") for c in params.get("required_status_checks", [])]
    return False, []


def verify_remote(required: list[str], token: str) -> list[str]:
    """Compare BOTH live mechanisms against the file. Returns problems."""
    problems: list[str] = []

    prot = _api("/repos/%s/branches/%s/protection" % (REPO, BRANCH), token)
    contexts = ((prot or {}).get("required_status_checks") or {}).get("contexts", [])
    missing, extra = drift(required, contexts)
    if missing or extra:
        problems.append(
            "classic branch protection on %r disagrees with %s — missing %s, extra %s "
            "(apply with `--print-api`)"
            % (BRANCH, CONFIG.name, missing or "nothing", extra or "nothing"))

    rulesets = _api("/repos/%s/rulesets" % REPO, token) or []
    checked = 0
    for summary in rulesets:
        detail = _api("/repos/%s/rulesets/%s" % (REPO, summary["id"]), token)
        includes = ((detail.get("conditions") or {}).get("ref_name") or {}).get("include", [])
        # `~DEFAULT_BRANCH` is GitHub's alias for whatever the default branch is.
        if not ({"refs/heads/" + BRANCH, "~DEFAULT_BRANCH"} & set(includes)):
            continue
        if detail.get("enforcement") != "active":
            continue
        checked += 1
        has_rule, contexts = ruleset_contexts(detail)
        if not has_rule:
            problems.append(
                "active ruleset %r targets %r but has no required_status_checks "
                "rule at all — it gates nothing" % (detail.get("name"), BRANCH))
            continue
        missing, extra = drift(required, contexts)
        if missing or extra:
            problems.append(
                "ruleset %r (id %s) disagrees with %s — missing %s, extra %s "
                "(apply with `--print-ruleset`; send the WHOLE body, a partial "
                "PUT drops the other rules)"
                % (detail.get("name"), detail.get("id"), CONFIG.name,
                   missing or "nothing", extra or "nothing"))

    if not checked:
        # Silence here would read as "the rulesets agree", which is the failure
        # this whole function exists to stop being invisible.
        problems.append(
            "no active ruleset targets %r — if protection moved to rulesets, "
            "this check is now blind; if it did not, one was deleted" % BRANCH)
    return problems


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--print-api", action="store_true",
                    help="print the CLASSIC branch-protection payload and exit")
    ap.add_argument("--print-ruleset", action="store_true",
                    help="print the ruleset required_status_checks rule and exit")
    ap.add_argument("--verify-remote", action="store_true",
                    help="compare BOTH live mechanisms against the file "
                         "(needs GITHUB_TOKEN; network — not part of `make lint`)")
    args = ap.parse_args(argv)

    required = read_config()

    if args.print_api:
        print("# apply with:")
        print("#   curl -X PUT -H \"Authorization: Bearer $GITHUB_TOKEN\" \\")
        print("#     %s/repos/%s/branches/%s/protection \\" % (GITHUB_API, REPO, BRANCH))
        print("#     -d @payload.json")
        print("# NOTE: this is only HALF of `main`'s protection — see --print-ruleset.")
        print(json.dumps(classic_payload(required), indent=2))
        return 0

    if args.print_ruleset:
        print("# One rule out of a ruleset body. The ruleset PUT replaces the whole")
        print("# object, so fetch it, swap ONLY this rule, and send it back — a")
        print("# partial body silently drops deletion/non_fast_forward/code_scanning.")
        print("#   curl %s/repos/%s/rulesets" % (GITHUB_API, REPO))
        print(json.dumps(ruleset_rule(required), indent=2))
        return 0

    if args.verify_remote:
        import os
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            # A skip, not a pass: `make lint` never passes this flag, so the
            # offline gate is unaffected, and a caller who asked for the remote
            # check deserves to know it did not happen.
            print("required-checks: --verify-remote skipped (no GITHUB_TOKEN)")
            return 0
        try:
            remote_problems = verify_remote(required, token)
        # A network fault is not drift: exit 2 (could not check) rather than 1
        # (found a problem), so a caller can tell "GitHub was down" from "your
        # protection is wrong" without reading the message.
        except Exception as exc:
            print("required-checks: --verify-remote could not reach GitHub (%s: %s)"
                  % (type(exc).__name__, exc), file=sys.stderr)
            return 2
        if remote_problems:
            print("required-checks: %d live-protection problem(s)"
                  % len(remote_problems), file=sys.stderr)
            for p in remote_problems:
                print("  - %s" % p, file=sys.stderr)
            return 1
        print("required-checks: live protection matches %s on both mechanisms "
              "(%d checks)." % (CONFIG.name, len(required)))
        return 0

    # Only the gate reads the workflows: the three modes above print or compare
    # the required list alone, and stay usable on an interpreter without PyYAML.
    checks = collect()
    problems = ambiguities(checks)

    for name in required:
        if ANY_JOB in name:
            # The placeholder for a remote callee's jobs, not a check name:
            # it would resolve against itself and never report.
            problems.append("required check %r contains %r, this gate's placeholder for "
                            "a remote reusable workflow's jobs — name the real job"
                            % (name, ANY_JOB))
            continue
        where = workflows_for(name, checks.by_name)
        if not where:
            # Nothing reports this name, so there is no trigger to judge — say
            # which job it was presumably meant for, and why it is not that.
            problems.append(unreported(name, checks))
            continue
        advisory = advisory_problem(name, checks)
        if advisory:
            problems.append(advisory)
        # A required context must also report on the merge queue's ref. The
        # queue evaluates required checks against gh-readonly-queue/*, not
        # against the pull request, so a workflow without a `merge_group:`
        # trigger never reports there and every enqueued PR waits forever —
        # the same never-reports deadlock as a `paths:` filter, arriving
        # through a different door. Checked independently of the
        # pull_request result below: a check can be perfectly requireable
        # today and still be the thing that breaks the day the queue is
        # switched on, which is a repo Setting and not visible from here.
        queue_ok, _ = resolve(name, checks.on_mg)
        if not queue_ok:
            problems.append(
                "required check %r comes from %s, which has no `merge_group:` "
                "trigger. Enabling the merge queue would deadlock every PR on "
                "it, because the queue evaluates required checks against the "
                "gh-readonly-queue/* ref where this never reports — add the "
                "trigger, or drop the check from the required list"
                % (name, ", ".join(where)))

        ok, _via = resolve(name, checks.on_pr)
        if ok:
            continue
        conditional, via = resolve(name, set(checks.filtered))
        if conditional:
            problems.append(
                "required check %r only runs on SOME pull requests (%s narrows "
                "its trigger with paths:/types:). GitHub creates no check run at "
                "all on a PR that does not match, so branch protection would "
                "wait forever and the PR could never merge — drop it from the "
                "list or widen the trigger" % (name, checks.filtered[via]))
        else:
            problems.append("required check %r is not a job that runs on "
                            "pull_request" % name)

    if problems:
        print("required-checks: %d problem(s)" % len(problems), file=sys.stderr)
        for p in problems:
            print("  - %s" % p, file=sys.stderr)
        return 1

    print("required-checks: %d required, %d PR check names, no ambiguity."
          % (len(required), len(checks.on_pr)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
