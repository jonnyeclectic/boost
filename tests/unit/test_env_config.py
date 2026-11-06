# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boolean env switches, overrides-only config writes, and the
choice/range checks on ``logging.*`` and ``serve.port``.

Every switch used to be a bare ``os.environ.get(name)`` truthiness test, so
``BOOST_ASSUME_YES=0`` confirmed a delete unasked and ``BOOST_NO_AI=false``
switched AI off. ``config set`` wrote the whole of DEFAULTS to disk, so a
default a later release changed never reached anyone who had once run it.
"""
from __future__ import annotations

import json
import logging

import pytest

from boost_cli.core import ai, config, embed, logs, output, paths, selfupdate
from boost_cli.core import typedvalue as tv

ON = ["1", "true", "TRUE", "yes", "on", " On "]
OFF = ["", "0", "false", "False", "no", "off", " OFF "]


def _flat(text):
    """``text`` with the pane-width hint wrapping folded back to spaces."""
    return " ".join(text.split())


@pytest.fixture
def fresh_warnings(monkeypatch):
    monkeypatch.setattr(tv, "_env_warned", set())


class TestEnvFlag:
    @pytest.mark.parametrize("value", ON)
    def test_true_words_are_on(self, sandbox, monkeypatch, value):
        monkeypatch.setenv("BOOST_X", value)
        assert tv.env_flag("BOOST_X") is True

    @pytest.mark.parametrize("value", OFF)
    def test_false_words_and_empty_are_off_silently(
            self, sandbox, monkeypatch, capsys, fresh_warnings, value):
        monkeypatch.setenv("BOOST_X", value)
        assert tv.env_flag("BOOST_X") is False
        assert capsys.readouterr().err == ""

    def test_unset_is_off(self, sandbox, monkeypatch, capsys):
        monkeypatch.delenv("BOOST_X", raising=False)
        assert tv.env_flag("BOOST_X") is False
        assert capsys.readouterr().err == ""

    def test_an_unreadable_value_is_off_and_warns_once(
            self, sandbox, monkeypatch, capsys, fresh_warnings):
        monkeypatch.setenv("BOOST_X", "Sure")
        assert tv.env_flag("BOOST_X") is False
        assert tv.env_flag("BOOST_X") is False
        assert capsys.readouterr().err == (
            "! BOOST_X='Sure' is not a boolean (1/0, true/false, yes/no, "
            "on/off) — treating it as off\n")

    def test_a_kill_switch_reads_an_unreadable_value_as_on(
            self, sandbox, monkeypatch, capsys, fresh_warnings):
        monkeypatch.setenv("BOOST_X", "y")
        assert tv.env_flag("BOOST_X", unknown=True) is True
        assert tv.env_flag("BOOST_X", unknown=True) is True
        assert capsys.readouterr().err == (
            "! BOOST_X='y' is not a boolean (1/0, true/false, yes/no, "
            "on/off) — treating it as on\n")

    @pytest.mark.parametrize("value", OFF)
    def test_a_kill_switch_still_reads_off_words_as_off(
            self, sandbox, monkeypatch, value):
        monkeypatch.setenv("BOOST_X", value)
        assert tv.env_flag("BOOST_X", unknown=True) is False

    @pytest.mark.parametrize("value", ON)
    def test_a_kill_switch_reads_on_words_as_on(self, sandbox, monkeypatch,
                                                 capsys, value):
        monkeypatch.setenv("BOOST_X", value)
        assert tv.env_flag("BOOST_X", unknown=True) is True
        assert capsys.readouterr().err == ""


class TestKillSwitchesFailClosed:
    """An unreadable value on a ``BOOST_NO_*`` switch keeps it switched on:
    it used to, and reading ``BOOST_NO_NET=y`` as off would call out from a
    machine its owner had told to stay offline."""

    def test_no_net(self, sandbox, monkeypatch, fresh_warnings):
        monkeypatch.setenv("BOOST_NO_NET", "y")
        assert selfupdate.latest_version() is None

    def test_no_ai(self, sandbox, monkeypatch, fresh_warnings):
        monkeypatch.setenv("BOOST_NO_AI", "y")
        assert ai.enabled() is False
        assert ai.unavailable_reason() == "disabled (BOOST_NO_AI is set)"

    def test_no_embed(self, sandbox, monkeypatch, fresh_warnings):
        monkeypatch.setenv("BOOST_NO_EMBED", "y")
        assert embed.enabled() is False

    def test_no_log(self, sandbox, monkeypatch, fresh_warnings):
        monkeypatch.setenv("BOOST_NO_LOG", "y")
        assert logs._file_enabled() is False

    def test_no_seed(self, sandbox, monkeypatch, fresh_warnings):
        from boost_cli.core import bootstrap
        monkeypatch.setenv("BOOST_NO_SEED", "y")
        assert bootstrap.will_seed() is False
        assert bootstrap.seed_catalog().skipped is True

    def test_assume_yes_stays_off(self, sandbox, monkeypatch, fresh_warnings):
        monkeypatch.setattr("sys.argv", ["boost"])
        monkeypatch.setattr(output, "stdin_is_tty", lambda *a: False)
        monkeypatch.setenv("BOOST_ASSUME_YES", "y")
        assert output.confirm("delete?") is False


class TestEachSwitch:
    """The finding's sites, each read with ``0`` meaning off."""

    def test_assume_yes_zero_does_not_confirm(self, sandbox, monkeypatch,
                                              capsys):
        monkeypatch.setattr("sys.argv", ["boost"])
        monkeypatch.setattr(output, "stdin_is_tty", lambda *a: False)
        monkeypatch.setenv("BOOST_ASSUME_YES", "0")
        assert output.confirm("delete?") is False
        monkeypatch.setenv("BOOST_ASSUME_YES", "1")
        assert output.confirm("delete?") is True

    @pytest.mark.parametrize("value,enabled", [("0", True), ("false", True),
                                               ("1", False), ("yes", False)])
    def test_no_ai(self, sandbox, monkeypatch, value, enabled):
        monkeypatch.setenv("BOOST_NO_AI", value)
        assert ai.enabled() is enabled
        reason = ai.unavailable_reason()
        assert (reason == "disabled (BOOST_NO_AI is set)") is not enabled

    def test_debug_zero_keeps_the_console_quiet(self, sandbox, monkeypatch):
        monkeypatch.setenv("BOOST_DEBUG", "0")
        assert logs._console_level(False, False, False) is None
        monkeypatch.setenv("BOOST_DEBUG", "1")
        assert logs._console_level(False, False, False) == logging.DEBUG

    def test_debug_zero_is_not_debug(self, sandbox, monkeypatch):
        monkeypatch.setenv("BOOST_DEBUG", "0")
        logs.reset()
        logs.configure()
        assert logs.is_debug() is False
        logs.reset()
        monkeypatch.setenv("BOOST_DEBUG", "on")
        logs.configure()
        assert logs.is_debug() is True
        logs.reset()

    def test_no_log_zero_keeps_the_file(self, sandbox, monkeypatch):
        monkeypatch.setenv("BOOST_NO_LOG", "0")
        assert logs._file_enabled() is True
        monkeypatch.setenv("BOOST_NO_LOG", "1")
        assert logs._file_enabled() is False

    def test_clicolor_force_zero_does_not_paint_a_pipe(self, sandbox,
                                                       monkeypatch):
        for name in ("BOOST_COLOR", "NO_COLOR", "TERM", "COLORTERM"):
            monkeypatch.delenv(name, raising=False)

        class Pipe:
            def isatty(self):
                return False
        monkeypatch.setenv("CLICOLOR_FORCE", "0")
        assert output.use_color(Pipe()) is False
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        assert output.use_color(Pipe()) is True
        assert output.color_level(Pipe()) == 2

    def test_clicolor_force_zero_does_not_claim_truecolor(self, sandbox,
                                                          monkeypatch):
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("COLORTERM", raising=False)
        monkeypatch.setenv("BOOST_COLOR", "always")
        monkeypatch.setenv("CLICOLOR_FORCE", "0")
        assert output.color_level() == 1

    def test_no_embed_zero_leaves_embedding_on(self, sandbox, monkeypatch):
        monkeypatch.setenv("BOOST_NO_EMBED", "0")
        assert embed.enabled() is True
        monkeypatch.setenv("BOOST_NO_EMBED", "1")
        assert embed.enabled() is False

    def test_no_net_zero_still_asks_pypi(self, sandbox, monkeypatch):
        asked = []

        def fake(*a, **k):
            asked.append(a)
            raise OSError("offline")
        monkeypatch.setattr(selfupdate.nethttp, "urlopen", fake)
        monkeypatch.setenv("BOOST_NO_NET", "1")
        assert selfupdate.latest_version() is None
        assert asked == []
        monkeypatch.setenv("BOOST_NO_NET", "0")
        assert selfupdate.latest_version() is None
        assert len(asked) == 1


