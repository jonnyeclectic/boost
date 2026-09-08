# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/archive.py — export archive-format helpers."""
from __future__ import annotations

import stat
import tarfile
import zipfile

from boost_cli.core import archive


class TestResolveExportFormat:
    def test_no_out_path_zip_flag_true(self):
        assert archive.resolve_export_format(None, True) == (True, None)

    def test_no_out_path_zip_flag_false(self):
        assert archive.resolve_export_format(None, False) == (False, None)

    def test_zip_suffix_without_flag_infers_zip(self):
        # This is the reported bug: `-o byname.zip` with no `--zip` used to
        # write a gzip tarball named `.zip`.
        assert archive.resolve_export_format("byname.zip", False) == (True, None)

    def test_tar_gz_suffix_without_flag_infers_tar(self):
        assert archive.resolve_export_format("out.tar.gz", False) == (False, None)

    def test_tgz_suffix_without_flag_infers_tar(self):
        assert archive.resolve_export_format("out.tgz", False) == (False, None)

    def test_unrecognized_suffix_without_flag_keeps_default(self):
        assert archive.resolve_export_format("out.bin", False) == (False, None)

    def test_matching_zip_suffix_and_flag_no_warning(self):
        assert archive.resolve_export_format("byflag.zip", True) == (True, None)

    def test_contradicting_tar_suffix_with_zip_flag_warns_but_honors_flag(self):
        use_zip, warning = archive.resolve_export_format("byflag.tar.gz", True)
        assert use_zip is True
        assert warning is not None
        assert "byflag.tar.gz" in warning

    def test_unrecognized_suffix_with_zip_flag_no_warning(self):
        assert archive.resolve_export_format("out.bin", True) == (True, None)

    def test_case_insensitive_suffix_matching(self):
        assert archive.resolve_export_format("OUT.ZIP", False) == (True, None)

    def test_directory_component_ignored_suffix_from_basename_only(self):
        assert archive.resolve_export_format("some.dir/out.zip", False) == (
            True, None)


class TestNormalizeTarMember:
    def test_zeroes_uid_gid_and_blanks_names(self):
        ti = tarfile.TarInfo("brainstorming/SKILL.md")
        ti.uid = 501
        ti.gid = 20
        ti.uname = "jonny"
        ti.gname = "staff"
        result = archive.normalize_tar_member(ti)
        assert result is ti
        assert ti.uid == 0
        assert ti.gid == 0
        assert ti.uname == ""
        assert ti.gname == ""

    def test_leaves_mode_and_name_untouched(self):
        ti = tarfile.TarInfo("Boostfile")
        ti.mode = 0o644
        archive.normalize_tar_member(ti)
        assert ti.mode == 0o644
        assert ti.name == "Boostfile"


class TestBoostfileZipinfo:
    def test_name_and_compression(self):
        zi = archive.boostfile_zipinfo((2026, 1, 2, 3, 4, 5))
        assert zi.filename == "Boostfile"
        assert zi.compress_type == zipfile.ZIP_DEFLATED
        assert zi.date_time == (2026, 1, 2, 3, 4, 5)

    def test_mode_is_0o644_not_the_zipfile_default_0o600(self):
        zi = archive.boostfile_zipinfo((2026, 1, 2, 3, 4, 5))
        mode = (zi.external_attr >> 16) & 0o777
        assert mode == 0o644
        assert stat.S_ISREG(zi.external_attr >> 16)
