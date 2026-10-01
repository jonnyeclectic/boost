# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the free-threaded canary installs what the suite imports.

``canary (3.14t free-threaded)`` is an allow-failure early-warning leg — a
GIL-removal regression should surface there before a user on 3.14t hits it on
release day. ``continue-on-error: true`` is deliberate, and is also exactly
what lets the leg rot unnoticed: nothing about a red canary stops a merge, so
nothing about a red canary gets read.

It had rotted. Seventeen failures, all one cause::

    ModuleNotFoundError: No module named 'setuptools'
      tests/unit/test_sdist_contents.py

That file runs setuptools' own MANIFEST matcher
(``setuptools._distutils.filelist``) rather than building an sdist over the
network. The canary builds its venv by hand — ``pip install pytest pytest-cov
coverage hypothesis`` then ``-e .`` — and a modern ``venv`` seeds pip alone,
while ``pip install -e .`` resolves the build backend in an *isolated* build
env that leaves nothing behind in ``.venv``. The main matrix never saw it:
``make venv`` installs the hash-pinned ``requirements/*.txt``.

The colour is the whole point of the leg. A canary that is red for an
environment gap goes from red to red the day a free-threaded regression lands.

So these tests derive, from the suite itself, the third-party modules it
imports **unguarded**, and fail if the canary's install list is missing one.
The classification is the load-bearing half: ``yaml``, ``sqlite_vec``,
``hypothesis`` and ``mutmut`` are all imported here too and are all *optional*
— each is behind ``pytest.importorskip`` or a ``try``/``except``, which is the
convention this file enforces the other side of. ``setuptools`` was neither
guarded nor installed, and that is the only shape that fails.

A module in neither the distribution map nor the repo-local set is a hard
error rather than a silent pass: a new test dependency must be classified by
the person adding it, not defaulted to "probably fine".

**It then happened again, to a different job, for the same reason.** The
weekly ``floors`` cron went red on 2026-09-30 with the same seventeen
``ModuleNotFoundError: No module named 'setuptools'``. That job also builds
its venv by hand, and this file had been written to read exactly one job —
``jobs["canary"]`` in ci.yml — so it had nothing to say about the second
place the same mistake lives. :func:`_harness_jobs` now finds them by shape
rather than by name: **six** jobs across three workflow files run
``tests/unit``/``tests/functional`` out of a venv they assemble themselves,
and a seventh is covered before it is written.

Six, not five. An earlier draft of this file said five and claimed "the sixth
is covered before it is written" — while ``ci.yml:onnx-inference``, which
builds its own venv and runs one file out of ``tests/unit``, was already
there and was being dropped by a path filter that compared with ``endswith``.
Finding jobs by shape is only worth anything if the shape is the real one.

Jobs that install from the hash-pinned ``requirements/*.txt`` are checked too,
not excused. They are merely the ones that happen to be right today, and a
lock can lose a pin (the whole reason ``lock_toolchain.py --audit`` exists) as
easily as a hand-typed line can miss one.
"""
from __future__ import annotations

import ast
import re
import shlex
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
WORKFLOWS = ROOT / ".github" / "workflows"


def _workflow_files() -> list[Path]:
    """Both spellings. GitHub reads ``.yaml`` as readily as ``.yml``, and a
    scan that globs one of them would not see a job written in the other."""
    return sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])

#: The suite trees this file speaks for. ``tests/langchain`` is deliberately
#: out: ``boost-langchain.yml`` installs it as an extra (``-e '.[langchain]'``),
#: so what that provides comes from pyproject's ``optional-dependencies``
#: rather than from a pip line, and none of that tree's third-party imports are
#: classified below. Widening to it means classifying them first.
SUITE_TREES = ("tests/unit", "tests/functional")

#: Third-party import name -> the distribution ``pip install`` wants. They
#: differ often enough (``yaml`` -> PyYAML, ``sqlite_vec`` -> sqlite-vec) that
#: mapping by hand is the honest option.
MODULE_TO_DIST = {
    "hypothesis": "hypothesis",
    "mutmut": "mutmut",
    "pytest": "pytest",
    "setuptools": "setuptools",
    "sqlite_vec": "sqlite-vec",
    "yaml": "PyYAML",
}

#: Importable from a checkout without being installed: first-party packages and
#: the ``scripts/`` modules the suite puts on ``sys.path`` to test directly.
REPO_LOCAL = {
    "boost_cli", "boost_langchain", "conftest", "evals", "noxfile",
    "publish_shards", "scripts", "shard_plan", "tests",
}


def _imports(tree: ast.AST) -> list[tuple[str, bool, bool]]:
    """Every top-level module imported by ``tree``, as (name, guarded, deferred).

    *guarded* — the import sits inside a ``try``, the explicit way a test
    declares a dependency optional.
    *deferred* — it sits inside a function, so it runs when that function is
    called rather than at collection. On its own that is not a guard: it is
    exactly what made ``setuptools`` fail as 17 errors instead of one.
    """
    out: list[tuple[str, bool, bool]] = []
    tries = (ast.Try, ast.TryStar) if hasattr(ast, "TryStar") else (ast.Try,)
    funcs = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)

    def walk(nodes, in_try: bool, in_func: bool) -> None:
        for node in nodes:
            if isinstance(node, ast.Import):
                out.extend((a.name.split(".")[0], in_try, in_func)
                           for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:          # a relative import is first-party
                    out.append(((node.module or "").split(".")[0],
                                in_try, in_func))
            elif isinstance(node, tries):
                # A ``try`` guards its body, its handlers and its ``finally``,
                # but not its ``else``: an import there runs only once the
                # guarded one has already succeeded.
                walk(node.body, True, in_func)
                for handler in node.handlers:
                    walk(handler.body, True, in_func)
                walk(node.finalbody, True, in_func)
                walk(node.orelse, in_try, in_func)
            elif isinstance(node, funcs):
                walk(ast.iter_child_nodes(node), in_try, True)
            else:
                walk(ast.iter_child_nodes(node), in_try, in_func)

    walk(ast.iter_child_nodes(tree), False, False)
    return out


def _skipped(src: str) -> set[str]:
    """Modules the file declares optional via ``pytest.importorskip("x")``."""
    return set(re.findall(r'importorskip\(\s*["\']([\w.]+)["\']', src))


def _module_skipif(tree: ast.AST) -> bool:
    """True when a module-level ``pytestmark`` skips the whole file.

    ``tests/unit/test_dense_boilerplate_cluster.py`` probes whether the
    sqlite-vec extension loads and sets ``pytestmark = pytest.mark.skipif(not
    _vec_loadable(), ...)``. Its helpers then ``import sqlite_vec`` with no
    ``try`` — which is safe, because no test in the file runs to call them.
    That covers a *deferred* import only: a module-level one in the same file
    would still fail at collection, before any marker is consulted.
    """
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "pytestmark"
                   for t in node.targets):
            continue
        if "skipif" in ast.dump(node.value):
            return True
    return False


def _scan(paths: list[Path]) -> tuple[set[str], set[str]]:
    """(required, optional) third-party modules imported under ``paths``."""
    files: list[Path] = []
    for p in paths:
        files += [p] if p.is_file() else sorted(p.rglob("*.py"))
    required: set[str] = set()
    optional: set[str] = set()
    for f in files:
        src = f.read_text(encoding="utf-8")
        tree = ast.parse(src)
        skipped = _skipped(src)
        whole_file_skips = _module_skipif(tree)
        for mod, in_try, deferred in _imports(tree):
            if not mod or mod in sys.stdlib_module_names or mod in REPO_LOCAL:
                continue
            guarded = (in_try or mod in skipped
                       or (deferred and whole_file_skips))
            (optional if guarded else required).add(mod)
    # Unguarded anywhere wins: one bare import is enough to break the leg.
    return required, optional - required


def _norm(dist: str) -> str:
    """PEP 503 name normalization — ``PyYAML``, ``pyyaml`` and ``py_yaml`` agree.

    A lock file is written normalized and a hand-typed pip line is not, so the
    two sides of every comparison below have to be put in the same spelling
    before they can disagree about anything real.
    """
    return re.sub(r"[-_.]+", "-", dist).lower()


def _locked_names(rel: str) -> set[str]:
    """Distributions a committed ``-r`` requirements file installs.

    Returns the empty set for a file that is not there. ``floors.yml`` compiles
    its ``requirements-lowest.txt`` from pyproject at the lowest-direct
    resolution, so whether it exists depends on *where this runs*: absent in a
    plain checkout, present in that job's own workspace by the time it runs the
    suite. Both readings are safe, which is the point — an unreadable file can
    only make this module claim something is *missing* that is really there, a
    loud false positive someone fixes, and never let a real gap pass silently.
    """
    path = ROOT / rel
    if not path.is_file():
        return set()
    return {_norm(m.group(1)) for m in
            re.finditer(r"(?m)^([A-Za-z0-9][A-Za-z0-9._-]*)==", path.read_text(encoding="utf-8"))}


#: `.venv/bin` on POSIX, `.venv/Scripts` on Windows, and `$VENV_BIN` — which
#: is how ci.yml spells the same thing so one `run:` serves both runners.
VENV_BIN = re.compile(r"^(?:\.venv/(?:bin|Scripts)|\$\{?VENV_BIN\}?)$")
#: A token made only of these ends a command: the shell separators
#: (`;` `|` `||` `&&` `&`) and the redirects (`>` `>>` `<`). `shlex`
#: with `punctuation_chars` hands each back on its own, so this is a
#: match over one token rather than a split of the raw line.
BOUNDARY = re.compile(r"[;|&<>]+")
GROUPING = {"(", ")", "{", "}"}
PREFIXES = {"then", "do", "sudo", "time", "exec", "env"}
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
PYTHON = re.compile(r"(?:.*/)?python[\d.t]*$")
PIP = re.compile(r"(?:.*/)?pip[\d.]*$")
PYTEST = re.compile(r"(?:.*/)?pytest$")


