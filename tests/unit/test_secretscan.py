# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/secretscan.py — embedded-secret detection."""
from __future__ import annotations

from boost_cli.core import secretscan


def _ids(findings):
    return [f.rule_id for f in findings]


class TestRuleMatches:
    def test_private_key_block(self):
        got = secretscan.scan_text("-----BEGIN RSA PRIVATE KEY-----")
        assert _ids(got) == ["private-key-block"]
        assert got[0].severity == "high"

    def test_openssh_private_key_block(self):
        assert _ids(secretscan.scan_text(
            "-----BEGIN OPENSSH PRIVATE KEY-----")) == ["private-key-block"]

    def test_aws_access_key_id(self):
        got = secretscan.scan_text("key = AKIAIOSFODNN7EXAMPLE")
        assert "aws-access-key-id" in _ids(got)

    def test_github_token(self):
        tok = "ghp_" + "a" * 36
        assert "github-token" in _ids(secretscan.scan_text("token: " + tok))

    def test_github_fine_grained_pat(self):
        tok = "github_pat_" + "A" * 30
        assert "github-token" in _ids(secretscan.scan_text(tok))

    def test_slack_token(self):
        assert "slack-token" in _ids(
            secretscan.scan_text("xoxb-123456789012-abcdefghijkl"))

    def test_google_api_key(self):
        key = "AIza" + "b" * 35
        assert "google-api-key" in _ids(secretscan.scan_text(key))

    def test_stripe_live_key(self):
        assert "stripe-secret-key" in _ids(
            secretscan.scan_text("sk_live_" + "c" * 20))

    def test_openai_key(self):
        assert "openai-key" in _ids(secretscan.scan_text("sk-" + "d" * 32))

    def test_jwt(self):
        jwt = "eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0NTY.SflKxwRJSMeKKF2QT4"
        assert "jwt" in _ids(secretscan.scan_text(jwt))

    def test_generic_assignment(self):
        got = secretscan.scan_text('api_key = "s3cr3t-value-here"')
        assert "generic-secret-assignment" in _ids(got)
        assert got[0].severity == "medium"

    def test_us_ssn(self):
        assert "us-ssn" in _ids(secretscan.scan_text("SSN: 123-45-6789"))


class TestNonMatches:
    def test_benign_prose_clean(self):
        text = ("# A skill\n\nRuns `pytest` and reports coverage. See the "
                "README for setup.\n")
        assert secretscan.scan_text(text) == []

    def test_short_akia_lookalike_not_matched(self):
        # too short to be a real AWS key id
        assert secretscan.scan_text("AKIA123") == []

    def test_unquoted_assignment_not_matched(self):
        # rule requires a quoted literal to avoid matching prose
        assert secretscan.scan_text("api_key = see the vault") == []

    def test_empty_text(self):
        assert secretscan.scan_text("") == []


class TestRedaction:
    def test_secret_value_never_appears_in_snippet(self):
        leaked = "AKIAIOSFODNN7EXAMPLE"
        got = secretscan.scan_text("aws = " + leaked)
        assert leaked not in got[0].snippet

    def test_snippet_keeps_short_prefix_hint(self):
        got = secretscan.scan_text("aws = AKIAIOSFODNN7EXAMPLE")
        assert "AKIA****" in got[0].snippet

    def test_generic_assignment_value_redacted(self):
        got = secretscan.scan_text('password = "hunter2-very-secret"')
        assert "hunter2-very-secret" not in got[0].snippet
        assert "hunt****" in got[0].snippet

    def test_redact_masks_short_values(self):
        assert secretscan.redact("abcd") == "****"

    def test_redact_keeps_four_char_prefix(self):
        assert secretscan.redact("abcdefghij") == "abcd****"

    def test_private_key_block_group0_redacts_whole_match(self):
        got = secretscan.scan_text("-----BEGIN PRIVATE KEY-----")
        # group 0 = whole match; redaction keeps a 4-char prefix hint
        assert got[0].snippet.startswith("----")
        assert "PRIVATE KEY" not in got[0].snippet


class TestScanMechanics:
    def test_line_numbers_one_based(self):
        text = "clean\nclean\nAKIAIOSFODNN7EXAMPLE"
        got = secretscan.scan_text(text)
        assert got[0].line == 3

    def test_sorted_high_before_medium(self):
        text = 'password = "abcdefgh"\n-----BEGIN PRIVATE KEY-----'
        got = secretscan.scan_text(text)
        assert [f.severity for f in got] == ["high", "medium"]
        assert got[0].rule_id == "private-key-block"

    def test_ties_broken_by_line(self):
        tok = "ghp_" + "a" * 36
        text = "AKIAIOSFODNN7EXAMPLE\n" + tok
        got = secretscan.scan_text(text)
        assert [f.line for f in got] == [1, 2]

    def test_description_populated(self):
        got = secretscan.scan_text("AKIAIOSFODNN7EXAMPLE")
        assert got[0].description


class TestScanFile:
    def test_reads_existing_file(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text("token: ghp_" + "a" * 36, encoding="utf-8")
        assert "github-token" in _ids(secretscan.scan_file(p))

    def test_missing_file_empty(self, tmp_path):
        assert secretscan.scan_file(tmp_path / "nope.md") == []

    def test_directory_path_empty(self, tmp_path):
        assert secretscan.scan_file(tmp_path) == []


class TestWorstSeverity:
    def test_high_wins(self):
        findings = secretscan.scan_text(
            'password = "abcdefgh"\nAKIAIOSFODNN7EXAMPLE')
        assert secretscan.worst_severity(findings) == "high"

    def test_empty_blank(self):
        assert secretscan.worst_severity([]) == ""

    def test_only_medium(self):
        findings = secretscan.scan_text('token = "abcdefgh12"')
        assert secretscan.worst_severity(findings) == "medium"
