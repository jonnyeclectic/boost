# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the conftest guard that catches a test writing into the checkout.

The `sandbox` fixture now chdirs, so no test *should* reach the developer's
own tree. This is the backstop for when one does anyway — a new test that
forgets `sandbox`, an explicit `base=` built from the wrong root, or a mutant
that weakens a scope guard while the mutation stage runs the suite against
`boost_cli/core`. The value it adds is not detection but *attribution*: the
failure it caused last time was twelve tests across four files asserting an
empty install state, none of which named the test that filled it.

The logic is tested as pure functions against a fake root, the way this repo
already tests `absolutize_source_paths` — driving it through a real pytest run
would need the failure it exists to raise.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from boost_cli.core import agents, claude_settings, hookhost, projectlock

CONFTEST = Path(__file__).resolve().parents[1] / "conftest.py"


def load_conftest():
    """Import tests/conftest.py by path, the way this repo tests scripts/."""
    spec = importlib.util.spec_from_file_location("boost_conftest_guard_test",
                                                  CONFTEST)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def guard():
    return load_conftest()


class TestWhatIsWatched:
    """The probe list is derived from the tables the writers read, so it
    cannot drift from them silently. These pin each derivation separately —
    a single "the list is N long" assertion would pass for the wrong reason
    the first time an agent is added."""

    def test_the_project_lock_is_watched(self, guard):
        root = Path("/repo")
        probes = guard.project_scope_probes(root)
        assert projectlock.lock_path(root) in probes

    def test_every_project_scope_agent_contributes_its_skills_dir(self, guard,
                                                                  sandbox):
        # `sandbox` so `known_agents()` reads DEFAULTS rather than the
        # developer's own config.json — the probe list is derived from DEFAULTS
        # directly, and this is what pins the two derivations together.
        root = Path("/repo")
        probes = set(guard.project_scope_probes(root))
        for name, spec in agents.project_agents().items():
            dotdir = agents.project_dotdir(name, spec)
            assert root / dotdir / Path(spec).name in probes, name

    def test_an_agent_outside_project_scope_is_not_watched(self, guard,
                                                           sandbox):
        # antigravity declares `project_scope: false` — its skills dir is two
        # levels under its dotdir, so there is no repo-local path to watch.
        # Watching a derived one would mean watching `<repo>/antigravity-cli`,
        # a directory nothing ever writes.
        root = Path("/repo")
        probes = set(guard.project_scope_probes(root))
        assert root / "antigravity-cli" / "skills" not in probes

    def test_every_hook_host_contributes_its_project_settings_file(self, guard):
        root = Path("/repo")
        probes = set(guard.project_scope_probes(root))
        for host in hookhost.hosts():
            want = claude_settings.settings_path("project", project_dir=root,
                                                 host=host)
            assert want in probes, host

    def test_the_rule_context_files_are_watched(self, guard):
        # A rule install does not create a file — it *edits* one that already
        # exists and that every agent working this repo loads as instructions.
        # So these are watched by content, which is what the fingerprint below
        # makes possible.
        root = Path("/repo")
        probes = set(guard.project_scope_probes(root))
        from boost_cli.core import rules
        for _global_name, project_name in rules.CONTEXT_FILES.values():
            assert root / project_name in probes, project_name

    def test_probes_are_deduplicated(self, guard):
        # claude-code's `.claude` arrives from the agent table and again from
        # the hook host table; GEMINI.md is both agents' context file. A
        # duplicated probe is harmless but would make the count meaningless.
        probes = guard.project_scope_probes(Path("/repo"))
        assert len(probes) == len(set(probes))

    def test_every_probe_is_under_the_root(self, guard):
        root = Path("/repo")
        for p in guard.project_scope_probes(root):
            assert p.is_relative_to(root), p


