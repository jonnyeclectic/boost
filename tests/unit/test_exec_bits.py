# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Exec bits: recorded beside the content hash, compared apart from it."""
from __future__ import annotations

import sys

import pytest

from boost_cli.core import integrity, staleness, store, util

posix = pytest.mark.skipif(sys.platform == "win32", reason="no POSIX exec bit")


def _tree(root):
    (root / "scripts").mkdir(parents=True)
    (root / ".git").mkdir()
    for rel, mode in (("SKILL.md", 0o644), ("scripts/b.sh", 0o755),
                      ("scripts/a.sh", 0o744), ("scripts/g.sh", 0o654),
                      (".git/hook", 0o755)):
        (root / rel).write_text("x", encoding="utf-8")
        (root / rel).chmod(mode)
    return root


@posix
def test_exec_bits_lists_owner_executable_hashed_files_sorted(tmp_path):
    # g.sh is group-executable only: the owner bit is the one that counts.
    assert util.exec_bits(_tree(tmp_path / "s")) == [
        "scripts/a.sh", "scripts/b.sh"]


@posix
def test_a_mode_does_not_change_the_content_hash(tmp_path):
    root = _tree(tmp_path / "s")
    before = util.sha256_dir(root)
    (root / "SKILL.md").chmod(0o755)
    assert util.sha256_dir(root) == before


@posix
def test_exec_drifted(tmp_path):
    root = _tree(tmp_path / "s")
    assert integrity.exec_drifted(root, {}) is False
    assert integrity.exec_drifted(
        root, {"exec": ["scripts/a.sh", "scripts/b.sh"]}) is False
    assert integrity.exec_drifted(root, {"exec": ["scripts/a.sh"]}) is True
    assert integrity.exec_drifted(root, {"exec": []}) is True


def test_windows_records_and_compares_no_exec_bits(tmp_path, monkeypatch):
    """`os.stat` reports an exec bit by extension there: unknown, not []."""
    root = tmp_path / "s"
    root.mkdir()
    (root / "run.sh").write_text("x", encoding="utf-8")
    monkeypatch.setattr(util.os, "name", "nt")
    assert util.exec_bits(root) is None
    assert integrity.exec_drifted(root, {"exec": ["run.sh"]}) is False
    assert integrity.exec_drifted(root, {"exec": []}) is False
    assert store.source_exec_changed({}, {}, root) is False


@posix
def test_source_exec_changed_without_a_baseline_is_false(tmp_path):
    assert store.source_exec_changed({}, {}, None) is False
    assert store.source_exec_changed({}, {}, tmp_path / "gone") is False


def test_upstream_reason_counts_a_mode_change_as_content():
    args = ("1.0.0", "1.0.0", "old", "new", "sha", "sha")
    assert staleness.upstream_reason(*args) is None
    assert staleness.upstream_reason(*args, exec_changed=True) == \
        staleness.CONTENT
    # Still only once the tap has moved, as for a content change.
    assert staleness.upstream_reason(
        "1.0.0", "1.0.0", "same", "same", "sha", "sha",
        exec_changed=True) is None


def test_drift_state_counts_a_mode_change_as_upstream_moved():
    assert staleness.drift_state("s", "s", False, "s") == staleness.IN_SYNC
    assert staleness.drift_state("s", "s", False, "s", exec_changed=True) \
        == staleness.UPSTREAM_MOVED
    # A local edit still outranks it.
    assert staleness.drift_state("x", "s", False, "s", exec_changed=True) \
        == staleness.LOCAL_EDITS


@posix
def test_source_exec_changed_with_an_unreadable_source_is_false(sandbox):
    """A tap that is not configured is no exec signal, not a crash: the
    content check beside this one owns the missing-source finding."""
    entry = {"name": "beta", "tap": "no-such-tap", "rel_dir": "."}
    assert store.source_exec_changed(entry, {"exec": []}, None) is False
