# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: whether the keyword index is the corpus or only its labels.

`rag.read_body` degrades to name + description when an item's defining file
cannot be read, and says nothing. That is the ordinary state after
`boost catalog --import`, which restores catalogues with **zero repositories
cloned** — so the index it builds is not the full-content index the `evals`
gate floors at recall@k 0.78. It is a frontmatter index wearing the same file
name, and `boost reindex` reported the same confident "N documents" either way.

The roadmap card `publish-the-keyword-index` measured the gap directly over
3,015 real entries, indexing them with and then without their clones:
**3,041,326 tokens versus 182,507**. A bundle-only index carries **6.0%** of
the searchable text. Nothing in the output said so, which is the same failure
shape as an unpinned eval corpus — a number that still renders confidently
while measuring something else.

So the index now records what it is. `read_body_full` returns the text *and*
whether that text contains the item's body; `build()` counts the documents that
carry only metadata and the tokens they contribute; `index_completeness()`
reads the answer back off disk without re-indexing anything.

The token counts are the honest denominator, not the document counts: an entry
whose body is missing still produces a document, so a doc-share reads 100%
complete right up until it reads 0%, while the token share degrades smoothly.

It does **not** reproduce the card's 6.0%, and an earlier version of this note
said it did. The card's figure is a share of the *corpus* — what the index
would hold if every registry were cloned — and nothing here can compute it,
because the bodies that were never read have no token count to compare
against. `body_share` is a share of *this index's own* tokens, so for the
bundle-only shape it reads 0.0, not 0.06. The two move in opposite directions;
see `TestIndexCompleteness.test_the_share_describes_this_index_not_the_corpus_behind_it`.
"""
from __future__ import annotations

import pytest

from boost_cli.core import rag


def _entry(name, tap="acme/skills", kind="skill", skill_md=None, desc=""):
    return {"name": name, "tap": tap, "kind": kind, "description": desc,
            "skill_md": (skill_md if skill_md is not None else "%s/SKILL.md" % name),
            "rel_dir": name, "curated": False}


class TestReadBodyFull:
    """The seam: one read, two answers."""

    def test_a_readable_file_reports_a_body(self, tmp_path):
        root = tmp_path / "repo"
        (root / "jest").mkdir(parents=True)
        (root / "jest" / "SKILL.md").write_text(
            "---\nname: jest\n---\n\nUnit testing for React.\n", encoding="utf-8")
        text, has_body = rag.read_body_full(
            _entry("jest", skill_md="jest/SKILL.md", desc="a runner"),
            {"acme/skills": root})
        assert has_body is True
        assert "Unit testing for React." in text

    def test_a_named_file_that_is_absent_reports_no_body(self, tmp_path):
        """The bundle-import case: the entry names a file, the clone is gone."""
        text, has_body = rag.read_body_full(
            _entry("ghost", skill_md="ghost/SKILL.md", desc="d"),
            {"acme/skills": tmp_path})
        assert has_body is False
        assert text == "ghost\nd"          # degrades exactly as before

    def test_an_entry_naming_no_file_reports_no_body(self, tmp_path):
        text, has_body = rag.read_body_full(
            _entry("x", skill_md="", desc="d"), {"acme/skills": tmp_path})
        assert has_body is False
        assert text == "x\nd"

    def test_read_body_still_returns_only_the_text(self, tmp_path):
        """`dense` and `boost_langchain` call it; its contract may not move."""
        e = _entry("ghost", skill_md="ghost/SKILL.md", desc="d")
        assert rag.read_body(e, {"acme/skills": tmp_path}) == "ghost\nd"
        assert isinstance(rag.read_body(e, {"acme/skills": tmp_path}), str)


@pytest.fixture()
def two_items(tmp_path, monkeypatch, sandbox):
    """One item with a body on disk, one whose clone is absent."""
    root = tmp_path / "repo"
    (root / "present").mkdir(parents=True)
    (root / "present" / "SKILL.md").write_text(
        "---\nname: present\n---\n\nalpha beta gamma delta epsilon\n",
        encoding="utf-8")
    entries = [_entry("present", skill_md="present/SKILL.md"),
               _entry("absent", skill_md="absent/SKILL.md")]
    monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": root})
    monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
    return root, entries


class TestBuildCountsWhatItCouldNotRead:
    def test_a_fully_cloned_corpus_reports_none_missing(self, two_items):
        _root, entries = two_items
        stats = rag.build([entries[0]])
        assert stats["docs"] == 1
        assert stats["metadata_only"] == 0

    def test_a_bundle_only_corpus_reports_every_document(self, two_items):
        _root, entries = two_items
        stats = rag.build([entries[1]])
        assert stats["docs"] == 1
        assert stats["metadata_only"] == 1

    def test_a_mixed_corpus_reports_the_exact_count(self, two_items):
        _root, entries = two_items
        stats = rag.build(entries)
        assert stats["docs"] == 2
        assert stats["metadata_only"] == 1     # not 0, not 2

    def test_the_count_survives_an_incremental_rebuild(self, two_items,
                                                       monkeypatch):
        """Reused taps keep their answer, or an incremental build under-reports.

        `build()` reuses every tap whose commit is unchanged, so the flag has to
        ride along in the persisted document rather than being recomputed — that
        is why `INDEX_VERSION` moved: a document written before this change
        carries no flag, and reading its absence as "has a body" is a wrong
        answer rather than a missing one.
        """
        _root, entries = two_items
        rag.build(entries)
        again = rag.build(entries)             # same commit -> all reused
        assert again["reused"] == ["acme/skills"]
        assert again["docs"] == 2
        assert again["metadata_only"] == 1


class TestIndexCompleteness:
    def test_no_index_reports_nothing(self, sandbox):
        assert rag.index_completeness() is None

    def test_it_reads_the_answer_back_off_disk(self, two_items):
        _root, entries = two_items
        rag.build(entries)
        got = rag.index_completeness()
        assert got["docs"] == 2
        assert got["metadata_only"] == 1

    def test_the_share_is_of_tokens_not_documents(self, two_items):
        """A token share, not a document share — a doc share reads 50% here."""
        _root, entries = two_items
        rag.build(entries)
        got = rag.index_completeness()
        assert got["tokens"] > got["metadata_only_tokens"] > 0
        assert 0.0 < got["body_share"] < 1.0
        assert got["body_share"] == pytest.approx(
            1.0 - got["metadata_only_tokens"] / got["tokens"])

    def test_the_share_describes_this_index_not_the_corpus_behind_it(
            self, two_items):
        """`body_share` counts the tokens that ARE here, not the ones that
        are missing — and the two move in opposite directions.

        "present" contributes its surface plus a body; "absent" contributes a
        surface alone. So the tokens actually indexed are mostly body text and
        `body_share` is HIGH, even though half the items lost their bodies
        entirely. An earlier comment here asserted the opposite ("well under
        the 0.5 a document-count share would report") and the only assertion
        guarding it was `0.0 < body_share < 1.0`, which every value satisfies —
        so the number was free to mean whatever the caller assumed. It was
        being printed as "this index holds N% of the searchable text", which is
        a share of the CORPUS, and that quantity is not computable here: the
        bodies that were never read have no token count to compare against.

        This pins the direction, which is the part that was never pinned.
        """
        _root, entries = two_items
        rag.build(entries)
        got = rag.index_completeness()
        assert got["body_share"] > 0.5, (
            "the body-bearing item dominates the tokens that were indexed")
        # The corpus share would be far lower than this, and is unknowable.
        # Nothing may present `body_share` as though it were that number.
        assert got["metadata_only_tokens"] < got["tokens"] - got[
            "metadata_only_tokens"]

    def test_a_wholly_metadata_index_reports_a_zero_share(self, two_items):
        _root, entries = two_items
        rag.build([entries[1]])
        got = rag.index_completeness()
        assert got["metadata_only"] == got["docs"] == 1
        assert got["body_share"] == 0.0


class TestTheCountsAccumulateRatherThanLatch:
    """Two bodyless documents, because one cannot tell `+= 1` from `= 1`.

    Every assertion above used a single missing body, which a mutant that
    *assigns* the running total instead of adding to it satisfies exactly. The
    counters are sums over a corpus; the smallest corpus that says so has two.
    """

    def test_two_missing_bodies_are_counted_as_two(self, tmp_path, monkeypatch,
                                                   sandbox):
        root = tmp_path / "repo"
        root.mkdir(parents=True)
        entries = [_entry("gone-a", skill_md="gone-a/SKILL.md", desc="alpha"),
                   _entry("gone-b", skill_md="gone-b/SKILL.md", desc="beta")]
        monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": root})
        monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
        stats = rag.build(entries)
        assert stats["docs"] == 2
        assert stats["metadata_only"] == 2          # not 1

        got = rag.index_completeness()
        assert got["metadata_only"] == 2
        # Both documents' tokens, not just the last one's.
        assert got["metadata_only_tokens"] == got["tokens"]
        assert got["tokens"] == sum(
            d["l"] for d in (rag._load_raw() or {})["docs"])

    def test_the_persisted_flag_is_exactly_one(self, two_items):
        """The index is an artifact other code reads; pin the value, not truth.

        `_save` tests the flag with `bool()`, so any non-zero would behave
        identically today and the stored format could drift silently.
        """
        _root, entries = two_items
        rag.build(entries)
        docs = (rag._load_raw() or {})["docs"]
        flags = [d.get("m") for d in docs]
        assert sorted(f for f in flags if f is not None) == [1]
        # ...and the document that HAS a body carries no key at all, which is
        # what keeps a fully cloned index from paying for the flag.
        assert [d for d in docs if "m" not in d]


class TestAnEmptyIndexClaimsNothing:
    """Zero documents must not read as a complete corpus.

    Every default in `index_completeness` is `or 0`, and every one of them is
    only exercised by an index whose stats are zero or absent. Flipped to `or
    1` they all still satisfy a test built on a real corpus — and the
    `body_share` fallback flipped to 1.0 would report an empty index as
    carrying 100% of its body text, which is the exact class of confidently
    wrong number this whole module exists to remove.
    """

    def test_every_total_is_zero_and_the_share_claims_no_body(self, sandbox):
        rag._save([], {})
        got = rag.index_completeness()
        assert got is not None
        assert got["docs"] == 0
        assert got["metadata_only"] == 0
        assert got["tokens"] == 0
        assert got["metadata_only_tokens"] == 0
        assert got["body_share"] == 0.0          # not 1.0
