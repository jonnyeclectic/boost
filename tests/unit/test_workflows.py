"""Unit tests: core.workflows — pure workflow-materialization logic.

workflows.py has no side effects: it decides which slot a workflow belongs in
(command vs subagent), where it lands per agent, and what text goes in the file.
The assertions pin the slot detection, the per-agent target path and extension,
and the Gemini TOML rendering so a workflow can't drop into the wrong directory
or land in a format its agent will silently never discover.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from boost_cli.core import workflows
from boost_cli.errors import BoostError


def _toml_loads(text: str) -> dict:
    """Parse ``text`` as TOML. tomllib is stdlib from 3.11 and the floor is
    3.12, so it is always importable — no skip guard needed any more."""
    import tomllib
    return tomllib.loads(text)


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


class TestTargetExt:
    """Only ONE (agent, slot) pair is special. The extension has to agree with
    :func:`workflows.render`, so both halves of that pair are pinned here."""

    def test_gemini_commands_are_toml(self):
        assert workflows.target_ext("gemini", "commands") == ".toml"

    def test_gemini_subagents_stay_markdown(self):
        # a Gemini subagent is Markdown+YAML like Claude's — only the slash
        # command format diverges.
        assert workflows.target_ext("gemini", "agents") == ".md"

    def test_claude_commands_stay_markdown(self):
        assert workflows.target_ext("claude-code", "commands") == ".md"

    def test_unknown_agent_falls_back_to_markdown(self):
        assert workflows.target_ext("aider", "commands") == ".md"
        assert workflows.target_ext("cursor", "commands") == ".md"

    def test_none_agent_keeps_the_historical_markdown_default(self):
        # the pre-Gemini callers pass no agent at all
        assert workflows.target_ext(None, "commands") == ".md"
        assert workflows.target_ext(None, "agents") == ".md"

    def test_unknown_slot_is_markdown_even_for_gemini(self):
        assert workflows.target_ext("gemini", "rules") == ".md"

    def test_constants(self):
        assert sorted(workflows.TOML_COMMAND_AGENTS) == ["gemini"]
        assert workflows.TOML_EXT == ".toml"
        assert workflows.DEFAULT_EXT == ".md"


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

    # --- gemini: commands are .toml, subagents stay .md ---
    def test_gemini_command_is_toml_in_user_scope(self):
        p = workflows.workflow_target(Path("/h/.gemini/skills"), "commands",
                                      "ship", agent="gemini")
        assert p == Path("/h/.gemini/commands/ship.toml")

    def test_gemini_subagent_is_markdown_in_user_scope(self):
        p = workflows.workflow_target(Path("/h/.gemini/skills"), "agents",
                                      "rev", agent="gemini")
        assert p == Path("/h/.gemini/agents/rev.md")

    def test_gemini_command_is_toml_in_project_scope(self):
        p = workflows.workflow_target(Path("/h/.gemini/skills"), "commands",
                                      "ship", base=Path("/repo"), agent="gemini")
        assert p == Path("/repo/.gemini/commands/ship.toml")

    def test_gemini_subagent_is_markdown_in_project_scope(self):
        p = workflows.workflow_target(Path("/h/.gemini/skills"), "agents",
                                      "rev", base=Path("/repo"), agent="gemini")
        assert p == Path("/repo/.gemini/agents/rev.md")

    def test_named_agent_does_not_change_a_markdown_agents_path(self):
        p = workflows.workflow_target(Path("/h/.claude/skills"), "commands",
                                      "ship", agent="claude-code")
        assert p == Path("/h/.claude/commands/ship.md")

    def test_extension_comes_from_the_agent_not_the_skills_dir(self):
        # the dotdir is ".gemini" but no agent was passed — the historical
        # signature must still yield Markdown rather than sniffing the path.
        p = workflows.workflow_target(Path("/h/.gemini/skills"), "commands", "ship")
        assert p == Path("/h/.gemini/commands/ship.md")

    def test_agent_is_keyword_compatible_after_base(self):
        # `agent` trails `base`, so the pre-Gemini positional call still works
        assert workflows.workflow_target(
            Path("/h/.claude/skills"), "commands", "ship", Path("/repo"),
        ) == Path("/repo/.claude/commands/ship.md")


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

    def test_toml_path_is_guarded_too(self):
        # the guard must precede the extension choice — the .toml branch is not
        # a second, unchecked way into the join.
        with pytest.raises(BoostError, match="invalid workflow name"):
            workflows.workflow_target(Path("/home/v/.gemini/skills"), "commands",
                                      self.EVIL, agent="gemini")

    def test_ordinary_name_still_lands_in_the_toml_slot(self):
        p = workflows.workflow_target(Path("/home/v/.gemini/skills"), "commands",
                                      "my_cmd-1.2", agent="gemini")
        assert p.name == "my_cmd-1.2.toml"
        assert Path(p).resolve().is_relative_to(Path("/home/v/.gemini").resolve())


MARKDOWN = "---\nname: ship\ndescription: Ship it\n---\n\nDo the thing.\n"


class TestRender:
    """`render` and `target_ext` must agree on exactly which (agent, slot) pair
    is special — a disagreement writes TOML into a .md file or vice versa."""

    def test_gemini_command_is_converted_to_toml(self):
        out = workflows.render("gemini", "commands", "ship", MARKDOWN)
        assert out != MARKDOWN
        assert _toml_loads(out) == {"description": "Ship it",
                                    "prompt": "Do the thing."}

    def test_gemini_subagent_is_verbatim(self):
        assert workflows.render("gemini", "agents", "rev", MARKDOWN) == MARKDOWN

    def test_claude_command_is_verbatim(self):
        assert workflows.render("claude-code", "commands", "ship", MARKDOWN) == MARKDOWN

    def test_unknown_and_none_agents_are_verbatim(self):
        assert workflows.render("cursor", "commands", "s", MARKDOWN) == MARKDOWN
        assert workflows.render(None, "commands", "s", MARKDOWN) == MARKDOWN
        assert workflows.render(None, "agents", "s", MARKDOWN) == MARKDOWN

    @pytest.mark.parametrize("agent", [None, "claude-code", "cursor", "gemini"])
    @pytest.mark.parametrize("slot", ["commands", "agents"])
    def test_conversion_happens_exactly_where_the_extension_is_toml(self, agent, slot):
        converted = workflows.render(agent, slot, "s", MARKDOWN) != MARKDOWN
        assert converted is (workflows.target_ext(agent, slot) == workflows.TOML_EXT)


class TestRenderGeminiCommand:
    def test_description_and_prompt_round_trip(self):
        data = _toml_loads(workflows.render_gemini_command("ship", MARKDOWN))
        assert data == {"description": "Ship it", "prompt": "Do the thing."}

    def test_frontmatter_is_dropped_not_carried(self):
        # Claude's metadata vocabulary is not Gemini's; only the two keys
        # Gemini's TOML v1 format defines are emitted.
        raw = "---\nname: ship\ndescription: D\ntags: [a, b]\nversion: 1.2\n---\n\nB\n"
        assert set(_toml_loads(workflows.render_gemini_command("ship", raw))) == {
            "description", "prompt"}

    def test_missing_description_omits_the_key_but_keeps_prompt(self):
        raw = "---\nname: ship\n---\n\nBody.\n"
        data = _toml_loads(workflows.render_gemini_command("ship", raw))
        assert "description" not in data     # optional key, so omit it
        assert data["prompt"] == "Body."     # required key, always present

    def test_no_frontmatter_at_all_still_emits_prompt(self):
        data = _toml_loads(workflows.render_gemini_command("ship", "Just prose.\n"))
        assert data == {"prompt": "Just prose."}

    def test_blank_description_is_omitted(self):
        raw = "---\nname: ship\ndescription: '   '\n---\n\nB\n"
        assert "description" not in _toml_loads(
            workflows.render_gemini_command("ship", raw))

    def test_empty_body_still_emits_an_empty_prompt(self):
        # Gemini rejects a command file with no `prompt` key outright, so an
        # empty body must become prompt = "" rather than a missing key.
        for raw in ("", "\n\n", "---\nname: ship\n---\n\n\n"):
            data = _toml_loads(workflows.render_gemini_command("ship", raw))
            assert data == {"prompt": ""}

    def test_ends_in_exactly_one_newline(self):
        out = workflows.render_gemini_command("ship", MARKDOWN)
        assert out.endswith("\n")
        assert not out.endswith("\n\n")

    def test_description_precedes_prompt(self):
        out = workflows.render_gemini_command("ship", MARKDOWN)
        assert out.index("description = ") < out.index("prompt = ")

    # --- hostile bodies: a tap controls this text verbatim ---
    HOSTILE = (
        'triple """ quotes\n'
        'a backslash \\ and a windows path C:\\temp\\new\n'
        'a tab\there and a CRLF\r\n'
        'unicode: caf\u00e9 \u2014 \u65e5\u672c\u8a9e \u2603\n'
        'ends with a quote "'
    )

    def test_hostile_body_parses_and_round_trips_byte_for_byte(self):
        out = workflows.render_gemini_command("h", self.HOSTILE)
        assert _toml_loads(out)["prompt"] == self.HOSTILE

    def test_hostile_body_stays_a_single_line_basic_string(self):
        # the multi-line \"\"\" form cannot hold a body containing \"\"\" or a
        # trailing quote — so newlines must be escaped, not embedded.
        out = workflows.render_gemini_command("h", self.HOSTILE)
        assert out.count("\n") == 1          # only the trailing newline
        assert '"""' not in out             # the body's triple quotes are escaped
        # the body's own trailing quote is escaped, then the string terminator
        assert out.rstrip("\n").endswith('\\""')

    def test_hostile_description_round_trips(self):
        raw = '---\ndescription: he said "hi" \\ and \u2014 caf\u00e9\n---\n\nB\n'
        data = _toml_loads(workflows.render_gemini_command("h", raw))
        assert data["description"] == 'he said "hi" \\ and \u2014 caf\u00e9'

    def test_unicode_is_not_escaped_into_ascii(self):
        # ensure_ascii=False keeps the file readable; \\uXXXX would also parse,
        # but the emitted TOML should carry the characters themselves.
        out = workflows.render_gemini_command("h", "caf\u00e9 \u2603\n")
        assert "caf\u00e9 \u2603" in out
        assert "\\u" not in out

    def test_name_does_not_leak_into_the_output(self):
        # the filename carries the command name; the TOML body must not repeat
        # it (Gemini derives the slash command from the path).
        out = workflows.render_gemini_command("supersecretname", MARKDOWN)
        assert "supersecretname" not in out