def _lines(run: str) -> list[str]:
    """A ``run:`` block's shell lines, decommented and continuations folded.

    Folding is not cosmetic. ``ci.yml`` wraps its longer pytest invocations
    across a backslash, and a scan that reads raw lines sees ``pytest`` on one
    and ``tests/unit`` on the next, matches neither, and reports the job as
    running no tests — which excludes it from every check in this file
    silently, the same way naming one job excluded four.
    """
    out: list[str] = []
    buf = ""
    for raw in run.splitlines():
        line = re.sub(r"(^|\s)#.*$", "", raw)
        # Comments first, or prose about pip counts as a pip line: the very
        # comment explaining that `pip install -e .` leaves nothing in .venv
        # parsed as an install of `an`, `build` and `the`.
        if line.rstrip().endswith("\\"):
            buf += line.rstrip()[:-1] + " "
            continue
        out.append(buf + line)
        buf = ""
    if buf:
        out.append(buf)
    return out


def _split_on_boundaries(tokens: list[str]) -> list[list[str]]:
    """Token runs between the boundaries, dropping empty runs."""
    out: list[list[str]] = [[]]
    for tok in tokens:
        if BOUNDARY.fullmatch(tok):
            out.append([])
        else:
            out[-1].append(tok)
    return [run for run in out if run]


def _tokens(line: str) -> list[str]:
    """One shell line as tokens, with separators broken out and quotes gone.

    ``punctuation_chars`` is what makes ``;`` and ``&&`` their own tokens
    instead of sticking to the word beside them; ``posix`` is what keeps a
    separator *inside* a quoted string from becoming one. An unbalanced
    quote is not a line this file can read, so it falls back to the
    whitespace split rather than raising out of a collection-time helper.
    """
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""           # `_lines` already stripped the comments
    try:
        return list(lexer)
    except ValueError:
        return line.split()


def _commands(line: str) -> list[list[str]]:
    """One shell line split into the commands it actually runs.

    Splitting on the separators is what makes ``echo`` an ``echo``: matching
    ``pip.*install`` anywhere in the line credited
    ``pip install pytest; echo setuptools`` with setuptools.

    The split is over *tokens*, not over the raw text, because a separator
    inside a quoted string is not a separator. Splitting the text credited
    ``echo "a; pip install setuptools"`` with setuptools — a false credit in
    the direction that matters, since what is being decided is whether a job
    installs what its suite imports — and tore a real line, ci.yml's
    ``grep -E '^(FAILED|ERROR) ' /tmp/pytest.out``, into two commands that
    were never run. Redirects end a command for the same reason: without
    that, ``pip install rich >> log`` credits a distribution named ``log``.

    (An earlier draft of this docstring said the stop-token check "was dead
    from the day it was written". It was not: a ``words`` list built by
    ``str.split()`` does contain a bare ``||``, ``&&`` or ``|``. Only ``;``
    was unreachable, because it sticks to the word before it.)
    """
    out = []
    for chunk in _split_on_boundaries(_tokens(line)):
        words = [w for w in chunk if w not in GROUPING]
        # Wrappers, and the `A=1 pip …` / `env A=1 pip …` assignment prefix.
        while words and (words[0] in PREFIXES
                         or ASSIGNMENT.fullmatch(words[0])):
            words = words[1:]
        if words:
            out.append(words)
    return out


def _interpreter(word: str) -> str:
    """Which Python a command's executable belongs to.

    ``system`` for a bare name, ``.venv`` for every spelling of the venv
    this repo builds, and the containing directory for anything else —
    including an absolute path, which buckets as *that directory* and not as
    ``system``. (An earlier draft of this docstring said an absolute path
    read as ``system``; it never did.) Bucketing
    ``/opt/hostedtoolcache/.../bin/python -m pip install x`` apart from a
    bare ``pytest`` is the conservative direction: the job reports the
    distribution missing, which is loud, rather than credited, which is not.

    Without this the checks are satisfiable by installing into the wrong
    Python. ``floors.yml:lowest`` is the live example: its "resolve the
    declared floors" step runs ``python -m pip -q install uv`` on the
    *runner's* interpreter, and the **next** step builds the ``.venv`` that
    runs the suite. :func:`_harness_jobs` collects per job and so unions
    those two steps, which is why the split has to be by interpreter and not
    by block — an earlier draft of this paragraph put both on one ``run:``
    block, which understates the union rather than overstating it. Moving
    ``setuptools`` onto the runner's line would otherwise leave this file
    green with the job still red on seventeen ModuleNotFoundErrors.
    """
    bare = word.strip("'\"")
    head, _, _leaf = bare.rpartition("/")
    if not head:
        return "system"
    if VENV_BIN.match(head):
        return ".venv"
    return head


#: Flags that send the install somewhere other than the interpreter's own
#: site-packages, or nowhere at all. A distribution behind one of these is
#: not importable by the suite, so crediting it is the dangerous direction:
#: `pip install --target vendor/ setuptools` would satisfy every assertion
#: here while the job stays red on the import it cannot make.
ELSEWHERE = {"--target", "-t", "--prefix", "--root", "--dry-run",
             "--download", "-d", "--platform", "--python-version"}