class TestFingerprint:
    def test_a_missing_path_is_absent_not_empty(self, guard, tmp_path):
        # Absent, not `""`. Two absences must never compare equal to a present
        # empty directory, or a test that *removed* the last skill from a real
        # `.claude/skills` would read as no change.
        fp = guard.fingerprint_paths([tmp_path / "nope"])
        assert fp == {}

    def test_a_file_is_fingerprinted_by_content(self, guard, tmp_path):
        f = tmp_path / "AGENTS.md"
        f.write_text("before", encoding="utf-8")
        before = guard.fingerprint_paths([f])
        f.write_text("after", encoding="utf-8")
        after = guard.fingerprint_paths([f])
        assert before != after
        assert guard.repo_root_intruders(before, after) == [str(f)]

    def test_a_file_rewritten_with_the_same_bytes_is_not_a_change(self, guard,
                                                                  tmp_path):
        # mtime would call this a change. It is not one, and a guard that
        # cried wolf on an idempotent write would be turned off within a week.
        f = tmp_path / "CLAUDE.local.md"
        f.write_text("same", encoding="utf-8")
        before = guard.fingerprint_paths([f])
        f.write_text("same", encoding="utf-8")
        assert guard.repo_root_intruders(before,
                                         guard.fingerprint_paths([f])) == []

    def test_a_directory_is_fingerprinted_by_its_entries(self, guard, tmp_path):
        d = tmp_path / "skills"
        d.mkdir()
        before = guard.fingerprint_paths([d])
        (d / "brainstorming").mkdir()
        after = guard.fingerprint_paths([d])
        assert guard.repo_root_intruders(before, after) == [str(d)]

    def test_a_directorys_contents_are_not_walked(self, guard, tmp_path):
        # Immediate entries only. `.claude/` in this checkout holds
        # `worktrees/`, so a recursive fingerprint would walk every other
        # agent's tree twice per test.
        d = tmp_path / "skills"
        (d / "brainstorming").mkdir(parents=True)
        before = guard.fingerprint_paths([d])
        (d / "brainstorming" / "SKILL.md").write_text("x", encoding="utf-8")
        assert guard.repo_root_intruders(before,
                                         guard.fingerprint_paths([d])) == []

    def test_an_unreadable_path_does_not_crash_the_guard(self, guard, tmp_path):
        # The guard runs in teardown for every test in the suite. A guard that
        # can raise turns one unrelated permissions oddity into 3,000 errors.
        d = tmp_path / "locked"
        d.mkdir()
        d.chmod(0o000)
        try:
            assert guard.fingerprint_paths([d]) != {}
        finally:
            d.chmod(0o755)


class TestIntruders:
    def test_nothing_changed_reports_nothing(self, guard):
        snap = {"/repo/.boost/skill-lock.json": "f:abc"}
        assert guard.repo_root_intruders(snap, dict(snap)) == []

    def test_an_appearance_is_reported(self, guard):
        assert guard.repo_root_intruders(
            {}, {"/repo/.boost/skill-lock.json": "f:abc"}) \
            == ["/repo/.boost/skill-lock.json"]

    def test_a_disappearance_is_reported_too(self, guard):
        # A test that *deletes* the developer's `.claude/settings.json` is the
        # same class of bug and strictly worse — it destroys state instead of
        # adding it — so the diff is symmetric rather than append-only.
        assert guard.repo_root_intruders(
            {"/repo/.claude/settings.json": "f:abc"}, {}) \
            == ["/repo/.claude/settings.json"]

    def test_the_report_is_sorted(self, guard):
        got = guard.repo_root_intruders(
            {}, {"/repo/z": "f:1", "/repo/a": "f:2", "/repo/m": "f:3"})
        assert got == ["/repo/a", "/repo/m", "/repo/z"]


class TestWatchedRoots:
    """Two roots, because the mutation stage runs the suite from `mutants/`.

    `.boost/skill-lock.json` lands at the repo root (project_root walks up and
    finds the checkout's `.git`), while a cwd-relative writer such as
    `claude_settings.settings_path("project")` lands in `mutants/` itself. A
    guard watching only one of them misses half the damage — measured: a
    `mutants/.codex/hooks.json` left by a mutant execution was read back by the
    next clean-test run and failed it.
    """

    def test_the_checkout_and_the_start_directory_are_both_watched(self, guard,
                                                                   tmp_path):
        root = tmp_path / "repo"
        start = root / "mutants"
        start.mkdir(parents=True)
        assert guard.watched_roots(root, start) == [root, start]

    def test_one_root_when_the_suite_starts_at_the_checkout(self, guard,
                                                            tmp_path):
        root = tmp_path / "repo"
        root.mkdir()
        assert guard.watched_roots(root, root) == [root]

    def test_a_start_directory_outside_the_checkout_is_still_watched(
            self, guard, tmp_path):
        # Running `pytest /path/to/boost/tests` from somewhere else entirely.
        # That directory is someone's working tree too.
        root = tmp_path / "repo"
        other = tmp_path / "elsewhere"
        root.mkdir()
        other.mkdir()
        assert guard.watched_roots(root, other) == [root, other]
