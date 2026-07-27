"""Unit tests: core.workflows — pure workflow-materialization logic.

workflows.py has no side effects: it decides which slot a workflow belongs in
(command vs subagent) and where it lands per agent. The assertions pin the slot
detection and the per-agent target path so a workflow can't drop into the wrong
directory.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from boost_cli.core import workflows
from boost_cli.errors import BoostError


class TestDetectSlot:
    def test_commands_dir_is_a_command(self):
        assert workflows.detect_slot("commands/ship.md") == workflows.SLOT_COMMANDS

    def test_agents_dir_is_a_subagent(self):
        assert workflows.detect_slot("agents/reviewer.md") == workflows.SLOT_AGENTS

    def test_subagents_dir_is_a_subagent(self):
        assert workflows.detect_slot("pack/subagents/x.md") == workflows.SLOT_AGENTS

    def test_workflows_dir_is_a_command(self):
        assert workflows.detect_slot("workflows/deploy.md") == workflows.SLOT_COMMANDS

    def test_bare_file_defaults_to_command(self):
        assert workflows.detect_slot("loose.md") == workflows.SLOT_COMMANDS

    def test_detection_is_case_insensitive(self):
        assert workflows.detect_slot("Agents/R.md") == workflows.SLOT_AGENTS

    def test_nested_agents_dir_detected(self):
        assert workflows.detect_slot("a/b/agents/c.md") == workflows.SLOT_AGENTS


class TestWorkflowTarget:
    def test_command_lands_in_commands_dir_at_agent_root(self):
        p = workflows.workflow_target(Path("/h/.claude/skills"), "commands", "ship")
        assert p == Path("/h/.claude/commands/ship.md")

    def test_subagent_lands_in_agents_dir(self):
        p = workflows.workflow_target(Path("/h/.claude/skills"), "agents", "rev")
        assert p == Path("/h/.claude/agents/rev.md")

    def test_uses_configured_skills_dir_parent(self):
        p = workflows.workflow_target(Path("/opt/cursor/skills"), "commands", "x")
        assert p == Path("/opt/cursor/commands/x.md")

    def test_project_scope_lands_under_repo_dotdir(self):
        p = workflows.workflow_target(Path("/h/.claude/skills"), "commands",
                                      "ship", base=Path("/repo"))
        assert p == Path("/repo/.claude/commands/ship.md")

    def test_project_scope_subagent_under_repo(self):
        p = workflows.workflow_target(Path("/h/.claude/skills"), "agents",
                                      "rev", base=Path("/repo"))
        assert p == Path("/repo/.claude/agents/rev.md")


class TestWorkflowNameTraversal:
    """Same tap-controlled-name exposure as rules: workflow_target joins the
    name straight onto the agent's commands/ or agents/ dir."""

    EVIL = "../../../../.ssh/authorized_keys"

    def test_user_scope_refuses_traversal(self):
        with pytest.raises(BoostError, match="invalid workflow name"):
            workflows.workflow_target(Path("/home/v/.claude/skills"), "commands", self.EVIL)

    def test_project_scope_refuses_traversal(self):
        with pytest.raises(BoostError, match="invalid workflow name"):
            workflows.workflow_target(Path("/x/.claude/skills"), "agents", self.EVIL,
                                      base=Path("/home/v/myrepo"))

    @pytest.mark.parametrize("name", ["..", ".", "a/b", "with space", ""])
    def test_refuses_other_non_components(self, name):
        with pytest.raises(BoostError):
            workflows.workflow_target(Path("/home/v/.claude/skills"), "commands", name)

    def test_ordinary_name_still_lands_in_the_slot(self):
        p = workflows.workflow_target(Path("/home/v/.claude/skills"), "commands",
                                      "my_cmd-1.2")
        assert p.parent.name == "commands"
        assert p.name == "my_cmd-1.2.md"
        assert Path(p).resolve().is_relative_to(Path("/home/v/.claude").resolve())
