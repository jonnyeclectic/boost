# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for core.rag — full-content BM25 retrieval (Phase 1).

Covers tokenizing, chunking, body extraction, index build (incl. commit-keyed
incremental refresh), BM25 ranking, the LLM rerank + its degradations, and the
`search`/`ready` seam. `rag.py` lives in core/, so these are mutation-gated;
the assertions pin the scoring math and every fallback branch.
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
from pathlib import Path
from unittest import mock

import pytest

from boost_cli.core import dense as dense_mod
from boost_cli.core import rag, registry

# ------------------------------------------------------------- tokenize

class TestTokenize:
    def test_lowercases_and_splits_on_non_alnum(self):
        assert rag.tokenize("Quick, Brown_Fox!") == ["quick", "brown", "fox"]

    def test_drops_stopwords(self):
        assert rag.tokenize("how can you test this") == ["test"]

    def test_drops_single_chars_but_keeps_two(self):
        assert rag.tokenize("a b2 c dd") == ["b2", "dd"]

    def test_empty(self):
        assert rag.tokenize("") == []


# ------------------------------------------------------------- chunk

class TestChunk:
    def test_empty_and_whitespace(self):
        assert rag.chunk("") == []
        assert rag.chunk("   \n  ") == []

    def test_short_text_is_one_chunk(self):
        assert rag.chunk("hello world", size=100) == ["hello world"]

    def test_packs_paragraphs_up_to_size(self):
        out = rag.chunk("aaaa\n\nbbbb", size=100)
        assert out == ["aaaa\nbbbb"]

    def test_splits_when_over_size_and_carries_overlap(self):
        out = rag.chunk("aaaa\n\nbbbb", size=6, overlap=2)
        assert out[0] == "aaaa"
        assert out[-1].endswith("bbbb")
        assert out[-1].startswith("aa")  # 2-char overlap tail of prev chunk

    def test_hard_splits_oversized_paragraph_with_overlap(self):
        out = rag.chunk("0123456789", size=4, overlap=1)
        assert out == ["0123", "3456", "6789"]

    def test_respects_cap(self):
        text = "\n\n".join("p%d" % i for i in range(50))
        assert len(rag.chunk(text, size=2, overlap=0, cap=3)) == 3

    def test_cap_hit_mid_hard_split(self):
        assert len(rag.chunk("0123456789", size=2, overlap=0, cap=2)) == 2


# ------------------------------------------------------------- read_body

def _entry(name, tap="acme/skills", kind="skill", skill_md=None, desc=""):
    return {"name": name, "tap": tap, "kind": kind, "description": desc,
            "skill_md": (skill_md if skill_md is not None else "%s/SKILL.md" % name),
            "rel_dir": name, "curated": False}


class TestReadBody:
    def test_strips_frontmatter_and_prepends_header(self, tmp_path):
        root = tmp_path / "repo"
        (root / "jest").mkdir(parents=True)
        (root / "jest" / "SKILL.md").write_text(
            "---\nname: jest\nsecretkey: hush\n---\n\nUnit testing for React.\n", encoding="utf-8")
        e = _entry("jest", skill_md="jest/SKILL.md", desc="a runner")
        body = rag.read_body(e, {"acme/skills": root})
        assert body.startswith("jest\na runner")
        assert "Unit testing for React." in body
        assert "secretkey" not in body  # frontmatter dropped

    def test_missing_file_degrades_to_header(self, tmp_path):
        e = _entry("ghost", skill_md="ghost/SKILL.md", desc="d")
        body = rag.read_body(e, {"acme/skills": tmp_path})
        assert body == "ghost\nd"

    def test_no_skill_md_returns_header_only(self, tmp_path):
        e = _entry("x", skill_md="", desc="d")
        assert rag.read_body(e, {"acme/skills": tmp_path}) == "x\nd"

    def test_unknown_tap_falls_back_to_repos_dir(self, sandbox):
        # no tap_paths mapping -> resolves under repos_dir()/<safe tap>
        e = _entry("y", tap="who/what", skill_md="y/SKILL.md", desc="d")
        assert rag.read_body(e, {}) == "y\nd"  # file absent -> header


class TestEntryPath:
    """rag.entry_path() — the one place an entry becomes a real path.

    `read_body` resolved this inline and kept the answer to itself, so a caller
    that wanted the *location* rather than the *bytes* had nothing to call. That
    gap is how `boost_langchain`'s Document metadata came to advertise the
    tap-relative `skill_md` as an openable `source`. Extracting it makes the one
    correct join reusable; every branch is pinned because core/ is mutation-gated.
    """

    def test_joins_the_tap_root_and_the_relative_path(self, tmp_path):
        e = _entry("jest", skill_md="jest/SKILL.md")
        assert rag.entry_path(e, {"acme/skills": tmp_path}) == (
            tmp_path / "jest" / "SKILL.md")

    def test_resolves_without_the_file_existing(self, tmp_path):
        # Pure path math, deliberately: a caller reporting provenance wants the
        # location the catalog claims even when the clone has since been pruned.
        # read_body's own missing-file degrade stays its business, not this one's.
        p = rag.entry_path(_entry("ghost"), {"acme/skills": tmp_path})
        assert p == tmp_path / "ghost" / "SKILL.md"
        assert not p.exists()

    def test_unknown_tap_falls_back_to_the_sanitized_repos_dir(self, sandbox):
        from boost_cli.core import paths
        e = _entry("y", tap="who/what", skill_md="y/SKILL.md")
        assert rag.entry_path(e, {}) == (
            paths.repos_dir() / "who__what" / "y" / "SKILL.md")

    def test_empty_skill_md_is_none(self, tmp_path):
        # None rather than the bare tap root: a directory is not where the item
        # is, and returning one would hand callers a path that opens the wrong
        # thing instead of an absence they must handle.
        assert rag.entry_path(_entry("x", skill_md=""),
                              {"acme/skills": tmp_path}) is None

    def test_absent_skill_md_key_is_none(self, tmp_path):
        assert rag.entry_path({"name": "x", "tap": "acme/skills"},
                              {"acme/skills": tmp_path}) is None

    def test_defaults_to_the_live_tap_map(self, sandbox, monkeypatch, tmp_path):
        monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": tmp_path})
        assert rag.entry_path(_entry("j", skill_md="j/SKILL.md")) == (
            tmp_path / "j" / "SKILL.md")

    def test_an_entry_with_no_tap_looks_up_the_empty_name(self, tmp_path):
        # A row missing `tap` entirely degrades to the empty tap name rather
        # than to None — so a map that *has* an empty-named entry still resolves
        # it. Pins the lookup default: None or any other sentinel would silently
        # divert this row to the repos_dir fallback below.
        assert rag.entry_path({"name": "x", "skill_md": "x/SKILL.md"},
                              {"": tmp_path}) == tmp_path / "x" / "SKILL.md"

    def test_an_entry_with_no_tap_falls_back_to_repos_dir_itself(self, sandbox):
        # Same missing `tap`, but nothing in the map: the sanitized-name join
        # gets the empty string, so the base is repos_dir() exactly. Pins the
        # second default — "None" or any placeholder would invent a directory
        # level that is not there.
        from boost_cli.core import paths
        assert rag.entry_path({"name": "x", "skill_md": "x/SKILL.md"}, {}) == (
            paths.repos_dir() / "x" / "SKILL.md")

    def test_read_body_reads_the_file_entry_path_names(self, tmp_path):
        """The two must not drift: same entry, same file."""
        (tmp_path / "jest").mkdir(parents=True)
        e = _entry("jest", skill_md="jest/SKILL.md", desc="a runner")
        rag.entry_path(e, {"acme/skills": tmp_path}).write_text(
            "---\nname: jest\n---\n\nUnit testing for React.\n", encoding="utf-8")
        assert "Unit testing for React." in rag.read_body(
            e, {"acme/skills": tmp_path})


# ------------------------------------------------------------- build/query

@pytest.fixture()
def corpus(tmp_path, monkeypatch, sandbox):
    """Two on-disk items + patched tap plumbing; returns (root, entries)."""
    root = tmp_path / "repo"
    items = {
        "jest-runner": "Unit testing for JavaScript and React components with jest.",
        "pytest-helper": "Python testing framework with fixtures and parametrize.",
    }
    entries = []
    for name, body in items.items():
        (root / name).mkdir(parents=True)
        (root / name / "SKILL.md").write_text(
            "---\nname: %s\n---\n\n%s\n" % (name, body), encoding="utf-8")
        entries.append(_entry(name, skill_md="%s/SKILL.md" % name))
    monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": root})
    monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
    return root, entries


class TestEnsure:
    """rag.ensure() — build-on-first-use so BM25 is the default everywhere."""

    def test_returns_true_without_building_when_ready(self, monkeypatch):
        monkeypatch.setattr(rag, "ready", lambda: True)
        monkeypatch.setattr(rag, "stale", lambda: False)
        monkeypatch.setattr(rag, "build", lambda *a, **k:
                            pytest.fail("must not build when already ready"))
        assert rag.ensure() is True

    def test_rebuilds_a_ready_but_stale_index(self, monkeypatch):
        """An index that exists but predates a tap change must be rebuilt.

        The regression: ensure() short-circuited on ready() alone, so after
        `boost tap X` search kept answering from the pre-X index forever.
        """
        state = {"built": 0}
        monkeypatch.setattr(rag, "ready", lambda: True)
        monkeypatch.setattr(rag, "stale", lambda: True)
        monkeypatch.setattr(registry, "list_taps", lambda: ["a-tap"])
        monkeypatch.setattr(rag, "build",
                            lambda *a, **k: state.__setitem__("built",
                                                              state["built"] + 1))
        assert rag.ensure() is True
        assert state["built"] == 1

    def test_returns_false_without_taps(self, monkeypatch):
        monkeypatch.setattr(rag, "ready", lambda: False)
        monkeypatch.setattr(registry, "list_taps", lambda: [])
        monkeypatch.setattr(rag, "build", lambda *a, **k:
                            pytest.fail("must not build without taps"))
        assert rag.ensure() is False

    def test_builds_when_index_missing(self, monkeypatch):
        state = {"ready": False, "built": 0}
        monkeypatch.setattr(rag, "ready", lambda: state["ready"])
        monkeypatch.setattr(registry, "list_taps", lambda: ["a-tap"])

        def _build(*a, **k):
            state["built"] += 1
            state["ready"] = True
        monkeypatch.setattr(rag, "build", _build)
        assert rag.ensure() is True
        assert state["built"] == 1

    def test_returns_false_when_build_raises(self, monkeypatch):
        monkeypatch.setattr(rag, "ready", lambda: False)
        monkeypatch.setattr(registry, "list_taps", lambda: ["a-tap"])

        def _boom(*a, **k):
            raise RuntimeError("disk full")
        monkeypatch.setattr(rag, "build", _boom)
        assert rag.ensure() is False


