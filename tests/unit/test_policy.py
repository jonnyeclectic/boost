# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/policy.py — governance rules for installs."""
from __future__ import annotations

import json

import pytest

from boost_cli.core import config, paths, policy, typedvalue

GOOD_ENTRY = {"name": "brainstorming", "tap": "acme/skills",
              "description": "Structured ideation", "version": "1.4.0"}


def set_policy(**overrides):
    pol = dict(policy.DEFAULTS)
    pol.update(overrides)
    policy.save(pol)
    return pol


class TestLoad:
    def test_missing_file_gives_defaults(self, sandbox):
        pol = policy.load()
        assert pol == policy.DEFAULTS
        assert pol == {
            "blocked_skills": [], "blocked_taps": [], "allowed_taps": [],
            "require_description": False, "require_version": False,
            "min_quality_score": 0, "max_skills": None, "pin_only": False,
            "denied_capabilities": [], "enforce_detected_capabilities": False,
            "require_signed_taps": False,
        }

    def test_corrupt_file_gives_defaults(self, sandbox):
        paths.ensure_dirs()
        paths.policy_path().write_text("{broken", encoding="utf-8")
        assert policy.load() == policy.DEFAULTS

    def test_user_values_override(self, sandbox):
        paths.ensure_dirs()
        paths.policy_path().write_text(json.dumps({"pin_only": True}), encoding="utf-8")
        pol = policy.load()
        assert pol["pin_only"] is True
        assert pol["blocked_skills"] == []


class TestSave:
    def test_extras_dropped_known_keys_kept(self, sandbox):
        policy.save({"pin_only": True, "rogue_key": "x", "another": 1})
        on_disk = json.loads(paths.policy_path().read_text(encoding="utf-8"))
        assert set(on_disk) == set(policy.DEFAULTS)
        assert "rogue_key" not in on_disk
        assert on_disk["pin_only"] is True

    def test_missing_keys_filled_from_defaults(self, sandbox):
        policy.save({"blocked_skills": ["bad"]})
        on_disk = json.loads(paths.policy_path().read_text(encoding="utf-8"))
        assert on_disk["blocked_skills"] == ["bad"]
        assert on_disk["max_skills"] is None
        assert on_disk["require_version"] is False


class TestCheckInstall:
    def test_default_policy_allows(self, sandbox):
        assert policy.check_install(GOOD_ENTRY, 0) == []
        assert policy.check_install(GOOD_ENTRY, 500) == []

    def test_pin_only(self, sandbox):
        set_policy(pin_only=True)
        assert policy.check_install(GOOD_ENTRY, 0) == [
            "environment is pin-only (frozen)"]

    def test_blocked_skills(self, sandbox):
        set_policy(blocked_skills=["brainstorming"])
        assert policy.check_install(GOOD_ENTRY, 0) == [
            "skill 'brainstorming' is on the blocklist"]
        assert policy.check_install(
            {**GOOD_ENTRY, "name": "other"}, 0) == []

    def test_blocked_taps(self, sandbox):
        set_policy(blocked_taps=["acme/skills"])
        assert policy.check_install(GOOD_ENTRY, 0) == [
            "tap 'acme/skills' is blocked"]
        assert policy.check_install({**GOOD_ENTRY, "tap": "safe/tap"}, 0) == []

    def test_allowed_taps_empty_allows_all(self, sandbox):
        set_policy(allowed_taps=[])
        assert policy.check_install(GOOD_ENTRY, 0) == []

    def test_allowed_taps_blocks_others(self, sandbox):
        set_policy(allowed_taps=["good/tap"])
        assert policy.check_install(GOOD_ENTRY, 0) == [
            "tap 'acme/skills' is not on the allowlist"]
        assert policy.check_install({**GOOD_ENTRY, "tap": "good/tap"}, 0) == []

    def test_allowed_taps_local_always_allowed(self, sandbox):
        set_policy(allowed_taps=["good/tap"])
        assert policy.check_install({**GOOD_ENTRY, "tap": "local"}, 0) == []

    def test_require_description(self, sandbox):
        set_policy(require_description=True)
        assert policy.check_install(GOOD_ENTRY, 0) == []
        no_desc = {**GOOD_ENTRY, "description": ""}
        assert policy.check_install(no_desc, 0) == [
            "skill has no description (required by policy)"]
        del no_desc["description"]
        assert policy.check_install(no_desc, 0) == [
            "skill has no description (required by policy)"]

    def test_require_version(self, sandbox):
        set_policy(require_version=True)
        assert policy.check_install(GOOD_ENTRY, 0) == []
        msg = "skill has no version (required by policy)"
        assert policy.check_install({**GOOD_ENTRY, "version": ""}, 0) == [msg]
        assert policy.check_install(
            {**GOOD_ENTRY, "version": "0.0.0"}, 0) == [msg]
        assert policy.check_install({**GOOD_ENTRY, "version": None}, 0) == [msg]

    def test_max_skills_boundary(self, sandbox):
        set_policy(max_skills=3)
        assert policy.check_install(GOOD_ENTRY, 2) == []          # one below
        assert policy.check_install(GOOD_ENTRY, 3) == [
            "max_skills limit (3) reached"]                       # at cap
        assert policy.check_install(GOOD_ENTRY, 4) == [
            "max_skills limit (3) reached"]

    def test_max_skills_none_means_unlimited(self, sandbox):
        set_policy(max_skills=None)
        assert policy.check_install(GOOD_ENTRY, 10_000) == []

    def test_max_skills_zero_blocks_first_install(self, sandbox):
        set_policy(max_skills=0)
        assert policy.check_install(GOOD_ENTRY, 0) == [
            "max_skills limit (0) reached"]

    def test_violations_accumulate(self, sandbox):
        set_policy(pin_only=True, blocked_skills=["brainstorming"],
                   require_description=True)
        v = policy.check_install({"name": "brainstorming", "tap": "t"}, 0)
        assert v == [
            "environment is pin-only (frozen)",
            "skill 'brainstorming' is on the blocklist",
            "skill has no description (required by policy)",
        ]

    def test_policy_enforce_false_bypasses_everything(self, sandbox):
        set_policy(pin_only=True, blocked_skills=["brainstorming"],
                   max_skills=0)
        cfg = config.load()
        cfg["policy_enforce"] = False
        config.save(cfg)
        assert policy.check_install(GOOD_ENTRY, 999) == []

    def test_missing_entry_fields_tolerated(self, sandbox):
        set_policy(blocked_skills=["x"], blocked_taps=["y"])
        assert policy.check_install({}, 0) == []


