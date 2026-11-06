# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""core.snapshot: a saved store always restores, and a failed restore never
empties the store; plus the rollback/export helpers in core.store."""
from __future__ import annotations

import json
import os
import sys
import tarfile

import pytest

from boost_cli.core import lockfile, projectlock, snapshot, store, util
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


def _held(tmp_path, name, body):
    d = tmp_path / "snapcore-held" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")
    return d


def test_held_copies_round_trip_beside_the_store(tmp_path):
    root = _store(tmp_path)
    held_root = tmp_path / "snapcore-held"
    beta = _held(tmp_path, "beta", "# beta\n")
    tar = tmp_path / "snapcore-held.tar.gz"
    res = snapshot.archive(root, tar, {"beta": beta,
                                       "gone": held_root / "gone"})
    assert res.held == ["beta"]
    with tarfile.open(str(tar)) as tf:
        assert snapshot.HELD_ARC + "/beta/SKILL.md" in tf.getnames()
    # Lost since the save, and a different copy now held under that name.
    util.rmtree(beta)
    _held(tmp_path, "beta", "newer\n")
    assert snapshot.restore(tar, root, "snap-held", held_root).held == ["beta"]
    assert _tree(root) == [".skill-lock.json", "alpha", "alpha/SKILL.md"]
    assert (held_root / "beta" / "SKILL.md").read_text(
        encoding="utf-8") == "# beta\n"
    assert [p.name for p in root.parent.iterdir()
            if p.name.startswith(".boost-restore")] == []


def test_held_copies_never_land_in_the_store(tmp_path):
    root = _store(tmp_path)
    tar = tmp_path / "snapcore-held2.tar.gz"
    snapshot.archive(root, tar, {"beta": _held(tmp_path, "beta", "b\n")})
    # No held root to put them in: dropped, still not in the store.
    assert snapshot.restore(tar, root, "snap-held2").held == []
    assert snapshot.HELD_ARC not in os.listdir(root)
    assert snapshot.archive(root, tmp_path / "snapcore-none.tar.gz").held == []
    assert snapshot.restore(tmp_path / "snapcore-none.tar.gz", root, "s",
                            tmp_path / "snapcore-held").held == []


def test_a_store_child_named_like_the_held_dir_is_refused(tmp_path):
    root = _store(tmp_path)
    (root / snapshot.HELD_ARC).mkdir()
    tar = tmp_path / "snapcore-reserved.tar.gz"
    with pytest.raises(BoostError) as ei:
        snapshot.archive(root, tar)
    assert ei.value.message == ("cannot snapshot .boost-held: the name is "
                                "reserved for held copies")
    assert not tar.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="needs symlinks")
def test_a_symlinked_held_copy_is_not_archived(tmp_path):
    root = _store(tmp_path)
    real = _held(tmp_path, "beta", "b\n")
    link = tmp_path / "snapcore-heldlink"
    link.symlink_to(real)
    tar = tmp_path / "snapcore-heldlink.tar.gz"
    assert snapshot.archive(root, tar, {"beta": link}).held == []


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


def _bytes(root):
    """Every file under ``root`` with its bytes — what an interrupted
    restore must leave exactly as it was."""
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _restore_dirs(root):
    return sorted(p.name for p in root.parent.iterdir()
                  if p.name.startswith(".boost-restore"))


def _edited_store(tmp_path):
    """A store saved, then edited by hand: a newer SKILL.md, a new skill,
    a real lock — so a rollback that loses or mixes anything shows."""
    root = _store(tmp_path)
    tar = tmp_path / "snapcore-ki.tar.gz"
    snapshot.archive(root, tar)
    (root / "alpha" / "SKILL.md").write_text("# alpha\nmy edit\n",
                                             encoding="utf-8")
    (root / "beta").mkdir()
    (root / "beta" / "SKILL.md").write_text("# beta\n", encoding="utf-8")
    (root / ".skill-lock.json").write_text(
        '{"version": 3, "skills": {"alpha": {}, "beta": {}}}\n',
        encoding="utf-8")
    return root, tar


@pytest.mark.parametrize("nth", [1, 2, 3, 4, 5])
def test_an_interrupted_swap_leaves_the_store_byte_identical(
        tmp_path, monkeypatch, nth):
    # Three children move out (calls 1-3), two move in (4-5). Ctrl-C at any
    # of them used to skip the move-back, and restore's cleanup then deleted
    # the parked originals: the lock and every skill not yet moved in, gone.
    root, tar = _edited_store(tmp_path)
    before = _bytes(root)
    real = os.replace
    calls = {"n": 0}

    def interrupted(src, dst):
        calls["n"] += 1
        if calls["n"] == nth:
            raise KeyboardInterrupt
        return real(src, dst)

    monkeypatch.setattr(snapshot.os, "replace", interrupted)
    with pytest.raises(KeyboardInterrupt):
        snapshot.restore(tar, root, "snap-ki")
    assert _bytes(root) == before
    assert _tree(root) == [".skill-lock.json", "alpha", "alpha/SKILL.md",
                           "beta", "beta/SKILL.md"]
    assert _restore_dirs(root) == []


@pytest.mark.parametrize("nth", [6, 7])
def test_a_skill_dir_already_moved_in_goes_back_out(tmp_path, monkeypatch, nth):
    # Skills are dirs, and os.replace will not overwrite a non-empty one: an
    # archive copy left in root would keep the parked original out of it.
    root, tar = _edited_store(tmp_path)
    (root / "zeta").mkdir()
    (root / "zeta" / "SKILL.md").write_text("# zeta live\n", encoding="utf-8")
    zeta_src = tmp_path / "snapcore-zeta"
    (zeta_src / "zeta").mkdir(parents=True)
    (zeta_src / "zeta" / "SKILL.md").write_text("# zeta archived\n",
                                                encoding="utf-8")
    with tarfile.open(str(tar), "r:gz") as tf:
        tf.extractall(str(zeta_src), filter="data")
    with tarfile.open(str(tar), "w:gz") as tf:
        for child in sorted(zeta_src.iterdir()):
            tf.add(str(child), arcname=child.name)
    before = _bytes(root)
    real = os.replace
    calls = {"n": 0}

    def interrupted(src, dst):
        # Four move out (1-4); lock, alpha, zeta move in (5-7).
        calls["n"] += 1
        if calls["n"] == nth:
            raise KeyboardInterrupt
        return real(src, dst)

    monkeypatch.setattr(snapshot.os, "replace", interrupted)
    with pytest.raises(KeyboardInterrupt):
        snapshot.restore(tar, root, "snap-zeta")
    assert _bytes(root) == before
    assert _restore_dirs(root) == []


def test_a_rollback_cut_short_keeps_the_parked_store(tmp_path, monkeypatch):
    # A second interrupt inside the rollback: the originals not yet moved
    # back stay parked — found by `boost doctor` — never deleted.
    root, tar = _edited_store(tmp_path)
    before = _bytes(root)
    real = os.replace
    calls = {"n": 0}

    def interrupted(src, dst):
        calls["n"] += 1
        if calls["n"] in (4, 6):   # first move in; then the first move back
            raise KeyboardInterrupt
        return real(src, dst)

    monkeypatch.setattr(snapshot.os, "replace", interrupted)
    with pytest.raises(KeyboardInterrupt):
        snapshot.restore(tar, root, "snap-ki2")
    left = _restore_dirs(root)
    assert len(left) == 1 and left[0].startswith(snapshot.PARKED_PREFIX)
    parked = root.parent / left[0]
    # Moves back run in name order: the lock (call 5) made it, alpha (call
    # 6) was cut short, and beta never started — both still parked, intact.
    assert _bytes(root) == {".skill-lock.json": before[".skill-lock.json"]}
    assert _bytes(parked) == {k: v for k, v in before.items()
                              if k != ".skill-lock.json"}


def test_a_failed_swap_removes_the_empty_parked_dir(tmp_path, monkeypatch):
    root, tar = _edited_store(tmp_path)
    real = os.replace
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] == 5:
            raise OSError("disk full")
        return real(src, dst)

    monkeypatch.setattr(snapshot.os, "replace", flaky)
    with pytest.raises(BoostError):
        snapshot.restore(tar, root, "snap-full")
    assert _restore_dirs(root) == []


def _tar_with(tmp_path, name, lock=None, skill=True, held=False):
    src = tmp_path / ("src-" + name)
    src.mkdir()
    if lock is not None:
        (src / ".skill-lock.json").write_text(lock, encoding="utf-8")
    if skill:
        (src / "foo").mkdir()
        (src / "foo" / "SKILL.md").write_text("# foo\n", encoding="utf-8")
    if held:
        (src / snapshot.HELD_ARC / "gamma").mkdir(parents=True)
        (src / snapshot.HELD_ARC / "gamma" / "SKILL.md").write_text(
            "# gamma\n", encoding="utf-8")
    tar = tmp_path / (name + ".tar.gz")
    with tarfile.open(str(tar), "w:gz") as tf:
        for child in sorted(src.iterdir()):
            tf.add(str(child), arcname=child.name)
    return tar


@pytest.mark.parametrize("lock, why", [
    ("{not json", "has a corrupt lock file"),
    ('{"version": 3, "rules": []}', "has a corrupt lock file"),
    ("[]", "has a corrupt lock file"),
    ('{"version": 99}',
     "has a lock file in schema 99, which this boost does not read"),
    (None, "holds skills but no lock file to say which are installed"),
])
def test_a_bad_archived_lock_is_refused_before_the_swap(tmp_path, lock, why):
    root = _store(tmp_path)
    before = _bytes(root)
    tar = _tar_with(tmp_path, "snapcore-badlock", lock)
    with pytest.raises(BoostError) as ei:
        snapshot.restore(tar, root, "snap-badlock")
    assert ei.value.message == "snapshot snap-badlock cannot be restored: it " + why
    assert ei.value.hint == snapshot.UNTOUCHED_HINT
    assert _bytes(root) == before
    assert _restore_dirs(root) == []


@pytest.mark.parametrize("held", [False, True])
def test_an_archive_of_an_empty_store_needs_no_lock(tmp_path, held):
    root = _store(tmp_path)
    tar = _tar_with(tmp_path, "snapcore-empty", skill=False, held=held)
    assert snapshot.restore(tar, root, "snap-empty",
                            tmp_path / "snapcore-held").held == (
        ["gamma"] if held else [])
    assert _tree(root) == []


def test_an_older_schema_lock_restores(tmp_path):
    root = _store(tmp_path)
    tar = _tar_with(tmp_path, "snapcore-v2", '{"version": 2, "skills": {}}')
    snapshot.restore(tar, root, "snap-v2")
    assert _tree(root) == [".skill-lock.json", "foo", "foo/SKILL.md"]


def test_rehome_rewrites_the_staged_lock_and_restamps_it(tmp_path,
                                                       monkeypatch):
    # The restored lock is stamped `updated` now, whatever `rehome` says: the
    # archive's own stamp put the restored state into lock history under an
    # id that collided with, and sorted above, entries written after it.
    monkeypatch.setattr(util, "now_iso", lambda: "2026-10-22T05:00:00Z")
    root = _store(tmp_path)
    tar = _tar_with(tmp_path, "snapcore-rh",
                    '{"version": 3, "rules": {}, '
                    '"updated": "2026-01-01T00:00:00Z"}')
    seen = []

    def unchanged(lock):
        seen.append(dict(lock))
        return False
    snapshot.restore(tar, root, "snap-rh", rehome=unchanged)
    assert seen == [{"version": 3, "rules": {},
                     "updated": "2026-01-01T00:00:00Z"}]
    assert (root / ".skill-lock.json").read_text(encoding="utf-8") == (
        '{\n  "version": 3,\n  "rules": {},\n'
        '  "updated": "2026-10-22T05:00:00Z"\n}\n')

    def changed(lock):
        lock["rules"]["r"] = {"x": 1}
        return True
    snapshot.restore(tar, root, "snap-rh", rehome=changed)
    assert json.loads((root / ".skill-lock.json").read_text(
        encoding="utf-8")) == {"version": 3, "rules": {"r": {"x": 1}},
                               "updated": "2026-10-22T05:00:00Z"}


def test_before_swap_runs_once_the_archive_is_vetted(tmp_path):
    # It is where `snapshot restore` keeps the live lock in history: run
    # while the store still holds it, and never for an archive refused.
    root = _store(tmp_path)
    tar = _tar_with(tmp_path, "snapcore-bs", '{"version": 3}')
    seen = []
    snapshot.restore(tar, root, "snap-bs", before_swap=lambda: seen.append(
        (root / ".skill-lock.json").read_text(encoding="utf-8")))
    assert seen == ["{}\n"]
    bad = _tar_with(tmp_path, "snapcore-bsx", "not json")
    with pytest.raises(BoostError):
        snapshot.restore(bad, root, "snap-bsx",
                         before_swap=lambda: seen.append("ran"))
    assert seen == ["{}\n"]


def test_a_rehome_refusal_leaves_the_store_untouched(tmp_path):
    root = _store(tmp_path)
    before = _bytes(root)
    tar = _tar_with(tmp_path, "snapcore-rhx", '{"version": 3}')

    def refuse(lock):
        raise BoostError("no", hint=snapshot.UNTOUCHED_HINT)
    with pytest.raises(BoostError):
        snapshot.restore(tar, root, "snap-rhx", rehome=refuse)
    assert _bytes(root) == before
    assert _restore_dirs(root) == []
    # No lock in the archive: nothing to rehome, and it is not asked.
    empty = _tar_with(tmp_path, "snapcore-rhy", skill=False)
    snapshot.restore(empty, root, "snap-rhy", rehome=refuse)
    assert _tree(root) == []


@pytest.mark.parametrize("home", [None, 7, ""])
def test_the_rehomer_reads_the_sidecar_home(sandbox, tmp_path, home):
    from boost_cli.core import paths
    tar = tmp_path / "snap-x.tar.gz"
    (tmp_path / "snap-x.json").write_text(
        "{}" if home is None else '{"home": %s}' % json.dumps(home),
        encoding="utf-8")
    old = tmp_path / "old-home"
    rows = [{"agent": "claude-code", "path": str(old / "notes" / "R.md")}]
    lock = {"rules": {"a": {"materializations": list(rows)},
                      "b": {"materializations": list(rows)}}}
    # No usable home recorded and no dotdir in the paths: both unplaced.
    with pytest.raises(BoostError) as ei:
        store.snapshot_rehomer("snap-x", tar)(lock)
    assert ei.value.message == (
        "snapshot snap-x cannot be restored: rule a, rule b record files "
        "outside this home that boost cannot place in it")
    assert ei.value.hint == snapshot.UNTOUCHED_HINT
    # Recorded: moved, and reported changed.
    (tmp_path / "snap-x.json").write_text(json.dumps({"home": str(old)}),
                                          encoding="utf-8")
    assert store.snapshot_rehomer("snap-x", tar)(lock) is True
    assert lock["rules"]["a"]["materializations"][0]["path"] == os.path.join(
        str(paths.home()), "notes", "R.md")
    assert store.snapshot_rehomer("snap-x", tar)(lock) is False


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


def _linked_skill(name, only=None):
    from boost_cli.core import paths
    d = paths.store_dir() / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("# %s\n" % name, encoding="utf-8")
    res = store.link_agents(name, only)
    row = {"version": "1.0.0", "commit": "c1", "agents": res.linked}
    if only:
        row["only_agents"] = list(only)
    lockfile.set_skill(name, row)
    return row


def test_restore_recorded_holds_sets_and_clears(sandbox):
    _linked_skill("snapcore-h")
    assert store.restore_recorded_holds("snapcore-missing", {}) == []
    assert store.restore_recorded_holds(
        "snapcore-h", {"version": "1.0.0"}) == []
    assert store.restore_recorded_holds(
        "snapcore-h", {"pinned": True, "commit_pin": "c0"}) == [
            "pinned", "commit_pin"]
    row = lockfile.get_skill("snapcore-h")
    assert row["pinned"] is True and row["commit_pin"] == "c0"
    assert store.restore_recorded_holds("snapcore-h", {}) == [
        "pinned", "commit_pin"]
    row = lockfile.get_skill("snapcore-h")
    assert "pinned" not in row and "commit_pin" not in row


def test_restore_recorded_holds_relinks_a_changed_scope(sandbox):
    from boost_cli.core import agents
    every = sorted(agents.linking_agents())
    _linked_skill("snapcore-s")
    assert sorted(lockfile.get_skill("snapcore-s")["agents"]) == every
    assert store.restore_recorded_holds(
        "snapcore-s", {"only_agents": ["cursor"]}) == ["only_agents"]
    row = lockfile.get_skill("snapcore-s")
    assert row["only_agents"] == ["cursor"] and row["agents"] == ["cursor"]
    assert store.linked_agents("snapcore-s") == ["cursor"]
    assert store.restore_recorded_holds("snapcore-s", {}) == ["only_agents"]
    row = lockfile.get_skill("snapcore-s")
    assert "only_agents" not in row and sorted(row["agents"]) == every
    assert sorted(store.linked_agents("snapcore-s")) == every


def test_restore_recorded_holds_only_records_a_held_skill_s_scope(sandbox):
    _linked_skill("snapcore-q")
    store.quarantine_skill("snapcore-q", lockfile.get_skill("snapcore-q"))
    assert store.restore_recorded_holds(
        "snapcore-q", {"only_agents": ["cursor"]}) == ["only_agents"]
    row = lockfile.get_skill("snapcore-q")
    assert row["only_agents"] == ["cursor"] and row["agents"] == []
    assert store.linked_agents("snapcore-q") == []


def test_reapply_recorded_aside(sandbox):
    _linked_skill("snapcore-r")
    assert store.reapply_recorded_aside("snapcore-r", {}) is None
    assert store.reapply_recorded_aside("snapcore-gone",
                                        {"quarantined": True}) is None
    assert store.reapply_recorded_aside("snapcore-gone",
                                        {"sidelined_by": "focus"}) is None
    assert store.reapply_recorded_aside(
        "snapcore-r", {"sidelined_by": "focus"}) == (
            "sidelined by `boost focus`")
    row = lockfile.get_skill("snapcore-r")
    assert row["sidelined_by"] == "focus" and row["agents"] == []
    assert store.linked_agents("snapcore-r") == []
    assert store.reapply_recorded_aside(
        "snapcore-r", {"quarantined": True, "sidelined_by": "focus"}) == (
            "quarantined")
    row = lockfile.get_skill("snapcore-r")
    assert row["quarantined"] is True and "sidelined_by" not in row
    assert store.is_held(row)


def test_restore_recorded_holds_only_records_a_sidelined_skill_s_scope(sandbox):
    _linked_skill("snapcore-f")
    store.sideline("snapcore-f", "focus")
    assert store.restore_recorded_holds(
        "snapcore-f", {"only_agents": ["cursor"]}) == ["only_agents"]
    row = lockfile.get_skill("snapcore-f")
    assert row["only_agents"] == ["cursor"] and row["agents"] == []
    assert store.linked_agents("snapcore-f") == []


# ── carrying what a snapshot does not cover across the swap ─────────────

def _carry_store(tmp_path):
    """A store with a recorded skill, the lock's .corrupt backup and a dir
    the lock never recorded; and an archive of the recorded part only."""
    root = _store(tmp_path)
    tar = tmp_path / "snapcore-carry.tar.gz"
    snapshot.archive(root, tar)
    (root / ".skill-lock.json.corrupt").write_text("CORRUPT\n", encoding="utf-8")
    (root / "mine").mkdir()
    (root / "mine" / "SKILL.md").write_text("# mine\n", encoding="utf-8")
    (root / "alpha" / "SKILL.md").write_text("changed\n", encoding="utf-8")
    return root, tar


def test_carried_children_survive_the_swap(tmp_path):
    root, tar = _carry_store(tmp_path)
    backup = tmp_path / "snapcore-kept"
    res = snapshot.restore(tar, root, "snap-carry",
                           carry=[".skill-lock.json.corrupt", "mine"],
                           backup_dir=backup)
    assert res.carried == [".skill-lock.json.corrupt", "mine"]
    assert res.backed_up == [] and res.held == []
    assert _tree(root) == [".skill-lock.json", ".skill-lock.json.corrupt",
                           "alpha", "alpha/SKILL.md", "mine", "mine/SKILL.md"]
    assert (root / ".skill-lock.json.corrupt").read_text(
        encoding="utf-8") == "CORRUPT\n"
    assert (root / "alpha" / "SKILL.md").read_text(encoding="utf-8") == "# alpha\n"
    assert not backup.exists()
    assert _restore_dirs(root) == []


def test_a_carried_child_the_archive_also_holds_is_backed_up(tmp_path):
    root, tar = _carry_store(tmp_path)
    backup = tmp_path / "snapcore-kept"
    (backup / "alpha").mkdir(parents=True)        # taken: the next free name
    res = snapshot.restore(tar, root, "snap-clash", carry=["alpha", "mine"],
                           backup_dir=backup)
    assert res.carried == ["mine"]
    assert res.backed_up == [backup / "alpha.2"]
    assert (backup / "alpha.2" / "SKILL.md").read_text(
        encoding="utf-8") == "changed\n"
    assert (root / "alpha" / "SKILL.md").read_text(encoding="utf-8") == "# alpha\n"
    assert _restore_dirs(root) == []


def test_keep_live_wins_a_clash(tmp_path):
    root, tar = _carry_store(tmp_path)
    res = snapshot.restore(tar, root, "snap-live", carry=["alpha"],
                           keep_live=["alpha"],
                           backup_dir=tmp_path / "snapcore-kept")
    assert res.carried == ["alpha"] and res.backed_up == []
    assert (root / "alpha" / "SKILL.md").read_text(encoding="utf-8") == "changed\n"
    assert not (root / "mine").exists()
    assert not (tmp_path / "snapcore-kept").exists()


def test_set_aside_always_goes_to_the_backup(tmp_path):
    root, tar = _carry_store(tmp_path)
    backup = tmp_path / "snapcore-kept"
    res = snapshot.restore(tar, root, "snap-aside",
                           carry=[".skill-lock.json.corrupt"],
                           keep_live=["mine"], set_aside=["mine"],
                           backup_dir=backup)
    assert res.carried == [".skill-lock.json.corrupt"]
    assert res.backed_up == [backup / "mine"]
    assert (backup / "mine" / "SKILL.md").read_text(encoding="utf-8") == "# mine\n"
    assert not (root / "mine").exists()


def test_without_a_backup_dir_a_clash_stays_parked(tmp_path):
    root, tar = _carry_store(tmp_path)
    res = snapshot.restore(tar, root, "snap-park", carry=["alpha", "mine"])
    assert res.carried == ["mine"] and res.backed_up == []
    [parked] = _restore_dirs(root)
    assert parked.startswith(snapshot.PARKED_PREFIX)
    assert (root.parent / parked / "alpha" / "SKILL.md").read_text(
        encoding="utf-8") == "changed\n"


@pytest.mark.skipif(sys.platform == "win32", reason="needs symlinks")
def test_a_dangling_symlink_is_not_carried(tmp_path):
    root, tar = _carry_store(tmp_path)
    (root / "gone").symlink_to(tmp_path / "snapcore-nowhere")
    res = snapshot.restore(tar, root, "snap-dangle", carry=["gone", "mine"],
                           backup_dir=tmp_path / "snapcore-kept")
    assert res.carried == ["mine"]
    assert not os.path.lexists(root / "gone")
    assert _restore_dirs(root) == []


def test_a_failed_carry_keeps_what_is_parked(tmp_path, monkeypatch):
    root, tar = _carry_store(tmp_path)
    real = os.replace

    def fail_mine(src, dst):
        if os.path.basename(str(src)) == "mine" and str(dst).startswith(
                str(root)):
            raise OSError(5, "no")
        return real(src, dst)
    monkeypatch.setattr(snapshot.os, "replace", fail_mine)
    with pytest.raises(BoostError) as ei:
        snapshot.restore(tar, root, "snap-cfail", carry=["mine"])
    assert ei.value.message.startswith(
        "restored snap-cfail, but could not carry everything")
    [parked] = _restore_dirs(root)
    assert ei.value.hint == "what was not carried is still in %s" % (
        root.parent.resolve() / parked)
    assert (root.parent / parked / "mine" / "SKILL.md").is_file()


@pytest.mark.parametrize("lock, why", [
    ("{not json", "has a corrupt lock file"),
    ('{"version": 99}',
     "has a lock file in schema 99, which this boost does not read"),
    (None, "holds skills but no lock file to say which are installed"),
])
def test_save_refuses_what_restore_would(sandbox, tmp_path, lock, why):
    root = _store(tmp_path)
    if lock is None:
        (root / ".skill-lock.json").unlink()
    else:
        (root / ".skill-lock.json").write_text(lock, encoding="utf-8")
    tar = tmp_path / "snapcore-refuse.tar.gz"
    with pytest.raises(BoostError) as ei:
        snapshot.archive(root, tar)
    assert ei.value.message == "cannot snapshot the store: it " + why
    assert ei.value.hint.endswith(
        ", then save again — a snapshot of it could not be restored")
    assert not tar.exists()


def test_save_of_an_empty_store_without_a_lock_is_allowed(tmp_path):
    root = tmp_path / "snapcore-bare"
    root.mkdir()
    tar = tmp_path / "snapcore-bare.tar.gz"
    snapshot.archive(root, tar)
    assert snapshot.restore(tar, root, "snap-bare").carried == []
