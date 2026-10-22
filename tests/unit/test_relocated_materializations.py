# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Rules, workflows and links left behind when an agent's config changes.

Two shapes of the same gap: the lock names agents, and every check walked
each agent's *current* dir.

* Repointing ``agents.cursor.dir`` after a rule and a workflow were written
  left both files in ``~/.cursor``, which Cursor no longer reads, while
  doctor said "fully materialized", verify said ok and sync moved nothing.
  ``reinstall`` then wrote the new file and forgot the old one, so no command
  could reach it again.
* Flipping ``agents.windsurf.links_skills`` false left boost's link in
  ``~/.windsurf/skills``: uninstall deleted the store dir and left the link
  dangling into it, and doctor called that "0 broken links".
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from boost_cli.core import agents, lockfile, paths, store


@pytest.fixture()
def mixed(boost, tmp_path):
    """A tap with one skill, one rule and one workflow, all installed."""
    src = tmp_path / "mixed-tap"
    (src / "skills" / "alpha").mkdir(parents=True)
    (src / "rules").mkdir()
    (src / "commands").mkdir()
    (src / "skills" / "alpha" / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: A skill.\n---\nBody.\n",
        encoding="utf-8")
    (src / "rules" / "tidy-imports.mdc").write_text(
        "---\ndescription: A rule.\n---\nRule body.\n", encoding="utf-8")
    (src / "commands" / "review-pr.md").write_text(
        "---\ndescription: A workflow.\n---\nWorkflow body.\n",
        encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=src, check=True)
    subprocess.run(["git", "add", "-A"], cwd=src, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "init"], cwd=src, check=True)
    boost("tap", str(src))
    for name in ("alpha", "tidy-imports", "review-pr"):
        boost("install", name)
    return src


def _home(*parts):
    return paths.home().joinpath(*parts)


OLD_RULE = (".cursor", "rules", "tidy-imports.mdc")
NEW_RULE = (".cursor2", "rules", "tidy-imports.mdc")
OLD_FLOW = (".cursor", "commands", "review-pr.md")
NEW_FLOW = (".cursor2", "commands", "review-pr.md")


def _repoint(boost):
    boost("config", "set", "agents.cursor.dir", "~/.cursor2/skills")


def _cursor_row(kind, name):
    get = lockfile.get_rule if kind == "rule" else lockfile.get_workflow
    return next(m for m in get(name)["materializations"]
                if m.get("agent") == "cursor")


