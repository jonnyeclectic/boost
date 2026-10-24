# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Every surface names the same agents and the same modified state.

Two splits, both between `boost doctor` and the surfaces that describe one
item. With an agent disabled, a skill kept naming it in `list`, `info`,
`stats` and MCP `boost_info` while a rule dropped it -- and doctor named only
the rule. And a hand-edited skill looked pristine everywhere doctor and
verify flagged it.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess

from boost_cli.commands import configuration
from boost_cli.core import paths


def _rule_tap(fixture_tap_src, dest):
    shutil.copytree(fixture_tap_src, dest)
    (dest / "rules").mkdir()
    (dest / "rules" / "dep-mgmt.mdc").write_text(
        "---\nname: dep-mgmt\nversion: 1.0.0\ndescription: Pin deps.\n---\n\n"
        "Always pin transitive dependency versions.\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(dest), "add", "-A"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(dest), "commit", "-qm", "add rule"],
                   check=True, capture_output=True)
    return dest


def _row(out: str, name: str) -> list[str]:
    """The cells of ``name``'s `boost list` row, split on column gaps."""
    line = next(ln for ln in out.splitlines() if ln.startswith(name + " "))
    return re.split(r"\s{2,}", line.strip())


def _kv(out: str, key: str) -> str:
    m = re.search(r"^\s*%s\s{2,}(.+)$" % re.escape(key), out, re.M)
    assert m, out
    return m.group(1).strip()


def _mcp_line(text: str, key: str) -> str:
    return next(ln for ln in text.splitlines()
                if ln.startswith(key + ": ")).split(": ", 1)[1]


class TestDisabledAgentParity:
    def test_skill_and_rule_drop_a_disabled_agent_on_every_surface(
            self, boost, fixture_tap_src, tmp_path):
        boost("tap", _rule_tap(fixture_tap_src, tmp_path / "rtap"))
        boost("install", "tdd-workflow")
        boost("install", "dep-mgmt")
        boost("install", "commit-messages", "--local")
        assert _row(boost("list").out, "tdd-workflow")[3] == \
            "antigravity·claude·cursor·windsurf"
        boost("config", "set", "agents.cursor.enabled", "false")

        listing = boost("list").out
        assert _row(listing, "tdd-workflow")[3] == "antigravity·claude·windsurf"
        assert _row(listing, "dep-mgmt")[3] == "claude·codex·gemini·windsurf"
        # Project scope copies into its own set: gemini and codex stay.
        assert _row(listing, "commit-messages")[3] == \
            "claude·codex·gemini·windsurf"

        skill = "antigravity, claude-code, windsurf"
        assert _kv(boost("info", "tdd-workflow").out, "agents") == skill
        assert _kv(boost("stats", "tdd-workflow").out, "agents") == skill
        text, err = configuration._tool_info({"name": "tdd-workflow"})
        assert not err and _mcp_line(text, "agents") == skill
        assert _kv(boost("info", "commit-messages").out, "agents") == \
            "claude-code, codex, gemini, windsurf"

        rule = "claude-code, codex, gemini, windsurf"
        assert _kv(boost("stats", "dep-mgmt").out, "agents") == rule
        text, _ = configuration._tool_info({"name": "dep-mgmt"})
        assert _mcp_line(text, "agents") == rule

    def test_doctor_names_the_skill_links_beside_the_rule_rows(
            self, boost, tapped, monkeypatch):
        monkeypatch.setenv("COLUMNS", "400")
        boost("install", "tdd-workflow")
        boost("install", "commit-messages", "--local")
        boost("config", "set", "agents.cursor.enabled", "false")
        r = boost("doctor", expect=None)
        assert ("2 recorded materializations name an agent boost no longer "
                "writes: skill tdd-workflow → cursor (is disabled), skill "
                "commit-messages → cursor (is disabled). Change that agent's "
                "entry in ~/.boost/config.json and run `boost sync`" in r.out)

    def test_an_enabled_machine_has_no_unwritten_skill_rows(
            self, boost, tapped):
        boost("install", "tdd-workflow")
        assert "materializations name" not in boost("doctor", expect=None).out


class TestModifiedSkillParity:
    def test_a_hand_edit_shows_on_every_surface(self, boost, tapped):
        boost("install", "commit-messages")
        boost("install", "tdd-workflow")

        def surfaces():
            listing = boost("list").out
            data = json.loads(boost("list", "--json").out)["skills"]
            info = boost("info", "commit-messages").out
            ijson = json.loads(boost("info", "commit-messages", "--json").out)
            stats = boost("stats", "commit-messages").out
            sjson = json.loads(boost("stats", "commit-messages", "--json").out)
            mlist, _ = configuration._tool_list({})
            minfo, _ = configuration._tool_info({"name": "commit-messages"})
            return listing, data, info, ijson, stats, sjson, mlist, minfo

        listing, data, info, ijson, stats, sjson, mlist, minfo = surfaces()
        assert len(_row(listing, "commit-messages")) == 4   # empty FLAGS
        assert "modified" not in data["commit-messages"]
        assert "[modified]" not in info and ijson["modified"] is False
        assert "modified" not in stats and sjson["modified"] is False
        assert "commit-messages v1.0.2 (fixture-tap)\n" in mlist
        assert "modified:" not in minfo

        skill_md = paths.store_dir() / "commit-messages" / "SKILL.md"
        with skill_md.open("a", encoding="utf-8") as f:
            f.write("local edit\n")
        listing, data, info, ijson, stats, sjson, mlist, minfo = surfaces()
        assert _row(listing, "commit-messages")[4] == "modified"
        assert len(_row(listing, "tdd-workflow")) == 4
        assert data["commit-messages"]["modified"] is True
        assert "modified" not in data["tdd-workflow"]
        assert "[installed] [modified] [fixture-tap]" in info
        assert ijson["modified"] is True
        assert _kv(stats, "modified") == "yes  (edited since install)"
        assert sjson["modified"] is True
        assert "commit-messages v1.0.2 (fixture-tap) [modified]\n" in mlist
        assert "tdd-workflow v3.0.1 (fixture-tap)\n" in mlist
        assert _mcp_line(minfo, "modified") == \
            "yes — edited since install; `boost verify` names it"
        # The same verdict doctor reaches.
        assert "skill commit-messages modified since install" in \
            boost("doctor", expect=None).out

    def test_a_hand_edited_project_skill_shows_too(self, boost, tapped, sandbox):
        boost("install", "brainstorming", "--local")
        listing = boost("list").out
        assert len(_row(listing, "brainstorming")) == 4
        copy = next(p for p in sandbox.parent.joinpath("cwd").rglob("SKILL.md")
                    if p.parent.name == "brainstorming")
        with copy.open("a", encoding="utf-8") as f:
            f.write("local edit\n")
        listing = boost("list").out
        assert _row(listing, "brainstorming")[4] == "modified"
        project = json.loads(boost("list", "--json").out)["project"]
        assert project["brainstorming"]["modified"] is True
        info = boost("info", "brainstorming").out
        assert "[installed in this project] [modified] [fixture-tap]" in info
        assert json.loads(
            boost("stats", "brainstorming", "--json").out)["modified"] is True
        mlist, _ = configuration._tool_list({})
        assert "brainstorming v1.4.0 (fixture-tap) [project] [modified]\n" \
            in mlist
        minfo, _ = configuration._tool_info({"name": "brainstorming"})
        assert "modified: yes" in minfo
