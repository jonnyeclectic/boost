# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""What a boost_install reply tells the agent beyond "installed".

Three gaps, each measured by driving the tool against a tap:

- **Using it now.** No reply said how to use the item in the session that
  installed it, while boost_list's description promised installed items were
  "usable this second". Whether a host loads a file written after its session
  started was not verified for any host, so the reply points at the text.
- **Declared MCP servers.** A skill whose sidecar declares a server installed
  with a reply that never named it; `boost info` and `boost deps` did. The
  agent reported success over a skill that fails later. (Roadmap card
  mcp-install-tool-names-declared-servers.)
- **Rules.** A rule landed in five files every later session reads, and the
  reply named one of them under a skill word, "linked agents".
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from boost_cli.commands import configuration
from boost_cli.core import lockfile, mcp, paths


def _call(tool, **args):
    resp = mcp.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": tool, "arguments": args}},
        version="test", registry=configuration.REGISTRY)
    res = resp["result"]
    return res["content"][0]["text"], res.get("isError", False)


def _skill(tap, name, decl=None, sidecar=None):
    d = tap / "skills" / name
    d.mkdir(parents=True)
    head = "---\nname: %s\ndescription: %s does a thing\nversion: 1.0.0\n" % (
        name, name)
    if decl:
        head += "mcp: %s\n" % decl
    (d / "SKILL.md").write_text(head + "---\n\n# %s\n\nBody.\n" % name,
                                encoding="utf-8")
    if sidecar is not None:
        (d / ".mcp.json").write_text(json.dumps(sidecar), encoding="utf-8")


@pytest.fixture()
def reply_tap(boost, sandbox, fixture_tap_src, tmp_path):
    """The fixture tap plus a rule, a workflow and two server-declaring skills."""
    tap = tmp_path / "reply-tap"
    shutil.copytree(fixture_tap_src, tap)
    (tap / "rules").mkdir()
    (tap / "rules" / "house-style.mdc").write_text(
        "---\nname: house-style\ndescription: house rules\n---\n\nUse tabs.\n",
        encoding="utf-8")
    (tap / "commands").mkdir()
    (tap / "commands" / "ship-it.md").write_text(
        "---\nname: ship-it\ndescription: release it\n---\n\nShip.\n",
        encoding="utf-8")
    _skill(tap, "needs-mcp", decl="github", sidecar={"mcpServers": {
        "github": {"command": "npx", "args": ["-y", "gh-mcp"]}}})
    _skill(tap, "name-only", decl="linear")
    for argv in (["add", "-A"], ["commit", "-qm", "reply tap"]):
        subprocess.run(["git", "-C", str(tap), *argv], check=True,
                       capture_output=True)
    boost("tap", tap)
    return tap


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    monkeypatch.chdir(root)
    return root


class TestTheReplySaysHowToUseItNow:
    def test_a_skill_names_boost_read_and_its_installed_file(self, reply_tap):
        text, is_err = _call("boost_install", name="brainstorming")
        assert is_err is False
        assert ("to use it now: follow the text boost_read returns for "
                "brainstorming, or read %s"
                % paths.tilde(paths.store_dir() / "brainstorming" / "SKILL.md")
                ) in text
        assert "depends on the host" in text

    def test_a_project_skill_names_the_copy_in_the_repository(
            self, reply_tap, repo):
        text, _ = _call("boost_install", name="brainstorming", scope="project")
        assert ("or read %s" % paths.tilde(
            repo / ".claude" / "skills" / "brainstorming" / "SKILL.md")) in text

    def test_a_workflow_points_at_boost_read(self, reply_tap):
        text, is_err = _call("boost_install", name="ship-it")
        assert is_err is False
        assert "to use it now: boost_read ship-it returns its text" in text
        assert "a command written after it started" in text

    def test_boost_list_no_longer_promises_usable_this_second(self):
        desc = {s["name"]: s["description"]
                for s in configuration.REGISTRY.specs()}["boost_list"]
        assert "usable this second" not in desc