class TestRepointedDirMaterializations:
    def test_doctor_names_both_rows_and_withholds_the_all_clear(self, boost,
                                                                mixed):
        _repoint(boost)
        out = " ".join(boost("doctor", expect=1).out.split())
        assert ("rule tidy-imports for cursor is at ~/.cursor/rules/"
                "tidy-imports.mdc, but Cursor now reads ~/.cursor2/rules/"
                "tidy-imports.mdc — run `boost sync` to move it") in out
        assert ("workflow review-pr for cursor is at ~/.cursor/commands/"
                "review-pr.md, but Cursor now reads ~/.cursor2/commands/"
                "review-pr.md — run `boost sync` to move it") in out
        assert "fully materialized" not in out
        # Named once each: the presence checks do not add "missing" lines.
        assert "missing its" not in out

    def test_verify_fails_both(self, boost, mixed):
        _repoint(boost)
        lines = [" ".join(ln.split()) for ln in
                 boost("verify", expect=1).out.splitlines()]
        assert "tidy-imports missing rule" in lines
        assert "review-pr missing workflow" in lines

    def test_sync_moves_both_and_doctor_agrees_after(self, boost, mixed):
        _repoint(boost)
        out = boost("sync").out
        assert "re-materialized rule tidy-imports from" in out
        assert "re-materialized workflow review-pr from" in out
        assert not os.path.lexists(_home(*OLD_RULE))
        assert not os.path.lexists(_home(*OLD_FLOW))
        assert _home(*NEW_RULE).read_text(encoding="utf-8") \
            == "---\ndescription: A rule.\n---\nRule body.\n"
        assert _home(*NEW_FLOW).is_file()
        assert (Path(_cursor_row("rule", "tidy-imports")["path"]).as_posix()
                == _home(*NEW_RULE).as_posix())
        assert (Path(_cursor_row("workflow", "review-pr")["path"]).as_posix()
                == _home(*NEW_FLOW).as_posix())
        assert "rule tidy-imports for cursor" not in boost("doctor").out
        boost("verify")
        # Nothing left to move: a second sync is a no-op for them.
        assert "re-materialized" not in boost("sync").out

    def test_heal_previews_then_moves(self, boost, mixed):
        _repoint(boost)
        out = boost("heal", "--dry-run").out
        assert "would re-materialize rule tidy-imports from" in out
        assert os.path.isfile(_home(*OLD_RULE))
        boost("heal")
        assert not os.path.lexists(_home(*OLD_RULE))
        assert os.path.isfile(_home(*NEW_RULE))

    def test_reinstall_then_uninstall_leaves_the_old_dir_empty(self, boost,
                                                               mixed):
        _repoint(boost)
        boost("reinstall", "tidy-imports")
        assert not os.path.lexists(_home(*OLD_RULE))
        assert os.path.isfile(_home(*NEW_RULE))
        assert [m["path"] for m in lockfile.get_rule("tidy-imports")
                ["materializations"] if m.get("agent") == "cursor"] \
            == [str(_home(*NEW_RULE))]
        boost("uninstall", "tidy-imports")
        assert not os.path.lexists(_home(*NEW_RULE))
        assert not os.path.lexists(_home(*OLD_RULE))

    def test_an_edited_old_rule_is_kept_and_still_recorded(self, boost, mixed):
        _home(*OLD_RULE).write_text("mine now\n", encoding="utf-8")
        _repoint(boost)
        boost("reinstall", "tidy-imports")
        assert _home(*OLD_RULE).read_text(encoding="utf-8") == "mine now\n"
        rows = [m["path"] for m in lockfile.get_rule("tidy-imports")
                ["materializations"] if m.get("agent") == "cursor"]
        assert rows == [str(_home(*NEW_RULE)), str(_home(*OLD_RULE))]

    def test_a_context_file_gives_up_only_the_block(self, boost, mixed):
        claude = _home(".claude", "CLAUDE.md")
        text = claude.read_text(encoding="utf-8")
        claude.write_text("# mine\n\n" + text, encoding="utf-8")
        boost("config", "set", "agents.claude-code.dir", "~/.claude2/skills")
        boost("sync")
        assert claude.read_text(encoding="utf-8") == "# mine\n"
        assert "boost:rule:tidy-imports start" in _home(
            ".claude2", "CLAUDE.md").read_text(encoding="utf-8")

    def test_a_context_file_boost_created_goes_when_emptied(self, boost, mixed):
        boost("config", "set", "agents.claude-code.dir", "~/.claude2/skills")
        boost("sync")
        assert not os.path.lexists(_home(".claude", "CLAUDE.md"))
        assert os.path.isfile(_home(".claude2", "CLAUDE.md"))


class TestRelocatedTo:
    def test_in_place_rows_are_not_relocated(self, boost, mixed):
        entry = lockfile.get_rule("tidy-imports")
        for m in entry["materializations"]:
            assert agents.relocated_to("rule", "tidy-imports", entry, m) is None

    def test_a_repointed_row_names_its_new_place(self, boost, mixed):
        _repoint(boost)
        entry = lockfile.get_workflow("review-pr")
        m = _cursor_row("workflow", "review-pr")
        assert agents.relocated_to("workflow", "review-pr", entry, m) \
            == _home(*NEW_FLOW)
        rule = lockfile.get_rule("tidy-imports")
        assert agents.relocated_to("rule", "tidy-imports", rule,
                                   _cursor_row("rule", "tidy-imports")) \
            == _home(*NEW_RULE)

    @pytest.mark.skipif(os.name == "nt", reason="symlinks need privilege")
    def test_the_same_file_by_another_spelling_is_not_moved(self, boost,
                                                            mixed, tmp_path):
        # $HOME was /tmp/x at install and is /private/tmp/x now (macOS).
        alias = tmp_path / "home-alias"
        alias.symlink_to(paths.home(), target_is_directory=True)
        entry = lockfile.get_rule("tidy-imports")
        m = {**_cursor_row("rule", "tidy-imports"),
             "path": str(alias.joinpath(*OLD_RULE))}
        assert agents.relocated_to("rule", "tidy-imports", entry, m) is None
        # ...while a moved dir under the alias still reads as moved.
        _repoint(boost)
        assert agents.relocated_to("rule", "tidy-imports", entry, m) \
            == _home(*NEW_RULE)

    def test_rows_with_nothing_to_compare(self, boost, mixed):
        _repoint(boost)
        entry = lockfile.get_workflow("review-pr")
        m = _cursor_row("workflow", "review-pr")
        assert agents.relocated_to("workflow", "review-pr", entry,
                                   {**m, "slot": None}) is None
        assert agents.relocated_to("workflow", "review-pr", entry,
                                   {**m, "path": ""}) is None
        assert agents.relocated_to("workflow", "review-pr", entry,
                                   {**m, "agent": None}) is None
        assert agents.relocated_to("workflow", "review-pr", entry,
                                   {**m, "agent": "nobody"}) is None
        assert agents.materialization_target(
            "workflow", "review-pr", entry, {**m, "slot": "skill"}) is None
        assert agents.materialization_target(
            "rule", "../escape", lockfile.get_rule("tidy-imports"),
            _cursor_row("rule", "tidy-imports")) is None

    def test_a_disabled_agent_is_not_relocated(self, boost, mixed):
        _repoint(boost)
        boost("config", "set", "agents.cursor.enabled", "false")
        entry = lockfile.get_rule("tidy-imports")
        assert agents.relocated_to("rule", "tidy-imports", entry,
                                   _cursor_row("rule", "tidy-imports")) is None


