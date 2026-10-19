# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional: a dirless agent row and a disabled agent's links, end to end.

`boost config set agents.curosr.enabled true` saves a row with no dir, and
install used to link into the working directory for it while doctor said
healthy. Uninstalling while an agent was disabled left that agent's link
dangling, and doctor could not see it because it only looked in enabled
agents' dirs.
"""
from __future__ import annotations

import os
import shutil
import sys

import pytest

from boost_cli.core import agents, config, paths

pytestmark = pytest.mark.skipif(sys.platform == "win32",
                                reason="symlink semantics differ on Windows")


@pytest.fixture(autouse=True)
def _fresh_warnings(monkeypatch):
    monkeypatch.setattr(agents, "_WARNED_DIRLESS", set(), raising=False)


def _tap(boost, src, dest):
    shutil.copytree(src, dest)
    boost("tap", dest)


def _disable_cursor():
    cfg = config.load()
    cfg["agents"]["cursor"]["enabled"] = False
    config.save(cfg)


class TestDirlessRow:
    def test_install_skips_it_and_doctor_names_it(self, boost, fixture_tap_src,
                                                  tmp_path):
        _tap(boost, fixture_tap_src, tmp_path / "dirguard-fn-cwd-tap")
        boost("config", "set", "agents.curosr.enabled", "true")
        res = boost("install", "brainstorming")
        assert not os.path.lexists(os.path.join(os.getcwd(), "brainstorming"))
        assert "curosr" not in res.out
        assert "agents.curosr has no dir" in res.err
        doc = boost("doctor", expect=1)
        text = doc.out + doc.err
        assert "agents.curosr has no dir" in text
        assert "boost config set agents.curosr.dir" in text
        # Reported once, by doctor itself, not again as the skip warning.
        assert text.count("agents.curosr has no dir") == 1


class TestDisabledAgentLinks:
    @pytest.fixture()
    def installed_then_disabled(self, boost, fixture_tap_src, tmp_path,
                                sandbox):
        _tap(boost, fixture_tap_src, tmp_path / "dirguard-fn-off-tap")
        boost("install", "brainstorming")
        link = sandbox / ".cursor" / "skills" / "brainstorming"
        assert link.is_symlink()
        _disable_cursor()
        return link

    def test_uninstall_removes_it_and_doctor_stays_healthy(
            self, boost, installed_then_disabled):
        link = installed_then_disabled
        boost("uninstall", "brainstorming")
        assert not os.path.lexists(link)
        doc = boost("doctor")
        assert "0 broken links" in doc.out

    def test_doctor_counts_and_heal_removes_a_dangling_one(
            self, boost, installed_then_disabled, sandbox):
        link = installed_then_disabled
        # The state the old uninstall left: store dir gone, link dangling.
        stray = link.parent / "gone-skill"
        stray.symlink_to(paths.store_dir() / "gone-skill")
        doc = boost("doctor", expect=1)
        assert "1 broken link" in doc.out
        boost("heal")
        assert not os.path.lexists(stray)
        assert link.is_symlink()

    def test_heal_leaves_a_foreign_dangling_link(
            self, boost, installed_then_disabled, tmp_path):
        foreign = installed_then_disabled.parent / "theirs"
        foreign.symlink_to(tmp_path / "unmounted-volume")
        boost("heal", expect=None)
        assert foreign.is_symlink()

    def test_gemini_shared_dir_is_never_swept(self, boost,
                                              installed_then_disabled, sandbox):
        gem = sandbox / ".gemini" / "skills"
        gem.mkdir(parents=True, exist_ok=True)
        planted = gem / "gone-skill"
        planted.symlink_to(paths.store_dir() / "gone-skill")
        boost("heal", expect=None)
        assert planted.is_symlink()