def _pip_install(words: list[str]) -> tuple[str, list[str]] | None:
    """``(interpreter, arguments)`` if this command is a pip install."""
    head = words[0].strip("'\"")
    rest = [w.strip("'\"") for w in words[1:]]
    exe = head
    if head == "uv" and rest[:2] == ["pip", "install"]:
        # `uv pip install --python X` names its target explicitly; without
        # it, uv installs into the active environment, which the caller
        # resolves from the surrounding `source … activate`.
        exe, args, skip = "", [], False
        for i, w in enumerate(rest[2:]):
            if skip:
                skip = False
                continue
            if w == "--python":
                exe, skip = rest[2:][i + 1] if i + 1 < len(rest) - 2 else "", True
                continue
            if w.startswith("--python="):
                exe = w.split("=", 1)[1]
                continue
            args.append(w)
        return (_interpreter(exe) if exe else ""), _strip_flags(args)
    if PYTHON.fullmatch(head) and rest[:2] == ["-m", "pip"]:
        rest = rest[2:]
    elif not PIP.fullmatch(head):
        return None
    while rest and rest[0].startswith("-"):     # pip's own flags, e.g. -q
        rest = rest[1:]
    if not rest or rest[0] != "install":
        return None
    return _interpreter(words[0]), _strip_flags(rest[1:])


def _strip_flags(args: list[str]) -> list[str] | None:
    """``None`` when a flag redirects the install off the interpreter."""
    return None if any(a.split("=")[0] in ELSEWHERE for a in args) else args


def _stream(run: str):
    """``(active_interpreter, words)`` per command, following activation.

    ``source .venv/bin/activate`` is the hole this exists for. After it,
    every command is a *bare* name — ``pip``, ``pytest`` — and
    :func:`_interpreter` reads a bare name as the system Python. So a
    ``python -m pip install`` before the activate and a bare ``pytest``
    after it both bucket as ``system``, which is exactly the merge that made
    an install into the wrong interpreter satisfy the suite. Tracking the
    activation keeps the two apart: commands after it resolve to the venv it
    named, commands before it do not.
    """
    active: str | None = None
    for line in _lines(run):
        for words in _commands(line):
            head = words[0].strip("'\"")
            if head in {"source", "."} and len(words) > 1:
                target = words[1].strip("'\"")
                if target.rsplit("/", 1)[-1].startswith("activate"):
                    active = _interpreter(target)
                    continue
            if head == "deactivate":
                active = None
                continue
            yield active, words


def _resolve(interp: str, active: str | None) -> str:
    """An unqualified command belongs to whatever is activated."""
    return active if (active and interp in {"system", ""}) else interp


def _installs(run: str, interpreter: str | None = None) -> set[str]:
    """Distributions a job's ``pip install`` lines put in one interpreter.

    Explicitly named ones, plus everything a committed ``-r`` file pins —
    without the second half, every job that installs from
    ``requirements/*.txt`` would read as installing nothing at all and so
    look broken. That is **four** of the six harness jobs —
    ``ci.yml:{tests,patch-coverage,onnx-inference}`` and
    ``sonarcloud.yml:sonar-analyze`` — not the three an earlier draft of
    this docstring counted, plus ``floors.yml:lowest``, which reads a
    ``requirements-lowest.txt`` it generates a step earlier. A number in
    prose that nothing checks is how that got stale;
    ``test_which_jobs_install_from_a_requirements_file`` now pins both sets
    as equalities.

    ``interpreter`` selects which Python to count installs into; ``None``
    counts them all, which is only ever right for a job with one.

    Known limits, both in the *dangerous* direction — crediting something
    the job may not have — and both tripwired rather than trusted:

    * a ``pip install`` behind a shell ``if``/``case`` or a step-level YAML
      ``if:`` is credited unconditionally, because nothing here evaluates
      conditions. :meth:`TestHarnessJobDiscovery.\
test_no_harness_job_installs_conditionally` fails the build the day one
      appears;
    * a ``-r`` pin carrying an environment marker
      (``colorama==0.4.6 ; sys_platform == 'win32'``) is credited on every
      matrix leg, including the legs where pip skips it. Evaluating markers
      needs the leg's platform, which is not available here;
      :meth:`TestInstallParsing.test_a_marker_gated_pin_still_counts` pins
      the behaviour so it is a known choice rather than a surprise.
    """
    got: set[str] = set()
    for active, words in _stream(run):
        parsed = _pip_install(words)
        if parsed is None:
            continue
        into, args = parsed
        if args is None:          # --target/--dry-run: not on this path
            continue
        into = _resolve(into, active)
        if interpreter is not None and into != interpreter:
            continue
        skip_next = False
        for i, word in enumerate(args):
            if skip_next:        # the filename after -r is not a package
                skip_next = False
                continue
            if word in {"-r", "--requirement"} and i + 1 < len(args):
                got |= _locked_names(args[i + 1])
                skip_next = True
                continue
            bare = word.strip("'\"")
            # `-e .` and `-e '.[rag]'` install something, but not by name.
            if (word.startswith("-") or bare in {".", "-e"}
                    or bare.startswith(".[")):
                continue
            got.add(_norm(re.split(r"[<>=!\[]", bare)[0]))
    return got


def _pytest_runs(run: str) -> list[tuple[str, list[Path]]]:
    """``(interpreter, tests/ paths)`` for each pytest invocation in a block."""
    out = []
    for active, words in _stream(run):
        head = words[0].strip("'\"")
        rest = words[1:]
        if PYTHON.fullmatch(head) and rest[:2] == ["-m", "pytest"]:
            rest = rest[2:]
        elif not PYTEST.fullmatch(head):
            continue
        paths = []
        for w in rest:
            bare = w.strip("'\"")
            if not bare.startswith("tests/"):
                continue
            # `tests/unit/test_x.py::test_y` is a node id. Kept whole it
            # passes `_under_suite` (a prefix test) and then scans to
            # nothing, because `is_file()` is False and `rglob` on a path
            # that does not exist yields no files — so the job reports zero
            # required imports and is satisfied vacuously.
            paths.append(ROOT / bare.split("::", 1)[0])
        if paths:
            out.append((_resolve(_interpreter(words[0]), active), paths))
    return out


def _under_suite(target: Path) -> bool:
    """Is this path one of the suite trees, or inside one?

    ``endswith`` was the first cut and dropped ``ci.yml:onnx-inference``,
    which runs a single file out of ``tests/unit`` from a venv it builds
    itself — the sixth harness job, already written when this file claimed to
    have covered the sixth before it was.
    """
    rel = target.as_posix()
    return any(rel == (ROOT / tree).as_posix()
               or rel.startswith((ROOT / tree).as_posix() + "/")
               for tree in SUITE_TREES)


def _targets(run: str) -> list[Path]:
    """Every ``tests/`` path a ``run:`` block hands pytest."""
    return [p for _interp, paths in _pytest_runs(run) for p in paths]


def _runs_of(workflow: str, job_id: str) -> list[str]:
    """Every ``run:`` body of one job, by workflow file name and job id."""
    doc = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8")) or {}
    job = (doc.get("jobs") or {}).get(job_id) or {}
    return [step.get("run") or "" for step in (job.get("steps") or [])]


