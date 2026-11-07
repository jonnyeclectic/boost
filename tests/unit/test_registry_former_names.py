# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a tap held under a catalogue row's former name is that row.

A tap is named from its URL, so a machine that tapped a registry before it was
renamed upstream holds it under the old name. Every lookup that keyed the
catalogue by the row's current name alone answered nothing for that tap: no
category (so its items lost the one they inherit), no confidence, and no ★
drift. ``config.registry_rows_by_name`` is the one place that knows both names.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import catalog, config, rag, registry, serve

OLD, NEW = "oldowner/claude-skills", "newowner/ai-skills"
GH = "https://github.com/"


@pytest.fixture
def catalogue(monkeypatch):
    """NEW was OLD; PLAIN never moved. The caches over the data are dropped."""
    rows = [{"name": NEW, "url": GH + NEW, "category": "infra",
             "confidence": "med", "curated": False, "formerly": [OLD]},
            {"name": "plain/repo", "url": GH + "plain/repo",
             "category": "ai", "confidence": "high", "curated": True}]
    monkeypatch.setattr(config, "load_registry_catalog", lambda: list(rows))
    rag._confidence_map.cache_clear()
    monkeypatch.setattr(serve, "_CATEGORIES", None)
    yield rows
    rag._confidence_map.cache_clear()


class TestRowsByName:
    def test_a_former_name_is_the_row(self, catalogue):
        rows = config.registry_rows_by_name()
        assert rows[OLD] is rows[NEW] is catalogue[0]
        assert set(rows) == {NEW, OLD, "plain/repo"}

    def test_a_former_name_never_shadows_another_rows_current_name(
            self, monkeypatch):
        """Two rows, one of which lists the other's current name as a former
        one of its own: the name belongs to the row that carries it now."""
        held = {"name": "a/x", "category": "ai"}
        mover = {"name": "b/y", "category": "infra", "formerly": ["a/x"]}
        for order in ([held, mover], [mover, held]):
            monkeypatch.setattr(config, "load_registry_catalog",
                                lambda order=order: list(order))
            rows = config.registry_rows_by_name()
            assert rows["a/x"] is held
            assert rows["b/y"] is mover
            assert config.registry_categories()["a/x"] == "ai"

    def test_only_an_owner_repo_former_name_aliases(self, monkeypatch):
        """A local tap is named after its directory, never `owner/repo`."""
        monkeypatch.setattr(config, "load_registry_catalog", lambda: [
            {"name": NEW, "formerly": ["claude-skills", "a/b/c", OLD]}])
        assert set(config.registry_rows_by_name()) == {NEW, OLD}

    def test_malformed_rows_are_skipped(self, monkeypatch):
        monkeypatch.setattr(config, "load_registry_catalog", lambda: [
            "not a row", {"category": "ai"}, {"name": "", "category": "ai"},
            {"name": NEW, "category": "infra"}])
        assert config.registry_categories() == {NEW: "infra"}

    def test_the_shipped_catalogue_carries_each_former_name(self):
        rows = config.registry_rows_by_name()
        assert rows["leogallego/claude-ansible-skills"]["name"] == (
            "leogallego/ai-skills-ansible")
        assert config.registry_categories()[
            "leogallego/claude-ansible-skills"] == "infra"


class TestLookups:
    def test_category(self, catalogue):
        cats = config.registry_categories()
        assert cats[OLD] == cats[NEW] == "infra"

    def test_confidence(self, catalogue):
        assert rag.registry_confidence(OLD) == "med"
        assert rag.registry_confidence(NEW) == "med"
        assert rag.registry_confidence("other/repo") is None

    def test_a_row_without_confidence_has_none(self, monkeypatch):
        """Not a crash, and not the string "None": unranked, under either
        name, like a tap the catalogue does not list."""
        monkeypatch.setattr(config, "load_registry_catalog", lambda: [
            {"name": NEW, "category": "infra", "formerly": [OLD]},
            {"name": "plain/repo", "confidence": "high"}])
        rag._confidence_map.cache_clear()
        try:
            assert rag.registry_confidence(NEW) is None
            assert rag.registry_confidence(OLD) is None
            assert rag.registry_confidence("plain/repo") == "high"
        finally:
            rag._confidence_map.cache_clear()

    def test_served_facets_agree_with_browse(self, catalogue):
        assert serve.registry_categories() == config.registry_categories()
        assert serve.registry_categories()[OLD] == "infra"

    def test_self_installing_by_former_name_and_by_its_url(self, monkeypatch):
        monkeypatch.setattr(config, "load_registry_catalog", lambda: [
            {"name": NEW, "self_installing": "./setup", "formerly": [OLD]}])
        assert config.self_installing_command(OLD) == "./setup"
        assert config.self_installing_command("mine", GH + OLD) == "./setup"
        assert config.self_installing_command("mine", GH + "other/x") is None


class TestOverstarred:
    def _rows(self, *rows):
        cfg = config.load()
        cfg["taps"] = list(rows)
        config.save(cfg)

    def test_a_star_on_the_former_name_is_drift(self, sandbox, catalogue):
        """`tap --catalog` once starred every row, and the renamed row is
        not curated: the ★ it left under the old name is the drift."""
        self._rows({"name": OLD, "url": GH + OLD, "curated": True},
                   {"name": "plain/repo", "url": GH + "plain/repo",
                    "curated": True},
                   {"name": "mine/repo", "url": GH + "mine/repo",
                    "curated": True})
        assert registry.overstarred() == [OLD]


class TestCacheCategory:
    def _cache(self, tap, tap_category):
        tap.cache_file.parent.mkdir(parents=True, exist_ok=True)
        tap.cache_file.write_text(json.dumps({
            "tap": tap.name, "url": tap.url, "format": catalog.CACHE_FORMAT,
            "commit": "", "tap_category": tap_category, "skills": []}),
            encoding="utf-8")
        catalog._ENTRY_CACHE.clear()

    def test_a_cache_scanned_before_the_rename_stays_current(self, sandbox,
                                                             catalogue):
        """Written while the row still had this name, under its category:
        nothing moved, so nothing is rescanned."""
        tap = registry.Tap(name=OLD, url=GH + OLD)
        self._cache(tap, "infra")
        assert catalog._cache_record(tap)[1] is True

    def test_a_cache_that_lost_the_category_is_rescanned(self, sandbox,
                                                         catalogue):
        tap = registry.Tap(name=OLD, url=GH + OLD)
        self._cache(tap, "")
        assert catalog._cache_record(tap)[1] is False

    def test_an_untagged_item_inherits_the_rows_category(self, catalogue,
                                                         tmp_path):
        skill = tmp_path / "x" / "SKILL.md"
        skill.parent.mkdir()
        skill.write_text("---\nname: x\ndescription: d\n---\n\nBody.\n",
                         encoding="utf-8")
        [entry] = catalog.scan_dir(tmp_path, tap_name=OLD)
        assert entry["category"] == "infra"
