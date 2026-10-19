# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost sync` over store dirs it did not install, and plugin duplicates.

The store dirs the lock does not record used to be one bucket, "orphaned
store dirs", that plain sync ignored and `--prune` deleted wholesale. On the
machine that prompted this they were three different things — a skill the
user wrote, ports of Cursor's built-in skills, and another tool's sync bucket
— and only the ports were copies. These tests pin each answer, and each
re-check standing between a confirm and a deletion.
"""
from __future__ import annotations

import errno
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from boost_cli.core import (
    agents,
    catalog,
    config,
    foreign,
    integrity,
    lockfile,
    paths,
    registry,
    store,
)
from boost_cli.errors import BoostError

#: chmod cannot take the owner's own read or search access away on Windows,
#: and root reads through any mode.
posix_modes = pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="needs POSIX permission bits, as a user other than root")

LINKED = ["claude-code", "windsurf", "cursor", "antigravity"]
REST = [a for a in LINKED if a != "claude-code"]
EMPTY = {"adoptable_store": [], "older_copies": [], "foreign_store": [],
         "not_skill_store": [], "unreadable_store": []}
PLUGIN = "eight-backend@eight"


@pytest.fixture()
def installed(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    store.install(catalog.resolve_one("brainstorming"))
    return t


def _skill(d: Path, body: str = "# s\n", when: float | None = None) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")
    if when is not None:
        os.utime(d / "SKILL.md", (when, when))
    return d


def _mine(name: str, body: str = "# mine\n", when: float | None = None) -> Path:
    return _skill(paths.store_dir() / name, body, when)


def _vendor(name: str, body: str = "# vendor\n") -> Path:
    return _skill(paths.home() / ".cursor" / "skills-cursor" / name, body)


def _codex(name: str, body: str = "# codex\n", when: float | None = None) -> Path:
    return _skill(paths.home() / ".codex" / "skills" / name, body, when)


def _classify(*names):
    return store.classify_unrecorded(list(names))


def _claude_link(name: str = "brainstorming") -> Path:
    return paths.home() / ".claude" / "skills" / name


def _leads_to(link: Path, target: Path) -> bool:
    return (store.normalize_link_target(link.readlink())
            == store.normalize_link_target(target))


def _disable_claude_code() -> None:
    cfg = config.load()
    cfg["agents"]["claude-code"]["enabled"] = False
    config.save(cfg)


def _set(name: str, **fields) -> None:
    e = lockfile.get_skill(name)
    e.update(fields)
    lockfile.set_skill(name, e)


def _dir_marketplace(body: str | None) -> Path:
    """Re-home ``claude_plugin``'s marketplace in a folder of the user's.

    One added with ``claude plugin marketplace add <dir>``: Claude Code reads
    the plugin from the folder every session, not from its ``installPath``.
    ``body`` is the folder's ``brainstorming``, None for a copy of the
    store's. Returns that skill's dir.
    """
    mdir = paths.home() / "src" / "eight"
    plugins = paths.home() / ".claude" / "plugins"
    (plugins / "known_marketplaces.json").write_text(json.dumps({"eight": {
        "source": {"source": "directory", "path": str(mdir)},
        "installLocation": str(mdir)}}), encoding="utf-8")
    (mdir / ".claude-plugin").mkdir(parents=True)
    (mdir / ".claude-plugin" / "marketplace.json").write_text(json.dumps({
        "name": "eight", "plugins": [{"name": "eight-backend",
                                      "source": "./plugins/eight-backend"}]}),
        encoding="utf-8")
    where = mdir / "plugins" / "eight-backend" / "skills" / "brainstorming"
    if body is None:
        shutil.copytree(paths.store_dir() / "brainstorming", where)
        return where
    return _skill(where, body)


class TestUnrecordedStoreDirs:
    def test_only_unrecorded_directories(self, installed):
        _mine("a")
        (paths.store_dir() / "b").mkdir()
        (paths.store_dir() / ".trash").mkdir(exist_ok=True)
        (paths.store_dir() / "file.txt").write_text("x", encoding="utf-8")
        assert store.unrecorded_store_dirs(lockfile.installed()) == ["a", "b"]

    def test_an_unreadable_store_holds_none(self, sandbox, monkeypatch):
        _mine("a")
        _mine("b copy")

        def boom(_p):
            raise PermissionError("no")
        monkeypatch.setattr(store.os, "listdir", boom)
        assert store.unrecorded_store_dirs({}) == []
        assert store.misnamed_store_dirs() == []

    def test_a_name_boost_cannot_record_is_kept_apart(self, sandbox):
        # A Finder duplicate stopped `boost doctor` three checks in: every path
        # into the store refuses the name.
        _mine("a")
        _mine("brainstorming copy")
        _mine("café-notes")
        (paths.store_dir() / ".a copy").mkdir()
        (paths.store_dir() / "x y.txt").write_text("x", encoding="utf-8")
        assert store.unrecorded_store_dirs({}) == ["a"]
        assert store.misnamed_store_dirs() == ["brainstorming copy", "café-notes"]


class TestHasContent:
    def test_no_store(self, sandbox):
        assert store.has_content() is False

    def test_a_dir_without_skill_md_is_not_content(self, sandbox):
        # Another tool's bucket held `boost doctor` at "lock file missing"
        # for good: there was nothing a lock could have recorded.
        (paths.store_dir() / "synced").mkdir(parents=True)
        (paths.store_dir() / "synced" / "manifest.json").write_text(
            "{}", encoding="utf-8")
        assert store.has_content() is False

    def test_a_dot_dir_is_not_content(self, sandbox):
        _mine(".trash")
        assert store.has_content() is False

    def test_a_skill_is(self, sandbox):
        (paths.store_dir() / "synced").mkdir(parents=True)
        _mine("pr-me")
        assert store.has_content() is True

    def test_an_unreadable_store_holds_none(self, sandbox, monkeypatch):
        _mine("pr-me")

        def boom(_p):
            raise PermissionError("no")
        monkeypatch.setattr(store.os, "listdir", boom)
        assert store.has_content() is False

    def test_a_dir_boost_cannot_look_into_counts(self, sandbox, monkeypatch):
        # "No SKILL.md" is an answer only when the lookup gives it: a store of
        # dirs with no search bit read as empty, which over a missing lock
        # told `verify` and `drift` there was nothing to check.
        _mine("pr-me")
        real = os.stat

        def stat(p, *a, **k):
            if str(p).endswith("SKILL.md"):
                raise PermissionError(13, "denied", str(p))
            return real(p, *a, **k)
        monkeypatch.setattr(store.os, "stat", stat)
        assert store.has_content() is True

    @posix_modes
    def test_a_dir_with_no_search_bit_counts(self, sandbox):
        d = _mine("pr-me")
        d.chmod(0o600)
        try:
            assert store.has_content() is True
        finally:
            d.chmod(0o700)

    def test_a_skill_md_that_is_not_a_file_is_none(self, sandbox):
        (paths.store_dir() / "x" / "SKILL.md").mkdir(parents=True)
        (paths.store_dir() / "notes").write_text("x", encoding="utf-8")
        assert store.has_content() is False


class TestLockVouches:
    def test_the_check_passed_in_is_the_one_read(self, installed, monkeypatch):
        monkeypatch.setattr(lockfile, "check", lambda: pytest.fail("read"))
        assert store.lock_vouches(lockfile.Integrity(True, None)) is True
        assert store.lock_vouches(lockfile.Integrity(False, "corrupt")) is False
        assert store.lock_vouches(lockfile.Integrity(False, "missing")) is False

    def test_a_missing_lock_over_an_empty_store_vouches(self, sandbox):
        assert store.lock_vouches(lockfile.Integrity(False, "missing")) is True

    def test_a_missing_lock_over_no_store_at_all_vouches(self, sandbox):
        shutil.rmtree(paths.store_dir(), ignore_errors=True)
        assert store.lock_vouches(lockfile.Integrity(False, "missing")) is True

    def test_a_missing_lock_over_any_dir_does_not(self, sandbox):
        # Not just a skill: with no lock, a link into another tool's bucket
        # (``synced/foo``) is not boost's to call stale.
        (paths.store_dir() / "synced" / "foo").mkdir(parents=True)
        assert store.lock_vouches(lockfile.Integrity(False, "missing")) is False

    def test_dot_entries_and_files_are_not_dirs(self, sandbox):
        (paths.store_dir() / ".trash").mkdir(parents=True)
        (paths.store_dir() / "notes.txt").write_text("x", encoding="utf-8")
        assert store.lock_vouches(lockfile.Integrity(False, "missing")) is True

    def test_a_store_boost_cannot_list_does_not(self, sandbox, monkeypatch):
        paths.store_dir().mkdir(parents=True, exist_ok=True)

        def boom(_p):
            raise PermissionError("no")
        monkeypatch.setattr(store.os, "listdir", boom)
        assert store.lock_vouches(lockfile.Integrity(False, "missing")) is False


class TestResolvesIntoStoreByInode:
    """APFS spells one dir several ways (``~/.Agents``, a firmlink), and
    ``resolve()`` keeps the spelling it was handed. Read as another tool's
    copy, the store's only copy was a copy of itself, and ``--prune`` deleted
    it. Simulated by making the strings disagree, so this holds on a
    case-sensitive volume too."""

    @pytest.fixture
    def respelled(self, sandbox, monkeypatch):
        root = str(paths.store_dir().resolve())

        def spell(p):
            s = str(p)
            return s if s == root else s.replace(root, root + "-SPELLED", 1)
        monkeypatch.setattr(store, "normalize_link_target", spell)

    def test_a_path_the_strings_put_outside_is_asked_by_inode(self, respelled):
        mine = _mine("my-skill")
        assert store.resolves_into_store(mine) is True
        assert store.resolves_into_store(_codex("my-skill")) is False

    def test_under(self, sandbox):
        root = paths.store_dir()
        mine = _mine("my-skill")
        assert store._under(mine, root) is True
        assert store._under(mine / "SKILL.md", root) is True
        # A path that cannot be looked at is skipped, not the end of the walk.
        assert store._under(mine / "gone" / "deeper", root) is True
        assert store._under(_codex("my-skill"), root) is False
        assert store._under(mine, root / "nowhere") is False


class TestClassifyUnrecorded:
    def test_nothing_to_classify_reads_nothing(self, sandbox, monkeypatch):
        monkeypatch.setattr(foreign, "inventory",
                            lambda *a, **k: pytest.fail("read"))
        assert _classify() == EMPTY

    def test_a_dir_without_skill_md_is_not_a_skill(self, sandbox):
        (paths.store_dir() / "synced" / "bucket").mkdir(parents=True)
        assert _classify("synced") == {**EMPTY, "not_skill_store": ["synced"]}

    def test_a_skill_nobody_else_has_is_adoptable(self, sandbox):
        _mine("pr-me")
        assert _classify("pr-me") == {**EMPTY, "adoptable_store": ["pr-me"]}

    def test_a_vendor_copy_is_foreign_whatever_its_bytes_or_age(self, sandbox):
        theirs = _vendor("automate", "# Cursor\n")
        _mine("automate", "# Codex port\n", when=4e9)     # newer, and changed
        assert _classify("automate") == {**EMPTY, "foreign_store": [
            ("automate", "Cursor's built-ins", str(theirs), "differs")]}

    def test_an_identical_vendor_copy_says_so(self, sandbox):
        theirs = _vendor("automate", "# same\n")
        _mine("automate", "# same\n")
        assert _classify("automate")["foreign_store"] == [
            ("automate", "Cursor's built-ins", str(theirs), "identical")]

    def test_the_identical_owner_is_named_whichever_comes_first(self, claude_plugin,
                                                                sandbox):
        # The confirm says what removing the store copy costs, and it costs
        # nothing while some owner holds the same bytes.
        _vendor("automate", "# Cursor's\n")
        theirs = claude_plugin("automate", "# same\n")
        _mine("automate", "# same\n")
        assert _classify("automate")["foreign_store"] == [
            ("automate", "Claude Code plugin %s" % PLUGIN, str(theirs), "identical")]

    def test_of_two_plugins_the_identical_one(self, claude_plugin, sandbox):
        claude_plugin("eight-adr", "# a\n", pid="a-first@m")
        theirs = claude_plugin("eight-adr", "# b\n", pid="b-second@m")
        _mine("eight-adr", "# b\n")
        assert _classify("eight-adr")["foreign_store"] == [
            ("eight-adr", "Claude Code plugin b-second@m", str(theirs), "identical")]

    @posix_modes
    def test_a_vendor_skill_it_cannot_look_in_keeps_the_name_from_adoption(
            self, sandbox):
        # Cursor's `automate` at mode 000 is invisible to the inventory, so
        # the store's copy read as nobody's and was recorded as the user's.
        theirs = _vendor("automate")
        _mine("automate")
        theirs.chmod(0)
        try:
            got = _classify("automate")
        finally:
            theirs.chmod(0o755)
        assert got == {**EMPTY, "unreadable_store": [("automate", str(theirs))]}

    @posix_modes
    def test_a_vendor_dir_it_cannot_search_keeps_every_name_from_adoption(
            self, sandbox):
        root = _vendor("automate").parent
        _mine("pr-me")
        root.chmod(0o600)
        try:
            got = _classify("pr-me")
        finally:
            root.chmod(0o755)
        assert got == {**EMPTY, "unreadable_store": [("pr-me", str(root))]}

    @posix_modes
    def test_sync_neither_records_nor_links_what_it_cannot_tell(self, installed):
        theirs = _vendor("automate")
        _mine("automate")
        theirs.chmod(0)
        try:
            actions = store.sync_apply(store.sync_plan())
        finally:
            theirs.chmod(0o755)
        assert not [a for a in actions if "automate" in a]
        assert "automate" not in lockfile.installed()
        assert not [a for a, d in agents.linking_agents().items()
                    if os.path.lexists(d / "automate")]

    def test_a_vendor_outranks_a_plugin(self, claude_plugin, installed):
        claude_plugin("automate", "# plugin\n")
        theirs = _vendor("automate")
        _mine("automate")
        assert _classify("automate")["foreign_store"] == [
            ("automate", "Cursor's built-ins", str(theirs), "differs")]

    def test_a_plugin_skill_is_foreign(self, claude_plugin, installed):
        theirs = claude_plugin("eight-adr", "# plugin\n")
        _mine("eight-adr", "# plugin\n")
        assert _classify("eight-adr")["foreign_store"] == [
            ("eight-adr", "Claude Code plugin %s" % PLUGIN, str(theirs),
             "identical")]

    def test_a_plugin_skill_is_matched_by_its_skill_md_name(self, claude_plugin,
                                                            sandbox):
        # A `cp -r` keeps the plugin's dir name; Claude Code lists the skill
        # under the frontmatter one.
        body = "---\nname: eight-adr\n---\n# plugin\n"
        theirs = claude_plugin("adr", body)
        _mine("adr", body)
        assert _classify("adr") == {**EMPTY, "foreign_store": [
            ("adr", "Claude Code plugin %s" % PLUGIN, str(theirs), "identical")]}

    def test_a_skill_md_name_nothing_else_has_owns_nothing(self, sandbox):
        _mine("pr-me", "---\nname: pr-me-v2\n---\n# mine\n")
        assert _classify("pr-me") == {**EMPTY, "adoptable_store": ["pr-me"]}

    def test_an_agent_copy_under_the_skill_md_name_is_not_one(self, sandbox):
        # Only a plugin keys its skills by the frontmatter name.
        body = "---\nname: eight-adr\n---\n# same\n"
        _codex("eight-adr", body)
        _mine("adr", body)
        assert _classify("adr") == {**EMPTY, "adoptable_store": ["adr"]}

    def test_an_identical_agent_copy_is_foreign(self, sandbox):
        theirs = _codex("pr-me", "# same\n", when=1e9)
        _mine("pr-me", "# same\n", when=4e9)
        assert _classify("pr-me")["foreign_store"] == [
            ("pr-me", "Codex", str(theirs), "identical")]

    def test_a_newer_agent_copy_owns_the_name(self, sandbox):
        _codex("pr-me", "# codex\n", when=2e9)
        newest = _skill(paths.home() / ".windsurf" / "skills" / "pr-me",
                        "# windsurf\n", when=3e9)
        _mine("pr-me", "# mine\n", when=1e9)
        assert _classify("pr-me") == {**EMPTY, "foreign_store": [
            ("pr-me", "Windsurf", str(newest), "differs")]}

    def test_a_tie_goes_to_the_other_copy(self, sandbox):
        theirs = _codex("pr-me", "# codex\n", when=2e9)
        _mine("pr-me", "# mine\n", when=2e9)
        assert _classify("pr-me")["foreign_store"] == [
            ("pr-me", "Codex", str(theirs), "differs")]

    def test_a_newer_store_copy_is_adopted_and_the_older_ones_named(self, sandbox):
        # The case that prompted the rule: a skill the user edits in
        # ~/.agents/skills, with a stale copy left in ~/.codex/skills.
        older = _codex("pr-me", "# old\n", when=1e9)
        oldest = _skill(paths.home() / ".windsurf" / "skills" / "pr-me",
                        "# older\n", when=5e8)
        _mine("pr-me", "# new\n", when=2e9)
        assert _classify("pr-me") == {**EMPTY,
                                      "adoptable_store": ["pr-me"],
                                      "older_copies": [
                                          ("pr-me", "Windsurf", str(oldest)),
                                          ("pr-me", "Codex", str(older))]}

    def test_a_store_link_to_another_tools_skill_is_in_no_bucket(self, sandbox):
        # The user's own alias, so the agents that read the store see a skill
        # kept in ~/.claude/skills: not a copy to prune, not boost's to record.
        theirs = _skill(paths.home() / ".claude" / "skills" / "my-notes")
        _mine("z-mine")
        (paths.store_dir() / "my-notes").symlink_to(theirs)
        assert _classify("my-notes", "z-mine") == {
            **EMPTY, "adoptable_store": ["z-mine"]}

    def test_an_agent_owned_name_does_not_end_the_pass(self, sandbox):
        same = _codex("a", "# a\n")
        _mine("a", "# a\n")
        newer = _codex("b", "# codex b\n", when=3e9)
        _mine("b", "# mine b\n", when=1e9)
        _mine("c")
        assert _classify("a", "b", "c") == {**EMPTY,
                                            "adoptable_store": ["c"],
                                            "foreign_store": [
                                                ("a", "Codex", str(same), "identical"),
                                                ("b", "Codex", str(newer), "differs")]}

    def test_a_dir_boost_cannot_look_into_is_unreadable(self, sandbox, monkeypatch):
        # Looked at before anything is read: with no search bit it held "no
        # SKILL.md" as far as ``isfile`` could tell, and was "not a skill".
        d = _mine("pr-me")
        real = os.access
        monkeypatch.setattr(store.os, "access",
                            lambda p, m, *a, **k: Path(p) != d and real(p, m, *a, **k))
        assert _classify("pr-me") == {**EMPTY, "unreadable_store": [("pr-me", str(d))]}

    @posix_modes
    def test_a_dir_with_no_search_bit_is_unreadable(self, sandbox):
        d = _mine("pr-me")
        d.chmod(0o600)
        try:
            got = _classify("pr-me")
        finally:
            d.chmod(0o700)
        assert got == {**EMPTY, "unreadable_store": [("pr-me", str(d))]}

    def test_a_skill_holding_something_unreadable_is_named_and_not_compared(
            self, sandbox, monkeypatch):
        _vendor("automate")
        bad = _mine("automate") / "refs"
        _mine("pr-me")
        monkeypatch.setattr(foreign, "unreadable",
                            lambda p: bad if Path(p).parent == paths.store_dir()
                            and Path(p).name == "automate" else None)
        assert _classify("automate", "pr-me") == {
            **EMPTY, "adoptable_store": ["pr-me"],
            "unreadable_store": [("automate", str(bad))]}

    def test_only_unreadable_dirs_read_no_inventory(self, sandbox, monkeypatch):
        _mine("pr-me")
        monkeypatch.setattr(foreign, "unreadable", lambda p: Path(p))
        monkeypatch.setattr(foreign, "inventory",
                            lambda *a, **k: pytest.fail("read"))
        assert _classify("pr-me")["unreadable_store"] == [
            ("pr-me", str(paths.store_dir() / "pr-me"))]

    def test_a_repo_named_like_a_vendor_skill_differs_whatever_its_bytes(
            self, sandbox):
        # The hash skips ``.git``, so the user's clone hashed as identical.
        theirs = _vendor("automate", "# same\n")
        (_mine("automate", "# same\n") / ".git").mkdir()
        assert _classify("automate")["foreign_store"] == [
            ("automate", "Cursor's built-ins", str(theirs), "differs")]

    def test_a_repo_is_never_an_identical_agent_copy(self, sandbox):
        older = _codex("pr-me", "# same\n", when=1e9)
        (_mine("pr-me", "# same\n", when=4e9) / ".git").mkdir()
        assert _classify("pr-me") == {**EMPTY, "adoptable_store": ["pr-me"],
                                      "older_copies": [("pr-me", "Codex", str(older))]}

    def test_a_repo_older_than_an_agent_copy_is_still_named(self, sandbox):
        newer = _codex("pr-me", "# same\n", when=4e9)
        (_mine("pr-me", "# same\n", when=1e9) / ".git").mkdir()
        assert _classify("pr-me")["foreign_store"] == [
            ("pr-me", "Codex", str(newer), "differs")]

    def test_a_second_path_is_decided_by_inode(self, sandbox, monkeypatch):
        theirs = _codex("pr-me", "# same\n")
        _mine("pr-me", "# same\n")
        monkeypatch.setattr(foreign, "same_dir", lambda a, b: True)
        assert _classify("pr-me") == EMPTY
        assert theirs.is_dir()

    def test_every_name_is_answered_in_order(self, sandbox):
        _vendor("v")
        for n in ("z", "v", "a"):
            _mine(n)
        (paths.store_dir() / "e").mkdir()
        got = _classify("z", "v", "e", "a")
        assert got["adoptable_store"] == ["z", "a"]
        assert [r[0] for r in got["foreign_store"]] == ["v"]
        assert got["not_skill_store"] == ["e"]


class TestCoveringPlugin:
    def test_none_without_plugins(self, installed):
        assert store.covering_plugin("brainstorming") is None

    def test_a_plugin_with_the_same_files(self, claude_plugin, installed):
        theirs = claude_plugin()
        plugin, path = store.covering_plugin("brainstorming")
        assert (plugin.id, str(path)) == (PLUGIN, str(theirs))

    def test_a_plugin_with_a_different_skill_by_the_name(self, claude_plugin,
                                                         installed):
        claude_plugin(body="# a different skill\n")
        assert store.covering_plugin("brainstorming") is None

    def test_matched_by_the_store_copys_skill_md_name(self, claude_plugin, sandbox):
        theirs = claude_plugin("adr", "---\nname: eight-adr\n---\n# p\n")
        shutil.copytree(theirs, paths.store_dir() / "adr")
        assert store.covering_plugin("adr")[0].id == PLUGIN

    def test_the_index_passed_in_is_the_one_read(self, claude_plugin, installed,
                                                 monkeypatch):
        claude_plugin()
        monkeypatch.setattr(foreign, "plugin_index", lambda: pytest.fail("read"))
        assert store.covering_plugin("brainstorming", {}) is None

    def test_the_plugin_with_the_same_files_whichever_comes_first(
            self, claude_plugin, installed):
        claude_plugin(body="# a different skill\n", pid="a-first@m")
        theirs = claude_plugin(pid="b-second@m")
        plugin, path = store.covering_plugin("brainstorming")
        assert (plugin.id, path) == ("b-second@m", theirs)

    def test_a_stale_cache_does_not_cover_what_the_folder_now_holds(
            self, claude_plugin, installed):
        # The cache matches the store; the folder Claude Code reads was
        # edited since. Covering it dropped the only `/brainstorming` link.
        claude_plugin()
        _dir_marketplace("# edited since the install\n")
        assert store.covering_plugin("brainstorming") is None

    def test_the_folder_covers_what_it_holds(self, claude_plugin, installed):
        claude_plugin(body="# the cache, stale\n")
        theirs = _dir_marketplace(None)
        plugin, path = store.covering_plugin("brainstorming")
        assert (plugin.id, path) == (PLUGIN, theirs)


class TestPluginCoverage:
    def test_identical_and_different_copies(self, claude_plugin, installed):
        store.install(catalog.resolve_one("tdd-workflow"))
        same = claude_plugin()
        other = claude_plugin("tdd-workflow", "# a different skill\n")
        assert store.plugin_coverage(lockfile.installed()) == {
            "brainstorming": (PLUGIN, str(same), "identical"),
            "tdd-workflow": (PLUGIN, str(other), "differs")}

    def test_none_while_claude_code_is_not_linked(self, claude_plugin, installed):
        claude_plugin()
        _disable_claude_code()
        assert store.plugin_coverage(lockfile.installed()) == {}

    @pytest.mark.parametrize("fields", [{"quarantined": True},
                                        {"sidelined_by": "focus"},
                                        {"only_agents": ["cursor"]}])
    def test_a_skill_with_no_claude_code_link_to_weigh(self, claude_plugin,
                                                       installed, fields):
        claude_plugin()
        _set("brainstorming", **fields)
        assert store.plugin_coverage(lockfile.installed()) == {}

    def test_the_identical_plugin_whichever_comes_first(self, claude_plugin,
                                                        installed):
        claude_plugin(body="# a different skill\n", pid="a-first@m")
        theirs = claude_plugin(pid="b-second@m")
        assert store.plugin_coverage(lockfile.installed()) == {
            "brainstorming": ("b-second@m", str(theirs), "identical")}

    def test_otherwise_the_first_by_id_differs(self, claude_plugin, installed):
        first = claude_plugin(body="# one\n", pid="a-first@m")
        claude_plugin(body="# two\n", pid="b-second@m")
        assert store.plugin_coverage(lockfile.installed()) == {
            "brainstorming": ("a-first@m", str(first), "differs")}

    def test_a_skipped_skill_does_not_end_the_pass(self, claude_plugin, installed):
        theirs = claude_plugin()
        (paths.store_dir() / "aaa").mkdir()        # no SKILL.md
        _mine("aab")                               # no plugin ships it
        lock = {"aa0": {"quarantined": True}, "aaa": {}, "aab": {},
                **lockfile.installed()}
        assert store.plugin_coverage(lock) == {
            "brainstorming": (PLUGIN, str(theirs), "identical")}


class TestPluginDuplicates:
    def test_none_without_plugins(self, installed):
        assert store.plugin_duplicates() == []

    def test_an_identical_plugin_copy(self, claude_plugin, installed):
        theirs = claude_plugin()
        assert store.plugin_duplicates() == [
            ("brainstorming", PLUGIN, str(theirs), "identical")]

    def test_a_different_plugin_copy(self, claude_plugin, installed):
        theirs = claude_plugin(body="# a different skill\n")
        assert store.plugin_duplicates() == [
            ("brainstorming", PLUGIN, str(theirs), "differs")]

    def test_the_lock_passed_in_is_the_one_read(self, claude_plugin, installed):
        claude_plugin()
        assert store.plugin_duplicates({}) == []

    def test_the_coverage_passed_in_is_the_one_read(self, installed):
        row = ("p@m", "/x", "identical")
        assert store.plugin_duplicates(lockfile.installed(),
                                       {"brainstorming": row}) == [
            ("brainstorming", *row)]

    def test_not_while_claude_code_is_not_linked(self, claude_plugin, installed):
        claude_plugin()
        _disable_claude_code()
        assert store.plugin_duplicates() == []

    def test_not_for_a_skill_scoped_away_from_claude_code(self, claude_plugin, installed):
        claude_plugin()
        _set("brainstorming", only_agents=["cursor"])
        assert store.plugin_duplicates() == []

    @pytest.mark.parametrize("key,value", [("quarantined", True),
                                           ("sidelined_by", "focus")])
    def test_not_for_a_skill_with_no_link(self, claude_plugin, installed, key, value):
        claude_plugin()
        _set("brainstorming", **{key: value})
        assert store.plugin_duplicates() == []

    def test_not_for_a_gutted_store_copy(self, claude_plugin, installed):
        claude_plugin()
        (paths.store_dir() / "brainstorming" / "SKILL.md").unlink()
        assert store.plugin_duplicates() == []

    def test_not_once_boosts_link_is_gone(self, claude_plugin, installed):
        claude_plugin()
        _claude_link().unlink()
        assert store.plugin_duplicates() == []

    def test_not_while_the_link_leads_elsewhere(self, claude_plugin, installed):
        claude_plugin()
        _claude_link().unlink()
        _claude_link().symlink_to(_skill(paths.home() / "dev" / "brainstorming"))
        assert store.plugin_duplicates() == []

    def test_sync_plan_carries_them_only_while_the_lock_vouches(self, claude_plugin, installed):
        claude_plugin()
        assert [r[0] for r in store.sync_plan()["plugin_duplicates"]] == [
            "brainstorming"]
        paths.lockfile_path().write_text("{nope", encoding="utf-8")
        assert store.sync_plan()["plugin_duplicates"] == []


class TestCoveredSkills:
    def test_only_a_plugin_shipping_the_same_files_covers_a_skill(self):
        coverage = {"same": (PLUGIN, "/p/same", foreign.IDENTICAL),
                    "other": (PLUGIN, "/p/other", foreign.DIFFERS)}
        assert store.covered_skills(coverage) == {"same"}

    def test_no_coverage_covers_nothing(self):
        assert store.covered_skills({}) == set()


class TestLeftToPlugin:
    def _left(self, agent="claude-code", link=None, covered=("brainstorming",)):
        return store.left_to_plugin("brainstorming", agent,
                                    link or _claude_link(), set(covered))

    def test_a_missing_claude_code_link_to_a_covered_skill(self, installed):
        _claude_link().unlink()
        assert self._left()

    def test_not_another_agents_link(self, installed):
        link = paths.home() / ".cursor" / "skills" / "brainstorming"
        link.unlink()
        assert not self._left(agent="cursor", link=link)

    def test_not_a_skill_no_plugin_covers(self, installed):
        _claude_link().unlink()
        assert not self._left(covered=set())

    def test_not_while_boosts_link_is_there(self, installed):
        assert not self._left()

    def test_another_link_by_the_name_is_no_fault(self, installed):
        mine = _skill(paths.home() / "dev" / "brainstorming")
        _claude_link().unlink()
        _claude_link().symlink_to(mine)
        assert self._left()

    def test_a_dir_where_the_link_would_go_is_no_fault(self, installed):
        _claude_link().unlink()
        _claude_link().mkdir()
        assert self._left()


class TestLinkAgentsLeavesACoveredSkillToItsPlugin:
    def test_a_fresh_install_makes_no_claude_code_link(self, claude_plugin,
                                                       installed):
        claude_plugin()
        store.uninstall("brainstorming")
        res = store.install(catalog.resolve_one("brainstorming"))
        assert res.covered == [PLUGIN]
        assert res.linked == REST and res.refused == []
        assert not os.path.lexists(_claude_link())
        e = lockfile.get_skill("brainstorming")
        assert e["agents"] == REST and "refused_agents" not in e

    def test_an_explicit_claude_code_install_too(self, claude_plugin, installed):
        claude_plugin()
        _claude_link().unlink()
        res = store.link_agents("brainstorming", only=["claude-code"])
        assert (res.linked, res.covered) == ([], [PLUGIN])
        assert not os.path.lexists(_claude_link())

    def test_a_link_already_there_is_kept(self, claude_plugin, installed):
        claude_plugin()
        res = store.link_agents("brainstorming")
        assert res.linked == LINKED and res.covered == []
        assert _claude_link().is_symlink()

    def test_another_link_by_the_name_is_left_alone(self, claude_plugin, installed):
        claude_plugin()
        mine = _skill(paths.home() / "dev" / "brainstorming")
        _claude_link().unlink()
        _claude_link().symlink_to(mine)
        assert store.link_agents("brainstorming").covered == [PLUGIN]
        assert _leads_to(_claude_link(), mine)

    def test_claude_codes_dir_is_not_created_for_it(self, claude_plugin, installed):
        claude_plugin()
        shutil.rmtree(paths.home() / ".claude" / "skills")
        store.link_agents("brainstorming")
        assert not os.path.lexists(paths.home() / ".claude" / "skills")

    def test_a_plugin_with_a_different_skill_does_not_cover_it(self, claude_plugin,
                                                               installed):
        claude_plugin(body="# a different skill\n")
        _claude_link().unlink()
        res = store.link_agents("brainstorming")
        assert "claude-code" in res.linked and res.covered == []
        assert _claude_link().is_symlink()

    def test_ending_a_sideline_does_not_bring_the_link_back(self, claude_plugin,
                                                            installed):
        claude_plugin()
        store.sideline("brainstorming", "focus")
        res = store.unsideline("brainstorming")
        assert res.covered == [PLUGIN]
        assert not os.path.lexists(_claude_link())
        assert lockfile.get_skill("brainstorming")["agents"] == REST


class TestSyncPlanLeavesACoveredSkillToItsPlugin:
    def test_the_agents_after_claude_code_are_still_repaired(self, claude_plugin,
                                                             installed):
        claude_plugin()
        _claude_link().unlink()
        (agents.linking_agents()["windsurf"] / "brainstorming").unlink()
        assert store.sync_plan()["missing_links"] == [("brainstorming", "windsurf")]

    def test_its_missing_claude_code_link_is_no_repair(self, claude_plugin,
                                                       installed):
        claude_plugin()
        _claude_link().unlink()
        plan = store.sync_plan()
        assert plan["missing_links"] == plan["plugin_duplicates"] == []
        assert store.sync_apply(plan) == []
        assert not os.path.lexists(_claude_link())

    def test_something_where_its_link_would_go_blocks_nothing(self, claude_plugin,
                                                              installed):
        claude_plugin()
        _claude_link().unlink()
        _claude_link().mkdir()
        assert store.sync_plan()["blocked_links"] == []

    def test_claude_codes_dir_in_the_way_blocks_nothing(self, claude_plugin,
                                                        installed):
        claude_plugin()
        shutil.rmtree(paths.home() / ".claude" / "skills")
        (paths.home() / ".claude" / "skills").write_text("x", encoding="utf-8")
        assert store.sync_plan()["blocked_links"] == []

    def test_a_different_skill_by_the_name_still_gets_its_link(self, claude_plugin,
                                                               installed):
        claude_plugin(body="# a different skill\n")
        _claude_link().unlink()
        assert store.sync_plan()["missing_links"] == [
            ("brainstorming", "claude-code")]


class TestSortUnrecorded:
    def test_an_intact_lock_is_classified(self, installed):
        _mine("pr-me")
        theirs = _vendor("automate")
        _mine("automate")
        _mine("b copy")
        assert store.sort_unrecorded(lockfile.installed()) == {
            **EMPTY, "adoptable_store": ["pr-me"],
            "foreign_store": [("automate", "Cursor's built-ins", str(theirs),
                               "differs")],
            "unrecorded_store": [], "misnamed_store": ["b copy"]}

    def test_a_missing_lock_queues_what_boost_may_have_installed(self, installed):
        _mine("pr-me")
        older = _codex("old-me", "# old\n", when=1e9)
        _mine("old-me", "# new\n", when=2e9)
        _vendor("linked")
        _mine("linked")
        (paths.home() / ".cursor" / "skills" / "linked").symlink_to(
            paths.store_dir() / "linked")
        theirs = _vendor("unlinked")
        _mine("unlinked")
        _mine("b copy")
        paths.lockfile_path().unlink()
        assert store.sort_unrecorded(lockfile.installed()) == {
            **EMPTY,
            "unrecorded_store": ["brainstorming", "linked", "old-me", "pr-me"],
            "older_copies": [("old-me", "Codex", str(older))],
            "foreign_store": [("unlinked", "Cursor's built-ins", str(theirs),
                               "differs")],
            "misnamed_store": ["b copy"]}

    def test_a_corrupt_lock_reads_nothing_else(self, installed, monkeypatch):
        _mine("pr-me")
        _mine("b copy")
        paths.lockfile_path().write_text("{oops", encoding="utf-8")
        monkeypatch.setattr(foreign, "inventory",
                            lambda *a, **k: pytest.fail("read"))
        assert store.sort_unrecorded(lockfile.installed()) == {
            **EMPTY, "unrecorded_store": ["brainstorming", "pr-me"],
            "misnamed_store": ["b copy"]}

    def test_the_check_passed_in_is_the_one_read(self, installed, monkeypatch):
        _mine("pr-me")
        monkeypatch.setattr(lockfile, "check", lambda: pytest.fail("read"))
        got = store.sort_unrecorded({}, lockfile.Integrity(False, "corrupt"))
        assert got["unrecorded_store"] == ["brainstorming", "pr-me"]


class TestPlanIssues:
    def test_counts_problems_and_not_notes(self):
        plan = {"missing_links": [("a", "cursor")], "foreign_store": [1, 2],
                "older_copies": [1, 2, 3], "not_skill_store": ["x"],
                "misnamed_store": ["x y"], "unreadable_store": [("u", "/u")],
                "plugin_duplicates": [("a", "p", "/x", "identical"),
                                      ("b", "p", "/y", "differs")]}
        assert store.plan_issues(plan) == 5

    def test_an_empty_plan(self):
        assert store.plan_issues({}) == 0


class TestSyncPlanKeepsAnAdoptedSkillsLink:
    def test_a_hand_made_link_to_an_adoptable_skill_is_not_stale(self, installed):
        mine = _mine("pr-me")
        _claude_link("pr-me").symlink_to(mine)
        plan = store.sync_plan()
        assert plan["adoptable_store"] == ["pr-me"]
        assert plan["stale_links"] == []

    def test_a_live_link_into_any_unrecorded_dir_is_not_stale(self, installed):
        # Plain sync removed these one line above the lines saying the dirs
        # they lead to were left alone: a copy of Cursor's skill, a skill in
        # another tool's bucket, a dir boost cannot record a name for.
        _vendor("automate")
        _claude_link("automate").symlink_to(_mine("automate"))
        _claude_link("foo").symlink_to(_skill(paths.store_dir() / "synced" / "foo"))
        _claude_link("notes").symlink_to(_mine("my notes"))
        plan = store.sync_plan()
        assert [r[0] for r in plan["foreign_store"]] == ["automate"]
        assert plan["stale_links"] == []

    def test_a_link_to_a_recorded_skill_under_another_name_is_stale(self, installed):
        link = _claude_link("other")
        link.symlink_to(paths.store_dir() / "brainstorming")
        assert store.sync_plan()["stale_links"] == [str(link)]

    def test_a_link_into_a_pruned_dir_is_stale_once_it_dangles(self, installed):
        link = _claude_link("automate")
        link.symlink_to(paths.store_dir() / "automate")
        assert store.sync_plan()["stale_links"] == [str(link)]

    def test_a_link_boost_cannot_follow_is_not_called_dangling(self, installed,
                                                               monkeypatch):
        # Under a store with no search bit every live link read as broken.
        link = _claude_link("automate")
        link.symlink_to(_mine("automate"))
        real = os.stat

        def stat(p, *a, **k):
            if str(p) == str(link):
                raise PermissionError(13, "denied", str(p))
            return real(p, *a, **k)
        monkeypatch.setattr(store.os, "stat", stat)
        assert store._dangles(link) is False

    def test_a_loop_dangles(self, installed):
        link = _claude_link("loop")
        link.symlink_to(link)
        with pytest.raises(OSError) as exc:
            link.stat()
        assert store._dangles(link) is True, (
            exc.value.errno, getattr(exc.value, "winerror", None))

    def test_a_loop_as_windows_reports_it_dangles(self, installed, monkeypatch):
        # ERROR_CANT_RESOLVE_FILENAME, with an errno that is not ELOOP.
        link = _claude_link("loop")
        link.symlink_to(_mine("loop"))
        real = os.stat

        def stat(p, *a, **k):
            if str(p) == str(link):
                err = OSError(errno.EINVAL, "cannot resolve", str(p))
                err.winerror = 1921
                raise err
            return real(p, *a, **k)
        monkeypatch.setattr(store.os, "stat", stat)
        assert store._dangles(link) is True

    def test_a_live_link_does_not_dangle(self, installed):
        assert store._dangles(_claude_link()) is False
        assert store._dangles(paths.home() / "nothing-here") is True

    def test_the_store_dir_a_link_leads_into(self, installed):
        mine = _mine("automate")
        (mine / "refs").mkdir()
        made = {}
        for n, to in (("a", mine), ("b", mine / "refs"),
                      ("c", paths.store_dir()), ("d", paths.home())):
            made[n] = _claude_link(n)
            made[n].symlink_to(to)
        assert {n: store._store_entry(link) for n, link in made.items()} == {
            "a": "automate", "b": "automate", "c": None, "d": None}

    def test_a_link_on_another_drive_leads_into_none(self, installed, monkeypatch):
        def other_drive(*_a):
            raise ValueError("path is on mount 'D:', start on mount 'C:'")
        monkeypatch.setattr(store.os.path, "relpath", other_drive)
        assert store._store_entry(_claude_link()) is None


class TestAdoption:
    def test_records_a_local_skill_and_links_it_everywhere(self, installed):
        _mine("pr-me")
        actions = store.sync_apply(store.sync_plan())
        assert actions == ["recorded pr-me as a local skill"] + [
            "linked pr-me → %s" % a for a in LINKED]
        e = lockfile.get_skill("pr-me")
        assert (e["tap"], e["source_dir"], e["commit"], e["version"]) == (
            "local", str(paths.store_dir() / "pr-me"), "", "0.0.0")
        assert e["agents"] == LINKED and e["only_agents"] is None
        assert all(os.path.islink(d / "pr-me")
                   for d in agents.linking_agents().values())
        assert store.sync_plan()["adoptable_store"] == []

    def test_a_hand_made_link_is_kept_as_the_scope(self, installed):
        mine = _mine("pr-me")
        _claude_link("pr-me").symlink_to(mine)
        actions = store.sync_apply(store.sync_plan())
        assert actions == ["recorded pr-me as a local skill"]
        e = lockfile.get_skill("pr-me")
        assert e["agents"] == ["claude-code"]
        assert e["only_agents"] == ["claude-code"]
        assert _claude_link("pr-me").is_symlink()
        assert not (paths.home() / ".cursor" / "skills" / "pr-me").exists()

    def test_a_dangling_link_into_the_store_is_the_scope_too(self, installed):
        _mine("pr-me")
        cursor = paths.home() / ".cursor" / "skills" / "pr-me"
        cursor.symlink_to(paths.store_dir() / "pr-me-before-a-rename")
        store.adopt_unrecorded("pr-me")
        e = lockfile.get_skill("pr-me")
        assert e["only_agents"] == ["cursor"] and e["agents"] == ["cursor"]
        assert os.path.realpath(cursor) == os.path.realpath(
            paths.store_dir() / "pr-me")

    def test_a_copy_of_a_tapped_source_is_still_a_local_skill(self, installed,
                                                              monkeypatch):
        # Matching it hashed every same-named entry's source, and each hash
        # widened that entry's clone.
        src = store.source_dir_for(catalog.resolve_one("tdd-workflow"))
        shutil.copytree(src, paths.store_dir() / "tdd-workflow")
        monkeypatch.setattr(catalog, "find", lambda *a: pytest.fail("matched"))
        monkeypatch.setattr(store, "_skill_source_sha",
                            lambda *a: pytest.fail("hashed"))
        actions = store.sync_apply(store.sync_plan())
        assert actions[0] == "recorded tdd-workflow as a local skill"
        assert lockfile.get_skill("tdd-workflow")["tap"] == "local"

    def test_a_skill_recorded_since_the_plan_is_left_to_that_record(self, installed):
        _mine("pr-me")
        plan = store.sync_plan()
        lockfile.set_skill("pr-me", {"tap": "elsewhere", "agents": []})
        assert store.sync_apply(plan) == []
        assert lockfile.get_skill("pr-me")["tap"] == "elsewhere"

    def test_a_dir_that_lost_its_skill_md_since_is_skipped(self, installed):
        mine = _mine("pr-me")
        plan = store.sync_plan()
        (mine / "SKILL.md").unlink()
        assert store.adopt_unrecorded("pr-me") == []
        assert store.sync_apply(plan) == []
        assert lockfile.get_skill("pr-me") is None

    def test_a_real_dir_in_the_way_is_a_warning_not_a_link(self, installed):
        _mine("pr-me")
        (paths.home() / ".cursor" / "skills" / "pr-me").mkdir()
        lines = store.adopt_unrecorded("pr-me")
        refused = [ln for ln in lines if store.is_unrepaired(ln)]
        assert refused == [
            "pr-me was not linked: ~/.cursor/skills/pr-me is in the way and is "
            "not boost's to replace — to link boost's copy, move or delete it, "
            "then re-run `boost sync`"]
        assert "linked pr-me → cursor" not in lines
        assert "linked pr-me → claude-code" in lines

    def test_the_users_own_link_is_left_where_it_leads(self, installed):
        # Any symlink used to count as boost's to replace, which re-pointed
        # Claude Code from the user's checkout to the store copy.
        checkout = _skill(paths.home() / "dev" / "pr-me", "# checkout\n", when=1e9)
        _mine("pr-me", "# store\n", when=2e9)
        _claude_link("pr-me").symlink_to(checkout)
        actions = store.sync_apply(store.sync_plan())
        assert actions == ["recorded pr-me as a local skill"] + [
            "linked pr-me → %s" % a for a in REST] + [
            "pr-me was not linked: ~/.claude/skills/pr-me is in the way and is "
            "not boost's to replace — to link boost's copy, move or delete it, "
            "then re-run `boost sync`"]
        assert _leads_to(_claude_link("pr-me"), checkout)
        e = lockfile.get_skill("pr-me")
        assert e["only_agents"] is None and e["agents"] == REST

    def test_nothing_to_link_asks_for_no_links(self, installed, monkeypatch):
        # `link_agents` reads an empty list as every agent.
        _mine("pr-me")
        for adir in agents.linking_agents().values():
            (adir / "pr-me").mkdir()
        monkeypatch.setattr(store, "link_agents", lambda *a, **k: pytest.fail("linked"))
        lines = store.adopt_unrecorded("pr-me")
        assert lines[0] == "recorded pr-me as a local skill"
        assert len(lines) == 5 and all(store.is_unrepaired(ln) for ln in lines[1:])
        assert lockfile.get_skill("pr-me")["agents"] == []

    @posix_modes
    def test_an_unreadable_file_is_named_and_the_rest_still_runs(self, installed):
        # Asked at plan time, so no preview promises a record the run refuses.
        secret = _mine("pr-me") / "secret.txt"
        secret.write_text("x", encoding="utf-8")
        secret.chmod(0)
        (paths.home() / ".cursor" / "skills" / "brainstorming").unlink()
        try:
            plan = store.sync_plan()
            actions = store.sync_apply(plan)
        finally:
            secret.chmod(0o644)
        assert plan["adoptable_store"] == []
        assert plan["unreadable_store"] == [("pr-me", str(secret))]
        assert store.sync_preview(plan) == []
        assert actions == ["linked brainstorming → cursor"]
        assert lockfile.get_skill("pr-me") is None

    @posix_modes
    def test_a_file_unreadable_since_the_plan_is_named(self, installed):
        secret = _mine("pr-me") / "secret.txt"
        secret.write_text("x", encoding="utf-8")
        plan = store.sync_plan()
        secret.chmod(0)
        try:
            actions = store.sync_apply(plan)
        finally:
            secret.chmod(0o644)
        line = ("pr-me was not recorded: ~/.agents/skills/pr-me/secret.txt is "
                "unreadable — make it readable, then re-run `boost sync`")
        assert line in actions and store.is_unrepaired(line)
        assert lockfile.get_skill("pr-me") is None

    @posix_modes
    def test_an_unreadable_file_under_a_lost_lock_is_named(self, installed):
        secret = paths.store_dir() / "brainstorming" / "secret.txt"
        secret.write_text("x", encoding="utf-8")
        secret.chmod(0)
        paths.lockfile_path().unlink()
        try:
            line = store.recover_unrecorded("brainstorming")
        finally:
            secret.chmod(0o644)
        assert line == ("brainstorming was not recorded: "
                        "~/.agents/skills/brainstorming/secret.txt is unreadable "
                        "— make it readable, then re-run `boost sync`")

    def test_is_journaled_as_an_adoption(self, installed):
        _mine("pr-me")
        store.adopt_unrecorded("pr-me")
        events = [json.loads(ln) for ln in
                  paths.pulse_path().read_text(encoding="utf-8").splitlines()]
        assert {"action": "adopt", "subject": "pr-me"}.items() <= events[-1].items()

    def test_the_preview_words_the_same_decision(self, installed):
        _mine("pr-me")
        assert store.sync_preview(store.sync_plan()) == [
            "would record pr-me, which boost did not install, and link it"]

    def test_the_preview_weighs_only_the_agents_the_run_links(self, installed):
        # Linked by hand from Cursor alone, it is recorded for Cursor alone,
        # so what sits in Windsurf's dir is no part of the run.
        mine = _mine("mine-x")
        (agents.linking_agents()["cursor"] / "mine-x").symlink_to(mine)
        (agents.linking_agents()["windsurf"] / "mine-x").mkdir()
        assert store.sync_preview(store.sync_plan()) == [
            "would record mine-x, which boost did not install, and link it"]

    def test_the_preview_names_what_is_in_the_way(self, installed):
        _mine("pr-me")
        (paths.home() / ".cursor" / "skills" / "pr-me").mkdir()
        assert store.sync_preview(store.sync_plan()) == [
            "would record pr-me, which boost did not install, and link it "
            "(not into cursor: ~/.cursor/skills/pr-me is in the way)"]

    def test_the_preview_says_when_nothing_will_be_linked(self, installed):
        _mine("pr-me")
        for adir in agents.linking_agents().values():
            (adir / "pr-me").mkdir()
        assert store.sync_preview(store.sync_plan()) == [
            "would record pr-me, which boost did not install, and leave it "
            "unlinked (%s)" % "; ".join(
                "not into %s: ~/%s/pr-me is in the way" % (
                    a, paths.tilde(d).removeprefix("~/"))
                for a, d in agents.linking_agents().items())]

    def test_a_lost_lock_still_reads_as_recovered(self, installed):
        # The two paths share one recorder and must not share its wording.
        paths.lockfile_path().unlink()
        assert store.recover_unrecorded("brainstorming") == (
            "re-recorded brainstorming from %s" % installed.name)

    def test_a_queued_dir_that_lost_its_skill_md_is_left(self, installed):
        # A plan only queues a dir with a SKILL.md, so this is a dir emptied
        # between the plan and the run.
        paths.lockfile_path().unlink()
        (paths.store_dir() / "husk").mkdir()
        plan = {**store.sync_plan(), "unrecorded_store": ["husk"]}
        assert store.sync_preview(plan) == [
            "would leave husk unrecorded (no SKILL.md to record)"]
        assert store.sync_apply(plan) == [
            "left husk unrecorded (no SKILL.md to record)"]


class TestOnlyCopy:
    def test_a_local_skill_whose_source_is_its_store_dir(self, sandbox):
        mine = _mine("pr-me")
        assert store.only_copy("pr-me", {"tap": "local", "source_dir": str(mine)})

    def test_one_whose_source_reaches_the_store_another_way(self, sandbox):
        alias = paths.home() / "alias"
        alias.symlink_to(_mine("pr-me"))
        assert store.only_copy("pr-me", {"tap": "local", "source_dir": str(alias)})

    def test_one_whose_source_is_gone(self, sandbox):
        _mine("pr-me")
        entry = {"tap": "local", "source_dir": str(paths.home() / "gone")}
        assert store.only_copy("pr-me", entry)

    def test_not_one_whose_source_is_elsewhere(self, sandbox):
        _mine("pr-me")
        src = _skill(paths.home() / "dev" / "pr-me")
        assert not store.only_copy("pr-me", {"tap": "local", "source_dir": str(src)})

    def test_not_a_tapped_skill(self, installed):
        assert not store.only_copy("brainstorming",
                                   lockfile.get_skill("brainstorming"))

    def test_not_a_url_import(self, sandbox):
        _mine("pr-me")
        entry = {"tap": "local", "source_url": "https://example.test/r.git",
                 "source_dir": "skills/pr-me"}
        assert not store.only_copy("pr-me", entry)


class TestSelfSourced:
    """A skill recorded where `boost sync` found it is its own source."""

    def test_a_skill_recorded_where_it_was_found(self, sandbox):
        mine = _mine("pr-me")
        assert integrity.self_sourced("pr-me", {"tap": "local",
                                                "source_dir": str(mine)})

    def test_still_one_once_its_store_dir_is_gone(self, sandbox):
        entry = {"tap": "local", "source_dir": str(paths.store_dir() / "pr-me")}
        assert integrity.self_sourced("pr-me", entry)

    def test_one_recorded_under_another_name_for_the_dir(self, sandbox):
        alias = paths.home() / "alias"
        alias.symlink_to(_mine("pr-me"))
        assert integrity.self_sourced("pr-me", {"tap": "local",
                                                "source_dir": str(alias)})

    def test_not_a_local_import_whose_source_is_gone(self, sandbox):
        # The store holds its only copy, but it was copied from something,
        # so drifting from that copy still means something.
        _mine("pr-me")
        entry = {"tap": "local", "source_dir": str(paths.home() / "gone")}
        assert store.only_copy("pr-me", entry)
        assert not integrity.self_sourced("pr-me", entry)

    def test_not_one_whose_source_is_elsewhere(self, sandbox):
        _mine("pr-me")
        src = _skill(paths.home() / "dev" / "pr-me")
        assert not integrity.self_sourced("pr-me", {"tap": "local",
                                                    "source_dir": str(src)})

    @pytest.mark.parametrize("fields", [
        {"tap": "a-tap"},
        {"tap": "local", "source_url": "https://example.test/r.git"},
    ])
    def test_not_a_tapped_skill_or_a_url_import(self, sandbox, fields):
        entry = {"source_dir": str(_mine("pr-me")), **fields}
        assert not integrity.self_sourced("pr-me", entry)

    @pytest.mark.parametrize("entry", [None, {}, {"tap": "local"},
                                       {"tap": "local", "source_dir": ""}])
    def test_not_an_entry_that_names_no_dir(self, sandbox, monkeypatch, entry):
        # An empty path is the cwd to `Path`, which may well be the store.
        monkeypatch.chdir(_mine("pr-me"))
        assert not integrity.self_sourced("pr-me", entry)


class TestEditingASkillKeptInTheStore:
    """Its edits are the skill changing, not drift from a reviewed copy."""

    def test_verify_reads_an_edited_one_as_ok(self, installed):
        mine = _mine("pr-me")
        store.adopt_unrecorded("pr-me")
        (mine / "SKILL.md").write_text("# edited\n", encoding="utf-8")
        assert integrity.status("pr-me") == integrity.STATUS_OK

    def test_a_missing_one_is_still_missing(self, installed):
        mine = _mine("pr-me")
        store.adopt_unrecorded("pr-me")
        shutil.rmtree(mine)
        assert integrity.status("pr-me") == integrity.STATUS_MISSING

    def test_an_import_from_elsewhere_still_reads_as_modified(self, installed):
        store.install_from_path(_skill(paths.home() / "dev" / "pr-me"))
        (paths.store_dir() / "pr-me" / "SKILL.md").write_text(
            "# edited\n", encoding="utf-8")
        assert integrity.status("pr-me") == integrity.STATUS_MODIFIED


class TestLocalSourceDir:
    @posix_modes
    def test_a_source_under_a_dir_boost_cannot_search_is_none(self, sandbox):
        # Path.is_file raised there on 3.12, which crashed `boost uninstall`.
        src = _skill(paths.home() / "locked" / "pr-me")
        src.parent.chmod(0o600)
        try:
            assert store.local_source_dir({"source_dir": str(src)}) is None
        finally:
            src.parent.chmod(0o755)


class TestInstallingOverAStoreDir:
    """Nothing that installs may copy over a dir the lock does not vouch for."""

    def test_a_store_dir_is_not_imported_onto_itself(self, installed):
        # Staging skips `.git`, so the copy swapped in deleted the history.
        mine = _mine("pr-me")
        (mine / ".git").mkdir()
        (mine / ".git" / "HEAD").write_text("ref: refs/heads/main\n",
                                            encoding="utf-8")
        with pytest.raises(BoostError) as exc:
            store.install_from_path(mine)
        assert exc.value.message == (
            "~/.agents/skills/pr-me is pr-me's own dir in the store, so there "
            "is nothing to copy it from")
        assert exc.value.hint == (
            "`boost sync` records a skill put in the store by hand")
        assert (mine / ".git" / "HEAD").is_file()
        assert lockfile.get_skill("pr-me") is None

    def test_nor_an_installed_skills(self, installed):
        sdir = store.skill_store_dir("brainstorming")
        before = lockfile.get_skill("brainstorming")
        with pytest.raises(BoostError) as exc:
            store.install_from_path(sdir)
        assert exc.value.hint == (
            "it is installed already, and edits there are live")
        assert lockfile.get_skill("brainstorming") == before

    def test_install_leaves_a_dir_the_lock_does_not_record(self, installed):
        mine = _mine("tdd-workflow", "# mine\n")
        with pytest.raises(BoostError) as exc:
            store.install(catalog.resolve_one("tdd-workflow"))
        assert exc.value.message == (
            "tdd-workflow is already in the store at "
            "~/.agents/skills/tdd-workflow, and the lock file does not "
            "record it")
        assert exc.value.hint == (
            "`boost sync` says whose it is, and records it if it is yours; "
            "`boost install tdd-workflow --force` replaces it")
        assert (mine / "SKILL.md").read_text(encoding="utf-8") == "# mine\n"
        assert lockfile.get_skill("tdd-workflow") is None

    def test_force_replaces_it(self, installed):
        mine = _mine("tdd-workflow", "# mine\n")
        store.install(catalog.resolve_one("tdd-workflow"), force=True)
        assert (mine / "SKILL.md").read_text(encoding="utf-8") != "# mine\n"
        assert lockfile.get_skill("tdd-workflow")["tap"] == installed.name

    def test_a_link_in_the_store_counts_even_dangling(self, installed):
        # The user's own link to a checkout, moved or not, is not boost's.
        link = paths.store_dir() / "tdd-workflow"
        link.symlink_to(paths.home() / "gone")
        with pytest.raises(BoostError, match="does not record it"):
            store.install(catalog.resolve_one("tdd-workflow"))
        assert _leads_to(link, paths.home() / "gone")

    def test_over_another_schema_it_names_replay(self, installed):
        _mine("tdd-workflow")
        paths.lockfile_path().write_text('{"version": 99}', encoding="utf-8")
        with pytest.raises(BoostError) as exc:
            store.install(catalog.resolve_one("tdd-workflow"))
        assert exc.value.hint == (
            "the lock file cannot be read — `boost replay` restores the lock "
            "that knows whose it is")

    def test_over_a_corrupt_lock_it_refuses_before_looking(self, installed):
        # A corrupt lock is refused for every install, store dir or not, so
        # the refusal names the backup rather than the dir.
        _mine("tdd-workflow")
        paths.lockfile_path().write_text("{not json", encoding="utf-8")
        with pytest.raises(BoostError) as exc:
            store.install(catalog.resolve_one("tdd-workflow"))
        assert exc.value.message.startswith("lock file is corrupt")
        assert "`boost replay rollback <id>`" in exc.value.hint
        assert ".skill-lock.json.corrupt" in exc.value.hint

    def test_import_leaves_one_too(self, installed):
        mine = _mine("pr-me", "# mine\n")
        with pytest.raises(BoostError) as exc:
            store.install_from_path(_skill(paths.home() / "dev" / "pr-me"))
        assert exc.value.hint == (
            "`boost sync` says whose it is, and records it if it is yours")
        assert (mine / "SKILL.md").read_text(encoding="utf-8") == "# mine\n"

    def test_a_recorded_skill_is_reimported_as_before(self, installed):
        src = _skill(paths.home() / "dev" / "pr-me", "# one\n")
        store.install_from_path(src)
        (src / "SKILL.md").write_text("# two\n", encoding="utf-8")
        store.install_from_path(src)
        assert (paths.store_dir() / "pr-me" / "SKILL.md").read_text(
            encoding="utf-8") == "# two\n"


class TestReplacesOnlyCopy:
    def test_another_dir_over_a_skill_kept_in_the_store(self, installed):
        _mine("pr-me")
        store.adopt_unrecorded("pr-me")
        assert store.replaces_only_copy(
            "pr-me", _skill(paths.home() / "dev" / "pr-me"))

    def test_not_the_store_dir_itself(self, installed):
        mine = _mine("pr-me")
        store.adopt_unrecorded("pr-me")
        assert not store.replaces_only_copy("pr-me", mine)

    def test_not_a_tapped_skill(self, installed):
        assert not store.replaces_only_copy(
            "brainstorming", _skill(paths.home() / "dev" / "brainstorming"))

    def test_not_a_name_with_no_record(self, sandbox):
        assert not store.replaces_only_copy(
            "pr-me", _skill(paths.home() / "dev" / "pr-me"))

    def test_the_name_is_the_one_an_import_would_use(self, sandbox):
        d = _skill(paths.home() / "dev" / "dir-name",
                   "---\nname: declared\n---\n# x\n")
        assert store.import_name(d) == "declared"
        assert store.import_name(d, "renamed") == "renamed"
        assert store.import_name(_skill(paths.home() / "dev" / "plain")) == "plain"


class TestRemoveForeignCopy:
    def _row(self, name="automate", how="identical"):
        return (*store.classify_unrecorded([name])["foreign_store"][0][:3], how)

    def test_deletes_the_copy_and_keeps_the_original(self, installed):
        theirs = _vendor("automate", "# same\n")
        _mine("automate", "# same\n")
        assert store.remove_foreign_copy(self._row()) is None
        assert not os.path.lexists(paths.store_dir() / "automate")
        assert (theirs / "SKILL.md").is_file()

    def test_a_symlinked_store_entry_loses_only_the_link(self, installed):
        theirs = _vendor("automate")
        elsewhere = _skill(paths.home() / "work" / "automate", "# vendor\n")
        (paths.store_dir() / "automate").symlink_to(elsewhere)
        row = ("automate", "Cursor's built-ins", str(theirs), "identical")
        assert store.remove_foreign_copy(row) is None
        assert (elsewhere / "SKILL.md").is_file()

    def test_answers_row_by_row(self, installed):
        theirs = _vendor("automate", "# same\n")
        _mine("automate", "# same\n")
        gone = ("explain", "x", str(_vendor("explain")), "identical")
        assert store.remove_foreign_copies([self._row(), gone]) == [
            None, "it is already gone"]
        assert (theirs / "SKILL.md").is_file()

    def test_kept_when_already_gone(self, installed):
        theirs = _vendor("automate")
        row = ("automate", "x", str(theirs), "identical")
        assert store.remove_foreign_copy(row) == "it is already gone"

    def test_a_missing_lock_is_no_reason_to_keep_it(self, installed):
        theirs = _vendor("automate", "# same\n")
        copy = _mine("automate", "# same\n")
        row = self._row()
        paths.lockfile_path().unlink()
        assert store.remove_foreign_copies([row]) == [None]
        assert not os.path.lexists(copy)
        assert (theirs / "SKILL.md").is_file()

    def test_kept_while_the_lock_cannot_be_read(self, installed):
        _vendor("automate", "# same\n")
        copy = _mine("automate", "# same\n")
        row = self._row()
        paths.lockfile_path().write_text("{oops", encoding="utf-8")
        assert store.remove_foreign_copies([row, row]) == [
            "the lock file cannot be read, so boost cannot tell whether it is "
            "boost's — restore the lock with `boost replay`"] * 2
        assert copy.is_dir()

    def test_kept_when_boost_has_recorded_it_since(self, installed):
        _vendor("automate", "# same\n")
        _mine("automate", "# same\n")
        row = self._row()
        lockfile.set_skill("automate", {"tap": "t", "agents": []})
        assert store.remove_foreign_copy(row) == "boost has recorded it since"
        assert (paths.store_dir() / "automate").is_dir()

    def test_kept_when_the_original_is_gone(self, installed):
        theirs = _vendor("automate", "# same\n")
        _mine("automate", "# same\n")
        row = self._row()
        (theirs / "SKILL.md").unlink()
        assert store.remove_foreign_copy(row) == (
            "the copy it duplicates, ~/.cursor/skills-cursor/automate, is gone")
        assert (paths.store_dir() / "automate").is_dir()

    def test_kept_when_the_original_now_leads_into_the_store(self, installed):
        theirs = _vendor("automate", "# same\n")
        copy = _mine("automate", "# same\n")
        row = self._row()
        shutil.rmtree(theirs)
        theirs.symlink_to(copy)
        assert store.remove_foreign_copy(row) == (
            "~/.cursor/skills-cursor/automate now leads back into the store, "
            "so it is not a second copy")
        assert copy.is_dir()

    def test_kept_when_the_original_links_into_it_file_by_file(self, installed):
        theirs = _vendor("automate", "# same\n")
        copy = _mine("automate", "# same\n")
        row = self._row()
        (theirs / "SKILL.md").unlink()
        (theirs / "SKILL.md").symlink_to(copy / "SKILL.md")
        assert store.remove_foreign_copy(row) == (
            "~/.cursor/skills-cursor/automate links into the store file by "
            "file, so deleting this would empty it")
        assert copy.is_dir()

    def test_kept_when_it_lost_its_skill_md(self, installed):
        _vendor("automate", "# same\n")
        copy = _mine("automate", "# same\n")
        row = self._row()
        (copy / "notes.md").write_text("mine\n", encoding="utf-8")
        (copy / "SKILL.md").unlink()
        assert store.remove_foreign_copy(row) == "it no longer holds a SKILL.md"
        assert (copy / "notes.md").is_file()

    def test_kept_when_edited_into_the_newest_copy(self, installed):
        # An agent's copy owned the name by being newer; an edit since makes
        # the store copy the one the user is working on.
        _codex("pr-me", "# codex\n", when=3e9)
        copy = _mine("pr-me", "# mine\n", when=1e9)
        row = self._row("pr-me", "differs")
        _skill(copy, "# mine, edited\n", when=4e9)
        assert store.remove_foreign_copy(row) == (
            "it is now newer than ~/.codex/skills/pr-me")
        assert copy.is_dir()

    def test_kept_when_it_is_now_a_copy_of_something_else(self, installed):
        _codex("automate", "# codex\n", when=3e9)
        copy = _mine("automate", "# mine\n", when=1e9)
        row = self._row(how="differs")
        _vendor("automate", "# cursor\n")
        assert store.remove_foreign_copy(row) == (
            "it is now a copy of ~/.cursor/skills-cursor/automate instead")
        assert copy.is_dir()

    def test_kept_when_it_is_no_longer_a_copy(self, installed):
        # Now the user's alias of that skill: deleting it would unlink the
        # second path they made on purpose.
        theirs = _codex("pr-me", "# same\n")
        copy = _mine("pr-me", "# same\n")
        row = self._row("pr-me")
        shutil.rmtree(copy)
        copy.symlink_to(theirs)
        assert store.remove_foreign_copy(row) == (
            "it is no longer a copy of ~/.codex/skills/pr-me")
        assert copy.is_symlink()

    def test_kept_when_it_holds_a_repository(self, installed):
        _vendor("automate", "# same\n")
        copy = _mine("automate", "# same\n")
        row = self._row()
        (copy / ".git").mkdir()
        assert store.remove_foreign_copy(row) == store.REPO_KEPT
        assert copy.is_dir()

    def test_kept_when_part_of_it_cannot_be_read_now(self, installed, monkeypatch):
        _vendor("automate", "# same\n")
        copy = _mine("automate", "# same\n")
        row = self._row()
        monkeypatch.setattr(foreign, "unreadable",
                            lambda p: copy / "refs" if Path(p) == copy else None)
        assert store.remove_foreign_copy(row) == (
            "part of it cannot be read now, so what it holds cannot be told")
        assert copy.is_dir()

    def test_kept_when_the_original_is_this_same_dir(self, installed, monkeypatch):
        # Asked last, so the reasons above keep their words: the same dir
        # under another spelling passes each of them as a copy of itself.
        _vendor("automate", "# same\n")
        _mine("automate", "# same\n")
        row = self._row()
        fresh = {**EMPTY, "foreign_store": [row]}
        assert store._still_a_copy(row, {}, fresh) is None
        monkeypatch.setattr(foreign, "same_dir", lambda a, b: True)
        assert store._still_a_copy(row, {}, fresh) == (
            "~/.cursor/skills-cursor/automate is this same dir under another name")

    def test_a_delete_that_fails_keeps_its_row_and_the_rest_still_run(
            self, installed, monkeypatch):
        for n in ("a-first", "b-next"):
            _vendor(n, "# same\n")
            _mine(n, "# same\n")
        rows = [self._row("a-first"), self._row("b-next")]
        real = store.util.remove_path

        def remove(p):
            if Path(p).name == "a-first":
                raise PermissionError(13, "Permission denied", str(Path(p) / "refs"))
            return real(p)
        monkeypatch.setattr(store.util, "remove_path", remove)
        assert store.remove_foreign_copies(rows) == [
            "deleting it stopped at ~/.agents/skills/a-first/refs: Permission "
            "denied — what is left is still there", None]
        assert (paths.store_dir() / "a-first").is_dir()
        assert not os.path.lexists(paths.store_dir() / "b-next")
        pulse = [json.loads(x) for x in paths.pulse_path().read_text(
            encoding="utf-8").splitlines()]
        assert [e["subject"] for e in pulse if e["action"] == "prune"] == ["b-next"]

    def test_an_error_with_no_path_names_the_skill(self, installed, monkeypatch):
        _vendor("automate", "# same\n")
        _mine("automate", "# same\n")
        row = self._row()

        def remove(_p):
            raise OSError("disk on fire")
        monkeypatch.setattr(store.util, "remove_path", remove)
        assert store.remove_foreign_copy(row) == (
            "deleting it stopped at automate: disk on fire — what is left is "
            "still there")

    def test_an_identical_copy_edited_since_is_kept(self, installed):
        _vendor("automate", "# same\n")
        copy = _mine("automate", "# same\n")
        row = self._row()
        (copy / "SKILL.md").write_text("# edited\n", encoding="utf-8")
        assert store.remove_foreign_copy(row) == (
            "it has changed since it matched ~/.cursor/skills-cursor/automate")
        assert copy.is_dir()

    def test_a_copy_confirmed_as_different_is_deleted_as_one(self, installed):
        _vendor("automate", "# cursor\n")
        _mine("automate", "# port\n")
        row = self._row(how="differs")
        assert store.remove_foreign_copy(row) is None
        assert not (paths.store_dir() / "automate").exists()

    def test_a_different_copy_that_came_to_match_is_still_one(self, installed):
        _vendor("automate", "# cursor\n")
        copy = _mine("automate", "# port\n")
        row = self._row(how="differs")
        (copy / "SKILL.md").write_text("# cursor\n", encoding="utf-8")
        assert store.remove_foreign_copy(row) is None
        assert not os.path.lexists(copy)

    def test_is_journaled(self, installed):
        theirs = _vendor("automate", "# same\n")
        _mine("automate", "# same\n")
        store.remove_foreign_copy(self._row())
        last = json.loads(paths.pulse_path().read_text(
            encoding="utf-8").splitlines()[-1])
        assert (last["action"], last["subject"], last["copy_of"]) == (
            "prune", "automate", str(theirs))


class TestDropPluginLink:
    def _row(self):
        return store.plugin_duplicates()[0]

    def test_drops_only_claude_codes_link_and_keeps_the_scope(self, claude_plugin,
                                                              installed):
        claude_plugin()
        ok, line = store.drop_plugin_link(self._row())
        assert ok is True
        assert line == ("unlinked brainstorming → claude-code (Claude Code loads "
                        "the same files from plugin %s)" % PLUGIN)
        e = lockfile.get_skill("brainstorming")
        assert e["only_agents"] is None and e["agents"] == REST
        assert not os.path.lexists(_claude_link())
        assert (paths.home() / ".cursor" / "skills" / "brainstorming").is_symlink()
        plan = store.sync_plan()
        assert plan["missing_links"] == plan["plugin_duplicates"] == []
        assert plan["out_of_scope_links"] == []
        assert store.sync_apply(plan) == []
        assert not os.path.lexists(_claude_link())

    def test_a_skill_scoped_to_claude_code_alone_is_dropped_too(self, claude_plugin,
                                                                installed):
        # An empty scope means every agent, so narrowing had no answer here.
        claude_plugin()
        for a in REST:
            (agents.linking_agents()[a] / "brainstorming").unlink()
        _set("brainstorming", only_agents=["claude-code"], agents=["claude-code"])
        ok, _line = store.drop_plugin_link(self._row())
        assert ok is True
        e = lockfile.get_skill("brainstorming")
        assert e["only_agents"] == ["claude-code"] and e["agents"] == []
        assert store.sync_plan()["missing_links"] == []

    def test_a_refused_claude_code_is_forgotten_too(self, claude_plugin, installed):
        claude_plugin()
        _set("brainstorming", refused_agents=["claude-code", "cursor"])
        store.drop_plugin_link(self._row())
        assert lockfile.get_skill("brainstorming")["refused_agents"] == ["cursor"]

    def test_a_refusal_list_of_only_claude_code_is_removed(self, claude_plugin, installed):
        claude_plugin()
        _set("brainstorming", refused_agents=["claude-code"])
        store.drop_plugin_link(self._row())
        assert "refused_agents" not in lockfile.get_skill("brainstorming")

    def test_refused_when_the_plugin_copy_changed_since(self, claude_plugin, installed):
        theirs = Path(claude_plugin())
        row = self._row()
        (theirs / "SKILL.md").write_text("# updated\n", encoding="utf-8")
        assert store.drop_plugin_link(row) == (
            False, "kept brainstorming → claude-code: it no longer matches the "
                   "copy in plugin %s" % PLUGIN)
        assert lockfile.get_skill("brainstorming")["agents"] == LINKED

    def test_refused_when_the_plugin_was_disabled_since(self, claude_plugin,
                                                        installed):
        claude_plugin()
        row = self._row()
        (paths.home() / ".claude" / "settings.json").write_text(
            json.dumps({"enabledPlugins": {PLUGIN: False}}), encoding="utf-8")
        assert store.drop_plugin_link(row) == (
            False, "kept brainstorming → claude-code: plugin %s is no longer "
                   "enabled" % PLUGIN)
        assert _claude_link().is_symlink()

    def test_refused_when_uninstalled_since(self, claude_plugin, installed):
        claude_plugin()
        row = self._row()
        store.uninstall("brainstorming")
        assert store.drop_plugin_link(row) == (
            False, "kept brainstorming: it is no longer linked into Claude Code")

    def test_refused_when_claude_code_was_disabled_since(self, claude_plugin, installed):
        claude_plugin()
        row = self._row()
        _disable_claude_code()
        assert store.drop_plugin_link(row) == (
            False, "kept brainstorming: it is no longer linked into Claude Code")

    def test_a_dir_that_refuses_the_unlink_keeps_the_record(self, claude_plugin,
                                                            installed, monkeypatch):
        claude_plugin()
        row = self._row()

        def boom(self, *a, **kw):
            raise PermissionError("no")
        monkeypatch.setattr(Path, "unlink", boom)
        assert store.drop_plugin_link(row) == (
            False, "kept brainstorming → claude-code: ~/.claude/skills refuses "
                   "the unlink")
        assert lockfile.get_skill("brainstorming")["agents"] == LINKED

    @pytest.mark.parametrize("swap", ["dir", "link"])
    def test_what_replaced_boosts_link_is_not_touched(self, claude_plugin,
                                                      installed, swap):
        claude_plugin()
        row = self._row()
        link = _claude_link()
        link.unlink()
        if swap == "dir":
            link.mkdir()
        else:
            link.symlink_to(_skill(paths.home() / "dev" / "brainstorming"))
        assert store.drop_plugin_link(row) == (
            False, "left brainstorming alone: ~/.claude/skills/brainstorming is "
                   "no longer boost's link")
        assert os.path.lexists(link)
        assert lockfile.get_skill("brainstorming")["agents"] == LINKED

    def test_is_journaled(self, claude_plugin, installed):
        claude_plugin()
        store.drop_plugin_link(self._row())
        last = json.loads(paths.pulse_path().read_text(
            encoding="utf-8").splitlines()[-1])
        assert (last["action"], last["subject"], last["plugin"]) == (
            "sync-prune", "brainstorming", PLUGIN)


class TestWording:
    def test_foreign_lines_group_by_owner_and_count_the_changes(self, sandbox):
        cursor = str(paths.home() / ".cursor" / "skills-cursor")
        rows = [("a", "Cursor's built-ins", cursor + "/a", "identical"),
                ("b", "Cursor's built-ins", cursor + "/b", "differs"),
                ("c", "Codex", str(paths.home() / ".codex/skills/c"), "differs")]
        assert store.foreign_store_lines(rows) == [
            "a, b copy skills from Cursor's built-ins (~/.cursor/skills-cursor), "
            "not boost's (1 of them changed from the original) — remove with "
            "`boost sync --prune`",
            "c copies a skill from Codex (~/.codex/skills), not boost's "
            "(changed from the original) — remove with `boost sync --prune`"]

    def test_a_repo_gets_its_own_line_and_no_prune_remedy(self, sandbox):
        (_mine("r") / ".git").mkdir()
        _mine("a")
        rows = [("r", "Codex", "/x/r", "differs"), ("a", "Codex", "/x/a", "identical")]
        assert store.is_repo_copy(rows[0]) is True
        assert store.is_repo_copy(rows[1]) is False
        assert store.foreign_store_lines(rows) == [
            "a copies a skill from Codex (/x), not boost's — remove with "
            "`boost sync --prune`",
            "r is named like a skill from Codex (/x/r), but it is a git "
            "repository, so `boost sync --prune` leaves it — move or delete "
            "it yourself if it is a copy"]

    def test_unreadable_line(self, sandbox):
        d = paths.store_dir()
        assert store.unreadable_line([("pr-me", str(d / "pr-me" / "refs"))]) == (
            "pr-me: ~/.agents/skills/pr-me/refs cannot be read, so boost cannot "
            "tell whose it is or record it — make it readable, then re-run "
            "`boost sync`")
        assert store.unreadable_line([("a", str(d / "a")), ("b", str(d / "b" / "x"))]) == (
            "2 store dirs cannot be recorded: boost cannot read what says whose "
            "they are (a: ~/.agents/skills/a, b: ~/.agents/skills/b/x) — make "
            "those readable, then re-run `boost sync`")

    def test_foreign_lines_for_identical_copies_say_nothing_changed(self, sandbox):
        rows = [("a", "o", "/x/a", "identical")]
        assert store.foreign_store_lines(rows) == [
            "a copies a skill from o (/x), not boost's — remove with "
            "`boost sync --prune`"]

    def test_foreign_lines_truncate_long_lists(self, sandbox):
        rows = [("s%d" % i, "o", "/x/s%d" % i, "identical") for i in range(10)]
        line = store.foreign_store_lines(rows)[0]
        assert line.startswith("s0, s1, s2, s3, s4, s5, s6, s7, … copy skills")

    def test_plugin_lines(self, sandbox):
        rows = [("a", "p@m", "/x", "identical"), ("b", "p@m", "/y", "identical"),
                ("c", "q@m", "/z", "identical"), ("d", "p@m", "/w", "differs")]
        assert store.plugin_duplicate_lines(rows) == [
            "a, b show twice in Claude Code — plugin p@m ships the same files; "
            "`boost sync --prune` drops boost's Claude Code link",
            "c shows twice in Claude Code — plugin q@m ships the same files; "
            "`boost sync --prune` drops boost's Claude Code link"]
        assert store.plugin_variant_lines(rows) == [
            "d shows twice in Claude Code — plugin p@m ships a different skill "
            "by that name; both left as they are"]

    def test_plugin_lines_name_eight_and_cut_after_eight(self, sandbox):
        rows = [("s%d" % i, "p@m", "/x", "identical") for i in range(9)]
        assert store.plugin_duplicate_lines(rows[:8])[0].startswith(
            "s0, s1, s2, s3, s4, s5, s6, s7 show twice")
        assert store.plugin_duplicate_lines(rows)[0].startswith(
            "s0, s1, s2, s3, s4, s5, s6, s7, … show twice")

    def test_older_copy_lines(self, sandbox):
        rows = [("pr-me", "Codex", str(paths.home() / ".codex/skills/pr-me"))]
        assert store.older_copy_lines(rows) == [
            "pr-me: the copy in ~/.codex/skills/pr-me (Codex) is older by file "
            "times — left alone"]

    def test_not_skill_line(self, sandbox):
        assert store.not_skill_line(["synced"]) == (
            "~/.agents/skills/synced holds no SKILL.md, so it is not a skill — "
            "left alone")
        assert store.not_skill_line(["a", "b", "c", "d", "e"]) == (
            "5 dirs in ~/.agents/skills hold no SKILL.md, so they are not "
            "skills (a, b, c, d, e) — left alone")
        assert store.not_skill_line(["a", "b", "c", "d", "e", "f"]) == (
            "6 dirs in ~/.agents/skills hold no SKILL.md, so they are not "
            "skills (a, b, c, d, e, …) — left alone")

    def test_misnamed_line(self, sandbox):
        assert store.misnamed_line(["b copy"]) == (
            "~/.agents/skills/b copy: boost cannot record a skill by that name "
            "(only letters, digits, '.', '_' and '-') — left alone")
        assert store.misnamed_line(["b copy", "c copy"]) == (
            "2 dirs in ~/.agents/skills have names boost cannot record a skill "
            "by (b copy, c copy) — left alone")
