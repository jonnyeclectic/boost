# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/config.py — deep-merged JSON configuration."""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys

import pytest

from boost_cli.core import config, paths, typedvalue
from boost_cli.errors import BoostError


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
        # declaration order, and each new agent is appended so an existing
        # config.json's key order keeps matching the defaults' prefix.
        assert list(cfg["agents"]) == ["claude-code", "windsurf", "cursor",
                                       "gemini", "antigravity"]
        assert cfg["agents"]["cursor"] == {"dir": "~/.cursor/skills",
                                           "enabled": True}
        # links_skills False is the whole point of the gemini entry: it reads
        # ~/.agents/skills natively, so a symlink would only duplicate the skill
        # into a second discovery tier.
        assert cfg["agents"]["gemini"] == {"dir": "~/.gemini/skills",
                                           "enabled": True,
                                           "links_skills": False}
        # Antigravity CLI is the opposite case in the same tree: it reads
        # neither ~/.agents/skills nor the shared ~/.gemini/skills, so it takes
        # a real link — into its own CLI tier, where Gemini cannot see it and
        # log a conflict.
        assert cfg["agents"]["antigravity"] == {
            "dir": "~/.gemini/antigravity-cli/skills", "enabled": True,
            "project_scope": False, "skills_only": True}


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


@pytest.mark.skipif(sys.platform == "win32",
                    reason="chmod can't make a directory unwritable on Windows")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                    reason="root ignores mode bits")
class TestSaveUnderAReadOnlyBoostHome:
    """`boost untap` exited 70 here: ensure_dirs raised on a cache dir a
    read-only ~/.boost would not create, and the config write behind it would
    have failed the same way."""

    def test_names_the_directory_and_leaves_the_file_alone(self, sandbox):
        config.save({"a": 1})
        shutil.rmtree(paths.cache_dir(), ignore_errors=True)
        home = paths.boost_home()
        home.chmod(0o500)
        try:
            with pytest.raises(BoostError) as e:
                config.save({"a": 2})
        finally:
            home.chmod(0o700)
        assert e.value.message == ("could not save ~/.boost/config.json "
                                   "(Permission denied): ~/.boost is not "
                                   "writable")
        assert e.value.hint == "run `chmod u+w ~/.boost`, then re-run"
        raw = paths.config_path().read_text(encoding="utf-8")
        assert json.loads(raw) == {"a": 1}

    def test_a_failure_that_is_not_a_permission_has_no_chmod_hint(
            self, sandbox, monkeypatch):
        def full(*a, **k):
            raise OSError(28, "No space left on device")
        monkeypatch.setattr(config.util, "atomic_write_text", full)
        with pytest.raises(BoostError) as e:
            config.save({"a": 1})
        assert e.value.message == ("could not save ~/.boost/config.json "
                                   "(No space left on device)")
        assert e.value.hint is None


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

    def test_defaulted_key_on_pristine_home_returns_false_no_file_created(
            self, sandbox):
        # A key present only via DEFAULTS has nothing on disk to remove —
        # unset() used to walk the DEFAULTS-merged view, where every
        # defaulted key is `in node` forever, so this reported success and
        # wrote a brand new config.json holding all of DEFAULTS.
        assert not paths.config_path().exists()
        assert config.unset("telemetry") is False
        assert not paths.config_path().exists()

    def test_repeat_unset_of_already_removed_key_returns_false_no_rewrite(
            self, sandbox):
        config.set_value("ai.enabled", "false")
        assert config.unset("ai.enabled") is True
        stamp = paths.config_path().stat().st_mtime_ns
        # Second call: the key is gone from the file, present only via
        # DEFAULTS again — must not report success or touch the file.
        assert config.unset("ai.enabled") is False
        assert paths.config_path().stat().st_mtime_ns == stamp
        assert config.get("ai.enabled") is True  # back to default

    def test_corrupt_json_reads_as_no_overrides_and_does_not_raise(
            self, sandbox):
        # _read_raw() must degrade the same way _read() does: a malformed
        # file is "no overrides", never a crash and never a match.
        paths.ensure_dirs()
        paths.config_path().write_text("{not json!!", encoding="utf-8")
        assert config.unset("telemetry") is False


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


