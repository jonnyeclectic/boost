"""Committed roadmap HTML stays in lockstep with its item source files.

The roadmap boards are generated from ``docs/roadmap/items/*.md`` by
``scripts/build_roadmap.py`` and injected into the marker regions of the
hand-authored pages. This test — the in-suite twin of the
``build_roadmap.py --check`` CI step — fails if the committed HTML drifts from a
fresh render, so a stale board can't merge.

Skips when the repo-root files aren't reachable (e.g. the mutation sandbox,
which only copies ``boost_cli/``).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "build_roadmap.py"
_ITEMS = _ROOT / "docs" / "roadmap" / "items"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_roadmap", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not (_SCRIPT.exists() and _ITEMS.exists()),
                    reason="repo-root files not reachable (e.g. mutation sandbox)")
def test_roadmap_html_is_regenerated():
    builder = _load_builder()
    path, fresh = builder.build_code()
    committed = path.read_text()
    assert committed == fresh, (
        "docs/roadmap.html is out of date — regenerate with\n"
        "    python3 scripts/build_roadmap.py\n"
        "and commit the result (see CONTRIBUTING.md)."
    )


@pytest.mark.skipif(not (_SCRIPT.exists() and _ITEMS.exists()),
                    reason="repo-root files not reachable (e.g. mutation sandbox)")
def test_design_roadmap_html_is_regenerated():
    builder = _load_builder()
    path, fresh = builder.build_design()
    committed = path.read_text()
    assert committed == fresh, (
        "docs/design-roadmap.html is out of date — regenerate with\n"
        "    python3 scripts/build_roadmap.py\n"
        "and commit the result (see CONTRIBUTING.md)."
    )


@pytest.mark.skipif(not (_SCRIPT.exists() and _ITEMS.exists()),
                    reason="repo-root files not reachable (e.g. mutation sandbox)")
def test_check_flag_passes_on_fresh_tree():
    builder = _load_builder()
    assert builder.main(["--check"]) == 0


@pytest.mark.skipif(not (_SCRIPT.exists() and _ITEMS.exists()),
                    reason="repo-root files not reachable (e.g. mutation sandbox)")
def test_every_code_item_has_required_fields():
    builder = _load_builder()
    for item in builder.load_items("code"):
        for field in ("id", "section", "status", "title"):
            assert item.get(field), "%s: missing %r" % (item["_file"], field)
        assert item["status"] in builder.STATUS_LABEL, (
            "%s: bad status %r" % (item["_file"], item["status"]))


@pytest.mark.skipif(not (_SCRIPT.exists() and _ITEMS.exists()),
                    reason="repo-root files not reachable (e.g. mutation sandbox)")
def test_every_design_item_has_required_fields():
    builder = _load_builder()
    for item in builder.load_items("design"):
        for field in ("id", "track", "status", "title"):
            assert item.get(field), "%s: missing %r" % (item["_file"], field)
        assert item["status"] in builder.DESIGN_STATUS, (
            "%s: bad status %r" % (item["_file"], item["status"]))
        assert str(item.get("impact", "")).lower() in builder.IMPACT_LABEL, (
            "%s: bad impact %r" % (item["_file"], item.get("impact")))
