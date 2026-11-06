# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli._detect_version — the release-critical version chain.

The version is resolved lazily from (in order) the setuptools-scm file, a
git-checkout `git describe` when the package sits in one, the installed
package metadata, then a sentinel. These tests force each branch so the
fallbacks stay covered and correct.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

import boost_cli


def _no_scm_file(monkeypatch):
    """Make `from ._version import version` raise ImportError."""
    monkeypatch.setitem(sys.modules, "boost_cli._version", None)


class _Proc:
    def __init__(self, rc=0, out=""):
        self.returncode = rc
        self.stdout = out


def test_outside_a_checkout_uses_installed_metadata(monkeypatch):
    _no_scm_file(monkeypatch)
    monkeypatch.setattr(boost_cli, "_checkout_root", lambda: None)

    def no_git(*a, **k):
        raise AssertionError("no checkout, so git must not be asked")

    monkeypatch.setattr(subprocess, "run", no_git)
    monkeypatch.setattr("importlib.metadata.version", lambda name: "9.9.9")
    assert boost_cli._detect_version() == "9.9.9"


def test_a_checkout_reports_its_own_describe_over_unrelated_metadata(
        monkeypatch, tmp_path):
    # A fresh clone (no generated _version.py) beside an unrelated installed
    # boost-skill-cli 1.0.9 used to report 1.0.9 — metadata answers for any
    # dist on sys.path, not for the package actually imported.
    _no_scm_file(monkeypatch)
    monkeypatch.setattr(boost_cli, "_checkout_root", lambda: tmp_path)
    monkeypatch.setattr("importlib.metadata.version", lambda name: "1.0.9")
    seen = []
    monkeypatch.setattr(subprocess, "run", lambda argv, **k: (
        seen.append(argv) or _Proc(0, "v1.2.204-203-g9ef1d107\n")))
    assert boost_cli._detect_version() == "1.2.204-203-g9ef1d107"
    assert seen == [["git", "-C", str(tmp_path), "describe", "--tags",
                     "--always", "--dirty", "--match", "v[0-9]*"]]


def test_a_checkout_whose_describe_fails_falls_back_to_metadata(monkeypatch,
                                                                tmp_path):
    _no_scm_file(monkeypatch)
    monkeypatch.setattr(boost_cli, "_checkout_root", lambda: tmp_path)
    monkeypatch.setattr("importlib.metadata.version", lambda name: "1.0.9")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(128, ""))
    assert boost_cli._detect_version() == "1.0.9"


def test_an_empty_describe_is_not_a_version(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(0, "\n"))
    assert boost_cli._describe(tmp_path) is None


def test_git_describe_strips_leading_v(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(subprocess, "run", lambda argv, **k: (
        seen.append(k) or _Proc(0, "v2.3.4-1-gabcdef\n")))
    assert boost_cli._describe(tmp_path) == "2.3.4-1-gabcdef"
    assert seen == [{"capture_output": True, "text": True,
                     "encoding": "utf-8", "errors": "replace", "timeout": 3}]


def test_git_failure_returns_sentinel(monkeypatch, tmp_path):
    _no_scm_file(monkeypatch)
    monkeypatch.setattr(boost_cli, "_checkout_root", lambda: tmp_path)

    def boom(*a, **k):
        raise Exception("nope")

    monkeypatch.setattr("importlib.metadata.version", boom)
    monkeypatch.setattr(subprocess, "run", boom)
    assert boost_cli._detect_version() == "0.0.0+unknown"


class TestCheckoutRoot:
    def test_the_package_parent_with_a_git_dir_is_a_checkout(self, monkeypatch,
                                                             tmp_path):
        (tmp_path / "boost_cli").mkdir()
        (tmp_path / ".git").mkdir()
        monkeypatch.setattr(boost_cli, "__file__",
                            str(tmp_path / "boost_cli" / "__init__.py"))
        assert boost_cli._checkout_root() == tmp_path.resolve()

    def test_a_worktree_git_file_also_counts(self, monkeypatch, tmp_path):
        (tmp_path / "boost_cli").mkdir()
        (tmp_path / ".git").write_text("gitdir: /x\n", encoding="utf-8")
        monkeypatch.setattr(boost_cli, "__file__",
                            str(tmp_path / "boost_cli" / "__init__.py"))
        assert boost_cli._checkout_root() == tmp_path.resolve()

    def test_site_packages_is_not_a_checkout(self, monkeypatch, tmp_path):
        (tmp_path / "boost_cli").mkdir()
        monkeypatch.setattr(boost_cli, "__file__",
                            str(tmp_path / "boost_cli" / "__init__.py"))
        assert boost_cli._checkout_root() is None


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_a_newer_non_version_tag_is_never_described(tmp_path, monkeypatch):
    # The real shape: `shards-latest` sits on a commit past the last release
    # tag. Unmatched, describe prefers it and the version reads as
    # `shards-latest-…`, which parses as no version at all.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t",
                        "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
                        "-c", "tag.gpgsign=false", *args],
                       check=True, capture_output=True)

    git("init", "-q")
    git("commit", "-q", "--allow-empty", "-m", "one")
    git("tag", "v1.2.3")
    git("commit", "-q", "--allow-empty", "-m", "two")
    git("tag", "shards-latest")
    described = boost_cli._describe(tmp_path)
    assert described is not None and described.startswith("1.2.3-1-g"), described
