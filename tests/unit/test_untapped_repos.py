# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""registry.untapped_repos: discovery rows minus repositories already tapped.

`boost discover` and the MCP `boost_discover_github` tool promise repos
nobody here has tapped, and listed tapped ones. Matching is by normalized
source URL, never by tap name.
"""
from __future__ import annotations

from boost_cli.core import config, registry


def _taps(*rows):
    config.save({"taps": [{"name": n, "url": u} for n, u in rows]})


class TestUntappedRepos:
    def test_no_taps_keeps_every_row(self, sandbox):
        _taps()
        rows = [{"repo": "a/b"}, {"repo": "c/d"}]
        assert registry.untapped_repos(rows) == (rows, 0)

    def test_a_tapped_repo_is_dropped_and_counted_once(self, sandbox):
        _taps(("skills", "https://github.com/anthropics/skills"))
        rows = [{"repo": "anthropics/skills", "path": "a"},
                {"repo": "someone/other", "path": "b"},
                {"repo": "anthropics/skills", "path": "c"}]
        assert registry.untapped_repos(rows) == (
            [{"repo": "someone/other", "path": "b"}], 1)

    def test_spellings_of_one_github_repo_match(self, sandbox):
        _taps(("a", "git@github.com:Anthropics/Skills.git"),
              ("b", "https://github.com/octo/pack/"))
        rows = [{"repo": "anthropics/SKILLS"}, {"repo": "Octo/Pack"},
                {"repo": "octo/pack2"}]
        assert registry.untapped_repos(rows) == ([{"repo": "octo/pack2"}], 2)

    def test_a_tap_name_alone_is_not_the_repo(self, sandbox, tmp_path):
        # A local tap called `skills`, and a GitLab `owner/repo`, are not
        # the GitHub repository of the same tail.
        _taps(("skills", str(tmp_path / "skills")),
              ("x/y", "https://gitlab.com/x/y"))
        rows = [{"repo": "anthropics/skills"}, {"repo": "x/y"}]
        assert registry.untapped_repos(rows) == (rows, 0)

    def test_a_row_without_a_repo_is_kept(self, sandbox):
        _taps(("skills", "https://github.com/anthropics/skills"))
        assert registry.untapped_repos([{"path": "p"}]) == ([{"path": "p"}], 0)

    def test_tapped_source_keys(self, sandbox):
        _taps(("a", "https://github.com/Anthropics/Skills.git"),
              ("b", "https://gitlab.com/Team/Repo"))
        assert registry.tapped_source_keys() == {
            "github.com/anthropics/skills", "gitlab.com/Team/Repo"}
