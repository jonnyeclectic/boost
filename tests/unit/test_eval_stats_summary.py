# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for scripts/eval_stats_summary.py — the significance summary."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "eval_stats_summary.py"

_skip = pytest.mark.skipif(not _SCRIPT.exists(), reason="script not reachable")


def _mod():
    spec = importlib.util.spec_from_file_location("eval_stats_summary", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PAYLOAD = {
    "significance": {
        "stat_test": "student",
        "metrics": ["recall@10", "mrr"],
        "model_names": ["catalog.search", "BM25 full-content"],
        "catalog.search": {
            "comparisons": {
                "BM25 full-content": {"recall@10": 0.0047, "mrr": 0.20},
            },
        },
        "BM25 full-content": {"comparisons": {}},
    }
}


@_skip
def test_significant_metric_marked_and_counted():
    md = _mod().render(_PAYLOAD)
    assert "Best engine: **BM25 full-content**" in md
    assert "✅ p=0.0047" in md          # recall@10 is significant
    assert "· p=0.2000" in md           # mrr is not
    assert "1 of the compared metrics reach significance." in md


@_skip
def test_missing_significance_is_a_graceful_skip():
    md = _mod().render({"k": 10})
    assert "_skipped_" in md
    assert "ranx" in md


@_skip
def test_none_payload_does_not_crash():
    md = _mod().render(None)
    assert "skipped" in md.lower()


@_skip
def test_single_engine_has_nothing_to_compare():
    md = _mod().render({"significance": {
        "metrics": ["recall@10"], "model_names": ["only-one"]}})
    assert "nothing to compare" in md


@_skip
def test_main_reads_file_and_prints(tmp_path, capsys):
    p = tmp_path / "stats.json"
    p.write_text(json.dumps(_PAYLOAD), encoding="utf-8")
    rc = _mod().main([str(p)])
    assert rc == 0
    assert "✅ p=0.0047" in capsys.readouterr().out


@_skip
def test_main_on_missing_file_is_graceful(capsys):
    rc = _mod().main(["/no/such/stats.json"])
    assert rc == 0
    assert "skipped" in capsys.readouterr().out.lower()
