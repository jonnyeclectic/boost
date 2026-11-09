# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""core/skillssh.py: the opt-in skills.sh source for `boost search`.

The payload shape is the one `GET https://skills.sh/api/search` returned on
2026-11-08 (100 rows for "pr review"); the rows here are trimmed copies.
"""
from __future__ import annotations

import io
import json
from typing import ClassVar

import pytest

from boost_cli.core import config, skillssh

ROW = {"id": "warpdotdev/common-skills/review-pr",
       "source": "warpdotdev/common-skills", "skillId": "review-pr",
       "name": "review-pr", "installs": 29090}


@pytest.fixture
def quiet_env(monkeypatch):
    for var in ("BOOST_NO_NET", "BOOST_SKILLS_SH"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(config, "get",
                        lambda key, default=None: default)
    return monkeypatch


class TestEnabled:
    def test_off_by_default(self, quiet_env):
        assert skillssh.enabled() is False

    def test_the_flag_turns_it_on(self, quiet_env):
        assert skillssh.enabled(force=True) is True

    def test_the_env_turns_it_on(self, quiet_env):
        quiet_env.setenv("BOOST_SKILLS_SH", "1")
        assert skillssh.enabled() is True

    def test_an_unreadable_env_value_does_not(self, quiet_env, capsys):
        quiet_env.setenv("BOOST_SKILLS_SH", "maybe")
        assert skillssh.enabled() is False

    def test_the_config_key_turns_it_on(self, quiet_env):
        quiet_env.setattr(config, "get", lambda key, default=None:
                          True if key == "skills_sh.enabled" else default)
        assert skillssh.enabled() is True

    @pytest.mark.parametrize("value", ["no", "false", "true", 1, "1"])
    def test_only_a_real_true_in_config_turns_it_on(self, quiet_env, value):
        # A hand-edited string is not a boolean; this switch sends data.
        quiet_env.setattr(config, "get", lambda key, default=None:
                          value if key == "skills_sh.enabled" else default)
        assert skillssh.enabled() is False

    def test_no_net_beats_the_flag(self, quiet_env):
        quiet_env.setenv("BOOST_NO_NET", "1")
        assert skillssh.enabled(force=True) is False

    def test_the_default_is_written_down_as_off(self):
        assert config.DEFAULTS["skills_sh"] == {"enabled": False}


class TestParse:
    def test_a_real_row(self):
        assert skillssh.parse({"skills": [ROW]}) == [
            {"source": "warpdotdev/common-skills", "name": "review-pr",
             "installs": 29090}]

    def test_skill_id_wins_over_name(self):
        row = dict(ROW, skillId="review-pr", name="Review PR!")
        assert skillssh.parse({"skills": [row]})[0]["name"] == "review-pr"

    def test_name_is_the_fallback(self):
        row = dict(ROW, skillId="", name="review-pr")
        assert skillssh.parse({"skills": [row]})[0]["name"] == "review-pr"

    @pytest.mark.parametrize("source", [
        "", "warpdotdev", "a/b/c", "https://evil.example/x",
        "own er/repo", "-owner/repo", "owner/re po"])
    def test_a_source_boost_could_not_tap_is_dropped(self, source):
        assert skillssh.parse({"skills": [dict(ROW, source=source)]}) == []

    def test_control_characters_are_stripped(self):
        row = dict(ROW, source="warpdotdev/common-skills\x1b",
                   skillId="review-pr\x07")
        hit = skillssh.parse({"skills": [row]})[0]
        assert hit["source"] == "warpdotdev/common-skills"
        assert hit["name"] == "review-pr"

    def test_a_name_with_spaces_is_dropped(self):
        assert skillssh.parse({"skills": [dict(ROW, skillId="rm -rf")]}) == []

    @pytest.mark.parametrize("installs", [-1, "29090", 1.5, True, None])
    def test_an_install_count_that_is_not_a_count_reads_unknown(self, installs):
        hit = skillssh.parse({"skills": [dict(ROW, installs=installs)]})[0]
        assert hit["installs"] is None

    def test_zero_installs_is_a_count(self):
        assert skillssh.parse(
            {"skills": [dict(ROW, installs=0)]})[0]["installs"] == 0

    def test_non_dict_rows_are_skipped(self):
        assert len(skillssh.parse({"skills": ["x", 3, None, ROW]})) == 1

    @pytest.mark.parametrize("payload", [[], {"skills": None}, {}, "x"])
    def test_a_changed_shape_is_an_error(self, payload):
        with pytest.raises(ValueError):
            skillssh.parse(payload)


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestSearch:
    def test_it_asks_the_find_endpoint(self, monkeypatch):
        seen = {}

        def fake(req, timeout):
            seen["url"], seen["timeout"] = req.full_url, timeout
            seen["accept"] = req.get_header("Accept")
            return _Resp(json.dumps({"skills": [ROW]}).encode())
        monkeypatch.setattr(skillssh.nethttp, "urlopen", fake)
        hits, err = skillssh.search("pr review", owner="warpdotdev")
        assert err is None
        assert hits[0]["source"] == "warpdotdev/common-skills"
        assert seen["url"] == ("https://skills.sh/api/search?"
                               "q=pr+review&owner=warpdotdev")
        assert seen["timeout"] == 5.0
        assert seen["accept"] == "application/json"

    def test_no_owner_sends_no_owner(self, monkeypatch):
        seen = {}

        def fake(req, timeout):
            seen["url"] = req.full_url
            return _Resp(b'{"skills": []}')
        monkeypatch.setattr(skillssh.nethttp, "urlopen", fake)
        assert skillssh.search("x") == ([], None)
        assert seen["url"] == "https://skills.sh/api/search?q=x"

    def test_a_network_failure_is_a_reason_not_a_raise(self, monkeypatch):
        def boom(req, timeout):
            raise OSError("connection refused")
        monkeypatch.setattr(skillssh.nethttp, "urlopen", boom)
        hits, err = skillssh.search("x")
        assert hits == []
        assert err == "skills.sh did not answer (connection refused)"

    def test_a_messageless_failure_names_its_type(self, monkeypatch):
        def boom(req, timeout):
            raise TimeoutError()
        monkeypatch.setattr(skillssh.nethttp, "urlopen", boom)
        assert skillssh.search("x")[1] == "skills.sh did not answer (TimeoutError)"

    def test_bad_json_is_a_reason(self, monkeypatch):
        monkeypatch.setattr(skillssh.nethttp, "urlopen",
                            lambda req, timeout: _Resp(b"<html>"))
        hits, err = skillssh.search("x")
        assert hits == [] and err.startswith("skills.sh did not answer (")

    def test_a_long_reason_is_cut(self, monkeypatch):
        def boom(req, timeout):
            raise OSError("y" * 500)
        monkeypatch.setattr(skillssh.nethttp, "urlopen", boom)
        assert len(skillssh.search("x")[1]) == len(
            "skills.sh did not answer ()") + 120


class TestRendering:
    HIT: ClassVar[dict] = {"source": "warpdotdev/common-skills", "name": "review-pr",
           "installs": 29090}

    LOCAL: ClassVar[dict] = {"warpdotdev/common-skills": {"review-pr"}}

    def test_state_tapped(self):
        assert skillssh.state(self.HIT, self.LOCAL) == "tapped"

    def test_state_ignores_repo_case(self):
        hit = dict(self.HIT, source="WarpDotDev/Common-Skills")
        assert skillssh.state(hit, self.LOCAL) == "tapped"

    def test_state_untapped(self):
        assert skillssh.state(dict(self.HIT, source="a/b"), self.LOCAL) == \
            "untapped"

    def test_state_tapped_but_not_in_the_local_copy(self):
        hit = dict(self.HIT, name="brand-new")
        assert skillssh.state(hit, self.LOCAL) == "not-in-copy"

    def test_state_an_empty_tap_is_still_tapped(self):
        assert skillssh.state(self.HIT, {"warpdotdev/common-skills": set()}) \
            == "not-in-copy"

    def test_tapped_hint_reads_then_installs(self):
        assert skillssh.install_hint(self.HIT, "tapped") == (
            "boost cat warpdotdev/common-skills:review-pr, then "
            "boost install warpdotdev/common-skills:review-pr")

    def test_untapped_hint_taps_then_reads(self):
        assert skillssh.install_hint(self.HIT, "untapped") == (
            "boost tap warpdotdev/common-skills, then "
            "boost cat warpdotdev/common-skills:review-pr")

    def test_stale_copy_hint_updates_then_reads(self):
        assert skillssh.install_hint(self.HIT, "not-in-copy") == (
            "boost update warpdotdev/common-skills, then "
            "boost cat warpdotdev/common-skills:review-pr — your copy of "
            "the tap predates it")

    def test_hit_line(self):
        assert skillssh.hit_line(self.HIT, "untapped") == (
            "review-pr  warpdotdev/common-skills  (29,090 installs) — "
            "`boost tap warpdotdev/common-skills, then "
            "boost cat warpdotdev/common-skills:review-pr`")

    def test_hit_line_unknown_count(self):
        assert "(installs unknown)" in skillssh.hit_line(
            dict(self.HIT, installs=None), "tapped")

    def test_hit_line_zero_is_a_count(self):
        assert "(0 installs)" in skillssh.hit_line(
            dict(self.HIT, installs=0), "tapped")


class TestSection:
    HIT = TestRendering.HIT

    def test_off_means_nothing_and_no_request(self, quiet_env):
        def fetch(q, o):
            raise AssertionError("asked skills.sh while it was off")
        assert skillssh.section("x", fetch=fetch) == []

    def test_on_lists_hits_marking_what_is_tapped(self, quiet_env):
        asked = []
        quiet_env.setattr(skillssh, "local_names", lambda sources: (
            asked.append(sources) or
            {"warpdotdev/common-skills": {"review-pr"}}))
        hits = [self.HIT, dict(self.HIT, source="a/b", name="z")]
        lines = skillssh.section("pr review", force=True,
                                 fetch=lambda q, o: (hits, None))
        assert lines[0].startswith("On skills.sh (")
        assert "read one before installing it" in lines[0]
        assert lines[1] == "  " + skillssh.hit_line(self.HIT, "tapped")
        assert lines[2] == "  " + skillssh.hit_line(hits[1], "untapped")
        assert len(lines) == 3
        assert asked == [{"warpdotdev/common-skills", "a/b"}]

    def test_it_shows_at_most_show(self, quiet_env):
        quiet_env.setattr(skillssh, "local_names", lambda sources: {})
        hits = [dict(self.HIT, name="s%d" % i) for i in range(9)]
        lines = skillssh.section("x", force=True,
                                 fetch=lambda q, o: (hits, None))
        assert len(lines) == 1 + 5
        lines = skillssh.section("x", force=True, show=2,
                                 fetch=lambda q, o: (hits, None))
        assert len(lines) == 3

    def test_the_query_and_owner_reach_the_fetch(self, quiet_env):
        seen = []
        skillssh.section("pr review", force=True, owner="o",
                         fetch=lambda q, o: (seen.append((q, o)) or ([], None)))
        assert seen == [("pr review", "o")]

    def test_a_failure_is_one_line(self, quiet_env):
        assert skillssh.section("x", force=True,
                                fetch=lambda q, o: ([], "it broke")) == [
            "skills.sh: it broke"]

    def test_no_hits_is_said(self, quiet_env):
        assert skillssh.section("x y", force=True,
                                fetch=lambda q, o: ([], None)) == [
            "skills.sh: no matches for 'x y'"]

    def test_local_names_survives_a_broken_registry(self, monkeypatch):
        from boost_cli.core import registry

        def boom():
            raise RuntimeError("config unreadable")
        monkeypatch.setattr(registry, "list_taps", boom)
        assert skillssh.local_names({"a/b"}) == {}

    def test_local_names_loads_only_the_named_taps(self, monkeypatch):
        from boost_cli.core import catalog, registry

        class T:
            def __init__(self, name):
                self.name = name
        loaded = []
        monkeypatch.setattr(registry, "list_taps",
                            lambda: [T("Owner/Repo"), T("other/repo")])
        monkeypatch.setattr(catalog, "load_tap", lambda tap: (
            loaded.append(tap.name) or [{"name": "x"}, {"name": None}]))
        assert skillssh.local_names({"owner/REPO"}) == {"owner/repo": {"x", ""}}
        assert loaded == ["Owner/Repo"]


class TestWiredIn:
    """`boost search` and `boost_search` print the block, and only when on."""

    HIT: ClassVar[dict] = {"source": "warpdotdev/common-skills", "name": "review-pr",
           "installs": 29090}

    @pytest.fixture
    def asked(self, tapped, monkeypatch):
        monkeypatch.delenv("BOOST_SKILLS_SH", raising=False)
        monkeypatch.delenv("BOOST_NO_NET", raising=False)
        calls = []
        monkeypatch.setattr(skillssh, "search", lambda q, o=None: (
            calls.append(q) or ([self.HIT], None)))
        return calls

    def test_cli_off_by_default(self, asked, capsys):
        from boost_cli.commands import discovery
        assert discovery.cmd_search(["jira"]) == 0
        assert asked == []
        assert "skills.sh" not in capsys.readouterr().out

    def test_cli_flag_adds_the_block(self, asked, capsys):
        from boost_cli.commands import discovery
        assert discovery.cmd_search(["jira", "--skills-sh"]) == 0
        text = capsys.readouterr().out
        assert asked == ["jira"]
        assert "jira-integration" in text           # local rows still lead
        assert text.index("jira-integration") < text.index("On skills.sh")
        assert "review-pr  warpdotdev/common-skills  (29,090 installs)" in text

    def test_cli_block_also_follows_no_matches(self, asked, capsys):
        from boost_cli.commands import discovery
        assert discovery.cmd_search(["zzqx", "--skills-sh"]) == 0
        text = capsys.readouterr().out
        assert "no matches for 'zzqx'" in text and "On skills.sh" in text

    def test_cli_json_is_unchanged(self, asked, capsys):
        from boost_cli.commands import discovery
        assert discovery.cmd_search(["jira", "--skills-sh", "--json"]) == 0
        assert isinstance(json.loads(capsys.readouterr().out), list)
        assert asked == []

    def test_mcp_needs_it_turned_on(self, asked, monkeypatch):
        from boost_cli.commands import configuration
        text, err = configuration._tool_search({"query": "jira"})
        assert not err and "skills.sh" not in text and asked == []
        monkeypatch.setenv("BOOST_SKILLS_SH", "1")
        text, err = configuration._tool_search({"query": "jira"})
        assert not err and asked == ["jira"]
        assert text.index("jira-integration") < text.index("On skills.sh")

    def test_mcp_block_follows_an_empty_reply(self, asked, monkeypatch):
        from boost_cli.commands import configuration
        monkeypatch.setenv("BOOST_SKILLS_SH", "1")
        text, err = configuration._tool_search({"query": "zzqx"})
        assert not err and "On skills.sh" in text
        assert "review-pr  warpdotdev/common-skills" in text

    def test_cli_json_says_the_flag_was_ignored(self, asked, capsys):
        from boost_cli.commands import discovery
        assert discovery.cmd_search(["jira", "--skills-sh", "--json"]) == 0
        assert "--skills-sh is ignored with --json" in capsys.readouterr().err

    def test_a_tapped_hit_reads_from_the_real_catalogue(self, asked,
                                                         monkeypatch):
        # The fixture tap is real: its name and its items come from disk.
        from boost_cli.core import registry
        tap = registry.list_taps()[0]
        monkeypatch.setattr(skillssh, "search", lambda q, o=None: ([
            {"source": tap.name, "name": "jira-integration", "installs": 3},
            {"source": tap.name, "name": "not-there", "installs": 1}], None))
        lines = skillssh.section("jira", force=True)
        assert ("boost cat %s:jira-integration, then boost install"
                % tap.name) in lines[1]
        assert "boost update %s" % tap.name in lines[2]