class TestRegistryCategories:
    def test_maps_name_to_category_dropping_uncategorized_rows(self, monkeypatch):
        monkeypatch.setattr(config, "load_registry_catalog", lambda: [
            {"name": "acme/ai-tap", "category": "ai"},
            {"name": "acme/no-category-tap"},
            {"name": "acme/blank-category-tap", "category": ""},
        ])
        assert config.registry_categories() == {"acme/ai-tap": "ai"}

    def test_against_the_real_bundled_catalog(self):
        # Every category value present is a non-empty string, and the map
        # covers exactly the rows the raw catalog itself marks categorized.
        cats = config.registry_categories()
        raw = config.load_registry_catalog()
        assert cats  # the bundled catalog does carry categories
        assert set(cats) == {e["name"] for e in raw if e.get("category")}
        assert all(isinstance(v, str) and v for v in cats.values())


# ------------------------------------------------------- typed config values

class TestSpecFor:
    def test_a_key_is_typed_by_its_default(self, sandbox):
        assert config.spec_for("telemetry") == typedvalue.BOOL
        assert config.spec_for("policy_enforce") == typedvalue.BOOL
        assert config.spec_for("serve.port") == typedvalue.INT
        assert config.spec_for("taps") == typedvalue.LIST
        assert config.spec_for("ai.model") == typedvalue.STR
        assert config.spec_for("ai") == typedvalue.DICT

    def test_a_deeply_nested_key_is_typed(self, sandbox):
        assert config.spec_for("agents.claude-code.enabled") == typedvalue.BOOL
        assert config.spec_for("agents.claude-code.dir") == typedvalue.STR

    def test_a_key_defaults_has_never_heard_of_is_untyped(self, sandbox):
        # `boost config set` accepts keys boost does not ship — inventing a
        # type for those would refuse values that work today.
        assert config.spec_for("brand.new.key") == typedvalue.ANY
        assert config.spec_for("security.enforce_digest") == typedvalue.ANY
        assert config.spec_for("agents.made-up.enabled") == typedvalue.ANY

    def test_a_path_that_crosses_a_scalar_is_untyped(self, sandbox):
        assert config.spec_for("ai.model.deeper") == typedvalue.ANY


class TestSetValueIsTyped:
    def test_a_boolean_key_reads_the_word_the_user_typed(self, sandbox):
        config.set_value("telemetry", "no")
        assert config.get("telemetry") is False
        config.set_value("telemetry", "on")
        assert config.get("telemetry") is True

    def test_a_bad_boolean_is_refused_and_nothing_is_written(self, sandbox):
        with pytest.raises(typedvalue.ValueTypeError):
            config.set_value("telemetry", "maybe")
        assert not paths.config_path().exists()
        assert config.get("telemetry") is False   # still the default

    def test_a_bad_number_is_refused(self, sandbox):
        with pytest.raises(typedvalue.ValueTypeError) as e:
            config.set_value("serve.port", "abc")
        assert e.value.key == "serve.port"
        assert config.get("serve.port") == 8787

    def test_a_string_key_keeps_a_numeric_looking_value_as_text(self, sandbox):
        config.set_value("ai.model", "42")
        assert config.get("ai.model") == "42"

    def test_an_untyped_key_keeps_the_old_lenient_parse(self, sandbox):
        config.set_value("security.enforce_digest", "true")
        assert config.get("security.enforce_digest") is True


