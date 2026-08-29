# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""A crash report is the one file users are invited to paste into a bug report.

`_env_snapshot` captured every ``BOOST_*`` variable verbatim, and boost's own
documented way to supply a key is ``BOOST_ANTHROPIC_API_KEY`` — so the variable
most likely to be set was also the one most likely to be secret. Three reports
on a real machine carried a live ``sk-ant-api03-...`` key in cleartext.
"""
from __future__ import annotations

import pytest

from boost_cli.core import logs


class TestEnvSnapshotRedaction:
    SECRET = "sk-ant-api03-" + "x" * 80

    @pytest.mark.parametrize("var", [
        "BOOST_ANTHROPIC_API_KEY",
        "BOOST_OPENAI_API_KEY",
        "BOOST_VOYAGE_API_KEY",
        "BOOST_GITHUB_TOKEN",
        "BOOST_REGISTRY_SECRET",
        "BOOST_TAP_PASSWORD",
    ])
    def test_secret_value_never_appears(self, var, monkeypatch):
        monkeypatch.setenv(var, self.SECRET)
        body = "\n".join(logs._env_snapshot())
        assert self.SECRET not in body
        assert var in body, "the variable is still worth reporting — only its value is not"

    def test_redaction_is_marked_not_silently_dropped(self, monkeypatch):
        monkeypatch.setenv("BOOST_ANTHROPIC_API_KEY", self.SECRET)
        line = next(x for x in logs._env_snapshot() if x.startswith("BOOST_ANTHROPIC_API_KEY"))
        # A dropped line reads as "unset", which sends a bug reporter down the
        # wrong path. Say the value was withheld.
        assert "REDACTED" in line

    def test_non_secret_values_survive(self, monkeypatch):
        monkeypatch.setenv("BOOST_ASSUME_YES", "1")
        monkeypatch.setenv("BOOST_NO_AI", "1")
        body = "\n".join(logs._env_snapshot())
        assert "BOOST_ASSUME_YES=1" in body
        assert "BOOST_NO_AI=1" in body

    def test_crash_report_on_disk_carries_no_secret(self, monkeypatch, sandbox):
        monkeypatch.setenv("BOOST_ANTHROPIC_API_KEY", self.SECRET)
        report = logs.write_crash_report(RuntimeError("boom"), ["install", "x"])
        assert report is not None
        assert self.SECRET not in report.read_text(encoding="utf-8")

    def test_a_secret_by_value_shape_is_caught_whatever_its_name(self, monkeypatch):
        # Name-matching alone is a denylist and will always trail the next
        # variable someone adds. A value that is unmistakably a key is redacted
        # on its shape too.
        monkeypatch.setenv("BOOST_SOMETHING_HARMLESS_SOUNDING", self.SECRET)
        body = "\n".join(logs._env_snapshot())
        assert self.SECRET not in body
