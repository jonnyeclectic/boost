# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: where an item lives in its tap, and whether a clone is shallow.

`boost changelog` and `boost home` both need the path inside a tap that *is*
an item. A skill is its directory. A rule or workflow is one file whose
directory it shares with its siblings, so using the directory showed a
sibling's commits as the item's history and linked a folder of other rules.
"""
from __future__ import annotations

import subprocess

import pytest

from boost_cli.core import catalog, gitutil, lockfile, store
from boost_cli.errors import BoostError


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


def _make_repo(path, commits=2):
    path.mkdir(parents=True)
    _git("init", "-q", cwd=path)
    _git("config", "user.email", "t@test", cwd=path)
    _git("config", "user.name", "Test Author", cwd=path)
    for i in range(commits):
        (path / "a.txt").write_text("%d\n" % i, encoding="utf-8")
        _git("add", "-A", cwd=path)
        _git("commit", "-qm", "commit %d" % i, cwd=path)
    return path


# ── gitutil.is_shallow ───────────────────────────────────────────────────

class TestIsShallow:
    def test_a_complete_clone_is_not_shallow(self, tmp_path):
        src = _make_repo(tmp_path / "src")
        dest = tmp_path / "dest"
        # A local *path* ignores --depth; this is how every local tap clones.
        _git("clone", "-q", "--depth", "1", str(src), str(dest), cwd=tmp_path)
        assert gitutil.is_shallow(dest) is False

    def test_a_depth_one_clone_is_shallow(self, tmp_path):
        src = _make_repo(tmp_path / "src")
        dest = tmp_path / "dest"
        _git("clone", "-q", "--depth", "1", src.as_uri(), str(dest), cwd=tmp_path)
        assert gitutil.is_shallow(dest) is True
        # And it really is cut short: one commit of two.
        log = subprocess.run(["git", "-C", str(dest), "log", "--oneline"],
                             check=True, capture_output=True, text=True)
        assert len(log.stdout.splitlines()) == 1

    def test_a_directory_that_is_not_a_repo_is_not_shallow(self, tmp_path):
        assert gitutil.is_shallow(tmp_path) is False

    def test_a_shallow_path_that_is_a_directory_does_not_count(self, tmp_path):
        repo = _make_repo(tmp_path / "r", commits=1)
        (repo / ".git" / "shallow").mkdir()
        assert gitutil.is_shallow(repo) is False

    def test_accepts_a_string_path(self, tmp_path):
        repo = _make_repo(tmp_path / "r", commits=1)
        (repo / ".git" / "shallow").write_text("x\n", encoding="utf-8")
        assert gitutil.is_shallow(str(repo)) is True


# ── catalog.upstream_path ────────────────────────────────────────────────

class TestUpstreamPath:
    @pytest.mark.parametrize("kind", ("rule", "workflow"))
    def test_a_catalog_rule_or_workflow_is_its_file(self, kind):
        entry = {"kind": kind, "rel_dir": "rules/ci-cd",
                 "skill_md": "rules/ci-cd/dotnet-build.mdc"}
        assert catalog.upstream_path(entry) == "rules/ci-cd/dotnet-build.mdc"

    def test_a_catalog_skill_is_its_directory(self):
        entry = {"kind": "skill", "rel_dir": "skills/x",
                 "skill_md": "skills/x/SKILL.md"}
        assert catalog.upstream_path(entry) == "skills/x"

    def test_an_entry_with_no_kind_is_a_skill(self):
        # Older and synthesised entries omit `kind`; every one of them is a
        # skill, and a skill's history covers its scripts and assets too.
        entry = {"rel_dir": "skills/x", "skill_md": "skills/x/SKILL.md"}
        assert catalog.upstream_path(entry) == "skills/x"

    def test_a_lock_rule_or_workflow_is_its_source_file(self):
        lk = {"kind": "rule", "tap": "t",
              "source_file": "rules/ci-cd/dotnet-build.mdc"}
        assert catalog.upstream_path(lk) == "rules/ci-cd/dotnet-build.mdc"

    def test_a_lock_skill_is_its_source_dir(self):
        assert catalog.upstream_path({"tap": "t", "source_dir": "skills/x"}) \
            == "skills/x"

    def test_a_catalog_rule_with_no_file_falls_back_to_its_directory(self):
        entry = {"kind": "rule", "rel_dir": "rules/ci-cd", "skill_md": ""}
        assert catalog.upstream_path(entry) == "rules/ci-cd"

    @pytest.mark.parametrize("entry", ({}, {"kind": "rule"},
                                       {"source_file": "", "source_dir": ""},
                                       {"rel_dir": ""}))
    def test_nothing_recorded_is_the_whole_repo(self, entry):
        assert catalog.upstream_path(entry) == "."


# ── store.upstream_source ────────────────────────────────────────────────

def _rule_entry(tap="sib", source_file="plugins/a/agents/csharp-reviewer.md"):
    return {"kind": "workflow", "tap": tap, "source_file": source_file}


class TestUpstreamSource:
    def test_an_installed_workflow_never_asks_the_catalog(self, sandbox,
                                                          monkeypatch):
        # The catalog would refuse: three copies of the name in one tap.
        lockfile.set_workflow("csharp-reviewer", _rule_entry())

        def refuse(*_a, **_k):
            raise BoostError("'csharp-reviewer' matches 3 different workflows")
        monkeypatch.setattr(catalog, "resolve_one", refuse)
        assert store.upstream_source("csharp-reviewer") == (
            "csharp-reviewer", "workflow", "sib",
            "plugins/a/agents/csharp-reviewer.md")

    def test_an_installed_skill_is_its_directory(self, sandbox):
        lockfile.set_skill("x", {"tap": "t", "source_dir": "skills/x"})
        assert store.upstream_source("x") == ("x", "skill", "t", "skills/x")

    def test_a_lock_entry_with_no_tap_is_local(self, sandbox):
        lockfile.set_skill("x", {"source_dir": "/abs/x"})
        assert store.upstream_source("x") == ("x", "skill", "local", "/abs/x")

    def test_a_name_not_installed_asks_the_catalog(self, sandbox, monkeypatch):
        seen = []

        def resolve(name, *_a, **_k):
            seen.append(name)
            return {"kind": "rule", "tap": "sib", "rel_dir": "rules/ci-cd",
                    "skill_md": "rules/ci-cd/dotnet-build.mdc"}
        monkeypatch.setattr(catalog, "resolve_one", resolve)
        assert store.upstream_source("dotnet-build") == (
            "dotnet-build", "rule", "sib", "rules/ci-cd/dotnet-build.mdc")
        assert seen == ["dotnet-build"]

    def test_a_catalog_entry_with_no_kind_is_a_skill(self, sandbox, monkeypatch):
        monkeypatch.setattr(catalog, "resolve_one", lambda *_a, **_k: {
            "tap": "t", "rel_dir": "skills/x", "skill_md": "skills/x/SKILL.md"})
        assert store.upstream_source("x") == ("x", "skill", "t", "skills/x")

    def test_a_qualifier_naming_another_tap_asks_the_catalog(self, sandbox,
                                                             monkeypatch):
        # Installed from `sib`, asked about `other:` - the installed copy is
        # not this qualifier's answer, and the catalog parses the qualifier.
        lockfile.set_workflow("csharp-reviewer", _rule_entry())
        seen = []

        def resolve(name, *_a, **_k):
            seen.append(name)
            return {"kind": "workflow", "tap": "other",
                    "rel_dir": "agents", "skill_md": "agents/csharp-reviewer.md"}
        monkeypatch.setattr(catalog, "resolve_one", resolve)
        assert store.upstream_source("other:csharp-reviewer") == (
            "csharp-reviewer", "workflow", "other", "agents/csharp-reviewer.md")
        assert seen == ["other:csharp-reviewer"]
