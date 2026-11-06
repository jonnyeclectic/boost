# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""catalog.declared_version: what the file declares, never the 0.0.0 stand-in.

`_make_entry` stamps 0.0.0 on an unversioned file so the field always sorts;
provenance quoting that read `@ 0.0.0` for a version that exists nowhere in
the source.
"""
from __future__ import annotations

from pathlib import Path

from boost_cli.core import catalog


def test_the_placeholder_is_what_an_unversioned_scan_stamps(tmp_path):
    skill = tmp_path / "skills" / "plain" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: plain\ndescription: d\n---\nbody\n",
                     encoding="utf-8")
    versioned = tmp_path / "skills" / "tagged" / "SKILL.md"
    versioned.parent.mkdir(parents=True)
    versioned.write_text(
        "---\nname: tagged\ndescription: d\nversion: 1.10\n---\nbody\n",
        encoding="utf-8")
    entries = {e["name"]: e for e in catalog.scan_dir(Path(tmp_path), "t")}
    assert entries["plain"]["version"] == catalog.UNDECLARED_VERSION == "0.0.0"
    assert catalog.declared_version(entries["plain"]) == ""
    # Lossless: 1.10 stays 1.10, not 1.1.
    assert catalog.declared_version(entries["tagged"]) == "1.10"


def test_meta_decides_when_present():
    assert catalog.declared_version(
        {"version": "2.0.0", "meta": {"version": "2.0.0"}}) == "2.0.0"
    assert catalog.declared_version(
        {"version": "0.0.0", "meta": {"name": "x"}}) == ""
    # A file that really declares 0.0.0 is quoted: the meta says it did.
    assert catalog.declared_version(
        {"version": "0.0.0", "meta": {"version": "0.0.0"}}) == "0.0.0"
    # A blank declaration is no declaration.
    assert catalog.declared_version(
        {"version": "0.0.0", "meta": {"version": "  "}}) == ""
    assert catalog.declared_version({"meta": {"version": "1.0"}}) == ""


def test_without_meta_the_placeholder_reads_as_absent():
    assert catalog.declared_version({"version": "0.0.0"}) == ""
    assert catalog.declared_version({"version": "3.1.4"}) == "3.1.4"
    assert catalog.declared_version({}) == ""
    assert catalog.declared_version({"version": None, "meta": None}) == ""
