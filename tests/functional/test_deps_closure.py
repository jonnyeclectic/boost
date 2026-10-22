# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional: one `requires:` closure for install, deps, update and bundle.

Four commands answered "what does this skill need" four ways. A qualified
`requires: [alpha:base]` was never met by an installed `base`; a bare
dependency two taps ship was announced as pulled in and then skipped while the
prerequisite line named the declaring tap's copy; `boost update` upgraded a
skill onto a new `requires:` and installed nothing; a Boostfile line installed
its skill alone. Exact lines and exit codes, because each bug was a line that
said one thing while the run did another.
"""
from __future__ import annotations

import subprocess

import pytest

from boost_cli.core import lockfile


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@e",
                    "-c", "user.name=t", *args], check=True,
                   capture_output=True)


def _skill(root, name, extra="", version="1.0.0", desc=None):
    d = root / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "---\nname: %s\ndescription: %s\nversion: %s\n%s---\n\nBody of %s.\n"
        % (name, desc or "%s in %s" % (name, root.name), version, extra, name),
        encoding="utf-8")


def _commit(root):
    if not (root / ".git").exists():
        subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "c")


def _lines(r):
    return [" ".join(line.split()) for line in (r.out + r.err).splitlines()
            if line.strip()]


@pytest.fixture
def alpha(tmp_path):
    root = tmp_path / "alpha"
    _skill(root, "base")
    _skill(root, "qual", "requires: [alpha:base]\n")
    _skill(root, "lib", "requires: [base, newdep]\n")
    _skill(root, "newdep")
    _skill(root, "util", "requires: [base]\n")
    _skill(root, "app", "requires: [lib, util]\n")
    _commit(root)
    return root


@pytest.fixture
def beta(tmp_path):
    root = tmp_path / "beta"
    _skill(root, "newdep", desc="a different newdep")
    _commit(root)
    return root


def _installed():
    return {n: e.get("tap") for n, e in lockfile.installed().items()}


class TestQualifiedRequirement:
    def test_install_counts_an_installed_base_as_met(self, boost, alpha):
        boost("tap", alpha)
        boost("install", "base")
        r = boost("install", "qual", "--dry-run")
        assert not any("pulling in" in ln for ln in _lines(r))
        assert not any("already installed" in ln for ln in _lines(r))
        r = boost("install", "qual")
        assert not any("already installed" in ln for ln in _lines(r))
        assert set(_installed()) == {"base", "qual"}

    def test_install_pulls_in_a_qualified_requirement(self, boost, alpha):
        boost("tap", alpha)
        r = boost("install", "qual")
        assert "pulling in 1 dependency required by your selection: base" \
            in _lines(r)
        assert _installed() == {"base": "alpha", "qual": "alpha"}

    def test_deps_renders_the_qualified_token(self, boost, alpha):
        boost("tap", alpha)
        boost("install", "qual", "--no-deps")
        r = boost("deps", expect=1)
        assert _lines(r) == [
            "qual requires alpha:base ✗ not installed",
            "! `boost install base` to satisfy 1 unmet requirement"]
        r = boost("deps", "qual", expect=1)
        assert "requires: alpha:base ✗ not installed" in _lines(r)
        boost("install", "base")
        r = boost("deps")
        assert _lines(r) == [
            "✓ no unmet requirements or conflicts across 2 skills"]
        r = boost("deps", "qual")
        assert "requires: alpha:base ✓ installed" in _lines(r)


class TestSameTapFirst:
    def test_install_takes_the_declaring_tap_s_copy(self, boost, alpha,
                                                     beta):
        boost("tap", alpha)
        boost("tap", beta)
        boost("install", "base")
        r = boost("install", "lib", "--dry-run")
        lines = _lines(r)
        assert ("pulling in 1 dependency required by your selection: "
                "alpha:newdep") in lines
        assert not any("matches 2 catalog entries" in ln for ln in lines)
        boost("install", "lib")
        assert _installed() == {"base": "alpha", "lib": "alpha",
                                "newdep": "alpha"}

    def test_deps_hint_is_a_command_that_runs(self, boost, alpha, beta):
        boost("tap", alpha)
        boost("tap", beta)
        boost("install", "lib", "--no-deps")
        r = boost("deps", "lib", expect=1)
        assert _lines(r)[-1] == ("! `boost install alpha:newdep base` to "
                                 "satisfy 2 unmet requirements")
        r = boost("deps", expect=1)
        assert _lines(r)[-1] == ("! `boost install alpha:newdep base` to "
                                 "satisfy 2 unmet requirements")
        boost("install", "alpha:newdep", "base")
        boost("deps", "lib")


class TestUpdateExpandsRequires:
    def test_an_upgrade_that_adds_a_requirement_installs_it(self, boost,
                                                            tmp_path):
        root = tmp_path / "up"
        _skill(root, "base")
        _skill(root, "lib", "requires: [base]\n")
        _commit(root)
        boost("tap", root)
        boost("install", "lib")
        _skill(root, "lib", "requires: [base, newdep]\n", version="1.1.0")
        _skill(root, "newdep")
        _commit(root)
        r = boost("update")
        lines = _lines(r)
        assert ("pulling in 1 dependency required by your selection: newdep"
                in lines)
        assert "✓ installed newdep v1.0.0 (up)" in lines
        assert _installed() == {"base": "up", "lib": "up", "newdep": "up"}
        boost("deps", "lib")


class TestBundleExpandsRequires:
    def test_dry_run_and_real_run_install_the_closure(self, boost, alpha,
                                                      tmp_path):
        boost("tap", alpha)
        bf = tmp_path / "Boostfile"
        bf.write_text("skill app\nskill util\n", encoding="utf-8")
        r = boost("bundle", "install", bf, "--dry-run")
        assert _lines(r) == [
            "pulling in 4 dependencies required by your selection: base, "
            "newdep, lib, util",
            "would install base v1.0.0 (alpha)",
            "would install newdep v1.0.0 (alpha)",
            "would install lib v1.0.0 (alpha)",
            "would install util v1.0.0 (alpha)",
            "would install app v1.0.0 (alpha)",
            "would install 5 skills, 1 already present"]
        assert _installed() == {}
        r = boost("bundle", "install", bf)
        assert _lines(r)[-1] == "Installed 5 skills, 1 already present"
        assert set(_installed()) == {"app", "lib", "util", "base", "newdep"}
        boost("deps", "app")
