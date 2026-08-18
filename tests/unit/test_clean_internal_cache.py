"""Unit tests: `boost clean` never deletes boost's own derived cache files.

``clean`` sweeps ``~/.boost/cache/*.json`` whose stem is not a configured tap
and calls what it finds a "stale tap cache". Two of boost's own artifacts live
in that directory and match that shape exactly: ``rag_index.json`` (the BM25
index — 44 MB on a real machine) and ``discovery.json``. Neither is a tap
catalog, and neither stem can ever be a configured tap, so both were swept on
every run. Deleting the BM25 index is not a no-op that repairs itself cheaply:
the next search rebuilds it by parsing every tap catalog on the machine, which
is ~71k items on a full install.

The guard is a registry of names in :data:`paths.INTERNAL_CACHE_FILES`, and the
drift test below fails the build when a module starts writing a cache artifact
without registering it — the same falsifiable-convention shape as
``measure_registry.py --self-check``.
"""
from __future__ import annotations

from boost_cli.commands import discovery
from boost_cli.core import complete, dense, paths, rag


def _seed_cache(names: list[str]) -> dict:
    """Create each named file under the sandbox cache dir; return {name: Path}."""
    paths.cache_dir().mkdir(parents=True, exist_ok=True)
    made = {}
    for name in names:
        pth = paths.cache_dir() / name
        pth.write_text('{"seeded": true}', encoding="utf-8")
        made[name] = pth
    return made


class TestDerivedIndexesSurviveClean:
    def test_rag_index_is_not_swept_as_a_stale_tap_cache(self, boost, sandbox):
        made = _seed_cache(["rag_index.json"])

        boost("clean")

        assert made["rag_index.json"].exists(), (
            "the BM25 index was deleted; the next search re-parses every tap")

    def test_discovery_cache_is_not_swept(self, boost, sandbox):
        made = _seed_cache(["discovery.json"])

        boost("clean")

        assert made["discovery.json"].exists()

    def test_dry_run_does_not_even_offer_to_remove_them(self, boost, sandbox):
        """The dry run is what a user reads before trusting `clean`."""
        _seed_cache(["rag_index.json", "discovery.json"])

        res = boost("clean", "--dry-run")

        assert "rag_index.json" not in res.out
        assert "discovery.json" not in res.out

    def test_a_genuinely_stale_tap_cache_is_still_removed(self, boost, sandbox):
        """The fix must not over-correct into never cleaning anything."""
        made = _seed_cache(["someowner__somerepo.json"])

        res = boost("clean")

        assert not made["someowner__somerepo.json"].exists()
        assert "someowner__somerepo" in res.out

    def test_a_live_taps_cache_is_kept_and_a_dead_ones_is_not(
            self, boost, tapped, sandbox):
        """Regression fence around the behaviour the sweep exists for."""
        live = [f for f in sorted(paths.cache_dir().glob("*.json"))
                if f.name not in paths.INTERNAL_CACHE_FILES]
        assert live, "fixture tap should have produced a catalog cache"
        dead = _seed_cache(["gone__repo.json"])["gone__repo.json"]

        boost("clean")

        assert all(f.exists() for f in live)
        assert not dead.exists()


class TestInternalCacheRegistryHasNoDrift:
    """Every derived artifact boost writes into cache/ must be registered."""

    def test_every_known_cache_artifact_is_registered(self, sandbox):
        owners = {
            "rag.index_path": rag.index_path,
            "rag.postings_path": rag.postings_path,
            "rag.rerank_cache_path": rag.rerank_cache_path,
            "dense.db_path": dense.db_path,
            "discovery._discovery_path": discovery._discovery_path,
            "complete.names_file": complete.names_file,
        }
        unregistered = {
            label: fn().name
            for label, fn in owners.items()
            if fn().parent == paths.cache_dir()
            and fn().name not in paths.INTERNAL_CACHE_FILES
        }

        assert not unregistered, (
            "these cache artifacts are not in paths.INTERNAL_CACHE_FILES, so "
            "`boost clean` may sweep them: %r" % unregistered)

    def test_registered_names_are_not_mistaken_for_tap_catalogs(self):
        """A tap's cache file is `<owner>__<repo>.json`; ours must never collide."""
        for name in paths.INTERNAL_CACHE_FILES:
            assert "__" not in name, (
                "%s looks like a tap catalog filename" % name)
