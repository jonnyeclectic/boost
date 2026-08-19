"""The ``entries=None`` fast path of ``rag.retrieve``.

A cold ``boost search`` used to call ``catalog.all_entries()`` — parsing every
tap cache on the machine (458 files, ~100 MB, 0.32 s measured) — to build a
``live`` map whose entries are only *displayed* for the final k hits. The fast
path ranks straight off the index's own doc metadata and materialises real
entries for just the taps the survivors came from.

The contract these tests pin: for the same index and a consistent catalogue,
the fast path is **byte-identical** to ``retrieve(..., entries=all_entries())``
— same hits, same order, same scores, snippets, and entry dicts — and any
state where that cannot be guaranteed (an entry vanished between index and
cache) falls back to the explicit-entries path rather than approximating.
"""
from __future__ import annotations

import json
import os

import pytest

from boost_cli.core import catalog, rag, registry


def _entry(name, tap, kind="skill", skill_md=None, desc="", curated=False):
    e = {"name": name, "tap": tap, "kind": kind,
         "skill_md": skill_md or ("%s/SKILL.md" % name),
         "description": desc}
    if curated:
        e["curated"] = True
    return e


@pytest.fixture()
def two_taps(tmp_path, monkeypatch, sandbox):
    """Two taps on disk — 'beta/tools' (uncurated) and 'zeta/skills' (curated).

    Engineered corpus: an equal-score tie (twin-a/twin-b share a body), a
    byte-identical cross-tap duplicate (dup-rule in both taps, curated copy in
    the tap that LOSES the rank tie-break, so promotion is observable), and
    all three kinds. Returns (by_tap, all_entries_list, load_calls).
    """
    bodies = {
        "beta/tools": {
            # "commit" also appears in dup-rule: doc 0 (a skill) sits before
            # the rule docs in every postings list, so a kind=rule query must
            # skip past this mismatch mid-scan rather than stop at it.
            "jest-runner": ("skill", "Unit testing for JavaScript and React components with jest, wired into commit hooks."),
            "deploy-guide": ("workflow", "Rolling kubernetes deployment with health checks and canary."),
            "twin-a": ("skill", "Identical prose for the tie break battery."),
            "twin-b": ("skill", "Identical prose for the tie break battery."),
            "dup-rule": ("rule", "Never commit secrets; scan diffs before push."),
        },
        "zeta/skills": {
            "dup-rule": ("rule", "Never commit secrets; scan diffs before push."),
            "pytest-helper": ("skill", "Python testing framework with fixtures and parametrize."),
        },
    }
    roots, by_tap = {}, {}
    for tap, items in bodies.items():
        root = tmp_path / tap.replace("/", "__")
        roots[tap] = root
        by_tap[tap] = []
        for name, (kind, body) in items.items():
            (root / name).mkdir(parents=True)
            (root / name / "SKILL.md").write_text(
                "---\nname: %s\n---\n\n%s\n" % (name, body), encoding="utf-8")
            by_tap[tap].append(_entry(name, tap, kind=kind,
                                      curated=(tap == "zeta/skills")))
    monkeypatch.setattr(rag, "_tap_paths", lambda: dict(roots))
    monkeypatch.setattr(rag, "_tap_commits",
                        lambda: {"beta__tools": "c1", "zeta__skills": "c2"})

    taps = [registry.Tap(name="beta/tools", url=""),
            registry.Tap(name="zeta/skills", url="", curated=True)]
    monkeypatch.setattr(registry, "list_taps", lambda: list(taps))

    load_calls: list[str] = []

    def fake_load_tap(tap, rebuild=False):
        load_calls.append(tap.name)
        return list(by_tap.get(tap.name, []))

    monkeypatch.setattr(catalog, "load_tap", fake_load_tap)

    everything = [e for es in by_tap.values() for e in es]
    rag.build(entries=everything, force=True)
    load_calls.clear()
    return by_tap, everything, load_calls