class TestGetInt:
    def test_a_stored_int(self, sandbox):
        config.set_value("serve.port", "9001")
        assert config.get_int("serve.port", 8787) == 9001

    def test_the_default_when_unset(self, sandbox):
        assert config.get_int("no.such.port", 8787) == 8787

    def test_an_explicit_null_falls_back_to_the_default(self, sandbox):
        cfg = config.load()
        cfg["serve"]["port"] = None
        config.save(cfg)
        assert config.get_int("serve.port", 8787) == 8787

    def test_a_hand_edited_string_number_is_read(self, sandbox):
        cfg = config.load()
        cfg["serve"]["port"] = "8080"
        config.save(cfg)
        assert config.get_int("serve.port", 8787) == 8080

    def test_a_hand_edited_non_number_raises_a_typed_error(self, sandbox):
        # Not a bare ValueError: `boost serve --help` used to die on this with
        # exit 70 and a crash report, before argparse ever ran.
        cfg = config.load()
        cfg["serve"]["port"] = "abc"
        config.save(cfg)
        with pytest.raises(typedvalue.ValueTypeError) as e:
            config.get_int("serve.port", 8787)
        assert e.value.key == "serve.port"
        assert e.value.expected == typedvalue.describe(typedvalue.INT)

    def test_a_boolean_is_not_a_port_number(self, sandbox):
        cfg = config.load()
        cfg["serve"]["port"] = True
        config.save(cfg)
        with pytest.raises(typedvalue.ValueTypeError):
            config.get_int("serve.port", 8787)


class TestCorruptFile:
    """A config.json that exists but fails to parse must warn (not silently
    degrade unremarked) and must never be clobbered by the next save without
    a trace — see the audit-corrupt-settings-config-state-json roadmap item."""

    def test_corrupt_read_warns_on_stderr(self, sandbox, capsys):
        paths.ensure_dirs()
        paths.config_path().write_text("{not json!!", encoding="utf-8")
        config.load()
        captured = capsys.readouterr()
        assert str(paths.config_path()) in captured.err
        assert captured.out == ""

    def test_missing_file_does_not_warn(self, sandbox, capsys):
        config.load()
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_set_value_quarantines_corrupt_file_instead_of_destroying_it(
            self, sandbox):
        paths.ensure_dirs()
        original = '{"taps": [{"name": "a/b", "url": "x", "curated": false}]'
        paths.config_path().write_text(original, encoding="utf-8")

        config.set_value("telemetry", "true")

        quarantined = paths.config_path().with_name("config.json.corrupt")
        assert quarantined.read_text(encoding="utf-8") == original
        fresh = json.loads(paths.config_path().read_text(encoding="utf-8"))
        assert fresh["telemetry"] is True
        # the corrupt file's content never survives into the new one
        assert "taps" not in fresh or fresh["taps"] == []

    def test_save_over_a_valid_file_never_quarantines(self, sandbox):
        config.save({"telemetry": True})
        config.save({"telemetry": False})
        assert not paths.config_path().with_name("config.json.corrupt").exists()

    def test_repeated_corruption_keeps_every_quarantined_copy(self, sandbox):
        paths.ensure_dirs()
        paths.config_path().write_text("bad one", encoding="utf-8")
        config.set_value("telemetry", "true")
        paths.config_path().write_text("bad two", encoding="utf-8")
        config.set_value("telemetry", "true")

        first = paths.config_path().with_name("config.json.corrupt")
        second = paths.config_path().with_name("config.json.corrupt.2")
        assert first.read_text(encoding="utf-8") == "bad one"
        assert second.read_text(encoding="utf-8") == "bad two"


