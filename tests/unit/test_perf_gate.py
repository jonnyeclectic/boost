"""Unit tests for scripts/perf_gate.py — the scaling-ratio decision logic."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "perf_gate.py"

_skip = pytest.mark.skipif(not _SCRIPT.exists(), reason="script not reachable")


def _mod():
    spec = importlib.util.spec_from_file_location("perf_gate", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@_skip
def test_linear_scaling_passes(monkeypatch, capsys):
    pg = _mod()
    fake = {64: {"scan": .01, "build": .01, "retrieve": .001},
            512: {"scan": .08, "build": .08, "retrieve": .008}}   # exactly 8x
    monkeypatch.setattr(pg, "_measure", lambda n, v: fake[n])
    assert pg.main([]) == 0
    assert "perf-gate: OK" in capsys.readouterr().out


@_skip
def test_quadratic_scaling_fails(monkeypatch, capsys):
    pg = _mod()
    fake = {64: {"scan": .01, "build": .01, "retrieve": .001},
            512: {"scan": .64, "build": .08, "retrieve": .008}}   # scan at 64x
    monkeypatch.setattr(pg, "_measure", lambda n, v: fake[n])
    assert pg.main([]) == 1
    out = capsys.readouterr()
    assert "FAIL scan" in out.out
    assert "superlinear" in out.err


@_skip
def test_absolute_backstop_fails_even_at_linear_ratio(monkeypatch, capsys):
    pg = _mod()
    fake = {64: {"scan": 5.0, "build": .01, "retrieve": .001},
            512: {"scan": 40.0, "build": .08, "retrieve": .008}}  # 8x but 40s
    monkeypatch.setattr(pg, "_measure", lambda n, v: fake[n])
    assert pg.main([]) == 1
    assert "FAIL scan" in capsys.readouterr().out


@_skip
def test_synthetic_catalog_has_expected_entry_count(tmp_path):
    pg = _mod()
    pg._mk_catalog(tmp_path, 5)
    import boost_cli.core.catalog as catalog
    entries = catalog.scan_dir(tmp_path, "t")
    kinds = sorted(e.get("kind", "skill") for e in entries)
    assert len(entries) == 15
    assert kinds.count("skill") == 5
    assert kinds.count("rule") == 5
    assert kinds.count("workflow") == 5
