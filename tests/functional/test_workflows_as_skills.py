# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: a workflow's copy in the skill store.

A workflow lands in each agent's ``agents/`` or ``commands/`` dir, which an
agent that reads only skills (Codex) never opens. So boost also writes
``~/.agents/skills/<name>/SKILL.md``, recorded on the workflow's own lock entry
and never linked into an agent — those agents already have the workflow file.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from boost_cli.core import lockfile, paths, policy, registry, store
from boost_cli.errors import BoostError

AGENT = ("---\nname: reviewer\nversion: 1.0.0\n"
         "description: Reviews a diff for bugs\n"
         "tools: Read, Grep\nmodel: sonnet\ncolor: blue\n---\n\n"
         "# Reviewer\n\nRead the diff.\n")
WANT = ("---\nname: reviewer\ndescription: Reviews a diff for bugs\n---\n\n"
        "# Reviewer\n\nRead the diff.\n")


def _commit(tap_dir, relpath, content, msg):
    p = tap_dir / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(tap_dir), "add", "-A"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tap_dir), "commit", "-qm", msg],
                   check=True, capture_output=True)


@pytest.fixture
def wf_tap(boost, fixture_tap_src, tmp_path):
    tap_dir = tmp_path / "wf-tap"
    shutil.copytree(fixture_tap_src, tap_dir)
    _commit(tap_dir, "agents/reviewer.md", AGENT, "add agent")
    boost("tap", tap_dir)
    return tap_dir


def _copy():
    return paths.store_dir() / "reviewer" / "SKILL.md"


def _rows():
    return lockfile.get_workflow("reviewer")["materializations"]