class TestCheckCapabilities:
    def test_declared_denied_capability_violates(self, sandbox):
        set_policy(denied_capabilities=["network"])
        v = policy.check_capabilities({"capabilities": ["network"]}, "body")
        assert v == ["declares the 'network' capability, denied by policy"]

    def test_declared_but_not_denied_is_allowed(self, sandbox):
        set_policy(denied_capabilities=["shell"])
        assert policy.check_capabilities({"capabilities": ["network"]}, "body") == []

    def test_empty_denylist_short_circuits(self, sandbox):
        # no denied capabilities -> allowed regardless of what the skill declares
        set_policy(denied_capabilities=[])
        assert policy.check_capabilities({"capabilities": ["network", "shell"]}, "x") == []

    def test_master_switch_bypasses(self, sandbox):
        set_policy(denied_capabilities=["network"])
        cfg = config.load()
        cfg["policy_enforce"] = False
        config.save(cfg)
        assert policy.check_capabilities({"capabilities": ["network"]}, "body") == []

    def test_detected_only_needs_strict_flag(self, sandbox):
        # a body that *looks* like it uses the network but doesn't declare it:
        # denied, yet only enforced when enforce_detected_capabilities is on.
        body = "import requests\nrequests.get('https://example.com')\n"
        set_policy(denied_capabilities=["network"],
                   enforce_detected_capabilities=False)
        assert policy.check_capabilities({}, body) == []
        set_policy(denied_capabilities=["network"],
                   enforce_detected_capabilities=True)
        v = policy.check_capabilities({}, body)
        assert v == ["looks like it uses 'network' (detected), denied by policy"]


class TestCheckTapSigning:
    def test_off_by_default(self, sandbox, tmp_path):
        clone = tmp_path / "c"
        clone.mkdir()
        assert policy.check_tap_signing(clone) == []

    def test_required_but_unsigned_violates(self, sandbox, tmp_path):
        set_policy(require_signed_taps=True)
        clone = tmp_path / "c"
        clone.mkdir()
        v = policy.check_tap_signing(clone)
        assert len(v) == 1 and "unsigned" in v[0] and "trusted signature" in v[0]

    def test_required_and_verified_passes(self, sandbox, tmp_path, signer):
        from boost_cli.core import provenance
        set_policy(require_signed_taps=True)
        provenance.add_trusted_key("acme", signer.public_key_text())
        clone = tmp_path / "c"
        clone.mkdir()
        signer.write_signed(clone)
        assert policy.check_tap_signing(clone) == []

    def test_required_but_untrusted_key_violates(self, sandbox, tmp_path, signer):
        set_policy(require_signed_taps=True)
        clone = tmp_path / "c"
        clone.mkdir()
        signer.write_signed(clone)                 # signed, key not trusted
        v = policy.check_tap_signing(clone)
        assert len(v) == 1 and "no trusted key" in v[0]

    def test_master_switch_bypasses(self, sandbox, tmp_path):
        set_policy(require_signed_taps=True)
        cfg = config.load()
        cfg["policy_enforce"] = False
        config.save(cfg)
        clone = tmp_path / "c"
        clone.mkdir()
        assert policy.check_tap_signing(clone) == []


# ------------------------------------------------------- typed policy values

def write_policy_json(raw: dict) -> None:
    """Write policy.json verbatim — no save() filtering, no type checking."""
    paths.ensure_dirs()
    paths.policy_path().write_text(json.dumps(raw), encoding="utf-8")