def _windsurf(name):
    return _home(".windsurf", "skills", name)


class TestLinksLeftAfterLinksSkillsOff:
    def _flip(self, boost):
        boost("config", "set", "agents.windsurf.links_skills", "false")

    def test_the_dir_is_remembered_once_flipped(self, boost, mixed):
        assert ("windsurf", _home(".windsurf", "skills")) \
            not in agents.remembered_native_dirs()
        self._flip(boost)
        assert ("windsurf", _home(".windsurf", "skills")) \
            in agents.remembered_native_dirs()
        # Never folded into the broad sweeps.
        assert _home(".windsurf", "skills") not in agents.sweep_dirs()

    def test_a_native_dir_boost_never_linked_into_is_not_remembered(
            self, boost, mixed):
        assert all(a != "gemini" for a, _d in agents.remembered_native_dirs())

    def test_uninstall_removes_only_its_own_link(self, boost, mixed):
        self._flip(boost)
        other = _windsurf("other")
        os.symlink(paths.store_dir() / "someone-else", other)
        theirs = _windsurf("theirs")
        os.symlink(paths.home() / "elsewhere", theirs)
        out = boost("uninstall", "alpha").out
        assert "Uninstalled" in out
        assert not os.path.lexists(_windsurf("alpha"))
        assert os.path.islink(other) and os.path.islink(theirs)

    def test_a_link_to_a_different_store_dir_under_the_name_stays(self, boost,
                                                                  mixed):
        self._flip(boost)
        link = _windsurf("alpha")
        os.unlink(link)
        os.symlink(paths.store_dir() / "beta", link)
        assert "windsurf" not in store.unlink_agents("alpha")
        assert os.path.islink(link)

    def test_doctor_counts_and_heal_removes_the_dangling_link(self, boost,
                                                              mixed):
        self._flip(boost)
        link = _windsurf("alpha")
        os.unlink(link)
        os.symlink(paths.store_dir() / "gone-skill", link)
        out = boost("doctor", expect=1).out
        assert "1 broken symlink in agent dirs" in out
        boost("heal")
        assert not os.path.lexists(link)

    def test_sync_sweeps_a_dangling_link_and_leaves_a_live_one(self, boost,
                                                               mixed):
        self._flip(boost)
        dangling = _windsurf("gone-skill")
        os.symlink(paths.store_dir() / "gone-skill", dangling)
        boost("sync")
        assert not os.path.lexists(dangling)
        # The live link is duplicate discovery's, removed only on request.
        assert os.path.islink(_windsurf("alpha"))

    def test_clean_lists_the_dangling_link(self, boost, mixed):
        self._flip(boost)
        os.symlink(paths.store_dir() / "gone-skill", _windsurf("gone-skill"))
        out = " ".join(boost("clean", "--dry-run").out.split())
        assert "would remove ~/.windsurf/skills/gone-skill (broken symlink)" \
            in out