def _flat(text):
    """Output with its wrapping undone, so a phrase can be found whole."""
    return " ".join(text.split())


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TestInstall:
    def test_writes_the_copy_records_it_last_and_links_nothing(self, boost,
                                                               wf_tap):
        r = boost("install", "reviewer")
        assert _copy().read_text(encoding="utf-8") == WANT
        assert "as a skill → ~/.agents/skills/reviewer" in _flat(r.out)
        rows = _rows()
        assert rows[-1] == {"agent": None, "slot": "skill",
                            "path": str(_copy()), "sha256": _sha(WANT)}
        assert all(m["slot"] == "agents" for m in rows[:-1])
        # The native file is still verbatim, and no agent gets a skill link.
        assert (paths.home() / ".claude" / "agents" / "reviewer.md").read_text(
            encoding="utf-8") == AGENT
        for d in (".claude/skills", ".cursor/skills", ".windsurf/skills",
                  ".gemini/antigravity-cli/skills"):
            assert not (paths.home() / d / "reviewer").exists()
        # Not a skill: the skills section stays empty, and as_skill is only
        # recorded when a flag said so.
        assert lockfile.get_skill("reviewer") is None
        assert "as_skill" not in lockfile.get_workflow("reviewer")
        # and `list` still names agents, never a `?` or a crash on None
        assert "?" not in lockfile.agent_names(
            "workflow", lockfile.get_workflow("reviewer"))

    def test_reinstall_keeps_exactly_one_row(self, boost, wf_tap):
        boost("install", "reviewer")
        boost("reinstall", "reviewer")
        boost("install", "reviewer", "--force")
        assert sum(m["slot"] == "skill" for m in _rows()) == 1

    def test_no_as_skill_writes_nothing_and_sticks(self, boost, wf_tap):
        r = boost("install", "reviewer", "--no-as-skill")
        assert "as a skill" not in _flat(r.out)
        assert not (paths.store_dir() / "reviewer").exists()
        assert lockfile.get_workflow("reviewer")["as_skill"] is False
        boost("reinstall", "reviewer")
        assert not (paths.store_dir() / "reviewer").exists()

    def test_no_as_skill_on_reinstall_removes_the_copy(self, boost, wf_tap):
        boost("install", "reviewer")
        r = boost("install", "reviewer", "--force", "--no-as-skill")
        assert "removed its copy from the skill store" in _flat(r.out)
        assert not (paths.store_dir() / "reviewer").exists()
        assert not any(m["slot"] == "skill" for m in _rows())

    def test_as_skill_overrides_config_off_and_is_recorded(self, boost,
                                                           wf_tap):
        boost("config", "set", "workflows_as_skills", "false")
        boost("install", "reviewer", "--as-skill")
        assert _copy().is_file()
        assert lockfile.get_workflow("reviewer")["as_skill"] is True

    def test_config_off_writes_nothing(self, boost, wf_tap):
        boost("config", "set", "workflows_as_skills", "false")
        boost("install", "reviewer")
        assert not (paths.store_dir() / "reviewer").exists()

    def test_config_off_then_reinstall_retires_a_default_copy(self, boost,
                                                              wf_tap):
        boost("install", "reviewer")
        boost("config", "set", "workflows_as_skills", "false")
        boost("reinstall", "reviewer")
        assert not (paths.store_dir() / "reviewer").exists()

    def test_flags_are_mutually_exclusive(self, boost, wf_tap):
        boost("install", "reviewer", "--as-skill", "--no-as-skill", expect=2)

    def test_dry_run_predicts_the_copy(self, boost, wf_tap):
        r = boost("install", "reviewer", "--dry-run")
        assert "as a skill → ~/.agents/skills/reviewer" in _flat(r.out)
        assert not (paths.store_dir() / "reviewer").exists()
        r = boost("install", "reviewer", "--dry-run", "--no-as-skill")
        assert "as a skill" not in _flat(r.out)

    def test_a_command_with_a_description_gets_one(self, boost, wf_tap):
        _commit(wf_tap, "commands/ship.md",
                "---\nname: ship\ndescription: Ship it\nargument-hint: x\n"
                "---\nShip $ARGUMENTS\n", "cmd")
        boost("update")
        boost("install", "ship")
        assert (paths.store_dir() / "ship" / "SKILL.md").read_text(
            encoding="utf-8") == ("---\nname: ship\ndescription: Ship it\n"
                                  "---\n\nShip $ARGUMENTS\n")

    def test_no_description_means_no_copy_and_says_why(self, boost, wf_tap):
        _commit(wf_tap, "commands/bare.md", "---\nname: bare\n---\nGo\n",
                "cmd")
        boost("update")
        r = boost("install", "bare")
        assert "it has no description" in _flat(r.out)
        assert not (paths.store_dir() / "bare").exists()
        assert lockfile.get_workflow("bare") is not None

    def test_project_scope_writes_no_copy(self, boost, wf_tap, sandbox,
                                          monkeypatch, tmp_path):
        repo = tmp_path / "proj"
        (repo / ".git").mkdir(parents=True)
        monkeypatch.chdir(repo)
        r = boost("install", "reviewer", "--local", "--as-skill")
        assert "--as-skill is user scope only" in _flat(r.out)
        assert not (paths.store_dir() / "reviewer").exists()


