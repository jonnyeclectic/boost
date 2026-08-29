# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: scripts/normalize_sdist.py — the sdist reproducibility fix.

setuptools writes each tar member's real mtime, plus the builder's uid/gid/user
name, into an sdist (pypa/setuptools#2133, open since 2020 — no native
SOURCE_DATE_EPOCH support exists to reach for instead; see the script's own
docstring for the investigation). Two builds of the same commit, seconds apart,
therefore differ in every directory entry and every build-time-generated file.
This script rewrites the tarball after the fact so that stops being true.

It lives in scripts/, which the mutation gate does not reach (that targets
boost_cli/core) and which coverage does not count toward the 90% floor (`source
= ["boost_cli"]` in pyproject.toml) — so these tests are the only net under it.
"""
from __future__ import annotations

import importlib.util
import io
import struct
import tarfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "normalize_sdist.py"

EPOCH = 1700000000  # an arbitrary, fixed SOURCE_DATE_EPOCH for every test


def _load():
    spec = importlib.util.spec_from_file_location("normalize_sdist", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


mod = _load()


def _make_sdist(path: Path, *, mtime: float, uid: int, gid: int,
                uname: str, gname: str) -> None:
    """A tiny tar.gz shaped like a real sdist: a directory and two files.

    Mirrors what the reported baseline diff actually contained — directory
    entries and generated metadata files carrying the builder's identity and
    the wall-clock time of the build.
    """
    with tarfile.open(path, "w:gz") as tar:
        for name, is_dir, data in (
            ("pkg-1.0/", True, None),
            ("pkg-1.0/PKG-INFO", False, b"Metadata-Version: 2.1\n"),
            ("pkg-1.0/pkg/__init__.py", False, b"__version__ = '1.0'\n"),
        ):
            info = tarfile.TarInfo(name=name)
            info.mtime = mtime
            info.uid = uid
            info.gid = gid
            info.uname = uname
            info.gname = gname
            if is_dir:
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                tar.addfile(info)
            else:
                info.type = tarfile.REGTYPE
                info.mode = 0o644
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))


def _gzip_header_mtime(path: Path) -> int:
    """The 4-byte little-endian MTIME field of a gzip file's header (RFC 1952)."""
    with open(path, "rb") as f:
        header = f.read(10)
    return struct.unpack("<I", header[4:8])[0]


