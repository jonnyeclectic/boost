#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Rewrite a built sdist so two builds of the same commit are byte-identical.

    SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) \\
        python3 scripts/normalize_sdist.py dist/*.tar.gz

``setuptools`` honours ``SOURCE_DATE_EPOCH`` when it stamps a wheel's zip
entries (``setuptools._vendor.wheel.wheelfile.get_zipinfo_datetime``), but it
has never done the equivalent for an sdist: ``distutils.archive_util.
make_tarball`` writes each tar member's *real* build-time mtime, and the
current user's uid/gid/uname/gname, with no environment variable to override
either. That gap is tracked upstream as pypa/setuptools#2133, open since 2020
with no fix landed as of setuptools 83 (the version this repository pins) —
the most recent maintainer activity on it, a workaround snippet, is from
January 2025. The one existing PyPI package that patches it,
``setuptools-reproducible``, does so by replacing the PEP 517 build backend
(``build-backend = "setuptools_reproducible"``) rather than adding a knob to
the one boost already uses, and its transitive closure could not be
hash-pinned by ``requirements/release-tools.txt`` the way the rest of the
toolchain is (a ``[build-system].requires`` entry is a bare PEP 508
requirement string with no hash syntax, so pip installs it into the isolated
build environment unpinned regardless).

So this is the smaller surface: a stdlib-only post-processing step, run on the
sdist ``python -m build`` already produced, before ``twine check`` and before
the artifact is attested. It touches exactly what the measured diff in
docs/verifying-releases.md named and nothing else:

* every member's mtime, clamped to ``SOURCE_DATE_EPOCH`` (never pushed later
  than it — only pulled back if the real build time was later, which for a
  build of a past commit it always is);
* every member's uid/gid, set to 0, and uname/gname, set to the empty string
  (not the builder's account, and not root's account name either — a bare 0
  with no name is what reproducible-builds.org's own archive guidance
  recommends, and what setuptools-reproducible converged on after discussion
  in the same upstream issue);
* the gzip container's own MTIME header field (RFC 1952 section 2.3.1), which
  carries a *second*, independent timestamp on top of the tar member times —
  clamping the members alone leaves this one still varying build to build.

Member order, mode bits, and file content are left exactly as built: the
measured baseline diff never implicated them, and rewriting more than the
measurement found would be a change nothing here can point back to.
"""
from __future__ import annotations

import gzip
import os
import sys
import tarfile
from pathlib import Path


def normalize(path: Path, epoch: int) -> None:
    """Rewrite the sdist at *path* in place, clamped to *epoch*.

    Writes to a sibling temp file and ``os.replace``s it over *path* only once
    the rewrite has fully succeeded, so a failure partway through never leaves
    a half-written archive where the real sdist used to be.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)

    tmp = path.with_name(path.name + ".normalizing")
    try:
        # filename="" so the gzip header carries no FNAME field — an embedded
        # original filename is one more thing that could differ between two
        # otherwise-identical invocations. mtime= is the header field
        # distutils never sets at all.
        with (tarfile.open(path, "r:gz") as src,
             tmp.open("wb") as raw,
             gzip.GzipFile(filename="", mode="wb", fileobj=raw,
                          mtime=epoch, compresslevel=9) as gz,
             tarfile.open(fileobj=gz, mode="w|") as dst):
            for member in src.getmembers():
                # A PAX-formatted member (the default write format since
                # Python 3.8, and what distutils produces whenever a
                # build-time mtime needs sub-second precision) carries its
                # original mtime a *second* time in `pax_headers`, which
                # `TarInfo.tobuf()` then prefers over the attribute below — so
                # the reassignment silently does nothing unless this stale
                # copy is cleared first. Every value it could hold is being
                # replaced below, so drop the whole dict rather than pick out
                # individual keys.
                member.pax_headers = {}
                member.mtime = min(int(member.mtime), epoch)
                member.uid = 0
                member.gid = 0
                member.uname = ""
                member.gname = ""
                if member.isfile():
                    dst.addfile(member, src.extractfile(member))
                else:
                    dst.addfile(member)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def resolve_epoch(explicit: int | None, env: dict[str, str]) -> int:
    """*explicit* if given, else ``$SOURCE_DATE_EPOCH`` from *env*.

    Refuses to guess: an sdist normalized to the wrong epoch is worse than one
    left alone, because it *looks* reproducible until compared against a
    second build that picked a different guess.
    """
    if explicit is not None:
        return explicit
    raw = env.get("SOURCE_DATE_EPOCH")
    if raw:
        return int(raw)
    raise SystemExit(
        "normalize_sdist: SOURCE_DATE_EPOCH is not set and no "
        "--source-date-epoch was given. Export it, typically:\n"
        "    export SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)")


def main(argv: list[str], env: dict[str, str] | None = None) -> int:
    if env is None:
        env = dict(os.environ)

    paths: list[str] = []
    explicit_epoch: int | None = None
    it = iter(argv)
    for arg in it:
        if arg == "--source-date-epoch":
            explicit_epoch = int(next(it))
        elif arg.startswith("--source-date-epoch="):
            explicit_epoch = int(arg.partition("=")[2])
        else:
            paths.append(arg)

    if not paths:
        print("normalize_sdist: no paths given", file=sys.stderr)
        return 1

    missing = [p for p in paths if not Path(p).is_file()]
    if missing:
        # Most likely cause: a shell glob (dist/*.tar.gz) matched nothing and
        # arrived as its own literal, unexpanded string. Accepting that
        # silently would leave the real sdist un-normalized and let the
        # pipeline attest it anyway — fail loudly instead.
        for p in missing:
            print(f"normalize_sdist: {p} does not exist", file=sys.stderr)
        return 1

    epoch = resolve_epoch(explicit_epoch, env)
    for p in paths:
        normalize(Path(p), epoch)
        print(f"normalized {p} to SOURCE_DATE_EPOCH={epoch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
