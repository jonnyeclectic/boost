# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A repo with no commits yet is still a repo.

`_current_branch` shelled `git rev-parse --abbrev-ref HEAD`, which fails on an
unborn HEAD with the same non-zero exit it gives outside a repo — so the two
states were indistinguishable. `boost context status` told the user "(not in a
git repository)" while standing in one, and `boost context apply` declined to
do anything there. `git init` followed by `boost context apply` is an ordinary
first five minutes in a new project.
"""
from __future__ import annotations

import json
import subprocess


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t",
                    *list(args)], cwd=str(cwd), check=True, capture_output=True)


def _unborn_repo(root, branch="feature/x"):
    """A freshly-initialised repo on `branch`, before its first commit."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", branch)
    return root


class TestUnbornHead:
    def test_status_names_the_branch(self, boost, tmp_path, monkeypatch):
        monkeypatch.chdir(_unborn_repo(tmp_path / "fresh"))
        r = boost("context", "status")
        assert "(not in a git repository)" not in r.out
        assert "feature/x" in r.out

    def test_json_carries_the_branch(self, boost, tmp_path, monkeypatch):
        monkeypatch.chdir(_unborn_repo(tmp_path / "fresh2"))
        r = boost("context", "status", "--json")
        assert json.loads(r.out)["branch"] == "feature/x"

    def test_apply_does_not_refuse(self, boost, tmp_path, monkeypatch):
        root = _unborn_repo(tmp_path / "fresh3")
        monkeypatch.chdir(root)
        r = boost("context", "apply")
        assert "not inside a git repository" not in r.out

    def test_the_first_commit_changes_nothing(self, boost, tmp_path, monkeypatch):
        """The answer must not depend on whether a commit happens to exist."""
        root = _unborn_repo(tmp_path / "fresh4")
        monkeypatch.chdir(root)
        before = boost("context", "status", "--json")
        _git(root, "commit", "-q", "--allow-empty", "-m", "init")
        after = boost("context", "status", "--json")
        assert json.loads(before.out)["branch"] == json.loads(after.out)["branch"]

    def test_a_real_non_repo_still_says_so(self, boost, tmp_path, monkeypatch):
        """The message this replaces is correct in the case it was written for."""
        plain = tmp_path / "notarepo"
        plain.mkdir()
        monkeypatch.chdir(plain)
        r = boost("context", "status")
        assert "(not in a git repository)" in r.out
        assert json.loads(boost("context", "status", "--json").out)["branch"] is None
