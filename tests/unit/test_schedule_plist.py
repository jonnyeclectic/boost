# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/commands/configuration._plist_interval_seconds.

Pure parsing helper behind `boost schedule status`'s launchd branch — see
docs/roadmap/items/audit-schedule-findings.md. A zero or missing
StartInterval used to render "every None" and, worse, hang the next-run loop
forever; this pins the parser's answer for every shape that loop depends on.
"""
from __future__ import annotations

import plistlib
import sys
from pathlib import Path

import pytest

from boost_cli.commands.configuration import (
    _cron_entry,
    _plist_body,
    _plist_interval_seconds,
    _read_plist,
)

_WRAP = "<?xml version=\"1.0\"?><plist><dict>%s</dict></plist>"


def _plist(body: str) -> str:
    return _WRAP % body


class TestPlistIntervalSeconds:
    def test_normal_interval(self):
        assert _plist_interval_seconds(
            _plist("<key>StartInterval</key><integer>43200</integer>")) == 43200

    def test_missing_key(self):
        assert _plist_interval_seconds(
            _plist("<key>Label</key><string>com.boost.sync</string>")) is None

    def test_zero_interval_is_unusable(self):
        # The bug: a next-run loop that advances by `secs` never catches up
        # to `now` when `secs` is 0, so this must come back None, not 0.
        assert _plist_interval_seconds(
            _plist("<key>StartInterval</key><integer>0</integer>")) is None

    def test_negative_interval_is_unusable(self):
        assert _plist_interval_seconds(
            _plist("<key>StartInterval</key><integer>-5</integer>")) is None

    def test_empty_text(self):
        assert _plist_interval_seconds("") is None

    def test_invalid_xml(self):
        # An unescaped '&' — what raw %s interpolation used to write.
        assert _plist_interval_seconds(
            _plist("<key>StartInterval</key><integer>60</integer>"
                   "<key>X</key><string>R&D</string>")) is None

    def test_non_integer_interval_is_unusable(self):
        assert _plist_interval_seconds(
            _plist("<key>StartInterval</key><true/>")) is None
        assert _plist_interval_seconds(
            _plist("<key>StartInterval</key><string>60</string>")) is None


class TestReadPlist:
    def test_valid_dict(self):
        assert _read_plist(_plist("<key>A</key><integer>1</integer>")) == {"A": 1}

    def test_invalid_xml_is_none(self):
        assert _read_plist(_plist("<key>A</key><string>R&D</string>")) is None

    def test_empty_is_none(self):
        assert _read_plist("") is None

    def test_non_dict_root_is_none(self):
        assert _read_plist("<plist><array/></plist>") is None


class TestPlistBody:
    """The job must act on the state it was enabled from, in a valid file."""

    def test_round_trips_with_env_and_ampersand_paths(self, monkeypatch, tmp_path):
        home = tmp_path / "R&D <home>"
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("BOOST_HOME", str(home / "custom-boost"))
        shim = home / "bin" / "boost"
        data = plistlib.loads(_plist_body(shim, 86400).encode("utf-8"))
        log = str(home / "custom-boost" / "logs" / "schedule.log")
        assert data == {
            "Label": "com.boost.sync",
            "ProgramArguments": [str(shim), "update"],
            "EnvironmentVariables": {"BOOST_HOME": str(home / "custom-boost"),
                                     "HOME": str(home)},
            "StartInterval": 86400,
            "StandardOutPath": log,
            "StandardErrorPath": log,
        }
        assert _plist_interval_seconds(_plist_body(shim, 86400)) == 86400


# The expected lines spell POSIX paths and shell quoting; cron is a POSIX
# backend, and on Windows str(Path("/x")) is a backslashed path that
# shlex.quote then wraps.
@pytest.mark.skipif(sys.platform == "win32", reason="cron entries are POSIX")
class TestCronEntry:
    def test_env_prefix_and_quoting(self, monkeypatch, tmp_path):
        home = tmp_path / "R&D 50%"
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("BOOST_HOME", str(home / "b"))
        q = "'%s" % home  # shlex.quote wraps a path holding a space
        q = q.replace("%", "\\%")
        assert _cron_entry("0 6 * * *", Path("/opt/boost")) == (
            "0 6 * * * BOOST_HOME=%s/b' HOME=%s' /opt/boost update >> "
            "%s/b/logs/schedule.log' 2>&1 # boost-sync" % (q, q, q))

    def test_plain_paths_are_unquoted(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", "/h")
        monkeypatch.setenv("BOOST_HOME", "/h/.boost")
        assert _cron_entry("0 */6 * * *", Path("/x/boost")) == (
            "0 */6 * * * BOOST_HOME=/h/.boost HOME=/h /x/boost update >> "
            "/h/.boost/logs/schedule.log 2>&1 # boost-sync")