def _harness_jobs() -> list[tuple[str, str, set[str], list[Path]]]:
    """Every workflow job that builds a venv by hand and runs the suite in it.

    ``(workflow, job id, installed distributions, test paths)``. Collected per
    *job*, not per step: ``sonarcloud.yml`` creates the venv and installs in
    one step and runs pytest in the next, and a per-step scan sees a pytest
    step that installs nothing.

    Jobs that install from the hash-pinned ``requirements/*.txt`` are included
    rather than excluded. They are the ones that happen to be right today, and
    "right today" is not the property worth asserting — a lock file can lose a
    pin (see ``scripts/lock_toolchain.py --audit``) as easily as a hand-typed
    line can miss one.
    """
    out: list[tuple[str, str, set[str], list[Path]]] = []
    for wf in _workflow_files():
        doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
        for job_id, job in (doc.get("jobs") or {}).items():
            runs = [step.get("run") or "" for step in (job.get("steps") or [])]
            if not any("venv" in r for r in runs):
                continue
            # The interpreter that runs the suite is the one whose installs
            # count. A job may also install into the runner's Python — uv,
            # for one — and those packages are not on the suite's path.
            suite: dict[str, list[Path]] = {}
            for r in runs:
                for interp, paths in _pytest_runs(r):
                    kept = [p for p in paths if _under_suite(p)]
                    if kept:
                        suite.setdefault(interp, []).extend(kept)
            if not suite:
                continue
            for interp, targets in sorted(suite.items()):
                installs: set[str] = set()
                for r in runs:
                    installs |= _installs(r, interp)
                out.append((wf.name, job_id, installs, targets))
    return out


def _canary_step() -> dict:
    jobs = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]
    assert "canary" in jobs, "the canary job was renamed or removed"
    for step in jobs["canary"]["steps"]:
        run = step.get("run", "")
        if "pytest" in run and "python -m venv" in run:
            return step
    pytest.fail("no venv+pytest step in the canary job")


def _canary_interpreter(run: str) -> str:
    """The interpreter the canary step's suite run actually uses."""
    for interp, paths in _pytest_runs(run):
        if any(_under_suite(p) for p in paths):
            return interp
    pytest.fail("the canary step runs no tests/ path")


def _canary_installs(run: str) -> set[str]:
    """Distributions the canary's installs put in the Python the suite uses.

    Attribution, not a union over the step. This pin exists so the fix
    "cannot be undone by accident", and it was the last place still counting
    every interpreter: moving ``setuptools`` onto a ``python -m pip`` line
    beside the venv left this assertion green while the venv running the
    suite could not import it — the exact move the rest of the file was
    rewritten to catch.
    """
    return _installs(run, _canary_interpreter(run))


def _canary_targets(run: str) -> list[Path]:
    targets = _targets(run)
    if not targets:
        pytest.fail("the canary step runs no tests/ path")
    return targets


#: Every job that assembles its own venv and runs the suite in it, as
#: ``workflow:job``. Pinned so a seventh is a decision: a new one that this
#: file has never seen is exactly the shape both regressions took.
HARNESS_JOBS = {
    "ci.yml:tests",            # the required coverage gate (-r test-tools.txt)
    "ci.yml:patch-coverage",   # diff-cover (-r coverage-tools.txt)
    "ci.yml:canary",           # 3.14t free-threaded, explicit pip line
    "ci.yml:onnx-inference",   # one file out of tests/unit, own venv, .[rag]
    "floors.yml:lowest",       # uv lowest-direct, explicit pip line
    "sonarcloud.yml:sonar-analyze",
}


#: Jobs that build a venv and run tests, but that :func:`_harness_jobs`
#: deliberately does not collect — each with the reason, because "not
#: collected" and "not checked" are the same state and only a named one is a
#: decision. Asserted as an *equality* by the discovery test below, so a
#: stale entry fails the build as loudly as a new blind spot does.
OUT_OF_SCOPE_JOBS = {
    # Runs `tests/langchain`, not a suite tree. What it needs comes from the
    # `[langchain]` extra in pyproject rather than a pip line, so there is no
    # hand-typed install list here to get wrong — and the job already asserts
    # its own suite RAN rather than skipped itself, which is the failure this
    # file exists to prevent, enforced locally instead.
    "boost-langchain.yml:conformance",
    # Drives `tests/unit` through mutmut, not through a `pytest tests/...`
    # invocation, so the collector cannot see the paths. Its venv installs
    # `requirements/mutation-tools.txt`, a hash-pinned superset of
    # test-tools.txt, so the same lock that covers `ci.yml:tests` covers it.
    "ci.yml:mutation-shard",
}


def _conditional_install_jobs() -> list[str]:
    """Harness jobs whose pip install is behind a condition.

    A step-level YAML ``if:`` is the *native* way to install conditionally,
    and it is the shape a reader of the ``run:`` body alone cannot see:
    ``- if: runner.os == 'Linux'`` over a ``pip install setuptools`` is
    credited on every leg of a matrix, including the legs where the step is
    skipped entirely.
    """
    guilty = []
    for wf in _workflow_files():
        doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
        for job_id, job in (doc.get("jobs") or {}).items():
            if "%s:%s" % (wf.name, job_id) not in HARNESS_JOBS:
                continue
            for step in job.get("steps") or []:
                body = step.get("run") or ""
                if not any(_pip_install(c) for _a, c in _stream(body)):
                    continue
                if step.get("if") or re.search(r"(?m)^\s*(if|case)\s", body):
                    guilty.append("%s:%s" % (wf.name, job_id))
    return sorted(set(guilty))


#: Ways of running the suite that :func:`_harness_jobs` cannot read, because
#: collection needs a literal `pytest` command carrying a `tests/` argument.
SUITE_RUNNERS = re.compile(r"\b(pytest|nox|tox|make\s+(test|check)|uv\s+run)\b")


def _unreadable_suite_jobs() -> list[str]:
    """Jobs that build a venv and run tests in a spelling we cannot parse."""
    collected = {"%s:%s" % (wf, job) for wf, job, _i, _t in _harness_jobs()}
    missed = []
    for wf in _workflow_files():
        doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
        for job_id, job in (doc.get("jobs") or {}).items():
            name = "%s:%s" % (wf.name, job_id)
            if name in collected:
                continue
            runs = [st.get("run") or "" for st in (job.get("steps") or [])]
            if not any("venv" in r for r in runs):
                continue
            if any(SUITE_RUNNERS.search(r) for r in runs):
                missed.append(name)
    return sorted(missed)


def _plant(tmp_path, name: str, body: str, monkeypatch) -> None:
    """Point the scanners at a throwaway workflow directory.

    Every tripwire in this file guards a shape the repo does not currently
    contain, so asserting over the real directory proves only that the shape
    is absent. Planting it is the difference between a guard and a guard's
    docstring.
    """
    (tmp_path / name).write_text(body, encoding="utf-8")
    monkeypatch.setattr("test_canary_deps.WORKFLOWS", tmp_path)