QUERIES = [
    ("jest testing react", None, 60),
    ("kubernetes deployment", None, 60),
    ("commit secrets", None, 60),
    ("identical prose battery", None, 60),
    ("testing", "skill", 60),
    ("commit secrets", "rule", 60),
    # Single term on purpose: its postings list is doc-id-ascending with the
    # jest-runner SKILL doc first, so the kind filter provably has to skip
    # past a mismatch mid-scan — a multi-term query would leave the scan
    # order to set() hashing.
    ("commit", "rule", 60),
    ("testing", None, 1),
    ("jest testing react components", None, 3),
]


class TestParity:
    """Fast path output == explicit-entries output, full Hit equality."""

    @pytest.mark.parametrize("query,kind,k", QUERIES)
    def test_fast_path_matches_explicit_entries_path(self, two_taps,
                                                     query, kind, k):
        _by_tap, everything, _calls = two_taps
        fast = rag.retrieve(query, k=k, kind=kind)
        slow = rag.retrieve(query, k=k, kind=kind, entries=everything)
        assert fast == slow
        assert fast, "fixture query %r must match something" % query

    def test_hit_shape_is_unchanged(self, two_taps):
        hits = rag.retrieve("jest testing")
        assert hits
        for h in hits:
            assert set(h) == {"entry", "score", "content", "snippet"}

    def test_returned_entries_are_the_real_catalog_dicts(self, two_taps):
        """No shadow/synthesised entry may leak out of the fast path."""
        by_tap, _everything, _calls = two_taps
        hits = rag.retrieve("jest testing")
        top = hits[0]["entry"]
        assert top in by_tap[top["tap"]]

    def test_tie_break_orders_identical_scores_by_name(self, two_taps):
        _by_tap, everything, _calls = two_taps
        fast = rag.retrieve("identical prose battery")
        names = [h["entry"]["name"] for h in fast]
        assert names.index("twin-a") < names.index("twin-b")
        assert fast == rag.retrieve("identical prose battery",
                                    entries=everything)

    def test_curated_copy_promoted_but_rank_and_score_kept(self, two_taps):
        """dup-rule: beta's copy wins the rank tie-break, zeta's is curated.

        The cluster must collapse to ONE hit showing the curated (zeta) entry
        while keeping the kept copy's score — on both paths, identically.
        """
        _by_tap, everything, _calls = two_taps
        fast = rag.retrieve("commit secrets")
        dups = [h for h in fast if h["entry"]["name"] == "dup-rule"]
        assert len(dups) == 1
        assert dups[0]["entry"]["tap"] == "zeta/skills"
        assert fast == rag.retrieve("commit secrets", entries=everything)

    def test_snippet_windows_onto_the_query_terms(self, tmp_path, monkeypatch,
                                                  sandbox):
        """Deferring _passage to the survivors must not change its output."""
        root = tmp_path / "solo"
        filler = "intro paragraph about setup and config. " * 8
        body = filler + "\n\nThe kubernetes operator reconciles pods."
        (root / "k8s").mkdir(parents=True)
        (root / "k8s" / "SKILL.md").write_text(
            "---\nname: k8s\n---\n\n%s\n" % body, encoding="utf-8")
        e = _entry("k8s", "solo/tap")
        monkeypatch.setattr(rag, "_tap_paths", lambda: {"solo/tap": root})
        monkeypatch.setattr(rag, "_tap_commits", lambda: {"solo__tap": "c1"})
        monkeypatch.setattr(registry, "list_taps",
                            lambda: [registry.Tap(name="solo/tap", url="")])
        monkeypatch.setattr(catalog, "load_tap", lambda tap, rebuild=False: [e])
        rag.build(entries=[e], force=True)
        hits = rag.retrieve("kubernetes operator")
        assert hits
        snip = hits[0]["snippet"]
        assert "kubernetes" in snip.lower()
        assert snip.startswith("…")
        assert len(snip) <= rag.SNIP_WIDTH + 2
        assert snip == rag.retrieve("kubernetes operator",
                                    entries=[e])[0]["snippet"]


