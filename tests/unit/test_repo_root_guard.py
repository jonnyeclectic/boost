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
import os
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
        # So these are watched by their boost markers, which is what the
        # fingerprint below makes possible.
        root = Path("/repo")
        probes = set(guard.project_scope_probes(root))
        from boost_cli.core import rules
        for _global_name, project_name in rules.CONTEXT_FILES.values():
            assert root / project_name in probes, project_name

    def test_the_lock_directory_is_watched_as_well_as_the_lock(self, guard):
        # A test that writes the lock and removes the *file* in its own
        # cleanup leaves `<root>/.boost/` behind — gitignored, and invisible to
        # a probe that only names the file, because before == after == absent.
        root = Path("/repo")
        probes = set(guard.project_scope_probes(root))
        from boost_cli.core import projectlock
        lock = projectlock.lock_path(root)
        assert lock in probes and lock.parent in probes

    def test_the_project_mcp_sidecar_is_watched(self, guard):
        # `store.register_project_mcp` joins `.mcp.json` straight onto the
        # base, so no table the probe list is derived from mentions it. It is
        # also the only project-scope artifact that is committable, so leaving
        # it out of the report means the developer cleans up everything the
        # guard names and still commits one file.
        root = Path("/repo")
        from boost_cli.core import store
        assert store.project_mcp_sidecar(root) in set(
            guard.project_scope_probes(root))

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
        # A probed file that is not a context file — those take the
        # marker-only branch, see `TestAContextFileIsWatchedByItsMarkers`.
        f = tmp_path / "settings.json"
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
        # `settings.json` deliberately: a context file goes down the
        # marker-only branch instead, and would pass this vacuously.
        f = tmp_path / "settings.json"
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

    def test_a_file_replaced_inside_a_watched_directory_is_a_change(self,
                                                                     guard,
                                                                     tmp_path):
        # The destructive case, and the one a name-only listing missed:
        # `boost install <workflow> --local` writes
        # `<root>/.claude/commands/<name>.md`, and the probe is the directory.
        # Overwriting a slash command the developer wrote by hand left the
        # listing byte-identical.
        d = tmp_path / "commands"
        d.mkdir()
        (d / "review.md").write_text("mine", encoding="utf-8")
        before = guard.fingerprint_paths([d])
        (d / "review.md").write_text("theirs, and longer", encoding="utf-8")
        assert guard.repo_root_intruders(before,
                                         guard.fingerprint_paths([d])) == [str(d)]

    def test_a_symlink_repointed_inside_a_watched_directory_is_a_change(
            self, guard, tmp_path):
        # The same hole one level over: a project-scope skill install links
        # `<root>/.claude/skills/<name>` into the canonical store, so a
        # reinstall re-points a link whose *name* never changes.
        d = tmp_path / "skills"
        d.mkdir()
        (tmp_path / "store-a").mkdir()
        (tmp_path / "store-b").mkdir()
        (d / "brainstorming").symlink_to(tmp_path / "store-a")
        before = guard.fingerprint_paths([d])
        (d / "brainstorming").unlink()
        (d / "brainstorming").symlink_to(tmp_path / "store-b")
        assert guard.repo_root_intruders(before,
                                         guard.fingerprint_paths([d])) == [str(d)]

    def test_a_broken_symlink_inside_a_watched_directory_still_lists(
            self, guard, tmp_path):
        # `os.readlink` rather than `resolve()`: the entry has to answer even
        # when its target does not exist, or a dangling link left behind by a
        # half-finished install would read as no entry at all.
        d = tmp_path / "skills"
        d.mkdir()
        before = guard.fingerprint_paths([d])
        (d / "brainstorming").symlink_to(tmp_path / "nowhere")
        after = guard.fingerprint_paths([d])
        assert guard.repo_root_intruders(before, after) == [str(d)]
        assert "brainstorming|l|" in after[str(d)]

    def test_a_broken_symlink_at_a_probe_path_is_present(self, guard,
                                                          tmp_path):
        # `is_dir()` and `exists()` both follow the link, so a dangling one
        # read as absent — the same value the guard compares against.
        p = tmp_path / "skills"
        before = guard.fingerprint_paths([p])
        p.symlink_to(tmp_path / "nowhere")
        assert guard.repo_root_intruders(before,
                                         guard.fingerprint_paths([p])) == [str(p)]

    def test_an_unreadable_path_does_not_crash_the_guard(self, guard,
                                                          tmp_path,
                                                          monkeypatch):
        # The guard runs in teardown for every test in the suite. A guard that
        # can raise turns one unrelated permissions oddity into 3,000 errors.
        #
        # The error is forced rather than provoked with chmod: as root — the
        # ordinary CI container — `chmod 0o000` does not stop `scandir`, so
        # that version returned a fingerprint without ever reaching the
        # `except OSError` branch it exists to cover, and passed.
        d = tmp_path / "locked"
        d.mkdir()

        def boom(_):
            raise PermissionError(13, "nope")
        monkeypatch.setattr(guard, "_dir_entries", boom)
        assert guard.fingerprint_paths([d]) == {str(d): "e:13"}

    def test_an_unreadable_path_reads_the_same_way_twice(self, guard,
                                                          tmp_path,
                                                          monkeypatch):
        # ...and the reason has to be stable, or an unreadable probe would
        # show up as a change on every single test.
        d = tmp_path / "locked"
        d.mkdir()

        def boom(_):
            raise PermissionError(13, "nope")
        monkeypatch.setattr(guard, "_dir_entries", boom)
        assert guard.repo_root_intruders(guard.fingerprint_paths([d]),
                                         guard.fingerprint_paths([d])) == []


    def test_a_same_size_overwrite_inside_a_watched_directory_is_a_change(
            self, guard, tmp_path):
        # The `mtime_ns` half of a directory entry, which the replacement test
        # above cannot reach: there the new body is longer, so `st_size` alone
        # discriminates and the timestamp could be dropped with the suite
        # green. `os.utime` rather than a bare rewrite, because two writes
        # inside one clock tick on a coarse filesystem carry the same stamp.
        d = tmp_path / "commands"
        d.mkdir()
        f = d / "review.md"
        f.write_text("mine", encoding="utf-8")
        os.utime(f, ns=(1_000_000_000, 1_000_000_000))
        before = guard.fingerprint_paths([d])
        f.write_text("hers", encoding="utf-8")          # same byte count
        os.utime(f, ns=(2_000_000_000, 2_000_000_000))
        assert guard.repo_root_intruders(
            before, guard.fingerprint_paths([d])) == [str(d)]


