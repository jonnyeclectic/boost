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


# ── clean / compact ──────────────────────────────────────────────────────

class TestCleanCompactJson:
    def test_clean_reports_items_with_path_kind_and_bytes(self, boost, sandbox):
        from boost_cli.core import paths
        # A cache file for a tap that is not configured is exactly what clean
        # sweeps, and it has a size worth reporting.
        paths.ensure_dirs()
        stale = paths.cache_dir() / "gone-tap.json"
        stale.write_text('{"entries": []}', encoding="utf-8")

        d = _payload(boost("clean", "--json"))
        assert d["ok"] is True and d["removed"] == 1
        row = d["items"][0]
        assert row["kind"] == "stale tap cache" and row["bytes"] > 0
        assert row["path"].endswith("gone-tap.json")
        assert not stale.exists()

    def test_clean_dry_run_reports_the_same_rows_and_removes_nothing(
            self, boost, sandbox):
        from boost_cli.core import paths
        paths.ensure_dirs()
        stale = paths.cache_dir() / "gone-tap.json"
        stale.write_text('{"entries": []}', encoding="utf-8")

        d = _payload(boost("clean", "--dry-run", "--json"))
        assert d["dry_run"] is True and d["count"] == 1 and d["removed"] == 0
        assert stale.exists(), "a dry run must not delete anything"

    def test_clean_on_a_tidy_machine_is_an_empty_document_not_silence(
            self, boost, sandbox):
        d = _payload(boost("clean", "--json"))
        assert d["items"] == [] and d["count"] == 0 and d["ok"] is True

    def test_compact_reports_per_tap_rows(self, boost, tapped):
        d = _payload(boost("compact", "--dry-run", "--json"))
        assert d["dry_run"] is True and isinstance(d["taps"], list)
        assert d["ok"] is True


# ── log / changelog ──────────────────────────────────────────────────────

class TestLogJson:
    def test_activity_events_are_verbatim_with_their_fields(
            self, boost, tapped):
        """The prose listing drops the `key=value` fields `pulse --json` shows
        over the same journal, and `log` is the command reached for first."""
        boost("install", "brainstorming")
        d = _payload(boost("log", "--json"))
        assert d["kind"] == "activity"
        install = [e for e in d["events"] if e.get("action") == "install"]
        assert install and install[0]["subject"] == "brainstorming"

    def test_an_empty_journal_is_an_empty_list(self, boost, sandbox):
        d = _payload(boost("log", "--json"))
        assert d["kind"] == "activity" and d["events"] == []

    def test_crashes_report_their_paths(self, boost, sandbox):
        from boost_cli.core import paths
        paths.ensure_dirs()
        (paths.logs_dir() / "crash-2026-01-01.log").write_text(
            "command: boost doctor\n", encoding="utf-8")
        d = _payload(boost("log", "--crashes", "--json"))
        assert d["kind"] == "crashes"
        assert d["reports"][0]["name"] == "crash-2026-01-01.log"
        assert "boost doctor" in d["reports"][0]["summary"]

    def test_skill_history_rows_are_structured_commits(self, boost, tapped):
        boost("install", "brainstorming")
        d = _payload(boost("log", "brainstorming", "--json"))
        assert d["kind"] == "history" and d["name"] == "brainstorming"
        assert set(d["commits"][0]) == {"sha", "date", "author", "subject"}

    def test_changelog_rows_are_structured_commits(self, boost, tapped):
        boost("install", "brainstorming")
        d = _payload(boost("changelog", "brainstorming", "--json"))
        assert d["name"] == "brainstorming"
        assert set(d["commits"][0]) == {"sha", "date", "author", "subject"}


# ── trending / hooks / quarantine / context ──────────────────────────────

class TestOtherReportsJson:
    def test_trending_names_which_list_it_returned(self, boost, tapped):
        """Curated picks and local install activity answer different
        questions; a consumer that could not tell them apart would read a
        recommendation as something this machine actually installs."""
        d = _payload(boost("trending", "--json"))
        assert d["source"] == "curated"

        boost("install", "brainstorming")
        d = _payload(boost("trending", "--json"))
        assert d["source"] == "installs"
        assert d["items"][0]["name"] == "brainstorming"
        assert d["items"][0]["installs"] == 1
        assert d["items"][0]["kind"] == "skill"

    def test_hooks_list_reports_every_column_plus_the_timeout(
            self, boost, sandbox):
        boost("hooks", "add", "SessionStart", "-c", "echo hi", "-n", "demo",
              "-s", "global", "--timeout", "25")
        d = _payload(boost("hooks", "list", "--json"))
        row = d["hooks"][0]
        assert row["name"] == "demo" and row["command"] == "echo hi"
        assert row["event"] == "SessionStart" and row["scope"] == "global"
        assert row["timeout"] == 25

    def test_hooks_list_empty_is_a_document(self, boost, sandbox):
        assert _payload(boost("hooks", "list", "--json")) == {"hooks": []}

    def test_quarantine_list_carries_a_comparable_timestamp(
            self, boost, tapped):
        """`since` is rendered English; `at` is what it was rendered from, and
        a consumer wants to compare rather than read."""
        boost("install", "brainstorming")
        boost("quarantine", "brainstorming")
        d = _payload(boost("quarantine", "--list", "--json"))
        row = d["quarantined"][0]
        assert row["name"] == "brainstorming" and row["kind"] == "skill"
        assert row["at"] and row["at"].startswith("20")

    def test_bare_context_json_means_context_status_json(self, boost, sandbox):
        """Bare `context` already meant status, and `context status --json`
        already worked — `context --json` was the one spelling rejected."""
        top = _payload(boost("context", "--json"))
        sub = _payload(boost("context", "status", "--json"))
        assert top == sub
        assert "enabled" in top and "branch" in top


# ── bundle install --dry-run ─────────────────────────────────────────────

class TestBundleDryRun:
    def test_it_installs_nothing_and_taps_nothing(self, boost, tapped,
                                                  tmp_path, sandbox):
        bf = tmp_path / "Boostfile"
        bf.write_text("tap other https://example.invalid/other\n"
                      "skill brainstorming\n", encoding="utf-8")

        r = boost("bundle", "install", str(bf), "--dry-run")
        assert "would tap other" in r.out
        assert "would install brainstorming" in r.out

        from boost_cli.core import lockfile, registry
        assert "brainstorming" not in lockfile.installed()
        assert "other" not in {t.name for t in registry.list_taps()}

    def test_it_warns_that_a_rule_would_edit_the_agent_context_file(
            self, boost, tmp_path, fixture_tap_src, sandbox):
        """The reason the flag exists: a bundle install can materialize a rule
        into the file the user reads every session, and had no preview."""
        import shutil
        import subprocess
        dst = tmp_path / "rule-tap"
        shutil.copytree(fixture_tap_src, dst)
        md = dst / "rules" / "house.mdc"
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text("---\nname: house\n---\n\nAlways write tests first.\n",
                      encoding="utf-8")
        subprocess.run(["git", "-C", str(dst), "add", "-A"], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", str(dst), "commit", "-qm", "rule"],
                       check=True, capture_output=True)
        boost("tap", str(dst))

        bf = tmp_path / "Boostfile"
        bf.write_text("skill house\n", encoding="utf-8")
        r = boost("bundle", "install", str(bf), "--dry-run")
        assert "would install house" in r.out and "[rule]" in r.out
        assert "context file" in r.out

        from boost_cli.core import lockfile
        assert "house" not in lockfile.installed_rules()