class _StatTap:
    """A tap whose cache_file reports a mtime we control."""

    def __init__(self, name, mtime=None):
        self.name = name
        self.safe_name = name.replace("/", "__")
        self._mtime = mtime

    @property
    def cache_file(self):
        mtime = self._mtime

        class _F:
            @staticmethod
            def stat():
                if mtime is None:
                    raise OSError("no cache file")
                return os.stat_result(
                    (0, 0, 0, 0, 0, 0, 0, 0, int(mtime), 0))
        return _F


class TestStale:
    """rag.stale() — the index must notice the taps moving under it.

    ready() answers "does an index exist", which is a different question, and
    conflating them meant `boost tap X` then `boost search` reported no matches
    for a skill `boost info X` described from the same machine.
    """

    def _fix(self, monkeypatch, *, stored, taps, built_at=100.0):
        monkeypatch.setattr(rag, "_load_raw", lambda: {"commits": stored})
        monkeypatch.setattr(rag.registry, "list_taps", lambda: list(taps))

        class _P:
            @staticmethod
            def stat():
                return os.stat_result((0, 0, 0, 0, 0, 0, 0, 0,
                                       int(built_at), 0))
        monkeypatch.setattr(rag, "index_path", lambda: _P)

    def test_missing_index_is_stale(self, monkeypatch):
        monkeypatch.setattr(rag, "_load_raw", lambda: None)
        assert rag.stale() is True

    def test_unchanged_taps_are_not_stale(self, monkeypatch):
        self._fix(monkeypatch, stored={"a__b": "c1"},
                  taps=[_StatTap("a/b", mtime=50)])
        assert rag.stale() is False

    def test_added_tap_is_stale(self, monkeypatch):
        # The reported bug: a brand-new tap need not touch any existing cache,
        # so only the tap *set* betrays it.
        self._fix(monkeypatch, stored={"a__b": "c1"},
                  taps=[_StatTap("a/b", mtime=50), _StatTap("x/y", mtime=50)])
        assert rag.stale() is True

    def test_removed_tap_is_stale(self, monkeypatch):
        # An untap deletes a cache rather than touching one, so mtimes alone
        # would never see it — the set comparison is what catches this.
        self._fix(monkeypatch, stored={"a__b": "c1", "x__y": "c2"},
                  taps=[_StatTap("a/b", mtime=50)])
        assert rag.stale() is True

    def test_cache_newer_than_index_is_stale(self, monkeypatch):
        # Same tap set, but that tap's contents moved and were re-cached.
        self._fix(monkeypatch, stored={"a__b": "c1"},
                  taps=[_StatTap("a/b", mtime=101)], built_at=100.0)
        assert rag.stale() is True

    def test_cache_exactly_as_old_as_index_is_fresh(self, monkeypatch):
        # Strictly-newer, not >=: build() writes the index after the caches it
        # consumed, so equal mtimes are the normal post-build state. Treating
        # them as stale would rebuild the index on every single search.
        self._fix(monkeypatch, stored={"a__b": "c1"},
                  taps=[_StatTap("a/b", mtime=100)], built_at=100.0)
        assert rag.stale() is False

    def test_unreadable_index_mtime_is_stale(self, monkeypatch):
        monkeypatch.setattr(rag, "_load_raw", lambda: {"commits": {}})
        monkeypatch.setattr(rag.registry, "list_taps", lambda: [])

        class _P:
            @staticmethod
            def stat():
                raise OSError("gone")
        monkeypatch.setattr(rag, "index_path", lambda: _P)
        assert rag.stale() is True

    def test_tap_without_a_cache_file_is_not_stale(self, monkeypatch):
        # A tap that has never been cached cannot be *newer* than the index;
        # build() picks it up regardless, so this must not force a rebuild on
        # every search.
        self._fix(monkeypatch, stored={"a__b": "c1"},
                  taps=[_StatTap("a/b", mtime=None)])
        assert rag.stale() is False

    def test_null_commits_key_is_stale_only_via_tap_set(self, monkeypatch):
        # An index written without commits reads as "no taps recorded".
        monkeypatch.setattr(rag, "_load_raw", lambda: {"commits": None})
        monkeypatch.setattr(rag.registry, "list_taps",
                            lambda: [_StatTap("a/b", mtime=1)])
        assert rag.stale() is True

    def test_fresh_after_a_real_build(self, corpus, monkeypatch):
        # The end-to-end shape: a real build writing a real index and its real
        # postings must leave something that reports itself current, or every
        # search pays for a rebuild. `corpus` fakes _tap_commits but not
        # list_taps, so the tap set has to be made to agree with it here.
        _root, entries = corpus
        monkeypatch.setattr(rag.registry, "list_taps",
                            lambda: [_StatTap("acme/skills", mtime=None)])
        rag.build(entries=entries, force=True)
        assert rag.ready() is True
        assert rag.stale() is False


class TestBuildAndRetrieve:
    def test_ready_false_before_build(self, sandbox):
        assert rag.ready() is False
        assert rag.retrieve("anything") == []
        assert rag.search("anything") is None

    def test_build_then_retrieve_ranks_by_body(self, corpus):
        _root, entries = corpus
        stats = rag.build(entries=entries, force=True)
        assert stats["entries"] == 2
        assert stats["docs"] >= 2
        assert rag.ready() is True

        hits = rag.retrieve("react component testing", entries=entries)
        assert hits[0]["entry"]["name"] == "jest-runner"
        assert hits[0]["score"] > 0
        assert "jest" in hits[0]["snippet"].lower()

    def test_retrieve_blank_query_returns_empty(self, corpus):
        _root, entries = corpus
        rag.build(entries=entries, force=True)
        assert rag.retrieve("the and of", entries=entries) == []

    def test_kind_filter(self, corpus):
        _root, entries = corpus
        entries[1]["kind"] = "rule"  # pytest-helper becomes a rule
        rag.build(entries=entries, force=True)
        names = {h["entry"]["name"]
                 for h in rag.retrieve("testing", kind="skill", entries=entries)}
        assert names == {"jest-runner"}

    def test_retrieve_skips_entries_absent_from_live_set(self, corpus):
        _root, entries = corpus
        rag.build(entries=entries, force=True)
        # query with only the surviving entry in the live set
        only = [entries[0]]
        hits = rag.retrieve("testing", entries=only)
        assert {h["entry"]["name"] for h in hits} <= {"jest-runner"}

    def test_k_caps_results(self, corpus):
        _root, entries = corpus
        rag.build(entries=entries, force=True)
        assert len(rag.retrieve("testing", k=1, entries=entries)) == 1

    def test_snippet_centers_on_match_past_the_head(
            self, tmp_path, monkeypatch, sandbox):
        # the matched terms sit well past the chunk's first 200 chars: the old
        # head-only snip would miss them; the windowed passage must surface them.
        root = tmp_path / "repo"
        filler = "intro paragraph about setup and config. " * 8   # ~320 chars
        body = filler + "\n\nThe kubernetes operator reconciles pods."
        (root / "k8s").mkdir(parents=True)
        (root / "k8s" / "SKILL.md").write_text(
            "---\nname: k8s\n---\n\n%s\n" % body, encoding="utf-8")
        e = _entry("k8s", skill_md="k8s/SKILL.md")
        monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": root})
        monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
        rag.build(entries=[e], force=True)
        hits = rag.retrieve("kubernetes operator", entries=[e])
        assert hits
        snip = hits[0]["snippet"]
        assert "kubernetes" in snip.lower()          # centered, not the head
        assert snip.startswith("…")                   # head was trimmed away
        assert len(snip) <= rag.SNIP_WIDTH + 2        # windowed, not whole chunk


@pytest.fixture()
def stem_corpus(tmp_path, monkeypatch, sandbox):
    """A corpus with deliberately paired singular/plural vocabulary.

    `pattern` AND `patterns` both exist as terms, which is what lets the
    never-expand-an-existing-token invariant be tested: a build that dropped
    that guard would expand `pattern` to `patterns` and change a query that
    already worked.
    """
    root = tmp_path / "stems"
    items = {
        "alpha": "pattern matching for structured logs.",
        "beta": "patterns and antipatterns in distributed systems.",
        "gamma": "webhook delivery retries.",
        "delta": "webhooks and callbacks delivery.",
        "epsilon": "delivered payloads and receipts to analyze.",
    }
    entries = []
    for name, body in items.items():
        (root / name).mkdir(parents=True)
        (root / name / "SKILL.md").write_text(
            "---\nname: %s\n---\n\n%s\n" % (name, body), encoding="utf-8")
        entries.append(_entry(name, skill_md="%s/SKILL.md" % name))
    monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": root})
    monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
    rag.build(entries=entries, force=True)
    return entries


