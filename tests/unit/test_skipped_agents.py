# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: an agent a rule or workflow skips by its own config is named.

An enabled agent that :func:`agents.materializing_agents` or
:func:`agents.workflow_agents` leaves out (``skills_only``, ``workflows:
false``) never gets a lock row, and every reporter walked the rows: install
listed only the agents it wrote and doctor called the item fully
materialized. A Claude Code profile added as ``skills_only`` (copied from the
antigravity row) got no subagent and no rule, and nothing said so.
"""
from __future__ import annotations

import os

import pytest

from boost_cli.commands import pkg
from boost_cli.core import agents, catalog, config, lockfile, paths, registry, store


@pytest.fixture()
def tap(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    return t


def _rule(tap, name="house-rules", rel="rules/house.mdc"):
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("---\nname: House\n---\n\nWrite tests first.\n",
                   encoding="utf-8")
    return {"name": name, "kind": "rule", "tap": tap.name, "version": "1.0.0",
            "rel_dir": str(src.parent.relative_to(tap.path)), "skill_md": rel,
            "description": "house rules", "curated": False, "meta": {}}


def _workflow(tap, name="reviewer", rel="agents/reviewer.md"):
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("---\nname: reviewer\ndescription: reviews\n---\n\nReview.\n",
                   encoding="utf-8")
    return {"name": name, "kind": "workflow", "tap": tap.name,
            "version": "1.0.0",
            "rel_dir": str(src.parent.relative_to(tap.path)), "skill_md": rel,
            "description": "reviews", "curated": False, "meta": {}}


def _add_agent(name, **flags):
    cfg = config.load()
    cfg["agents"][name] = {"dir": "~/.%s/skills" % name, **flags}
    config.save(cfg)


def _set(agent, **flags):
    cfg = config.load()
    cfg["agents"][agent].update(flags)
    config.save(cfg)


class TestSkippedAgents:
    def test_a_workflow_names_each_linking_agent_its_set_leaves_out(self, tap):
        store.install(_workflow(tap), as_skill=False)
        # config order; gemini and codex link nothing, so they are not asked
        assert store.skipped_agents(
            "workflow", lockfile.get_workflow("reviewer")) == [
            ("windsurf", agents.REASON_NO_COMMAND_FORMAT),
            ("antigravity", agents.REASON_SKILLS_ONLY)]

    def test_a_rule_names_only_the_skills_only_agent(self, tap):
        store.install(_rule(tap))
        assert store.skipped_agents(
            "rule", lockfile.get_rule("house-rules")) == [
            ("antigravity", agents.REASON_SKILLS_ONLY)]

    def test_a_config_added_skills_only_profile_is_named(self, tap):
        _add_agent("claude-personal", skills_only=True)
        store.install(_rule(tap))
        store.install(_workflow(tap), as_skill=False)
        assert ("claude-personal", agents.REASON_SKILLS_ONLY) in \
            store.skipped_agents("rule", lockfile.get_rule("house-rules"))
        assert ("claude-personal", agents.REASON_SKILLS_ONLY) in \
            store.skipped_agents("workflow", lockfile.get_workflow("reviewer"))

    def test_a_skill_skips_no_linking_agent(self, tap):
        assert store.skipped_agents("skill", {"base": None,
                                              "only_agents": []}) == []

    def test_an_agent_that_has_a_row_is_left_to_its_row(self, tap):
        """A row already names the agent, and `unwritten_materializations`
        words it -- naming it here too would say it twice."""
        store.install(_rule(tap))
        locked = lockfile.get_rule("house-rules")
        locked["materializations"].append(
            {"agent": "antigravity", "mode": "file", "path": "/nope"})
        assert store.skipped_agents("rule", locked) == []

    @pytest.mark.parametrize("key", ["foreign", "declined"])
    def test_a_foreign_or_declined_row_names_the_agent_too(self, tap, key):
        store.install(_workflow(tap), as_skill=False)
        locked = lockfile.get_workflow("reviewer")
        locked[key] = [{"agent": "windsurf", "slot": "agents",
                        "path": "/nope", "reason": "r"}]
        assert store.skipped_agents("workflow", locked) == [
            ("antigravity", agents.REASON_SKILLS_ONLY)]

    def test_a_declared_narrowing_is_never_widened(self, tap):
        store.install(_workflow(tap), only_agents=["cursor"], as_skill=False)
        assert store.skipped_agents(
            "workflow", lockfile.get_workflow("reviewer")) == []

    def test_a_declared_agent_it_skips_is_still_named(self, tap):
        entry = {"base": None, "only_agents": ["cursor", "windsurf"],
                 "materializations": []}
        assert store.skipped_agents("workflow", entry) == [
            ("windsurf", agents.REASON_NO_COMMAND_FORMAT)]

    def test_an_empty_declared_scope_reads_as_every_agent(self, tap):
        entry = {"base": None, "only_agents": [], "materializations": []}
        assert [a for a, _ in store.skipped_agents("rule", entry)] == [
            "antigravity"]

    def test_an_entry_with_no_rows_is_still_judged(self, tap):
        """Every agent skipped is exactly the case with no rows at all."""
        assert store.skipped_agents("rule", {"base": None}) == [
            ("antigravity", agents.REASON_SKILLS_ONLY)]

    def test_a_disabled_agent_is_not_named(self, tap):
        _set("antigravity", enabled=False)
        assert store.skipped_agents("rule", {"base": None}) == []

    def test_a_quarantined_entry_is_not_judged(self, tap):
        assert store.skipped_agents(
            "rule", {"base": None, "quarantined": True}) == []

    def test_a_stranded_entry_is_not_judged(self, tap):
        gone = str(paths.home() / "no-such-repo")
        # a workflow: windsurf has project scope and takes no workflow, so
        # only the stranded check keeps it out
        assert store.skipped_agents(
            "workflow", {"base": gone, "scope": "project"}) == []

    def test_project_scope_asks_the_project_agents(self, tap, tmp_path):
        """antigravity has no project scope, so a project item never reaches
        it whatever it is; windsurf does, and takes no workflow there.

        codex is named here and not at user scope: a project skill is a real
        dir in `<repo>/.codex/skills`, and a project workflow has no skill
        copy (that lives in the user store), so in a repo codex gets nothing.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        entry = {"base": str(repo), "scope": "project",
                 "materializations": []}
        assert store.skipped_agents("workflow", entry) == [
            ("windsurf", agents.REASON_NO_COMMAND_FORMAT),
            ("codex", agents.REASON_NO_COMMAND_FORMAT)]
        assert store.skipped_agents("rule", entry) == []

    def test_install_carries_the_skips_on_its_result(self, tap):
        _add_agent("claude-personal", skills_only=True)
        res = store.install(_rule(tap))
        assert res.skipped_agents == [
            ("antigravity", agents.REASON_SKILLS_ONLY),
            ("claude-personal", agents.REASON_SKILLS_ONLY)]
        res = store.install(_workflow(tap), as_skill=False)
        assert res.skipped_agents == [
            ("windsurf", agents.REASON_NO_COMMAND_FORMAT),
            ("antigravity", agents.REASON_SKILLS_ONLY),
            ("claude-personal", agents.REASON_SKILLS_ONLY)]

    def test_a_skill_install_carries_none(self, tap):
        res = store.install(catalog.resolve_one("brainstorming"))
        assert res.skipped_agents == []


