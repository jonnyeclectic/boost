# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost search --tap / --owner`: narrow a search to one source.

`npx skills find` takes an owner; boost could only filter by category, so
"what does anthropics ship for PDFs" meant reading the TAP column by eye.
"""
from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from boost_cli.commands import discovery
from boost_cli.core import catalog, registry, skillssh


def _make_tap(root):
    """A second tap whose `python-style` also answers 'commit'."""
    for name, desc in (("react-patterns", "Component patterns for React"),
                       ("python-style", "Commit formatting for Python")):
        d = root / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: %s\ndescription: %s\nversion: 1.0.0\n---\n\n"
            "# %s\n\nBody text.\n" % (name, desc, name), encoding="utf-8")
    for argv in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "skills"]):
        subprocess.run(["git", "-c", "user.email=t@t.test", "-c",
                        "user.name=t", *argv], cwd=root, check=True,
                       capture_output=True)
    return root


@pytest.fixture()
def two_taps(boost, tapped, tmp_path):
    """The fixture tap plus `extra-tap`, which also answers 'commit'."""
    boost("tap", _make_tap(tmp_path / "extra-tap"))
    return {t.name for t in registry.list_taps()}


def _names(r):
    return [e["name"] for e in json.loads(r.out)]


def _taps(r):
    return {e["tap"] for e in json.loads(r.out)}


class TestTapFilter:
    def test_it_keeps_only_that_taps_rows(self, boost, two_taps):
        assert len(two_taps) == 2
        everything = boost("search", "commit", "--json")
        assert len(_taps(everything)) == 2
        r = boost("search", "commit", "--tap", "extra-tap", "--json")
        assert _names(r) == ["python-style"]

    def test_the_tap_is_matched_like_a_tap_qualifier(self, boost, two_taps):
        r = boost("search", "commit", "--tap", "EXTRA-TAP", "--json")
        assert _taps(r) == {"extra-tap"}

    def test_an_unknown_tap_is_an_error_not_an_empty_list(self, boost,
                                                          two_taps):
        r = boost("search", "patterns", "--tap", "nope/nothing", expect=1)
        assert "no tap named 'nope/nothing' is configured" in r.err
        assert "`boost taps` lists them" in r.err

    def test_a_filter_that_empties_the_list_names_itself(self, boost,
                                                         two_taps):
        r = boost("search", "jira", "--tap", "extra-tap")
        assert ("○ no matches for 'jira' from tap 'extra-tap'"
                in r.out)
        assert "drop --tap" in r.out
        assert "boost browse --categories" not in r.out
        assert "boost discover" not in r.out

    def test_it_composes_with_category(self, boost, two_taps):
        r = boost("search", "workflow", "--category", "testing",
                  "--tap", "extra-tap")
        assert ("no matches for 'workflow' in category 'testing' from tap "
                "'extra-tap'" in r.out)
        assert "drop --category or --tap" in r.out


class TestOwnerFilter:
    def test_a_local_tap_has_no_owner(self, boost, tapped):
        r = boost("search", "commit", "--owner", "acme", expect=1)
        assert "no configured tap is owned by 'acme'" in r.err


class TestOwnerMatches:
    @pytest.mark.parametrize("tap, owner", [
        ("anthropics/skills", "anthropics"),
        ("Anthropics/skills", "anthropics"),
        ("anthropics/skills", "ANTHROPICS")])
    def test_the_owner_half_case_folded(self, tap, owner):
        assert catalog.owner_matches(tap, owner) is True

    @pytest.mark.parametrize("tap, owner", [
        ("anthropics/skills", "anthropic"),
        ("anthropics/skills", "skills"),
        ("local-tap", "local-tap"),
        ("", "x"),
        ("a/b", "")])
    def test_anything_else(self, tap, owner):
        assert catalog.owner_matches(tap, owner) is False


def _args(**kw):
    base = {"category": None, "tap": None, "owner": None, "skills_sh": True}
    return SimpleNamespace(**(base | kw))


_ROWS = ({"tap": "acme/one"}, {"tap": "acme/two"}, {"tap": "zed/one"},
         {"tap": "local"})


class TestSearchFilter:

    def _kept(self, **kw):
        keep = discovery._search_filter(_args(**kw))
        return [r["tap"] for r in _ROWS if keep(r)]

    def test_no_filter_is_none(self):
        assert discovery._search_filter(_args()) is None

    def test_owner(self):
        assert self._kept(owner="acme") == ["acme/one", "acme/two"]

    def test_tap(self):
        assert self._kept(tap="zed/one") == ["zed/one"]

    def test_both_must_hold(self):
        assert self._kept(owner="acme", tap="one") == ["acme/one"]

    def test_words_and_flags(self):
        a = _args(category="ai", tap="x/y", owner="x")
        assert discovery._filter_words(a) == (
            "in category 'ai' from tap 'x/y' by owner 'x'")
        assert discovery._filter_flags(a) == "--category or --tap or --owner"


class TestSkillsShNarrowing:
    """skills.sh takes `owner`; `tap` is narrowed by source afterwards."""

    hits = ({"source": "acme/one", "name": "a", "installs": 3},
            {"source": "acme/two", "name": "b", "installs": 2},
            {"source": "zed/one", "name": "c", "installs": 1})

    def _run(self, monkeypatch, **kw):
        seen = {}

        def fetch(query, owner):
            seen["owner"] = owner
            return list(self.hits), None
        monkeypatch.setattr(skillssh, "local_names", lambda sources: {})
        lines = skillssh.section("q", force=True, fetch=fetch, **kw)
        shown = [h["source"] for h in self.hits
                 if any(" %s " % h["source"] in ln for ln in lines)]
        return seen["owner"], shown

    def test_owner_is_sent_to_the_api(self, monkeypatch):
        owner, shown = self._run(monkeypatch, owner="acme")
        assert owner == "acme"
        assert shown == ["acme/one", "acme/two"]

    def test_a_tap_sends_its_owner_and_keeps_only_that_repo(
            self, monkeypatch):
        owner, shown = self._run(monkeypatch, tap="acme/one")
        assert owner == "acme"
        assert shown == ["acme/one"]

    def test_a_bare_repo_tap_sends_no_owner(self, monkeypatch):
        owner, shown = self._run(monkeypatch, tap="one")
        assert owner is None
        assert shown == ["acme/one", "zed/one"]

    def test_unfiltered_shows_everything(self, monkeypatch):
        owner, shown = self._run(monkeypatch)
        assert owner is None and len(shown) == 3

    def test_nothing_left_after_narrowing(self, monkeypatch):
        monkeypatch.setattr(skillssh, "local_names", lambda sources: {})
        lines = skillssh.section(
            "q", force=True, tap="x/y",
            fetch=lambda q, o: ([{"source": "a/b", "name": "x",
                                  "installs": 1}], None))
        assert lines == ["skills.sh: no matches for 'q'"]

    @pytest.mark.parametrize("tap, owner, want", [
        (None, None, None), ("a/b", None, "a"), ("b", None, None),
        ("a/b", "z", "z"), (None, "z", "z")])
    def test_request_owner(self, tap, owner, want):
        assert skillssh.request_owner(tap, owner) == want


class TestSourceFilterCore:
    def test_none_without_a_filter(self):
        assert catalog.source_filter() is None

    def test_unmatched_source(self):
        names = ["acme/one", "local"]
        assert catalog.unmatched_source(None, None, names) is None
        assert catalog.unmatched_source("one", None, names) is None
        assert catalog.unmatched_source(None, "ACME", names) is None
        assert catalog.unmatched_source("two", None, names) == (
            "no tap named 'two' is configured")
        assert catalog.unmatched_source(None, "zed", names) == (
            "no configured tap is owned by 'zed'")
        assert catalog.unmatched_source("one", "zed", names) == (
            "no configured tap is owned by 'zed'")


class TestMcpSearch:
    def _call(self, **args):
        from boost_cli.commands import configuration
        return configuration._tool_search(args)

    def test_tap_narrows_the_corpus(self, two_taps):
        text, err = self._call(query="commit", tap="extra-tap")
        assert err is False
        assert "python-style" in text
        assert "commit-messages" not in text

    def test_unfiltered_sees_both(self, two_taps):
        text, _err = self._call(query="commit")
        assert "python-style" in text and "commit-messages" in text

    def test_an_unknown_tap_is_an_error(self, two_taps):
        text, err = self._call(query="commit", tap="nope")
        assert err is True
        assert text.startswith("no tap named 'nope' is configured")

    def test_owner_on_local_taps_is_an_error(self, two_taps):
        text, err = self._call(query="commit", owner="acme")
        assert err is True
        assert "no configured tap is owned by 'acme'" in text

    def test_the_schema_declares_both(self):
        from boost_cli.commands import configuration
        spec = next(s for s in configuration.REGISTRY.specs()
                    if s["name"] == "boost_search")
        props = spec["inputSchema"]["properties"]
        assert props["tap"]["type"] == props["owner"]["type"] == "string"
        assert spec["inputSchema"]["required"] == ["query"]
