# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/policy.py — governance rules for installs."""
from __future__ import annotations

import json

import pytest

from boost_cli.core import config, jsonstate, paths, policy, typedvalue

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

    @pytest.mark.parametrize("raw", [b"\xff\xfe", b"[1]"])
    def test_an_unusable_file_gives_defaults_not_a_crash(self, sandbox, raw):
        # Non-UTF-8 bytes raised past the JSONDecodeError guard and took
        # `boost install` down at exit 70.
        paths.ensure_dirs()
        paths.policy_path().write_bytes(raw)
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

    def test_blocked_skills_tap_qualified(self, sandbox):
        # `install` takes `tap:name`; a blocklist entry written that way used
        # to be stored with a check mark and never match.
        set_policy(blocked_skills=["acme/skills:brainstorming"])
        assert policy.check_install(GOOD_ENTRY, 0) == [
            "skill 'brainstorming' is on the blocklist"]
        assert policy.check_install(
            {**GOOD_ENTRY, "tap": "other/tap"}, 0) == []

    def test_is_blocked(self):
        assert policy.is_blocked("x", "fx", ["x"]) is True
        assert policy.is_blocked("x", "fx", ["fx:x"]) is True
        assert policy.is_blocked("x", "gx", ["fx:x"]) is False
        assert policy.is_blocked("x", "fx", ["fx:y", "y"]) is False
        assert policy.is_blocked("x", None, [":x"]) is False
        assert policy.is_blocked("x", "", [":x"]) is False
        assert policy.is_blocked("x", "fx", None) is False

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


class TestCheckInstalledVersion:
    """Retrospective require_version, run by `boost policy check` against an
    already-installed lock entry rather than a catalog entry at install time.
    """

    def test_off_by_default(self, sandbox):
        assert policy.check_installed_version({"version": ""}) == []

    def test_missing_or_placeholder_version_violates(self, sandbox):
        set_policy(require_version=True)
        msg = "skill has no version (required by policy)"
        assert policy.check_installed_version({"version": ""}) == [msg]
        assert policy.check_installed_version({"version": "0.0.0"}) == [msg]
        assert policy.check_installed_version({"version": None}) == [msg]
        assert policy.check_installed_version({}) == [msg]

    def test_real_version_allowed(self, sandbox):
        set_policy(require_version=True)
        assert policy.check_installed_version({"version": "1.4.0"}) == []

    def test_master_switch_bypasses(self, sandbox):
        set_policy(require_version=True)
        cfg = config.load()
        cfg["policy_enforce"] = False
        config.save(cfg)
        assert policy.check_installed_version({"version": ""}) == []


class TestCheckInstalledMeta:
    """Retrospective require_description + denied_capabilities, run against a
    skill's store copy (frontmatter + body) rather than a catalog entry.
    """

    def test_off_by_default(self, sandbox):
        assert policy.check_installed_meta({"description": ""}, "body") == []

    def test_require_description(self, sandbox):
        set_policy(require_description=True)
        msg = "skill has no description (required by policy)"
        assert policy.check_installed_meta({"description": ""}, "b") == [msg]
        assert policy.check_installed_meta({}, "b") == [msg]
        assert policy.check_installed_meta(
            {"description": "does things"}, "b") == []

    def test_folds_in_check_capabilities(self, sandbox):
        set_policy(denied_capabilities=["network"])
        v = policy.check_installed_meta(
            {"description": "x", "capabilities": ["network"]}, "body")
        assert v == ["declares the 'network' capability, denied by policy"]

    def test_both_checks_accumulate(self, sandbox):
        set_policy(require_description=True, denied_capabilities=["network"])
        v = policy.check_installed_meta({"capabilities": ["network"]}, "body")
        assert v == [
            "skill has no description (required by policy)",
            "declares the 'network' capability, denied by policy",
        ]

    def test_master_switch_bypasses(self, sandbox):
        set_policy(require_description=True)
        cfg = config.load()
        cfg["policy_enforce"] = False
        config.save(cfg)
        assert policy.check_installed_meta({"description": ""}, "b") == []


