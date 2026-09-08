# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/discovery.py — the pure logic behind
`boost index`'s gh-failure hints and zero-result write decision."""
from __future__ import annotations

from boost_cli.core import discovery


class TestGhFailureHint:
    def test_rate_limit_message_gets_the_friendly_hint(self):
        raw = ("gh: API rate limit exceeded for installation ID 12345.\n"
               '{"message": "API rate limit exceeded", "documentation_url": '
               '"https://docs.github.com/rest"}')
        hint = discovery.gh_failure_hint(raw)
        assert hint == ("GitHub rate limit hit — wait a minute or "
                         "authenticate: `gh auth login` / GH_TOKEN")

    def test_bare_http_403_gets_the_friendly_hint(self):
        # No "rate limit" wording at all — a bare 403 is still an auth/quota
        # failure `gh` itself would send the user to `gh auth login` for.
        raw = "gh: Forbidden (HTTP 403)"
        assert discovery.gh_failure_hint(raw) == (
            "GitHub rate limit hit — wait a minute or authenticate: "
            "`gh auth login` / GH_TOKEN")

    def test_gh_auth_login_suggestion_gets_the_friendly_hint(self):
        raw = "gh: To authenticate, please run `gh auth login`."
        assert discovery.gh_failure_hint(raw) == (
            "GitHub rate limit hit — wait a minute or authenticate: "
            "`gh auth login` / GH_TOKEN")

    def test_unrelated_failure_falls_back_to_the_raw_tail(self):
        # A 404 shares no marker with the rate-limit cluster, so the user
        # still sees gh's own specific complaint rather than a wrong hint.
        raw = "gh: Not Found (HTTP 404)"
        assert discovery.gh_failure_hint(raw) == "gh: Not Found (HTTP 404)"

    def test_fallback_keeps_only_the_last_three_lines(self):
        raw = "\n".join("line %d" % i for i in range(1, 8))
        assert discovery.gh_failure_hint(raw) == "line 5\nline 6\nline 7"

    def test_empty_input_falls_back_to_a_generic_hint(self):
        assert discovery.gh_failure_hint("") == "check `gh auth status`"

    def test_whitespace_only_input_falls_back_to_a_generic_hint(self):
        assert discovery.gh_failure_hint("   \n  ") == "check `gh auth status`"


class TestShouldWriteIndex:
    def test_writes_when_there_are_items(self):
        assert discovery.should_write_index(1, index_exists=True) is True
        assert discovery.should_write_index(1, index_exists=False) is True

    def test_writes_an_empty_index_when_none_exists_yet(self):
        assert discovery.should_write_index(0, index_exists=False) is True

    def test_keeps_a_previous_index_on_a_zero_result_run(self):
        assert discovery.should_write_index(0, index_exists=True) is False
