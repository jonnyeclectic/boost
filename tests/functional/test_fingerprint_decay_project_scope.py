# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost fingerprint` and `boost decay` see project-scope installs.

`boost list --local` showed a skill installed `--scope project`, while the
fingerprint digest stayed byte-identical before and after the install and
`decay` never judged it — both read the user lock alone, though every agent
run in the repo loads the vendored copy.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import projectlock


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A git-marked project directory, cd'd into."""
    d = tmp_path / "fdp-repo"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d.resolve()


def _fp(boost):
    return json.loads(boost("fingerprint", "--json").out)


class TestFingerprint:
    def test_project_install_moves_the_digest(self, boost, tapped, repo):
        before = _fp(boost)
        boost("install", "--local", "commit-messages")
        after = _fp(boost)
        sha = projectlock.get_skill(repo, "commit-messages")["sha256"]
        assert sha
        assert "project/commit-messages:%s" % sha in after["components"]
        assert after["fingerprint"] != before["fingerprint"]
        assert (sorted(set(after["components"]) - set(before["components"]))
                == ["project/commit-messages:%s" % sha])
        r = boost("fingerprint", "--verbose")
        assert "project/commit-messages" in r.out

    def test_outside_the_project_the_digest_is_user_only(
            self, boost, tapped, repo, tmp_path, monkeypatch):
        boost("install", "--local", "commit-messages")
        inside = _fp(boost)
        outside_dir = tmp_path / "not-a-project"
        outside_dir.mkdir()
        monkeypatch.chdir(outside_dir)
        outside = _fp(boost)
        assert not [c for c in outside["components"]
                    if c.startswith("project/")]
        assert outside["fingerprint"] != inside["fingerprint"]


class TestDecay:
    def test_project_install_is_a_row(self, boost, tapped, repo):
        boost("install", "brainstorming")
        boost("install", "--local", "commit-messages")
        data = json.loads(boost("decay", "--json").out)
        assert [(s["name"], s["scope"]) for s in data["skills"]] == [
            ("brainstorming", "user"), ("commit-messages", "project")]
        assert [(s["relevance"], s["verdict"]) for s in data["skills"]] == [
            ("none", "review"), ("ok", "ok")]
        r = boost("decay")
        assert "commit-messages (project)" in r.out
        assert "brainstorming (project)" not in r.out
        assert "0 decay candidates · 1 to review · 1 ok" in r.out

    def test_project_row_is_read_from_the_repo_copy(self, boost, tapped,
                                                    repo):
        # The repo's `.git` gives the stack keywords git/commit/workflow. The
        # name alone matches `commit` (low); only the `git` tag in the copy's
        # frontmatter lifts it to ok — and there is no store copy to read, so
        # an ok proves the row was read from the repo.
        boost("install", "--local", "commit-messages")
        row = json.loads(boost("decay", "--json").out)["skills"][0]
        assert (row["name"], row["scope"], row["relevance"]) == (
            "commit-messages", "project", "ok")
