# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: taps never download Git LFS payloads.

A tap is indexed for its Markdown; boost never reads an LFS payload. Without
GIT_LFS_SKIP_SMUDGE, tapping a repo that keeps large media in LFS downloads all of it on
clone — heygen-com/hyperframes tracks 163 LFS files totalling 578 MB (83 of them .mp4
regression baselines) alongside the 31 SKILL.md files boost actually wants.

Pointer files still check out as ordinary text, so discovery is unaffected. The variable
is inert where git-lfs is not installed, which is why this is tested at the env level
rather than by observing a clone.
"""
from __future__ import annotations

import os
import subprocess

from boost_cli.core import gitutil


def _capture(monkeypatch) -> dict:
    """Run a git command with subprocess.run stubbed; return the kwargs it received."""
    seen: dict = {}

    def fake_run(argv, **kwargs):
        seen.setdefault("calls", []).append(argv)
        seen["argv"] = argv
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(gitutil, "has_git", lambda: True)
    monkeypatch.setattr(subprocess, "run", fake_run)
    return seen


class TestLfsSmudgeIsSkipped:
    def test_every_git_call_skips_lfs_smudge(self, monkeypatch):
        seen = _capture(monkeypatch)

        gitutil.run(["status"])

        assert seen["env"]["GIT_LFS_SKIP_SMUDGE"] == "1"

    def test_clone_skips_lfs_smudge(self, monkeypatch, tmp_path):
        seen = _capture(monkeypatch)

        gitutil.clone_shallow("https://example.test/repo.git", tmp_path / "dest")

        assert seen["env"]["GIT_LFS_SKIP_SMUDGE"] == "1"
        # `argv` is the last call — the sparse cone. The clone itself is first.
        clone = seen["calls"][0]
        assert "--depth" in clone and "1" in clone

    def test_the_inherited_environment_is_preserved(self, monkeypatch):
        """Only one variable is added; PATH and friends must survive."""
        monkeypatch.setenv("BOOST_SENTINEL", "kept")
        seen = _capture(monkeypatch)

        gitutil.run(["status"])

        assert seen["env"]["BOOST_SENTINEL"] == "kept"
        assert seen["env"]["PATH"] == os.environ["PATH"]

    def test_the_process_environment_is_not_mutated(self, monkeypatch):
        """The variable is passed per-call, never leaked into boost's own environment."""
        monkeypatch.delenv("GIT_LFS_SKIP_SMUDGE", raising=False)
        _capture(monkeypatch)

        gitutil.run(["status"])

        assert "GIT_LFS_SKIP_SMUDGE" not in os.environ