class TestSkippedAgentItems:
    def test_each_agent_once_with_every_item_it_skips(self, tap):
        _add_agent("claude-personal", skills_only=True)
        store.install(_rule(tap))
        store.install(_rule(tap, name="api-rules", rel="rules/api.mdc"))
        store.install(_workflow(tap), as_skill=False)
        assert store.skipped_agent_items() == [
            ("antigravity", agents.REASON_SKILLS_ONLY,
             ["rule api-rules", "rule house-rules", "workflow reviewer"]),
            ("claude-personal", agents.REASON_SKILLS_ONLY,
             ["rule api-rules", "rule house-rules", "workflow reviewer"]),
            ("windsurf", agents.REASON_NO_COMMAND_FORMAT,
             ["workflow reviewer"])]

    def test_nothing_installed_names_nothing(self, tap):
        assert store.skipped_agent_items() == []


class TestSkipLine:
    def test_it_names_the_reason_and_the_key_that_decides_it(self, sandbox):
        _add_agent("claude-personal", skills_only=True)
        assert agents.skip_line("claude-personal",
                                agents.REASON_SKILLS_ONLY) == (
            "claude-personal: takes skills only "
            "(agents.claude-personal.skills_only) — not written")
        _add_agent("my-tool", workflows=False)
        assert agents.skip_line("my-tool",
                                agents.REASON_NO_COMMAND_FORMAT) == (
            "my-tool: has no slash-command format "
            "(agents.my-tool.workflows) — not written")

    def test_a_format_boost_withdrew_names_no_key(self, sandbox):
        """antigravity's ``skills_only`` and windsurf's ``workflows: false``
        are boost's own (``config.DEFAULTS`` says why at each), and flipping
        either writes a file the agent never loads: the key is not offered."""
        assert agents.skip_line("antigravity", agents.REASON_SKILLS_ONLY) == (
            "antigravity: takes skills only — not written")
        assert agents.skip_line("windsurf",
                                agents.REASON_NO_COMMAND_FORMAT) == (
            "windsurf: has no slash-command format — not written")

    def test_a_built_in_row_the_user_withdrew_keeps_its_key(self, sandbox):
        """The setting is the user's when it is not the row's default."""
        _set("claude-code", skills_only=True)
        _set("cursor", workflows=False)
        assert agents.skip_line("claude-code", agents.REASON_SKILLS_ONLY) == (
            "claude-code: takes skills only (agents.claude-code.skills_only) "
            "— not written")
        assert agents.skip_line("cursor",
                                agents.REASON_NO_COMMAND_FORMAT) == (
            "cursor: has no slash-command format (agents.cursor.workflows) "
            "— not written")

    def test_an_unconfigured_agent_keeps_its_key(self, sandbox):
        assert agents.skip_line("ghost", agents.REASON_SKILLS_ONLY) == (
            "ghost: takes skills only (agents.ghost.skills_only) — not written")

    def test_every_config_reason_names_its_key(self, sandbox):
        assert agents.skip_line("cursor", agents.REASON_DISABLED) == (
            "cursor: is disabled (agents.cursor.enabled) — not written")
        assert agents.skip_line("cursor",
                                agents.REASON_NO_PROJECT_SCOPE) == (
            "cursor: has no project scope (agents.cursor.project_scope) "
            "— not written")
        # at its built-in value, but a reason the user may reverse
        assert agents.skip_line("antigravity",
                                agents.REASON_NO_PROJECT_SCOPE) == (
            "antigravity: has no project scope "
            "(agents.antigravity.project_scope) — not written")

    def test_a_reason_no_flag_decides_names_no_key(self, sandbox):
        assert agents.skip_line("x", agents.REASON_UNKNOWN) == (
            "x: is not written — not written")

    def test_the_report_prints_one_line_per_skipped_agent(self, tap, capsys):
        _add_agent("claude-personal", skills_only=True)
        res = store.install(_rule(tap))
        pkg._report_result(res)
        flat = " ".join(capsys.readouterr().out.split())
        assert ("claude-personal: takes skills only "
                "(agents.claude-personal.skills_only) — not written") in flat
        assert "antigravity: takes skills only — not written" in flat


