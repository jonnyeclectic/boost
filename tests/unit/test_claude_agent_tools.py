# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a Claude Code subagent whose ``tools`` name no Claude tool is
written, and said.

A tap's agent written for GitHub Copilot carried ``tools: codebase,
edit/editFiles, terminalCommand, search, githubRepo``. boost dropped it into
``~/.claude/agents`` verbatim and reported success; Claude Code loads the file
and then refuses to launch it ("would be spawned with zero tools"). Declining
the file would delete a copy the user may have fixed by hand, and dropping the
line would widen the grant to every tool, so the file is still written and
``render_notes`` names the line to fix.
"""
from __future__ import annotations

import shutil

import pytest

from boost_cli.commands import pkg
from boost_cli.core import catalog, registry, store, workflows

COPILOT = "codebase, edit/editFiles, terminalCommand, search, githubRepo"


def _agent(tools: str | None, name: str = "gh-expert") -> str:
    line = "" if tools is None else "tools: %s\n" % tools
    return "---\nname: %s\ndescription: d\n%s---\nBody.\n" % (name, line)


def _notes(raw: str) -> list[str]:
    return workflows.render_notes("claude-code", workflows.SLOT_AGENTS, raw)


class TestClaudeAgentNotes:
    def test_the_copilot_tools_line_is_named_entry_by_entry(self):
        assert _notes(_agent(COPILOT)) == [
            "`tools` grants `codebase`, `edit/editFiles`, `terminalCommand`, "
            "`search`, `githubRepo`, none of which is a Claude Code tool, and "
            "Claude Code refuses to launch a subagent whose tools resolve to "
            "nothing — fix the `tools` line; written as the tap has it"]

    @pytest.mark.parametrize("tools", [
        "[codebase, githubRepo]",
        "\n  - codebase\n  - githubRepo",
        "\n- codebase\n- githubRepo",
        '"codebase, githubRepo"',
    ])
    def test_every_readable_shape_is_judged(self, tools):
        notes = _notes(_agent(tools))
        assert len(notes) == 1
        assert "`codebase`, `githubRepo`, none of which" in notes[0]

    def test_a_lowercase_built_in_is_given_its_spelling(self):
        """`read` is not `Read` to Claude Code; saying which is the fix."""
        assert _notes(_agent("read, grep, codebase")) == [
            "`tools` grants `read`, `grep`, `codebase`, none of which is a "
            "Claude Code tool, and Claude Code refuses to launch a subagent "
            "whose tools resolve to nothing — fix the `tools` line (Claude "
            "Code spells `read` as `Read`, `grep` as `Grep`); written as the "
            "tap has it"]

    @pytest.mark.parametrize("tools", [
        "Read, Grep, Bash",
        "Task",
        "Agent",
        "Agent(worker, researcher)",
        "Bash(git add *, git commit *)",
        "mcp__github__create_issue",
        "mcp__github__*",
        "*",
        # not a tool today; Claude-shaped, so a newer Claude Code may have it
        "FutureTool",
        # partial: Claude Code launches with the subset, so boost is quiet too
        "Read, codebase",
        "[Read, codebase]",
        "codebase, Agent(worker, researcher)",
    ])
    def test_a_line_with_any_claude_entry_is_quiet(self, tools):
        assert _notes(_agent(tools)) == []

    @pytest.mark.parametrize("raw", [
        _agent(None),                                  # inherits every tool
        _agent(""),                                    # empty
        _agent("~"),
        _agent("[]"),
        _agent(">\n  codebase"),                       # block scalar
        _agent("\n  a: codebase"),                     # nested mapping
        _agent("[codebase,\n  githubRepo]"),           # flow list over lines
        "Body with no frontmatter.\n",
        "---\nname: x\ntools: codebase\n",             # never closed
        "---\n  indented: x\ntools: codebase\n---\nB\n",   # unreadable block
    ])
    def test_nothing_readable_or_nothing_granted_is_quiet(self, raw):
        assert _notes(raw) == []

    def test_disallowed_tools_is_not_the_grant(self):
        """Deny entries that resolve to nothing never stop a launch."""
        raw = ("---\nname: x\ndescription: d\ndisallowedTools: codebase\n"
               "---\nB\n")
        assert _notes(raw) == []

    def test_only_claude_codes_agents_slot_is_judged(self):
        raw = _agent(COPILOT)
        assert workflows.render_notes("claude-code", workflows.SLOT_COMMANDS,
                                      raw) == []
        assert workflows.render_notes("cursor", workflows.SLOT_AGENTS,
                                      raw) == []
        # and it is a note, never a refusal: the file is still written
        assert workflows.render_problem("claude-code", workflows.SLOT_AGENTS,
                                        raw) is None
        assert workflows.render("claude-code", workflows.SLOT_AGENTS, "x",
                                raw) == raw


class TestClaudeToolSplit:
    @pytest.mark.parametrize(("text", "want"), [
        ("Read, Grep", ["Read", "Grep"]),
        ("Agent(worker, researcher), Read",
         ["Agent(worker, researcher)", "Read"]),
        ("Bash(git add *, git commit *)", ["Bash(git add *, git commit *)"]),
        ("Bash(echo (a, b)), Read", ["Bash(echo (a, b))", "Read"]),
        # a stray `)` never drives the depth negative and swallows the rest
        ("a), b, c", ["a)", "b", "c"]),
        (" , Read,, ", ["Read"]),
        ("", []),
    ])
    def test_commas_inside_parentheses_do_not_split(self, text, want):
        assert workflows._split_claude_tools(text) == want


class TestClaudeToolNames:
    def test_every_built_in_is_claude_shaped(self):
        """The shape test is what decides, so it has to cover the list: a
        built-in it rejected would be warned about as foreign."""
        names = workflows.CLAUDE_TOOL_NAMES | workflows.CLAUDE_TOOL_ALIASES
        assert {n for n in names if not workflows.claude_tool_resolves(n)} \
            == set()

    def test_the_documented_set_is_the_one_shipped(self):
        # https://code.claude.com/docs/en/tools-reference, read 2026-10-31
        assert {"Agent", "Bash", "Edit", "Glob", "Grep", "Read", "Write",
                "WebFetch", "WebSearch", "NotebookEdit", "TodoWrite",
                "Skill"} <= workflows.CLAUDE_TOOL_NAMES
        assert {"Task"} == workflows.CLAUDE_TOOL_ALIASES

    @pytest.mark.parametrize(("entry", "ok"), [
        ("Read", True), ("Bash(git *)", True), ("mcp__x__y", True),
        ("*", True), ("Zz9", True),
        ("read", False), ("mcp_x", False), ("**", False),
        ("Bash(", False), ("Bash)x", False), ("9Read", False),
        ("Read x", False), ("", False),
    ])
    def test_what_resolves(self, entry, ok):
        assert workflows.claude_tool_resolves(entry) is ok


AGENT = _agent(COPILOT, name="gh-expert")


@pytest.fixture()
def tap(sandbox, fixture_tap_src, tmp_path):
    src = tmp_path / "claude-tools-tap"
    shutil.copytree(fixture_tap_src, src, symlinks=True)
    t = registry.add(str(src))
    catalog.rebuild_tap(t)
    return t


def _wf(tap, body=AGENT, name="github-actions-expert",
        rel="agents/github-actions-expert.md"):
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(body, encoding="utf-8")
    return {"name": name, "kind": "workflow", "tap": tap.name,
            "version": "1.0.0", "rel_dir": str(src.parent.relative_to(tap.path)),
            "skill_md": rel, "description": "d", "curated": False, "meta": {}}


class TestInstall:
    def test_the_file_is_written_and_the_note_printed(self, tap, capsys):
        res = store.install(_wf(tap), as_skill=False)
        assert "claude-code" in res.linked
        assert [n for n in res.render_notes if n.startswith("claude-code: ")
                ] == ["claude-code: `tools` grants `codebase`, `edit/editFiles`, "
                      "`terminalCommand`, `search`, `githubRepo`, none of which "
                      "is a Claude Code tool, and Claude Code refuses to "
                      "launch a subagent whose tools resolve to nothing — fix "
                      "the `tools` line; written as the tap has it"]
        pkg._warn_unwritable(res)
        out = " ".join(capsys.readouterr().out.split())
        assert ("github-actions-expert: claude-code: `tools` grants "
                "`codebase`") in out

    def test_a_subagent_says_how_claude_code_runs_it(self, tap, capsys):
        """It is not `/github-actions-expert`, and the @-mention is the
        frontmatter `name`, not the file name."""
        res = store.install(_wf(tap), as_skill=False)
        assert res.invocation == [
            "claude-code: a subagent, not a slash command — @-mention it as "
            "`@agent-gh-expert`, or ask Claude to use it"]
        pkg._report_result(res)
        out = " ".join(capsys.readouterr().out.split())
        assert "@-mention it as `@agent-gh-expert`" in out

    def test_a_command_or_an_unwritten_agent_says_nothing(self, tap):
        cmd = _wf(tap, body="---\ndescription: d\n---\nRun.\n", name="run-it",
                  rel="commands/run-it.md")
        assert store.install(cmd, as_skill=False).invocation == []
        res = store.install(_wf(tap), only_agents=["cursor"], as_skill=False)
        assert res.invocation == []


class TestInvocationHint:
    def test_only_claude_codes_agents_slot(self):
        raw = _agent("Read", name="x")
        assert workflows.invocation_hint("claude-code", workflows.SLOT_AGENTS,
                                         "f", raw) is not None
        assert workflows.invocation_hint("claude-code",
                                         workflows.SLOT_COMMANDS, "f",
                                         raw) is None
        assert workflows.invocation_hint("cursor", workflows.SLOT_AGENTS,
                                         "f", raw) is None

    def test_no_frontmatter_name_falls_back_to_the_file_name(self):
        assert workflows.invocation_hint(
            "claude-code", workflows.SLOT_AGENTS, "reviewer",
            "---\ndescription: d\n---\nB\n") == (
            "a subagent, not a slash command — @-mention it as "
            "`@agent-reviewer`, or ask Claude to use it")
        assert "`@agent-reviewer`" in workflows.invocation_hint(
            "claude-code", workflows.SLOT_AGENTS, "reviewer",
            "---\nname: '  '\n---\nB\n")