class TestStemExpansions:
    """`boost search brainstorm` found nothing while `brainstorming` found the
    skill: `tokenize` is exact-match, so a query term and its own inflection are
    unrelated strings. Measured over the 461 tap caches on one real machine,
    4,663 of 29,607 item names (15.7%) were unreachable by an attested stem —
    `pattern` missed 474 names ending `-patterns`, `skill` missed 252.
    """

    def test_a_term_that_has_postings_is_never_expanded(self, stem_corpus):
        """The invariant the whole design rests on.

        Expansion may only ever add signal where there was exactly none, which
        is what makes it unable to move a ranking that already worked — and so
        unable to move the eval floors. `pattern` and `patterns` both exist
        here, so a build that dropped the guard would rewrite `pattern` into
        `patterns` and this fails.
        """
        assert rag.stem_expansions(["pattern"]) == {}
        assert rag.stem_expansions(["webhook"]) == {}
        assert rag.stem_expansions(["pattern", "webhook", "delivery"]) == {}

    def test_only_the_missing_term_of_a_mixed_query_is_expanded(self, stem_corpus):
        assert rag.stem_expansions(["pattern", "callback"]) == {
            "callback": "callbacks"}

    def test_picks_the_commonest_expansion_not_the_first_alphabetically(
            self, stem_corpus):
        """`delivery` is in two documents and `delivered` in one, and
        `delivered` sorts first — so ordering by document count is the only way
        to land on `delivery`."""
        assert rag.stem_expansions(["deliver"]) == {"deliver": "delivery"}

    @pytest.mark.parametrize("term,expected", [
        ("cal", {}),                       # 3 chars: below the floor
        ("call", {"call": "callbacks"}),   # 4 chars: exactly at it
        ("callb", {"callb": "callbacks"}),
    ])
    def test_the_minimum_term_length_boundary(self, stem_corpus, term, expected):
        """Short prefixes expand to noise, so there is a floor; these pin it at
        exactly 4, which a mutant moving it either way breaks."""
        assert rag.stem_expansions([term]) == expected

    def test_a_term_whose_next_character_is_z_is_still_found(self, stem_corpus):
        """`z` is the highest character `tokenize` can emit, so an upper bound
        of ``term + "z"`` silently excludes exactly the terms that continue
        with one — `analy` would never reach `analyze`. The bound is `~`,
        which sorts above every character a token can contain.
        """
        assert rag.stem_expansions(["analy"]) == {"analy": "analyze"}

    def test_a_term_that_prefixes_nothing_stays_missing(self, stem_corpus):
        assert rag.stem_expansions(["zzzznothing"]) == {}

    def test_the_upper_bound_does_not_leak_past_the_prefix(self, stem_corpus):
        """`camel` sorts after `call` but is not a `call`-prefixed term, so a
        range whose upper bound is wrong would drag in neighbours."""
        assert rag.stem_expansions(["calm"]) == {}

    def test_no_postings_file_yields_no_expansions(self, sandbox):
        assert rag.stem_expansions(["callback"]) == {}

    def test_duplicate_terms_are_asked_once_and_answered_once(self, stem_corpus):
        assert rag.stem_expansions(["callback", "callback"]) == {
            "callback": "callbacks"}


class TestRetrieveUsesStemExpansions:
    def test_a_singular_query_reaches_the_plural_item(self, stem_corpus):
        """The reported symptom, in miniature: `callbacks` is indexed, the user
        types `callback`, and before this the answer was nothing at all."""
        hits = rag.retrieve("callback", entries=stem_corpus)
        assert [h["entry"]["name"] for h in hits] == ["delta"]

    def test_the_snippet_highlights_the_term_that_actually_matched(
            self, stem_corpus):
        hits = rag.retrieve("callback", entries=stem_corpus)
        assert "callbacks" in hits[0]["snippet"].lower()

    def test_a_query_whose_terms_all_exist_is_untouched(self, stem_corpus):
        names = [h["entry"]["name"]
                 for h in rag.retrieve("pattern", entries=stem_corpus)]
        assert names == ["alpha"]      # not beta, which owns `patterns`

    def test_a_mixed_query_keeps_the_existing_term_and_fixes_the_other(
            self, stem_corpus):
        names = {h["entry"]["name"]
                 for h in rag.retrieve("pattern callback", entries=stem_corpus)}
        assert names == {"alpha", "delta"}

    def test_a_query_that_matches_nothing_at_all_still_returns_nothing(
            self, stem_corpus):
        assert rag.retrieve("zzzznothing", entries=stem_corpus) == []


class TestBm25Math:
    """Pin the exact BM25 arithmetic (k1=1.2, b=0.75) so formula mutants die."""

    def test_default_avg_when_stats_absent(self):
        # raw with no "stats" -> avg defaults to 1.0 (kills `.get("stats", None)`)
        raw = {"docs": [{"l": 2}], "postings": {"x": [[0, 1]]}}
        idf = math.log(1 + (1 - 1 + 0.5) / (1 + 0.5))
        denom = 1 + 1.2 * (1 - 0.75 + 0.75 * 2 / 1.0)
        expected = idf * (1 * (1.2 + 1)) / denom
        assert rag._bm25(["x"], raw, raw["postings"])[0] == pytest.approx(expected)

    def test_avg_len_floor_is_one(self):
        # avg_len 0.0 must floor to 1.0, not 2.0
        raw = {"docs": [{"l": 2}], "stats": {"avg_len": 0.0},
               "postings": {"x": [[0, 1]]}}
        idf = math.log(1 + (1 - 1 + 0.5) / (1 + 0.5))
        denom = 1 + 1.2 * (1 - 0.75 + 0.75 * 2 / 1.0)
        expected = idf * (1 * (1.2 + 1)) / denom
        assert rag._bm25(["x"], raw, raw["postings"])[0] == pytest.approx(expected)

    def test_zero_length_doc_floors_to_one_exactly(self):
        # dl floors to 1 (not 2) when the stored length is 0
        raw = {"docs": [{"l": 0}], "stats": {"avg_len": 1.0},
               "postings": {"x": [[0, 3]]}}
        idf = math.log(1 + (1 - 1 + 0.5) / (1 + 0.5))
        denom = 3 + 1.2 * (1 - 0.75 + 0.75 * 1 / 1.0)
        expected = idf * (3 * (1.2 + 1)) / denom
        assert rag._bm25(["x"], raw, raw["postings"])[0] == pytest.approx(expected)

    def test_exact_scores(self):
        raw = {
            "docs": [{"l": 2}, {"l": 4}],
            "stats": {"avg_len": 3.0},
            "postings": {"react": [[0, 1]], "test": [[0, 1], [1, 2]]},
        }
        scores = rag._bm25(["react", "test"], raw, raw["postings"])
        idf_r = math.log(1 + (2 - 1 + 0.5) / (1 + 0.5))
        idf_t = math.log(1 + (2 - 2 + 0.5) / (2 + 0.5))
        denom0 = 1 + 1.2 * (1 - 0.75 + 0.75 * 2 / 3.0)   # dl=2
        denom1 = 2 + 1.2 * (1 - 0.75 + 0.75 * 4 / 3.0)   # dl=4, tf=2
        exp0 = idf_r * (1 * (1.2 + 1)) / denom0 + idf_t * (1 * (1.2 + 1)) / denom0
        exp1 = idf_t * (2 * (1.2 + 1)) / denom1
        assert scores[0] == pytest.approx(exp0)
        assert scores[1] == pytest.approx(exp1)

    def test_absent_term_scores_nothing(self):
        raw = {"docs": [{"l": 3}], "stats": {"avg_len": 3.0},
               "postings": {"react": [[0, 1]]}}
        assert dict(rag._bm25(["missing"], raw, raw["postings"])) == {}

    def test_zero_length_doc_uses_floor(self):
        raw = {"docs": [{"l": 0}], "stats": {"avg_len": 0.0},
               "postings": {"x": [[0, 1]]}}
        # must not ZeroDivisionError (dl and avg both floor to 1)
        assert rag._bm25(["x"], raw, raw["postings"])[0] > 0


class TestIncremental:
    def test_reuses_unchanged_tap(self, corpus, monkeypatch):
        _root, entries = corpus
        first = rag.build(entries=entries, force=True)
        # same commit -> the tap is reused, nothing reindexed
        second = rag.build(entries=entries)
        assert second["reused"] == ["acme__skills"]
        assert second["reindexed"] == []
        assert second["docs"] == first["docs"]
        # index still queryable after a reuse-only rebuild
        assert rag.retrieve("python fixtures", entries=entries)

    def test_commit_change_forces_reindex(self, corpus, monkeypatch):
        _root, entries = corpus
        rag.build(entries=entries, force=True)
        monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c2"})
        stats = rag.build(entries=entries)
        assert stats["reused"] == []
        assert stats["reindexed"] == ["acme/skills"]

    def test_force_ignores_cached_commit(self, corpus):
        _root, entries = corpus
        rag.build(entries=entries, force=True)
        stats = rag.build(entries=entries, force=True)
        assert stats["reused"] == []


# ------------------------------------------------------------- rerank

def _hit(name, score, snippet="s", kind="skill", desc="d"):
    return {"entry": {"name": name, "kind": kind, "description": desc},
            "score": score, "snippet": snippet}