class TestMaxSkillsViolation:
    """The environment-wide max_skills cap, reported once — not once per
    installed skill, unlike every other check in this module.
    """

    def test_off_by_default(self, sandbox):
        assert policy.max_skills_violation(500) is None

    def test_none_means_unlimited(self, sandbox):
        set_policy(max_skills=None)
        assert policy.max_skills_violation(10_000) is None

    def test_under_cap_allowed(self, sandbox):
        set_policy(max_skills=3)
        assert policy.max_skills_violation(2) is None
        assert policy.max_skills_violation(3) is None

    def test_over_cap_violates(self, sandbox):
        set_policy(max_skills=3)
        assert policy.max_skills_violation(4) == (
            "max_skills limit (3) exceeded (4 installed)")

    def test_master_switch_bypasses(self, sandbox):
        set_policy(max_skills=0)
        cfg = config.load()
        cfg["policy_enforce"] = False
        config.save(cfg)
        assert policy.max_skills_violation(999) is None


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

    def test_corrupt_policy_refuses_the_tap(self, sandbox, tmp_path):
        p = paths.policy_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"require_signed_taps": true', encoding="utf-8")
        clone = tmp_path / "c"
        clone.mkdir()
        err = jsonstate.read_object(p)[1]
        assert policy.check_tap_signing(clone) == [
            "%s — boost cannot read the policy, so it will not tap until the "
            "file is repaired" % err]

    def test_corrupt_policy_tap_honours_enforce_switch(self, sandbox, tmp_path):
        p = paths.policy_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"require_signed_taps": true', encoding="utf-8")
        cfg = config.load()
        cfg["policy_enforce"] = False
        config.save(cfg)
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


class TestRanges:
    """The type alone let `policy set min_quality_score 500` and `max_skills -1`
    through with rc 0; the next audit or install then failed against a limit
    nothing could meet."""

    @pytest.mark.parametrize("raw", ["0", "100", "60"])
    def test_a_score_inside_0_to_100_is_taken(self, sandbox, raw):
        assert policy.parse_value("min_quality_score", raw) == int(raw)

    @pytest.mark.parametrize("raw", ["-1", "101", "500", "-5"])
    def test_a_score_outside_0_to_100_is_refused(self, sandbox, raw):
        with pytest.raises(typedvalue.ValueTypeError) as e:
            policy.parse_value("min_quality_score", raw)
        assert e.value.key == "min_quality_score"
        assert e.value.raw == raw
        assert e.value.spec == typedvalue.INT
        assert e.value.expected == "a whole number from 0 to 100"
        assert str(e.value) == ("min_quality_score expects a whole number "
                                "from 0 to 100, got %r" % raw)

    @pytest.mark.parametrize("raw, want", [("0", 0), ("1", 1), ("99999", 99999),
                                           ("null", None)])
    def test_a_cap_of_zero_or_more_or_null_is_taken(self, sandbox, raw, want):
        assert policy.parse_value("max_skills", raw) == want

    def test_a_negative_cap_is_refused(self, sandbox):
        with pytest.raises(typedvalue.ValueTypeError) as e:
            policy.parse_value("max_skills", "-1")
        assert e.value.expected == ("a whole number of 0 or more, "
                                    "or null for no limit")

    def test_an_unbounded_key_is_untouched(self, sandbox):
        assert policy.parse_value("pin_only", "no") is False
        assert policy.parse_value("blocked_skills", "-1") == ["-1"]

    def test_a_stored_out_of_range_value_falls_back_and_is_named(self, sandbox):
        write_policy_json({"min_quality_score": 500, "max_skills": -1})
        pol = policy.load()
        assert pol["min_quality_score"] == 0
        assert pol["max_skills"] is None
        # Read as the default for display, but enforcement refuses: the
        # default is the permissive value, not the one the user wrote.
        assert policy.check_install(GOOD_ENTRY, 3) == [policy.invalid_violation()]
        assert sorted(policy.invalid_values()) == [
            ("max_skills", -1, "a whole number of 0 or more, or null for no limit"),
            ("min_quality_score", 500, "a whole number from 0 to 100")]

    def test_a_stored_string_out_of_range_is_refused_too(self, sandbox):
        write_policy_json({"min_quality_score": "101"})
        assert policy.load()["min_quality_score"] == 0
        assert policy.invalid_values() == [
            ("min_quality_score", "101", "a whole number from 0 to 100")]

    def test_stored_bounds_themselves_are_kept(self, sandbox):
        write_policy_json({"min_quality_score": 100, "max_skills": 0})
        pol = policy.load()
        assert (pol["min_quality_score"], pol["max_skills"]) == (100, 0)
        assert policy.invalid_values() == []


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
        # No traceback — and no install either: the refusal names both keys.
        v = policy.check_install(GOOD_ENTRY, 500)
        assert v == [policy.invalid_violation()]
        assert "max_skills" in v[0] and "blocked_skills" in v[0]

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


