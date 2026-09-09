# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: three `boost doctor` wording defects from the 2026-08 CLI audit.

See docs/roadmap/items/audit-doctor-findings.md. The crash-glyph and verdict
verb-agreement fixes are exercised end to end in
tests/functional/test_cli_quality.py::TestDoctor; this file targets the third
one directly, because reaching a *degraded* dense store through the full CLI
needs a real sqlite-vec build. `_report_search_engine` reports through a
`core.report.Report` passed as a plain argument, so the join can be pinned
without one — in JSON mode the collector prints nothing and keeps every
message addressable in its payload.
"""
from __future__ import annotations

from boost_cli.commands import quality
from boost_cli.core import dense, report


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

    rep = report.Report(as_json=True)
    quality._report_search_engine(rep)

    checks = rep.payload()["checks"]
    assert len(checks) == 1
    # A degraded store is a real fault, so it must still move the exit code.
    assert checks[0]["status"] == "issue" and rep.issues == 1
    message = checks[0]["message"]
    assert "BM25 — reindex with `boost reindex --dense`" in message
    assert "BM25. reindex" not in message
    assert "BM25." not in message