class TestCollision:
    def test_an_installed_skill_wins(self, boost, wf_tap, tmp_path):
        src = tmp_path / "src" / "reviewer"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text(
            "---\nname: reviewer\ndescription: mine\n---\nmine\n",
            encoding="utf-8")
        boost("import", src)
        r = boost("install", "reviewer")
        assert "a skill named reviewer is already installed" in _flat(r.out)
        assert _copy().read_text(encoding="utf-8").endswith("mine\n")
        assert not any(m["slot"] == "skill" for m in _rows())
        # and the skill's own uninstall later is untouched by the workflow
        assert "reviewer" not in store.workflow_owned_store_names()

    def test_a_foreign_dir_is_left_alone(self, boost, wf_tap):
        mine = paths.store_dir() / "reviewer"
        mine.mkdir(parents=True)
        (mine / "SKILL.md").write_text("---\nname: reviewer\n---\nmine\n",
                                       encoding="utf-8")
        r = boost("install", "reviewer")
        assert "is already in the skill store and is not this workflow's" in _flat(r.out)
        assert (mine / "SKILL.md").read_text(encoding="utf-8").endswith("mine\n")
        assert not any(m["slot"] == "skill" for m in _rows())

    def test_installing_a_skill_over_the_copy_is_refused_then_forced(
            self, boost, wf_tap, tmp_path):
        boost("install", "reviewer")
        src = tmp_path / "src" / "reviewer"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text(
            "---\nname: reviewer\ndescription: mine\n---\nmine\n",
            encoding="utf-8")
        r = boost("import", src, expect=1)
        assert "as the skill copy of workflow reviewer" in _flat(r.err)
        assert _copy().read_text(encoding="utf-8") == WANT
        assert ("`boost install wf-tap:reviewer --path agents --force "
                "--no-as-skill` takes the copy out of the store") in _flat(r.err)
        # the hint is the command to run, so run exactly it
        boost("install", "wf-tap:reviewer", "--path", "agents", "--force",
              "--no-as-skill")
        boost("import", src)
        assert lockfile.get_skill("reviewer") is not None
        assert _copy().read_text(encoding="utf-8").endswith("mine\n")

    def test_a_forced_install_that_is_refused_leaves_the_copy_owned(
            self, boost, wf_tap, tmp_path):
        # --force gets past the copy, but a later refusal (here the capability
        # policy) must not leave it disowned: an unowned store dir is one
        # `boost sync` adopts and links beside the workflow.
        boost("install", "reviewer")
        p = policy.load()
        p["denied_capabilities"] = ["network"]
        policy.save(p)
        src = tmp_path / "src" / "reviewer"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text(
            "---\nname: reviewer\ndescription: mine\n"
            "capabilities: [network]\n---\nmine\n", encoding="utf-8")
        with pytest.raises(BoostError, match="network"):
            store.install_from_path(src, name="reviewer", force=True)
        assert any(m["slot"] == "skill" for m in _rows())
        assert "reviewer" in store.workflow_owned_store_names()
        assert _copy().read_text(encoding="utf-8") == WANT
        assert "recorded reviewer" not in _flat(boost("sync").out)

    def test_a_forced_skill_install_takes_the_dir_from_the_workflow(
            self, boost, wf_tap):
        boost("install", "reviewer")
        store._drop_skill_copy_row(
            store._refuse_unrecorded("reviewer", None, True))
        assert not any(m["slot"] == "skill" for m in _rows())
        # Disowned but still byte for byte the workflow's copy, the dir is
        # claimed back by the workflow's next install (`skill_copy_blocker`).
        r = boost("install", "reviewer", "--force")
        assert "is not this workflow's" not in _flat(r.out)
        assert any(m["slot"] == "skill" for m in _rows())
        # Once it holds anything else it is just a dir, and is left alone.
        store._drop_skill_copy_row("reviewer")
        _copy().write_text(WANT + "edited\n", encoding="utf-8")
        r = boost("install", "reviewer", "--force")
        assert "is not this workflow's" in _flat(r.out)
        shutil.rmtree(paths.store_dir() / "reviewer")
        boost("install", "reviewer", "--force")
        # and without force a tap install is refused, naming the retry
        with pytest.raises(BoostError) as err:
            store._refuse_unrecorded("reviewer", None, False,
                                     retry="`boost install reviewer --force`")
        assert "as the skill copy of workflow reviewer" in err.value.message
        assert err.value.hint == ("`boost install reviewer --force` replaces "
                                  "it; the workflow keeps its own files")


class TestUpdateUninstall:
    def test_update_refreshes_the_copy(self, boost, wf_tap):
        boost("install", "reviewer")
        _commit(wf_tap, "agents/reviewer.md",
                AGENT.replace("1.0.0", "1.1.0").replace("Read the diff.",
                                                        "Read it twice."),
                "bump")
        boost("update", "--yes")
        assert _copy().read_text(encoding="utf-8") == WANT.replace(
            "Read the diff.", "Read it twice.")
        assert _rows()[-1]["sha256"] == _sha(_copy().read_text(encoding="utf-8"))
        assert sum(m["slot"] == "skill" for m in _rows()) == 1

    def test_uninstall_removes_the_dir(self, boost, wf_tap):
        boost("install", "reviewer")
        boost("uninstall", "reviewer", "--yes")
        assert not (paths.store_dir() / "reviewer").exists()

    def test_uninstall_keeps_an_edited_copy(self, boost, wf_tap):
        boost("install", "reviewer")
        _copy().write_text(WANT + "my notes\n", encoding="utf-8")
        r = boost("uninstall", "reviewer", "--yes")
        assert "left ~/.agents/skills/reviewer/SKILL.md in place" in _flat(r.out)
        assert _copy().read_text(encoding="utf-8").endswith("my notes\n")
        assert lockfile.get_workflow("reviewer") is None
        assert not (paths.home() / ".claude" / "agents" / "reviewer.md").exists()

    def test_quarantine_and_release_round_trip(self, boost, wf_tap):
        boost("install", "reviewer")
        boost("quarantine", "reviewer")
        assert not (paths.store_dir() / "reviewer").exists()
        boost("quarantine", "--release", "reviewer")
        assert _copy().read_text(encoding="utf-8") == WANT