TRUNCATED = '{"blocked_skills": ["tdd-workflow"]'
TRAILING_COMMA = '{"blocked_skills": ["tdd-workflow"], "allowed_taps": ["fx"],}'


def _corrupt(raw: str):
    paths.ensure_dirs()
    p = paths.policy_path()
    p.write_text(raw, encoding="utf-8")
    return p


def _err(capsys) -> str:
    return " ".join(capsys.readouterr().err.split())


class TestCorruptPolicy:
    """A policy.json that does not parse is not "no policy": fail closed."""

    @pytest.mark.parametrize("raw", [TRUNCATED, TRAILING_COMMA])
    def test_check_names_the_parse_error(self, sandbox, raw):
        p = _corrupt(raw)
        err = policy.check()
        assert err is not None
        assert err.startswith("%s: invalid JSON (" % p)

    def test_check_is_none_when_missing_or_valid(self, sandbox):
        assert policy.check() is None
        set_policy(pin_only=True)
        assert policy.check() is None
        assert policy.corrupt_violation() is None

    @pytest.mark.parametrize("raw", [TRUNCATED, TRAILING_COMMA])
    def test_install_is_refused(self, sandbox, raw):
        _corrupt(raw)
        assert policy.check_install(GOOD_ENTRY, 0) == [
            "%s — boost cannot read the policy, so it will not install until "
            "the file is repaired" % policy.check()]

    def test_policy_enforce_false_still_bypasses(self, sandbox):
        cfg = config.load()
        cfg["policy_enforce"] = False
        config.save(cfg)
        _corrupt(TRUNCATED)
        assert policy.check_install(GOOD_ENTRY, 0) == []
        # The violation itself does not depend on the switch.
        assert policy.corrupt_violation() is not None

    def test_load_warns_once_per_process(self, sandbox, capsys):
        p = _corrupt(TRUNCATED)
        assert policy.load() == policy.DEFAULTS
        policy.load()
        policy.invalid_values()
        err = _err(capsys)
        assert err.count("reading the policy as defaults") == 1
        assert ("%s: invalid JSON" % p) in err
        assert ("installs are refused until it is repaired, and the next "
                "`boost policy set` moves it aside to policy.json.corrupt") in err

    def test_a_valid_file_does_not_warn(self, sandbox, capsys):
        set_policy(pin_only=True)
        policy.load()
        assert capsys.readouterr().err == ""

    def test_save_quarantines_the_corrupt_file(self, sandbox, capsys):
        p = _corrupt(TRAILING_COMMA)
        policy.save({"require_description": True})
        assert (p.parent / "policy.json.corrupt").read_text(
            encoding="utf-8") == TRAILING_COMMA
        assert json.loads(p.read_text(encoding="utf-8"))[
            "require_description"] is True
        assert ("%s was corrupt and has been moved to %s before writing the "
                "new policy" % (p, p.parent / "policy.json.corrupt")) \
            in _err(capsys)

    def test_save_never_overwrites_an_earlier_quarantine(self, sandbox):
        p = _corrupt(TRUNCATED)
        policy.save({})
        _corrupt(TRAILING_COMMA)
        policy.save({})
        assert (p.parent / "policy.json.corrupt").read_text(
            encoding="utf-8") == TRUNCATED
        assert (p.parent / "policy.json.corrupt.2").read_text(
            encoding="utf-8") == TRAILING_COMMA

    def test_save_over_a_valid_file_quarantines_nothing(self, sandbox):
        set_policy(pin_only=True)
        set_policy(pin_only=False)
        assert sorted(q.name for q in paths.policy_path().parent.iterdir()
                      if q.name.startswith("policy")) == ["policy.json"]


