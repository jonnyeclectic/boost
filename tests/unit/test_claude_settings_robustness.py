# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Hook names, foreign shapes and project roots in `core/claude_settings`.

Three bugs, one file each in the findings that produced this module:

* a ``--name`` with surrounding whitespace was stored raw and read back
  trimmed, so it never matched itself — re-adding duplicated the hook and
  removing could not find it;
* an inner hook entry that is not an object (another tool's, or a typo)
  crashed every reader with ``AttributeError``, ``boost doctor`` included;
* project scope used the raw cwd: from a repo subdirectory it scattered a
  ``.claude/`` below the root, and from ``$HOME`` it wrote the *global* file.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import claude_settings as cs
from boost_cli.errors import BoostError


class TestCleanName:
    def test_trims_surrounding_whitespace(self):
        assert cs.clean_name("  my hook \t") == "my hook"

    def test_keeps_inner_spaces(self):
        assert cs.clean_name("a b") == "a b"

    @pytest.mark.parametrize("bad", ["", "   ", "\t", None])
    def test_refuses_an_empty_name(self, bad):
        with pytest.raises(BoostError, match="non-empty name"):
            cs.clean_name(bad)

    @pytest.mark.parametrize("bad", ["a\nrm -rf x", "a\rb", "x # boost:y"])
    def test_refuses_a_name_that_would_escape_the_comment(self, bad):
        with pytest.raises(BoostError, match="line break"):
            cs.clean_name(bad)


class TestPaddedNameRoundTrips:
    def test_readding_a_padded_name_replaces_instead_of_duplicating(
            self, sandbox):
        cs.add_hook("global", "Stop", "my hook ", "echo a")
        cs.add_hook("global", "Stop", "my hook ", "echo a")
        rows = cs.list_hooks("global")
        assert len(rows) == 1
        assert rows[0]["name"] == "my hook"
        stored = cs.load("global")["hooks"]["Stop"][0]["hooks"][0]["command"]
        assert stored == "echo a # boost:my hook"

    def test_the_padded_name_removes_what_it_added(self, sandbox):
        cs.add_hook("global", "Stop", " pad ", "echo a")
        assert cs.has_hook("global", "Stop", " pad ")
        assert cs.remove_hook_by_name("global", " pad ") == 1
        assert cs.list_hooks("global") == []
        assert not cs.has_hook("global", "Stop", "pad")

    def test_remove_hook_trims_too(self, sandbox):
        cs.add_hook("global", "Stop", "pad", "echo a")
        assert cs.remove_hook("global", "Stop", "pad  ") == 1

    def test_duplicates_already_on_disk_are_removable_by_trimmed_name(
            self, sandbox):
        entry = {"type": "command", "command": "echo a # boost:dup ",
                 "timeout": 10}
        cs.save("global", {"hooks": {"Stop": [
            {"hooks": [dict(entry)]}, {"hooks": [dict(entry)]}]}})
        assert cs.remove_hook_by_name("global", "dup") == 2
        assert "hooks" not in cs.load("global")

    def test_add_refuses_an_all_whitespace_name_without_writing(self, sandbox):
        with pytest.raises(BoostError):
            cs.add_hook("global", "Stop", "   ", "echo a")
        assert not cs.settings_path("global").exists()

    def test_remove_with_an_empty_name_finds_nothing_rather_than_raising(
            self, sandbox):
        cs.add_hook("global", "Stop", "keep", "echo a")
        assert cs.remove_hook_by_name("global", "  ") == 0
        assert cs.has_hook("global", "Stop", "keep")


FOREIGN = {"hooks": {"Stop": [
    {"hooks": ["echo hi", 7, {"type": "command", "command": "theirs"}]}]}}


class TestForeignShapesAreSkippedNotCrashedOn:
    def _seed(self, data):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def test_readers_skip_a_non_object_inner_entry(self, sandbox):
        self._seed(FOREIGN)
        assert cs.list_hooks("global") == []
        assert cs.foreign_hooks("global") == [
            {"scope": "global", "event": "Stop", "command": "theirs",
             "matcher": ""}]
        assert not cs.has_hook("global", "Stop", "echo hi")

    def test_remove_leaves_non_object_entries_untouched(self, sandbox):
        p = self._seed(FOREIGN)
        before = p.read_text(encoding="utf-8")
        assert cs.remove_hook_by_name("global", "a") == 0
        assert cs.remove_hook("global", "Stop", "a") == 0
        assert p.read_text(encoding="utf-8") == before

    def test_add_and_remove_keep_the_foreign_entries_verbatim(self, sandbox):
        self._seed(FOREIGN)
        cs.add_hook("global", "Stop", "mine", "boost guard")
        blocks = cs.load("global")["hooks"]["Stop"]
        assert blocks[0] == FOREIGN["hooks"]["Stop"][0]
        assert [r["name"] for r in cs.list_hooks("global")] == ["mine"]
        assert cs.remove_hook_by_name("global", "mine") == 1
        assert cs.load("global") == FOREIGN

    def test_owned_entries_beside_a_string_are_still_removed(self, sandbox):
        self._seed({"hooks": {"Stop": [{"hooks": [
            "echo hi", {"type": "command", "command": "x # boost:mine"}]}]}})
        assert cs.remove_hook("global", "Stop", "mine") == 1
        assert cs.load("global")["hooks"]["Stop"] == [{"hooks": ["echo hi"]}]

    @pytest.mark.parametrize("hooks", [[], "nope", 3])
    def test_a_non_object_hooks_key_reads_as_no_hooks(self, sandbox, hooks):
        self._seed({"hooks": hooks})
        assert cs.list_hooks("global") == []
        assert cs.foreign_hooks("global") == []
        assert cs.remove_hook_by_name("global", "a") == 0
        assert not cs.has_hook("global", "Stop", "a")

    @pytest.mark.parametrize("hooks", [[], "nope"])
    def test_add_refuses_a_non_object_hooks_key_without_writing(
            self, sandbox, hooks):
        p = self._seed({"hooks": hooks, "model": "opus"})
        before = p.read_text(encoding="utf-8")
        with pytest.raises(BoostError, match="'hooks' must be an object"):
            cs.add_hook("global", "SessionStart", "a", "x")
        assert p.read_text(encoding="utf-8") == before

    def test_an_event_that_is_not_a_list_is_skipped_by_readers(self, sandbox):
        self._seed({"hooks": {
            "SessionStart": {"hooks": [{"command": "x # boost:a"}]},
            "Stop": [{"hooks": [{"command": "y # boost:b"}]}]}})
        assert [r["name"] for r in cs.list_hooks("global")] == ["b"]
        assert cs.foreign_hooks("global") == []
        assert not cs.has_hook("global", "SessionStart", "a")
        assert cs.remove_hook("global", "SessionStart", "a") == 0
        assert cs.remove_hook_by_name("global", "b") == 1

    def test_add_refuses_an_event_that_is_not_a_list(self, sandbox):
        p = self._seed({"hooks": {"SessionStart": {"x": 1}}})
        before = p.read_text(encoding="utf-8")
        with pytest.raises(BoostError,
                           match=r"hooks\.SessionStart must be a list"):
            cs.add_hook("global", "SessionStart", "a", "x")
        assert p.read_text(encoding="utf-8") == before

    def test_add_to_another_event_beside_a_bad_one_still_works(self, sandbox):
        self._seed({"hooks": {"SessionStart": {"x": 1}}})
        cs.add_hook("global", "Stop", "a", "x")
        data = cs.load("global")
        assert data["hooks"]["SessionStart"] == {"x": 1}
        assert cs.has_hook("global", "Stop", "a")


class TestProjectScopeResolvesTheProjectRoot:
    def test_a_subdirectory_resolves_to_the_repo_root(
            self, sandbox, tmp_path, monkeypatch):
        repo = tmp_path / "proj-subdir-root"
        deep = repo / "src" / "deep"
        deep.mkdir(parents=True)
        (repo / ".git").mkdir()
        monkeypatch.chdir(deep)
        want = repo.resolve() / ".claude" / "settings.json"
        assert str(cs.settings_path("project")) == str(want)
        cs.add_hook("project", "SessionStart", "h5", "echo hi")
        assert want.is_file()
        assert not (deep / ".claude").exists()
        monkeypatch.chdir(repo)
        assert [r["name"] for r in cs.list_hooks("project")] == ["h5"]

    def test_an_explicit_project_dir_still_wins(self, sandbox, tmp_path):
        other = tmp_path / "explicit-proj"
        assert cs.settings_path("project", other) == \
            other / ".claude" / "settings.json"
        assert cs.project_base(other) == other

    def test_an_unmarked_cwd_is_its_own_project(
            self, sandbox, tmp_path, monkeypatch):
        loose = tmp_path / "loose-proj"
        loose.mkdir()
        monkeypatch.chdir(loose)
        assert cs.settings_path("project").parent.parent.resolve() == \
            loose.resolve()

    def test_home_is_not_a_project(self, sandbox, monkeypatch):
        monkeypatch.chdir(sandbox)
        assert cs.project_base() is None
        with pytest.raises(BoostError, match="no project here"):
            cs.settings_path("project")

    def test_a_project_add_from_home_never_writes_the_global_file(
            self, sandbox, monkeypatch):
        monkeypatch.chdir(sandbox)
        with pytest.raises(BoostError, match="no project here"):
            cs.add_hook("project", "SessionStart", "h2", "echo")
        assert not cs.settings_path("global").exists()
        assert not (sandbox / ".claude").exists()

    def test_listing_from_home_shows_a_global_hook_once(
            self, sandbox, monkeypatch):
        cs.add_hook("global", "Stop", "once", "echo")
        monkeypatch.chdir(sandbox)
        rows = cs.list_hooks()
        assert [(r["scope"], r["name"]) for r in rows] == [("global", "once")]
        assert [r["scope"] for r in cs.foreign_hooks()] == []

    def test_listing_from_a_project_reads_both_scopes(
            self, sandbox, tmp_path, monkeypatch):
        repo = tmp_path / "proj-both-scopes"
        repo.mkdir()
        (repo / ".git").mkdir()
        monkeypatch.chdir(repo)
        cs.add_hook("global", "Stop", "g", "echo")
        cs.add_hook("project", "Stop", "p", "echo")
        assert [(r["scope"], r["name"]) for r in cs.list_hooks()] == [
            ("global", "g"), ("project", "p")]


class TestReadingProjectScopeWithNoProject:
    """A read of project scope from ``$HOME`` is empty, never an error.

    ``bmad doctor`` and ``bmad status`` read project scope unasked; when
    ``settings_path("project")`` started refusing ``$HOME``, both died with
    "there is no project here" on the global row's heels. The global hook must
    not leak through under the project label either — that was the
    double-listing the refusal was added for.
    """

    @pytest.fixture()
    def at_home(self, sandbox, monkeypatch):
        monkeypatch.chdir(sandbox)
        cs.add_hook("global", "SessionStart", "home-read", "echo g")
        return sandbox

    def test_load_is_empty(self, at_home):
        assert cs.load("project") == {}
        assert cs.load("global") != {}

    def test_has_hook_is_false(self, at_home):
        assert cs.has_hook("project", "SessionStart", "home-read") is False
        assert cs.has_hook("global", "SessionStart", "home-read") is True

    def test_explicit_project_lists_nothing(self, at_home):
        assert cs.list_hooks("project") == []
        assert cs.foreign_hooks("project") == []

    def test_remove_finds_nothing_and_leaves_global(self, at_home):
        assert cs.remove_hook("project", "SessionStart", "home-read") == 0
        assert cs.remove_hook_by_name("project", "home-read") == 0
        assert cs.has_hook("global", "SessionStart", "home-read") is True

    def test_a_write_still_refuses(self, at_home):
        with pytest.raises(BoostError, match="no project here"):
            cs.add_hook("project", "SessionStart", "home-write", "echo")
