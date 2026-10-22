# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""What a boost killed mid-write leaves in the store is named and cleaned.

Measured before this fix: a SIGKILL inside ``atomic_write_text``'s fsync left
``~/.agents/skills/.boost-lcfrfiee.tmp`` (a 0600 copy of the lock file), and
``boost doctor`` said healthy while ``boost clean`` said nothing to clean. A
staging dir an install never renamed into place was invisible the same way.
"""
from __future__ import annotations

import os
import sys
import time

import pytest

from boost_cli.core import paths, snapshot, store

NOW = 2_000_000_000.0
OLD = NOW - store.STALE_TEMP_AGE - 1


def _make(name: str, *, kind: str = "file", mtime: float = OLD):
    root = paths.store_dir()
    root.mkdir(parents=True, exist_ok=True)
    p = root / name
    if kind == "dir":
        p.mkdir()
        (p / "SKILL.md").write_text("x", encoding="utf-8")
    else:
        p.write_text("{}", encoding="utf-8")
    os.utime(p, (mtime, mtime))
    return p


class TestStaleTemps:
    def test_an_old_temp_file_and_staging_dir_are_found(self, sandbox):
        tmp = _make(".boost-lcfrfiee.tmp")
        stage = _make(".boost-abcd_123", kind="dir")
        # Sorted by path: "_" sorts before "l".
        assert store.stale_temps(NOW) == [(stage, "stale staging dir"),
                                         (tmp, "stale temp file")]

    def test_the_age_is_a_strict_bound(self, sandbox):
        _make(".boost-aaaaaaaa.tmp", mtime=NOW - store.STALE_TEMP_AGE)
        assert store.stale_temps(NOW) == []
        assert store.STALE_TEMP_AGE == 3600.0

    def test_one_second_past_it_is_stale(self, sandbox):
        p = _make(".boost-aaaaaaaa.tmp", mtime=NOW - store.STALE_TEMP_AGE - 1)
        assert store.stale_temps(NOW) == [(p, "stale temp file")]

    @pytest.mark.parametrize("name", [
        ".boost-abcdefg.tmp",       # 7 chars
        ".boost-abcdefghi.tmp",     # 9 chars
        ".boost-ABCDEFGH.tmp",      # not tempfile's alphabet
        ".boost-abcd-fgh.tmp",
        ".boost-abcdefgh.txt",
        "boost-abcdefgh.tmp",
        ".boost-abcdefgh.old",
        ".boost-reclone"])
    def test_only_boosts_own_exact_names(self, sandbox, name):
        _make(name)
        assert store.stale_temps(NOW) == []

    def test_a_dir_named_like_a_temp_file_is_not_one(self, sandbox):
        _make(".boost-abcdefgh.tmp", kind="dir")
        _make(".boost-abcdefgh")             # a file named like a staging dir
        assert store.stale_temps(NOW) == []

    @pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privilege")
    def test_a_symlink_is_never_one(self, sandbox, tmp_path):
        root = paths.store_dir()
        root.mkdir(parents=True, exist_ok=True)
        (root / ".boost-abcdefgh").symlink_to(tmp_path)
        os.utime(root / ".boost-abcdefgh", (OLD, OLD), follow_symlinks=False)
        assert store.stale_temps(NOW) == []

    def test_a_missing_store_has_none(self, sandbox):
        assert store.stale_temps() == []

    def test_by_default_it_reads_the_clock(self, sandbox):
        p = _make(".boost-aaaaaaaa.tmp", mtime=1_000_000_000.0)
        _make(".boost-bbbbbbbb.tmp", mtime=time.time())
        assert store.stale_temps() == [(p, "stale temp file")]


def _beside(name: str, mtime: float = OLD):
    """A dir ``name`` in the store's parent, where `snapshot restore` makes
    its staging, parked and held dirs."""
    paths.store_dir().mkdir(parents=True, exist_ok=True)
    p = paths.store_dir().resolve().parent / name
    p.mkdir()
    (p / "SKILL.md").write_text("x", encoding="utf-8")
    os.utime(p, (mtime, mtime))
    return p


class TestRestoreLeftovers:
    def test_each_restore_dir_is_named_by_what_it_holds(self, sandbox):
        stage = _beside(snapshot.STAGING_PREFIX + "abcd1234")
        old = _beside(snapshot.PARKED_PREFIX + "abcd1234")
        held = _beside(snapshot.HELD_PREFIX + "abcd1234")
        assert store.stale_temps(NOW) == sorted([
            (stage, "stale restore staging dir"),
            (old, store.PARKED_STORE),
            (held, "stale restore staging dir")])
        assert store.PARKED_STORE == (
            "previous store parked by an interrupted restore")

    @pytest.mark.parametrize("name", [
        snapshot.STAGING_PREFIX + "abcd123",       # 7 chars
        snapshot.PARKED_PREFIX + "abcd12345",      # 9 chars
        snapshot.HELD_PREFIX + "ABCD1234",
        ".boost-restored-abcd1234",
        "boost-restore-abcd1234"])
    def test_only_mkdtemps_own_names(self, sandbox, name):
        _beside(name)
        assert store.stale_temps(NOW) == []

    def test_young_files_and_links_are_not_one(self, sandbox, tmp_path):
        _beside(snapshot.PARKED_PREFIX + "abcd1234", mtime=NOW)
        parent = paths.store_dir().resolve().parent
        f = parent / (snapshot.STAGING_PREFIX + "abcd1234")
        f.write_text("x", encoding="utf-8")
        os.utime(f, (OLD, OLD))
        assert store.stale_temps(NOW) == []
        assert store.stale_temps(NOW + store.STALE_TEMP_AGE + 1) == [
            (parent / (snapshot.PARKED_PREFIX + "abcd1234"),
             store.PARKED_STORE)]


class TestCli:
    def test_doctor_names_them_and_clean_removes_them(self, boost, installed):
        tmp = _make(".boost-lcfrfiee.tmp", mtime=1_000_000_000.0)
        stage = _make(".boost-zz99yy88", kind="dir", mtime=1_000_000_000.0)
        young = _make(".boost-young123", kind="dir",
                      mtime=time.time())
        r = boost("doctor", expect=1)
        assert ("2 stale temp files or staging dirs a killed boost left in "
                "~/.agents/skills (.boost-lcfrfiee.tmp, .boost-zz99yy88) — "
                "`boost clean` removes them") in " ".join(r.out.split())
        r = boost("clean", "--dry-run")
        assert "would remove ~/.agents/skills/.boost-lcfrfiee.tmp (stale temp file)" in r.out
        assert "would remove ~/.agents/skills/.boost-zz99yy88 (stale staging dir)" in r.out
        assert "SKILL.md" not in r.out          # removed whole, not listed inside
        boost("clean")
        assert not tmp.exists() and not stage.exists()
        assert young.is_dir()
        assert "stale temp" not in boost("doctor").out

    def test_one_is_worded_singular(self, boost, installed):
        _make(".boost-lcfrfiee.tmp", mtime=1_000_000_000.0)
        r = boost("doctor", expect=1)
        assert ("1 stale temp file or staging dir a killed boost left in "
                "~/.agents/skills (.boost-lcfrfiee.tmp) — `boost clean` removes "
                "it") in " ".join(r.out.split())

    def test_doctor_names_a_parked_store_and_clean_leaves_it(
            self, boost, installed):
        stage = _beside(snapshot.STAGING_PREFIX + "zz99yy88", 1_000_000_000.0)
        old = _beside(snapshot.PARKED_PREFIX + "zz99yy88", 1_000_000_000.0)
        r = boost("doctor", expect=1)
        flat = " ".join(r.out.split())
        assert ("~/.agents/.boost-restore-old-zz99yy88 holds the previous "
                "store parked by an interrupted restore — compare it with "
                "~/.agents/skills, move back what is missing, then delete it"
                ) in flat
        assert ("1 stale temp file or staging dir a killed boost left in "
                "~/.agents/skills (.boost-restore-zz99yy88) — `boost clean` "
                "removes it") in flat
        r = boost("clean", "--dry-run")
        assert ("would remove ~/.agents/.boost-restore-zz99yy88 (stale "
                "restore staging dir)") in r.out
        assert "would remove ~/.agents/.boost-restore-old" not in r.out
        assert ("left ~/.agents/.boost-restore-old-zz99yy88 alone: it holds "
                "the previous store parked by an interrupted restore — move "
                "back what ~/.agents/skills is missing, then delete it"
                ) in " ".join(r.err.split())
        boost("clean")
        assert not stage.exists()
        assert (old / "SKILL.md").read_text(encoding="utf-8") == "x"