class TestRerank:
    def test_no_ai_returns_bm25_order(self, monkeypatch, sandbox):
        monkeypatch.setattr(rag.ai, "available", lambda: False)
        hits = [_hit("a", 2.0), _hit("b", 1.0)]
        out, label = rag.rerank("q", hits, limit=5)
        assert [h["entry"]["name"] for h in out] == ["a", "b"]
        assert label == "BM25 full-content"

    def test_ai_reorders(self, monkeypatch, sandbox):
        monkeypatch.setattr(rag.ai, "available", lambda: True)
        monkeypatch.setattr(rag.ai, "ask", lambda *a, **k: '["b", "a"]')
        hits = [_hit("a", 2.0), _hit("b", 1.0)]
        out, label = rag.rerank("q", hits, limit=5)
        assert [h["entry"]["name"] for h in out] == ["b", "a"]
        assert label == "Claude relevance"

    def test_ai_partial_order_appends_rest(self, monkeypatch, sandbox):
        monkeypatch.setattr(rag.ai, "available", lambda: True)
        monkeypatch.setattr(rag.ai, "ask", lambda *a, **k: '["b"]')
        hits = [_hit("a", 2.0), _hit("b", 1.0)]
        out, _label = rag.rerank("q", hits, limit=5)
        assert [h["entry"]["name"] for h in out] == ["b", "a"]

    def test_ai_garbage_reply_degrades(self, monkeypatch, sandbox):
        monkeypatch.setattr(rag.ai, "available", lambda: True)
        monkeypatch.setattr(rag.ai, "ask", lambda *a, **k: "no json here")
        hits = [_hit("a", 2.0), _hit("b", 1.0)]
        out, label = rag.rerank("q", hits, limit=5)
        assert [h["entry"]["name"] for h in out] == ["a", "b"]
        assert label == "BM25 full-content"

    def test_limit_truncates(self, monkeypatch, sandbox):
        monkeypatch.setattr(rag.ai, "available", lambda: False)
        hits = [_hit("a", 3.0), _hit("b", 2.0), _hit("c", 1.0)]
        out, _ = rag.rerank("q", hits, limit=2)
        assert len(out) == 2

    def test_prompt_carries_task_and_candidate_snippets(self, monkeypatch, sandbox):
        captured = {}
        monkeypatch.setattr(rag.ai, "available", lambda: True)

        def fake_ask(prompt, *a, **k):
            captured["prompt"] = prompt
            return '["a", "b"]'
        monkeypatch.setattr(rag.ai, "ask", fake_ask)
        hits = [_hit("a", 2.0, snippet="alpha-snippet"),
                _hit("b", 1.0, snippet="beta-snippet")]
        rag.rerank("find-the-widget", hits, limit=5)
        p = captured["prompt"]
        assert "find-the-widget" in p          # task threaded in
        assert "alpha-snippet" in p            # snippet (not just name) fed in
        assert "beta-snippet" in p


def _wire_live_catalog(monkeypatch, entries):
    """Serve ``entries`` as the machine's live catalogue for ``entries=None``.

    The fast path sources from ``registry.list_taps()`` + ``catalog.load_tap``
    (never the whole catalogue); its vanished-entry fallback still reads
    ``all_entries``. Wire all three seams so either route sees the same data.
    """
    from boost_cli.core import registry
    taps = sorted({e["tap"] for e in entries})
    monkeypatch.setattr(registry, "list_taps",
                        lambda: [registry.Tap(name=t, url="") for t in taps])
    monkeypatch.setattr(
        rag.catalog, "load_tap",
        lambda tap, rebuild=False: [e for e in entries if e["tap"] == tap.name])
    monkeypatch.setattr(rag.catalog, "all_entries", lambda: entries)


class TestSearchSeam:
    def test_search_none_without_index(self, sandbox):
        assert rag.search("x") is None

    def test_search_smart_false_returns_bm25(self, corpus, monkeypatch):
        _root, entries = corpus
        rag.build(entries=entries, force=True)
        _wire_live_catalog(monkeypatch, entries)
        result = rag.search("testing", limit=5, smart=False)
        assert result is not None
        hits, label = result
        assert label == "BM25 full-content"
        assert hits

    def test_search_smart_degrades_without_ai(self, corpus, monkeypatch):
        _root, entries = corpus
        rag.build(entries=entries, force=True)
        _wire_live_catalog(monkeypatch, entries)
        monkeypatch.setattr(rag.ai, "available", lambda: False)
        _hits, label = rag.search("testing", limit=5)
        assert label == "BM25 full-content"

    def test_search_smart_is_default_and_uses_ai(self, corpus, monkeypatch):
        _root, entries = corpus
        rag.build(entries=entries, force=True)
        _wire_live_catalog(monkeypatch, entries)
        monkeypatch.setattr(rag.ai, "available", lambda: True)
        monkeypatch.setattr(rag.ai, "ask",
                            lambda *a, **k: '["pytest-helper", "jest-runner"]')
        hits, label = rag.search("testing")          # no smart= -> defaults True
        assert label == "Claude relevance"
        assert hits[0]["entry"]["name"] == "pytest-helper"

    def test_search_default_limit_caps_at_10(self, tmp_path, monkeypatch, sandbox):
        root = tmp_path / "repo"
        entries = []
        for i in range(12):
            name = "item%d" % i
            (root / name).mkdir(parents=True)
            (root / name / "SKILL.md").write_text(
                "---\nname: %s\n---\n\ntesting common utility %d\n" % (name, i), encoding="utf-8")
            entries.append(_entry(name, skill_md="%s/SKILL.md" % name))
        monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": root})
        monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
        _wire_live_catalog(monkeypatch, entries)
        monkeypatch.setattr(rag.ai, "available", lambda: False)
        rag.build(entries=entries, force=True)
        hits, _label = rag.search("testing common")   # default limit == 10
        assert len(hits) == 10


# ------------------------------------------------------------- helpers

class TestJsonArray:
    def test_extracts_array(self):
        assert rag._json_array('prefix ["x", "y"] suffix') == ["x", "y"]

    def test_extracts_multiline_array(self):
        # requires the re.S flag — a mutant dropping it returns None
        assert rag._json_array('[\n  "x",\n  "y"\n]') == ["x", "y"]

    def test_none_when_no_array(self):
        assert rag._json_array("just text") is None
        assert rag._json_array("") is None

    def test_none_on_bad_json(self):
        assert rag._json_array("[oops") is None

    def test_none_when_not_a_list(self):
        assert rag._json_array('{"a": 1}') is None


class TestTapPlumbing:
    def test_tap_commits_reads_cache_then_head(self, sandbox, monkeypatch):
        taps = [registry.Tap(name="acme/x", url="u")]
        monkeypatch.setattr(rag.registry, "list_taps", lambda: taps)
        from boost_cli.core import paths
        paths.ensure_dirs()
        taps[0].cache_file.write_text(json.dumps({"commit": "abc123"}), encoding="utf-8")
        assert rag._tap_commits() == {"acme__x": "abc123"}

    def test_tap_paths_maps_name_to_repo_dir(self, sandbox, monkeypatch):
        from boost_cli.core import paths
        taps = [registry.Tap(name="acme/x", url="u")]
        monkeypatch.setattr(rag.registry, "list_taps", lambda: taps)
        assert rag._tap_paths() == {"acme/x": paths.repos_dir() / "acme__x"}


# =====================================================================
# Mutation-hardening: the tests below pin exact outputs of every helper
# so structural / off-by-one / string / kwarg mutants are all killed.
# =====================================================================


class _Cache:
    def __init__(self, text):
        self._text = text

    def read_text(self, encoding=None):
        if self._text is None:
            raise OSError("no cache file")
        return self._text


class _FakeTap:
    def __init__(self, name, cache_text=None, is_cloned=False):
        self.name = name
        self.safe_name = name.replace("/", "__")
        self.path = "/repos/" + self.safe_name
        self.is_cloned = is_cloned
        self.cache_file = _Cache(cache_text)


class TestTapCommitsStates:
    def test_no_cache_no_clone_is_empty_string(self, monkeypatch):
        # a real "" (not None / "XXXX") when nothing is known
        monkeypatch.setattr(rag.registry, "list_taps",
                            lambda: [_FakeTap("a/b")])
        assert rag._tap_commits() == {"a__b": ""}

    def test_blank_cache_commit_stays_empty(self, monkeypatch):
        monkeypatch.setattr(rag.registry, "list_taps",
                            lambda: [_FakeTap("a/b", cache_text='{"commit": ""}')])
        assert rag._tap_commits() == {"a__b": ""}

    def test_cache_commit_wins_over_head_when_present(self, monkeypatch):
        tap = _FakeTap("a/b", cache_text='{"commit": "CACHE"}', is_cloned=True)
        monkeypatch.setattr(rag.registry, "list_taps", lambda: [tap])
        monkeypatch.setattr(rag.gitutil, "head_commit",
                            lambda p: "HEAD" if p == tap.path else "WRONG")
        # `not commit and is_cloned` is False -> head must NOT overwrite CACHE
        assert rag._tap_commits() == {"a__b": "CACHE"}

    def test_falls_back_to_head_commit_when_cache_missing(self, monkeypatch):
        tap = _FakeTap("a/b", cache_text=None, is_cloned=True)
        monkeypatch.setattr(rag.registry, "list_taps", lambda: [tap])
        monkeypatch.setattr(rag.gitutil, "head_commit",
                            lambda p: "HEAD" if p == tap.path else "WRONG")
        assert rag._tap_commits() == {"a__b": "HEAD"}

    def test_empty_head_commit_stays_empty_string(self, monkeypatch):
        tap = _FakeTap("a/b", cache_text=None, is_cloned=True)
        monkeypatch.setattr(rag.registry, "list_taps", lambda: [tap])
        monkeypatch.setattr(rag.gitutil, "head_commit", lambda p: "")
        assert rag._tap_commits() == {"a__b": ""}


