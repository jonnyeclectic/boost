# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A query that is exactly an item's name ranks that item first.

BM25 weighs a name only as a 3x field, so a keyword-denser competitor
outscored the item the user typed the name of: with `code_review` installed,
`boost search code_review` listed `review-checklist` first, in text and
``--json`` alike, under every case and separator spelling.
"""
from __future__ import annotations

import pytest

from boost_cli.core import catalog, rag, registry

TAP = "acme/skills"
ITEMS = {
    "code_review": ("Review pull requests for bugs.",
                    "Read the diff and review the code carefully."),
    "review-checklist": ("Checklist for code review; review code for bugs.",
                         "Walk the code review checklist. Review each changed "
                         "file. Note bugs in the code. Review the code review."),
    "unrelated": ("Deploy containers.", "Roll out kubernetes pods."),
}


@pytest.fixture()
def corpus(tmp_path, monkeypatch, sandbox):
    root = tmp_path / "acme__skills"
    entries = []
    for name, (desc, body) in ITEMS.items():
        (root / name).mkdir(parents=True)
        (root / name / "SKILL.md").write_text(
            "---\nname: %s\ndescription: %s\n---\n\n%s\n" % (name, desc, body),
            encoding="utf-8")
        entries.append({"name": name, "tap": TAP, "kind": "skill",
                        "skill_md": "%s/SKILL.md" % name, "description": desc})
    monkeypatch.setattr(rag, "_tap_paths", lambda: {TAP: root})
    monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
    monkeypatch.setattr(registry, "list_taps",
                        lambda: [registry.Tap(name=TAP, url="")])
    monkeypatch.setattr(catalog, "load_tap", lambda tap, rebuild=False: list(entries))
    rag.build(entries=entries, force=True)
    return entries


def _names(hits) -> list:
    return [h["entry"]["name"] for h in hits]


@pytest.mark.parametrize("query", ["code_review", "code-review", "CODE_REVIEW",
                                   "code review", "  Code  Review "])
@pytest.mark.parametrize("explicit", [False, True])
def test_exact_name_ranks_first_on_both_paths(corpus, query, explicit):
    hits = rag.retrieve(query, entries=corpus if explicit else None)
    assert _names(hits)[:2] == ["code_review", "review-checklist"]
    # The scenario is real only if the competitor outscores it on text.
    assert hits[1]["score"] > hits[0]["score"]


def test_promotion_happens_before_the_k_cut(corpus):
    assert _names(rag.retrieve("code review", k=1)) == ["code_review"]
    assert _names(rag.retrieve("code review", k=1, entries=corpus)) == ["code_review"]


def test_a_non_name_query_keeps_bm25_order(corpus):
    assert _names(rag.retrieve("review code bugs"))[0] == "review-checklist"


def test_name_key_folds_case_and_separators():
    assert rag.name_key("  Code__Review - Helper ") == "code-review-helper"
    assert rag.name_key("--x--") == "x"
    assert rag.name_key("a\tb") == "a-b"


def _hit(name: str, score: float) -> dict:
    return {"entry": {"name": name, "tap": "t", "kind": "skill",
                      "skill_md": "%s/SKILL.md" % name},
            "score": score, "snippet": ""}


class TestPromoteExactName:
    def test_moves_every_exact_match_forward_stably(self):
        hits = [_hit("a", 5), _hit("x_y", 4), _hit("b", 3), _hit("X-Y", 2)]
        out = rag.promote_exact_name(hits, "x y")
        assert [(h["entry"]["name"], h["score"]) for h in out] == \
            [("x_y", 4), ("X-Y", 2), ("a", 5), ("b", 3)]

    def test_no_match_returns_the_list_unchanged(self):
        hits = [_hit("a", 2), _hit("b", 1)]
        assert rag.promote_exact_name(hits, "c") is hits

    def test_an_empty_key_promotes_nothing(self):
        hits = [_hit("a", 2), _hit("-", 1)]
        assert rag.promote_exact_name(hits, " - ") is hits


def test_retrieve_any_promotes_after_fusion(monkeypatch):
    # BM25 #2 + dense #1 outranks BM25 #1 + dense #3 under RRF; the exact
    # name must still lead the fused list.
    from boost_cli.core import dense as dense_mod
    bm25 = [_hit("code_review", 2), _hit("review-checklist", 3)]
    dense = [_hit("review-checklist", 0.9), _hit("other", 0.8),
             _hit("code_review", 0.7)]
    monkeypatch.setattr(rag, "ready", lambda: True)
    monkeypatch.setattr(rag, "retrieve", lambda *_a, **_k: list(bm25))
    monkeypatch.setattr(dense_mod, "ready", lambda: True)
    monkeypatch.setattr(dense_mod, "retrieve", lambda *_a, **_k: list(dense))
    monkeypatch.setattr(rag, "_with_content", lambda hits: hits)
    hits, label = rag.retrieve_any("code-review")
    assert label == "hybrid RRF (BM25 + dense)"
    assert _names(hits) == ["code_review", "review-checklist", "other"]
    plain, _ = rag.retrieve_any("review")
    assert _names(plain)[0] == "review-checklist"