class TestCheckReportsTheRawState:
    """`load()` degrades a corrupt file to DEFAULTS; `check()` is what lets
    doctor say so instead of verdicting "ready to set up" (see
    corrupt-config-reads-as-ready-to-set-up)."""

    def test_missing_file_is_not_a_problem(self, sandbox):
        assert config.check() is None

    def test_a_valid_file_is_not_a_problem(self, sandbox):
        config.save({"taps": []})
        assert config.check() is None

    def test_invalid_json_names_the_file_and_the_error(self, sandbox):
        paths.ensure_dirs()
        paths.config_path().write_text('{"taps": [', encoding="utf-8")
        err = config.check()
        assert err and str(paths.config_path()) in err and "invalid JSON" in err

    def test_a_non_object_is_a_problem_too(self, sandbox):
        paths.ensure_dirs()
        paths.config_path().write_text("[]", encoding="utf-8")
        assert "expected a JSON object" in config.check()

    def test_invalid_utf8_names_the_file_instead_of_crashing(self, sandbox):
        paths.ensure_dirs()
        paths.config_path().write_bytes(b"\xff\xfe")
        err = config.check()
        assert err.startswith(str(paths.config_path()) + ": not valid UTF-8")

    def test_unlisted_clones_are_the_directories_under_repos(self, sandbox):
        assert config.unlisted_clones() == []           # no repos/ at all
        paths.ensure_dirs()
        for name in ("b__two", "a__one"):
            (paths.repos_dir() / name).mkdir()
        (paths.repos_dir() / "stray.txt").write_text("x", encoding="utf-8")
        assert config.unlisted_clones() == ["a__one", "b__two"]


# `boost tap` appends to `taps`, and crashed with AttributeError on every one of
# these. Meanwhile `first_run` read the truthy ones as a configured machine and
# `list_taps` read all of them as no taps, so doctor said "ready to set up".
NOT_A_LIST = [('"x"', "str"), ("null", "NoneType"), ("{}", "dict"),
              ('{"a/b": {}}', "dict"), ("5", "int"), ("true", "bool"),
              ('""', "str")]


class TestTapsThatIsNotAList:
    """A `taps` boost cannot read is the same broken file as invalid JSON, on
    every surface: check() names it, load() reads DEFAULTS, save() moves it
    aside, and first_run() does not call the machine new."""

    def _write(self, text):
        paths.ensure_dirs()
        paths.config_path().write_text(text, encoding="utf-8")

    @pytest.mark.parametrize("taps,found", NOT_A_LIST)
    def test_check_names_the_key_and_what_it_holds(self, sandbox, taps, found):
        self._write('{"taps": %s}' % taps)
        assert config.check() == ('%s: expected "taps" to be a list, found %s'
                                  % (paths.config_path(), found))

    @pytest.mark.parametrize("text", ['{"taps": []}', '{"telemetry": true}'])
    def test_a_list_or_no_taps_key_is_fine(self, sandbox, text):
        self._write(text)
        assert config.check() is None

    @pytest.mark.parametrize("taps,_found", NOT_A_LIST)
    def test_it_is_never_a_first_run(self, sandbox, taps, _found):
        self._write('{"taps": %s}' % taps)
        assert config.first_run() is False

    def test_the_whole_file_reads_as_defaults_with_one_warning(self, sandbox,
                                                                capsys):
        # The same degrade as invalid JSON, so every message that describes
        # that state ("running on defaults", "the next write moves it aside")
        # is true of this one too.
        self._write('{"taps": "x", "telemetry": true}')
        assert config.load() == config.DEFAULTS
        err = capsys.readouterr().err
        assert err.count(str(paths.config_path())) == 1
        assert 'expected "taps" to be a list' in err

    def test_list_taps_still_reads_it_as_none(self, sandbox):
        from boost_cli.core import registry
        self._write('{"taps": {"a/b": {"url": "u"}}}')
        assert registry.list_taps() == []

    def test_the_next_write_moves_it_aside(self, sandbox):
        # What doctor promises. Before, save() only quarantined a file that
        # failed to parse, so this one was written back with "taps": "x"
        # intact and `boost tap` crashed appending to it.
        original = '{"taps": "x", "telemetry": true}'
        self._write(original)
        config.set_value("ai.enabled", "false")
        quarantined = paths.config_path().with_name("config.json.corrupt")
        assert quarantined.read_text(encoding="utf-8") == original
        fresh = json.loads(paths.config_path().read_text(encoding="utf-8"))
        assert fresh["taps"] == [] and fresh["ai"]["enabled"] is False
        assert config.check() is None

    def test_unset_reads_no_overrides_from_it(self, sandbox):
        self._write('{"taps": "x"}')
        assert config.unset("taps") is False
        assert paths.config_path().read_text(encoding="utf-8") == '{"taps": "x"}'
