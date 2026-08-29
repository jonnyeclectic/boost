# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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
        paths.config_path().write_text("{not json!!", encoding="utf-8")
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
        # Order is load-bearing: agents are iterated (and linked/reported) in
        # declaration order, and gemini was appended last so an existing
        # config.json's key order keeps matching the defaults' prefix.
        assert list(cfg["agents"]) == ["claude-code", "windsurf", "cursor",
                                       "gemini"]
        assert cfg["agents"]["cursor"] == {"dir": "~/.cursor/skills",
                                           "enabled": True}
        # links_skills False is the whole point of the gemini entry: it reads
        # ~/.agents/skills natively, so a symlink would only duplicate the skill
        # into a second discovery tier.
        assert cfg["agents"]["gemini"] == {"dir": "~/.gemini/skills",
                                           "enabled": True,
                                           "links_skills": False}


class TestDeepMerge:
    def test_user_override_wins_nested_merge_preserved(self, sandbox):
        paths.ensure_dirs()
        paths.config_path().write_text(json.dumps(
            {"ai": {"model": "custom-model"}, "telemetry": True}), encoding="utf-8")
        cfg = config.load()
        assert cfg["ai"]["model"] == "custom-model"       # override wins
        assert cfg["ai"]["enabled"] is True               # sibling preserved
        assert cfg["ai"]["author_model"] == "claude-sonnet-5"
        assert cfg["telemetry"] is True
        assert cfg["serve"]["port"] == 8787               # untouched section

    def test_scalar_replaces_dict(self, sandbox):
        paths.ensure_dirs()
        paths.config_path().write_text(json.dumps({"serve": "off"}), encoding="utf-8")
        assert config.load()["serve"] == "off"

    def test_load_does_not_mutate_defaults(self, sandbox):
        snapshot = copy.deepcopy(config.DEFAULTS)
        paths.ensure_dirs()
        paths.config_path().write_text(json.dumps(
            {"agents": {"claude-code": {"enabled": False}}, "extra": 1}), encoding="utf-8")
        cfg = config.load()
        assert cfg["agents"]["claude-code"]["enabled"] is False
        assert cfg["extra"] == 1
        assert snapshot == config.DEFAULTS


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
        raw = paths.config_path().read_text(encoding="utf-8")
        assert json.loads(raw) == {"a": 1}
        assert raw.endswith("\n")

    def test_save_is_pretty_printed_and_preserves_key_order(self, sandbox):
        # 2-space indent and insertion order (sort_keys=False) — the config file
        # is human-edited, so it must stay readable and stable, not compacted or
        # alphabetized. Pins indent=2 and sort_keys=False.
        config.save({"zeta": 1, "alpha": 2})
        raw = paths.config_path().read_text(encoding="utf-8")
        assert '\n  "zeta": 1' in raw                 # 2-space indent, not compact
        assert raw.index('"zeta"') < raw.index('"alpha"')   # insertion, not sorted


