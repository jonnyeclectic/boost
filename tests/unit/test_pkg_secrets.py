# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: pkg._warn_secrets — the install-time secret-scan wiring."""
from __future__ import annotations

from boost_cli.commands import pkg
from boost_cli.core import output as out
from boost_cli.core.store import InstallResult


def _capture(monkeypatch):
    warnings = []
    monkeypatch.setattr(out, "warn", lambda m: warnings.append(m))
    return warnings


def _result(tmp_path, body):
    dest = tmp_path / "leaky-skill"
    dest.mkdir()
    (dest / "SKILL.md").write_text(body, encoding="utf-8")
    return InstallResult(name="leaky-skill", dest=dest)


def test_warns_on_embedded_secret(monkeypatch, tmp_path):
    warnings = _capture(monkeypatch)
    pkg._warn_secrets(_result(tmp_path, "aws = AKIAIOSFODNN7EXAMPLE"))
    assert any("possible secret" in w for w in warnings)
    assert any("high" in w for w in warnings)


def test_never_prints_raw_secret(monkeypatch, tmp_path):
    leaked = "AKIAIOSFODNN7EXAMPLE"
    warnings = _capture(monkeypatch)
    pkg._warn_secrets(_result(tmp_path, "aws = " + leaked))
    assert all(leaked not in w for w in warnings)


def test_quiet_on_clean_skill(monkeypatch, tmp_path):
    warnings = _capture(monkeypatch)
    pkg._warn_secrets(_result(tmp_path, "# Clean\nRuns pytest.\n"))
    assert warnings == []


def test_missing_skill_md_quiet(monkeypatch, tmp_path):
    dest = tmp_path / "no-md"
    dest.mkdir()
    warnings = _capture(monkeypatch)
    pkg._warn_secrets(InstallResult(name="no-md", dest=dest))
    assert warnings == []


def test_singular_wording(monkeypatch, tmp_path):
    warnings = _capture(monkeypatch)
    pkg._warn_secrets(_result(tmp_path, "aws = AKIAIOSFODNN7EXAMPLE"))
    summary = next(w for w in warnings if "possible secret" in w)
    assert "1 possible secret in" in summary