class TestAContextFileIsWatchedByItsMarkers:
    """`CLAUDE.local.md`, `GEMINI.md` and `AGENTS.md` are prose humans edit.

    Hashing them whole makes any concurrent edit a test failure: `make check`
    runs for tens of minutes, so a line appended to `AGENTS.md` meanwhile fails
    one arbitrary test with the project-install message and passes on the
    re-run — a flake in a required gate, blaming an innocent test.
    """

    def test_prose_appended_by_a_human_is_not_a_change(self, guard, tmp_path):
        f = tmp_path / "AGENTS.md"
        f.write_text("# notes\n", encoding="utf-8")
        before = guard.fingerprint_paths([f])
        f.write_text("# notes\nsomething a teammate typed\n", encoding="utf-8")
        assert guard.repo_root_intruders(
            before, guard.fingerprint_paths([f])) == []

    def test_a_rule_block_appearing_is_a_change(self, guard, tmp_path):
        from boost_cli.core import rules
        start, end = rules.markers("some-rule")
        f = tmp_path / "AGENTS.md"
        f.write_text("# notes\n", encoding="utf-8")
        before = guard.fingerprint_paths([f])
        f.write_text("# notes\n%s\nbody\n%s\n" % (start, end),
                     encoding="utf-8")
        assert guard.repo_root_intruders(
            before, guard.fingerprint_paths([f])) == [str(f)]

    def test_a_rule_block_disappearing_is_a_change_too(self, guard, tmp_path):
        # Uninstall is the worse direction: a test that strips a rule the
        # developer installed leaves no trace a content hash would out-live.
        from boost_cli.core import rules
        start, end = rules.markers("some-rule")
        f = tmp_path / "GEMINI.md"
        f.write_text("%s\nbody\n%s\n" % (start, end), encoding="utf-8")
        before = guard.fingerprint_paths([f])
        f.write_text("", encoding="utf-8")
        assert guard.repo_root_intruders(
            before, guard.fingerprint_paths([f])) == [str(f)]

    def test_the_filenames_and_the_marker_come_from_rules(self, guard):
        from boost_cli.core import rules
        names, marker = guard.context_file_facts()
        assert names == {n for pair in rules.CONTEXT_FILES.values()
                         for n in pair}
        assert marker and rules.BLOCK_START.startswith(marker)
        assert "%s" not in marker

    def test_a_file_that_is_not_a_context_file_is_still_hashed(self, guard,
                                                               tmp_path):
        # The carve-out is by filename, so it must not swallow the other
        # probed file: `settings.json` carries no boost markers at all, and a
        # marker fingerprint of it would be "" before and after every hook
        # write.
        f = tmp_path / "settings.json"
        f.write_text('{"hooks": {}}', encoding="utf-8")
        before = guard.fingerprint_paths([f])
        f.write_text('{"hooks": {"SessionStart": []}}', encoding="utf-8")
        assert guard.repo_root_intruders(
            before, guard.fingerprint_paths([f])) == [str(f)]


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


