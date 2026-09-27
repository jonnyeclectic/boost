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
    got: set[str] = set()
    for line in run.splitlines():
        m = re.search(r"pip\s+(?:-q\s+)?install\s+(.*)$", line.strip())
        if not m:
            continue
        for word in m.group(1).split():
            # -e . and -r file.txt install something, but not by name.
            if word.startswith("-") or word in {".", "-e"}:
                continue
            got.add(re.split(r"[<>=!\[]", word)[0])
    return got


def _canary_targets(run: str) -> list[Path]:
    for line in run.splitlines():
        if "pytest" in line and "tests/" in line:
            return [ROOT / w for w in line.split() if w.startswith("tests/")]
    pytest.fail("the canary step runs no tests/ path")


class TestCanaryDependencies:
    def test_every_unguarded_import_is_installed(self):
        """The regression itself: an unguarded import the leg cannot satisfy.

        One-directional on purpose — the canary also installs ``pytest-cov``
        and ``coverage``, which nothing imports by name, and an extra
        dependency costs seconds while a missing one costs the signal.
        """
        run = _canary_step()["run"]
        required, _ = _scan([*_canary_targets(run), ROOT / "tests/conftest.py"])
        installed = _canary_installs(run)
        missing = sorted(MODULE_TO_DIST.get(m, m) for m in required
                         if MODULE_TO_DIST.get(m, m) not in installed)
        assert not missing, (
            f"the canary job imports {missing} unguarded but installs "
            f"{sorted(installed)} — add them to its pip install line, or "
            f"guard the import with pytest.importorskip")

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
