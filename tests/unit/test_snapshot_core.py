# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""core.snapshot: a saved store always restores, and a failed restore never
empties the store; plus the rollback/export helpers in core.store."""
from __future__ import annotations

import os
import sys
import tarfile

import pytest

from boost_cli.core import lockfile, projectlock, snapshot, store
from boost_cli.errors import BoostError


def _store(tmp_path):
    root = tmp_path / "snapcore-store"
    (root / "alpha").mkdir(parents=True)
    (root / "alpha" / "SKILL.md").write_text("# alpha\n", encoding="utf-8")
    (root / ".skill-lock.json").write_text("{}\n", encoding="utf-8")
    return root


def _tree(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))


def test_archive_then_restore_round_trips(tmp_path):
    root = _store(tmp_path)
    tar = tmp_path / "snapcore-rt.tar.gz"
    res = snapshot.archive(root, tar)
    assert res.dereferenced == [] and res.skipped == []
    (root / "alpha" / "SKILL.md").write_text("changed\n", encoding="utf-8")
    (root / "beta").mkdir()
    snapshot.restore(tar, root, "snap-rt")
    assert _tree(root) == [".skill-lock.json", "alpha", "alpha/SKILL.md"]
    assert (root / "alpha" / "SKILL.md").read_text(encoding="utf-8") == "# alpha\n"
    assert [p.name for p in root.parent.iterdir()
            if p.name.startswith(".boost-restore")] == []


@pytest.mark.skipif(sys.platform == "win32", reason="needs symlinks")
def test_archive_dereferences_top_level_links(tmp_path):
    root = _store(tmp_path)
    target = tmp_path / "snapcore-dev"
    target.mkdir()
    (target / "SKILL.md").write_text("# dev\n", encoding="utf-8")
    (root / "dev").symlink_to(target)
    (root / "dangling").symlink_to(tmp_path / "snapcore-missing")
    tar = tmp_path / "snapcore-deref.tar.gz"
    res = snapshot.archive(root, tar)
    assert res.dereferenced == ["dev"]
    assert res.skipped == ["dangling"]
    with tarfile.open(str(tar)) as tf:
        names = {m.name: m for m in tf.getmembers()}
    assert names["dev"].isdir()
    assert "dev/SKILL.md" in names
    assert "dangling" not in names


@pytest.mark.skipif(sys.platform == "win32", reason="needs symlinks")
def test_archive_refuses_a_nested_absolute_link(tmp_path):
    root = _store(tmp_path)
    (root / "alpha" / "escape").symlink_to("/etc")
    tar = tmp_path / "snapcore-nested.tar.gz"
    with pytest.raises(BoostError) as ei:
        snapshot.archive(root, tar)
    assert "cannot snapshot alpha/escape" in ei.value.message
    assert not tar.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="needs symlinks")
def test_archive_keeps_a_relative_link_inside_a_skill(tmp_path):
    root = _store(tmp_path)
    (root / "alpha" / "README.md").symlink_to("SKILL.md")
    tar = tmp_path / "snapcore-rel.tar.gz"
    snapshot.archive(root, tar)
    (root / "alpha" / "README.md").unlink()
    snapshot.restore(tar, root, "snap-rel")
    link = root / "alpha" / "README.md"
    assert link.is_symlink() and os.readlink(link) == "SKILL.md"


def test_restore_refused_member_leaves_store_untouched(tmp_path):
    root = _store(tmp_path)
    before = _tree(root)
    tar = tmp_path / "snapcore-bad.tar.gz"
    with tarfile.open(str(tar), "w:gz") as tf:
        ti = tarfile.TarInfo("evil")
        ti.type = tarfile.SYMTYPE
        ti.linkname = "/etc"
        tf.addfile(ti)
    with pytest.raises(BoostError) as ei:
        snapshot.restore(tar, root, "snap-bad")
    assert ei.value.message.startswith("snapshot snap-bad cannot be restored")
    assert ei.value.hint == snapshot.UNTOUCHED_HINT
    assert _tree(root) == before
    assert [p.name for p in root.parent.iterdir()
            if p.name.startswith(".boost-restore")] == []


def test_restore_unreadable_and_truncated(tmp_path):
    root = _store(tmp_path)
    before = _tree(root)
    junk = tmp_path / "snapcore-junk.tar.gz"
    junk.write_bytes(b"not a tar")
    with pytest.raises(BoostError) as ei:
        snapshot.restore(junk, root, "snap-junk")
    assert ei.value.message.startswith("snapshot snap-junk is unreadable")
    good = tmp_path / "snapcore-good.tar.gz"
    snapshot.archive(root, good)
    cut = tmp_path / "snapcore-cut.tar.gz"
    cut.write_bytes(good.read_bytes()[:-20])
    with pytest.raises(BoostError) as ei:
        snapshot.restore(cut, root, "snap-cut")
    assert "snap-cut" in ei.value.message
    assert ei.value.hint == snapshot.UNTOUCHED_HINT
    assert _tree(root) == before


def test_restore_swap_failure_puts_old_children_back(tmp_path, monkeypatch):
    root = _store(tmp_path)
    (root / "zeta").mkdir()
    tar = tmp_path / "snapcore-swap.tar.gz"
    snapshot.archive(root, tar)
    (root / "zeta").rmdir()
    (root / "local-only").mkdir()
    before = _tree(root)
    real = os.replace
    calls = {"in": 0}

    def flaky(src, dst):
        # Moves into root from staging: let the first through, fail the second.
        if os.path.dirname(str(dst)) == str(root):
            calls["in"] += 1
            if calls["in"] == 2:
                raise OSError("disk full")
        return real(src, dst)

    monkeypatch.setattr(snapshot.os, "replace", flaky)
    with pytest.raises(BoostError) as ei:
        snapshot.restore(tar, root, "snap-swap")
    assert "disk full" in ei.value.message
    assert ei.value.hint == "the previous store contents were put back"
    assert _tree(root) == before


def test_reapply_recorded_holds(sandbox):
    lockfile.set_skill("snapcore-a", {"version": "1.0.0", "commit": "c1"})
    assert store.reapply_recorded_holds("snapcore-a", {}) is False
    assert "pinned" not in lockfile.get_skill("snapcore-a")

    assert store.reapply_recorded_holds("snapcore-a", {"pinned": True}) is False
    row = lockfile.get_skill("snapcore-a")
    assert row["pinned"] is True and "commit_pin" not in row

    assert store.reapply_recorded_holds(
        "snapcore-a", {"commit_pin": "c1"}) is False
    assert lockfile.get_skill("snapcore-a")["commit_pin"] == "c1"

    lockfile.set_skill("snapcore-b", {"version": "1.0.0", "commit": "c2"})
    assert store.reapply_recorded_holds(
        "snapcore-b", {"pinned": False, "commit_pin": "c1"}) is True
    row = lockfile.get_skill("snapcore-b")
    assert row["commit_pin"] == "c1" and "pinned" not in row

    assert store.reapply_recorded_holds(
        "snapcore-missing", {"pinned": True}) is False
    assert lockfile.get_skill("snapcore-missing") is None


def test_project_skills(sandbox, tmp_path, monkeypatch):
    repo = tmp_path / "snapcore-repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.chdir(repo)
    base, skills = store.project_skills()
    assert str(base) == str(repo) and skills == {}
    projectlock.set_skill(repo, "snapcore-p", {"version": "2.0.0"})
    base, skills = store.project_skills()
    assert list(skills) == ["snapcore-p"]
    assert skills["snapcore-p"]["version"] == "2.0.0"
    monkeypatch.chdir(sandbox)
    assert store.project_skills() == (None, {})
