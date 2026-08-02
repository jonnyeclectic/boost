"""Unit tests: how the retrieval eval decides a hit is a hit.

Grading was by *name*, and names in this catalogue are not identifying —
measured over 71,655 entries, 35 of the 53 golden target names resolve to more
than one body, and `code-reviewer` alone is 79 copies across 59 distinct
skills. So a query graded against `code-reviewer` scored a hit when any of 59
different skills ranked first, which makes every published number an upper
bound.

These tests pin the fix (an optional per-row `exemplar` that grades by content
class, so mirrors of one skill still count and homonyms do not) and the property
that a row without an exemplar still grades *relevance* by name, so the golden
sets can migrate a row at a time.

They also pin the second half, which the first pass got wrong. A grade key does
two jobs: it decides whether an entry is relevant, and it is the identity the
ranked list is de-duplicated on. Keying both on the name meant 13 genuinely
different skills called `code-reviewer` collapsed into ONE rank slot — the eval
crediting a ranker for a compression that exists only in the scoring code, and
over the pinned corpus that inflated recall@10 by about one query (0.863 vs
0.852). Exemplar rows had the mirror-image bug: their distractors keyed on
`tap::skill_md`, so byte-identical mirrors of a distractor each took a slot.

Relevance is therefore decided by name (or class), while identity is always the
entry's content hash — one convention for every row, which is what lets an
exemplar-graded row and a name-graded row be averaged into one number.
"""
from __future__ import annotations

import importlib.util
import json
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


class TestIdentityIsTheBodyNotTheName:
    """One de-duplication convention, whether or not the row pins an exemplar."""

    def test_two_different_skills_sharing_a_name_take_two_slots(self):
        # The inflation: owner/a and owner/b are different `code-reviewer`s. A
        # user scrolling results sees two entries, so the eval must too.
        m = _load()
        row = m.prepare_row({"query": "q", "relevant": ["something-else"]}, HASHES)
        assert len(m.dedupe_keys([m.grade_key(row, A, HASHES),
                                  m.grade_key(row, B, HASHES)])) == 2

    def test_a_byte_identical_mirror_takes_one_slot(self):
        # owner/c mirrors owner/a. Counting it twice would punish nothing and
        # reward nothing — it is the same skill arriving from two registries.
        m = _load()
        row = m.prepare_row({"query": "q", "relevant": ["something-else"]}, HASHES)
        assert len(m.dedupe_keys([m.grade_key(row, A, HASHES),
                                  m.grade_key(row, C, HASHES)])) == 1

    def test_distractor_mirrors_collapse_for_an_exemplar_row_too(self):
        # The mirror-image bug: keyed on tap::skill_md, two mirrors of a
        # DISTRACTOR each took a rank slot, pushing the target later.
        m = _load()
        row = m.prepare_row(
            {"query": "q", "relevant": ["code-reviewer"],
             "exemplar": "owner/b::code-reviewer/SKILL.md"}, HASHES)
        assert len(m.dedupe_keys([m.grade_key(row, A, HASHES),
                                  m.grade_key(row, C, HASHES)])) == 1

    def test_a_relevant_entry_is_still_keyed_by_its_name(self):
        # Relevance semantics are unchanged: recall over a multi-name `relevant`
        # list still needs each distinct name found.
        m = _load()
        row = m.prepare_row({"query": "q", "relevant": ["code-reviewer"]}, HASHES)
        assert m.grade_key(row, A, HASHES) == "code-reviewer"

    def test_an_entry_with_no_content_hash_still_gets_a_unique_key(self):
        # Degrade, don't collide: an unhashed entry must not merge with another
        # unhashed one and silently shorten the ranked list.
        m = _load()
        row = m.prepare_row({"query": "q", "relevant": ["x"]}, HASHES)
        one = _entry("p", "owner/z", "p/SKILL.md")
        two = _entry("q", "owner/z", "q/SKILL.md")
        assert m.grade_key(row, one, HASHES) != m.grade_key(row, two, HASHES)


class TestTheWorksheetShowsWhatIsLeftToDecide:
    """Pinning the remaining rows is a judgment, so hand over a menu, not a task.

    28 of the 50 natural-language rows resolved to exactly one body and were
    pinned mechanically. The other 22 do not: `code-reviewer` alone is 13
    different skills here, and their descriptions share a median similarity of
    about 0.15, so there is no "same skill re-published" shortcut to take. The
    menu is generated rather than written into the golden file as a comment, so
    it keeps describing the corpus that is actually tapped instead of rotting.
    """

    def test_an_ambiguous_row_lists_every_candidate_body(self):
        m = _load()
        rows = [m.prepare_row({"query": "q", "relevant": ["code-reviewer"]}, HASHES)]
        sheet = m.exemplar_worksheet(rows, [A, B, C, OTHER], HASHES)
        assert len(sheet) == 1
        specs = {c["spec"] for c in sheet[0]["candidates"]}
        assert specs == {"owner/a::code-reviewer/SKILL.md",
                         "owner/b::code-reviewer/SKILL.md"}

    def test_mirrors_are_one_candidate_not_two(self):
        # owner/c is byte-identical to owner/a; offering both would be offering
        # the same decision twice.
        m = _load()
        rows = [m.prepare_row({"query": "q", "relevant": ["code-reviewer"]}, HASHES)]
        assert m.exemplar_worksheet(rows, [A, C], HASHES) == []

    def test_a_row_that_already_pins_an_exemplar_is_done(self):
        m = _load()
        rows = [m.prepare_row({"query": "q", "relevant": ["code-reviewer"],
                               "exemplar": "owner/a::code-reviewer/SKILL.md"},
                              HASHES)]
        assert m.exemplar_worksheet(rows, [A, B, C], HASHES) == []

    def test_the_shipped_set_has_nothing_left_to_decide(self):
        # This used to guard a 28/22 split: 28 rows whose exemplar was a lookup
        # were pinned, and 22 that needed a judgment were left open. The split
        # is closed — the worksheet is what generated the candidates for those
        # 22, and it should now come back empty for the shipped set.
        path = _ROOT / "tests" / "eval" / "golden-natural.jsonl"
        rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")]
        assert len(rows) == 50
        assert [r["query"] for r in rows if not r.get("exemplar")] == []


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