class TestNormalize:
    def test_clamps_mtime_to_the_epoch(self, tmp_path):
        sdist = tmp_path / "pkg-1.0.tar.gz"
        _make_sdist(sdist, mtime=time.time(), uid=501, gid=20,
                   uname="cassandra", gname="staff")
        mod.normalize(sdist, EPOCH)
        with tarfile.open(sdist, "r:gz") as tar:
            for member in tar.getmembers():
                assert member.mtime <= EPOCH

    def test_zeroes_ownership(self, tmp_path):
        sdist = tmp_path / "pkg-1.0.tar.gz"
        _make_sdist(sdist, mtime=EPOCH - 100, uid=501, gid=20,
                   uname="cassandra", gname="staff")
        mod.normalize(sdist, EPOCH)
        with tarfile.open(sdist, "r:gz") as tar:
            for member in tar.getmembers():
                assert member.uid == 0
                assert member.gid == 0
                assert member.uname == ""
                assert member.gname == ""

    def test_normalizes_the_gzip_header_timestamp(self, tmp_path):
        sdist = tmp_path / "pkg-1.0.tar.gz"
        _make_sdist(sdist, mtime=EPOCH - 100, uid=0, gid=0, uname="", gname="")
        mod.normalize(sdist, EPOCH)
        assert _gzip_header_mtime(sdist) == EPOCH

    def test_omits_the_gzip_filename_field(self, tmp_path):
        # The FNAME flag bit (0x08) must be clear — an embedded filename is
        # one more thing that could vary between two otherwise-identical builds.
        sdist = tmp_path / "pkg-1.0.tar.gz"
        _make_sdist(sdist, mtime=EPOCH, uid=0, gid=0, uname="", gname="")
        mod.normalize(sdist, EPOCH)
        with open(sdist, "rb") as f:
            header = f.read(10)
        flags = header[3]
        assert flags & 0x08 == 0

    def test_preserves_member_order_and_content(self, tmp_path):
        sdist = tmp_path / "pkg-1.0.tar.gz"
        _make_sdist(sdist, mtime=EPOCH, uid=501, gid=20,
                   uname="cassandra", gname="staff")
        with tarfile.open(sdist, "r:gz") as tar:
            before_names = [m.name for m in tar.getmembers()]
            before_content = tar.extractfile("pkg-1.0/PKG-INFO").read()
        mod.normalize(sdist, EPOCH)
        with tarfile.open(sdist, "r:gz") as tar:
            after_names = [m.name for m in tar.getmembers()]
            after_content = tar.extractfile("pkg-1.0/PKG-INFO").read()
        assert after_names == before_names
        assert after_content == before_content

    def test_remains_a_valid_tarball(self, tmp_path):
        # A stand-in for "twine check still passes": the archive extracts
        # cleanly and every member is reachable, which is what a downstream
        # consumer (pip, twine) actually needs from the container format.
        sdist = tmp_path / "pkg-1.0.tar.gz"
        _make_sdist(sdist, mtime=EPOCH, uid=501, gid=20,
                   uname="cassandra", gname="staff")
        mod.normalize(sdist, EPOCH)
        extract_to = tmp_path / "out"
        with tarfile.open(sdist, "r:gz") as tar:
            tar.extractall(extract_to, filter="data")
        assert (extract_to / "pkg-1.0" / "PKG-INFO").is_file()
        assert (extract_to / "pkg-1.0" / "pkg" / "__init__.py").is_file()

    def test_two_builds_with_different_builder_identity_converge(self, tmp_path):
        # The actual promise: two "builds" that differ only in the fields a
        # real builder varies (wall-clock mtime, uid/gid, uname/gname) become
        # byte-identical once normalized to the same epoch.
        a = tmp_path / "a.tar.gz"
        b = tmp_path / "b.tar.gz"
        _make_sdist(a, mtime=time.time(), uid=501, gid=20,
                   uname="alice", gname="staff")
        time.sleep(0.01)
        _make_sdist(b, mtime=time.time(), uid=1000, gid=1000,
                   uname="bob", gname="bob")
        mod.normalize(a, EPOCH)
        mod.normalize(b, EPOCH)
        assert a.read_bytes() == b.read_bytes()

    def test_idempotent(self, tmp_path):
        sdist = tmp_path / "pkg-1.0.tar.gz"
        _make_sdist(sdist, mtime=time.time(), uid=501, gid=20,
                   uname="cassandra", gname="staff")
        mod.normalize(sdist, EPOCH)
        once = sdist.read_bytes()
        mod.normalize(sdist, EPOCH)
        assert sdist.read_bytes() == once

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            mod.normalize(tmp_path / "does-not-exist.tar.gz", EPOCH)


class TestEpochResolution:
    def test_explicit_epoch_wins(self):
        assert mod.resolve_epoch(explicit=123, env={"SOURCE_DATE_EPOCH": "999"}) == 123

    def test_falls_back_to_environment(self):
        assert mod.resolve_epoch(explicit=None, env={"SOURCE_DATE_EPOCH": "456"}) == 456

    def test_neither_is_an_error(self):
        with pytest.raises(SystemExit):
            mod.resolve_epoch(explicit=None, env={})


class TestMain:
    def test_missing_path_argument_fails_loudly(self, tmp_path, capsys):
        # A shell glob that matched nothing arrives as a literal, non-existent
        # path. Silently accepting it would attest an unnormalized sdist.
        missing = tmp_path / "dist" / "*.tar.gz"
        rc = mod.main([str(missing)], env={"SOURCE_DATE_EPOCH": str(EPOCH)})
        assert rc != 0
        assert "does not exist" in capsys.readouterr().err

    def test_normalizes_every_path_given(self, tmp_path):
        a = tmp_path / "a.tar.gz"
        b = tmp_path / "b.tar.gz"
        _make_sdist(a, mtime=time.time(), uid=501, gid=20, uname="x", gname="y")
        _make_sdist(b, mtime=time.time() + 5, uid=502, gid=21, uname="p", gname="q")
        rc = mod.main([str(a), str(b)], env={"SOURCE_DATE_EPOCH": str(EPOCH)})
        assert rc == 0
        assert _gzip_header_mtime(a) == EPOCH
        assert _gzip_header_mtime(b) == EPOCH

    def test_env_var_read_from_os_environ_by_default(self, tmp_path, monkeypatch):
        sdist = tmp_path / "pkg-1.0.tar.gz"
        _make_sdist(sdist, mtime=time.time(), uid=501, gid=20,
                   uname="x", gname="y")
        monkeypatch.setenv("SOURCE_DATE_EPOCH", str(EPOCH))
        rc = mod.main([str(sdist)])
        assert rc == 0
        assert _gzip_header_mtime(sdist) == EPOCH