class TestOverridesOnly:
    def _disk(self):
        return json.loads(paths.config_path().read_text(encoding="utf-8"))

    def test_set_writes_only_the_key(self, sandbox):
        config.set_value("policy_enforce", "false")
        assert self._disk() == {"policy_enforce": False}
        config.set_value("ai.model", "m")
        assert self._disk() == {"policy_enforce": False, "ai": {"model": "m"}}

    def test_a_changed_default_reaches_a_user_who_set_something(
            self, sandbox, monkeypatch):
        config.set_value("policy_enforce", "false")
        monkeypatch.setitem(config.DEFAULTS["ai"], "model", "NEW-DEFAULT")
        monkeypatch.setattr(config, "_cache", None)
        assert config.get("ai.model") == "NEW-DEFAULT"
        assert config.get("policy_enforce") is False

    def test_mutate_hands_the_writer_the_raw_overrides(self, sandbox):
        seen = []
        assert config.mutate(lambda cfg: seen.append(dict(cfg))) is True
        assert seen == [{}]
        assert self._disk() == {}

    def test_an_old_full_file_still_reads_and_is_not_trimmed(self, sandbox):
        paths.config_path().parent.mkdir(parents=True, exist_ok=True)
        full = json.loads(json.dumps(config.DEFAULTS))
        full["ai"]["model"] = "old-model"
        paths.config_path().write_text(json.dumps(full), encoding="utf-8")
        assert config.get("ai.model") == "old-model"
        config.set_value("policy_enforce", "false")
        disk = self._disk()
        assert disk["ai"]["model"] == "old-model"
        assert disk["policy_enforce"] is False

    def test_a_defaulted_scalar_is_not_turned_into_a_section(self, sandbox):
        with pytest.raises(TypeError, match="'port' is not a section"):
            config.set_value("serve.port.x", "1")
        assert not paths.config_path().exists()
        assert config.get("serve.port") == 8787

    def test_a_stored_scalar_is_not_turned_into_a_section(self, sandbox):
        config.set_value("custom", "5")
        with pytest.raises(TypeError, match="'custom' is not a section"):
            config.set_value("custom.x", "1")
        assert self._disk() == {"custom": 5}


