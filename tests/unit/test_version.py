# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli._detect_version — the release-critical version chain.

The version is resolved lazily from (in order) the setuptools-scm file, the
installed package metadata, a git-checkout `git describe`, then a sentinel.
These tests force each branch so the fallbacks stay covered and correct.
"""
from __future__ import annotations

import subprocess
import sys

import boost_cli


def _no_scm_file(monkeypatch):
    """Make `from ._version import version` raise ImportError."""
    monkeypatch.setitem(sys.modules, "boost_cli._version", None)


def test_prefers_installed_metadata(monkeypatch):
    _no_scm_file(monkeypatch)
    monkeypatch.setattr("importlib.metadata.version", lambda name: "9.9.9")
    assert boost_cli._detect_version() == "9.9.9"


def test_git_describe_fallback_strips_leading_v(monkeypatch):
    _no_scm_file(monkeypatch)

    def no_metadata(name):
        raise Exception("not installed")

    monkeypatch.setattr("importlib.metadata.version", no_metadata)

    class Proc:
        returncode = 0
        stdout = "v2.3.4-1-gabcdef\n"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Proc())
    assert boost_cli._detect_version() == "2.3.4-1-gabcdef"


def test_git_failure_returns_sentinel(monkeypatch):
    _no_scm_file(monkeypatch)

    def boom(*a, **k):
        raise Exception("nope")

    monkeypatch.setattr("importlib.metadata.version", boom)
    monkeypatch.setattr(subprocess, "run", boom)
    assert boost_cli._detect_version() == "0.0.0+unknown"
