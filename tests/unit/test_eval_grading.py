"""Unit tests: how the retrieval eval decides a hit is a hit.

Grading was by *name*, and names in this catalogue are not identifying —
measured over 71,655 entries, 35 of the 53 golden target names resolve to more
than one body, and `code-reviewer` alone is 79 copies across 59 distinct
skills. So a query graded against `code-reviewer` scored a hit when any of 59
different skills ranked first, which makes every published number an upper
bound.

These tests pin the fix (an optional per-row `exemplar` that grades by content
class, so mirrors of one skill still count and homonyms do not) *and* the
property that matters more: with no exemplar, grading is byte-for-byte what it
was, so the published baselines stay comparable.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "eval_retrieval.py"

pytestmark = pytest.mark.skipif(
    not _SCRIPT.exists(), reason="repo-root script not reachable")


def _load():
    spec = importlib.util.spec_from_file_location("eval_retrieval", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _entry(name, tap, path):
    return {"name": name, "tap": tap, "skill_md": path}


# Two taps ship `code-reviewer`. Same name, DIFFERENT bodies — the homonym case.
# A third tap mirrors the first byte-for-byte — the mirror case.
HASHES = {
    ("owner/a", "code-reviewer/SKILL.md"): "hash-A",
    ("owner/b", "code-reviewer/SKILL.md"): "hash-B",
    ("owner/c", "code-reviewer/SKILL.md"): "hash-A",     # mirror of owner/a
}
A = _entry("code-reviewer", "owner/a", "code-reviewer/SKILL.md")
B = _entry("code-reviewer", "owner/b", "code-reviewer/SKILL.md")
C = _entry("code-reviewer", "owner/c", "code-reviewer/SKILL.md")
OTHER = _entry("something-else", "owner/a", "something-else/SKILL.md")


class TestNameGradingIsUnchanged:
    """The default must stay identical, or published numbers stop comparing."""

    def test_a_row_without_an_exemplar_grades_by_name(self):
        m = _load()
        row = {"query": "q", "relevant": ["code-reviewer"], "kind": "skill"}
        row = m.prepare_row(row, HASHES)
        assert m.grade_key(row, B, HASHES) == "code-reviewer"
        assert m.relevant_keys(row) == {"code-reviewer"}

    def test_the_wrong_name_is_still_wrong(self):
        m = _load()
        row = m.prepare_row({"query": "q", "relevant": ["code-reviewer"]}, HASHES)
        assert m.grade_key(row, OTHER, HASHES) not in m.relevant_keys(row)


class TestExemplarGradingSeparatesHomonyms:
    def test_the_named_body_counts(self):
        m = _load()
        row = m.prepare_row(
            {"query": "q", "relevant": ["code-reviewer"],
             "exemplar": "owner/a::code-reviewer/SKILL.md"}, HASHES)
        assert m.grade_key(row, A, HASHES) in m.relevant_keys(row)

    def test_a_byte_identical_mirror_still_counts(self):
        # owner/c ships the same body from a different tap. Refusing it would
        # punish a correct answer for arriving from a mirror, which is the
        # failure mode that made name-grading attractive in the first place.
        m = _load()
        row = m.prepare_row(
            {"query": "q", "relevant": ["code-reviewer"],
             "exemplar": "owner/a::code-reviewer/SKILL.md"}, HASHES)
        assert m.grade_key(row, C, HASHES) in m.relevant_keys(row)

    def test_a_different_skill_sharing_the_name_does_not(self):
        # The whole point: owner/b is a *different* code-reviewer.
        m = _load()
        row = m.prepare_row(
            {"query": "q", "relevant": ["code-reviewer"],
             "exemplar": "owner/a::code-reviewer/SKILL.md"}, HASHES)
        assert m.grade_key(row, B, HASHES) not in m.relevant_keys(row)

    def test_distinct_homonyms_get_distinct_keys(self):
        # They must not collide, or recall counts one hit twice.
        m = _load()
        row = m.prepare_row(
            {"query": "q", "relevant": ["code-reviewer"],
             "exemplar": "owner/a::code-reviewer/SKILL.md"}, HASHES)
        assert m.grade_key(row, B, HASHES) != m.grade_key(row, OTHER, HASHES)


class TestExemplarsFailLoudly:
    """A silent fallback to name-grading would hide a typo as a passing gate."""

    def test_an_exemplar_naming_nothing_is_an_error(self):
        m = _load()
        with pytest.raises(SystemExit) as ei:
            m.prepare_row({"query": "q", "relevant": ["code-reviewer"],
                           "exemplar": "owner/a::typo.md"}, HASHES)
        assert "typo.md" in str(ei.value)

    def test_a_malformed_exemplar_is_an_error(self):
        m = _load()
        with pytest.raises(SystemExit):
            m.prepare_row({"query": "q", "relevant": ["x"],
                           "exemplar": "no-separator"}, HASHES)


class TestDedupeKeepsTheBestRank:
    def test_repeats_collapse_to_first_occurrence(self):
        m = _load()
        assert m.dedupe_keys(["a", "b", "a", "c"]) == ["a", "b", "c"]

    def test_mirrors_collapse_under_exemplar_grading(self):
        # A and C are the same body; counting both would inflate recall.
        m = _load()
        row = m.prepare_row(
            {"query": "q", "relevant": ["code-reviewer"],
             "exemplar": "owner/a::code-reviewer/SKILL.md"}, HASHES)
        keys = m.dedupe_keys([m.grade_key(row, e, HASHES) for e in (A, C, B)])
        assert len(keys) == 2