class TestHarnessJobs:
    """Every venv a workflow builds by hand must satisfy what it then runs."""

    def test_every_harness_job_installs_what_the_suite_imports(self):
        """The regression, twice over: an unguarded import a leg cannot satisfy.

        One-directional on purpose — several of these also install
        ``pytest-cov`` and ``coverage``, which nothing imports by name, and an
        extra dependency costs seconds while a missing one costs the signal.
        """
        broken = {}
        for wf, job, installed, targets in _harness_jobs():
            required, _ = _scan([*targets, ROOT / "tests/conftest.py"])
            missing = sorted(_norm(MODULE_TO_DIST.get(m, m)) for m in required
                             if _norm(MODULE_TO_DIST.get(m, m)) not in installed)
            if missing:
                broken[f"{wf}:{job}"] = (missing, sorted(installed))
        assert not broken, (
            "these jobs run the suite out of a venv that cannot import it: "
            + "; ".join(f"{k} is missing {v[0]} (installs {v[1]})"
                        for k, v in sorted(broken.items()))
            + " — add them to that job's pip install line, or guard the "
              "import with pytest.importorskip")

    def test_every_harness_job_can_import_yaml(self):
        """This file's own dependency, which it used to skip over instead.

        The module opens with `pytest.importorskip("yaml")`, because it reads
        `.github/workflows/*.yml`. PyYAML was pinned in `lint-tools.txt` and
        `mutation-tools.txt` and in neither `test-tools.txt` nor
        `coverage-tools.txt`, and neither hand-typed pip line named it — so
        the file skipped in **all six** jobs that run the suite, including
        the required `tests` leg and the free-threaded canary it was written
        to protect. (The card that raised this said three jobs; measuring
        them said six.)

        It was still enforced, in a place nobody reads it: `setup.cfg` copies
        `.github/` into `mutants/`, so it runs in the mutation gate's
        baseline and a failure fails a required check — reported as
        "mutation gate: `mutmut run` failed to execute", every shard red, the
        workflow file named nowhere.

        `test_every_harness_job_installs_what_the_suite_imports` cannot catch
        this, and correctly so: it scans for *unguarded* imports, and an
        `importorskip` is guarded by construction. A guard that turns the
        whole file off in every job it guards is the one case where being
        guarded is the defect, so it gets its own assertion.
        """
        skipping = [f"{wf}:{job}" for wf, job, installed, _t in _harness_jobs()
                    if "pyyaml" not in {_norm(d) for d in installed}]
        assert not skipping, (
            "test_canary_deps.py needs PyYAML and these jobs do not install "
            "it, so the whole file skips there: " + ", ".join(skipping))

    def test_the_set_of_hand_built_jobs_is_the_one_we_know_about(self):
        """A new job assembling its own venv has to be looked at, not inherited.

        Both regressions were a job nobody had thought about in these terms.
        Failing here is cheap — add the name once the job is checked — and it
        is the only moment the question gets asked at all.
        """
        found = {f"{wf}:{job}" for wf, job, _, _ in _harness_jobs()}
        assert found == HARNESS_JOBS

    def test_the_floors_job_installs_setuptools(self):
        """Pin the second occurrence, the way the canary's is pinned below.

        ``floors.yml`` resolves the declared lower bounds with uv and runs the
        suite against them. Neither half of ``python -m venv`` plus ``pip
        install -e .`` provides setuptools, so the job was red on
        test_sdist_contents.py rather than on any floor.
        """
        jobs = {f"{wf}:{job}": installed for wf, job, installed, _ in _harness_jobs()}
        assert "setuptools" in jobs["floors.yml:lowest"]


class TestCanaryDependencies:

    def test_setuptools_is_one_of_them(self):
        """Pin the specific case, so the fix cannot be undone by accident.

        ``tests/unit/test_sdist_contents.py`` imports setuptools inside a
        helper, so the failure is 17 errors at call time rather than one
        collection error — which is why it read as a test problem for as long
        as it did.
        """
        required, optional = _scan([ROOT / "tests/unit", ROOT / "tests/functional"])
        assert "setuptools" in required
        assert "setuptools" not in optional
        assert "setuptools" in _canary_installs(_canary_step()["run"])

    def test_moving_it_off_the_suite_interpreter_breaks_the_pin(self):
        """The pin above is attribution, not a union over the step.

        Installing setuptools into the runner's Python instead of the venv
        leaves the canary red on seventeen ModuleNotFoundErrors, so the pin
        must go red too. It did not: `_canary_installs` unioned every
        interpreter, and this is the one move it could not see.
        """
        moved = ("python -m venv .venv\n"
                 "python -m pip -q install setuptools\n"
                 ".venv/bin/pip -q install pytest\n"
                 ".venv/bin/pytest tests/unit tests/functional -q\n")
        assert "setuptools" not in _canary_installs(moved)
        assert "pytest" in _canary_installs(moved)

    def test_the_optional_ones_stay_optional(self):
        """The other four third-party imports are guarded, and must stay so.

        If one of these ever loses its guard this file starts demanding it in
        the canary — which is the correct answer, but it should be a decision.
        """
        required, optional = _scan(
            [ROOT / "tests/unit", ROOT / "tests/functional", ROOT / "tests/conftest.py"])
        assert {"hypothesis", "mutmut", "sqlite_vec"} <= optional
        assert required == {"pytest", "setuptools"}

    def test_every_third_party_import_is_classified(self):
        """A module in neither table fails rather than passing unnoticed."""
        required, optional = _scan(
            [ROOT / "tests/unit", ROOT / "tests/functional", ROOT / "tests/conftest.py"])
        unknown = sorted((required | optional) - set(MODULE_TO_DIST))
        assert not unknown, (
            f"{unknown} is imported by the suite and is in neither "
            f"MODULE_TO_DIST nor REPO_LOCAL — say which it is")

    def test_the_canary_still_allows_failure(self):
        """Green is the point; blocking on it is not.

        The leg is a signal. If it ever becomes required, this file's premise
        (a red canary is ignorable, so it must be green to mean anything)
        stops holding and the docstring above needs rewriting.
        """
        jobs = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]
        assert jobs["canary"]["continue-on-error"] is True


class TestGuardDetection:
    """The classifier is the part that can be quietly wrong, so test it."""

    @staticmethod
    def _one(src: str) -> tuple[set[str], set[str]]:
        tree = ast.parse(src)
        skipped, skips = _skipped(src), _module_skipif(tree)
        req, opt = set(), set()
        for mod, in_try, deferred in _imports(tree):
            guarded = in_try or mod in skipped or (deferred and skips)
            (opt if guarded else req).add(mod)
        return req, opt - req

    def test_a_bare_import_is_required(self):
        assert self._one("import widget")[0] == {"widget"}

    def test_a_try_guarded_import_is_optional(self):
        req, opt = self._one("try:\n    import widget\nexcept ImportError:\n    widget = None\n")
        assert (req, opt) == (set(), {"widget"})

    def test_importorskip_makes_it_optional(self):
        src = 'import pytest\nwidget = pytest.importorskip("widget")\nimport widget\n'
        assert "widget" in self._one(src)[1]

    def test_a_nested_import_inside_a_function_still_counts(self):
        """The setuptools shape: deferred, unguarded, fails at call time."""
        assert self._one("def f():\n    from widget.sub import thing\n")[0] == {"widget"}

    def test_an_else_branch_is_not_guarded(self):
        """``try: ... else: import x`` runs only on success, so x is required."""
        src = "try:\n    pass\nexcept ImportError:\n    pass\nelse:\n    import widget\n"
        assert self._one(src)[0] == {"widget"}

    def test_a_whole_file_skipif_guards_a_deferred_import(self):
        """The sqlite-vec shape: no test in the file runs, so nothing calls it."""
        src = ("import pytest\n"
               "pytestmark = pytest.mark.skipif(not probe(), reason='x')\n"
               "def helper():\n    import widget\n")
        req, opt = self._one(src)
        assert "widget" in opt and "widget" not in req

    def test_a_whole_file_skipif_does_not_guard_a_top_level_import(self):
        """A marker is consulted after collection; a module import is not."""
        src = ("import pytest\nimport widget\n"
               "pytestmark = pytest.mark.skipif(not probe(), reason='x')\n")
        assert "widget" in self._one(src)[0]

    def test_a_plain_pytestmark_is_not_a_skip(self):
        """``pytestmark = pytest.mark.slow`` guards nothing."""
        src = ("import pytest\npytestmark = pytest.mark.slow\n"
               "def helper():\n    import widget\n")
        assert "widget" in self._one(src)[0]

    def test_one_unguarded_site_outweighs_a_guarded_one(self, tmp_path):
        """Across files, not within one: the leg breaks on the bare import.

        This is the real ``setuptools`` situation in miniature — plenty of
        files never touch it, and one imports it without a guard.
        """
        (tmp_path / "a_test.py").write_text(
            "import pytest\nwidget = pytest.importorskip('widget')\n")
        (tmp_path / "b_test.py").write_text("import widget\n")
        required, optional = _scan([tmp_path])
        assert "widget" in required
        assert "widget" not in optional

    def test_an_empty_scan_finds_nothing(self, tmp_path):
        assert _scan([tmp_path]) == (set(), set())


