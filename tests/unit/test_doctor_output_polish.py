# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: three `boost doctor` wording defects from the 2026-08 CLI audit.

See docs/roadmap/items/audit-doctor-findings.md. The crash-glyph and verdict
verb-agreement fixes are exercised end to end in
tests/functional/test_cli_quality.py::TestDoctor; this file targets the third
one directly, because reaching a *degraded* dense store through the full CLI
needs a real sqlite-vec build. `_report_search_engine` takes its `bad`
callback as a plain argument, so the join can be pinned without one.
"""
from __future__ import annotations

from boost_cli.commands import quality
from boost_cli.core import dense


def test_degraded_dense_hint_joins_with_an_em_dash_not_a_period(monkeypatch):
    """Was: "...using BM25. install the extra: ...", a lowercase sentence
    start because `fix_hint` strings begin lowercase by design — the other
    two consumers (discovery.py, core/mcp.py) already join with "— %s"."""
    monkeypatch.setattr(
        dense, "status",
        lambda count=False: {
            "ready": False, "degraded": True, "reason": "model-changed",
            "chunks": 42, "built_model": "old-model", "built_provider": None,
            "model": "new-model", "provider": "voyage",
        })
    monkeypatch.setattr(
        dense, "fix_hint",
        lambda reason, status=None: "reindex with `boost reindex --dense`")

    messages = []
    quality._report_search_engine(lambda msg, wrap=False: messages.append(msg))

    assert len(messages) == 1
    assert "BM25 — reindex with `boost reindex --dense`" in messages[0]
    assert "BM25. reindex" not in messages[0]
    assert "BM25." not in messages[0]