def test_links_to_store_dir_reads_the_raw_target(sandbox):
    adir = paths.home() / "d"
    adir.mkdir()
    rel = adir / "rel"
    os.symlink(os.path.relpath(store.skill_store_dir("x"), adir), rel)
    assert store.links_to_store_dir(rel, "x")
    assert not store.links_to_store_dir(rel, "y")
    assert not store.links_to_store_dir(adir, "x")  # not a link


def test_a_project_row_is_never_relocated(boost, mixed):
    """A repo's committed layout does not move with a dir under $HOME."""
    _repoint(boost)
    entry = dict(lockfile.get_rule("tidy-imports"),
                 base=str(paths.home() / "repo"))
    m = _cursor_row("rule", "tidy-imports")
    assert agents.materialization_target("rule", "tidy-imports", entry,
                                         m) is None
    assert agents.relocated_to("rule", "tidy-imports", entry, m) is None


def test_a_store_alias_is_not_a_remembered_native_dir(boost, mixed):
    adir = _home(".windsurf", "skills")
    for link in adir.iterdir():
        os.unlink(link)
    adir.rmdir()
    os.symlink(paths.store_dir(), adir)
    boost("config", "set", "agents.windsurf.links_skills", "false")
    assert all(a != "windsurf" for a, _d in agents.remembered_native_dirs())


class TestRetireMoved:
    """`store._retire_moved` on the rows a re-install moved off."""

    @staticmethod
    def _block_row(path, sha=None, created=None):
        row = {"agent": "claude-code", "mode": "claude", "path": str(path)}
        if sha:
            row["sha256"] = sha
        if created is not None:
            row["created"] = created
        return row

    def _existing(self, *rows):
        return {"materializations": list(rows)}

    def test_a_damaged_old_block_keeps_its_row_and_text(self, sandbox):
        old = paths.home() / "old" / "CLAUDE.md"
        old.parent.mkdir()
        text = "mine\n<!-- boost:rule:r start -->\nno end marker\n"
        old.write_text(text, encoding="utf-8")
        row = self._block_row(old)
        assert store._retire_moved("r", self._existing(row), ["claude-code"],
                                   []) == [row]
        assert old.read_text(encoding="utf-8") == text

    def test_an_old_file_with_no_block_drops_the_row(self, sandbox):
        old = paths.home() / "old" / "CLAUDE.md"
        old.parent.mkdir()
        old.write_text("mine\n", encoding="utf-8")
        assert store._retire_moved(
            "r", self._existing(self._block_row(old)), ["claude-code"],
            []) == []
        assert old.read_text(encoding="utf-8") == "mine\n"

    def test_an_edited_block_keeps_its_row(self, sandbox):
        from boost_cli.core import rules
        old = paths.home() / "old" / "CLAUDE.md"
        old.parent.mkdir()
        text = rules.merge_block("", "r", "edited body")
        old.write_text(text, encoding="utf-8")
        row = self._block_row(old, sha="0" * 64, created=True)
        assert store._retire_moved("r", self._existing(row), ["claude-code"],
                                   []) == [row]
        assert old.read_text(encoding="utf-8") == text

    def test_a_dangling_old_context_file_is_nothing_to_strip(self, sandbox):
        old = paths.home() / "CLAUDE.md"
        os.symlink(paths.home() / "nowhere.md", old)
        assert store._retire_moved(
            "r", self._existing(self._block_row(old)), ["claude-code"],
            []) == []
        assert os.path.islink(old)

    def test_an_old_path_that_is_a_new_one_by_another_name_stays(self,
                                                                 sandbox):
        real = paths.home() / "real"
        real.mkdir()
        f = real / "r.mdc"
        f.write_text("body", encoding="utf-8")
        alias = paths.home() / "alias"
        os.symlink(real, alias)
        row = {"agent": "cursor", "mode": "file", "path": str(alias / "r.mdc")}
        new = [{"agent": "windsurf", "path": str(f)}]
        assert store._retire_moved("r", self._existing(row), ["cursor"],
                                   new) == []
        assert f.read_text(encoding="utf-8") == "body"

    def test_an_untouched_agent_keeps_its_file(self, sandbox):
        f = paths.home() / "r.mdc"
        f.write_text("body", encoding="utf-8")
        row = {"agent": "cursor", "mode": "file", "path": str(f)}
        assert store._retire_moved("r", self._existing(row), ["windsurf"],
                                   []) == []
        assert f.is_file()