def _profile(name="claude-personal", marker=True, **flags):
    _add_agent(name, **{"skills_only": True, **flags})
    if marker:
        (paths.home() / (".%s" % name)).mkdir(parents=True, exist_ok=True)
        (paths.home() / (".%s" % name) / ".claude.json").write_text(
            "{}\n", encoding="utf-8")


def _unstattable_marker(monkeypatch):
    """``os.stat`` of any ``.claude.json`` fails as it does under a dir the
    user cannot search."""
    real = os.stat

    def stat(path, *args, **kwargs):
        if os.fspath(path).endswith(".claude.json"):
            raise PermissionError(13, "Permission denied", os.fspath(path))
        return real(path, *args, **kwargs)
    monkeypatch.setattr(os, "stat", stat)


class TestClaudeProfileRows:
    def test_a_skills_only_row_beside_a_claude_json_is_named(self, sandbox):
        _profile()
        assert agents.claude_profile_rows() == ["claude-personal"]

    def test_a_row_with_no_claude_json_is_not(self, sandbox):
        _profile(marker=False)
        assert agents.claude_profile_rows() == []

    def test_a_directory_named_claude_json_is_not_the_marker(self, sandbox):
        _profile(marker=False)
        (paths.home() / ".claude-personal" / ".claude.json").mkdir(
            parents=True)
        assert agents.claude_profile_rows() == []

    def test_a_row_that_already_takes_rules_is_not(self, sandbox):
        _profile(skills_only=False)
        assert agents.claude_profile_rows() == []

    def test_a_disabled_row_is_not(self, sandbox):
        _profile(enabled=False)
        assert agents.claude_profile_rows() == []

    def test_the_note_offers_the_flag_and_sync(self, sandbox):
        _profile(project_scope=False)
        assert agents.claude_profile_note("claude-personal") == (
            "agents.claude-personal looks like a Claude Code profile — "
            "`boost config set agents.claude-personal.skills_only false` "
            "then `boost sync` gives it agents/, commands/ and rules/")

    def test_a_profile_with_project_scope_is_told_to_drop_it(self, sandbox):
        """A config-added row takes project scope unless it says otherwise,
        and in a repo Claude Code reads `.claude/` under any profile: a
        project install into `<repo>/.claude-personal/` is never loaded."""
        _profile()
        assert agents.claude_profile_note("claude-personal") == (
            "agents.claude-personal looks like a Claude Code profile — "
            "`boost config set agents.claude-personal.skills_only false` "
            "then `boost sync` gives it agents/, commands/ and rules/; run "
            "`boost config set agents.claude-personal.project_scope false` "
            "first — in a repo Claude Code reads `.claude/` under any "
            "profile, never `.claude-personal/`")

    def test_a_marker_it_cannot_stat_is_not_a_profile(self, sandbox,
                                                      monkeypatch):
        """Under a dir that is not searchable, ``Path.is_file`` raises
        PermissionError on Python 3.12 and 3.13 rather than answering False.
        Faked at ``os.stat`` -- a mode-000 dir stops nothing for root, which
        is who the mutation runner is -- with the marker really there, so
        only the swallowed error can make the answer empty."""
        _profile()
        _unstattable_marker(monkeypatch)
        assert agents.claude_profile_rows() == []

    def test_doctor_finishes_its_report_over_it(self, sandbox, monkeypatch,
                                                capsys):
        """Doctor asks this on every run: a raise there was exit 70 and a
        crash report in place of the verdict."""
        from boost_cli.commands import quality
        _profile()
        _unstattable_marker(monkeypatch)
        assert quality.cmd_doctor([]) in (0, 1)
        out = capsys.readouterr().out
        assert "looks like a Claude Code profile" not in out
        assert ("● healthy" in out or "attention — see the suggestions "
                "above" in out or "ready to set up" in out), out

    def test_a_built_in_row_is_never_called_a_profile(self, sandbox):
        """antigravity is skills_only by design; a `.claude.json` beside it
        does not make it Claude Code."""
        (paths.home() / ".gemini" / "antigravity-cli").mkdir(parents=True)
        (paths.home() / ".gemini" / "antigravity-cli" / ".claude.json"
         ).write_text("{}\n", encoding="utf-8")
        assert agents.claude_profile_rows() == []