class TestInstallParsing:
    """The pip-line reader, which can be quietly wrong in either direction.

    A false negative here is the whole bug class this file exists for: the
    parser reports a distribution as installed, the job cannot import it, and
    nothing says so until a cron goes red. Each of these is a shape that was
    actually mis-read while the reader was being written.
    """

    def test_a_named_distribution_is_installed(self):
        assert _installs("pip install widget") == {"widget"}

    def test_a_version_specifier_is_stripped(self):
        assert _installs("pip -q install 'widget>=8' other==1.2") == {"widget", "other"}

    def test_a_venv_path_prefix_and_quotes_are_tolerated(self):
        """ci.yml's `tests` job spells it `"$VENV_BIN/pip" -q install ...`."""
        assert _installs('"$VENV_BIN/pip" -q install widget') == {"widget"}

    def test_a_comment_mentioning_pip_install_is_not_a_pip_line(self):
        """The comment explaining this very bug parsed as an install.

        `# ... `pip install -e .` resolves the build backend in an isolated
        environment` added `an`, `build`, `the` and `resolves` to floors.yml's
        installed set — harmless there, and a false *negative* the first time
        a comment happens to name a real distribution.
        """
        run = ("# `pip install -e .` resolves the build backend in an env\n"
               "pip install widget\n")
        assert _installs(run) == {"widget"}

    def test_a_trailing_shell_operator_ends_the_argument_list(self):
        """`pip -q install sqlite-vec || true` installs one thing, not three."""
        assert _installs("pip -q install sqlite-vec || true") == {"sqlite-vec"}

    def test_an_editable_dot_names_nothing(self):
        assert _installs("pip install -e . widget") == {"widget"}

    def test_an_extras_install_names_nothing(self):
        """`-e '.[rag]'` installs the extra's dependencies, but not by name."""
        assert _installs("pip -q install -e '.[rag]'") == set()

    def test_a_requirements_file_contributes_what_it_pins(self):
        assert "setuptools" in _installs("pip install -r requirements/test-tools.txt")

    def test_the_requirements_filename_is_not_itself_a_distribution(self):
        """It fell through to the name branch and installed `test-tools-txt`."""
        got = _installs("pip install -r requirements/test-tools.txt")
        assert not any(g.startswith("test-tools") for g in got)

    def test_a_requirements_file_that_is_not_there_contributes_nothing(self):
        """The conservative reading: a loud false positive, never a silent pass.

        Spelled with a name that cannot exist rather than with floors.yml's
        real `requirements-lowest.txt`, which this test first used and which
        made it environment-dependent — that job compiles the file into its
        own workspace before running the suite, so the assertion held in a
        checkout and failed inside the one job it described.
        """
        assert not (ROOT / "requirements/no-such-file.txt").exists()
        assert _installs("pip install -r requirements/no-such-file.txt") == set()

    def test_a_marker_gated_pin_still_counts(self):
        """`pyyaml==6.0.3 ; python_full_version != '3.13.*' \\` is a real shape."""
        assert "pyyaml" in _locked_names("requirements/mutation-tools.txt")

    def test_names_are_compared_in_one_spelling(self):
        """The two real cases: PyYAML's casing and sqlite-vec's separator.

        A lock file is written PEP 503-normalized and MODULE_TO_DIST is typed
        by hand, so `yaml -> PyYAML` has to meet `pyyaml==6.0.3` and
        `sqlite_vec -> sqlite-vec` has to meet `sqlite-vec==`. Runs of `_`,
        `-` and `.` collapse to one `-`, which is PEP 503 exactly — so
        `py_yaml` becomes `py-yaml`, a different project, and correctly does
        not match `pyyaml`.
        """
        assert _norm("PyYAML") == _norm("pyyaml") == "pyyaml"
        assert _norm("sqlite_vec") == _norm("sqlite-vec") == "sqlite-vec"
        assert _norm("zope.interface") == _norm("zope-interface")
        assert _norm("py_yaml") != _norm("pyyaml")

    def test_installs_are_attributed_to_the_interpreter_they_land_in(self):
        """The finding that made the whole check satisfiable the wrong way.

        `floors.yml` installs uv into the *runner's* Python at the top of the
        same `run:` block whose `.venv` runs the suite. A union over the block
        cannot tell "setuptools is on the suite's path" from "setuptools is
        on some path", so moving the name one line up would have left this
        file green with the job still red on seventeen imports.
        """
        run = ("python -m pip -q install uv\n"
               ".venv/bin/pip -q install pytest\n")
        assert _installs(run, ".venv") == {"pytest"}
        assert _installs(run, "system") == {"uv"}
        assert _installs(run) == {"uv", "pytest"}   # None means "any"

    def test_every_spelling_of_the_venv_is_one_interpreter(self):
        # ci.yml writes `$VENV_BIN` so one `run:` serves POSIX and Windows;
        # reading those as three interpreters would split a job's installs
        # away from the pytest that needs them.
        for exe in (".venv/bin/pip", ".venv/Scripts/pip", '"$VENV_BIN/pip"',
                    "${VENV_BIN}/pip"):
            assert _installs("%s install rich" % exe, ".venv") == {"rich"}

    def test_a_bare_pip_and_python_dash_m_are_both_the_system(self):
        assert _installs("pip install rich", "system") == {"rich"}
        assert _installs("python3.12 -m pip install rich", "system") == {"rich"}
        assert _installs("pip install rich", ".venv") == set()

    def test_a_semicolon_ends_the_command(self):
        # `;` is the separator the old stop-token check could not see:
        # `str.split()` leaves it attached to the word before it, so no
        # element ever equalled ";" and `pip install pytest; echo setuptools`
        # credited setuptools. (`||`, `&&` and `|` are surrounded by spaces in
        # every real line here and did split, so the check was under-reaching
        # rather than dead — an earlier comment here said dead.)
        got = _installs("pip install pytest; echo setuptools")
        assert got == {"pytest"}

    def test_a_word_that_is_not_a_command_head_is_not_an_install(self):
        assert _installs("echo 'run pip install setuptools by hand'") == set()
        assert _installs("grep -q pip install < notes.txt") == set()

    def test_a_separator_inside_quotes_is_not_a_separator(self):
        """The false credit a raw-text split produced.

        `echo "…; pip install setuptools"` runs no pip at all. Splitting the
        text made the quoted tail its own command, so a job that merely
        *mentions* the fix in a step-summary line was credited with having
        applied it — and `test_every_harness_job_installs_what_the_suite_
        imports` would have gone green on a venv that cannot import it.
        """
        assert _installs('echo "a; pip install setuptools"') == set()
        noisy = 'echo x ; echo "y | pip install rich"'
        assert _installs(noisy) == set()
        # …while the same words unquoted still are two commands.
        assert _installs('echo a; pip install setuptools') == {"setuptools"}

    def test_a_quoted_separator_does_not_tear_a_real_line(self):
        # ci.yml really runs this. Split on the raw text it became
        # ['grep', '-E', "'^(FAILED"] and ['ERROR)', "'", '/tmp/pytest.out'].
        # S108: the path is ci.yml's, quoted so the assertion is that line
        # and not a paraphrase of it. Nothing here opens it.
        line = "grep -E '^(FAILED|ERROR) ' /tmp/pytest.out"
        assert _commands(line) == [
            ["grep", "-E", "^(FAILED|ERROR) ", "/tmp/pytest.out"]]   # noqa: S108

    def test_a_redirect_ends_the_arguments(self):
        # Otherwise the redirect target is counted as a distribution name.
        assert _installs("pip install rich >> install.log") == {"rich"}

    def test_an_unbalanced_quote_falls_back_instead_of_raising(self):
        # A helper called at collection time must not turn an unreadable
        # line into a collection error for the whole module.
        assert _installs('pip install rich "unclosed') == {"rich", "unclosed"}

    def test_an_absolute_interpreter_is_its_own_bucket(self):
        """Not `system` — the docstring used to say it was.

        A job installing with `/opt/hostedtoolcache/.../bin/python -m pip`
        and running a bare `pytest` reports the distribution missing rather
        than credited. That is the conservative direction, but only the
        docstring was wrong about which direction it is.
        """
        run = ("/opt/hostedtoolcache/Python/3.12/x64/bin/python -m pip "
               "install setuptools")
        assert _installs(run, "system") == set()
        assert _installs(run, "/opt/hostedtoolcache/Python/3.12/x64/bin") \
            == {"setuptools"}

    def test_a_backslash_continuation_is_one_line(self):
        # Defensive, and labelled as such: no workflow here wraps a `pytest`
        # or `pip install` line today — `grep -n 'pytest.*\\$'` over
        # .github/workflows is empty — so this pins a shape the parser must
        # keep handling, not one it currently meets. An earlier comment
        # claimed ci.yml wrapped its longer invocations and that the job
        # "reads as running nothing"; it does not, because no such line
        # exists. Read raw, a wrapped invocation *would* put `pytest` and its
        # paths on different lines, which is why the folding stays.
        run = ".venv/bin/pytest \\\n  tests/unit tests/functional -q\n"
        assert [p.name for p in _targets(run)] == ["unit", "functional"]
        assert _installs(".venv/bin/pip install \\\n  rich \\\n  pyyaml",
                         ".venv") == {"rich", "pyyaml"}

    def test_a_single_test_file_is_under_the_suite(self):
        # `endswith` dropped ci.yml:onnx-inference, which runs exactly one
        # file out of tests/unit from a venv it builds itself.
        assert _under_suite(ROOT / "tests/unit/test_localembed_e2e.py")
        assert _under_suite(ROOT / "tests/unit")
        assert not _under_suite(ROOT / "tests/smoke.sh")
        assert not _under_suite(ROOT / "tests/eval/golden.jsonl")

    def test_activation_keeps_the_two_interpreters_apart(self):
        """The bypass that survived the first interpreter fix.

        After `source .venv/bin/activate` every command is a *bare* name, and
        a bare name reads as the system Python — so an install before the
        activate and the suite run after it collapsed into one bucket, which
        is exactly the merge the attribution exists to prevent.
        """
        run = ("python -m pip install setuptools\n"
               "source .venv/bin/activate\n"
               "pip install pytest\n"
               "pytest tests/unit -q\n")
        assert _installs(run, "system") == {"setuptools"}
        assert _installs(run, ".venv") == {"pytest"}
        assert [i for i, _p in _pytest_runs(run)] == [".venv"]

    def test_deactivate_ends_the_activation(self):
        run = ("source .venv/bin/activate\n"
               "pip install rich\n"
               "deactivate\n"
               "pip install click\n")
        assert _installs(run, ".venv") == {"rich"}
        assert _installs(run, "system") == {"click"}

    def test_an_install_sent_elsewhere_is_not_on_the_path(self):
        """`--target` and friends put the distribution somewhere the suite
        cannot import from, and `--dry-run` installs nothing at all."""
        for flag in ("--target vendor", "-t vendor", "--prefix /opt",
                     "--root /tmp/r", "--dry-run", "--platform manylinux1"):
            run = ".venv/bin/pip install %s setuptools" % flag
            assert _installs(run, ".venv") == set(), flag
        # and the ordinary form still counts
        assert _installs(".venv/bin/pip install setuptools",
                         ".venv") == {"setuptools"}

    def test_a_pytest_node_id_still_names_its_file(self):
        """`tests/unit/test_x.py::test_y` passes `_under_suite` as a prefix
        and then scans to nothing — `is_file()` is False and `rglob` on a
        path that does not exist yields nothing — so the job reports zero
        required imports and is satisfied vacuously."""
        got = _targets(".venv/bin/pytest tests/unit/test_sdist_contents.py::t")
        assert [p.name for p in got] == ["test_sdist_contents.py"]
        assert got[0].is_file()

    def test_an_env_prefix_does_not_hide_the_command(self):
        assert _installs("env PIP_NO_CACHE=1 .venv/bin/pip install rich",
                         ".venv") == {"rich"}
        assert _installs("PIP_NO_CACHE=1 .venv/bin/pip install rich",
                         ".venv") == {"rich"}

    def test_uv_pip_install_names_its_target(self):
        assert _installs("uv pip install --python .venv/bin/python rich",
                         ".venv") == {"rich"}
        # without --python, uv installs into whatever is activated
        assert _installs("source .venv/bin/activate\nuv pip install rich",
                         ".venv") == {"rich"}

    def test_a_line_with_no_install_contributes_nothing(self):
        assert _installs("python -m venv .venv\npip download widget\n") == set()