class TestChoicesAndRanges:
    @pytest.mark.parametrize("raw,stored", [("debug", "DEBUG"), ("OFF", "OFF"),
                                            (" Critical ", "CRITICAL")])
    def test_level_takes_a_known_name_in_canonical_case(self, sandbox, raw,
                                                        stored):
        config.set_value("logging.level", raw)
        assert config.get("logging.level") == stored

    def test_level_refuses_anything_else(self, sandbox):
        with pytest.raises(tv.ValueTypeError) as e:
            config.set_value("logging.level", "verbose")
        assert e.value.expected == ("one of OFF, DEBUG, INFO, WARNING, "
                                    "ERROR, CRITICAL")
        assert e.value.raw == "verbose"
        assert not paths.config_path().exists()

    def test_format(self, sandbox):
        config.set_value("logging.format", "JSON")
        assert config.get("logging.format") == "json"
        with pytest.raises(tv.ValueTypeError) as e:
            config.set_value("logging.format", "yaml")
        assert e.value.expected == "one of text, json"

    @pytest.mark.parametrize("raw", ["0", "65535", "8080"])
    def test_port_in_range(self, sandbox, raw):
        config.set_value("serve.port", raw)
        assert config.get("serve.port") == int(raw)

    @pytest.mark.parametrize("raw", ["-1", "-3", "65536", "99999"])
    def test_port_out_of_range(self, sandbox, raw):
        with pytest.raises(tv.ValueTypeError) as e:
            config.set_value("serve.port", raw)
        assert e.value.expected == "a whole number from 0 to 65535"
        assert e.value.raw == raw
        assert not paths.config_path().exists()

    def test_check_value_leaves_other_keys_alone(self, sandbox):
        assert config.check_value("ai.model", "anything") == "anything"
        assert config.check_value("policy_enforce", 5) == 5

    def test_placeholder(self):
        assert config.placeholder("logging.level") == (
            "OFF|DEBUG|INFO|WARNING|ERROR|CRITICAL")
        assert config.placeholder("logging.format") == "text|json"
        assert config.placeholder("serve.port") == "0-65535"
        assert config.placeholder("policy_enforce") == "bool"

    def test_cli_names_the_choices(self, boost):
        r = boost("config", "set", "logging.level", "verbose", expect=1)
        assert ("logging.level expects one of OFF, DEBUG, INFO, WARNING, "
                "ERROR, CRITICAL") in r.err
        assert ('got "verbose" — try `boost config set logging.level '
                '<OFF|DEBUG|INFO|WARNING|ERROR|CRITICAL>`') in _flat(r.err)
        r = boost("config", "set", "serve.port", "99999", expect=1)
        assert "serve.port expects a whole number from 0 to 65535" in r.err
        assert "`boost config set serve.port <0-65535>`" in _flat(r.err)


