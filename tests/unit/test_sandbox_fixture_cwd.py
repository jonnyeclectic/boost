# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the `sandbox` fixture sandboxes the working directory too.

`sandbox` redirects `HOME`, clears `BOOST_HOME`, `CODEX_HOME` and friends, and
sets five `BOOST_NO_*` guards — and used to leave the one input project scope
actually resolves against. `scopes.resolve_base` walks up from `os.getcwd()`,
so a test installing with `scope="project"` and no explicit `base` wrote into
the developer's own checkout: `.boost/skill-lock.json` plus a full agent
fan-out at the repo root, and for a rule the context files every agent working
this repo then loads as instructions.

These tests drive the property that matters — where a project-scope write
*lands* — rather than only asserting that `Path.cwd()` moved, because a fixture
that chdirs somewhere still inside the checkout would pass the latter and fail
the former.
"""
from __future__ import annotations

import os
from pathlib import Path

from boost_cli.core import projectlock, scopes

ROOT = Path(__file__).resolve().parents[2]


class TestTheFixtureMovesTheWorkingDirectory:
    def test_cwd_is_inside_the_sandbox(self, sandbox, tmp_path):
        here = Path(os.getcwd()).resolve()
        assert here.is_relative_to(tmp_path.resolve())

    def test_cwd_is_not_the_checkout(self, sandbox):
        # The assertion the other half of this file exists for. `is_relative_to`
        # rather than `!=`: a cwd three levels down inside the repo resolves to
        # the same project root and does the same damage.
        assert not Path(os.getcwd()).resolve().is_relative_to(ROOT)

    def test_the_sandbox_cwd_is_not_the_sandbox_home(self, sandbox):
        # Distinct directories on purpose. `scopes.project_root` refuses to call
        # `$HOME` a project — a "project" install there would write into the very
        # dirs user scope owns — so a cwd *equal* to the fake HOME would make
        # `resolve_base` return None and quietly change what these tests mean.
        assert Path(os.getcwd()).resolve() != sandbox.resolve()


class TestWhereAProjectScopeWriteLands:
    def test_resolve_base_stays_in_the_sandbox(self, sandbox, tmp_path):
        base = scopes.resolve_base(scopes.SCOPE_PROJECT)
        assert base is not None
        assert Path(base).resolve().is_relative_to(tmp_path.resolve())

    def test_resolve_base_is_not_the_checkout(self, sandbox):
        base = scopes.resolve_base(scopes.SCOPE_PROJECT)
        assert not Path(base).resolve().is_relative_to(ROOT)

    def test_no_project_marker_is_visible_from_the_sandbox(self, sandbox):
        # The mechanism, pinned separately from its consequence: tmp_path has no
        # `.git`, so the walk up finds nothing and `resolve_base` falls back to
        # the cwd. If a future fixture put the sandbox *under* the checkout, this
        # is the assertion that would say why the others broke.
        assert scopes.project_root() is None

    def test_the_project_lock_would_land_in_the_sandbox(self, sandbox,
                                                        tmp_path):
        lock = projectlock.lock_path(scopes.resolve_base(scopes.SCOPE_PROJECT))
        assert lock.resolve().is_relative_to(tmp_path.resolve())
        # Named explicitly because it is the file the bug left behind: a killed
        # run's `.boost/skill-lock.json` at the repo root is read back by the
        # next full suite, which then fails twelve tests that assert an empty
        # install state and name none of the tests responsible.
        assert lock.name == "skill-lock.json"


class TestATestThatWantsARealProjectSaysSo:
    """The escape hatch, pinned: the chdir must not make project roots
    untestable. A test that means to exercise "the cwd is inside a repo" plants
    its own marker, which is both explicit and independent of where the suite
    happens to be run from."""

    def test_a_planted_marker_is_found(self, sandbox, tmp_path, monkeypatch):
        repo = tmp_path / "repo" / "src" / "deep"
        repo.mkdir(parents=True)
        (tmp_path / "repo" / ".git").mkdir()
        monkeypatch.chdir(repo)
        assert scopes.project_root() == (tmp_path / "repo").resolve()
