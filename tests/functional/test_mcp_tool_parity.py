# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The MCP tools must answer "is it installed, and is it intact" the way the CLI does.

Four disagreements, each one the agent acted on: boost_doctor called a
hand-edited skill healthy, boost_info read a `tap:name` as not installed and
mixed two taps' rows into one reply, and boost_list / boost_info / boost_search
never looked at the project lock `boost list` reads.
"""
from __future__ import annotations

from boost_cli.commands import configuration
from boost_cli.core import mcp, paths


def _tool(tool, **args):
    return configuration._mcp_tool(tool, args)


class TestDoctorSeesSkillDrift:
    def test_an_edited_skill_is_an_issue_not_healthy(self, boost, tapped):
        boost("install", "commit-messages")
        text, is_err = _tool("boost_doctor")
        assert "healthy — no issues found" in text
        assert is_err is False

        md = paths.store_dir() / "commit-messages" / "SKILL.md"
        md.write_text(md.read_text(encoding="utf-8") + "\nLOCAL EDIT\n",
                      encoding="utf-8")
        text, is_err = _tool("boost_doctor")
        assert ("skill commit-messages: modified since install "
                "(run `boost reinstall commit-messages` to discard local "
                "edits)") in text
        assert "1 issue(s) — run `boost doctor` for details" in text
        assert "healthy" not in text
        assert is_err is True
        # ...and the CLI, asking the same core test, agrees.
        cli = boost("doctor", expect=None)
        assert "skill commit-messages modified since install" in cli.out

    def test_a_quarantined_skill_is_not_reported_as_drift(self, boost, tapped):
        from boost_cli.core import lockfile
        boost("install", "commit-messages")
        md = paths.store_dir() / "commit-messages" / "SKILL.md"
        md.write_text("edited", encoding="utf-8")
        entry = lockfile.get_skill("commit-messages")
        lockfile.set_skill("commit-messages", {**entry, "quarantined": True})
        text, _ = _tool("boost_doctor")
        assert "skill commit-messages: modified" not in text


class TestInfoResolvesTheQualifiedName:
    def test_a_qualified_install_reads_as_installed(self, boost, tapped,
                                                    rival_tap):
        boost("install", "rival-tap:brainstorming")
        text, is_err = _tool("boost_info", name="rival-tap:brainstorming")
        assert is_err is False
        assert "version: 9.9.9" in text
        assert "tap: rival-tap" in text
        assert "installed: yes (" in text
        assert "installed: no" not in text

    def test_the_other_taps_qualifier_does_not_claim_the_install(
            self, boost, tapped, rival_tap):
        boost("install", "rival-tap:brainstorming")
        text, is_err = _tool("boost_info", name="fixture-tap:brainstorming")
        assert is_err is False
        assert "version: 1.4.0" in text
        assert "tap: fixture-tap" in text
        assert "installed: no" in text

    def test_the_description_is_the_installed_taps(self, boost, tapped,
                                                   rival_tap):
        boost("install", "rival-tap:brainstorming")
        text, _ = _tool("boost_info", name="brainstorming")
        assert "tap: rival-tap" in text
        assert "description: A rival ideation skill" in text
        assert "divergent-thinking" not in text

    def test_an_ambiguous_uninstalled_name_says_so(self, boost, tapped,
                                                   rival_tap):
        # The same error boost_read and boost_install raise; the server turns
        # it into an isError result rather than describing the first tap's.
        resp = mcp.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "boost_info",
                        "arguments": {"name": "brainstorming"}}},
            version="0", registry=configuration.REGISTRY)
        text = resp["result"]["content"][0]["text"]
        assert resp["result"]["isError"] is True
        assert "multiple taps: fixture-tap, rival-tap" in text
        assert "installed: no" not in text

    def test_an_unknown_name_is_still_an_error(self, boost, tapped):
        text, is_err = _tool("boost_info", name="zzz-nope")
        assert is_err is True
        assert text == "no skill named 'zzz-nope' (installed or in any tap)"


class TestProjectScopeIsInstalled:
    def test_list_info_and_search_see_a_local_install(self, boost, tapped):
        boost("install", "commit-messages", "--local")
        assert not (paths.store_dir() / "commit-messages").exists()

        text, is_err = _tool("boost_list")
        assert is_err is False
        assert not text.startswith("nothing installed")
        assert "commit-messages v1.0.2 (fixture-tap) [project]" in text
        assert "project skills (" in text
        assert "1 skill ·" in text

        text, is_err = _tool("boost_info", name="commit-messages")
        assert is_err is False
        assert "installed: yes (" in text
        assert "scope: project (" in text
        assert "installed: no" not in text

        text, _ = _tool("boost_search", query="commit message discipline")
        hit = next(ln for ln in text.splitlines() if "commit-messages" in ln)
        assert "[installed]" in hit
        assert "none of these are installed" not in text

    def test_a_user_install_has_no_project_scope_line(self, boost, tapped):
        boost("install", "commit-messages")
        text, _ = _tool("boost_info", name="commit-messages")
        assert "installed: yes (" in text
        assert "scope: project" not in text
        listed, _ = _tool("boost_list")
        assert "[project]" not in listed
        assert "project skills" not in listed