class TestNotAnUnrecordedSkill:
    def test_sync_and_doctor_leave_it_alone(self, boost, wf_tap):
        boost("install", "reviewer")
        assert "reviewer" in store.workflow_owned_store_names()
        assert "reviewer" not in store.unrecorded_store_dirs(lockfile.installed())
        plan = store.sync_plan()
        assert "reviewer" not in json.dumps(
            {k: v for k, v in plan.items()
             if k not in ("missing_materializations",)})
        assert plan["missing_materializations"] == []
        r = boost("sync", "--diff")
        assert "reviewer" not in _flat(r.out)
        boost("sync")
        assert not (paths.home() / ".claude" / "skills" / "reviewer").exists()
        assert lockfile.get_skill("reviewer") is None
        r = boost("doctor", expect=None)
        assert "reviewer" not in _flat(r.out)
        assert "not reachable as skill" not in _flat(r.out)

    def test_sync_rewrites_a_deleted_copy(self, boost, wf_tap):
        boost("install", "reviewer")
        _copy().unlink()
        r = boost("doctor", expect=None)
        assert "workflow reviewer missing its skill copy at" in _flat(r.out)
        boost("sync")
        assert _copy().read_text(encoding="utf-8") == WANT


class TestHealBackfill:
    def _strip(self):
        """An entry installed before the copy existed: no row, no file."""
        entry = lockfile.get_workflow("reviewer")
        entry["materializations"] = [m for m in entry["materializations"]
                                     if m["slot"] != "skill"]
        lockfile.set_workflow("reviewer", entry)
        shutil.rmtree(paths.store_dir() / "reviewer")

    def test_doctor_and_heal_name_it_and_as_skill_writes_it(self, boost,
                                                            wf_tap):
        boost("install", "reviewer")
        self._strip()
        assert store.workflows_without_skill_copy() == ["reviewer"]
        r = boost("doctor", expect=None)
        assert ("1 workflow not reachable as skill (reviewer) — `boost heal "
                "--as-skill` puts it in the skill store") in _flat(r.out)
        r = boost("heal")
        assert "1 workflow not reachable as skill" in _flat(r.out)
        assert not (paths.store_dir() / "reviewer").exists()

        r = boost("heal", "--as-skill", "--dry-run")
        assert ("would write workflow reviewer's skill copy to "
                "~/.agents/skills/reviewer") in _flat(r.out)
        assert not (paths.store_dir() / "reviewer").exists()

        r = boost("heal", "--as-skill")
        assert "wrote workflow reviewer's skill copy" in _flat(r.out)
        assert _copy().read_text(encoding="utf-8") == WANT
        assert _rows()[-1]["slot"] == "skill"
        assert store.workflows_without_skill_copy() == []

    def test_backfill_reads_the_installed_text_not_a_moved_tap(self, boost,
                                                               wf_tap):
        boost("install", "reviewer")
        self._strip()
        # The tap's clone moves on; the installed agent file is the old text.
        src = registry.get("wf-tap").path / "agents" / "reviewer.md"
        src.write_text(AGENT.replace("Read the diff.", "Something new."),
                       encoding="utf-8")
        boost("heal", "--as-skill")
        assert _copy().read_text(encoding="utf-8") == WANT

    def test_no_installed_text_left_means_no_backfill(self, boost, wf_tap):
        boost("install", "reviewer")
        self._strip()
        (registry.get("wf-tap").path / "agents" / "reviewer.md").write_text(
            "changed\n", encoding="utf-8")
        for m in _rows():
            Path(m["path"]).write_text("edited\n", encoding="utf-8")
        assert store.workflows_without_skill_copy() == []

    def test_an_explicit_no_is_not_backfilled(self, boost, wf_tap):
        boost("install", "reviewer", "--no-as-skill")
        assert store.workflows_without_skill_copy() == []
        boost("heal", "--as-skill")
        assert not (paths.store_dir() / "reviewer").exists()

    def test_config_off_is_said(self, boost, wf_tap):
        boost("install", "reviewer")
        self._strip()
        boost("config", "set", "workflows_as_skills", "false")
        r = boost("heal", "--as-skill")
        assert "workflows_as_skills is off" in _flat(r.out)
        assert not (paths.store_dir() / "reviewer").exists()


