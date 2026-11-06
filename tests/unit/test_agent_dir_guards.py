# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit: an agent row with no dir is skipped, and removal reaches disabled agents.

Two holes in the agent table. A row with no ``dir`` expanded to ``Path("")``,
which is the working directory, so an install linked the skill wherever it
ran. And :func:`store.unlink_agents` walked only *enabled* agents, so
uninstalling while cursor was disabled left its link dangling into the
deleted store dir.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from boost_cli.core import agents, catalog, config, registry, store
from boost_cli.errors import BoostError

needs_symlinks = pytest.mark.skipif(sys.platform == "win32",
                                    reason="symlink semantics differ on Windows")


@pytest.fixture(autouse=True)
def _fresh_warnings(monkeypatch):
    monkeypatch.setattr(agents, "_WARNED_DIRLESS", set(), raising=False)


def _tap(src, dest):
    shutil.copytree(src, dest)
    registry.add(str(dest))


def _set_row(name, row):
    cfg = config.load()
    cfg["agents"][name] = row
    config.save(cfg)


class TestDirlessRow:
    @pytest.mark.parametrize("row", [
        {"enabled": True},
        {"enabled": True, "dir": ""},
        {"enabled": True, "dir": "   "},
        {"enabled": True, "dir": None},
        {"enabled": True, "dir": "."},
        {"enabled": True, "dir": "${BOOST_TEST_DIRGUARD_NOPE:-}"},
    ])
    def test_is_left_out_of_every_agent_set(self, sandbox, monkeypatch, row):
        monkeypatch.delenv("BOOST_TEST_DIRGUARD_NOPE", raising=False)
        _set_row("curosr", row)
        assert "curosr" not in agents.known_agents()
        assert "curosr" not in agents.linking_agents()
        assert "curosr" not in agents.unlinking_agents()
        assert "curosr" not in agents.enabled_agents()
        assert agents.dirless() == ["curosr"]
        # Skipped, not refused: the rest of the table still resolves.
        assert agents.check() == []
        assert "cursor" in agents.known_agents()

    def test_warns_once_naming_the_key(self, sandbox, capsys):
        _set_row("curosr", {"enabled": True})
        agents.known_agents()
        agents.known_agents()
        err = capsys.readouterr().err
        assert err.count("agents.curosr has no dir") == 1
        assert "boost config set agents.curosr.dir" in err
        assert "boost config unset agents.curosr" in err

    def test_claim_silences_the_warning(self, sandbox, capsys):
        _set_row("curosr", {"enabled": True})
        assert agents.dirless(claim=True) == ["curosr"]
        agents.known_agents()
        assert "has no dir" not in capsys.readouterr().err

    def test_dirless_without_claim_keeps_the_warning(self, sandbox, capsys):
        _set_row("curosr", {"enabled": True})
        agents.dirless()
        agents.known_agents()
        assert "agents.curosr has no dir" in capsys.readouterr().err

    def test_a_real_dir_is_not_dirless(self, sandbox):
        assert agents.dirless() == []
        _set_row("aider", {"enabled": True, "dir": "~/.aider/skills"})
        assert agents.known_agents()["aider"]["dir"] == sandbox / ".aider" / "skills"
        assert agents.dirless() == []

    def test_dirless_is_in_config_order(self, sandbox):
        _set_row("zeta", {"enabled": True})
        _set_row("alpha", {"dir": ""})
        assert agents.dirless() == ["zeta", "alpha"]

    def test_unresolvable_row_stays_check_s_not_dirless(self, sandbox,
                                                        monkeypatch):
        monkeypatch.delenv("BOOST_TEST_DIRGUARD_NOPE", raising=False)
        _set_row("cursor", {"dir": "${BOOST_TEST_DIRGUARD_NOPE}/skills"})
        assert agents.dirless() == []
        assert [n for n, _e in agents.check()] == ["cursor"]
        with pytest.raises(BoostError):
            agents.known_agents()

    @needs_symlinks
    def test_install_links_nothing_into_cwd(self, sandbox, fixture_tap_src,
                                            tmp_path):
        _set_row("curosr", {"enabled": True})
        _tap(fixture_tap_src, tmp_path / "dirguard-cwd-tap")
        res = store.install(catalog.resolve_one("brainstorming"))
        cwd = Path(os.getcwd())
        assert not os.path.lexists(cwd / "brainstorming")
        assert "curosr" not in (res.linked or [])
        assert (sandbox / ".claude" / "skills" / "brainstorming").is_symlink()


@needs_symlinks
class TestUnlinkReachesDisabledAgents:
    @pytest.fixture()
    def linked(self, sandbox, fixture_tap_src, tmp_path):
        _tap(fixture_tap_src, tmp_path / "dirguard-unlink-tap")
        store.install(catalog.resolve_one("brainstorming"))
        link = sandbox / ".cursor" / "skills" / "brainstorming"
        assert link.is_symlink()
        cfg = config.load()
        cfg["agents"]["cursor"]["enabled"] = False
        config.save(cfg)
        return link

    def test_unlinking_agents_keeps_disabled_drops_native(self, linked):
        assert "cursor" not in agents.linking_agents()
        wide = agents.unlinking_agents()
        assert "cursor" in wide
        assert "gemini" not in wide
        assert "codex" not in wide
        assert str(wide["cursor"]) == str(linked.parent)

    def test_uninstall_removes_the_disabled_agent_s_link(self, linked):
        res = store.uninstall("brainstorming")
        assert not os.path.lexists(linked)
        assert "cursor" in res["unlinked"]
        assert "claude-code" in res["unlinked"]

    def test_unlink_leaves_a_link_that_is_not_boost_s(self, linked, tmp_path):
        mine = tmp_path / "my-checkout"
        mine.mkdir()
        linked.unlink()
        linked.symlink_to(mine)
        assert "cursor" not in store.unlink_agents("brainstorming")
        assert linked.is_symlink()
        assert str(Path(os.readlink(linked))) == str(mine)

    def test_unlink_leaves_a_real_directory(self, linked):
        linked.unlink()
        linked.mkdir()
        assert "cursor" not in store.unlink_agents("brainstorming")
        assert linked.is_dir()

    def test_native_store_dir_is_never_touched(self, linked, sandbox):
        gem = sandbox / ".gemini" / "skills"
        gem.mkdir(parents=True, exist_ok=True)
        planted = gem / "brainstorming"
        planted.symlink_to(store.skill_store_dir("brainstorming"))
        store.uninstall("brainstorming")
        assert planted.is_symlink()

    def test_sync_sweeps_a_dangling_link_in_the_disabled_dir(self, linked):
        stray = linked.parent / "gone-skill"
        stray.symlink_to(store.skill_store_dir("gone-skill"))
        stale = store.sync_plan()["stale_links"]
        assert str(stray) in stale
        # The live link to an installed skill is not stale, disabled or not.
        assert str(linked) not in stale

    def test_sync_does_not_sweep_the_native_store_dir(self, linked, sandbox):
        gem = sandbox / ".gemini" / "skills"
        gem.mkdir(parents=True, exist_ok=True)
        planted = gem / "gone-skill"
        planted.symlink_to(store.skill_store_dir("gone-skill"))
        assert str(planted) not in store.sync_plan()["stale_links"]