class TestARuleNamesEveryFileItWrote:
    def test_each_materialization_is_listed(self, reply_tap):
        text, is_err = _call("boost_install", name="house-style")
        assert is_err is False
        home = paths.home()
        for written in (home / ".claude" / "CLAUDE.md",
                        home / ".gemini" / "GEMINI.md",
                        home / ".codex" / "AGENTS.md",
                        home / ".cursor" / "rules" / "house-style.mdc",
                        home / ".windsurf" / "rules" / "house-style.md"):
            assert written.is_file(), written
            assert "\n  %s\n" % paths.tilde(written) in text, written
        assert "standing instructions every session reads from now on" in text
        assert "`boost uninstall house-style` removes it from all of them" \
            in text
        assert "linked agents" not in text
        assert "to use it now: boost_read house-style returns its text" in text

    def test_the_install_description_draws_the_consent_line(self):
        desc = {s["name"]: s["description"]
                for s in configuration.REGISTRY.specs()}["boost_install"]
        assert "ask the user before installing a rule" in desc



class TestAProjectRuleOrWorkflowIsNotInTheProjectLock:
    """Only a skill is recorded in the repository's .boost/skill-lock.json.

    A project rule or workflow is written into the repository and recorded in
    the user's lock with its base, and a rule's Claude target is the personal,
    git-ignored CLAUDE.local.md. The reply told the agent "recorded in
    .boost/skill-lock.json; commit .boost/ ..." for all three kinds, over a
    rule install that had created no .boost/ at all.
    """

    def test_a_project_rule_names_the_lock_that_holds_it(self, reply_tap,
                                                         repo):
        text, is_err = _call("boost_install", name="house-style",
                             scope="project")
        assert is_err is False
        assert lockfile.get_rule("house-style")["scope"] == "project"
        assert not (repo / ".boost").exists()
        assert ".boost/skill-lock.json" not in text
        assert "commit .boost/" not in text
        assert ("scope: project (%s) — written into this repository, "
                "recorded in %s rather than in .boost/"
                % (paths.tilde(repo), paths.tilde(paths.lockfile_path()))
                ) in text

    def test_a_project_workflow_is_written_not_linked(self, reply_tap, repo):
        text, is_err = _call("boost_install", name="ship-it", scope="project")
        assert is_err is False
        assert (repo / ".claude" / "commands" / "ship-it.md").is_file()
        assert "written into this repository for: claude-code" in text
        assert "linked agents" not in text
        assert "commit .boost/" not in text
        assert not (repo / ".boost").exists()

    def test_a_project_skill_still_points_at_the_project_lock(self, reply_tap,
                                                               repo):
        text, _ = _call("boost_install", name="brainstorming", scope="project")
        assert (repo / ".boost" / "skill-lock.json").is_file()
        assert ("scope: project (%s) — real files in this repository, "
                "recorded in .boost/skill-lock.json" % paths.tilde(repo)) \
            in text
        assert "rather than in .boost/" not in text


class TestDeclaredMcpServersAreNamed:
    def test_a_runnable_server_comes_with_the_command_to_register_it(
            self, reply_tap):
        text, is_err = _call("boost_install", name="needs-mcp")
        assert is_err is False
        assert "needs MCP server github: `npx -y gh-mcp` — not registered" \
            in text
        assert "ask the user to run this for each agent they use:" in text
        assert "  claude mcp add github --scope user -- npx -y gh-mcp" in text
        # Named, never acted on: registering is the user's call.
        assert not (paths.home() / ".claude.json").exists()

    def test_a_name_only_declaration_says_there_is_no_command(self, reply_tap):
        text, _ = _call("boost_install", name="name-only")
        line = next(ln for ln in text.splitlines() if "linear" in ln)
        assert line.startswith("needs MCP server linear (no command declared)")
        assert "`boost mcp register`" in line
        # boost will not invent a command line on the author's behalf.
        assert "claude mcp add" not in text

    def test_a_project_install_says_it_recorded_the_server(
            self, reply_tap, repo):
        text, _ = _call("boost_install", name="needs-mcp", scope="project")
        assert ("needs MCP server github: `npx -y gh-mcp` — recorded in this "
                "repository's .mcp.json") in text
        doc = json.loads((repo / ".mcp.json").read_text(encoding="utf-8"))
        assert "github" in doc["mcpServers"]
        assert "claude mcp add" not in text

    def test_an_unwritable_sidecar_is_reported_not_claimed(
            self, reply_tap, repo):
        (repo / ".mcp.json").write_text("{not json", encoding="utf-8")
        text, is_err = _call("boost_install", name="needs-mcp",
                             scope="project")
        assert is_err is False
        assert "not recorded, .mcp.json left unchanged" in text
        assert "recorded in this repository" not in text

    def test_a_skill_that_declares_nothing_says_nothing(self, reply_tap):
        text, _ = _call("boost_install", name="brainstorming")
        assert "MCP server" not in text
