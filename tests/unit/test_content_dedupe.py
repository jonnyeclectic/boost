"""Collapsing byte-identical copies before they reach the ten slots a user sees.

Measured over 77 tapped registries (29,938 entries): **78.3% are byte-identical
duplicates**, largest cluster 40 copies, and the natural-language query set
averages **4.94 of 10 result slots** consumed by a repeat of a name already in
the list — worst case 9 of 10.

Two measurements decide the design:

* **Cluster on content, never on name.** 82.7% of entries share a name but only
  78.3% share a body. That ~4.4% gap is real distinct content — the
  `admin-interface-rule` pair fixed in #366 is two different rules under one
  name — and name-based dedup would merge exactly those.
* **Content clustering cannot over-merge here.** Of 14,153 distinct bodies, the
  number of clusters spanning more than one name is **0**. So collapsing by body
  never merges two differently-named items; it is strictly safer than the
  name-based alternative the card also offered.

The quality prior is `curated`: within a cluster every copy is byte-identical,
so the one worth surfacing is the one from a tap the user marked trusted.
"""
from __future__ import annotations

from boost_cli.core import rag


def _hit(name, tap, score, content, curated=False, skill_md=None):
    return {"entry": {"name": name, "tap": tap, "curated": curated,
                      "skill_md": skill_md or ("%s/SKILL.md" % name),
                      "kind": "skill", "description": ""},
            "score": score, "snippet": "", "content": content}


class TestCollapsesIdenticalBodies:
    def test_two_byte_identical_copies_become_one(self):
        hits = [_hit("rule", "a/x", 3.0, "same"), _hit("rule", "b/y", 2.0, "same")]
        out = rag.dedupe_by_content(hits, limit=10)
        assert len(out) == 1

    def test_the_best_ranked_copy_is_the_one_kept(self):
        hits = [_hit("rule", "a/x", 3.0, "same"), _hit("rule", "b/y", 2.0, "same")]
        assert rag.dedupe_by_content(hits, limit=10)[0]["entry"]["tap"] == "a/x"

    def test_a_cluster_of_forty_becomes_one(self):
        # The largest real cluster measured over 77 taps.
        hits = [_hit("rule", "t%d/r" % i, 40.0 - i, "same") for i in range(40)]
        assert len(rag.dedupe_by_content(hits, limit=10)) == 1

    def test_order_of_surviving_hits_is_preserved(self):
        hits = [_hit("a", "t/1", 5.0, "A"), _hit("b", "t/2", 4.0, "B"),
                _hit("a2", "t/3", 3.0, "A")]          # dupe of the first
        out = rag.dedupe_by_content(hits, limit=10)
        assert [h["entry"]["name"] for h in out] == ["a", "b"]


class TestNeverMergesDistinctContent:
    """The failure that would matter: two different rules collapsed into one."""

    def test_same_name_different_bodies_stay_two_results(self):
        # The #366 pair: one tap, one name, two genuinely different rules.
        hits = [_hit("admin-interface-rule", "z/rules", 3.0, "express mongodb",
                     skill_md="a/express-mongodb/admin-interface-rule.mdc"),
                _hit("admin-interface-rule", "z/rules", 2.0, "mern fullstack",
                     skill_md="a/fullstack-mern/admin-interface-rule.mdc")]
        out = rag.dedupe_by_content(hits, limit=10)
        assert len(out) == 2, "distinct bodies were merged on a shared name"

    def test_missing_content_is_never_treated_as_a_match(self):
        # Two hits with no recorded hash must not collapse into each other just
        # because both are unknown — that would silently hide real results.
        hits = [_hit("a", "t/1", 3.0, None), _hit("b", "t/2", 2.0, None)]
        assert len(rag.dedupe_by_content(hits, limit=10)) == 2


class TestQualityPrior:
    """Every copy in a cluster is byte-identical, so surface the trusted one."""

    def test_a_curated_copy_wins_over_a_better_ranked_uncurated_one(self):
        hits = [_hit("rule", "rando/x", 3.0, "same"),
                _hit("rule", "trusted/y", 2.0, "same", curated=True)]
        kept = rag.dedupe_by_content(hits, limit=10)[0]["entry"]
        assert kept["tap"] == "trusted/y"

    def test_the_kept_hit_keeps_the_best_score_in_its_cluster(self):
        # Swapping which copy is shown must not demote the cluster's ranking.
        hits = [_hit("rule", "rando/x", 3.0, "same"),
                _hit("rule", "trusted/y", 2.0, "same", curated=True)]
        assert rag.dedupe_by_content(hits, limit=10)[0]["score"] == 3.0

    def test_two_curated_copies_fall_back_to_rank(self):
        hits = [_hit("rule", "a/x", 3.0, "same", curated=True),
                _hit("rule", "b/y", 2.0, "same", curated=True)]
        assert rag.dedupe_by_content(hits, limit=10)[0]["entry"]["tap"] == "a/x"


class TestLimit:
    def test_limit_is_applied_after_collapsing_not_before(self):
        # The whole point: duplicates must not consume the slots. Ten copies of
        # one body followed by three distinct items should yield four results,
        # not one.
        hits = ([_hit("dup", "t%d/r" % i, 20.0 - i, "same") for i in range(10)]
                + [_hit("x", "t/a", 5.0, "X"), _hit("y", "t/b", 4.0, "Y"),
                   _hit("z", "t/c", 3.0, "Z")])
        out = rag.dedupe_by_content(hits, limit=4)
        assert [h["entry"]["name"] for h in out] == ["dup", "x", "y", "z"]

    def test_empty_input_is_empty_output(self):
        assert rag.dedupe_by_content([], limit=10) == []


class TestHashesReachEveryEngine:
    """Dense hits carry no hash of their own; one map serves all engines."""

    def test_hashes_are_read_from_the_bm25_index(self, sandbox):
        rag._save([{"n": "a", "t": "x/y", "f": "a/SKILL.md", "h": "deadbeef",
                    "k": "skill", "c": 0, "l": 1, "snip": "s",
                    "tf": {"z": 1}}], {})
        rag._CACHE.clear()
        assert rag.content_hashes() == {("x/y", "a/SKILL.md"): "deadbeef"}

    def test_a_dense_hit_gets_its_hash_attached(self, sandbox):
        rag._save([{"n": "a", "t": "x/y", "f": "a/SKILL.md", "h": "deadbeef",
                    "k": "skill", "c": 0, "l": 1, "snip": "s",
                    "tf": {"z": 1}}], {})
        rag._CACHE.clear()
        bare = [{"entry": {"name": "a", "tap": "x/y",
                           "skill_md": "a/SKILL.md"},
                 "score": 1.0, "snippet": ""}]
        assert rag._with_content(bare)[0]["content"] == "deadbeef"

    def test_an_existing_hash_is_not_overwritten(self, sandbox):
        hits = [{"entry": {"name": "a", "tap": "x/y", "skill_md": "a/SKILL.md"},
                 "score": 1.0, "snippet": "", "content": "mine"}]
        assert rag._with_content(hits)[0]["content"] == "mine"

    def test_no_index_degrades_to_leaving_hits_alone(self, sandbox):
        # No BM25 index yet: dedupe must no-op rather than collapse everything
        # into one result on a shared empty hash.
        bare = [{"entry": {"name": "a", "tap": "x/y", "skill_md": "a.md"},
                 "score": 2.0, "snippet": ""},
                {"entry": {"name": "b", "tap": "x/y", "skill_md": "b.md"},
                 "score": 1.0, "snippet": ""}]
        out = rag.dedupe_by_content(rag._with_content(bare), limit=10)
        assert len(out) == 2
