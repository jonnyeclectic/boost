"""Unit tests: boost_cli/core/config.py — deep-merged JSON configuration."""
from __future__ import annotations

import copy
import json

import pytest

from boost_cli.core import config, paths


class TestLoadDefaults:
    def test_missing_file_returns_defaults_copy(self, sandbox):
        cfg = config.load()
        assert cfg == config.DEFAULTS
        assert cfg is not config.DEFAULTS
        cfg["agents"]["claude-code"]["enabled"] = False
        assert config.DEFAULTS["agents"]["claude-code"]["enabled"] is True

    def test_corrupt_json_returns_defaults(self, sandbox):
        paths.ensure_dirs()
        paths.config_path().write_text("{not json!!")
        assert config.load() == config.DEFAULTS

    def test_default_values(self, sandbox):
        cfg = config.load()
        assert cfg["ai"]["enabled"] is True
        assert cfg["ai"]["model"] == "claude-haiku-4-5-20251001"
        assert cfg["ai"]["author_model"] == "claude-sonnet-5"
        assert cfg["serve"]["port"] == 8787
        assert cfg["policy_enforce"] is True
        assert cfg["telemetry"] is False
        assert cfg["taps"] == []
        assert set(cfg["agents"]) == {"claude-code", "windsurf", "cursor"}
        assert cfg["agents"]["cursor"] == {"dir": "~/.cursor/skills",
                                           "enabled": True}


class TestDeepMerge:
    def test_user_override_wins_nested_merge_preserved(self, sandbox):
        paths.ensure_dirs()
        paths.config_path().write_text(json.dumps(
            {"ai": {"model": "custom-model"}, "telemetry": True}))
        cfg = config.load()
        assert cfg["ai"]["model"] == "custom-model"       # override wins
        assert cfg["ai"]["enabled"] is True               # sibling preserved
        assert cfg["ai"]["author_model"] == "claude-sonnet-5"
        assert cfg["telemetry"] is True
        assert cfg["serve"]["port"] == 8787               # untouched section

    def test_scalar_replaces_dict(self, sandbox):
        paths.ensure_dirs()
        paths.config_path().write_text(json.dumps({"serve": "off"}))
        assert config.load()["serve"] == "off"

    def test_load_does_not_mutate_defaults(self, sandbox):
        snapshot = copy.deepcopy(config.DEFAULTS)
        paths.ensure_dirs()
        paths.config_path().write_text(json.dumps(
            {"agents": {"claude-code": {"enabled": False}}, "extra": 1}))
        cfg = config.load()
        assert cfg["agents"]["claude-code"]["enabled"] is False
        assert cfg["extra"] == 1
        assert config.DEFAULTS == snapshot


class TestSaveRoundtrip:
    def test_save_then_load(self, sandbox):
        cfg = config.load()
        cfg["telemetry"] = True
        cfg["serve"]["port"] = 9999
        config.save(cfg)
        again = config.load()
        assert again["telemetry"] is True
        assert again["serve"]["port"] == 9999

    def test_save_writes_json_file(self, sandbox):
        config.save({"a": 1})
        raw = paths.config_path().read_text()
        assert json.loads(raw) == {"a": 1}
        assert raw.endswith("\n")


class TestGet:
    def test_dotted_hit(self, sandbox):
        assert config.get("ai.model") == "claude-haiku-4-5-20251001"
        assert config.get("serve.port") == 8787
        assert config.get("agents.windsurf.dir") == "~/.windsurf/skills"

    def test_top_level_hit(self, sandbox):
        assert config.get("policy_enforce") is True

    def test_miss_returns_default(self, sandbox):
        assert config.get("no.such.key") is None
        assert config.get("no.such.key", "fallback") == "fallback"

    def test_traversal_through_non_dict_returns_default(self, sandbox):
        # ai.model is a string; going deeper must not raise
        assert config.get("ai.model.deeper", "dflt") == "dflt"


class TestSetValue:
    def test_json_true(self, sandbox):
        config.set_value("telemetry", "true")
        assert config.get("telemetry") is True

    def test_json_int(self, sandbox):
        config.set_value("serve.port", "3")
        assert config.get("serve.port") == 3

    def test_json_list(self, sandbox):
        config.set_value("taps", "[1, 2]")
        assert config.get("taps") == [1, 2]

    def test_plain_string(self, sandbox):
        config.set_value("ai.model", "plain")
        assert config.get("ai.model") == "plain"

    def test_nested_key_creation(self, sandbox):
        config.set_value("brand.new.key", "42")
        assert config.get("brand.new.key") == 42
        assert config.get("brand.new") == {"key": 42}

    def test_persisted_to_disk(self, sandbox):
        config.set_value("telemetry", "true")
        on_disk = json.loads(paths.config_path().read_text())
        assert on_disk["telemetry"] is True

    def test_type_error_when_path_crosses_scalar(self, sandbox):
        with pytest.raises(TypeError) as e:
            config.set_value("ai.model.sub", "1")
        assert "'model'" in str(e.value)
        assert "not a section" in str(e.value)


class TestUnset:
    def test_present_returns_true_and_persists(self, sandbox):
        config.set_value("custom.flag", "true")
        assert config.unset("custom.flag") is True
        on_disk = json.loads(paths.config_path().read_text())
        assert "flag" not in on_disk.get("custom", {})
        assert config.get("custom.flag") is None

    def test_unset_override_restores_default_on_load(self, sandbox):
        config.set_value("serve.port", "9999")
        assert config.get("serve.port") == 9999
        assert config.unset("serve.port") is True
        assert config.get("serve.port") == 8787  # deep merge restores default

    def test_absent_returns_false(self, sandbox):
        assert config.unset("never.was.here") is False
        assert config.unset("absent_top") is False

    def test_path_through_scalar_returns_false(self, sandbox):
        assert config.unset("ai.model.sub") is False


class TestDefaultTaps:
    def test_shape(self):
        assert len(config.DEFAULT_TAPS) == 5
        names = [t["name"] for t in config.DEFAULT_TAPS]
        assert names == ["anthropics/skills", "obra/superpowers",
                         "trailofbits/skills", "expo/skills",
                         "K-Dense-AI/claude-scientific-skills"]
        for tap in config.DEFAULT_TAPS:
            assert tap["curated"] is True
            assert tap["url"].startswith("https://github.com/")
            assert tap["url"].endswith(tap["name"])
            assert tap["focus"]
