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
SEPARATORS = re.compile(r"\s*(?:\|\||&&|[;|])\s*")
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


def _commands(line: str) -> list[list[str]]:
    """One shell line split into the commands it actually runs.

    Splitting on the separators is what makes ``echo`` an ``echo``: matching
    ``pip.*install`` anywhere in the line credited
    ``pip install pytest; echo setuptools`` with setuptools, and a
    ``words`` list built by ``str.split()`` never contained a bare ``;`` for
    the stop-token check to find, so the check was dead from the day it was
    written.
    """
    out = []
    for chunk in SEPARATORS.split(line):
        words = chunk.split()
        while words and words[0] in {"then", "do", "sudo", "time", "exec"}:
            words = words[1:]
        if words:
            out.append(words)
    return out


def _interpreter(word: str) -> str:
    """Which Python a command's executable belongs to.

    ``system`` for a bare name or an absolute one, ``.venv`` for every
    spelling of the venv this repo builds, and the directory itself for
    anything else. Without this the checks are satisfiable by installing into
    the wrong Python: ``floors.yml`` runs ``python -m pip install uv`` on the
    runner's interpreter at the top of the same block whose venv runs the
    suite, so a union over the block cannot tell a fixed job from a broken
    one, and moving ``setuptools`` onto that line would leave this file green
    with the job still red on seventeen ModuleNotFoundErrors.
    """
    bare = word.strip("'\"")
    head, _, _leaf = bare.rpartition("/")
    if not head:
        return "system"
    if VENV_BIN.match(head):
        return ".venv"
    return head


def _pip_install(words: list[str]) -> tuple[str, list[str]] | None:
    """``(interpreter, arguments)`` if this command is a pip install."""
    head = words[0].strip("'\"")
    rest = words[1:]
    if PYTHON.fullmatch(head) and rest[:2] == ["-m", "pip"]:
        rest = rest[2:]
    elif not PIP.fullmatch(head):
        return None
    while rest and rest[0].startswith("-"):     # pip's own flags, e.g. -q
        rest = rest[1:]
    if not rest or rest[0] != "install":
        return None
    return _interpreter(words[0]), rest[1:]


def _installs(run: str, interpreter: str | None = None) -> set[str]:
    """Distributions a job's ``pip install`` lines put in one interpreter.

    Explicitly named ones, plus everything a committed ``-r`` file pins —
    without the second half, the three jobs that install from
    ``requirements/*.txt`` would read as installing nothing at all and every
    one of them would look broken.

    ``interpreter`` selects which Python to count installs into; ``None``
    counts them all, which is only ever right for a job with one.

    Known limit: a ``pip install`` inside an ``if``/``case`` is credited
    unconditionally, because nothing here evaluates shell conditions.
    :meth:`TestHarnessJobDiscovery.test_no_harness_job_installs_conditionally`
    fails the build rather than let that become wrong quietly.
    """
    got: set[str] = set()
    for line in _lines(run):
        for words in _commands(line):
            parsed = _pip_install(words)
            if parsed is None:
                continue
            into, args = parsed
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
    for line in _lines(run):
        for words in _commands(line):
            head = words[0].strip("'\"")
            rest = words[1:]
            if PYTHON.fullmatch(head) and rest[:2] == ["-m", "pytest"]:
                rest = rest[2:]
            elif not PYTEST.fullmatch(head):
                continue
            paths = [ROOT / w.strip("'\"") for w in rest
                     if w.strip("'\"").startswith("tests/")]
            if paths:
                out.append((_interpreter(words[0]), paths))
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


def _canary_installs(run: str) -> set[str]:
    """Distributions the canary's ``pip install`` lines name explicitly."""
    return _installs(run)


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
        # The stop-token check was dead: `str.split()` leaves the `;` attached
        # to the word before it, so no element ever equalled ";" and
        # `pip install pytest; echo setuptools` credited setuptools.
        got = _installs("pip install pytest; echo setuptools")
        assert got == {"pytest"}

    def test_a_word_that_is_not_a_command_head_is_not_an_install(self):
        assert _installs("echo 'run pip install setuptools by hand'") == set()
        assert _installs("grep -q pip install < notes.txt") == set()

    def test_a_backslash_continuation_is_one_line(self):
        # ci.yml wraps its longer invocations. Read raw, `pytest` and the
        # paths land on different lines and the job reads as running nothing.
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

    def test_both_workflow_extensions_are_scanned(self):
        # GitHub reads `.yaml` as readily as `.yml`. Globbing one of them
        # would make a job written in the other invisible to every check
        # here — the same failure as naming one job, one character wider.
        found = {f.name for f in _workflow_files()}
        assert found == {f.name for f in WORKFLOWS.iterdir()
                         if f.suffix in {".yml", ".yaml"}}
        assert "ci.yml" in found

    def test_no_harness_job_installs_conditionally(self):
        """The one shape this file's parser cannot read correctly.

        Nothing here evaluates shell conditions, so a `pip install` inside an
        `if` or a `case` is credited unconditionally — the dangerous
        direction, since the job can then be missing at runtime what this
        check says it has. No harness job does that today. This fails the
        build the day one starts, rather than letting the check quietly go
        one-sided.
        """
        guilty = []
        for wf in _workflow_files():
            doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
            for job_id, job in (doc.get("jobs") or {}).items():
                if "%s:%s" % (wf.name, job_id) not in HARNESS_JOBS:
                    continue
                for step in job.get("steps") or []:
                    body = step.get("run") or ""
                    if not any(_pip_install(c) for ln in _lines(body)
                               for c in _commands(ln)):
                        continue
                    if re.search(r"(?m)^\s*(if|case)\s", body):
                        guilty.append("%s:%s" % (wf.name, job_id))
        assert not guilty, (
            "these jobs wrap a pip install in a shell conditional, which "
            "_installs() credits unconditionally: %s" % sorted(set(guilty)))

    def test_every_collected_job_has_at_least_one_suite_target(self):
        for wf, job, _, targets in _harness_jobs():
            assert targets, f"{wf}:{job} was collected with no test path"
            for t in targets:
                assert _under_suite(t), f"{wf}:{job} collected {t}"