MINE = "---\nname: reviewer\ndescription: mine\n---\nMY SKILL\n"


class TestReviewFindings:
    """Paths where the copy used to outlive, or overwrite, what owns the dir."""

    def _skill_src(self, tmp_path):
        src = tmp_path / "src" / "reviewer"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text(MINE, encoding="utf-8")
        return src

    def test_release_never_overwrites_a_skill_installed_meanwhile(
            self, boost, wf_tap, tmp_path):
        boost("install", "reviewer")
        boost("quarantine", "reviewer")
        # A forced skill install takes the dir from the quarantined workflow:
        # it must forget the stashed copy too, not only the live row.
        store._drop_skill_copy_row(
            store._refuse_unrecorded("reviewer", None, True))
        entry = lockfile.get_workflow("reviewer")
        assert not any(m["slot"] == "skill"
                       for m in entry.get("quarantine_stash") or ())
        boost("import", self._skill_src(tmp_path))
        boost("quarantine", "--release", "reviewer")
        assert _copy().read_text(encoding="utf-8") == MINE
        assert lockfile.get_skill("reviewer") is not None

    def test_release_leaves_a_dir_made_during_quarantine(self, boost, wf_tap):
        boost("install", "reviewer")
        boost("quarantine", "reviewer")
        _copy().parent.mkdir(parents=True)
        _copy().write_text(MINE, encoding="utf-8")
        r = boost("quarantine", "--release", "reviewer")
        assert ("not restored as a skill: ~/.agents/skills/reviewer now holds "
                "something else — left alone") in _flat(r.out)
        assert _copy().read_text(encoding="utf-8") == MINE
        # the workflow no longer claims it, and its own files came back
        assert not any(m["slot"] == "skill" for m in _rows())
        assert "reviewer" not in store.workflow_owned_store_names()
        assert (paths.home() / ".claude" / "agents" / "reviewer.md").is_file()

    def test_release_rewrites_the_copy_when_the_lock_records_a_skill(
            self, boost, wf_tap):
        boost("install", "reviewer")
        boost("quarantine", "reviewer")
        # Dir gone but a skill entry by that name: still not ours to write.
        lockfile.set_skill("reviewer", {"tap": "local", "version": "1"})
        boost("quarantine", "--release", "reviewer")
        assert not _copy().exists()
        assert not any(m["slot"] == "skill" for m in _rows())

    def test_a_kept_edited_copy_stays_owned_so_sync_does_not_adopt_it(
            self, boost, wf_tap):
        boost("install", "reviewer")
        _copy().write_text(WANT + "my notes\n", encoding="utf-8")
        r = boost("install", "reviewer", "--force", "--no-as-skill")
        assert "left ~/.agents/skills/reviewer/SKILL.md in place" in _flat(r.out)
        assert "reviewer" in store.workflow_owned_store_names()
        boost("sync", "--yes")
        assert lockfile.get_skill("reviewer") is None
        assert not os.path.lexists(paths.home() / ".claude" / "skills"
                                   / "reviewer")
        assert _copy().read_text(encoding="utf-8").endswith("my notes\n")
        # nor does verify, heal or doctor put boost's text back over it
        boost("verify", expect=None)
        boost("heal", expect=None)
        boost("doctor", expect=None)
        assert _copy().read_text(encoding="utf-8").endswith("my notes\n")
        assert lockfile.get_skill("reviewer") is None
        # once it is back to what boost wrote, the next run retires it
        _copy().write_text(WANT, encoding="utf-8")
        boost("reinstall", "reviewer")
        assert not (paths.store_dir() / "reviewer").exists()
        assert not any(m["slot"] == "skill" for m in _rows())

    def test_a_kept_copy_without_description_stays_owned(self, boost,
                                                         wf_tap):
        boost("install", "reviewer")
        _copy().write_text(WANT + "my notes\n", encoding="utf-8")
        _commit(wf_tap, "agents/reviewer.md",
                AGENT.replace("description: Reviews a diff for bugs\n",
                              "").replace("1.0.0", "1.1.0"),
                "drop description")
        r = boost("update", "--yes")
        assert "left the edited ~/.agents/skills/reviewer/SKILL.md in place" \
            in _flat(r.out)
        assert "reviewer" in store.workflow_owned_store_names()
        assert _copy().read_text(encoding="utf-8").endswith("my notes\n")

    def test_mcp_install_reply_names_the_copy(self, boost, wf_tap):
        from boost_cli.commands import configuration
        reply = configuration._tool_install({"name": "reviewer"})
        text = reply[0] if isinstance(reply, tuple) else reply
        assert "as a skill: %s" % _copy().parent in text

    def test_mcp_install_reply_says_why_there_is_no_copy(self, boost, wf_tap):
        mine = paths.store_dir() / "reviewer"
        mine.mkdir(parents=True)
        (mine / "SKILL.md").write_text(MINE, encoding="utf-8")
        from boost_cli.commands import configuration
        reply = configuration._tool_install({"name": "reviewer"})
        text = reply[0] if isinstance(reply, tuple) else reply
        assert "is not this workflow's" in _flat(text)

    def test_reinstall_says_the_copy_was_retired(self, boost, wf_tap):
        boost("install", "reviewer")
        boost("config", "set", "workflows_as_skills", "false")
        r = boost("reinstall", "reviewer")
        assert "removed its copy from the skill store" in _flat(r.out)
        assert not (paths.store_dir() / "reviewer").exists()

    def test_install_says_it_once(self, boost, wf_tap):
        boost("install", "reviewer")
        r = boost("install", "reviewer", "--force", "--no-as-skill")
        assert _flat(r.out).count("removed its copy from the skill store") == 1