class TestReadBodyHardening:
    def test_missing_name_key_uses_empty_default(self, tmp_path):
        e = {"tap": "acme/skills", "description": "d", "skill_md": ""}
        assert rag.read_body(e, {"acme/skills": tmp_path}) == "d"

    def test_missing_description_key_uses_empty_default(self, tmp_path):
        e = {"name": "n", "tap": "acme/skills", "skill_md": ""}
        assert rag.read_body(e, {"acme/skills": tmp_path}) == "n"

    def test_reads_via_repos_dir_when_tap_unmapped(self, sandbox):
        from boost_cli.core import paths
        paths.ensure_dirs()
        d = paths.repos_dir() / "who__what" / "y"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("---\nname: y\n---\n\nmarmalade toast\n", encoding="utf-8")
        e = _entry("y", tap="who/what", skill_md="y/SKILL.md", desc="d")
        body = rag.read_body(e, {})  # empty map -> base None -> repos_dir/<safe>
        assert "marmalade" in body

    def test_invalid_utf8_is_replaced_not_raised(self, tmp_path):
        root = tmp_path / "repo"
        (root / "x").mkdir(parents=True)
        (root / "x" / "SKILL.md").write_bytes(
            b"---\nname: x\n---\n\n\xff\xfe not valid utf8\n")
        e = _entry("x", skill_md="x/SKILL.md", desc="d")
        body = rag.read_body(e, {"acme/skills": root})
        assert isinstance(body, str)
        assert body.startswith("x\nd")
        assert "not valid utf8" in body  # decoded with errors="replace"


class TestChunkBoundaries:
    def test_exact_fit_packs_inclusive(self):
        # len(cur)+1+len(p) == size -> packs (<=, not <); +2 would not fit
        assert rag.chunk("aaaa\n\nbb", size=7, overlap=0) == ["aaaa\nbb"]

    def test_off_by_one_join_width(self):
        # +1 accounts for the '\n'; -1 would wrongly pack these
        assert rag.chunk("aaaa\n\nbbb", size=7, overlap=0) == ["aaaa", "bbb"]

    def test_overlap_tail_is_the_end_of_prev_chunk(self):
        out = rag.chunk("abcdef\n\nghijkl", size=7, overlap=2)
        assert out[0] == "abcdef"
        assert out[1].startswith("ef")       # last 2 chars of prev (not "cdef")
        assert "XX" not in out[1]            # join uses "\n", not "XX\nXX"

    def test_zero_overlap_injects_nothing(self):
        assert rag.chunk("abcdef\n\nghijkl", size=7, overlap=0) == [
            "abcdef", "ghijkl"]


class TestMakeDocs:
    def test_uses_passed_tap_paths_not_global(self, tmp_path, sandbox,
                                              monkeypatch):
        root = tmp_path / "repo"
        (root / "a").mkdir(parents=True)
        (root / "a" / "SKILL.md").write_text(
            "---\nname: a\n---\n\nblueberry pancakes\n", encoding="utf-8")
        monkeypatch.setattr(rag, "_tap_paths", lambda: {})  # global is empty
        e = _entry("a", skill_md="a/SKILL.md")
        docs = rag._make_docs([e], {"acme/skills": root})
        terms = set().union(*(d["tf"] for d in docs)) if docs else set()
        assert "blueberry" in terms

    def test_term_frequencies_and_kind_default_and_snippet(self, monkeypatch):
        monkeypatch.setattr(rag, "read_body",
                            lambda e, tp: "widget widget gadget")
        e = {"name": "n", "tap": "x/y", "skill_md": "s"}  # no kind
        docs = rag._make_docs([e], {})
        assert docs[0]["tf"] == {"widget": 2, "gadget": 1}
        assert docs[0]["k"] == "skill"          # e.get("kind", "skill")

    def test_snippet_stores_chunk_head_up_to_snip_store(self, monkeypatch):
        # v2: more than SNIP_WIDTH is stored (windowed later at retrieve time)
        # so `retrieve` can center on the matched terms — but capped at
        # SNIP_STORE to bound index growth.
        monkeypatch.setattr(rag, "read_body", lambda e, tp: "Q" * 250)
        e = _entry("n")
        docs = rag._make_docs([e], {})
        assert docs[0]["snip"] == "Q" * 250              # under cap -> stored whole

    def test_snippet_storage_is_capped(self, monkeypatch):
        monkeypatch.setattr(rag, "read_body",
                            lambda e, tp: "Q" * (rag.SNIP_STORE + 200))
        e = _entry("n")
        docs = rag._make_docs([e], {})
        assert docs[0]["snip"] == "Q" * rag.SNIP_STORE

    def test_one_document_per_entry_however_long_the_body(self, monkeypatch):
        # Inverted deliberately. This asserted `len(docs) > 1`, the chunking the
        # index no longer does: each window carried its own copy of the shared
        # fields and its own snippet, and `retrieve` collapsed them back to one
        # hit per entry anyway, so the extra documents were built, stored,
        # re-parsed on every cold search, and then discarded.
        monkeypatch.setattr(rag, "read_body", lambda e, tp: "widget " * 400)
        docs = rag._make_docs([_entry("n")], {})
        assert len(docs) == 1
        assert docs[0]["tf"]["widget"] == 400

    def test_the_entry_surface_is_indexed_with_the_body(self, monkeypatch):
        # A chunked index matched names for free — the name sat in whatever
        # chunk contained it. One doc per entry has to state the surface, or
        # searching for an item by its own name stops working.
        monkeypatch.setattr(rag, "read_body", lambda e, tp: "unrelated prose")
        docs = rag._make_docs(
            [_entry("code-reviewer", desc="reviews diffs")], {})
        tf = docs[0]["tf"]
        assert "reviewer" in tf, "the de-hyphenated name must be searchable"
        assert "diffs" in tf, "the description must be searchable"

    def test_empty_chunk_is_skipped_not_break(self, monkeypatch):
        body = ("the " * 220) + "\n\n" + ("widget " * 130)
        monkeypatch.setattr(rag, "read_body", lambda e, tp: body)
        e = _entry("n")
        docs = rag._make_docs([e], {})
        # An all-stopword passage contributes no terms; the entry still yields
        # its one document, carrying the terms from the rest of the body.
        assert len(docs) == 1
        assert "widget" in docs[0]["tf"]


class TestPassage:
    def test_short_text_returned_stripped_and_whole(self):
        assert rag._passage("  hello world  ", ["hello"], width=200) \
            == "hello world"

    def test_exact_width_returned_as_is(self):
        t = "x" * 50
        assert rag._passage(t, [], width=50) == t        # len == width -> as-is

    def test_no_term_falls_back_to_head_and_rstrips(self):
        # width lands on a trailing space -> right-strip it (not left), + ellipsis
        t = "word " * 100                                 # long, term absent
        out = rag._passage(t, ["zzz"], width=40)
        assert out == ("word " * 8).rstrip() + "…"

    def test_centers_on_match_with_left_context(self):
        t = "a" * 100 + " needle " + "b" * 100
        out = rag._passage(t, ["needle"], width=40)
        assert "needle" in out
        assert out.startswith("…") and out.endswith("…")
        # left context is exactly width // 4 chars before the match
        assert out.lstrip("…").index("needle") == 40 // 4

    def test_centers_on_first_not_last_occurrence(self):
        t = "P" * 11 + "needle" + "Q" * 400 + "needle" + "R" * 50
        out = rag._passage(t, ["needle"], width=40)
        assert "P" in out and "R" not in out             # first match (find, not rfind)

    def test_match_at_position_zero_is_counted(self):
        t = "aa" + "P" * 300 + "bb" + "Q" * 50
        out = rag._passage(t, ["aa", "bb"], width=40)
        assert out.startswith("aa")                       # p >= 0, not p > 0

    def test_leading_ellipsis_when_window_starts_at_one(self):
        t = "x" * 11 + "needle" + "y" * 100               # start == 11 - 40//4 == 1
        out = rag._passage(t, ["needle"], width=40)
        assert out.startswith("…")                        # start > 0, not start > 1

    def test_match_near_start_has_no_leading_ellipsis(self):
        t = "needle " + "b" * 300
        out = rag._passage(t, ["needle"], width=40)
        assert not out.startswith("…")
        assert out.endswith("…")
        assert out.startswith("needle")

    def test_match_near_end_clamps_window_no_trailing_ellipsis(self):
        t = "a" * 300 + " needle"
        out = rag._passage(t, ["needle"], width=40)
        # clamped so a full width window still ends exactly at the match
        assert out == "…" + "a" * 33 + " needle"

    def test_case_insensitive_match(self):
        t = "x" * 100 + " NEEDLE " + "y" * 100
        assert "NEEDLE" in rag._passage(t, ["needle"], width=30)

    def test_earliest_of_several_terms_wins(self):
        t = "a" * 50 + " zebra " + "b" * 200 + " apple " + "c" * 50
        out = rag._passage(t, ["apple", "zebra"], width=40)
        assert "zebra" in out and "apple" not in out


class TestPostingsAndKept:
    def test_postings_inversion(self):
        raw = {"postings": {"foo": [[0, 2], [1, 3]]}}
        assert dict(rag._postings_to_doc_tf(raw)) == {0: {"foo": 2},
                                                      1: {"foo": 3}}

    def test_postings_missing_key_is_empty(self):
        assert dict(rag._postings_to_doc_tf({})) == {}

    def test_kept_docs_empty_when_no_docs(self):
        assert rag._kept_docs({}, set()) == []

    def test_kept_docs_recovers_tf_and_defaults_empty(self):
        raw = {"docs": [{"t": "x/y", "n": "a", "f": "a/SKILL.md", "k": "skill",
                         "c": 0, "l": 1, "snip": "s"}], "postings": {}}
        assert rag._kept_docs(raw, {"x__y"}) == [
            {"t": "x/y", "n": "a", "f": "a/SKILL.md", "k": "skill", "c": 0,
             "l": 1, "snip": "s", "tf": {}}]


