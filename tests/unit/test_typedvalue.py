# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/typedvalue.py — read a string at a key's type.

The bug this module exists for is not the crash, it is the SILENT INVERSION:
`policy set pin_only no` stored the string "no", which is truthy, so boost
froze every install for a user who had just turned the freeze off. So the
boolean tables are asserted word by word rather than "it parses".
"""
from __future__ import annotations

import pytest

from boost_cli.core import typedvalue as tv


class TestSpecNames:
    def test_the_names_are_stable(self):
        # A spec name is user-visible: it is the placeholder the CLI hint
        # prints, as in `boost policy set pin_only <bool>`.
        assert (tv.BOOL, tv.INT, tv.INT_OR_NONE, tv.LIST,
                tv.STR, tv.DICT, tv.ANY) == (
            "bool", "int", "int-or-null", "list", "str", "dict", "any")

    def test_the_names_are_distinct(self):
        names = (tv.BOOL, tv.INT, tv.INT_OR_NONE, tv.LIST,
                 tv.STR, tv.DICT, tv.ANY)
        assert len(set(names)) == len(names)


class TestSpecFor:
    @pytest.mark.parametrize("default,spec", [
        (True, tv.BOOL), (False, tv.BOOL),
        (0, tv.INT), (8787, tv.INT), (-3, tv.INT),
        ([], tv.LIST), (["a"], tv.LIST),
        ({}, tv.DICT), ({"a": 1}, tv.DICT),
        ("", tv.STR), ("text", tv.STR),
        (None, tv.ANY),
    ])
    def test_default_value_names_its_own_type(self, default, spec):
        assert tv.spec_for(default) == spec

    def test_bool_is_tested_before_int(self):
        # bool subclasses int, so the natural isinstance order types every
        # boolean key as a number — and then `pin_only 2` is a legal value.
        assert tv.spec_for(True) != tv.INT
        assert tv.spec_for(False) != tv.INT

    def test_a_float_default_is_untyped_rather_than_an_int(self):
        # No key defaults to a float today; typing one as INT would silently
        # truncate. ANY keeps the old lenient behaviour instead.
        assert tv.spec_for(1.5) == tv.ANY


class TestBool:
    @pytest.mark.parametrize("word", ["true", "yes", "on", "1",
                                      "TRUE", "Yes", "ON", " true "])
    def test_true_words(self, word):
        assert tv.coerce("pin_only", word, tv.BOOL) is True

    @pytest.mark.parametrize("word", ["false", "no", "off", "0",
                                      "FALSE", "No", "OFF", " false "])
    def test_false_words(self, word):
        assert tv.coerce("pin_only", word, tv.BOOL) is False

    @pytest.mark.parametrize("word", ["maybe", "", "2", "y", "n", "nope"])
    def test_anything_else_is_refused(self, word):
        with pytest.raises(tv.ValueTypeError):
            tv.coerce("pin_only", word, tv.BOOL)

    def test_the_words_are_disjoint(self):
        assert not (tv.TRUE_WORDS & tv.FALSE_WORDS)


class TestInt:
    @pytest.mark.parametrize("raw,value", [
        ("0", 0), ("60", 60), ("-3", -3), (" 42 ", 42)])
    def test_whole_numbers(self, raw, value):
        assert tv.coerce("min_quality_score", raw, tv.INT) == value

    @pytest.mark.parametrize("raw", ["abc", "", "6.5", "1e3", "0x10", "  "])
    def test_non_numbers_are_refused(self, raw):
        with pytest.raises(tv.ValueTypeError):
            tv.coerce("min_quality_score", raw, tv.INT)

    def test_the_error_names_the_key_and_the_type(self):
        with pytest.raises(tv.ValueTypeError) as e:
            tv.coerce("min_quality_score", "abc", tv.INT)
        assert e.value.key == "min_quality_score"
        assert e.value.raw == "abc"
        assert e.value.spec == tv.INT
        assert e.value.expected == "a whole number"
        # The whole message, not a substring: it is what the CLI frames.
        assert str(e.value) == "min_quality_score expects a whole number, got 'abc'"


class TestIntOrNone:
    @pytest.mark.parametrize("raw", ["", "null", "none", "NULL", " None "])
    def test_the_no_limit_words(self, raw):
        assert tv.coerce("max_skills", raw, tv.INT_OR_NONE) is None

    def test_a_number_is_a_cap(self):
        assert tv.coerce("max_skills", "5", tv.INT_OR_NONE) == 5

    def test_a_non_number_is_refused_not_read_as_no_limit(self):
        # The failure mode being closed: `policy set max_skills abc` exited 0
        # and the next install died on int('abc'). Reading it as "no cap"
        # would be the same silent-wrong-answer in a different costume.
        with pytest.raises(tv.ValueTypeError) as e:
            tv.coerce("max_skills", "abc", tv.INT_OR_NONE)
        assert e.value.expected == "a whole number, or null for no limit"


class TestList:
    def test_a_json_array_is_taken_as_written(self):
        assert tv.coerce("blocked_skills", '["a", "b"]', tv.LIST) == ["a", "b"]
        assert tv.coerce("taps", "[1, 2]", tv.LIST) == [1, 2]

    def test_a_comma_list_is_split_and_stripped(self):
        assert tv.coerce("blocked_skills", "a, b ,c", tv.LIST) == ["a", "b", "c"]

    def test_empty_pieces_are_dropped(self):
        assert tv.coerce("blocked_skills", "a,,b,", tv.LIST) == ["a", "b"]
        assert tv.coerce("blocked_skills", "", tv.LIST) == []

    def test_a_bare_number_becomes_a_one_item_list(self):
        # `policy set blocked_skills 42` used to store the int 42, and
        # `name in 42` is "TypeError: argument of type 'int' is not iterable"
        # out of policy check AND out of install.
        assert tv.coerce("blocked_skills", "42", tv.LIST) == ["42"]

    def test_a_json_object_is_not_mistaken_for_a_list(self):
        assert tv.coerce("blocked_skills", '{"a": 1}', tv.LIST) == ['{"a": 1}']

    def test_a_list_key_never_raises(self):
        # Its documented surface is a comma list, so every string is a legal
        # one. This is the one spec with no failure mode.
        for raw in ("", "x", "42", "true", "{", "[1,"):
            assert isinstance(tv.coerce("blocked_skills", raw, tv.LIST), list)


class TestStr:
    def test_a_string_key_keeps_the_text_verbatim(self):
        assert tv.coerce("ai.model", "plain", tv.STR) == "plain"

    def test_a_numeric_looking_string_stays_a_string(self):
        # json.loads used to turn `config set ai.model 42` into the int 42.
        assert tv.coerce("ai.model", "42", tv.STR) == "42"
        assert tv.coerce("logging.level", "true", tv.STR) == "true"


class TestDict:
    def test_a_json_object(self):
        assert tv.coerce("ai", '{"enabled": false}', tv.DICT) == {"enabled": False}

    @pytest.mark.parametrize("raw", ["[]", "3", "not json", '"a"'])
    def test_anything_that_is_not_an_object_is_refused(self, raw):
        with pytest.raises(tv.ValueTypeError):
            tv.coerce("ai", raw, tv.DICT)


class TestAny:
    def test_json_when_it_parses(self):
        assert tv.coerce("custom.flag", "true", tv.ANY) is True
        assert tv.coerce("custom.n", "42", tv.ANY) == 42
        assert tv.coerce("custom.l", "[1]", tv.ANY) == [1]

    def test_the_raw_string_otherwise(self):
        assert tv.coerce("custom.s", "plain", tv.ANY) == "plain"

    def test_an_unknown_spec_falls_back_to_lenient(self):
        assert tv.coerce("k", "true", "no-such-spec") is True


class TestDescribe:
    # Pinned verbatim, not by substring: the phrase IS the error message a
    # user reads, and "close enough" is how a hint drifts out of usefulness.
    @pytest.mark.parametrize("spec,phrase", [
        (tv.BOOL, "a boolean (true/false, yes/no, on/off, 1/0)"),
        (tv.INT, "a whole number"),
        (tv.INT_OR_NONE, "a whole number, or null for no limit"),
        (tv.LIST, "a comma-separated list, or a JSON array"),
        (tv.STR, "a string"),
        (tv.DICT, "a JSON object"),
        (tv.ANY, "any value"),
    ])
    def test_the_phrase_for_each_spec(self, spec, phrase):
        assert tv.describe(spec) == phrase

    def test_the_phrases_are_distinct(self):
        specs = [tv.BOOL, tv.INT, tv.INT_OR_NONE, tv.LIST, tv.STR, tv.DICT]
        assert len({tv.describe(s) for s in specs}) == len(specs)

    def test_an_unknown_spec_describes_rather_than_raising(self):
        # A wrong hint must never be what turns a working setter into a crash.
        assert tv.describe("no-such-spec") == tv.describe(tv.ANY)

    def test_the_boolean_phrase_lists_the_words_a_user_can_retype(self):
        phrase = tv.describe(tv.BOOL)
        for word in tv.TRUE_WORDS | tv.FALSE_WORDS:
            assert word in phrase


class TestMatches:
    @pytest.mark.parametrize("value,spec,ok", [
        (True, tv.BOOL, True), ("true", tv.BOOL, False), (1, tv.BOOL, False),
        (3, tv.INT, True), (True, tv.INT, False), ("3", tv.INT, False),
        (None, tv.INT, False),
        (None, tv.INT_OR_NONE, True), (3, tv.INT_OR_NONE, True),
        (True, tv.INT_OR_NONE, False), ("3", tv.INT_OR_NONE, False),
        ([], tv.LIST, True), ("a,b", tv.LIST, False), (42, tv.LIST, False),
        ("s", tv.STR, True), (3, tv.STR, False),
        ({}, tv.DICT, True), ([], tv.DICT, False),
        (object(), tv.ANY, True),
    ])
    def test_already_typed_values(self, value, spec, ok):
        assert tv.matches(value, spec) is ok

    def test_a_bool_is_not_a_number_even_though_python_says_so(self):
        # `serve.port: true` is not port 1.
        assert tv.matches(True, tv.INT) is False
        assert tv.matches(False, tv.INT_OR_NONE) is False


class TestAdapt:
    def test_a_matching_value_is_returned_untouched(self):
        value = ["a"]
        assert tv.adapt("blocked_skills", value, tv.LIST) is value

    def test_a_string_gets_one_chance_to_be_re_read(self):
        # This is what rescues a hand-edited (or older-boost) policy.json.
        assert tv.adapt("pin_only", "no", tv.BOOL) is False
        assert tv.adapt("serve.port", "8080", tv.INT) == 8080

    def test_a_string_that_cannot_be_re_read_still_raises(self):
        with pytest.raises(tv.ValueTypeError):
            tv.adapt("serve.port", "abc", tv.INT)

    def test_a_non_string_mismatch_is_refused_rather_than_guessed(self):
        # Turning 42 into [42] or "42" would be inventing data, not reading it.
        with pytest.raises(tv.ValueTypeError) as e:
            tv.adapt("blocked_skills", 42, tv.LIST)
        assert e.value.raw == 42
        with pytest.raises(tv.ValueTypeError):
            tv.adapt("pin_only", 1, tv.BOOL)

    def test_none_is_not_quietly_accepted_for_a_typed_key(self):
        with pytest.raises(tv.ValueTypeError):
            tv.adapt("pin_only", None, tv.BOOL)