class TestSectionSet:
    """`config set <section> <json>` checks every leaf like its dotted key."""

    def _disk(self):
        return json.loads(paths.config_path().read_text(encoding="utf-8"))

    def test_bool_word_is_stored_as_a_bool(self, sandbox):
        config.set_value("ai", '{"enabled": "off", "model": "m"}')
        assert self._disk() == {"ai": {"enabled": False, "model": "m"}}
        assert config.get("ai.enabled") is False
        assert ai.enabled() is False

    def test_choice_is_stored_in_canonical_case(self, sandbox):
        config.set_value("logging", '{"level": "debug", "format": "JSON", '
                                    '"file": "no"}')
        assert self._disk() == {"logging": {"level": "DEBUG",
                                            "format": "json", "file": False}}

    @pytest.mark.parametrize("key,raw,leaf,bad,expected", [
        ("logging", '{"level": "verbose", "file": "no"}', "logging.level",
         "verbose", "one of OFF, DEBUG, INFO, WARNING, ERROR, CRITICAL"),
        ("logging", '{"file": "maybe"}', "logging.file", "maybe",
         tv.describe(tv.BOOL)),
        ("serve", '{"port": 99999}', "serve.port", 99999,
         "a whole number from 0 to 65535"),
        ("serve", '{"port": true}', "serve.port", True, tv.describe(tv.INT)),
        ("ai", '{"enabled": {"x": 1}}', "ai.enabled", {"x": 1},
         tv.describe(tv.BOOL)),
        ("ai", '{"model": 5}', "ai.model", 5, tv.describe(tv.STR)),
        ("agents", '{"claude-code": 5}', "agents.claude-code", 5,
         tv.describe(tv.DICT)),
    ])
    def test_a_bad_leaf_refuses_the_whole_value(self, sandbox, key, raw, leaf,
                                                bad, expected):
        with pytest.raises(tv.ValueTypeError) as e:
            config.set_value(key, raw)
        assert e.value.key == leaf
        assert e.value.raw == bad
        assert e.value.expected == expected
        assert not paths.config_path().exists()

    @pytest.mark.parametrize("agent", ["claude-code", "brand-new"])
    def test_nested_agent_dir_is_checked(self, sandbox, agent):
        with pytest.raises(tv.ValueTypeError) as e:
            config.set_value("agents", '{"%s": {"dir": "rel"}}' % agent)
        assert e.value.key == "agents.%s.dir" % agent
        assert not paths.config_path().exists()
        config.set_value("agents", '{"%s": {"dir": "~/x", "enabled": "no"}}'
                         % agent)
        stored = self._disk()["agents"][agent]
        assert stored["dir"] == "~/x"
        # an agent DEFAULTS describes types `enabled`; a new one does not
        assert stored["enabled"] == (False if agent == "claude-code"
                                     else "no")

    def test_a_section_given_as_a_json_string_is_walked(self, sandbox):
        with pytest.raises(tv.ValueTypeError) as e:
            config.set_value("agents",
                             json.dumps({"claude-code": '{"dir": "rel"}'}))
        assert e.value.key == "agents.claude-code.dir"
        assert not paths.config_path().exists()

    def test_unknown_leaves_pass_through(self, sandbox):
        config.set_value("ai", '{"extra": "off", "deep": {"n": 1}}')
        assert self._disk() == {"ai": {"extra": "off", "deep": {"n": 1}}}
        config.set_value("custom", '{"a": {"b": "off"}}')
        assert self._disk()["custom"] == {"a": {"b": "off"}}

    def test_cli_names_the_leaf(self, boost):
        r = boost("config", "set", "serve", '{"port": 99999}', expect=1)
        assert "serve.port expects a whole number from 0 to 65535" in r.err
        assert ("got 99999 — try `boost config set serve.port <0-65535>`"
                in _flat(r.err))
        assert not paths.config_path().exists()
        r = boost("config", "set", "ai", '{"enabled": "off"}')
        assert r.out.lstrip().startswith('✓ set ai = {"enabled": false, ')
        assert self._disk() == {"ai": {"enabled": False}}


