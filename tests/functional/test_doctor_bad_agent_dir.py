# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional: one unresolvable agent dir is an issue row, not a dead report.

`paths.expand` refuses `${VAR}` with no fallback and nothing in the
environment, and `agents.known_agents` expands every row — so on main one bad
`agents.<name>.dir` made `boost doctor` exit 1 after printing the lock line,
with no verdict and, under `--json`, no JSON at all. Every guarded section is
reached only with something installed, so the fixture installs one of each
kind: drop any one `agents_ok` guard and these tests crash on that call.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from boost_cli.core import config

RULE = "house-rule"
WORKFLOW = "ship-it"
KEY = "agents.cursor.dir"


@pytest.fixture()
def trio(boost, fixture_tap_src, tmp_path, monkeypatch):
    """A sandbox with a skill, a rule and a workflow installed."""
    monkeypatch.delenv("BOOST_TEST_NOPE", raising=False)
    tap = tmp_path / "trio-tap"
    shutil.copytree(fixture_tap_src, tap)
    (tap / "rules").mkdir()
    (tap / "rules" / "house.mdc").write_text(
        "---\nname: %s\nversion: 1.0.0\n---\n\nAlways test.\n" % RULE,
        encoding="utf-8")
    (tap / "commands").mkdir()
    (tap / "commands" / ("%s.md" % WORKFLOW)).write_text(
        "---\nname: %s\nversion: 1.0.0\n---\n\nShip it.\n" % WORKFLOW,
        encoding="utf-8")
    subprocess.run(["git", "-C", str(tap), "add", "-A"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tap), "commit", "-qm", "trio"],
                   check=True, capture_output=True)
    for argv in (("tap", tap), ("install", "brainstorming"),
                 ("install", RULE), ("install", WORKFLOW)):
        boost(*argv)
    return boost


def _break_cursor(value="${BOOST_TEST_NOPE}/skills"):
    cfg = config.load()
    cfg["agents"]["cursor"]["dir"] = value
    config.save(cfg)


class TestDoctorText:
    def test_names_the_key_and_still_reaches_the_verdict(self, trio):
        _break_cursor()
        res = trio("doctor", expect=1)
        out = " ".join(res.out.split())   # undo the pane wrap
        assert "%s: BOOST_TEST_NOPE is not set" % KEY in out
        assert "`boost config set %s <dir>`" % KEY in out
        assert "${BOOST_TEST_NOPE:-<default>}" in out
        assert "doctor skipped its link, materialization and agent-dir " \
               "checks" in out
        # Checks after the first agent lookup still ran: the summary and a
        # verdict that counts exactly the one issue.
        assert "1 skill installed" in out
        assert "links not checked" in out
        assert "1 issue needs attention" in out
        assert "lock file parses" in out

    def test_skipped_checks_claim_nothing(self, trio):
        _break_cursor()
        out = " ".join(trio("doctor", expect=1).out.split())
        assert "links not checked" in out   # the report really got this far
        # Both lines assert what the skipped sections would have measured.
        assert "with agent links" not in out
        assert "fully materialized" not in out
        assert "0 broken links" not in out

    def test_resolvable_config_runs_every_check(self, trio):
        # The other direction of the same predicate: a fallback resolves, so
        # nothing is skipped and the machine reads healthy.
        _break_cursor("${BOOST_TEST_NOPE:-~/.cursor}/skills")
        trio("sync")
        out = " ".join(trio("doctor").out.split())
        assert "agents.cursor.dir" not in out
        assert "with agent links" in out
        assert "fully materialized" in out
        assert "0 broken links" in out
        assert "healthy" in out

    def test_the_named_remedy_clears_it(self, trio):
        _break_cursor()
        trio("doctor", expect=1)
        trio("config", "set", KEY, "${BOOST_TEST_NOPE:-~/.cursor}/skills")
        assert KEY not in trio("doctor").out


class TestDoctorJson:
    def test_emits_json_with_the_issue_row(self, trio):
        _break_cursor()
        res = trio("doctor", "--json", expect=1)
        doc = json.loads(res.out)
        rows = [c for c in doc["checks"] if c["name"] == "agent-config"]
        assert len(rows) == 1
        assert rows[0]["status"] == "issue"
        assert rows[0]["message"].startswith(KEY + ": ")
        assert doc["issues"] == 1


class TestMcpDoctor:
    def test_names_the_key_and_counts_it(self, trio):
        from boost_cli.commands import configuration
        _break_cursor()
        text, is_err = configuration._mcp_tool("boost_doctor", {})
        assert is_err is True
        assert "%s: BOOST_TEST_NOPE is not set" % KEY in text
        assert "installed skills: 1" in text
        # Not `boost sync`: sync refuses on the same row.
        assert "1 issue(s) — run `boost doctor` for details" in text

    def test_resolvable_config_reports_no_agent_row(self, trio):
        from boost_cli.commands import configuration
        text, _is_err = configuration._mcp_tool("boost_doctor", {})
        assert "agents.cursor.dir" not in text
