# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for scripts/check_anchors.py — the local link/anchor checker."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_anchors.py"
_DOCS = Path(__file__).resolve().parents[2] / "docs"

_skip = pytest.mark.skipif(not _SCRIPT.exists(), reason="script not reachable")


def _mod():
    spec = importlib.util.spec_from_file_location("check_anchors", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@_skip
def test_real_docs_have_no_broken_links():
    """The in-suite twin of the CI anchor pass."""
    problems = _mod().check(_DOCS)
    assert problems == [], "broken links in docs/: %s" % problems


@_skip
def test_dangling_in_page_anchor_is_caught(tmp_path):
    (tmp_path / "a.html").write_text(
        '<a href="#nope">x</a><h2 id="yes">y</h2>', encoding="utf-8")
    problems = _mod().check(tmp_path)
    assert len(problems) == 1 and "#nope" in problems[0]


@_skip
def test_valid_in_page_anchor_passes(tmp_path):
    (tmp_path / "a.html").write_text(
        '<a href="#yes">x</a><h2 id="yes">y</h2>', encoding="utf-8")
    assert _mod().check(tmp_path) == []


@_skip
def test_missing_local_target_is_caught(tmp_path):
    (tmp_path / "a.html").write_text('<link href="../style/gone.css">', encoding="utf-8")
    problems = _mod().check(tmp_path)
    assert len(problems) == 1 and "missing local target" in problems[0]


@_skip
def test_cross_page_anchor_checked_against_the_target(tmp_path):
    (tmp_path / "a.html").write_text('<a href="b.html#deep">x</a>', encoding="utf-8")
    (tmp_path / "b.html").write_text('<h2 id="other">y</h2>', encoding="utf-8")
    problems = _mod().check(tmp_path)
    assert len(problems) == 1 and "no anchor #deep" in problems[0]

    (tmp_path / "b.html").write_text('<h2 id="deep">y</h2>', encoding="utf-8")
    assert _mod().check(tmp_path) == []


@_skip
def test_external_and_scheme_links_are_skipped(tmp_path):
    (tmp_path / "a.html").write_text(
        '<a href="https://example.com/nope#frag">x</a>'
        '<a href="mailto:a@b.c">y</a><img src="data:image/svg+xml,x">',
        encoding="utf-8")
    assert _mod().check(tmp_path) == []


@_skip
def test_main_reports_and_exits_nonzero_on_break(tmp_path, capsys):
    (tmp_path / "a.html").write_text('<a href="#nope">x</a>', encoding="utf-8")
    rc = _mod().main(["--docs", str(tmp_path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "check-anchors: FAILED" in err
    assert "build_roadmap.py" in err          # the actionable hint