class TestCaching:
    def test_reads_only_once_when_file_unchanged(self, sandbox, monkeypatch):
        calls = {"n": 0}
        real = config._read

        def counting():
            calls["n"] += 1
            return real()

        monkeypatch.setattr(config, "_cache", None)
        monkeypatch.setattr(config, "_cache_key", None)
        monkeypatch.setattr(config, "_read", counting)
        config.get("ai.model")
        config.get("serve.port")
        config.load()
        assert calls["n"] == 1  # cached: file never re-read

    def test_external_write_invalidates_cache(self, sandbox):
        paths.ensure_dirs()
        paths.config_path().write_text(json.dumps({"serve": {"port": 1}}), encoding="utf-8")
        assert config.get("serve.port") == 1
        # A different size on disk changes the stat stamp -> reload.
        paths.config_path().write_text(json.dumps({"serve": {"port": 22222}}), encoding="utf-8")
        assert config.get("serve.port") == 22222

    def test_save_visible_to_get(self, sandbox):
        assert config.get("telemetry") is False  # warm the cache
        config.save({"telemetry": True})
        assert config.get("telemetry") is True

    def test_get_returns_isolated_container(self, sandbox):
        agents = config.get("agents")
        agents["claude-code"]["enabled"] = False
        assert config.get("agents")["claude-code"]["enabled"] is True

    def test_load_returns_isolated_copy(self, sandbox):
        first = config.load()
        first["serve"]["port"] = 424242
        assert config.get("serve.port") == 8787
        assert config.load()["serve"]["port"] == 8787

    def test_missing_file_stamps_then_reloads_on_create(self, sandbox):
        assert config.get("serve.port") == 8787  # no file yet -> defaults
        config.save({"serve": {"port": 7000}})
        assert config.get("serve.port") == 7000


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
        on_disk = json.loads(paths.config_path().read_text(encoding="utf-8"))
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
        on_disk = json.loads(paths.config_path().read_text(encoding="utf-8"))
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

    def test_unset_deeply_nested_key_targets_the_leaf(self, sandbox):
        # a 3-level key exercises the parent-walk `parts[:-1]` and leaf `parts[-1]`
        # correctly — a 2-level key can't tell them from `parts[:1]` / `parts[1]`.
        cfg = config.load()
        cfg["deep"] = {"mid": {"leaf": 1, "keep": 2}}
        config.save(cfg)
        assert config.unset("deep.mid.leaf") is True
        assert config.load()["deep"]["mid"] == {"keep": 2}   # only leaf removed

    def test_path_through_scalar_returns_false(self, sandbox):
        assert config.unset("ai.model.sub") is False


class TestDefaultTaps:
    def test_shape(self):
        assert len(config.DEFAULT_TAPS) == 7
        names = [t["name"] for t in config.DEFAULT_TAPS]
        assert names == ["anthropics/skills", "obra/superpowers",
                         "trailofbits/skills", "expo/skills",
                         "K-Dense-AI/scientific-agent-skills",
                         "PatrickJS/awesome-cursorrules",
                         "qdhenry/Claude-Command-Suite"]
        for tap in config.DEFAULT_TAPS:
            assert tap["curated"] is True
            assert tap["url"].startswith("https://github.com/")
            assert tap["url"].endswith(tap["name"])
            assert tap["focus"]

    def test_the_defaults_cover_all_three_item_kinds(self):
        # The five skills-first repos measured 302 skills and 41 workflows
        # between them and ZERO rules, so a default install could not find a
        # guardrail at all — the kind whose whole job is steering toward a
        # better path and away from an anti-pattern. The focus lines are what
        # a user reads in `boost tap --defaults` output, so each kind has to
        # be findable there too, not just present in the clone.
        focus = " ".join(t["focus"].lower() for t in config.DEFAULT_TAPS)
        assert "rules" in focus
        assert "workflows" in focus
        assert "skills" in focus


class TestRegistryCatalog:
    def test_bundled_catalog_loads_and_is_well_formed(self):
        cat = config.load_registry_catalog()
        assert len(cat) >= 50
        names = [e["name"] for e in cat]
        assert len(names) == len(set(names))  # deduped
        for e in cat:
            assert e["type"] in ("skill", "rule", "workflow")
            assert e["url"] == "https://github.com/" + e["name"]
            assert e["focus"]
            assert isinstance(e["est_items"], int)
            assert isinstance(e["list_only"], bool)

    def test_scannable_estimate_clears_1500(self):
        cat = config.load_registry_catalog()
        scannable = sum(e["est_items"] for e in cat if not e["list_only"])
        assert scannable >= 1500

    def test_covers_all_three_types(self):
        types = {e["type"] for e in config.load_registry_catalog()}
        assert types == {"skill", "rule", "workflow"}

    def test_missing_file_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "REGISTRY_CATALOG", tmp_path / "nope.json")
        assert config.load_registry_catalog() == []
