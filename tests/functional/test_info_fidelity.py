# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`info`, `explain` and the MCP read tools describe the item that is installed.

Four ways they did not. Once `update --taps-only` moved a tap, the catalog row
(the tap's HEAD) supplied the description beside the lock's older version.
`info` on a rule or workflow never showed the update `outdated` listed. A tap
shipping one name as a skill and a workflow had the installed one described by
its namesake. And a rule installed `--local` into another repo read, over MCP,
as plainly installed.
"""
from __future__ import annotations

import json
import re
import subprocess

import pytest

from boost_cli.commands import configuration


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   capture_output=True)


def _write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _item(name, desc, version="1.0.0", body="Always use tabs."):
    return ("---\nname: %s\ndescription: %s\nversion: %s\n---\n\n# %s\n\n- %s\n"
            % (name, desc, version, name.title(), body))


def _commit(root, msg):
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", msg)


@pytest.fixture()
def mytap(boost, tmp_path):
    """A real git tap with a skill, a rule and a workflow at 1.0.0."""
    root = tmp_path / "mytap"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@boost.test")
    _git(root, "config", "user.name", "Tap")
    _write(root, "skills/alpha/SKILL.md", _item("alpha", "Alpha old description"))
    _write(root, "rules/style.mdc", _item("style", "Style rule old"))
    _write(root, "commands/ship.md", _item("ship", "Ship old"))
    _commit(root, "v1")
    boost("tap", root)
    return root


def _bump(root):
    """Move every item upstream to 2.0.0 with a new description and body."""
    for rel, name, desc in (("skills/alpha/SKILL.md", "alpha", "Alpha NEW description"),
                            ("rules/style.mdc", "style", "Style rule NEW"),
                            ("commands/ship.md", "ship", "Ship NEW")):
        _write(root, rel, _item(name, desc, "2.0.0", "Always use spaces."))
    _commit(root, "v2")


def _tool(tool, **args):
    return configuration._mcp_tool(tool, args)


def _kv(out, key):
    m = re.search(r"^  %s\s+(.*)$" % re.escape(key), out, re.MULTILINE)
    return m.group(1).rstrip() if m else None


class TestHomonymPicksTheInstalledKind:
    @pytest.fixture()
    def twin_tap(self, mytap):
        _write(mytap, "skills/wf/SKILL.md", _item("wf", "WF as SKILL"))
        _write(mytap, "workflows/wf.md", _item("wf", "WF as WORKFLOW"))
        _write(mytap, "skills/dup/SKILL.md", _item("dup", "Dup SKILL desc"))
        _write(mytap, "commands/dup.md", _item("dup", "Dup WORKFLOW desc"))
        _commit(mytap, "homonyms")
        return mytap

    def test_installed_workflow_is_described_as_the_workflow(self, boost,
                                                             twin_tap):
        boost("update", "--taps-only")
        boost("install", "wf", "--path", "workflows")
        r = boost("info", "wf")
        assert _kv(r.out, "description") == "WF as WORKFLOW"
        assert _kv(r.out, "source") == "workflows/wf.md"
        text, is_err = _tool("boost_info", name="wf")
        assert is_err is False
        assert "kind: workflow" in text.splitlines()
        assert "description: WF as WORKFLOW" in text.splitlines()

    def test_installed_skill_is_described_as_the_skill(self, boost, twin_tap):
        boost("update", "--taps-only")
        boost("install", "dup", "--path", "skills/dup")
        r = boost("info", "dup")
        assert _kv(r.out, "description") == "Dup SKILL desc"
        text, is_err = _tool("boost_info", name="dup")
        assert is_err is False
        assert "description: Dup SKILL desc" in text.splitlines()
        assert "kind: workflow" not in text