class TestSavePayload:
    def test_full_payload_structure(self, sandbox):
        docs = [
            {"n": "a", "t": "x/y", "f": "a/SKILL.md", "k": "skill", "c": 0,
             "l": 2, "snip": "sa", "tf": {"foo": 1, "bar": 1}},
            {"n": "b", "t": "x/y", "f": "b.mdc", "k": "rule", "c": 3,
             "l": 4, "snip": "sb", "tf": {"foo": 2}},
        ]
        rag._save(docs, {"x__y": "c1"})
        raw = json.loads(rag.index_path().read_text(encoding="utf-8"))
        assert raw["version"] == rag.INDEX_VERSION
        assert raw["engine"] == rag.ENGINE
        assert "generated" in raw
        assert raw["commits"] == {"x__y": "c1"}
        assert raw["params"] == {"chunk_chars": rag.CHUNK_CHARS,
                                 "overlap": rag.OVERLAP,
                                 "k1": rag.K1, "b": rag.B}
        assert raw["stats"]["docs"] == 2
        assert raw["stats"]["avg_len"] == pytest.approx((2 + 4) / 2)
        # The JSON no longer carries postings; they are queried per-term from
        # the SQLite store, which is the whole point of moving them.
        assert "postings" not in raw
        assert rag.read_postings(["foo"])["foo"] == [[0, 1], [1, 2]]
        assert rag.read_postings(["bar"])["bar"] == [[0, 1]]
        assert rag.read_postings(["nope"]) == {}
        assert raw["docs"][0] == {"n": "a", "t": "x/y", "f": "a/SKILL.md",
                                  "h": "", "k": "skill", "c": 0, "l": 2,
                                  "snip": "sa"}
        assert raw["docs"][1] == {"n": "b", "t": "x/y", "f": "b.mdc",
                                  "h": "", "k": "rule", "c": 3, "l": 4,
                                  "snip": "sb"}

    def test_empty_docs_avg_len_zero(self, sandbox):
        rag._save([], {})
        raw = json.loads(rag.index_path().read_text(encoding="utf-8"))
        assert raw["stats"]["avg_len"] == 0.0
        assert raw["docs"] == []
        assert "postings" not in raw
        # An empty corpus still writes the store, so `ready()` can distinguish
        # "indexed nothing" from "never indexed".
        assert rag.postings_path().exists()
        assert rag.read_postings(["anything"]) == {}

    def test_save_invalidates_stale_cache_entry(self, sandbox):
        key = str(rag.index_path())
        rag._CACHE[key] = (1.0, {"stale": True})
        rag._save([{"n": "a", "t": "x/y", "f": "a/SKILL.md", "k": "skill",
                    "c": 0, "l": 1, "snip": "s", "tf": {"z": 1}}], {})
        assert key not in rag._CACHE


class TestLoadRaw:
    def test_rejects_wrong_version(self, sandbox):
        from boost_cli.core import paths
        paths.ensure_dirs()
        rag.index_path().write_text(json.dumps(
            {"version": 999, "docs": [1], "postings": {}}), encoding="utf-8")
        rag._CACHE.clear()
        assert rag._load_raw() is None

    def test_pops_cache_when_file_disappears(self, sandbox):
        rag._save([{"n": "a", "t": "x/y", "f": "a/SKILL.md", "k": "skill",
                    "c": 0, "l": 1, "snip": "s", "tf": {"z": 1}}], {})
        key = str(rag.index_path())
        assert rag._load_raw() is not None
        assert key in rag._CACHE
        rag.index_path().unlink()
        assert rag._load_raw() is None
        assert key not in rag._CACHE

    def test_reparses_when_mtime_changes(self, sandbox):
        import os
        rag._save([{"n": "a", "t": "x/y", "f": "a/SKILL.md", "k": "skill",
                    "c": 0, "l": 1, "snip": "s", "tf": {"z": 1}}], {})
        first = rag._load_raw()
        assert first["stats"]["docs"] == 1          # cached (mtime, A)
        p = rag.index_path()
        p.write_text(json.dumps({
            "version": rag.INDEX_VERSION, "engine": "bm25", "generated": "x",
            "commits": {},
            "params": {}, "stats": {"docs": 5}, "docs": [], "postings": {}}), encoding="utf-8")
        st = p.stat()
        os.utime(p, (st.st_mtime + 50, st.st_mtime + 50))
        second = rag._load_raw()
        assert second["stats"]["docs"] == 5         # new mtime -> reparsed


class TestBuildEdge:
    def test_stats_reports_tap_count(self, corpus):
        _root, entries = corpus
        stats = rag.build(entries=entries, force=True)
        assert stats["taps"] == 1

    def test_tolerates_old_index_without_commits(self, corpus):
        from boost_cli.core import paths
        _root, entries = corpus
        paths.ensure_dirs()
        rag.index_path().write_text(json.dumps(
            {"version": rag.INDEX_VERSION, "docs": [],
             "postings": {}}), encoding="utf-8")  # no "commits" key
        rag._CACHE.clear()
        stats = rag.build(entries=entries)  # force=False -> loads the old index
        assert stats["docs"] >= 1


class TestRetrieveInternals:
    def _save_docs(self, docs):
        rag._save(docs, {})

    def test_max_score_per_item_kept_across_chunks(self, sandbox):
        # two chunks of one item; first (doc 0) is the better snippet
        self._save_docs([
            {"n": "a", "t": "x/y", "f": "a/SKILL.md", "k": "skill", "c": 0, "l": 3,
             "snip": "FIRST", "tf": {"widget": 1}},
            {"n": "a", "t": "x/y", "f": "a/SKILL.md", "k": "skill", "c": 1, "l": 3,
             "snip": "SECOND", "tf": {"widget": 1}},
        ])
        hits = rag.retrieve("widget", entries=[_entry("a", tap="x/y")])
        assert len(hits) == 1
        assert hits[0]["snippet"] == "FIRST"   # tie keeps first; prev cmp is [0]

    def test_ranks_by_score_not_name(self, sandbox):
        self._save_docs([
            {"n": "aaa", "t": "x/y", "f": "aaa/SKILL.md", "k": "skill", "c": 0, "l": 5,
             "snip": "sa", "tf": {"widget": 1}},
            {"n": "zzz", "t": "x/y", "f": "zzz/SKILL.md", "k": "skill", "c": 0, "l": 5,
             "snip": "sz", "tf": {"widget": 5}},
        ])
        hits = rag.retrieve("widget", entries=[_entry("aaa", tap="x/y"),
                                               _entry("zzz", tap="x/y")])
        assert hits[0]["entry"]["name"] == "zzz"   # higher score wins the sort

    def test_kind_filter_continues_past_wrong_kind(self, sandbox):
        # the wrong-kind doc has the lower id: a `break` would drop the match
        self._save_docs([
            {"n": "ra", "t": "x/y", "f": "ra/SKILL.md", "k": "rule", "c": 0, "l": 1, "snip": "r",
             "tf": {"widget": 1}},
            {"n": "sk", "t": "x/y", "f": "sk/SKILL.md", "k": "skill", "c": 0, "l": 1, "snip": "s",
             "tf": {"widget": 1}},
        ])
        hits = rag.retrieve("widget", kind="skill",
                            entries=[_entry("ra", tap="x/y", kind="rule"),
                                     _entry("sk", tap="x/y", kind="skill")])
        assert {h["entry"]["name"] for h in hits} == {"sk"}

    def test_absent_from_live_set_continues(self, sandbox):
        # doc 0 is not in the live set; a `break` would drop the live doc 1
        self._save_docs([
            {"n": "gone", "t": "x/y", "f": "gone/SKILL.md", "k": "skill", "c": 0, "l": 1,
             "snip": "g", "tf": {"widget": 1}},
            {"n": "live", "t": "x/y", "f": "live/SKILL.md", "k": "skill", "c": 0, "l": 1,
             "snip": "L", "tf": {"widget": 1}},
        ])
        hits = rag.retrieve("widget", entries=[_entry("live", tap="x/y")])
        assert {h["entry"]["name"] for h in hits} == {"live"}


class TestRerankExact:
    def test_exact_prompt_and_kwargs(self, monkeypatch, sandbox):
        cap = {}
        monkeypatch.setattr(rag.ai, "available", lambda: True)

        def fake_ask(prompt, system=None, max_tokens=None):
            cap["prompt"] = prompt
            cap["system"] = system
            cap["max_tokens"] = max_tokens
            return '["a", "b", "c", "d"]'
        monkeypatch.setattr(rag.ai, "ask", fake_ask)
        hits = [
            {"entry": {"name": "a", "kind": "rule", "description": "da"},
             "score": 4.0, "snippet": "alpha"},
            {"entry": {"name": "b", "description": "beta"},   # no kind
             "score": 3.0, "snippet": ""},                    # empty -> desc
            {"entry": {"name": "c"},                          # no kind/desc
             "score": 2.0, "snippet": ""},
            {"entry": {"name": "d", "kind": "skill", "description": "dd"},
             "score": 1.0, "snippet": "D" * 200},             # trunc to 180
        ]
        rag.rerank("myquery", hits, limit=5)
        listing = "\n".join([
            "- a [rule]: alpha",
            "- b [skill]: beta",
            "- c [skill]: ",
            "- d [skill]: " + "D" * 180,
        ])
        expected = (
            "Task: myquery\n\nCandidate skills (name, kind, best matching "
            "text):\n" + listing + "\n\nOrder the skill names best-match-first "
            "for the task. Reply with ONLY a JSON array of names.")
        assert cap["prompt"] == expected
        assert cap["system"] == (
            "You rank AI coding skills by how well they fit a task.")
        assert cap["max_tokens"] == 400

    def test_shortlist_capped_at_15(self, monkeypatch):
        cap = {}
        monkeypatch.setattr(rag.ai, "available", lambda: True)

        def fake_ask(prompt, system=None, max_tokens=None):
            cap["prompt"] = prompt
            return "[]"
        monkeypatch.setattr(rag.ai, "ask", fake_ask)
        hits = [_hit("n%d" % i, float(20 - i), snippet="s%d" % i)
                for i in range(20)]
        rag.rerank("q", hits, limit=5)
        block = cap["prompt"].split("text):\n", 1)[1].split("\n\nOrder", 1)[0]
        assert len(block.splitlines()) == 15   # max(limit, 15), not 16

    def test_default_limit_is_10(self, monkeypatch):
        monkeypatch.setattr(rag.ai, "available", lambda: False)
        hits = [_hit("n%d" % i, float(20 - i)) for i in range(12)]
        out, _label = rag.rerank("q", hits)     # no limit -> default 10
        assert len(out) == 10


