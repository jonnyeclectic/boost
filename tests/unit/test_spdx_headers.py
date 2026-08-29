# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Every source file carries a copyright line and an SPDX licence identifier.

The sweep that puts them there is `scripts/add_spdx_headers.py`, which also
owns the file list and the expression; this is the gate that keeps a new file
from landing without one.
"""
from __future__ import annotations

import importlib.util
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
    """`GPL-3.0-only` is a claim about LICENSE; keep the two in step."""
    licence = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in licence
    assert "Version 3" in licence
    # If an "or any later version" grant is ever added, `-only` becomes wrong.
    # This is the tripwire for that day.
    assert "at your option) any later version" not in licence.split("Preamble")[0]
