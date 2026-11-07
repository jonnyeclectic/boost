# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a catalogue row tapped under its former name is not cloned again.

The catalogue moves a row to the name GitHub now redirects to, and records the
old one as ``formerly``. A machine that tapped the row before the move holds
the same repository under the old name, and `tap --catalog` deduped by name
alone, so it cloned that repository a second time under the new one.
"""
from __future__ import annotations

import pytest

from boost_cli.commands import taps as taps_cmd
from boost_cli.core import config, gitutil, registry
from boost_cli.errors import BoostError

OLD, NEW = "oldowner/moved", "newowner/moved"
GH = "https://github.com/"


def _rows(*names):
    cfg = config.load()
    cfg["taps"] = [{"name": n, "url": GH + n, "curated": False} for n in names]
    config.save(cfg)


@pytest.fixture
def catalogue(monkeypatch):
    """The catalogue: NEW was OLD, and PLAIN never moved."""
    rows = [{"name": NEW, "url": GH + NEW, "type": "skill", "formerly": [OLD]},
            {"name": "plain/repo", "url": GH + "plain/repo", "type": "skill"}]
    monkeypatch.setattr(config, "load_registry_catalog", lambda: list(rows))
    return rows


@pytest.fixture
def no_clone(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("must not clone")
    monkeypatch.setattr(gitutil, "clone_shallow", boom)


@pytest.fixture
def cloned(monkeypatch):
    """The specs `add_many` clones; nothing is cloned."""
    seen: list[str] = []

    def fake(spec, curated, pin):
        seen.append(spec)
        name, url = registry.parse_spec(spec)
        return {"spec": spec, "name": name, "url": url, "ok": True,
                "tap": registry.Tap(name=name, url=url)}
    monkeypatch.setattr(registry, "_clone_one", fake)
    return seen


class TestRenames:
    def test_maps_each_former_name_to_its_row(self, catalogue):
        assert registry.renames() == {
            "github.com/oldowner/moved": "github.com/newowner/moved"}

    def test_the_shipped_catalogue_is_read(self):
        assert registry.renames()["github.com/diegosouzapw/omniroute"] == (
            "github.com/cheaper-inference/omniroute")


class TestRenamedTwin:
    def test_old_name_held_answers_for_the_new(self, catalogue):
        old = registry.Tap(name=OLD, url=GH + OLD)
        assert registry.renamed_twin(
            GH + NEW, [old], registry.renames()) is old

    def test_new_name_held_answers_for_the_old(self, catalogue):
        new = registry.Tap(name=NEW, url=GH + NEW)
        assert registry.renamed_twin(
            GH + OLD, [new], registry.renames()) is new

    def test_the_same_repository_is_not_its_own_twin(self, catalogue):
        new = registry.Tap(name=NEW, url=GH + NEW)
        assert registry.renamed_twin(
            GH + NEW, [new], registry.renames()) is None

    def test_an_unrenamed_repository_does_not_scan_the_taps(self, catalogue):
        """`plan_specs` asks once per spec over every tap; for the rows no
        rename touches, keying each tap was all of its cost."""
        class Untouchable:
            @property
            def url(self):
                raise AssertionError("scanned the taps for an unrenamed row")
        assert registry.renamed_twin(
            GH + "plain/repo", [Untouchable()], registry.renames()) is None

    def test_another_forge_under_the_old_name_is_not_the_row(self, catalogue):
        lab = registry.Tap(name=OLD, url="https://gitlab.com/" + OLD)
        assert registry.renamed_twin(
            GH + NEW, [lab], registry.renames()) is None


class TestPlanSkipsAFormerName:
    def test_catalogue_url_over_the_old_name_is_skipped(self, sandbox,
                                                        catalogue, cloned):
        _rows(OLD)
        [res] = registry.add_many([GH + NEW])
        assert cloned == []
        assert res == {"spec": GH + NEW, "name": NEW, "ok": False,
                       "skipped": True, "error": "already tapped",
                       "tapped_as": OLD, "renamed": True}
        assert [t["name"] for t in config.get("taps")] == [OLD]

    def test_owner_repo_over_the_new_name_is_skipped(self, sandbox,
                                                      catalogue):
        _rows(NEW)
        [row] = registry.plan_specs([OLD])
        assert (row["skipped"], row["tapped_as"], row["renamed"]) == (
            True, NEW, True)

    def test_an_unrelated_tap_does_not_hold_it(self, sandbox, catalogue,
                                               cloned):
        _rows("other/moved")
        registry.add_many([GH + NEW])
        assert cloned == [GH + NEW]

    def test_a_row_without_formerly_is_unaffected(self, sandbox, catalogue,
                                                  cloned):
        _rows(OLD)
        registry.add_many([GH + "plain/repo"])
        assert cloned == [GH + "plain/repo"]

    def test_a_name_match_is_not_called_a_rename(self, sandbox, catalogue):
        _rows(NEW)
        [row] = registry.plan_specs([NEW])
        assert row["tapped_as"] == NEW
        assert "renamed" not in row

    @pytest.mark.parametrize("asked", [NEW, OLD])
    def test_both_names_held_is_a_plain_name_match(self, sandbox, catalogue,
                                                   asked):
        """A machine the old `tap --catalog` gave both clones: the name that
        holds the spec answers, and nothing calls it a rename of itself."""
        _rows(OLD, NEW)
        [row] = registry.plan_specs([asked])
        assert row["tapped_as"] == asked
        assert "renamed" not in row


class TestTapCommand:
    def test_add_refuses_the_new_name(self, sandbox, catalogue, no_clone):
        _rows(OLD)
        with pytest.raises(BoostError) as ei:
            registry.add(NEW)
        assert ei.value.message == (
            "%s already tapped as %s (one repository, renamed upstream)"
            % (NEW, OLD))
        assert ei.value.hint == "`boost update %s` to refresh it" % OLD

    def test_add_of_a_url_names_the_tap_not_the_url(self, sandbox, catalogue,
                                                    no_clone):
        _rows(OLD)
        with pytest.raises(BoostError) as ei:
            registry.add(GH + NEW + ".git")
        assert ei.value.message == (
            "%s already tapped as %s (one repository, renamed upstream)"
            % (NEW, OLD))

    def test_add_at_a_commit_names_the_held_tap(self, sandbox, catalogue,
                                                no_clone):
        _rows(OLD)
        with pytest.raises(BoostError) as ei:
            registry.add(NEW, at="a" * 40)
        assert ei.value.message == (
            "%s already tapped as %s (one repository, renamed upstream)"
            % (NEW, OLD))
        assert ei.value.hint.startswith("`boost untap %s`" % OLD)

    def test_tap_new_name_skips_and_says_why_once(self, sandbox, catalogue,
                                                  no_clone, capsys):
        _rows(OLD)
        assert taps_cmd.cmd_tap([NEW]) == 0
        out = capsys.readouterr().out
        assert out.count("renamed upstream") == 1
        assert "%s already tapped as %s" % (NEW, OLD) in out
        assert [t["name"] for t in config.get("taps")] == [OLD]

    def test_catalogue_preview_counts_it_as_tapped(self, sandbox, catalogue,
                                                   capsys):
        _rows(OLD)
        assert taps_cmd.cmd_tap(["--catalog", "--dry-run"]) == 0
        out = capsys.readouterr().out
        assert "%s already tapped as %s (one repository, renamed upstream)" % (
            NEW, OLD) in out
        assert "1 registry to tap, 1 already tapped" in out

    def test_quickstart_says_it_the_way_tap_does(self, sandbox, catalogue,
                                                 cloned, capsys):
        from boost_cli.commands import quickstart
        _rows(OLD)
        _names, outcome = quickstart._tap_defaults(
            [{"name": NEW, "url": GH + NEW}], {}, dry_run=False)
        assert cloned == []
        assert outcome.already == [NEW]
        assert "%s already tapped as %s (one repository, renamed upstream)" % (
            NEW, OLD) in capsys.readouterr().out
