# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the companion-file listing behind boost_read's header line.

See tests/functional/test_mcp_read_companions.py for the measured gap: a
skill whose SKILL.md says "read FORMS.md" was served as if it were the whole
skill, with nothing saying forms.md, reference.md and scripts/ existed.
"""
from __future__ import annotations

import os

import pytest

from boost_cli.core import mcp, store


def _header(text: str) -> list[str]:
    return text.split("\n\n", 1)[0].splitlines()


class TestCompanionFiles:
    def test_files_and_counted_directories(self, tmp_path):
        d = tmp_path / "s"
        (d / "scripts" / "lib").mkdir(parents=True)
        (d / "assets").mkdir()
        for rel in ("SKILL.md", "forms.md", "scripts/a.py",
                    "scripts/lib/b.py", "assets/logo.png", ".hidden",
                    "scripts/.cache"):
            (d / rel).write_text("x", encoding="utf-8")
        (d / "scripts" / ".git").mkdir()
        (d / "scripts" / ".git" / "HEAD").write_text("x", encoding="utf-8")
        assert store.companion_files(d) == [
            "assets/ (1 file)", "forms.md", "scripts/ (2 files)"]

    def test_only_skill_md(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("x", encoding="utf-8")
        assert store.companion_files(tmp_path) == []

    def test_an_unreadable_dir(self, tmp_path):
        assert store.companion_files(tmp_path / "missing") == []

    @pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges")
    def test_a_linked_directory_is_named_not_walked(self, tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        (real / "x.py").write_text("x", encoding="utf-8")
        d = tmp_path / "s"
        d.mkdir()
        (d / "vendored").symlink_to(real, target_is_directory=True)
        assert store.companion_files(d) == ["vendored"]


class TestCompanionsLine:
    def test_nothing_to_say(self):
        assert mcp.companions_line([], "~/x") is None

    def test_installed(self):
        assert mcp.companions_line(["a.md"], "~/x") == (
            "files beside it: a.md — in ~/x, where the text's relative "
            "paths resolve")

    def test_not_installed(self):
        assert mcp.companions_line(["a.md"], None) == (
            "also ships: a.md — this reply is SKILL.md alone; boost_install "
            "puts these beside it, and the text's relative paths resolve in "
            "that directory")

    def test_a_long_list_is_counted_past_the_cap(self):
        names = ["f%02d" % i for i in range(mcp.COMPANIONS_SHOWN + 3)]
        line = mcp.companions_line(names, None)
        assert ", ".join(names[:mcp.COMPANIONS_SHOWN]) + ", and 3 more" in line
        assert names[mcp.COMPANIONS_SHOWN] not in line

    def test_exactly_the_cap_is_not_counted(self):
        names = ["f%d" % i for i in range(mcp.COMPANIONS_SHOWN)]
        assert "more" not in mcp.companions_line(names, None)

    def test_read_reply_carries_it_in_the_header(self):
        text = mcp.read_reply("x", "body", companions=["a.md"])
        assert _header(text)[-1].startswith("also ships: a.md")

    def test_a_not_installed_reply_never_points_into_a_tap_clone(self):
        # The tap copy is boost's internal clone; only an installed copy's
        # directory is offered as where to read the files.
        text = mcp.read_reply("x", "body", companions=["a.md"],
                              skill_dir="~/.boost/repos/t/x")
        assert "~/.boost/repos" not in text

    def test_an_installed_reply_names_its_dir(self):
        text = mcp.read_reply("x", "body", installed=True,
                              companions=["a.md"], skill_dir="~/s/x")
        assert "in ~/s/x," in text
