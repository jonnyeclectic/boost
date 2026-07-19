"""Unit tests: pkg._warn_confusions — the install-time typosquat guard wiring."""
from __future__ import annotations

from boost_cli.commands import pkg
from boost_cli.core import catalog
from boost_cli.core import output as out


def _capture(monkeypatch, entries):
    monkeypatch.setattr(catalog, "all_entries", lambda: entries)
    warnings = []
    monkeypatch.setattr(out, "warn", lambda m: warnings.append(m))
    return warnings


def test_warns_on_cross_tap_lookalike(monkeypatch):
    entries = [{"name": "deploy", "tap": "alice/skills"},
               {"name": "deployy", "tap": "mallory/evil"}]
    warnings = _capture(monkeypatch, entries)
    pkg._warn_confusions([entries[0]])
    assert len(warnings) == 1
    assert "mallory/evil" in warnings[0] and "deploy" in warnings[0]


def test_quiet_when_no_confusion(monkeypatch):
    entries = [{"name": "deploy", "tap": "alice/skills"},
               {"name": "totally-unrelated", "tap": "bob/x"}]
    warnings = _capture(monkeypatch, entries)
    pkg._warn_confusions([entries[0]])
    assert warnings == []


def test_same_tap_sibling_not_warned(monkeypatch):
    entries = [{"name": "deploy", "tap": "alice/skills"},
               {"name": "deployy", "tap": "alice/skills"}]
    warnings = _capture(monkeypatch, entries)
    pkg._warn_confusions([entries[0]])
    assert warnings == []


def test_empty_entries_skips_catalog_lookup(monkeypatch):
    def boom():
        raise AssertionError("catalog must not be queried for an empty install")
    monkeypatch.setattr(catalog, "all_entries", boom)
    pkg._warn_confusions([])  # returns before touching the catalog