# --------------------------------------- unreadable values fail closed

LIST_PHRASE = "a comma-separated list, or a JSON array"
BOOL_PHRASE = "a boolean (true/false, yes/no, on/off, 1/0)"
CAP_PHRASE = "a whole number, or null for no limit"


class TestInvalidViolation:
    """A value unreadable at its type reads as its (permissive) default for
    display; enforcement refuses instead of obeying that default."""

    def test_none_when_every_value_reads(self, sandbox):
        assert policy.invalid_violation() is None
        set_policy(pin_only=True, max_skills=5)
        assert policy.invalid_violation() is None
        assert policy.unreadable_violation() is None

    def test_one_key_is_named_with_its_type(self, sandbox):
        write_policy_json({"blocked_skills": {"cowboy-coding": True}})
        assert policy.invalid_violation() == (
            'policy.json holds blocked_skills = {"cowboy-coding": true}, which '
            "expects %s — boost cannot read it, so it will not install until "
            "it is fixed with `boost policy set` or `boost policy unset`"
            % LIST_PHRASE)

    def test_several_keys_are_all_named(self, sandbox):
        write_policy_json({"pin_only": "frozen", "max_skills": "2.5"})
        assert policy.invalid_violation("tap") == (
            'policy.json holds pin_only = "frozen", which expects %s; '
            'max_skills = "2.5", which expects %s — boost cannot read them, '
            "so it will not tap until they are fixed with `boost policy set` "
            "or `boost policy unset`" % (BOOL_PHRASE, CAP_PHRASE))

    def test_unreadable_prefers_the_parse_error(self, sandbox):
        _corrupt(TRUNCATED)
        assert policy.unreadable_violation() == policy.corrupt_violation()
        assert policy.unreadable_violation() is not None

    def test_unreadable_falls_back_to_the_invalid_value(self, sandbox):
        write_policy_json({"pin_only": "frozen"})
        assert policy.corrupt_violation() is None
        assert policy.unreadable_violation() == policy.invalid_violation()
        assert policy.unreadable_violation() is not None

    @pytest.mark.parametrize("raw", [
        {"blocked_skills": {"cowboy-coding": True}},
        {"pin_only": "frozen"},
        {"max_skills": "2.5"},
        {"blocked_taps": 7},
        {"require_signed_taps": "maybe"},
    ])
    def test_each_bad_key_blocks_install(self, sandbox, raw):
        write_policy_json(raw)
        assert policy.check_install(GOOD_ENTRY, 0) == [policy.invalid_violation()]

    def test_a_bad_require_signed_taps_refuses_the_tap(self, sandbox, tmp_path):
        write_policy_json({"require_signed_taps": "maybe"})
        assert policy.check_tap_signing(tmp_path) == [
            policy.invalid_violation("tap")]

    def test_enforce_switch_still_bypasses(self, sandbox, tmp_path):
        cfg = config.load()
        cfg["policy_enforce"] = False
        config.save(cfg)
        write_policy_json({"pin_only": "frozen"})
        assert policy.check_install(GOOD_ENTRY, 0) == []
        assert policy.check_tap_signing(tmp_path) == []
        assert policy.check_source("evil/repo", tmp_path) == []


