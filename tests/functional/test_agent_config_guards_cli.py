# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional: an agent dir that is the store, a relative dir, string flags.

With ``~/.cursor/skills -> ~/.agents/skills``, install, doctor, sync and heal
each told the user to move or delete every installed skill's *store* copy —
and following that advice deleted it. A relative ``agents.cursor.dir`` was
saved behind a check mark and grew a skills tree in every cwd. And
``"enabled": "false"`` linked the agent anyway.
"""
from __future__ import annotations

import json
import os
import shutil
import sys

import pytest

from boost_cli.core import agents, config, paths, util

pytestmark = pytest.mark.skipif(sys.platform == "win32",
                                reason="symlink semantics differ on Windows")


@pytest.fixture(autouse=True)
def _fresh_warnings():
    saved = (set(agents._WARNED_DIRLESS), set(agents._WARNED_FLAGS))
    agents._WARNED_DIRLESS.clear()
    agents._WARNED_FLAGS.clear()
    yield
    agents._WARNED_DIRLESS.clear()
    agents._WARNED_DIRLESS.update(saved[0])
    agents._WARNED_FLAGS.clear()
    agents._WARNED_FLAGS.update(saved[1])


def _tap(boost, src, dest):
    shutil.copytree(src, dest)
    boost("tap", dest)


def _patch_row(name, **fields):
    cfg = config.load()
    cfg["agents"].setdefault(name, {}).update(fields)
    config.save(cfg)


def _flat(res):
    return " ".join((res.out + res.err).split())


class TestStoreAlias:
    def test_no_command_advises_deleting_the_store(self, boost, sandbox,
                                                   fixture_tap_src, tmp_path):
        _tap(boost, fixture_tap_src, tmp_path / "alias-fn-tap")
        boost("install", "brainstorming", "tdd-workflow")
        cursor = sandbox / ".cursor" / "skills"
        util.rmtree(cursor)
        cursor.symlink_to(paths.store_dir())
        before = sorted(os.listdir(paths.store_dir()))

        inst = boost("install", "cowboy-coding")
        assert "not managed by boost" not in _flat(inst)
        doc = boost("doctor")
        text = _flat(doc)
        assert "move or delete" not in text
        assert ("agents.cursor.dir (~/.cursor/skills) is the canonical store, "
                "so Cursor reads every skill there directly — boost does not "
                "link into it") in text
        for cmd in ("sync", "heal"):
            assert "move or delete" not in _flat(boost(cmd))
        assert sorted(os.listdir(paths.store_dir())) == sorted(
            [*before, "cowboy-coding"])
        assert cursor.is_symlink()

    def test_doctor_json_records_the_note(self, boost, sandbox):
        cursor = sandbox / ".cursor" / "skills"
        cursor.parent.mkdir(parents=True, exist_ok=True)
        paths.store_dir().mkdir(parents=True, exist_ok=True)
        cursor.symlink_to(paths.store_dir())
        doc = boost("doctor", "--json", expect=None)
        checks = json.loads(doc.out)["checks"]
        notes = [c for c in checks if c["name"] == "agent-config"]
        assert [c["status"] for c in notes] == ["info"]
        assert notes[0]["message"].startswith("agents.cursor.dir (")


class TestRelativeDir:
    def test_config_set_refuses_it(self, boost):
        res = boost("config", "set", "agents.cursor.dir", "cursor-rel/skills",
                    expect=1)
        assert ("agents.cursor.dir expects an absolute path, or one starting "
                "with ~ or ${VAR} — a relative dir resolves against the "
                "working directory") in _flat(res)
        assert config.get("agents.cursor.dir") == "~/.cursor/skills"

    def test_hand_edit_refuses_install_in_any_cwd(self, boost,
                                                  fixture_tap_src, tmp_path):
        _tap(boost, fixture_tap_src, tmp_path / "rel-fn-tap")
        _patch_row("cursor", dir="cursor-rel/skills")
        for w in ("w1", "w2"):
            cwd = tmp_path / w
            cwd.mkdir()
            os.chdir(cwd)
            res = boost("install", "brainstorming", expect=1)
            assert ("agents.cursor.dir: 'cursor-rel/skills' is a relative "
                    "path") in _flat(res)
            assert list(cwd.iterdir()) == []
        # Refused before the copy: nothing lands in the store unrecorded.
        assert not (paths.store_dir() / "brainstorming").exists()
        doc = boost("doctor", expect=1)
        assert ("agents.cursor.dir: 'cursor-rel/skills' is a relative path, "
                "which would resolve against whatever directory boost runs "
                "from — use an absolute path, or one starting with ~ or "
                "${VAR}, or set a path with") in _flat(doc)


class TestStringFlags:
    def test_enabled_string_false_is_not_linked(self, boost, sandbox,
                                                fixture_tap_src, tmp_path):
        _tap(boost, fixture_tap_src, tmp_path / "flag-fn-tap")
        _patch_row("cursor", enabled="false")
        boost("install", "brainstorming")
        assert not os.path.lexists(sandbox / ".cursor" / "skills"
                                   / "brainstorming")
        assert (sandbox / ".claude" / "skills" / "brainstorming").is_symlink()

    def test_links_skills_string_false_keeps_gemini_unlinked(
            self, boost, sandbox, fixture_tap_src, tmp_path):
        _tap(boost, fixture_tap_src, tmp_path / "flag-fn-tap2")
        _patch_row("gemini", links_skills="false")
        boost("install", "brainstorming")
        boost("sync")
        assert not os.path.lexists(sandbox / ".gemini" / "skills"
                                   / "brainstorming")

    def test_doctor_names_a_junk_flag_once(self, boost):
        _patch_row("gemini", links_skills="nope")
        doc = boost("doctor", expect=1)
        text = _flat(doc)
        assert ('agents.gemini.links_skills is "nope", not a boolean, so boost '
                "reads it as false — fix it with `boost config set "
                "agents.gemini.links_skills <true|false>`") in text
        # Claimed by doctor, so the skip warning does not print beside it.
        assert "agents.gemini.links_skills expects" not in text
