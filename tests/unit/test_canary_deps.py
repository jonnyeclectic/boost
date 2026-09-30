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
place the same mistake lives. Five jobs across three workflow files run
``tests/unit``/``tests/functional`` out of a venv they assemble themselves,
and :func:`_harness_jobs` now finds them by shape rather than by name, so the
sixth is covered before it is written.

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

    Returns the empty set for a file that is not in the repo. That is the case
    for ``floors.yml``, whose ``requirements-lowest.txt`` is compiled by the job
    itself from pyproject at the lowest-direct resolution, and it is the
    conservative reading in the right direction: an unreadable file can only
    make this module claim something is *missing* that is really there — a loud
    false positive someone fixes — never let a real gap pass silently.
    """
    path = ROOT / rel
    if not path.is_file():
        return set()
    return {_norm(m.group(1)) for m in
            re.finditer(r"(?m)^([A-Za-z0-9][A-Za-z0-9._-]*)==", path.read_text(encoding="utf-8"))}


def _installs(run: str) -> set[str]:
    """Distributions a job's ``pip install`` lines put in its venv.

    Explicitly named ones, plus everything a committed ``-r`` file pins —
    without the second half, the three jobs that install from
    ``requirements/*.txt`` would read as installing nothing at all and every
    one of them would look broken.
    """
    got: set[str] = set()
    for raw in run.splitlines():
        # Shell comments first, or prose about pip counts as a pip line: the
        # very comment explaining that `pip install -e .` leaves nothing in
        # .venv parsed as an install of `an`, `build` and `the`.
        line = re.sub(r"(^|\s)#.*$", "", raw).strip()
        m = re.search(r"pip[\"\']?\s+(?:-q\s+)?install\s+(.*)$", line)
        if not m:
            continue
        words = m.group(1).split()
        for stop, word in enumerate(words):   # `pip install x || true`
            if word in {"||", "&&", ";", "|", "#"}:
                words = words[:stop]
                break
        skip_next = False
        for i, word in enumerate(words):
            if skip_next:            # the filename after -r is not a package
                skip_next = False
                continue
            if word in {"-r", "--requirement"} and i + 1 < len(words):
                got |= _locked_names(words[i + 1])
                skip_next = True
                continue
            bare = word.strip("'\"")
            # `-e .` and `-e '.[rag]'` install something, but not by name.
            if word.startswith("-") or bare in {".", "-e"} or bare.startswith(".["):
                continue
            got.add(_norm(re.split(r"[<>=!\[]", bare)[0]))
    return got


def _targets(run: str) -> list[Path]:
    """The ``tests/`` paths a ``run:`` block hands pytest."""
    for line in run.splitlines():
        if "pytest" in line and "tests/" in line:
            return [ROOT / w for w in line.split() if w.startswith("tests/")]
    return []


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
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
        for job_id, job in (doc.get("jobs") or {}).items():
            runs = [step.get("run") or "" for step in (job.get("steps") or [])]
            if not any("venv" in r for r in runs):
                continue
            targets = [t for r in runs for t in _targets(r)
                       if any(str(t).endswith(tree) for tree in SUITE_TREES)]
            if not targets:
                continue
            installs: set[str] = set()
            for r in runs:
                installs |= _installs(r)
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
#: ``workflow:job``. Pinned so a sixth is a decision: a new one that this file
#: has never seen is exactly the shape both regressions took.
HARNESS_JOBS = {
    "ci.yml:tests",            # the required coverage gate (-r test-tools.txt)
    "ci.yml:patch-coverage",   # diff-cover (-r coverage-tools.txt)
    "ci.yml:canary",           # 3.14t free-threaded, explicit pip line
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

    def test_a_requirements_file_that_is_not_in_the_repo_contributes_nothing(self):
        """floors.yml compiles `requirements-lowest.txt` at runtime.

        Empty is the conservative reading: it can only produce a loud false
        positive, never let a real gap pass.
        """
        assert _installs("pip install -r requirements-lowest.txt") == set()

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

    def test_every_collected_job_has_at_least_one_suite_target(self):
        for wf, job, _, targets in _harness_jobs():
            assert targets, f"{wf}:{job} was collected with no test path"
            for t in targets:
                assert any(str(t).endswith(tree) for tree in SUITE_TREES)
