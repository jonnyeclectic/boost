# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""What `boost clean` may sweep inside the store, and where it looks for
broken links: the dirs the lock claims, the dirs heal sweeps, nothing else."""
from __future__ import annotations

import sys

import pytest

from boost_cli.core import lockfile, paths, store


def _skill_copy(name):
    return {"version": "1", "tap": "t", "materializations": [
        {"agent": None, "slot": "skill",
         "path": str(paths.store_dir() / name / "SKILL.md")},
        {"agent": "claude-code", "slot": "commands",
         "path": str(paths.home() / ".claude" / "commands" / (name + ".md"))}]}


class TestRecordedStoreDirs:
    def test_skills_then_workflow_copies_sorted(self, sandbox):
        lockfile.set_skill("zeta", {"version": "1"})
        lockfile.set_skill("alpha", {"version": "1"})
        lockfile.set_workflow("ship", _skill_copy("ship"))
        root = paths.store_dir()
        assert store.recorded_store_dirs() == [
            root / "alpha", root / "ship", root / "zeta"]

    def test_a_name_no_store_dir_could_have_is_skipped(self, sandbox):
        lockfile.set_skill("../escape", {"version": "1"})
        wf = _skill_copy("ship")
        wf["materializations"][0]["path"] = str(paths.home() / "x" / "SKILL.md")
        lockfile.set_workflow("ship", wf)
        assert store.recorded_store_dirs() == []

    def test_an_empty_lock_claims_nothing(self, sandbox):
        assert store.recorded_store_dirs() == []


class TestHygieneCandidates:
    def test_no_store_has_none(self, sandbox):
        assert store.hygiene_candidates() == []

    def test_top_level_junk_and_recorded_dirs_only(self, sandbox):
        root = paths.store_dir()
        (root / "brainstorming" / "sub").mkdir(parents=True)
        (root / "brainstorming" / "sub" / ".DS_Store").write_bytes(b"x")
        (root / "notskill" / "__pycache__").mkdir(parents=True)
        (root / ".DS_Store").write_bytes(b"x")
        (root / "README").write_bytes(b"x")
        lockfile.set_skill("brainstorming", {"version": "1"})
        lockfile.set_skill("gone", {"version": "1"})     # no dir: skipped
        assert store.hygiene_candidates() == sorted([
            root / ".DS_Store", root / "brainstorming" / "sub",
            root / "brainstorming" / "sub" / ".DS_Store"])

    @pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privilege")
    def test_a_recorded_name_that_is_a_link_is_not_walked(self, sandbox):
        # A store entry that is a symlink leads out of the store: what sits
        # under its target is not boost's to delete.
        outside = paths.home() / "elsewhere" / "__pycache__"
        outside.mkdir(parents=True)
        (outside / "x.pyc").write_bytes(b"x")
        paths.store_dir().mkdir(parents=True, exist_ok=True)
        (paths.store_dir() / "linked").symlink_to(outside.parent)
        lockfile.set_skill("linked", {"version": "1"})
        assert store.hygiene_candidates() == []
