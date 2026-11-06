# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost doctor` names a ★ the catalogue no longer gives; `boost heal` clears it.

The flag lives in two places — the config row and every cached entry, stamped
at scan time — so a heal that only flipped config would leave browse and the
curated fallback still reading the old star.
"""
import shutil

import pytest

from boost_cli.core import catalog, config, registry

CATALOGUE = [{"name": "o/plain", "url": "https://github.com/o/plain",
              "curated": False}]


@pytest.fixture()
def legacy(boost, sandbox, fixture_tap_src, monkeypatch):
    """A catalogue tap starred the old, batch-wide way, cache and all."""
    monkeypatch.setattr(config, "load_registry_catalog", lambda: CATALOGUE)
    monkeypatch.setattr(
        "boost_cli.core.gitutil.clone_shallow",
        lambda url, dest: shutil.copytree(fixture_tap_src, dest))
    boost("tap", "o/plain")
    cfg = config.load()
    cfg["taps"][0]["curated"] = True
    config.save(cfg)
    catalog.rebuild_tap(registry.get("o/plain"))
    assert all(e["curated"] for e in catalog.load_tap(registry.get("o/plain")))


def test_doctor_reports_it_as_one_issue(boost, legacy):
    r = boost("doctor", expect=1)
    text = " ".join(r.out.split())
    assert ("1 tap carries a ★ the catalogue no longer gives (o/plain) — "
            "`boost heal` clears it") in text
    assert text.count("★ the catalogue") == 1


def test_dry_run_changes_nothing(boost, legacy):
    r = boost("heal", "--dry-run")
    assert "would clear the ★ on 1 tap the catalogue does not curate" in r.out
    assert registry.get("o/plain").curated is True


def test_heal_clears_config_and_cache(boost, legacy):
    r = boost("heal")
    assert "cleared the ★ on 1 tap the catalogue does not curate" in r.out
    tap = registry.get("o/plain")
    assert tap.curated is False
    assert not any(e["curated"] for e in catalog.load_tap(tap))
    assert registry.overstarred() == []
    assert "★" not in boost("heal").out
