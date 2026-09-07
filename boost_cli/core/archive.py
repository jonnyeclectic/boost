# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Archive-format helpers for `boost export`.

Kept out of commands/pkg.py (thin CLI glue) so the mutation gate, which only
targets boost_cli/core, covers the format-inference and member-normalization
logic `boost export` depends on.
"""
from __future__ import annotations

import stat
import tarfile
import zipfile
from pathlib import Path


def resolve_export_format(out_path: str | None, zip_flag: bool) -> tuple[bool, str | None]:
    """Decide zip vs. tar.gz for `boost export` from `--zip` and `-o`'s suffix.

    `--zip` alone used to decide the archive format even when `-o` named a
    contradicting extension: `-o x.zip` with no `--zip` wrote a gzip tarball
    named `.zip` (and file(1) called it exactly that), with no warning either
    way. When `--zip` is absent, a recognized extension on `out_path`
    (`.zip`, or `.tar.gz`/`.tgz`) now decides the format instead. When
    `--zip` is given, it still wins — an explicit flag is not silently
    overridden by a filename — but a recognized extension that contradicts it
    produces a warning naming what will actually be written. An unrecognized
    extension (or no `-o` at all) leaves `zip_flag` as the only signal.

    Returns ``(use_zip, warning)``; ``warning`` is ``None`` when nothing needs
    saying.
    """
    if not out_path:
        return zip_flag, None
    name = Path(out_path).name.lower()
    is_zip_suffix = name.endswith(".zip")
    is_tar_suffix = name.endswith((".tar.gz", ".tgz"))
    if zip_flag:
        if is_tar_suffix:
            return True, ("%s looks like a tar archive but --zip was passed — "
                          "writing a .zip anyway" % out_path)
        return True, None
    if is_zip_suffix:
        return True, None
    return False, None


def normalize_tar_member(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo:
    """`tarfile.add` filter: zero uid/gid, blank uname/gname on every member.

    `tarfile.add`'s default filter copies the real filesystem owner onto each
    member, so an export built as one user and extracted as root left a
    root-owned Boostfile (built from a bare `TarInfo`, uid/gid 0 and
    uname/gname "" by construction) sitting beside user-owned skill files —
    and leaked the builder's username into every archive along the way.
    Applying this to every member, the hand-built Boostfile included, makes
    `boost export`'s tar archives deterministic and free of local-account
    metadata.
    """
    tarinfo.uid = 0
    tarinfo.gid = 0
    tarinfo.uname = ""
    tarinfo.gname = ""
    return tarinfo


def boostfile_zipinfo(date_time: tuple[int, int, int, int, int, int]) -> zipfile.ZipInfo:
    """`ZipInfo` for a zip export's Boostfile member, mode 0o644 not 0o600.

    `ZipFile.writestr` given a bare member name (as `boost export` used to
    pass) builds its own `ZipInfo` internally, and leaves `external_attr` at
    the zipfile module's default of `0o600 << 16` — inconsistent with the
    0o644 skill files `ZipFile.write` adds alongside it from their real disk
    permissions in the same archive.
    """
    zi = zipfile.ZipInfo("Boostfile", date_time)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.external_attr = (0o644 | stat.S_IFREG) << 16
    return zi