class TestLostLock:
    """With the lock file gone, the copy is told apart by the workflow file
    beside it. `heal` used to re-record it as a local skill, the next run
    linked it into every agent beside the workflow's own file, and `doctor`
    then called the machine healthy."""

    def _lose_lock(self, boost):
        boost("install", "reviewer")
        boost("install", "brainstorming")
        paths.lockfile_path().unlink()

    def test_heal_does_not_adopt_it_and_says_so(self, boost, wf_tap):
        self._lose_lock(boost)
        assert store.workflow_copy_evidence("reviewer") == (
            paths.home() / ".claude" / "agents" / "reviewer.md")
        assert "reviewer" not in store.unrecorded_store_dirs({})
        r = boost("heal", expect=1)
        flat = _flat(r.out + r.err)
        assert "re-recorded brainstorming from wf-tap" in flat
        assert "reviewer as a local skill" not in flat
        assert ("~/.agents/skills/reviewer is the skill copy of the workflow "
                "at ~/.claude/agents/reviewer.md, which the lock does not "
                "record — `boost install reviewer` re-records both") in flat
        assert lockfile.get_skill("reviewer") is None
        assert lockfile.get_skill("brainstorming") is not None
        # A second pass changes nothing: still not adopted, never linked.
        boost("heal", expect=1)
        assert lockfile.get_skill("reviewer") is None
        assert not os.path.lexists(paths.home() / ".claude" / "skills"
                                   / "reviewer")
        assert _copy().read_text(encoding="utf-8") == WANT

    def test_doctor_names_it_and_does_not_prescribe_sync(self, boost, wf_tap):
        self._lose_lock(boost)
        r = boost("doctor", expect=1)
        flat = _flat(r.out)
        assert "1 store dir unrecorded" in flat          # brainstorming only
        assert "`boost install reviewer` re-records both" in flat
        boost("heal", expect=1)
        r = boost("doctor", expect=1)
        flat = _flat(r.out)
        assert "`boost install reviewer` re-records both" in flat
        assert "added outside boost" not in flat
        assert "● healthy" not in flat
        assert "1 issue needs attention" in flat
        plan = store.sync_plan()
        assert plan["workflow_copies"] == [
            ("reviewer", str(paths.home() / ".claude" / "agents"
                             / "reviewer.md"))]
        assert plan["adoptable_store"] == []
        assert store.plan_issues(plan) == 1

    def test_the_named_install_reclaims_the_copy_and_converges(self, boost,
                                                               wf_tap):
        self._lose_lock(boost)
        boost("heal", expect=1)
        r = boost("install", "reviewer")
        assert "not this workflow's" not in _flat(r.out)
        assert _rows()[-1] == {"agent": None, "slot": "skill",
                               "path": str(_copy()), "sha256": _sha(WANT)}
        assert store.sync_plan()["workflow_copies"] == []
        boost("heal")
        boost("doctor")

    def test_a_skill_named_like_the_workflow_is_still_adopted(self, boost,
                                                              wf_tap):
        """Evidence is content, not name: the user's own skill by the same
        name, with other text, is a skill to record."""
        self._lose_lock(boost)
        _copy().write_text(WANT + "\nMine now.\n", encoding="utf-8")
        assert store.workflow_copy_evidence("reviewer") is None
        assert "reviewer" in store.unrecorded_store_dirs({})
        assert store.sync_plan()["workflow_copies"] == []

    def test_recover_refuses_it_when_asked_directly(self, boost, wf_tap):
        self._lose_lock(boost)
        line = store.recover_unrecorded("reviewer")
        assert line == ("reviewer was not recorded: it is the skill copy of "
                        "the workflow at ~/.claude/agents/reviewer.md — "
                        "`boost install reviewer` re-records both")
        assert store.is_unrepaired(line)
        assert store.adopt_unrecorded("reviewer") == [line]
        assert lockfile.get_skill("reviewer") is None


