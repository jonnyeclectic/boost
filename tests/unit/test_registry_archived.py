# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a catalogue row GitHub has archived says so wherever it is shown.

An archived repository still clones and still ships its items, so the row
stays in the catalogue and nothing skips it. What changed is that nothing
upstream will fix it again, and six rows were indistinguishable from live ones
in `boost tap --catalog --dry-run`, quickstart, `boost info` and `discover`.
``config.archived_registries`` is the one lookup all four ask.
"""
from __future__ import annotations

import re

import pytest

from boost_cli.commands import discovery, info, quickstart
from boost_cli.commands import taps as taps_cmd
from boost_cli.core import bootstrap, config, registry

GH = "https://github.com/"
FROZEN, LIVE, OLD = "owner/frozen", "owner/live", "owner/old-name"

# Archived on GitHub on 2026-11-07, re-checked live before they were recorded.
SHIPPED_ARCHIVED = {
    "DVC2/cursor-agent-configs", "brennercruvinel/CCPlugins",
    "iannuttall/claude-agents", "obra/superpowers-skills",
    "steipete/agent-rules", "wshobson/commands",
}


def _row(name, **extra):
    return {"name": name, "url": GH + name, "type": "skill",
            "category": "general", "est_items": 5, "focus": "f " + name,
            **extra}


def _tapped(*names):
    """Configure ``names`` as taps already held, with no clone behind them."""
    cfg = config.load()
    cfg["taps"] = [{"name": n, "url": GH + n, "curated": False} for n in names]
    config.save(cfg)


@pytest.fixture
def catalogue(monkeypatch):
    """FROZEN is archived and was OLD; LIVE is not."""
    rows = [_row(FROZEN, archived=True, formerly=[OLD]), _row(LIVE)]
    monkeypatch.setattr(config, "load_registry_catalog", lambda: list(rows))
    return rows


class TestArchivedRegistries:
    def test_names_the_archived_row_and_its_former_name(self, catalogue):
        assert config.archived_registries() == {FROZEN, OLD}

    @pytest.mark.parametrize("value", [False, None, "true", 1, "yes"])
    def test_only_a_literal_true_is_archived(self, monkeypatch, value):
        """A damaged value is not a verdict about GitHub."""
        monkeypatch.setattr(config, "load_registry_catalog",
                            lambda: [_row(FROZEN, archived=value)])
        assert config.archived_registries() == frozenset()

    def test_a_row_without_the_key_is_live(self, monkeypatch):
        monkeypatch.setattr(config, "load_registry_catalog",
                            lambda: [_row(LIVE)])
        assert config.archived_registries() == frozenset()

    def test_the_note_is_one_phrase(self):
        assert config.ARCHIVED_NOTE == "archived upstream"

    def test_the_shipped_catalogue_marks_the_six(self):
        """Each was archived=True on GitHub on 2026-11-07. DVC2's row was
        also renamed, so its former name is archived with it."""
        assert config.archived_registries() == (
            SHIPPED_ARCHIVED | {"DVC2/cursor_prompts"})

    def test_no_shipped_row_is_dropped_for_being_archived(self):
        names = {r["name"] for r in config.load_registry_catalog()}
        assert names >= SHIPPED_ARCHIVED


class TestTapCatalogPreview:
    def _lines(self, capsys):
        return capsys.readouterr().out.splitlines()

    def test_the_archived_row_is_marked_and_the_live_one_is_not(
            self, sandbox, catalogue, capsys):
        assert taps_cmd.cmd_tap(["--catalog", "--dry-run"]) == 0
        lines = self._lines(capsys)
        frozen = next(ln for ln in lines if ln.startswith(FROZEN))
        live = next(ln for ln in lines if ln.startswith(LIVE))
        assert "archived upstream · f %s" % FROZEN in frozen
        assert "archived" not in live

    def test_the_footer_counts_them(self, sandbox, catalogue, capsys):
        taps_cmd.cmd_tap(["--catalog", "--dry-run"])
        assert ("2 registries to tap (1 archived upstream) · ~10 items"
                in capsys.readouterr().out)

    def test_the_footer_counts_only_the_rows_it_would_tap(
            self, sandbox, catalogue, capsys):
        """An archived row already held is not in the table, so the footer
        that stands in for the FOCUS column does not count it either."""
        _tapped(FROZEN)
        taps_cmd.cmd_tap(["--catalog", "--dry-run"])
        out = capsys.readouterr().out
        assert "1 registry to tap, 1 already tapped · ~5 items" in out
        assert "archived" not in out

    def test_nothing_archived_adds_nothing(self, sandbox, monkeypatch, capsys):
        monkeypatch.setattr(config, "load_registry_catalog",
                            lambda: [_row(LIVE)])
        taps_cmd.cmd_tap(["--catalog", "--dry-run"])
        out = capsys.readouterr().out
        assert "archived" not in out
        assert "1 registry to tap · ~5 items" in out

    def test_an_archived_row_is_still_tapped(self, sandbox, catalogue,
                                             monkeypatch, capsys):
        """Marked, never skipped: whether bulk `--catalog` should skip an
        archived row is a policy this change does not make."""
        seen: list[str] = []

        def fake(spec, curated, pin):
            seen.append(spec)
            name, url = registry.parse_spec(spec)
            return {"spec": spec, "name": name, "url": url, "ok": False,
                    "error": "offline"}
        monkeypatch.setattr(registry, "_clone_one", fake)
        taps_cmd.cmd_tap(["--catalog"])
        assert sorted(seen) == sorted([GH + FROZEN, GH + LIVE])


class TestQuickstartPreview:
    def test_a_named_line_is_marked(self, sandbox, catalogue, capsys):
        quickstart._tap_defaults(
            [{"name": FROZEN, "url": GH + FROZEN},
             {"name": LIVE, "url": GH + LIVE}], {}, dry_run=True)
        lines = capsys.readouterr().out.splitlines()
        assert any(re.search(r"would tap %s \(archived upstream\)$" % FROZEN,
                             ln) for ln in lines), lines
        assert any(re.search(r"would tap %s$" % LIVE, ln) for ln in lines)

    def test_the_summary_line_counts_them(self, sandbox, catalogue, capsys):
        many = [{"name": "o/r%d" % i, "url": GH + "o/r%d" % i}
                for i in range(bootstrap.MAX_NAMED_REGISTRIES)]
        quickstart._tap_defaults([*many, {"name": FROZEN, "url": GH + FROZEN}],
                                 {}, dry_run=True)
        assert ("would tap %d registries (0 pinned to a published shard's "
                "commit, 1 archived upstream)"
                % (bootstrap.MAX_NAMED_REGISTRIES + 1)
                in capsys.readouterr().out)

    def test_the_summary_line_counts_only_what_it_would_tap(
            self, sandbox, catalogue, capsys):
        """An archived registry already held is skipped, not tapped, so the
        count of archived ones it would tap leaves it out."""
        _tapped(FROZEN)
        many = [{"name": "o/r%d" % i, "url": GH + "o/r%d" % i}
                for i in range(bootstrap.MAX_NAMED_REGISTRIES + 1)]
        quickstart._tap_defaults([*many, {"name": FROZEN, "url": GH + FROZEN}],
                                 {}, dry_run=True)
        out = capsys.readouterr().out
        assert ("would tap %d registries (0 pinned to a published shard's "
                "commit)" % (bootstrap.MAX_NAMED_REGISTRIES + 1)) in out
        assert "archived" not in out

    def test_the_summary_line_is_unchanged_without_one(self, sandbox,
                                                      catalogue, capsys):
        many = [{"name": "o/r%d" % i, "url": GH + "o/r%d" % i}
                for i in range(bootstrap.MAX_NAMED_REGISTRIES + 1)]
        quickstart._tap_defaults(many, {}, dry_run=True)
        out = capsys.readouterr().out
        assert "published shard's commit)" in out
        assert "archived" not in out


class TestInfoCard:
    def test_the_tap_row_is_marked(self, catalogue, capsys):
        info._tap_row({"tap": FROZEN})
        assert re.search(r"tap\s+%s  \(archived upstream\)$" % FROZEN,
                         capsys.readouterr().out.rstrip())

    def test_a_tap_held_under_the_former_name_is_marked(self, catalogue,
                                                       capsys):
        info._tap_row({"tap": OLD})
        assert "archived upstream" in capsys.readouterr().out

    def test_a_live_tap_row_is_unchanged(self, catalogue, capsys):
        info._tap_row({"tap": LIVE})
        assert re.search(r"tap\s+%s$" % LIVE, capsys.readouterr().out.rstrip())

    def test_a_card_for_an_item_of_an_archived_tap(self, boost, installed,
                                                   monkeypatch):
        tap = next(t.name for t in registry.list_taps()
                   if t.name != "boost/builtin")
        monkeypatch.setattr(config, "load_registry_catalog",
                            lambda: [_row(tap, archived=True)])
        out = boost("info", installed).out
        assert re.search(r"tap\s+%s  \(archived upstream\)" % re.escape(tap),
                         out)


class TestDiscoverCell:
    def test_the_marker_follows_the_name_and_count(self):
        cell = discovery._repo_cell({"repo": FROZEN, "files": 3},
                                    frozenset({FROZEN}))
        assert cell == "%s (3) (archived upstream)" % FROZEN

    def test_a_repo_the_catalogue_does_not_mark_is_unchanged(self):
        assert discovery._repo_cell({"repo": LIVE}, frozenset({FROZEN})) == LIVE

    def test_a_malformed_repo_is_not_looked_up(self):
        assert discovery._repo_cell({"repo": ["x"]}, frozenset({FROZEN}))