class TestLaziness:
    """What the fast path is FOR: never parse the whole catalogue."""

    def test_fast_path_never_calls_all_entries(self, two_taps, monkeypatch):
        monkeypatch.setattr(
            catalog, "all_entries",
            lambda: pytest.fail("fast path must not read the whole catalogue"))
        assert rag.retrieve("jest testing")

    def test_k_smaller_than_survivors_stays_on_the_fast_path(self, two_taps,
                                                             monkeypatch):
        """Filling k early must return the hits, not wander into fallback."""
        monkeypatch.setattr(
            catalog, "all_entries",
            lambda: pytest.fail("fast path must not read the whole catalogue"))
        assert len(rag.retrieve("testing", k=1)) == 1

    def test_only_touched_taps_are_loaded(self, two_taps):
        """kubernetes matches only beta/tools items, so zeta stays unread."""
        _by_tap, _everything, load_calls = two_taps
        hits = rag.retrieve("kubernetes deployment")
        assert hits
        assert set(load_calls) == {"beta/tools"}

    def test_each_touched_tap_is_loaded_once(self, two_taps):
        _by_tap, _everything, load_calls = two_taps
        rag.retrieve("testing")          # hits in both taps
        assert sorted(load_calls) == sorted(set(load_calls))


class TestDegradation:
    """Any state the fast path cannot prove consistent falls back wholesale."""

    def test_vanished_entry_falls_back_to_the_slow_path(self, two_taps,
                                                        monkeypatch):
        """A tap whose cache is gone serves nothing; the fast path must then
        answer exactly what the explicit-entries path answers — not drop, not
        error."""
        by_tap, _everything, _calls = two_taps

        def gone(tap, rebuild=False):
            return [] if tap.name == "beta/tools" else list(by_tap[tap.name])

        monkeypatch.setattr(catalog, "load_tap", gone)
        fast = rag.retrieve("testing")
        slow = rag.retrieve("testing", entries=by_tap["zeta/skills"])
        assert fast == slow
        assert all(h["entry"]["tap"] == "zeta/skills" for h in fast)

    def test_untapped_tap_is_filtered_even_on_a_stale_index(self, two_taps,
                                                            monkeypatch):
        """Untapping a repo must stop its docs ranking, index rebuild or not."""
        monkeypatch.setattr(
            registry, "list_taps",
            lambda: [registry.Tap(name="zeta/skills", url="", curated=True)])
        hits = rag.retrieve("commit secrets")
        assert hits
        assert all(h["entry"]["tap"] == "zeta/skills" for h in hits)
        assert rag.retrieve("jest react") == []


class TestDedupePromotionCarry:
    """Promotion must copy the kept hit wholesale, swapping only the entry.

    The old promotion rebuilt the dict with a literal four keys, which would
    silently drop anything else a caller carried on the hit — the fast path
    relies on the carry staying intact through dedupe.
    """

    def test_promotion_preserves_extra_keys(self):
        kept = {"entry": {"name": "x", "tap": "a/t", "skill_md": "x/SKILL.md"},
                "score": 2.0, "snippet": "raw snip", "content": "h1",
                "extra": "carried"}
        curated = {"entry": {"name": "x", "tap": "b/t", "curated": True,
                             "skill_md": "x/SKILL.md"},
                   "score": 1.0, "snippet": "other", "content": "h1"}
        out = rag.dedupe_by_content([kept, curated], 10)
        assert len(out) == 1
        assert out[0]["entry"]["tap"] == "b/t"          # promoted source
        assert out[0]["score"] == 2.0                    # kept rank
        assert out[0]["snippet"] == "raw snip"           # kept snippet
        assert out[0]["extra"] == "carried"              # carried through


class TestLoadRawStamp:
    """_load_raw must notice a rewrite that lands in the same mtime tick."""

    def test_same_mtime_different_size_is_reloaded(self, two_taps):
        first = rag._load_raw()
        assert first is not None
        p = rag.index_path()
        st = p.stat()
        payload = json.loads(p.read_text(encoding="utf-8"))
        payload["docs"] = payload["docs"][:1]
        p.write_text(json.dumps(payload), encoding="utf-8")
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
        again = rag._load_raw()
        assert again is not None
        assert len(again["docs"]) == 1