class TestHarnessJobDiscovery:
    def test_a_job_is_collected_across_its_steps_not_within_one(self):
        """sonarcloud.yml installs in one step and runs pytest in the next.

        A per-step scan sees a pytest step that installs nothing and reports
        every dependency missing.
        """
        jobs = {f"{wf}:{job}": inst for wf, job, inst, _ in _harness_jobs()}
        assert "pytest" in jobs["sonarcloud.yml:sonar-analyze"]

    def test_only_jobs_that_run_the_suite_are_collected(self):
        """`boost-langchain.yml` builds a venv and runs `tests/langchain`.

        Out of scope on purpose: it installs `-e '.[langchain]'`, so what it
        provides comes from pyproject's optional-dependencies rather than a
        pip line, and that tree's imports are not in MODULE_TO_DIST.
        """
        found = {wf for wf, _, _, _ in _harness_jobs()}
        assert "boost-langchain.yml" not in found

    def test_both_workflow_extensions_are_scanned(self, tmp_path, monkeypatch):
        """GitHub reads ``.yaml`` as readily as ``.yml``.

        Globbing one of them makes a job written in the other invisible to
        every check in this file — the same failure as naming one job, one
        character wider. Planted rather than asserted over the real
        directory, which holds no ``.yaml`` today: a test that passes because
        the input it guards against is absent is not guarding anything.
        """
        (tmp_path / "a.yml").write_text("on: push\n", encoding="utf-8")
        (tmp_path / "b.yaml").write_text("on: push\n", encoding="utf-8")
        (tmp_path / "c.md").write_text("not a workflow\n", encoding="utf-8")
        monkeypatch.setattr("test_canary_deps.WORKFLOWS", tmp_path)

        assert [f.name for f in _workflow_files()] == ["a.yml", "b.yaml"]

    def test_the_real_workflow_directory_is_fully_covered(self):
        found = {f.name for f in _workflow_files()}
        assert found == {f.name for f in WORKFLOWS.iterdir()
                         if f.suffix in {".yml", ".yaml"}}
        assert "ci.yml" in found

    def test_no_harness_job_installs_conditionally(self):
        """The one shape this file's parser cannot read correctly.

        Nothing here evaluates conditions, so a `pip install` behind a shell
        `if`/`case` or a step-level YAML `if:` is credited unconditionally —
        the dangerous direction, since the job can then be missing at runtime
        what this check says it has. No harness job does that today.
        """
        assert _conditional_install_jobs() == []

    def test_a_step_level_if_is_what_that_check_must_catch(self, tmp_path,
                                                           monkeypatch):
        # Planted, because the repo contains no such step: asserting `== []`
        # over the real directory passes just as well with the check deleted.
        _plant(tmp_path, "probe.yml", """
on: push
jobs:
  gated:
    steps:
      - run: |
          python -m venv .venv
          .venv/bin/pip -q install pytest
      - if: runner.os == 'Linux'
        run: .venv/bin/pip -q install setuptools
      - run: .venv/bin/pytest tests/unit -q
""", monkeypatch)
        monkeypatch.setattr("test_canary_deps.HARNESS_JOBS", {"probe.yml:gated"})

        assert _conditional_install_jobs() == ["probe.yml:gated"]

    def test_a_shell_if_is_caught_too(self, tmp_path, monkeypatch):
        _plant(tmp_path, "probe.yml", """
on: push
jobs:
  gated:
    steps:
      - run: |
          python -m venv .venv
          if [ "$RUNNER_OS" = Linux ]; then
            .venv/bin/pip -q install setuptools
          fi
          .venv/bin/pytest tests/unit -q
""", monkeypatch)
        monkeypatch.setattr("test_canary_deps.HARNESS_JOBS", {"probe.yml:gated"})

        assert _conditional_install_jobs() == ["probe.yml:gated"]

    def test_an_unconditional_install_is_not_flagged(self, tmp_path,
                                                     monkeypatch):
        _plant(tmp_path, "probe.yml", """
on: push
jobs:
  plain:
    steps:
      - run: |
          python -m venv .venv
          .venv/bin/pip -q install pytest setuptools
          .venv/bin/pytest tests/unit -q
""", monkeypatch)
        monkeypatch.setattr("test_canary_deps.HARNESS_JOBS", {"probe.yml:plain"})

        assert _conditional_install_jobs() == []

    def test_no_venv_job_runs_the_suite_in_a_way_this_file_cannot_read(self):
        """The blind spot that would make a job vacuously compliant.

        Collection needs two things it cannot infer: some step's `run:` must
        mention a venv, and some command must be a `pytest` carrying a
        `tests/` argument. A job that builds a venv and then runs the suite
        through `make test`, `nox`, `tox`, `uv run pytest`, or a bare
        `pytest -q` taking its paths from config satisfies neither — so it is
        not collected, not checked, and not in HARNESS_JOBS either, which
        means the pin test stays green while a whole job goes unexamined.

        The two jobs that legitimately qualify are named in
        `OUT_OF_SCOPE_JOBS` with their reasons, and this is an *equality*: an
        entry that stops matching is as much a stale claim as a new blind
        spot is a gap.
        """
        missed = set(_unreadable_suite_jobs())
        assert missed == OUT_OF_SCOPE_JOBS, (
            "unexplained: %s   ·   no longer matching: %s"
            % (sorted(missed - OUT_OF_SCOPE_JOBS),
               sorted(OUT_OF_SCOPE_JOBS - missed)))

    def test_a_make_test_job_is_what_that_check_must_catch(self, tmp_path,
                                                           monkeypatch):
        # Again planted: the repo has no such job, so `== OUT_OF_SCOPE_JOBS`
        # over the real directory cannot show the detector works at all.
        _plant(tmp_path, "probe.yml", """
on: push
jobs:
  via-make:
    steps:
      - run: |
          python -m venv .venv
          .venv/bin/pip -q install pytest
          make test
""", monkeypatch)

        assert _unreadable_suite_jobs() == ["probe.yml:via-make"]
        assert [j for _w, j, _i, _t in _harness_jobs()] == []   # uncollected

    def test_a_readable_job_is_collected_rather_than_flagged(self, tmp_path,
                                                             monkeypatch):
        _plant(tmp_path, "probe.yml", """
on: push
jobs:
  readable:
    steps:
      - run: |
          python -m venv .venv
          .venv/bin/pip -q install pytest
          .venv/bin/pytest tests/unit -q
""", monkeypatch)

        assert _unreadable_suite_jobs() == []
        assert [j for _w, j, _i, _t in _harness_jobs()] == ["readable"]

    def test_which_jobs_install_from_a_requirements_file(self):
        """An equality, so a new job fails as loudly as a removed one.

        `_installs` expands `-r <file>` because a job that installs only
        that way would otherwise read as installing nothing. The docstring
        said three such jobs long after there were four — a number in prose
        that nothing checked.

        Two sets, because they are not the same question. The committed
        `requirements/*.txt` files are the hash-pinned ones a lock audit
        covers; `floors.yml:lowest` reads `requirements-lowest.txt`, which
        the job *generates* a step earlier with `uv pip compile`, so it is
        expanded by the same code path and pinned by nothing else.
        """
        committed, generated = set(), set()
        for wf, job, _installed, _t in _harness_jobs():
            for run in _runs_of(wf, job):
                for _active, words in _stream(run):
                    pair = _pip_install(words)
                    for arg in pair[1] or () if pair else ():
                        if arg.startswith("requirements/"):
                            committed.add(f"{wf}:{job}")
                        elif arg.endswith(".txt"):
                            generated.add(f"{wf}:{job}")
        assert committed == {
            "ci.yml:tests", "ci.yml:patch-coverage", "ci.yml:onnx-inference",
            "sonarcloud.yml:sonar-analyze",
        }
        assert generated == {"floors.yml:lowest"}
        # `ci.yml:canary` is in neither: it names every distribution on the
        # command line, which is why it is the job this file pins hardest.
        assert "ci.yml:canary" not in committed | generated

    def test_the_single_file_job_resolves_to_that_file(self):
        """A pin on what a job's targets *are*, not that it has some.

        The assertion this replaces looped over `_harness_jobs()` and
        re-checked the two conditions `_harness_jobs` filters on — `targets`
        non-empty and every target `_under_suite`. Both hold by construction
        for every row it can emit, so the test passed with `_under_suite`
        stubbed to `True` (nothing changes) and with it stubbed to `False`
        (no rows, loop body never runs). `_under_suite` is covered directly
        by `test_a_single_test_file_is_under_the_suite`; what was not covered
        is that a target survives collection intact.
        """
        rows = {job: targets for _wf, job, _i, targets in _harness_jobs()}
        assert "onnx-inference" in rows, "the single-file harness job moved"
        assert [p.relative_to(ROOT).as_posix() for p in rows["onnx-inference"]] \
            == ["tests/unit/test_localembed_e2e.py"]
