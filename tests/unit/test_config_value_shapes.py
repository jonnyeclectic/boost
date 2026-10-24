# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit: hand-edited config.json values of the wrong JSON type.

A tap row whose ``name`` was a number reached ``registry.safe_name``, one
whose ``url`` was null reached the ``update`` pool worker, and an ``agents``
section that was a string reached ``agents.known_agents`` — each an
AttributeError at exit 70 from taps, search, info, update, doctor and install.
``config._read`` now leaves such values out of the merged view with one
warning each, doctor counts them, and every writer still writes them back,
because writers read the raw file (:func:`config.mutate`).
"""
from __future__ import annotations

import json
import shutil

import pytest

from boost_cli.commands import quality
from boost_cli.core import agents, config, paths, registry
from boost_cli.errors import BoostError


@pytest.fixture()
def fresh(sandbox, monkeypatch):
    monkeypatch.setattr(config, "_WARNED_SHAPE", set())
    return sandbox


def _write(data) -> str:
    paths.ensure_dirs()
    text = json.dumps(data)
    paths.config_path().write_text(text, encoding="utf-8")
    return text


GOOD = {"name": "a/b", "url": "https://github.com/a/b"}


def _cfg() -> str:
    return paths.tilde(paths.config_path())


class TestSanitize:
    @pytest.mark.parametrize("row,why", [
        ({"name": 7, "url": "u"},
         '"name" is 7 (a number), not a non-empty string'),
        ({"name": "", "url": "u"},
         '"name" is "" (a string), not a non-empty string'),
        ({"name": None, "url": "u"},
         '"name" is null, not a non-empty string'),
        ({"url": "u"}, 'has no "name"'),
        ({"name": "x", "url": None}, '"url" is null, not a string'),
        ({"name": "x", "url": 3}, '"url" is 3 (a number), not a string'),
        ("a/b", 'is "a/b" (a string), not an object'),
        ([1], "is [1] (a list), not an object"),
        ({"name": {}, "url": "u"},
         '"name" is {} (an object), not a non-empty string'),
    ])
    def test_a_bad_tap_row_is_skipped_and_named(self, fresh, row, why):
        out, issues = config._sanitize({"taps": [GOOD, row, GOOD]})
        assert out == {"taps": [GOOD, GOOD]}
        assert issues == ["taps[1] %s, so boost skips that tap — repair or "
                          "remove the row in %s" % (why, _cfg())]

    def test_a_row_without_url_is_fine(self, fresh):
        assert config._sanitize({"taps": [{"name": "x"}]}) == (
            {"taps": [{"name": "x"}]}, [])

    @pytest.mark.parametrize("value,shown", [
        ("x", '"x" (a string)'), (None, "null"), ([], "[] (a list)"),
        (True, "true (a boolean)"), (1.5, "1.5 (a number)")])
    def test_a_non_object_agents_section_reads_the_defaults(
            self, fresh, value, shown):
        out, issues = config._sanitize({"agents": value, "x": 1})
        assert out == {"x": 1}
        assert issues == ["agents is %s, not an object, so boost reads the "
                          "default agents — `boost config unset agents` "
                          "restores them" % shown]

    def test_a_non_object_agent_row(self, fresh):
        spec = {"dir": "/abs/skills"}
        out, issues = config._sanitize({"agents": {
            "cursor": "x", "mine": 3, "ok": spec}})
        assert out == {"agents": {"ok": spec}}
        assert issues == [
            'agents.cursor is "x" (a string), not an object, so boost reads '
            "its default — `boost config unset agents.cursor` removes it",
            "agents.mine is 3 (a number), not an object, so boost skips that "
            "agent — `boost config unset agents.mine` removes it"]

    def test_a_clean_config_is_untouched(self, fresh):
        data = {"taps": [GOOD], "agents": {"cursor": {"enabled": False}},
                "serve": "off"}
        assert config._sanitize(data) == (data, [])
        assert config._sanitize({}) == ({}, [])


class TestRead:
    def test_load_skips_the_row_and_warns_once(self, fresh, capsys):
        _write({"taps": [GOOD, {"name": 7, "url": "u"}], "agents": "x"})
        cfg = config.load()
        assert cfg["taps"] == [GOOD]
        assert cfg["agents"] == config.DEFAULTS["agents"]
        err = " ".join(capsys.readouterr().err.split())
        assert err.count("! config.json:") == 2
        assert ('config.json: taps[1] "name" is 7 (a number), not a '
                "non-empty string, so boost skips that tap — repair or remove "
                "the row in %s" % _cfg()) in err
        assert "`boost config unset agents` restores them" in err
        # a write changes the stat stamp; the re-read must not repeat it
        config.set_value("ai.enabled", "false")
        config.load()
        assert capsys.readouterr().err == ""

    def test_shape_issues_is_silent_and_matches(self, fresh, capsys):
        _write({"taps": [{"url": "u"}]})
        assert config.shape_issues() == [
            'taps[0] has no "name", so boost skips that tap — repair or '
            "remove the row in %s" % _cfg()]
        assert capsys.readouterr().err == ""

    def test_shape_issues_is_empty_without_a_file(self, fresh):
        assert config.shape_issues() == []

    def test_a_corrupt_file_has_no_shape_issues(self, fresh):
        paths.ensure_dirs()
        paths.config_path().write_text("{nope", encoding="utf-8")
        assert config.shape_issues() == []


class TestSurvivesAWrite:
    def test_bad_values_are_written_back_verbatim(self, fresh, capsys):
        bad_tap = {"name": 7, "url": None, "pin": "abc"}
        _write({"taps": [GOOD, bad_tap], "agents": "x"})
        config.set_value("ai.enabled", "false")
        on_disk = json.loads(paths.config_path().read_text(encoding="utf-8"))
        assert on_disk == {"taps": [GOOD, bad_tap], "agents": "x",
                           "ai": {"enabled": False}}
        assert not paths.config_path().with_name(
            "config.json.corrupt").exists()
        assert config.check() is None

    def test_untap_keeps_the_bad_row(self, fresh, tmp_path, fixture_tap_src):
        dest = tmp_path / "t"
        shutil.copytree(fixture_tap_src, dest)
        tap = registry.add(str(dest))
        cfg = json.loads(paths.config_path().read_text(encoding="utf-8"))
        cfg["taps"].append({"name": 7})
        _write(cfg)
        registry.remove(tap.name)
        on_disk = json.loads(paths.config_path().read_text(encoding="utf-8"))
        assert on_disk["taps"] == [{"name": 7}]


class TestTapOverAMalformedRow:
    """`boost tap` never says "tapped" over a config that lists no usable row.

    The reader skipped a same-name ``"url": 123`` row while the writer counted
    it as taken: the new row was never written, the clone sat unlisted, and
    the next command said "no taps configured".
    """

    def test_the_new_row_takes_the_malformed_rows_place(
            self, fresh, tmp_path, fixture_tap_src, capsys):
        dest = tmp_path / "fixture-tap"
        shutil.copytree(fixture_tap_src, dest)
        bad = {"name": "fixture-tap", "url": 123}
        _write({"taps": [GOOD, bad, {"name": 7}]})
        tap = registry.add(str(dest))
        on_disk = json.loads(paths.config_path().read_text(encoding="utf-8"))
        rows = on_disk["taps"]
        assert rows[0] == GOOD
        assert (rows[1]["name"], rows[1]["url"]) == ("fixture-tap",
                                                     tap.url)
        # A malformed row of another name is left exactly as it was.
        assert rows[2:] == [{"name": 7}]
        assert [t.name for t in registry.list_taps()] == ["a/b",
                                                          "fixture-tap"]
        # The read before the write already said boost skips that row.
        assert ('taps[1] "url" is 123 (a number), not a string, so boost '
                "skips that tap" in " ".join(capsys.readouterr().err.split()))

    def test_a_row_with_no_url_is_named_not_left_blank(
            self, fresh, tmp_path, fixture_tap_src):
        dest = tmp_path / "fixture-tap"
        shutil.copytree(fixture_tap_src, dest)
        _write({"taps": [{"name": "fixture-tap"}]})
        with pytest.raises(BoostError) as ei:
            registry.add(str(dest))
        assert ei.value.message == ("tap name fixture-tap is already used by "
                                    "a config.json row with no url")
        on_disk = json.loads(paths.config_path().read_text(encoding="utf-8"))
        assert on_disk == {"taps": [{"name": "fixture-tap"}]}

    def test_a_real_url_is_still_named(self):
        assert registry._taken("x", "u", "/a/x").message == \
            "tap name x is already used by /a/x"


class TestTheRemedyWorks:
    def test_unset_agents_clears_the_issue(self, fresh):
        _write({"agents": "x"})
        assert config.unset("agents") is True
        assert config.shape_issues() == []
        assert config.check() is None

    def test_unset_one_agent_clears_the_issue(self, fresh):
        _write({"agents": {"cursor": "x"}})
        assert config.unset("agents.cursor") is True
        assert config.shape_issues() == []


class TestReaders:
    def test_list_taps_and_agents_do_not_raise(self, fresh):
        _write({"taps": [GOOD, {"name": 7, "url": "u"},
                         {"name": "x", "url": None}],
                "agents": {"cursor": "x"}})
        assert [t.name for t in registry.list_taps()] == ["a/b"]
        assert agents.check() == []
        assert "cursor" in agents.known_agents()

    def test_a_string_agents_section_reads_every_default(self, fresh):
        _write({"agents": "x"})
        assert set(agents.known_agents()) == set(config.DEFAULTS["agents"])


class TestCli:
    def test_taps_search_info_exit_cleanly(self, fresh, boost, tmp_path,
                                            fixture_tap_src):
        dest = tmp_path / "t"
        shutil.copytree(fixture_tap_src, dest)
        registry.add(str(dest))
        cfg = json.loads(paths.config_path().read_text(encoding="utf-8"))
        cfg["taps"] += [{"name": 7, "url": "u"}, {"name": "x", "url": None}]
        cfg["agents"] = "x"
        _write(cfg)
        res = boost("taps")
        assert "1 tap" in res.out and "5 items" in res.out
        boost("search", "brainstorming")
        boost("info", "brainstorming")
        boost("update")
        boost("install", "brainstorming")

    def test_doctor_counts_each_one_as_an_issue(self, fresh, capsys):
        _write({"taps": [{"name": 7}], "agents": "x"})
        rc = quality.cmd_doctor(["--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 1
        msgs = [c["message"] for c in payload["checks"]
                if c["name"] == "config" and c["status"] == "issue"]
        assert msgs == config.shape_issues()
        assert len(msgs) == 2
