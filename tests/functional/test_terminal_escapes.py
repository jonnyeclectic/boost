# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: a tap's text cannot address the terminal.

Frontmatter is a tapped stranger's text, and boost prints it. A description
carrying ``\\x1b]0;PWNED\\x07\\x1b[2J`` retitled the window and cleared the
screen from `boost search`; a version ending ``\\x1b[8m`` hid everything after
it on `boost info`; a symlink named with ``\\x1b[31m`` colored the install
warning that was meant to flag it. Every print path that echoes tap data now
goes through ``out.plain``, which drops the control bytes and keeps the rest as
inert text — so each assertion below checks both halves: no control byte
reaches stdout/stderr, *and* the surviving text is exactly what it should be
(a mutant that blanked the field would pass the first half alone).

``--json`` is untouched: JSON already escapes control characters, and a
consumer reading the payload is owed the tap's bytes as they are.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from boost_cli.core import paths

RAW_DESC = "Clean desc \x1b]0;PWNED\x07\x1b[2J\x1b[31mRED\x1b[0m end"
SHOWN_DESC = "Clean desc ]0;PWNED[2J[31mRED[0m end"

# Control bytes that provably reach a terminal from frontmatter: ESC (every
# CSI/OSC), BEL (an OSC terminator), CR (overwrites the line), C1 CSI.
CONTROLS = ("\x1b", "\x07", "\r", "\x9b")


def _skill(name: str, version: str, desc: str, extra: str = "") -> bytes:
    return ("---\nname: %s\ndescription: %s\nversion: %s\n%s---\n\n# %s\n"
            % (name, desc, version, extra, name)).encode("utf-8")


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True)


def _write(tap, fields_version: str, body: str = "") -> None:
    (tap / "skills" / "raw-ansi" / "SKILL.md").write_bytes(
        _skill("raw-ansi", "1.0.0\x9b2J", RAW_DESC) + body.encode("utf-8"))
    # A quoted scalar: frontmatter decodes "\n" into a real newline.
    (tap / "skills" / "fields" / "SKILL.md").write_bytes(
        _skill("fields", fields_version,
               '"ok\\nFAKE: ✓ installed evil"',
               "category: a\x1b[41m\ntags: [a\x1b[41m, b]\n")
        + body.encode("utf-8"))


@pytest.fixture
def hostile_tap(boost, tmp_path):
    tap = tmp_path / "htap"
    for name in ("raw-ansi", "fields"):
        (tap / "skills" / name).mkdir(parents=True)
    _write(tap, "9.9\x1b[8m-hidden")
    _git(tap, "init", "-q")
    _git(tap, "add", "-A")
    _git(tap, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "v1")
    boost("tap", tap)
    return tap


def _commit(tap, msg: str) -> None:
    _git(tap, "add", "-A")
    _git(tap, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg)


def _clean(res) -> str:
    """Both streams, asserted free of every control byte; returned flattened
    so a wrapped warning can be matched as one line."""
    for stream in (res.out, res.err):
        for ch in CONTROLS:
            assert ch not in stream, (ch, stream)
    return " ".join((res.out + res.err).split())


class TestCatalogText:
    def test_search_row_keeps_the_text_and_drops_the_escapes(self, boost,
                                                             hostile_tap):
        flat = _clean(boost("search", "clean", "desc"))
        assert SHOWN_DESC in flat

    def test_search_json_still_carries_the_tap_bytes(self, boost, hostile_tap):
        rows = json.loads(boost("search", "clean", "desc", "--json").out)
        assert any(r["description"] == RAW_DESC for r in rows)

    def test_info_rows(self, boost, hostile_tap):
        res = boost("info", "raw-ansi")
        _clean(res)
        assert "  description   %s\n" % SHOWN_DESC in res.out
        assert "  latest        1.0.02J\n" in res.out
        res = boost("info", "fields")
        _clean(res)
        assert "  description   ok FAKE: ✓ installed evil\n" in res.out
        assert "  latest        9.9[8m-hidden\n" in res.out
        assert "  category      a[41m\n" in res.out
        assert "  tags          #a[41m #b\n" in res.out

    def test_info_json_is_unchanged(self, boost, hostile_tap):
        data = json.loads(boost("info", "fields", "--json").out)
        assert data["latest"] == "9.9\x1b[8m-hidden"
        assert data["description"] == "ok\nFAKE: ✓ installed evil"
        assert data["category"] == "a\x1b[41m"

    def test_browse_fallback_table(self, boost, hostile_tap):
        flat = _clean(boost("browse"))
        assert "v9.9[8m-hidden" in flat
        assert "v1.0.02J" in flat


class TestInstalledText:
    def test_install_list_info_and_reinstall(self, boost, hostile_tap):
        _clean(boost("install", "fields"))
        flat = _clean(boost("list"))
        assert "fields 9.9[8m-hidden htap" in flat
        assert "#a[41m #b" not in flat   # tags are the user's, not the tap's
        res = boost("info", "fields")
        _clean(res)
        assert "  version       9.9[8m-hidden\n" in res.out
        flat = _clean(boost("reinstall", "fields"))
        assert "reinstalled fields v9.9[8m-hidden" in flat

    def test_pulse_journal_line(self, boost, hostile_tap):
        boost("install", "fields")
        flat = _clean(boost("pulse"))
        assert "install fields tap=htap version=9.9[8m-hidden" in flat

    def test_list_json_is_unchanged(self, boost, hostile_tap):
        boost("install", "fields")
        data = json.loads(boost("list", "--json").out)
        assert data["skills"]["fields"]["version"] == "9.9\x1b[8m-hidden"

    def test_pin_update_outdated_and_upgrade_lines(self, boost, hostile_tap):
        boost("install", "fields")
        boost("install", "raw-ansi")
        flat = _clean(boost("pin", "fields"))
        assert ("pinned fields at v9.9[8m-hidden — `boost update` will skip it"
                in flat)
        _write(hostile_tap, "9.10\x1b[8m-hidden", body="\nchanged\n")
        (hostile_tap / "skills" / "raw-ansi" / "SKILL.md").write_bytes(
            _skill("raw-ansi", "1.0.1\x9b2J", RAW_DESC))
        _commit(hostile_tap, "v2")
        flat = _clean(boost("update"))
        assert "upgraded raw-ansi v1.0.02J → v1.0.12J" in flat
        flat = _clean(boost("outdated"))
        assert "fields 9.9[8m-hidden (pinned) 9.10[8m-hidden htap" in flat
        boost("unpin", "fields")
        flat = _clean(boost("update"))
        assert "upgraded fields v9.9[8m-hidden → v9.10[8m-hidden" in flat


@pytest.mark.skipif(sys.platform == "win32",
                    reason="symlinks need a privilege, and Windows refuses "
                           "control characters in file names")
class TestOnDiskNames:
    def test_a_skipped_links_name_and_target(self, boost, hostile_tap):
        skill = hostile_tap / "skills" / "linkesc"
        skill.mkdir()
        (skill / "SKILL.md").write_bytes(_skill("linkesc", "1.0.0", "links"))
        os.symlink("/nonexist/\x1b[2J\x1b]0;OWNED\x07x",
                   skill / "f\x1b[31mred")
        _commit(hostile_tap, "links")
        boost("update")
        flat = _clean(boost("install", "linkesc"))
        assert ("linkesc: not copied — the link f[31mred → "
                "/nonexist/[2J]0;OWNEDx leads to nothing") in flat

    def test_doctor_names_a_misnamed_store_dir_without_its_escape(self,
                                                                 boost,
                                                                 hostile_tap):
        boost("install", "fields")
        (paths.store_dir() / "st\x1b[31mray").mkdir()
        flat = _clean(boost("doctor", expect=None))
        assert ("~/.agents/skills/st[31mray: boost cannot record a skill "
                "by that name") in flat
        data = json.loads(boost("doctor", "--json", expect=None).out)
        assert any("st\x1b[31mray" in c["message"] for c in data["checks"])
