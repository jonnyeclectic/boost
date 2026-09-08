# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/commands/configuration._plist_interval_seconds.

Pure parsing helper behind `boost schedule status`'s launchd branch — see
docs/roadmap/items/audit-schedule-findings.md. A zero or missing
StartInterval used to render "every None" and, worse, hang the next-run loop
forever; this pins the parser's answer for every shape that loop depends on.
"""
from __future__ import annotations

from boost_cli.commands.configuration import _plist_interval_seconds

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
