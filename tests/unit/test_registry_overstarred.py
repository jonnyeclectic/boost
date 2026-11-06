# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`registry.overstarred` / `unstar`: take back the ★ the catalogue no longer gives.

A machine that tapped the catalogue before the ★ was narrowed holds ~460
starred rows; `boost heal` clears the ones the catalogue does not curate. What
must never happen is clearing a star the user asked for, or one on a tap the
catalogue does not list — those are the user's, not boost's.
"""
import pytest

from boost_cli.core import config, gitutil, policy, registry

CATALOGUE = [
    {"name": "o/starred", "url": "https://github.com/o/starred", "curated": True},
    {"name": "o/plain", "url": "https://github.com/o/plain", "curated": False},
    {"name": "o/plain2", "url": "https://github.com/o/plain2", "curated": False},
]


@pytest.fixture()
def catalogue(sandbox, monkeypatch):
    monkeypatch.setattr(config, "load_registry_catalog", lambda: CATALOGUE)


def _taps(rows):
    cfg = config.load()
    cfg["taps"] = rows
    config.save(cfg)


def _row(name, curated, **extra):
    return {"name": name, "url": "u", "curated": curated, **extra}


class TestOverstarred:
    def test_names_only_a_starred_row_the_catalogue_does_not_curate(
            self, catalogue):
        _taps([_row("o/starred", True), _row("o/plain", True),
               _row("o/plain2", False), _row("me/own", True)])
        assert registry.overstarred() == ["o/plain"]

    def test_a_star_the_user_asked_for_is_kept(self, catalogue):
        _taps([_row("o/plain", True, curated_by=registry.CURATED_BY_USER)])
        assert registry.overstarred() == []

    def test_an_unstarred_curated_row_is_not_drift(self, catalogue):
        # A plain `boost tap` is opt-in; heal never adds a star.
        _taps([_row("o/starred", False)])
        assert registry.overstarred() == []

    def test_malformed_taps_read_as_none(self, catalogue):
        _taps(None)
        assert registry.overstarred() == []
        _taps("nope")
        assert registry.overstarred() == []
        _taps(["junk", {"curated": True}])
        assert registry.overstarred() == []


class TestUnstar:
    def test_clears_named_rows_in_one_write(self, catalogue, monkeypatch):
        _taps([_row("o/plain", True), _row("o/plain2", True),
               _row("o/starred", True)])
        writes = []
        real = config.save
        monkeypatch.setattr(config, "save",
                            lambda cfg: (writes.append(1), real(cfg))[1])
        assert registry.unstar(["o/plain", "o/plain2"]) == ["o/plain",
                                                           "o/plain2"]
        assert len(writes) == 1
        assert {t.name: t.curated for t in registry.list_taps()} == {
            "o/plain": False, "o/plain2": False, "o/starred": True}
        assert registry.overstarred() == []

    def test_nothing_to_do_writes_nothing(self, catalogue, monkeypatch):
        _taps([_row("o/plain", False)])
        writes = []
        monkeypatch.setattr(config, "save", lambda cfg: writes.append(1))
        assert registry.unstar([]) == []
        assert registry.unstar(["o/plain", "absent"]) == []
        assert writes == []


class TestUserMarker:
    @pytest.fixture()
    def fake_clone(self, monkeypatch):
        def clone(url, dest, sparse=True):
            dest.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(gitutil, "clone_shallow", clone)
        monkeypatch.setattr(policy, "check_tap_signing", lambda path: [])

    def _rows(self):
        return {t["name"]: t for t in config.load()["taps"]}

    def test_add_curated_marks_the_star_as_the_users(self, catalogue,
                                                     fake_clone):
        registry.add("o/plain", curated=True)
        registry.add("o/plain2")
        rows = self._rows()
        assert rows["o/plain"]["curated_by"] == registry.CURATED_BY_USER
        assert "curated_by" not in rows["o/plain2"]
        assert registry.overstarred() == []

    def test_batch_flag_marks_but_catalogue_names_do_not(self, catalogue,
                                                         fake_clone):
        registry.add_many(["o/plain"], curated=True)
        registry.add_many(["o/starred", "o/plain2"],
                          curated_names={"o/starred"})
        rows = self._rows()
        assert rows["o/plain"]["curated_by"] == registry.CURATED_BY_USER
        assert rows["o/starred"]["curated"] is True
        assert "curated_by" not in rows["o/starred"]
        assert "curated_by" not in rows["o/plain2"]
