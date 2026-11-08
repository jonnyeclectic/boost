# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""boost_read says when SKILL.md is not the whole skill, and where the rest is.

Measured against anthropics/skills at 2c5958e: `boost_read pdf` returned
SKILL.md alone, which says "If you need to fill out a PDF form, read
FORMS.md" and runs `scripts/*.py`. The reply never said forms.md,
reference.md and eight scripts existed, and the server's instructions told
the agent to "work from what you read". boost_install's "to use it now" line
named only SKILL.md's path, with no base for the relative ones. 14 of that
repo's 19 skills ship files besides SKILL.md and LICENSE.txt.
"""
from __future__ import annotations

import subprocess

import pytest

from boost_cli.commands import configuration
from boost_cli.core import mcp, paths

SKILL = "pdfish"


def _git(repo, *argv):
    subprocess.run(["git", "-C", str(repo), *argv], check=True,
                   capture_output=True)


@pytest.fixture()
def companion_tap(boost, sandbox, tmp_path):
    """A git tap whose one skill ships two docs and three scripts."""
    tap = tmp_path / "companion-tap"
    d = tap / "skills" / SKILL
    (d / "scripts" / "lib").mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: %s\ndescription: fill a pdf form\nversion: 1.0.0\n---\n\n"
        "To fill a form, read FORMS.md and run scripts/fill.py.\n" % SKILL,
        encoding="utf-8")
    (d / "forms.md").write_text("# forms\n", encoding="utf-8")
    (d / "reference.md").write_text("# reference\n", encoding="utf-8")
    for rel in ("scripts/fill.py", "scripts/check.py", "scripts/lib/util.py"):
        (d / rel).write_text("print('x')\n", encoding="utf-8")
    _git(tap, "init", "-q")
    _git(tap, "add", "-A")
    _git(tap, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm",
         "tap")
    boost("tap", tap)
    return tap


def _header(text: str) -> list[str]:
    return text.split("\n\n", 1)[0].splitlines()


class TestTheReadSaysWhatElseShips:
    def test_a_tap_skill_names_its_companions(self, companion_tap):
        text, is_err = configuration._tool_read({"name": SKILL})
        assert not is_err
        line = next(h for h in _header(text) if h.startswith("also ships: "))
        assert line.startswith(
            "also ships: forms.md, reference.md, scripts/ (3 files) — ")
        assert "boost_install puts these beside it" in line
        assert "To fill a form, read FORMS.md" in text

    def test_an_installed_skill_names_where_they_are(self, boost,
                                                     companion_tap):
        boost("install", SKILL)
        text, _ = configuration._tool_read({"name": SKILL})
        line = next(h for h in _header(text)
                    if h.startswith("files beside it: "))
        where = paths.tilde(paths.store_dir() / SKILL)
        assert line == ("files beside it: forms.md, reference.md, scripts/ "
                        "(3 files) — in %s, where the text's relative paths "
                        "resolve" % where)
        assert (paths.store_dir() / SKILL / "scripts" / "fill.py").is_file()

    def test_the_path_argument_names_them_too(self, companion_tap):
        text, _ = configuration._tool_read({"name": SKILL,
                                            "path": "skills/" + SKILL})
        assert any(h.startswith("also ships: forms.md")
                   for h in _header(text))

    def test_a_skill_with_nothing_beside_it_gets_no_line(self, boost,
                                                         fixture_tap_src):
        boost("tap", fixture_tap_src)
        text, _ = configuration._tool_read({"name": "brainstorming"})
        assert not any(h.startswith(("also ships", "files beside"))
                       for h in _header(text))


class TestTheInstallReplyNamesTheBaseDirectory:
    def test_use_it_now_names_the_directory(self, companion_tap):
        text, is_err = mcp.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "boost_install",
                        "arguments": {"name": SKILL}}},
            version="test", registry=configuration.REGISTRY
        )["result"]["content"][0]["text"], False
        assert not is_err
        assert ("the files it names by relative path are in %s "
                % paths.tilde(paths.store_dir() / SKILL)) in text


def test_the_tool_description_says_the_header_names_them():
    spec = next(s for s in configuration.REGISTRY.specs()
                if s["name"] == "boost_read")
    assert ("ships files beside SKILL.md, and the reply's header names them"
            in spec["description"])