class TestBlockerClaimsAnIdenticalCopy:
    def test_only_an_exact_lone_skill_md_is_claimed(self, sandbox):
        d = paths.store_dir() / "wf"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("T", encoding="utf-8")
        assert store.skill_copy_blocker("wf", None, "T") is None
        assert store.skill_copy_blocker("wf", None, "U") is not None
        assert store.skill_copy_blocker("wf", None) is not None
        (d / "extra.txt").write_text("x", encoding="utf-8")
        assert store.skill_copy_blocker("wf", None, "T") is not None


class TestASkillAndAWorkflowShareAName:
    """One tap ships both ``skills/reviewer/SKILL.md`` and
    ``agents/reviewer.md``. Bare ``reviewer`` names two items, so every
    command a refusal hands back must be the qualified one, and running it
    verbatim must work."""

    SKILL = ("---\nname: reviewer\ndescription: the skill one\n---\n\n"
             "skill body\n")

    @pytest.fixture
    def both(self, boost, wf_tap):
        _commit(wf_tap, "skills/reviewer/SKILL.md", self.SKILL, "add skill")
        boost("update")
        return wf_tap

    def test_the_refusal_hint_is_a_command_that_runs(self, boost, both):
        boost("install", "wf-tap:reviewer", "--path", "agents")
        assert _copy().read_text(encoding="utf-8") == WANT
        r = boost("install", "wf-tap:reviewer", "--path", "skills/reviewer",
                  expect=1)
        assert ("hint: `boost install wf-tap:reviewer --path skills/reviewer "
                "--force` replaces it; the workflow keeps its own files"
                in _flat(r.err))
        # bare, the name is ambiguous — which is why the hint is qualified
        boost("install", "reviewer", "--force", expect=1)
        r = boost("install", "wf-tap:reviewer", "--path", "skills/reviewer",
                  "--force")
        assert r.rc == 0
        assert _copy().read_text(encoding="utf-8") == self.SKILL
        assert lockfile.get_skill("reviewer")["tap"] == "wf-tap"
        # the workflow lost only its copy; its agent file is untouched
        assert not any(m["slot"] == "skill" for m in _rows())
        assert (paths.home() / ".claude" / "agents" / "reviewer.md").read_text(
            encoding="utf-8") == AGENT
