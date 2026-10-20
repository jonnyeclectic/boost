# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/cohort.py.

Pure logic behind `boost cohort apply`'s reporting and `--skills` parsing —
see docs/roadmap/items/audit-cohort-findings.md.
"""
from __future__ import annotations

import pytest

from boost_cli.core import cohort


class TestParseSkills:
    def test_single_comma_list(self):
        assert cohort.parse_skills(["a,b,c"]) == ["a", "b", "c"]

    def test_repeated_flag_appends_rather_than_replaces(self):
        # The bug: argparse's plain default (one string) makes a repeated
        # --skills silently discard every earlier occurrence.
        assert cohort.parse_skills(["a", "b"]) == ["a", "b"]

    def test_repeated_flag_with_comma_lists_combines_both(self):
        assert cohort.parse_skills(["a,b", "c,d"]) == ["a", "b", "c", "d"]

    def test_whitespace_and_empty_entries_are_dropped(self):
        assert cohort.parse_skills([" a , , b "]) == ["a", "b"]

    def test_empty_input_is_empty(self):
        assert cohort.parse_skills([]) == []

    def test_all_blank_input_is_empty(self):
        assert cohort.parse_skills(["", "  ", ",,"]) == []


class TestApplySummary:
    def test_no_missing_keeps_the_original_two_clause_wording(self):
        assert cohort.apply_summary(2, 3, 0) == (
            "applied: 2 installed, 3 already present")

    def test_missing_appends_a_third_clause(self):
        # The exact bug: a missing member used to be accounted for nowhere.
        assert cohort.apply_summary(0, 0, 1) == (
            "applied: 0 installed, 0 already present, 1 not found")

    def test_all_three_present(self):
        assert cohort.apply_summary(1, 2, 3) == (
            "applied: 1 installed, 2 already present, 3 not found")

    def test_counts_are_not_swapped(self):
        summary = cohort.apply_summary(5, 7, 9)
        assert "5 installed" in summary
        assert "7 already present" in summary
        assert "9 not found" in summary


class TestApplyExitCode:
    def test_clean_pass_is_zero(self):
        assert cohort.apply_exit_code(1, 0, 0) == 0
        assert cohort.apply_exit_code(0, 1, 0) == 0
        assert cohort.apply_exit_code(0, 0, 0) == 0

    def test_only_missing_is_one(self):
        # The exact bug: a rollout whose only member was missing from every
        # tap returned 0 — indistinguishable from a clean, uneventful pass.
        assert cohort.apply_exit_code(0, 0, 1) == 1

    def test_missing_alongside_an_install_is_zero(self):
        assert cohort.apply_exit_code(1, 0, 1) == 0

    def test_missing_alongside_a_present_is_zero(self):
        assert cohort.apply_exit_code(0, 1, 1) == 0


class TestShapeError:
    def test_well_formed_map_is_fine(self):
        assert cohort.shape_error({}) is None
        assert cohort.shape_error(
            {"c": {"skills": ["a"], "percent": 0, "created": "x"}}) is None

    def test_non_object_cohort(self):
        assert cohort.shape_error({"c1": "x"}) == (
            "cohort 'c1' is a str, not an object")

    @pytest.mark.parametrize("skills", [None, "a,b", ["a", 1], {"a": 1}])
    def test_skills_must_be_a_list_of_names(self, skills):
        spec = {"percent": 5} if skills is None else {"skills": skills,
                                                       "percent": 5}
        assert cohort.shape_error({"c": spec}) == (
            "cohort 'c' has no list of skill names")

    @pytest.mark.parametrize("percent", [None, "50", 5.0, True])
    def test_percent_must_be_an_integer(self, percent):
        spec = {"skills": []} if percent is None else {"skills": [],
                                                       "percent": percent}
        assert cohort.shape_error({"c": spec}) == (
            "cohort 'c' has no integer percent")

    def test_first_bad_cohort_is_named_after_good_ones(self):
        assert cohort.shape_error({
            "good": {"skills": [], "percent": 1}, "bad": []}) == (
            "cohort 'bad' is a list, not an object")


class TestLoad:
    def test_missing_file_is_no_cohorts(self, tmp_path):
        assert cohort.load(tmp_path / "cohorts.json") == ({}, None)

    def test_valid_file_round_trips(self, tmp_path):
        p = tmp_path / "cohorts.json"
        p.write_text('{"c": {"skills": ["a"], "percent": 50}}',
                     encoding="utf-8")
        assert cohort.load(p) == ({"c": {"skills": ["a"], "percent": 50}},
                                  None)

    def test_shape_error_names_the_file(self, tmp_path):
        p = tmp_path / "cohorts.json"
        p.write_text('{"c1": "x"}', encoding="utf-8")
        assert cohort.load(p) == (
            {}, "%s: cohort 'c1' is a str, not an object" % p)

    @pytest.mark.parametrize("raw", [b"[]", b"{\"a\": 1,}", b"{\"a\": \"\xff\"}"])
    def test_unparseable_file_is_an_error(self, tmp_path, raw):
        p = tmp_path / "cohorts.json"
        p.write_bytes(raw)
        data, err = cohort.load(p)
        assert data == {}
        assert err.startswith("%s: " % p)