class TestTheRootsAreDerivedFromTheFilesystem:
    """The bug `TestWatchedRoots` below cannot catch.

    Those tests feed synthetic roots, so they pin the *function*. Under the
    mutation gate mutmut copies `tests/` into `mutants/` and runs pytest from
    there, so `Path(__file__).parent.parent` — the checkout everywhere else —
    becomes `<checkout>/mutants`. `_START_DIR` is the same directory, the two
    collapse to one root, and the project install that `scopes.resolve_base`
    puts at the real repo root goes unwatched. That is the exact run the guard
    was written for, and every assertion about `watched_roots` stayed green
    through it.
    """

    def test_a_watched_root_is_a_real_working_tree(self, guard):
        roots = guard.guard_roots()
        assert any(
            any((r / m).exists() for m in (".git", ".hg", ".svn"))
            for r in roots), roots

    def test_the_checkout_is_watched_even_when_run_from_a_copy(self, guard,
                                                               tmp_path):
        # `mutants/` shape, spelled out: a subdirectory of a working tree,
        # holding its own copy of the suite.
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        mutants = repo / "mutants"
        (mutants / "tests").mkdir(parents=True)
        assert guard.checkout_root(mutants) == repo
        assert guard.watched_roots(guard.checkout_root(mutants), mutants) \
            == [repo, mutants]

    def test_a_git_worktree_marker_is_a_file_not_a_directory(self, guard,
                                                              tmp_path):
        # This suite runs in a `git worktree`, where `.git` is a file pointing
        # at the real gitdir. An `is_dir()` check would find no marker here and
        # walk past the checkout entirely.
        repo = tmp_path / "wt"
        repo.mkdir()
        (repo / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
        deep = repo / "a" / "b"
        deep.mkdir(parents=True)
        assert guard.checkout_root(deep) == repo

    def test_no_marker_anywhere_falls_back_to_the_start_directory(self, guard,
                                                                   tmp_path):
        # An unpacked sdist. Watching *something* beats watching nothing.
        d = tmp_path / "loose"
        d.mkdir()
        if any((a / m).exists()
               for a in (d, *d.parents) for m in (".git", ".hg", ".svn")):
            pytest.skip("tmp_path is inside a working tree on this machine")
        assert guard.checkout_root(d) == d


    def test_guard_roots_watches_the_checkout_above_a_mutants_copy(
            self, guard, monkeypatch, tmp_path):
        # The composition, not its pieces. `test_a_watched_root_is_a_real_
        # working_tree` above passes in an ordinary run even with both
        # `checkout_root` calls deleted from `guard_roots`, because `ROOT` is
        # then the checkout already — so the regression it guards against
        # could land green in CI and on every machine but the mutation gate.
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        mutants = repo / "mutants"
        (mutants / "tests").mkdir(parents=True)
        monkeypatch.setattr(guard, "ROOT", mutants)
        monkeypatch.setattr(guard, "_START_DIR", mutants)
        monkeypatch.setattr(guard, "_REAL_HOME", tmp_path / "home")
        assert guard.guard_roots() == [repo, mutants]

    def test_the_walk_stops_at_home(self, guard, tmp_path):
        # A dotfiles `$HOME`. `scopes.project_root` returns None here, so no
        # project install can land at `$HOME`, and watching it would put the
        # live `~/.claude`, `~/.codex` and `~/.boost` trees under a guard that
        # fails whichever test is running when another terminal touches them.
        home = tmp_path / "home"
        (home / ".git").mkdir(parents=True)
        start = home / "Code" / "loose"
        start.mkdir(parents=True)
        assert guard.checkout_root(start, home=home) == start

    def test_a_checkout_below_home_still_wins(self, guard, tmp_path):
        # The stop must not cost the ordinary case: every real checkout on a
        # developer machine is under `$HOME`.
        home = tmp_path / "home"
        (home / ".git").mkdir(parents=True)
        repo = home / "Code" / "boost"
        (repo / ".git").mkdir(parents=True)
        deep = repo / "tests" / "unit"
        deep.mkdir(parents=True)
        assert guard.checkout_root(deep, home=home) == repo

    def test_the_home_stop_is_captured_at_import(self, guard, monkeypatch,
                                                 tmp_path):
        # Read once, at import — which happens at collection, before any
        # fixture. A per-call read would see `sandbox`'s tempdir `$HOME`
        # instead, which is no stop at all.
        monkeypatch.setenv("HOME", str(tmp_path))
        assert tmp_path == load_conftest()._REAL_HOME


class TestTheGuardReadsNoConfig:
    """`project_scope_probes` used to call `agents.project_dotdir`, which calls
    `known_agents()`, which calls `paths.expand` on every agent's dir. That
    raises `BoostError` for an unresolvable `${VAR}` — a config state boost
    deliberately tolerates. In an autouse fixture that is not one failure, it
    is a setup error on every test in the suite, on that developer's machine
    only, with the traceback pointing at the guard."""

    def test_probes_survive_a_config_that_cannot_be_loaded(self, guard,
                                                            monkeypatch):
        from boost_cli.core import config
        monkeypatch.setattr(config, "load",
                            lambda *a, **k: (_ for _ in ()).throw(
                                RuntimeError("boom")))
        probes = guard.project_scope_probes(Path("/repo"))
        assert projectlock.lock_path(Path("/repo")) in probes

    def test_the_inlined_dotdir_matches_the_real_one(self, guard, sandbox):
        # The copy is only safe while it agrees with the original.
        from boost_cli.core import config
        for name, spec in config.DEFAULTS["agents"].items():
            skills_dir = Path(str(spec["dir"]))
            assert guard._probe_dotdir(spec) == \
                agents.project_dotdir(name, skills_dir), name

    def test_an_agent_added_by_hand_is_watched(self, guard):
        # `store.install` iterates the *live* table, so an agent a developer
        # added in config.json is one boost writes to under project scope.
        specs = {"cline": {"dir": "~/.cline/skills", "enabled": True}}
        probes = set(guard.project_scope_probes(Path("/repo"), specs=specs))
        assert Path("/repo/.cline/skills") in probes


class TestWatchedRoots:
    """Two roots, because the mutation stage runs the suite from `mutants/`.

    `.boost/skill-lock.json` lands at the repo root (project_root walks up and
    finds the checkout's `.git`), while a cwd-relative writer such as
    `claude_settings.settings_path("project")` lands in `mutants/` itself. A
    guard watching only one of them misses half the damage, and which one it
    lands in depends on the writer rather than on anything the test chose.
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