class TestMutateKeepsUnreadableValues:
    def test_setting_another_key_keeps_the_bad_value_verbatim(self, sandbox):
        write_policy_json({"blocked_skills": {"cowboy-coding": True},
                           "pin_only": "frozen"})
        policy.set_key("min_quality_score", 5)
        stored = json.loads(paths.policy_path().read_text(encoding="utf-8"))
        assert stored["blocked_skills"] == {"cowboy-coding": True}
        assert stored["pin_only"] == "frozen"
        assert stored["min_quality_score"] == 5
        assert policy.check_install(GOOD_ENTRY, 0) == [policy.invalid_violation()]

    def test_setting_the_bad_key_repairs_it(self, sandbox):
        write_policy_json({"blocked_skills": {"cowboy-coding": True},
                           "pin_only": "frozen"})
        policy.set_key("blocked_skills", ["cowboy-coding"])
        assert [k for k, _v, _e in policy.invalid_values()] == ["pin_only"]
        policy.set_key("pin_only", False)
        assert policy.invalid_values() == []
        assert policy.check_install(
            dict(GOOD_ENTRY, name="cowboy-coding"), 0) == [
            "skill 'cowboy-coding' is on the blocklist"]


class TestCheckSource:
    def test_source_violations_default_allow(self, sandbox):
        assert policy.source_violations("evil/repo", policy.load()) == []

    def test_allowlist_has_no_local_exemption(self, sandbox):
        pol = set_policy(allowed_taps=["gov"])
        assert policy.source_violations("evil/repo", pol) == [
            "source 'evil/repo' is not on the allowlist"]
        assert policy.source_violations("local", pol) == [
            "source 'local' is not on the allowlist"]
        assert policy.source_violations("gov", pol) == []

    def test_blocklisted_source(self, sandbox):
        pol = set_policy(blocked_taps=["evil/repo"])
        assert policy.source_violations("evil/repo", pol) == [
            "source 'evil/repo' is blocked"]
        assert policy.source_violations("good/repo", pol) == []

    def test_both_accumulate(self, sandbox):
        pol = set_policy(blocked_taps=["evil/repo"], allowed_taps=["gov"])
        assert policy.source_violations("evil/repo", pol) == [
            "source 'evil/repo' is blocked",
            "source 'evil/repo' is not on the allowlist"]

    def test_check_source_folds_in_signing(self, sandbox, tmp_path):
        set_policy(allowed_taps=["gov"], require_signed_taps=True)
        assert policy.check_source("evil/repo", tmp_path) == [
            "source 'evil/repo' is not on the allowlist",
            "source is unsigned (no .boost/tap.manifest.minisig), and policy "
            "requires a trusted signature"]

    def test_check_source_allows_a_signed_allowed_source(self, sandbox,
                                                         tmp_path, signer):
        from boost_cli.core import provenance
        set_policy(allowed_taps=["gov"], require_signed_taps=True)
        provenance.add_trusted_key("acme", signer.public_key_text())
        signer.write_signed(tmp_path)
        assert policy.check_source("gov", tmp_path) == []

    def test_check_source_fails_closed_on_an_unreadable_policy(self, sandbox,
                                                               tmp_path):
        write_policy_json({"allowed_taps": {"gov": True}})
        assert policy.check_source("gov", tmp_path) == [
            policy.invalid_violation()]

    def test_tap_wording_is_unchanged(self, sandbox, tmp_path):
        set_policy(require_signed_taps=True)
        assert policy.check_tap_signing(tmp_path) == [
            "tap is unsigned (no .boost/tap.manifest.minisig), and policy "
            "requires a trusted signature"]
