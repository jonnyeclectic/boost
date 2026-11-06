# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost clean --deep` counts and ages snapshots, not files.

`snapshot save` writes ``<id>.tar.gz`` plus an ``<id>.json`` sidecar. clean
iterated the directory, so one old snapshot was prompted as "remove 2
snapshot(s)", and each file was aged by its own mtime while `snapshot list`
shows the sidecar's ``created`` — so a tarball and its sidecar could fall on
opposite sides of the cutoff, one removed and one orphaned.
"""
from __future__ import annotations

import json
import os
import time

from boost_cli.core import output, paths, snapshot

DAY = 86400


def _snap(d, sid, created, mtime=None, tar=b"t" * 10, meta=True):
    d.mkdir(parents=True, exist_ok=True)
    (d / (sid + ".tar.gz")).write_bytes(tar)
    if meta:
        (d / (sid + ".json")).write_text(
            json.dumps({"id": sid, "created": created}), encoding="utf-8")
    if mtime is not None:
        for f in d.glob(sid + ".*"):
            os.utime(f, (mtime, mtime))


def _iso(when):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(when))


class TestUnits:
    def test_a_tarball_and_its_sidecar_are_one_unit(self, tmp_path):
        old = time.time() - 100 * DAY
        _snap(tmp_path, "snap-a", _iso(old))
        (u,) = snapshot.units(tmp_path)
        assert u.id == "snap-a"
        assert [f.name for f in u.files] == ["snap-a.tar.gz", "snap-a.json"]
        assert u.sizes[0] == 10
        assert u.sizes[1] == (tmp_path / "snap-a.json").stat().st_size
        assert abs(u.created - old) < 1

    def test_age_is_the_sidecars_created_not_the_files_mtime(self, tmp_path):
        now = time.time()
        # Files touched long ago, but the snapshot was saved yesterday.
        _snap(tmp_path, "snap-new", _iso(now - DAY), mtime=now - 200 * DAY)
        # Files fresh, but the snapshot is old.
        _snap(tmp_path, "snap-old", _iso(now - 100 * DAY))
        cutoff = now - 90 * DAY
        assert [u.id for u in snapshot.older_than(tmp_path, cutoff)] == [
            "snap-old"]

    def test_without_a_readable_created_the_tarball_mtime_decides(
            self, tmp_path):
        now = time.time()
        _snap(tmp_path, "snap-x", "not a time", mtime=now - 100 * DAY)
        _snap(tmp_path, "snap-y", "", meta=False, mtime=now - 100 * DAY)
        _snap(tmp_path, "snap-z", "", meta=False)
        (tmp_path / "snap-w.tar.gz").write_bytes(b"x")
        (tmp_path / "snap-w.json").write_text("{broken", encoding="utf-8")
        got = snapshot.older_than(tmp_path, now - 90 * DAY)
        assert [u.id for u in got] == ["snap-x", "snap-y"]
        assert [len(u.files) for u in got] == [2, 1]

    def test_anything_else_is_a_unit_of_its_own(self, tmp_path):
        (tmp_path / "ancient").mkdir()
        (tmp_path / "ancient" / "f").write_text("abc", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
        got = {u.id: (u.files, u.sizes) for u in snapshot.units(tmp_path)}
        assert got == {"ancient": ((tmp_path / "ancient",), (3,)),
                       "notes.txt": ((tmp_path / "notes.txt",), (5,))}


class TestCleanDeep:
    @staticmethod
    def _old(n=1):
        when = time.time() - 100 * DAY
        for i in range(n):
            _snap(paths.snapshots_dir(), "snap-%d" % i, _iso(when))

    def test_the_prompt_counts_snapshots(self, boost, sandbox, monkeypatch):
        self._old()
        asked = []

        def confirm(prompt, default=False, quiet=False):
            asked.append(prompt)
            return False
        monkeypatch.setattr(output, "confirm", confirm)
        boost("clean", "--deep", expect=1)
        assert asked == ["remove 1 snapshot older than 90 days?"]
        assert (paths.snapshots_dir() / "snap-0.json").is_file()
        assert (paths.snapshots_dir() / "snap-0.tar.gz").is_file()

    def test_the_prompt_pluralizes(self, boost, sandbox, monkeypatch):
        self._old(2)
        asked = []
        monkeypatch.setattr(output, "confirm",
                            lambda p, default=False, quiet=False:
                            asked.append(p) or False)
        boost("clean", "--deep", expect=1)
        assert asked == ["remove 2 snapshots older than 90 days?"]

    def test_dry_run_names_both_files_and_one_snapshot(self, boost, sandbox):
        self._old()
        res = boost("clean", "--deep", "--dry-run")
        assert res.out.count("(old snapshot)") == 2
        size = sum(f.stat().st_size for f in paths.snapshots_dir().iterdir())
        assert ("2 item(s) (1 old snapshot) · %dB would be freed" % size
                ) in res.out

    def test_dry_run_json_counts_snapshots(self, boost, sandbox):
        self._old(2)
        d = json.loads(boost("clean", "--deep", "--dry-run", "--json").out)
        assert d["count"] == 4 and d["snapshots"] == 2

    def test_both_files_go_together(self, boost, sandbox):
        self._old()
        _snap(paths.snapshots_dir(), "snap-keep", _iso(time.time()),
              mtime=time.time() - 200 * DAY)
        res = boost("clean", "--deep", "--yes")
        assert sorted(f.name for f in paths.snapshots_dir().iterdir()) == [
            "snap-keep.json", "snap-keep.tar.gz"]
        assert "cleaned 2 item(s)" in res.out

    def test_no_snapshot_note_without_snapshots(self, boost, sandbox):
        res = boost("clean", "--deep", "--dry-run")
        assert "old snapshot" not in res.out
        d = json.loads(boost("clean", "--deep", "--dry-run", "--json").out)
        assert d["snapshots"] == 0
