# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: every pytest node id the contributor docs show selects a test.

CLAUDE.md's "one test" example was `test_catalog.py::test_scan_dir`, which
`pytest` rejects with "no match in any of [<Module test_catalog.py>]": the
tests live in `class TestScanDir`. An example command that errors teaches the
reader that the docs cannot be trusted, at the first command they copy.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
DOCS = ("CLAUDE.md", "CONTRIBUTING.md", "README.md")


def _node_ids() -> list[tuple[str, str]]:
    out = []
    for doc in DOCS:
        text = (ROOT / doc).read_text(encoding="utf-8")
        out += [(doc, m) for m in re.findall(r"pytest\s+\"?(tests/\S+?\.py::[\w:]+)", text)]
    return out


def _defines(path: Path, parts: list[str]) -> bool:
    scope: list[ast.stmt] = ast.parse(path.read_text(encoding="utf-8")).body
    for name in parts:
        hit = next((n for n in scope
                    if isinstance(n, (ast.ClassDef, ast.FunctionDef))
                    and n.name == name), None)
        if hit is None:
            return False
        scope = hit.body
    return True


def test_the_docs_still_show_a_node_id():
    assert any(doc == "CLAUDE.md" for doc, _ in _node_ids())


@pytest.mark.parametrize("doc,node", _node_ids())
def test_node_id_names_a_real_test(doc, node):
    path, *parts = node.split("::")
    assert (ROOT / path).is_file(), "%s: %s does not exist" % (doc, path)
    assert _defines(ROOT / path, parts), "%s: pytest finds no %s" % (doc, node)