class TestSpecFor:
    def test_every_default_key_declares_a_type(self, sandbox):
        assert set(policy.VALUE_TYPES) == set(policy.DEFAULTS)

    def test_types_are_derived_from_the_defaults(self, sandbox):
        assert policy.spec_for("pin_only") == typedvalue.BOOL
        assert policy.spec_for("require_signed_taps") == typedvalue.BOOL
        assert policy.spec_for("min_quality_score") == typedvalue.INT
        assert policy.spec_for("blocked_skills") == typedvalue.LIST
        assert policy.spec_for("denied_capabilities") == typedvalue.LIST

    def test_max_skills_declares_the_type_its_default_cannot(self, sandbox):
        # Its default is None, which names no type at all.
        assert policy.DEFAULTS["max_skills"] is None
        assert policy.spec_for("max_skills") == typedvalue.INT_OR_NONE

    def test_an_unknown_key_is_untyped(self, sandbox):
        assert policy.spec_for("no_such_key") == typedvalue.ANY


class TestParseValue:
    def test_a_boolean_key_reads_the_word_the_user_typed(self, sandbox):
        # THE bug: "no" is a truthy string, so `policy set pin_only no` used
        # to turn pin-only ON and freeze every install.
        assert policy.parse_value("pin_only", "no") is False
        assert policy.parse_value("pin_only", "off") is False
        assert policy.parse_value("pin_only", "0") is False
        assert policy.parse_value("pin_only", "yes") is True

    def test_a_bad_boolean_is_refused_at_the_setter(self, sandbox):
        with pytest.raises(typedvalue.ValueTypeError):
            policy.parse_value("pin_only", "maybe")

    def test_a_bad_number_is_refused_at_the_setter(self, sandbox):
        with pytest.raises(typedvalue.ValueTypeError):
            policy.parse_value("max_skills", "abc")
        with pytest.raises(typedvalue.ValueTypeError):
            policy.parse_value("min_quality_score", "abc")

    def test_a_bare_number_for_a_list_key_is_a_one_item_list(self, sandbox):
        assert policy.parse_value("blocked_skills", "42") == ["42"]

    def test_a_comma_list_still_works(self, sandbox):
        assert policy.parse_value("blocked_skills", "a,b") == ["a", "b"]


class TestLoadCoercesStoredValues:
    def test_a_string_boolean_written_by_hand_is_read_as_the_boolean(self, sandbox):
        write_policy_json({"pin_only": "no"})
        assert policy.load()["pin_only"] is False
        assert policy.check_install(GOOD_ENTRY, 0) == []

    def test_a_string_number_written_by_hand_is_read_as_the_number(self, sandbox):
        write_policy_json({"max_skills": "2"})
        assert policy.load()["max_skills"] == 2
        assert policy.check_install(GOOD_ENTRY, 2) == ["max_skills limit (2) reached"]

    def test_an_unreadable_value_falls_back_to_the_default(self, sandbox):
        # A caller mid-install must get a working policy, not a traceback.
        write_policy_json({"max_skills": "abc", "blocked_skills": 42})
        pol = policy.load()
        assert pol["max_skills"] is None
        assert pol["blocked_skills"] == []
        assert policy.check_install(GOOD_ENTRY, 500) == []

    def test_a_good_value_beside_a_bad_one_still_applies(self, sandbox):
        write_policy_json({"max_skills": "abc", "pin_only": True})
        assert policy.load()["pin_only"] is True

    def test_unknown_keys_are_carried_through_untouched(self, sandbox):
        write_policy_json({"rogue": {"deep": 1}})
        assert policy.load()["rogue"] == {"deep": 1}

    def test_a_non_dict_file_reads_as_no_overrides(self, sandbox):
        paths.ensure_dirs()
        paths.policy_path().write_text("[1, 2]", encoding="utf-8")
        assert policy.load() == policy.DEFAULTS


class TestInvalidValues:
    def test_a_clean_file_reports_nothing(self, sandbox):
        write_policy_json({"pin_only": True, "max_skills": 5})
        assert policy.invalid_values() == []

    def test_a_missing_file_reports_nothing(self, sandbox):
        assert policy.invalid_values() == []

    def test_a_coercible_string_is_not_an_error(self, sandbox):
        write_policy_json({"pin_only": "no"})
        assert policy.invalid_values() == []

    def test_each_bad_value_is_named_with_what_was_expected(self, sandbox):
        write_policy_json({"max_skills": "abc", "blocked_skills": 42})
        bad = {k: (v, e) for k, v, e in policy.invalid_values()}
        assert set(bad) == {"max_skills", "blocked_skills"}
        assert bad["max_skills"][0] == "abc"
        assert bad["max_skills"][1] == typedvalue.describe(typedvalue.INT_OR_NONE)
        assert bad["blocked_skills"][0] == 42
        assert bad["blocked_skills"][1] == typedvalue.describe(typedvalue.LIST)

    def test_unknown_keys_are_not_reported_as_invalid(self, sandbox):
        write_policy_json({"rogue": "anything"})
        assert policy.invalid_values() == []