class TestTheMigrationIsFinished:
    """Every natural-language row now pins its exemplars, and must keep doing so.

    The mechanism shipped in #412 with 28 of 50 rows migrated — the ones whose
    exemplar was a lookup rather than a judgment. The remaining 22 were left
    open deliberately, because choosing which of 13 `code-reviewer`s a question
    refers to is a statement about intent. They are decided now, under a rule
    stated in the file's own header, and this is the ratchet that stops a new
    row arriving name-graded and quietly re-opening the hole.
    """

    _GOLDEN = _ROOT / "tests" / "eval" / "golden-natural.jsonl"

    def _rows(self):
        return [json.loads(ln) for ln in
                self._GOLDEN.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.lstrip().startswith("#")]

    @pytest.mark.skipif(not _GOLDEN.exists(), reason="query set not reachable")
    def test_every_row_pins_an_exemplar(self):
        missing = [r["query"] for r in self._rows() if not r.get("exemplar")]
        assert missing == [], (
            "%d natural-language rows are still graded by name — run "
            "`eval_retrieval.py --golden tests/eval/golden-natural.jsonl "
            "--worksheet` for the candidates: %s" % (len(missing), missing[:3]))

    @pytest.mark.skipif(not _GOLDEN.exists(), reason="query set not reachable")
    def test_every_exemplar_is_well_formed(self):
        # Resolvability needs a materialised corpus and is enforced at run time
        # by prepare_row; the shape can be checked anywhere, so it is.
        for row in self._rows():
            spec = row["exemplar"]
            specs = [spec] if isinstance(spec, str) else spec
            assert specs, row["query"]
            for one in specs:
                assert "::" in one, (row["query"], one)
                tap, path = one.split("::", 1)
                assert "/" in tap and path, (row["query"], one)

    @pytest.mark.skipif(not _GOLDEN.exists(), reason="query set not reachable")
    def test_no_exemplar_is_a_localised_copy(self):
        """The stated rule, enforced rather than trusted.

        The queries are English. `affaan-m/ECC` ships `code-reviewer` and
        `update-docs` in seven languages under `docs/<locale>/`, and a reader
        who asked in English is not served by the Turkish one. Byte-identical
        mirrors still count automatically — they are one content class — so
        this excludes only genuine translations.
        """
        for row in self._rows():
            spec = row["exemplar"]
            for one in ([spec] if isinstance(spec, str) else spec):
                assert "/docs/es/" not in one and "::docs/es/" not in one, one
                assert "/docs/ja-JP/" not in one and "::docs/ja-JP/" not in one, one
                assert "::docs/zh-CN/" not in one and "::docs/zh-TW/" not in one, one
                assert "::docs/ko-KR/" not in one and "::docs/pt-BR/" not in one, one
                assert "::docs/tr/" not in one, one


class TestASupersededBaselineIsDropped:
    """A baseline key is `name@digest`, so an edited query set orphans the old one.

    The digest can only recur if someone reverts the file byte for byte, so a
    superseded entry is never read again — it is dead weight that accumulates
    one row per edit. Pinning the 22 rows produced the first one, so the save
    path now prunes.
    """

    def test_an_older_digest_of_the_same_set_is_stale(self):
        m = _load()
        keys = ["golden.jsonl@aaa", "golden-natural.jsonl@old",
                "golden-natural.jsonl@new"]
        assert m.stale_keys(keys, "golden-natural.jsonl@new") == [
            "golden-natural.jsonl@old"]

    def test_other_query_sets_are_left_alone(self):
        # The whole point of the keyed layout: one set's re-baseline must not
        # touch another's history.
        m = _load()
        keys = ["golden.jsonl@aaa", "golden-natural.jsonl@old"]
        assert "golden.jsonl@aaa" not in m.stale_keys(
            keys, "golden-natural.jsonl@new")

    def test_the_key_being_written_is_never_stale(self):
        m = _load()
        assert m.stale_keys(["a.jsonl@x"], "a.jsonl@x") == []

    def test_a_name_containing_an_at_sign_is_split_on_the_last_one(self):
        # Splitting on the first `@` would read "odd@name.jsonl@new" as the set
        # "odd", quietly matching — and deleting — an unrelated baseline.
        m = _load()
        keys = ["odd@name.jsonl@old", "name.jsonl@old"]
        assert m.stale_keys(keys, "odd@name.jsonl@new") == ["odd@name.jsonl@old"]
