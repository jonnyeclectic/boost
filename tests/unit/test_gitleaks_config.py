# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit test: .gitleaks.toml — the secret-scanning gate's configuration.

Validates the config is well-formed and does what the CI gate relies on:
extend the upstream default ruleset and allowlist boost's own synthetic
secret-scanner fixtures (so the gate stays green on deliberate test data while
still catching a real leak anywhere else).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_CONFIG = Path(__file__).resolve().parents[2] / ".gitleaks.toml"

pytestmark = [
    pytest.mark.skipif(not _CONFIG.exists(),
                       reason="repo-root .gitleaks.toml not reachable (e.g. mutation sandbox)"),
    pytest.mark.skipif(sys.version_info < (3, 11),
                       reason="tomllib is stdlib only on Python 3.11+"),
]


def _load():
    import tomllib
    with open(_CONFIG, "rb") as f:
        return tomllib.load(f)


def test_is_valid_toml():
    assert isinstance(_load(), dict)


def test_extends_the_default_ruleset():
    # Without useDefault the config would replace, not extend, gitleaks' rules —
    # silently disabling every built-in detector.
    cfg = _load()
    assert cfg.get("extend", {}).get("useDefault") is True


def test_allowlists_the_secretscan_fixtures():
    cfg = _load()
    allowlists = cfg.get("allowlists") or ([cfg["allowlist"]] if "allowlist" in cfg else [])
    paths = [p for al in allowlists for p in al.get("paths", [])]
    assert any("test_secretscan" in p for p in paths), (
        "the synthetic-secret fixture file must be allowlisted or the gate "
        "reports boost's own test data as a leak")


def test_allowlist_does_not_blanket_ignore_tests():
    # A too-broad `tests/` allowlist would blind the scanner to a real secret
    # committed in any other test file. Keep it scoped to the fixture file.
    cfg = _load()
    allowlists = cfg.get("allowlists") or ([cfg["allowlist"]] if "allowlist" in cfg else [])
    paths = [p for al in allowlists for p in al.get("paths", [])]
    for p in paths:
        assert p.rstrip("$").rstrip("/") not in ("tests", "tests/", r"tests/.*", "tests"), \
            "allowlist path %r is too broad — scope it to the fixture file" % p
