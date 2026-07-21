"""Unit tests: boost_cli/core/typosquat.py — edit distance & name confusion."""
from __future__ import annotations

from typing import ClassVar

from boost_cli.core import typosquat


class TestEditDistance:
    def test_identical_is_zero(self):
        assert typosquat.edit_distance("brainstorm", "brainstorm") == 0

    def test_single_substitution(self):
        assert typosquat.edit_distance("cat", "cot") == 1

    def test_single_insertion(self):
        assert typosquat.edit_distance("cat", "cart") == 1

    def test_single_deletion(self):
        assert typosquat.edit_distance("cart", "cat") == 1

    def test_transposition_costs_two(self):
        # Levenshtein (no adjacent-swap rule) scores a swap as two edits
        assert typosquat.edit_distance("ab", "ba") == 2

    def test_symmetric(self):
        assert (typosquat.edit_distance("kitten", "sitting", cap=5)
                == typosquat.edit_distance("sitting", "kitten", cap=5))

    def test_classic_kitten_sitting_is_three(self):
        assert typosquat.edit_distance("kitten", "sitting", cap=9) == 3

    def test_empty_strings(self):
        assert typosquat.edit_distance("", "") == 0
        assert typosquat.edit_distance("", "abc", cap=5) == 3

    def test_cap_returns_sentinel_when_farther(self):
        # true distance is 3; with cap=1 we only learn "> cap" as cap + 1
        assert typosquat.edit_distance("abcde", "xyzde", cap=1) == 2

    def test_length_gap_shortcut(self):
        # length difference alone exceeds the cap -> sentinel, no DP needed
        assert typosquat.edit_distance("a", "aaaaaa", cap=2) == 3

    def test_true_distance_returned_within_cap(self):
        assert typosquat.edit_distance("foo", "foobar", cap=5) == 3


class TestConfusableNames:
    NAMES: ClassVar[list] = ["brainstorm", "brainstorms", "brainstom", "commit", "unrelated"]

    def test_finds_distance_one_only_by_default(self):
        got = typosquat.confusable_names("brainstorm", self.NAMES)
        assert got == ["brainstom", "brainstorms"]  # both 1 edit away

    def test_exact_match_excluded(self):
        assert "brainstorm" not in typosquat.confusable_names(
            "brainstorm", self.NAMES)

    def test_distance_two_needs_higher_max(self):
        # "brainstrom" is 2 edits from "brainstorm" (swap) -> hidden at max 1
        cands = ["brainstrom", "brainstorm"]
        assert typosquat.confusable_names("brainstorm", cands) == []
        assert typosquat.confusable_names(
            "brainstorm", cands, max_distance=2) == ["brainstrom"]

    def test_case_insensitive(self):
        assert typosquat.confusable_names("Commit", ["commiy"]) == ["commiy"]

    def test_deduplicates_case_variants(self):
        assert typosquat.confusable_names("cat", ["cot", "COT"]) == ["cot"]

    def test_sorted_by_distance_then_name(self):
        # "care" is 2 from "cat"; "bat"/"cot" are 1 -> closest first, then a-z
        got = typosquat.confusable_names("cat", ["cot", "bat", "care"],
                                         max_distance=2)
        assert got == ["bat", "cot", "care"]

    def test_empty_candidates(self):
        assert typosquat.confusable_names("cat", []) == []


def _e(name, tap):
    return {"name": name, "tap": tap}


class TestFindConfusions:
    def test_same_name_different_tap_flagged(self):
        target = _e("deploy", "alice/skills")
        entries = [target, _e("deploy", "mallory/evil")]
        got = typosquat.find_confusions(target, entries)
        assert [x["tap"] for x in got] == ["mallory/evil"]

    def test_near_name_different_tap_flagged(self):
        target = _e("deploy", "alice/skills")
        got = typosquat.find_confusions(
            target, [target, _e("deployy", "mallory/evil")])
        assert [x["name"] for x in got] == ["deployy"]

    def test_same_tap_never_flagged(self):
        target = _e("deploy", "alice/skills")
        # a sibling one edit away in the SAME tap is not a confusion
        got = typosquat.find_confusions(
            target, [target, _e("deployy", "alice/skills")])
        assert got == []

    def test_target_identity_excluded(self):
        target = _e("deploy", "alice/skills")
        assert typosquat.find_confusions(target, [target]) == []

    def test_far_name_not_flagged(self):
        target = _e("deploy", "alice/skills")
        got = typosquat.find_confusions(
            target, [target, _e("something-else", "mallory/evil")])
        assert got == []

    def test_respects_max_distance(self):
        target = _e("deploy", "alice/skills")
        entries = [target, _e("deproy", "x/y")]  # 1 edit
        assert len(typosquat.find_confusions(target, entries)) == 1
        assert typosquat.find_confusions(
            target, [target, _e("depployy", "x/y")]) == []  # 2 edits, max 1

    def test_sorted_by_distance_then_name_then_tap(self):
        target = _e("deploy", "alice/skills")
        entries = [
            target,
            _e("deployy", "z/last"),     # dist 1
            _e("deploy", "a/first"),     # dist 0 -> should come first
            _e("deploy", "m/mid"),       # dist 0
        ]
        got = typosquat.find_confusions(target, entries)
        assert [(x["name"], x["tap"]) for x in got] == [
            ("deploy", "a/first"), ("deploy", "m/mid"), ("deployy", "z/last")]
