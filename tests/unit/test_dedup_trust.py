"""Which copy survives dedup, when every copy is byte-identical.

Content-hash dedup collapses a cluster to one result. Because the bodies are
identical, *which* one survives is not a relevance question at all — it decides
where the user installs from. The roadmap card asks for "a quality prior —
source trust, stars, recency, maintenance".

Two signals exist today and they are not the same thing:

* the entry's own ``curated`` flag — the user tapped that registry with
  ``--curated``, i.e. a decision this machine's owner made;
* ``confidence`` in the shipped ``registries.json`` — high / med / low, a
  maintainer judgement about the registry, covering 466 registries.

The user's own flag outranks the shipped default deliberately: a shipped
opinion should never override a decision the user made on their own machine.
Below both, ranking order breaks the tie, so the behaviour stays deterministic
when there is no trust signal at all.
"""
from __future__ import annotations

from boost_cli.core import rag


def _hit(name, tap, score, content, curated=False):
    return {"entry": {"name": name, "tap": tap, "curated": curated,
                      "skill_md": "%s/SKILL.md" % name, "kind": "skill",
                      "description": ""},
            "score": score, "snippet": "", "content": content}


class TestTrustRank:
    """`source_rank` orders candidates; lower sorts first."""

    def test_a_curated_tap_beats_an_uncurated_one(self, monkeypatch):
        monkeypatch.setattr(rag, "registry_confidence", lambda tap: None)
        assert rag.source_rank({"tap": "a/x", "curated": True}) < \
               rag.source_rank({"tap": "b/y", "curated": False})

    def test_high_confidence_beats_low(self, monkeypatch):
        conf = {"a/x": "high", "b/y": "low"}
        monkeypatch.setattr(rag, "registry_confidence", conf.get)
        assert rag.source_rank({"tap": "a/x"}) < rag.source_rank({"tap": "b/y"})

    def test_high_beats_med_beats_low(self, monkeypatch):
        conf = {"h": "high", "m": "med", "l": "low"}
        monkeypatch.setattr(rag, "registry_confidence", conf.get)
        ranks = [rag.source_rank({"tap": t}) for t in ("h", "m", "l")]
        assert ranks == sorted(ranks) and len(set(ranks)) == 3

    def test_the_users_own_flag_outranks_a_shipped_high(self, monkeypatch):
        # A shipped opinion must not override a decision made on this machine.
        conf = {"rando": None, "shipped": "high"}
        monkeypatch.setattr(rag, "registry_confidence", conf.get)
        assert rag.source_rank({"tap": "rando", "curated": True}) < \
               rag.source_rank({"tap": "shipped", "curated": False})

    def test_an_unknown_registry_ranks_below_a_known_one(self, monkeypatch):
        monkeypatch.setattr(rag, "registry_confidence",
                            {"known": "low"}.get)
        assert rag.source_rank({"tap": "known"}) < \
               rag.source_rank({"tap": "never-heard-of-it"})


class TestDedupUsesIt:
    """The prior only matters inside a cluster of identical bodies."""

    def test_a_trusted_copy_wins_over_a_better_ranked_one(self, monkeypatch):
        monkeypatch.setattr(rag, "registry_confidence",
                            {"rando/x": "low", "solid/y": "high"}.get)
        hits = [_hit("rule", "rando/x", 3.0, "same"),
                _hit("rule", "solid/y", 2.0, "same")]
        assert rag.dedupe_by_content(hits, 10)[0]["entry"]["tap"] == "solid/y"

    def test_the_cluster_keeps_its_best_score(self, monkeypatch):
        monkeypatch.setattr(rag, "registry_confidence",
                            {"rando/x": "low", "solid/y": "high"}.get)
        hits = [_hit("rule", "rando/x", 3.0, "same"),
                _hit("rule", "solid/y", 2.0, "same")]
        assert rag.dedupe_by_content(hits, 10)[0]["score"] == 3.0

    def test_equal_trust_falls_back_to_rank(self, monkeypatch):
        monkeypatch.setattr(rag, "registry_confidence",
                            {"a/x": "high", "b/y": "high"}.get)
        hits = [_hit("rule", "a/x", 3.0, "same"), _hit("rule", "b/y", 2.0, "same")]
        assert rag.dedupe_by_content(hits, 10)[0]["entry"]["tap"] == "a/x"

    def test_trust_never_merges_distinct_bodies(self, monkeypatch):
        # The prior decides *which* copy, never *whether* to collapse.
        monkeypatch.setattr(rag, "registry_confidence",
                            {"a/x": "high", "b/y": "low"}.get)
        hits = [_hit("rule", "a/x", 3.0, "one body"),
                _hit("rule", "b/y", 2.0, "a different body")]
        assert len(rag.dedupe_by_content(hits, 10)) == 2


class TestConfidenceLookup:
    """Reading the shipped catalog, without paying for it on every call."""

    def test_a_shipped_registry_resolves(self):
        # Picked from registries.json; asserted as a real value, not just truthy.
        assert rag.registry_confidence("Aaronontheweb/dotnet-cursor-rules") == "med"

    def test_an_unknown_registry_is_none(self):
        assert rag.registry_confidence("nobody/nothing") is None

    def test_the_catalog_is_read_once(self, monkeypatch):
        # 466 registries parsed per hit would be a real cost in a search loop.
        calls = []
        rag._confidence_map.cache_clear()
        real = rag.config.load_registry_catalog
        monkeypatch.setattr(rag.config, "load_registry_catalog",
                            lambda: calls.append(1) or real())
        rag.registry_confidence("a")
        rag.registry_confidence("b")
        rag.registry_confidence("c")
        assert len(calls) == 1
