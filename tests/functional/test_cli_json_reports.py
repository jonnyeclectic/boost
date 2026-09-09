# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`--json` on the read-only reporting commands.

Eleven of them rejected the flag their group siblings all accept, which left
the commands a machine actually reads — `doctor` is what CI would poll and the
MCP server already exposes a `boost_doctor` tool — offering only prose.

Two properties are asserted for every command here, because both fail quietly:

**The whole of stdout must parse.** Not "contains JSON" — these commands emit
`out.info` chrome, headings and spinners, and one stray line makes the document
unusable for a consumer that by definition is not reading it with their eyes.
So every test does `json.loads(r.out)` on the entire stream.

**The exit code is unchanged and must agree with the payload.** A payload
saying `ok: true` beside a non-zero exit is the one failure a CI consumer
cannot detect for itself.
"""
from __future__ import annotations

import json


def _payload(result):
    """Parse the WHOLE of stdout, so stray chrome fails the test."""
    return json.loads(result.out)


# ── doctor ───────────────────────────────────────────────────────────────

class TestDoctorJson:
    def test_healthy_machine_emits_parseable_json_and_exits_zero(
            self, boost, tapped):
        boost("install", "brainstorming")
        r = boost("doctor", "--json")
        d = _payload(r)
        assert d["ok"] is True and d["issues"] == 0
        assert d["verdict"] == "healthy"
        names = {c["name"] for c in d["checks"]}
        assert {"git", "taps", "lockfile", "skills"} <= names
        assert all(c["status"] in ("ok", "issue", "warn", "info")
                   for c in d["checks"])

    def test_stdout_carries_the_payload_and_nothing_else(self, boost, tapped):
        """The prose run prints a heading and glyph lines; the JSON run must
        print neither, or the document does not parse."""
        boost("install", "brainstorming")
        prose = boost("doctor")
        assert "boost doctor" in prose.out and "✓" in prose.out

        r = boost("doctor", "--json")
        assert "==>" not in r.out and "✓" not in r.out
        _payload(r)  # parses, or the test fails here

    def test_issues_exit_one_and_the_payload_says_so(self, boost, tapped):
        """doctor's contract is `1 if issues else 0`, and --json must not
        change it — a CI gate reads the status before the body."""
        boost("install", "brainstorming")
        # Delete the store directory out from under the lock file: doctor
        # reports a missing skill, which is a real issue.
        from boost_cli.core import store, util
        util.rmtree(store.skill_store_dir("brainstorming"))

        r = boost("doctor", "--json", expect=1)
        d = _payload(r)
        assert d["ok"] is False and d["issues"] >= 1
        assert any(c["status"] == "issue" for c in d["checks"])

    def test_an_untapped_machine_is_not_called_healthy_in_json_either(
            self, boost):
        """The prose path refuses to say "healthy" with no taps configured.
        The payload must carry the same refusal, not a bare `ok: true` a
        consumer would read as a working install."""
        d = _payload(boost("doctor", "--json"))
        assert d["verdict"] is not None and "ready to set up" in d["verdict"]

    def test_a_note_does_not_raise_the_issue_count(self, boost, tapped):
        """Informational rows exist so doctor can mention what boost will not
        fix without going permanently red on it."""
        boost("install", "brainstorming")
        d = _payload(boost("doctor", "--json"))
        assert d["issues"] == sum(1 for c in d["checks"]
                                  if c["status"] == "issue")


# ── test ─────────────────────────────────────────────────────────────────

class TestTestJson:
    def test_rows_carry_the_uncoloured_failed_checks(self, boost, tapped):
        boost("install", "brainstorming")
        d = _payload(boost("test", "--json"))
        assert d["ok"] is True and d["failed"] == 0 and d["passed"] == 1
        row = d["skills"][0]
        assert row["name"] == "brainstorming"
        assert row["ok"] is True and row["failed"] == []
        # The table wraps these in role() escapes; the payload must not.
        assert "\x1b" not in json.dumps(d)

    def test_an_empty_machine_still_emits_a_document(self, boost):
        """The prose path prints "no skills installed" and returns. Emitting
        nothing at all under --json would be indistinguishable from a crash."""
        d = _payload(boost("test", "--json"))
        assert d["skills"] == [] and d["ok"] is True and d["passed"] == 0

    def test_a_failing_skill_exits_one_and_names_its_checks(
            self, boost, tapped):
        boost("install", "brainstorming")
        from boost_cli.core import store
        # Rewrite the body so the recorded sha256 no longer matches: `verify`
        # is the check that fails.
        md = store.skill_store_dir("brainstorming") / "SKILL.md"
        md.write_text(md.read_text(encoding="utf-8") + "\ndrifted\n",
                      encoding="utf-8")

        r = boost("test", "--json", expect=1)
        d = _payload(r)
        assert d["ok"] is False and d["failed"] == 1
        assert "verify" in d["skills"][0]["failed"]


# ── health ───────────────────────────────────────────────────────────────

class TestHealthJson:
    def test_dashboard_rows_become_structured_values(self, boost, tapped):
        boost("install", "brainstorming")
        d = _payload(boost("health", "--json"))
        assert d["skills"] == {"installed": 1, "quarantined": 0, "pinned": 0}
        assert d["taps"]["configured"] == 1
        assert d["status"] == "healthy" and d["ok"] is True

    def test_agent_coverage_is_counts_not_a_painted_glyph(self, boost, tapped):
        """The prose row embeds a role() escape for ✓/!. A consumer parsing
        that would be parsing our palette."""
        boost("install", "brainstorming")
        d = _payload(boost("health", "--json"))
        cov = d["claude-code"]
        assert cov["linked"] == cov["expected"] == 1 and cov["ok"] is True
        assert "\x1b" not in json.dumps(d)

    def test_prose_still_prints_the_dashboard(self, boost, tapped):
        """Both arms of the branch stay exercised — the prose path is the one
        every existing user sees."""
        boost("install", "brainstorming")
        r = boost("health")
        assert "boost health" in r.out
        assert "● healthy" in r.out
