# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/imperative.py — shared normative-rule extractor."""
from __future__ import annotations

from boost_cli.core import imperative


class TestRuleRe:
    def test_matches_each_modal(self):
        for modal in ("Always", "Never", "Must", "Must not", "Do not",
                      "Don't", "don't"):
            assert imperative.RULE_RE.match(modal + " do the thing"), modal

    def test_captures_modal_and_rest(self):
        m = imperative.RULE_RE.match("Never commit secrets")
        assert m.group(1).lower() == "never"
        assert m.group(2) == " commit secrets"

    def test_tolerates_leading_list_marker(self):
        for lead in ("- ", "* ", "+ ", "> ", "1. ", "2) "):
            assert imperative.RULE_RE.match(lead + "always run tests"), lead

    def test_must_not_captured_as_two_words(self):
        m = imperative.RULE_RE.match("must not skip review")
        assert m.group(1).lower() == "must not"

    def test_non_rule_line_returns_none(self):
        assert imperative.RULE_RE.match("This is just prose.") is None

    def test_word_boundary_rejects_musttache(self):
        # "mustache" must not match the "must" modal (\b boundary)
        assert imperative.RULE_RE.match("mustache growing tips") is None

    def test_match_helper_mirrors_rule_re(self):
        assert imperative.match("always x") is not None
        assert imperative.match("nope") is None


class TestNormRule:
    def test_lowercases_first_char(self):
        assert imperative.norm_rule("Always run tests") == "always run tests"

    def test_strips_emphasis_markers(self):
        assert imperative.norm_rule("**Always** run `tests`") == \
            "always run tests"

    def test_strips_trailing_period(self):
        assert imperative.norm_rule("Never skip.") == "never skip"

    def test_empty_stays_empty(self):
        assert imperative.norm_rule("") == ""
        assert imperative.norm_rule("   ") == ""

    def test_only_first_char_lowercased(self):
        # an embedded acronym keeps its case; only the leading char changes
        assert imperative.norm_rule("Always use TDD") == "always use TDD"


class TestImperativeRules:
    def test_extracts_and_normalizes_rules(self):
        body = ("# Rules\n\n- Always run the suite.\n- Never force-push.\n"
                "Some prose here.\n")
        assert imperative.imperative_rules(body) == [
            "always run the suite", "never force-push"]

    def test_numbered_step_becomes_follow(self):
        body = "1. Write a failing test first\n2. Make it pass\n"
        assert imperative.imperative_rules(body) == [
            "follow: write a failing test first", "follow: make it pass"]

    def test_numbered_single_word_ignored(self):
        # a one-word numbered item is not a meaningful rule
        assert imperative.imperative_rules("1. Go\n") == []

    def test_deduplicates_preserving_order(self):
        body = "- Always test.\n- Always test.\n- Never skip.\n"
        assert imperative.imperative_rules(body) == [
            "always test", "never skip"]

    def test_rule_line_beats_follow_when_both_apply(self):
        # a numbered line that is ALSO a rule normalizes as a rule, not follow:
        assert imperative.imperative_rules("1. Always run tests\n") == [
            "always run tests"]

    def test_empty_body(self):
        assert imperative.imperative_rules("") == []

    def test_non_rule_prose_yields_nothing(self):
        assert imperative.imperative_rules("Just some notes.\nMore notes.") == []


class TestParityWithOldBehavior:
    """Lock the exact strings the simulate/explain functional tests depend on."""

    def test_tdd_style_fixture_rules(self):
        body = ("- Never write production code without a failing test.\n"
                "- Always run the full suite before committing.\n"
                "1. Write a failing test first. Watch it fail.\n")
        assert imperative.imperative_rules(body) == [
            "never write production code without a failing test",
            "always run the full suite before committing",
            "follow: write a failing test first. Watch it fail"]