class TestSearchForwarding:
    def _ready_index(self):
        rag._save([{"n": "a", "t": "x/y", "f": "a/SKILL.md", "k": "skill",
                    "c": 0, "l": 1, "snip": "s", "tf": {"z": 1}}], {})

    def test_forwards_retrieve_args(self, sandbox, monkeypatch):
        self._ready_index()
        cap = {}

        def spy(query, k=60, kind=None, entries=None):
            cap.update(query=query, k=k, kind=kind, entries=entries)
            return []
        monkeypatch.setattr(rag, "retrieve", spy)
        sentinel = [{"name": "e", "tap": "x/y"}]
        rag.search("q", limit=20, kind="skill", smart=False, entries=sentinel)
        assert cap["query"] == "q"
        assert cap["k"] == 80               # max(60, 20 * 4)
        assert cap["kind"] == "skill"
        assert cap["entries"] is sentinel

    def test_k_floor_is_sixty(self, sandbox, monkeypatch):
        self._ready_index()
        cap = {}

        def spy(query, k=60, kind=None, entries=None):
            cap["k"] = k
            return []
        monkeypatch.setattr(rag, "retrieve", spy)
        rag.search("q", limit=1, smart=False)
        assert cap["k"] == 60               # max(60, 4)

    def test_forwards_query_limit_and_engine_to_rerank(self, sandbox, monkeypatch):
        # `engine` joined the signature so a degraded rerank can report what
        # actually retrieved instead of assuming BM25; asserted here because
        # dropping it again would be silent — search would still return a
        # plausible label, just the wrong one.
        self._ready_index()
        monkeypatch.setattr(rag, "retrieve", lambda *a, **k: [_hit("a", 1.0)])
        cap = {}

        def spyr(query, hits, limit=10, engine="BM25 full-content"):
            cap.update(query=query, limit=limit, engine=engine)
            return ([], "x")
        monkeypatch.setattr(rag, "rerank", spyr)
        rag.search("theq", limit=5)         # smart defaults to True
        assert cap["query"] == "theq"
        assert cap["limit"] == 5
        assert cap["engine"] == "BM25 full-content"   # what this index is


class TestIndexPath:
    def test_filename(self, sandbox):
        assert rag.index_path().name == "rag_index.json"


class TestEngineRouting:
    """search() prefers the dense backend, floors to BM25, else falls back."""

    def _bm25_ready(self):
        rag._save([{"n": "a", "t": "x/y", "f": "a/SKILL.md", "k": "skill",
                    "c": 0, "l": 1, "snip": "s", "tf": {"react": 1}}], {})

    def test_dense_alone_when_bm25_has_no_index(self, sandbox, monkeypatch):
        # Renamed: this never set up a BM25 index, so it was measuring "dense
        # is the only engine available", not a preference between the two.
        # There is no preference any more — with both present they fuse.
        monkeypatch.setattr(dense_mod, "ready", lambda: True)
        picked = [{"entry": {"name": "d", "tap": "x/y"}, "score": 9.0,
                   "snippet": "D"}]
        monkeypatch.setattr(dense_mod, "retrieve", lambda *a, **k: picked)
        hits, label = rag.search("react", smart=False)
        assert label == "dense vectors"
        assert hits[0]["entry"]["name"] == "d"

    def test_dense_none_falls_through_to_bm25(self, sandbox, monkeypatch):
        self._bm25_ready()
        monkeypatch.setattr(dense_mod, "ready", lambda: True)
        monkeypatch.setattr(dense_mod, "retrieve", lambda *a, **k: None)
        result = rag.search("react", smart=False,
                            entries=[_entry("a", tap="x/y")])
        assert result is not None
        _hits, label = result
        assert label == "BM25 full-content"

    def test_bm25_when_dense_not_ready(self, sandbox, monkeypatch):
        self._bm25_ready()
        monkeypatch.setattr(dense_mod, "ready", lambda: False)
        _hits, label = rag.search("react", smart=False,
                                  entries=[_entry("a", tap="x/y")])
        assert label == "BM25 full-content"

    def test_none_when_no_index_at_all(self, sandbox, monkeypatch):
        monkeypatch.setattr(dense_mod, "ready", lambda: False)
        assert rag.search("react", smart=False) is None

    def test_dense_zero_hits_still_falls_through_to_bm25(self, sandbox,
                                                        monkeypatch):
        # THE BUG: `[]` is what dense.retrieve returns when every KNN neighbour
        # was dropped for a kind mismatch or for no longer being live — a thin
        # index, not a verdict on the query. Taking it as final answered "no
        # results" with a perfectly good BM25 index sitting unused.
        self._bm25_ready()
        monkeypatch.setattr(dense_mod, "ready", lambda: True)
        monkeypatch.setattr(dense_mod, "retrieve", lambda *a, **k: [])
        result = rag.search("react", smart=False,
                            entries=[_entry("a", tap="x/y")])
        assert result is not None, "empty dense result must not end the search"
        hits, label = result
        assert label == "BM25 full-content"
        assert [h["entry"]["name"] for h in hits] == ["a"]

    def test_dense_zero_hits_with_no_bm25_index_falls_all_the_way_out(
            self, sandbox, monkeypatch):
        # Nothing left to try: the caller has to know to use catalog.search,
        # which it only does when it gets None back.
        monkeypatch.setattr(dense_mod, "ready", lambda: True)
        monkeypatch.setattr(dense_mod, "retrieve", lambda *a, **k: [])
        assert rag.search("react", smart=False) is None

    def test_a_non_empty_dense_result_is_now_fused_not_final(self, sandbox,
                                                             monkeypatch):
        # SUPERSEDED CONTRACT, deliberately. This used to assert that a real
        # dense hit ended the search — "the fix must not turn into 'always run
        # BM25 too'". The golden-set eval retired the premise: dense does not
        # beat BM25 there (hit@1 0.780 each over 91 queries), so ending the
        # search on a dense hit hands keyword queries to an engine that is at
        # best tied for them. Both rankings are now fused by RRF.
        #
        # The half of the old fix that still stands is tested above: an EMPTY
        # dense result is not a verdict, and must still fall through to BM25.
        self._bm25_ready()
        monkeypatch.setattr(dense_mod, "ready", lambda: True)
        monkeypatch.setattr(dense_mod, "retrieve", lambda *a, **k: [
            {"entry": {"name": "d", "tap": "x/y", "skill_md": "d/SKILL.md"},
             "score": 9.0, "snippet": "D"}])
        hits, label = rag.search("react", smart=False,
                                 entries=[_entry("a", tap="x/y")])
        assert "hybrid" in label.lower(), label
        assert "d" in [h["entry"]["name"] for h in hits], \
            "the dense hit must survive fusion, not be dropped"


class TestAtomicIndexSave:
    """`_save` must route the index through util.atomic_write_text so a crash
    or concurrent reader never sees a truncated/corrupt BM25 index."""

    def test_save_routes_through_atomic_write_text(self, corpus, monkeypatch):
        _root, entries = corpus
        calls = []
        real = rag.util.atomic_write_text

        def spy(path, text, *a, **k):
            calls.append(Path(path))
            return real(path, text, *a, **k)

        monkeypatch.setattr(rag.util, "atomic_write_text", spy)
        rag.build(entries=entries, force=True)
        # The index write went through the atomic helper, not a bare write_text.
        assert rag.index_path() in calls

    def test_index_is_complete_json_and_leaves_no_temp_turd(self, corpus):
        _root, entries = corpus
        rag.build(entries=entries, force=True)
        p = rag.index_path()
        payload = json.loads(p.read_text(encoding="utf-8"))  # parseable ⇒ not truncated
        # Postings moved to their own SQLite store; the JSON is documents only.
        assert payload["docs"] and "postings" not in payload
        assert rag.postings_path().exists()
        # atomic_write_text writes to ".<name>.*.tmp" then os.replace — the
        # temp file must not survive a successful save.
        assert list(p.parent.glob("." + p.name + ".*")) == []

    def test_rebuild_replaces_index_atomically(self, corpus):
        _root, entries = corpus
        rag.build(entries=entries, force=True)
        rag.build(entries=entries, force=True)  # second save swaps in place
        payload = json.loads(rag.index_path().read_text(encoding="utf-8"))
        assert payload["stats"]["docs"] >= 2


