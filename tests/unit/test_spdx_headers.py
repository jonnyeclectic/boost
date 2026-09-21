# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Every source file carries a copyright line and an SPDX licence identifier.

The sweep that puts them there is `scripts/add_spdx_headers.py`, which also
owns the file list and the expression; this is the gate that keeps a new file
from landing without one.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = ROOT / "scripts" / "add_spdx_headers.py"


def _mod():
    spec = importlib.util.spec_from_file_location("add_spdx_headers", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SPDX = _mod()
_FILES = _SPDX.source_files()


def test_the_sweep_found_something() -> None:
    """A glob that silently matches nothing would pass every test below."""
    assert len(_FILES) > 250, f"only {len(_FILES)} source files -- the glob is wrong"


@pytest.mark.parametrize("path", _FILES, ids=_SPDX.relative)
def test_copyright_and_licence_header(path: Path) -> None:
    # The header must be near the top, where a reader lands. Ten lines is room
    # for a shebang, an encoding line and a blank, and no more.
    head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:10])
    rel = _SPDX.relative(path)
    assert _SPDX.COPYRIGHT in head, f"{rel}: no copyright line in the first 10 lines"
    assert _SPDX.SPDX_LINE in head, f"{rel}: no {_SPDX.SPDX_LINE} in the first 10 lines"


@pytest.mark.parametrize("path", _FILES, ids=_SPDX.relative)
def test_shebang_stays_first(path: Path) -> None:
    """A header inserted above `#!` turns an executable script into text."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("#!"):
        pytest.skip("no shebang")
    assert text.splitlines()[0].startswith("#!")


def test_stamping_is_idempotent() -> None:
    """Running the sweep twice must not stack two headers on a file."""
    once = _SPDX.stamp("import os\n")
    assert not _SPDX.needs_header(once)
    assert once.count(_SPDX.SPDX_LINE) == 1


def test_stamp_keeps_a_shebang_on_line_one() -> None:
    out = _SPDX.stamp("#!/usr/bin/env bash\nset -e\n")
    assert out.startswith("#!/usr/bin/env bash\n")
    assert out.splitlines()[1] == f"# {_SPDX.COPYRIGHT}"


def test_expression_matches_the_declared_licence() -> None:
    """The stamped expression is a claim about LICENSE; keep the two in step.

    The header says `Apache-2.0`, so LICENSE must be the Apache License 2.0 and
    must not still be the GPL text. That second assertion is the one with
    history: a relicence that updates 319 headers and forgets the licence file
    leaves every source file pointing at terms the repository does not ship.
    """
    path = ROOT / "LICENSE"
    if not path.is_file():
        pytest.skip("LICENSE not reachable from this tree")
    licence = path.read_text(encoding="utf-8")
    assert "Apache License" in licence
    assert "Version 2.0, January 2004" in licence
    assert "GNU GENERAL PUBLIC LICENSE" not in licence
    # Apache-2.0's whole point over MIT is the patent grant; if LICENSE were
    # ever swapped for a text lacking it, the expression would be wrong.
    assert "Grant of Patent License" in licence


def test_claude_md_names_the_expression_the_sweep_stamps() -> None:
    """The instruction agents read must name the licence the tree uses.

    CLAUDE.md is not commentary: it is the file every contributor and every
    agent reads before writing a line, and its header rule quotes the SPDX
    expression literally. #587 relicensed the tree from `GPL-3.0-only` to
    Apache-2.0 — LICENSE, pyproject, `SPDX_ID` and every header — and left
    that sentence behind, so for months the one surface a human reads told
    them to open a new file with a licence the repository does not ship.

    Pinned to `SPDX_ID` rather than to the string "Apache-2.0", so the next
    relicence is still one edit and this test moves with it.
    """
    path = ROOT / "CLAUDE.md"
    if not path.is_file():
        pytest.skip("CLAUDE.md not reachable from this tree")
    text = path.read_text(encoding="utf-8")
    assert "SPDX-License-Identifier: %s" % _SPDX.SPDX_ID in text
    # And names no other: a second expression in the same file is the drift
    # this test exists to catch, whichever direction it points.
    others = {m for m in re.findall(r"SPDX-License-Identifier: ([\w.\-+]+)", text)
              if m != _SPDX.SPDX_ID}
    assert not others, "CLAUDE.md also names %s" % ", ".join(sorted(others))


def test_no_two_package_files_are_byte_identical() -> None:
    """Two identical files in the wheel are a `check-wheel-contents` W002.

    Adding the header made `boost_cli/commands/__init__.py` and
    `boost_cli/core/__init__.py` byte-identical -- both had been empty, and
    empty files are exempt from that check. Each now carries a one-line
    docstring saying what the package is, which is the fix and the
    documentation at once.
    """
    import hashlib
    from collections import defaultdict

    by_digest: dict[str, list[str]] = defaultdict(list)
    for path in sorted((ROOT / "boost_cli").rglob("*.py")):
        by_digest[hashlib.sha256(path.read_bytes()).hexdigest()].append(
            _SPDX.relative(path)
        )
    dupes = {d: f for d, f in by_digest.items() if len(f) > 1}
    assert not dupes, f"identical files ship twice in the wheel: {dupes}"


@pytest.mark.parametrize("guide", ["CLAUDE.md", "CONTRIBUTING.md"])
def test_contributor_guide_names_the_expression_the_script_writes(guide):
    # Both guides told contributors to write GPL-3.0-only headers long after
    # every file, LICENSE and this script had moved to Apache-2.0.
    path = ROOT / guide
    if not path.exists():
        pytest.skip("%s not reachable (e.g. mutation sandbox)" % guide)
    text = path.read_text(encoding="utf-8")
    assert set(re.findall(r"SPDX-License-Identifier: ([\w.+-]+)", text)) \
        == {_SPDX.SPDX_ID}