class TestLogLevelEnv:
    def test_off_silences_a_configured_level(self, sandbox, monkeypatch,
                                             capsys):
        config.set_value("logging.level", "DEBUG")
        assert logs._console_level(False, False, False) == logging.DEBUG
        monkeypatch.setenv("BOOST_LOG_LEVEL", "off")
        assert logs._console_level(False, False, False) is None
        assert capsys.readouterr().err == ""

    def test_a_known_level_beats_config(self, sandbox, monkeypatch):
        config.set_value("logging.level", "DEBUG")
        monkeypatch.setenv("BOOST_LOG_LEVEL", "warning")
        assert logs._console_level(False, False, False) == logging.WARNING

    def test_an_unknown_level_silences_and_warns(self, sandbox, monkeypatch,
                                                 capsys):
        config.set_value("logging.level", "INFO")
        monkeypatch.setenv("BOOST_LOG_LEVEL", "loud")
        assert logs._console_level(False, False, False) is None
        assert capsys.readouterr().err == (
            "! BOOST_LOG_LEVEL='LOUD' is not one of OFF, DEBUG, INFO, "
            "WARNING, ERROR, CRITICAL — treating it as OFF\n")


class TestServePort:
    @pytest.fixture
    def bound(self, monkeypatch):
        from boost_cli.core import serve
        calls = []
        monkeypatch.setattr(serve, "serve_http",
                            lambda host, port: calls.append((host, port)))
        return calls

    def _store(self, port):
        paths.config_path().parent.mkdir(parents=True, exist_ok=True)
        paths.config_path().write_text(json.dumps({"serve": {"port": port}}),
                                       encoding="utf-8")

    def test_a_bad_stored_port_names_the_config_key(self, boost, bound):
        self._store(99999)
        r = boost("serve", expect=1)
        assert "config serve.port is 99999 — must be 0-65535" in r.err
        assert ("`boost config set serve.port <0-65535>`, or `boost config "
                "unset serve.port` for the default") in _flat(r.err)
        assert "--port" not in r.err
        assert bound == []

    def test_an_explicit_port_overrides_a_bad_stored_one(self, boost, bound):
        self._store(-3)
        boost("serve", "--port", "9000")
        assert bound == [("127.0.0.1", 9000)]

    def test_a_good_stored_port_is_used(self, boost, bound):
        self._store(65535)
        boost("serve")
        assert bound == [("127.0.0.1", 65535)]

    def test_the_default_port(self, boost, bound):
        boost("serve")
        assert bound == [("127.0.0.1", 8787)]

    def test_check_value_raises_for_a_stored_value(self, sandbox):
        with pytest.raises(tv.ValueTypeError):
            config.check_value("serve.port", 65536)
        assert config.check_value("serve.port", 0) == 0