class TestPostingsStore:
    """Postings live in SQLite so a query reads its terms, not the whole index.

    They were the largest part of the JSON index — 64% of it after unchunking —
    and `json.loads` had to materialise every one to answer a query touching a
    handful of terms. On a real 83-tap install that was 8-13 s and multiple GB
    resident per cold search, against 31-70 ms of scoring.

    Scoring itself is unchanged, which is the property these tests protect:
    `_bm25` takes postings as an argument, so moving where they are stored
    cannot alter what comes back.
    """

    def _built(self):
        rag._save([{"n": "a", "t": "x/y", "f": "a/SKILL.md", "h": "h1",
                    "k": "skill", "c": 0, "l": 2, "snip": "sa",
                    "tf": {"react": 2, "test": 1}},
                   {"n": "b", "t": "x/y", "f": "b/SKILL.md", "h": "h2",
                    "k": "skill", "c": 0, "l": 1, "snip": "sb",
                    "tf": {"test": 3}}], {})
        rag._CACHE.clear()

    def test_only_the_asked_for_terms_come_back(self, sandbox):
        self._built()
        got = rag.read_postings(["react"])
        assert set(got) == {"react"}, "read more than the query needed"

    def test_a_term_maps_to_every_doc_that_has_it(self, sandbox):
        self._built()
        assert sorted(rag.read_postings(["test"])["test"]) == [[0, 1], [1, 3]]

    def test_an_absent_term_is_simply_missing(self, sandbox):
        self._built()
        assert rag.read_postings(["nonesuch"]) == {}

    def test_no_terms_is_no_query(self, sandbox):
        self._built()
        assert rag.read_postings([]) == {}

    def test_more_terms_than_sqlite_takes_as_parameters(self, sandbox):
        # SQLite caps host parameters (999 on older builds); the reader chunks.
        self._built()
        many = ["t%d" % i for i in range(2500)] + ["react"]
        assert set(rag.read_postings(many)) == {"react"}

    def test_a_rebuild_replaces_rather_than_appends(self, sandbox):
        self._built()
        rag._save([{"n": "a", "t": "x/y", "f": "a/SKILL.md", "h": "h1",
                    "k": "skill", "c": 0, "l": 1, "snip": "sa",
                    "tf": {"react": 1}}], {})
        rag._CACHE.clear()
        assert rag.read_postings(["react"])["react"] == [[0, 1]]
        assert rag.read_postings(["test"]) == {}, "stale postings survived"

    def test_no_temp_file_survives_a_successful_write(self, sandbox):
        self._built()
        p = rag.postings_path()
        assert p.exists()
        assert list(p.parent.glob(p.name + ".tmp")) == []

    def test_a_missing_store_reads_as_empty_not_an_error(self, sandbox):
        # Degrading to "no hits" beats raising out of a user's search.
        assert not rag.postings_path().exists()
        assert rag.read_postings(["react"]) == {}

    def test_ready_is_false_without_the_postings_store(self, sandbox):
        self._built()
        rag.postings_path().unlink()
        rag._CACHE.clear()
        assert rag.ready() is False, \
            "a docs-only index would score every query to zero hits"


class TestPostingsInterning:
    """Terms live in their own table, not repeated on every posting row.

    Measured on a real 458-tap store: 18,619,658 posting rows over 210,422
    distinct terms averaging 6.6 characters — the term string alone was ~123 MB
    of a 653 MB file, each term stored 88 times over on average. These tests
    pin the interned shape directly against the SQLite file, because
    `read_postings`/`stem_expansions` alone would pass just as well against the
    old un-interned layout — a mutant that reverted `_write_postings` to store
    `term TEXT` on every posting row would leave every other test in this file
    green.
    """

    def _built(self):
        rag._save([{"n": "a", "t": "x/y", "f": "a/SKILL.md", "h": "h1",
                    "k": "skill", "c": 0, "l": 2, "snip": "sa",
                    "tf": {"react": 2, "test": 1}},
                   {"n": "b", "t": "x/y", "f": "b/SKILL.md", "h": "h2",
                    "k": "skill", "c": 0, "l": 1, "snip": "sb",
                    "tf": {"test": 3}}], {})
        rag._CACHE.clear()

    def _connect(self):
        return sqlite3.connect("file:%s?mode=ro" % rag.postings_path(),
                                uri=True)

    def test_postings_rows_carry_an_integer_term_id_not_term_text(
            self, sandbox):
        self._built()
        con = self._connect()
        try:
            cols = {row[1]: row[2]
                    for row in con.execute("PRAGMA table_info(postings)")}
        finally:
            con.close()
        assert cols == {"term_id": "INTEGER", "doc": "INTEGER", "tf": "INTEGER"}

    def test_every_posting_row_resolves_to_a_term_via_the_terms_table(
            self, sandbox):
        self._built()
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT t.term, p.doc, p.tf FROM postings p "
                "JOIN terms t ON p.term_id = t.id "
                "WHERE t.term = 'test' ORDER BY p.doc").fetchall()
        finally:
            con.close()
        assert rows == [("test", 0, 1), ("test", 1, 3)]

    def test_a_term_used_by_two_docs_is_stored_once_in_the_terms_table(
            self, sandbox):
        self._built()
        con = self._connect()
        try:
            term_ids = {row[0] for row in
                        con.execute("SELECT term_id FROM postings p "
                                    "JOIN terms t ON p.term_id = t.id "
                                    "WHERE t.term = 'test'")}
            term_rows = con.execute(
                "SELECT COUNT(*) FROM terms WHERE term = 'test'").fetchone()[0]
        finally:
            con.close()
        assert len(term_ids) == 1, "test's two postings must share one term_id"
        assert term_rows == 1, "the term string itself must appear exactly once"

    def test_document_frequency_is_precomputed_per_term(self, sandbox):
        self._built()
        con = self._connect()
        try:
            df = dict(con.execute("SELECT term, df FROM terms"))
        finally:
            con.close()
        assert df == {"react": 1, "test": 2}

    def test_term_text_is_unique_in_the_terms_table(self, sandbox):
        self._built()
        con = sqlite3.connect(str(rag.postings_path()))
        try:
            with pytest.raises(sqlite3.IntegrityError):
                con.execute("INSERT INTO terms (id, term, df) "
                            "VALUES (999, 'test', 1)")
        finally:
            con.close()


class TestConcurrentPostingsBuildsDoNotDestroyEachOther:
    """Two `rag.build()` runs must not delete each other's temp file.

    `_write_postings` writes to a temp beside the final path and swaps it in.
    While that temp had a FIXED name and was unlinked on entry, a second build
    starting mid-flight deleted the first's finished file, and the first then
    raised `FileNotFoundError` out of `tmp.replace(final)` — observed on a real
    464-tap install:

        FileNotFoundError: rag_postings.sqlite.tmp -> rag_postings.sqlite
          at rag.py in _write_postings, tmp.replace(final)

    The loser's work is thrown away and the user gets a crash report rather
    than a result, on a command whose whole job is to rebuild that file.
    `boost search` auto-builds on a cold index, so two terminals is enough.
    """

    def test_a_second_build_does_not_delete_the_first_s_temp(self, sandbox):
        # A writes its temp; B runs to completion in the middle; A must still
        # be able to swap its own file in.
        seen: list = []
        real_connect = rag.sqlite3.connect

        def connect_then_run_a_rival(path, *a, **kw):
            con = real_connect(path, *a, **kw)
            if not seen:
                seen.append(path)
                # A rival build, start to finish, while this one is open.
                rag._write_postings({"beta": [[1, 1]]})
            return con

        with mock.patch.object(rag.sqlite3, "connect",
                               side_effect=connect_then_run_a_rival):
            rag._write_postings({"alpha": [[0, 1]]})

        # No crash is the headline, and the file the outer build wrote is the
        # one that must be standing.
        assert rag.postings_path().exists()
        assert rag.read_postings(["alpha"])["alpha"] == [[0, 1]]

    def test_each_build_uses_its_own_temp_path(self, sandbox):
        # The mechanism, pinned directly: a shared constant temp name is what
        # made the race possible, so two builds must not name the same file.
        names: list[str] = []
        real_connect = rag.sqlite3.connect

        def record(path, *a, **kw):
            names.append(str(path))
            return real_connect(path, *a, **kw)

        with mock.patch.object(rag.sqlite3, "connect", side_effect=record):
            rag._write_postings({"alpha": [[0, 1]]})
            rag._write_postings({"beta": [[1, 1]]})

        assert len(names) == 2
        assert names[0] != names[1], (
            "both builds wrote %s — a fixed temp name lets one delete the "
            "other's finished file" % names[0])

    def test_no_temp_files_are_left_behind(self, sandbox):
        rag._write_postings({"alpha": [[0, 1]]})
        leftovers = list(rag.postings_path().parent.glob("*.tmp*"))
        assert leftovers == [], "left %s behind" % leftovers

    def test_a_failed_build_cleans_up_and_leaves_the_old_index_standing(
            self, sandbox):
        """A build that raises must not leave a temp behind or eat the error.

        The cleanup path is the whole reason the temp is unique: if a failing
        build left its file, the directory would fill with one per crash, and
        a swallowed exception would report success for an index that was never
        written. `util.atomic_write_text` makes the same two guarantees.
        """
        rag._write_postings({"alpha": [[0, 1]]})       # an index worth keeping
        before = rag.postings_path().read_bytes()

        closed: list[bool] = []

        class Boom:
            def execute(self, *a, **kw):
                raise RuntimeError("disk went away")

            def executemany(self, *a, **kw):  # pragma: no cover - unreached
                raise RuntimeError("disk went away")

            def commit(self):  # pragma: no cover - unreached
                pass

            def close(self):
                closed.append(True)

        with (mock.patch.object(rag.sqlite3, "connect", return_value=Boom()),
              pytest.raises(RuntimeError, match="disk went away")):
            rag._write_postings({"beta": [[1, 1]]})

        assert closed, "the connection was leaked on the failure path"
        assert list(rag.postings_path().parent.glob("*.tmp*")) == []
        # The swap never happened, so the previous index is still the one on
        # disk — a failed rebuild must not cost you the index you had.
        assert rag.postings_path().read_bytes() == before
        assert rag.read_postings(["alpha"])["alpha"] == [[0, 1]]
