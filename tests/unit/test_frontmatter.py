# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/frontmatter.py — the SKILL.md YAML-subset parser."""
from __future__ import annotations

import pytest

from boost_cli.core import frontmatter


class TestSplit:
    def test_no_frontmatter(self):
        assert frontmatter.split("# Just markdown") == ("", "# Just markdown")

    def test_basic_split(self):
        block, body = frontmatter.split("---\nname: x\n---\n\n# Body")
        assert block == "name: x"
        assert body == "# Body"

    def test_unterminated_fence_is_body(self):
        text = "---\nname: x\nno closing fence"
        assert frontmatter.split(text) == ("", text)

    def test_dots_terminator(self):
        block, _ = frontmatter.split("---\nname: x\n...\nbody")
        assert block == "name: x"

    def test_leading_content_means_no_frontmatter(self):
        text = "hello\n---\nname: x\n---"
        assert frontmatter.split(text) == ("", text)


class TestUnclosed:
    """`split()` reads a fence that opens and never closes as "no frontmatter
    at all" — the same outcome as a file with no fence to begin with. This is
    the check a caller uses to tell those two apart before reporting one
    diagnosis instead of three symptoms of it (see util.score_skill)."""

    def test_open_fence_no_close_is_unclosed(self):
        assert frontmatter.unclosed(
            "---\nname: x\ndescription: y\nno closing fence\n") is True

    def test_closed_fence_is_not_unclosed(self):
        assert frontmatter.unclosed("---\nname: x\n---\nbody") is False

    def test_dots_terminator_counts_as_closed(self):
        assert frontmatter.unclosed("---\nname: x\n...\nbody") is False

    def test_no_fence_at_all_is_not_unclosed(self):
        assert frontmatter.unclosed("just a plain markdown body\n") is False

    def test_leading_content_before_dashes_is_not_unclosed(self):
        # Same case split() treats as "no frontmatter" — the first line isn't
        # a bare "---", so this was never an attempt to open a fence.
        assert frontmatter.unclosed("hello\n---\nname: x\n") is False

    def test_empty_text_is_not_unclosed(self):
        assert frontmatter.unclosed("") is False

    def test_only_the_opening_fence_with_nothing_after(self):
        assert frontmatter.unclosed("---\n") is True

    def test_fence_line_with_trailing_whitespace_still_closes(self):
        assert frontmatter.unclosed("---\nname: x\n---  \nbody") is False


class TestParse:
    def test_scalars(self):
        meta, _ = frontmatter.parse(
            "---\nname: brainstorming\nversion: 1.4.0\ncount: 3\n"
            "ratio: 1.5\nflag: true\noff: false\nnothing: null\n---\nbody")
        assert meta["name"] == "brainstorming"
        assert meta["version"] == "1.4.0"   # stays a string (semver-ish)
        assert meta["count"] == 3
        assert meta["ratio"] == 1.5
        assert meta["flag"] is True
        assert meta["off"] is False
        assert meta["nothing"] is None

    def test_quoted_strings_keep_specials(self):
        meta, _ = frontmatter.parse('---\ntitle: "a: b, c"\nalt: \'x #y\'\n---\n')
        assert meta["title"] == "a: b, c"
        assert meta["alt"] == "x #y"

    def test_folded_continuation(self):
        meta, _ = frontmatter.parse(
            "---\ndescription: Structured ideation &\n"
            "  divergent-thinking facilitation\n---\n")
        assert meta["description"] == (
            "Structured ideation & divergent-thinking facilitation")

    def test_block_scalar_with_colons(self):
        meta, _ = frontmatter.parse(
            "---\ndescription: |-\n  Reference for the API.\n"
            "  Second line: has a colon.\nversion: 1.0\n---\n")
        assert meta["description"] == (
            "Reference for the API. Second line: has a colon.")
        assert meta["version"] == 1.0

    def test_flow_list(self):
        meta, _ = frontmatter.parse("---\ntags: [a, b, 'c d']\nempty: []\n---\n")
        assert meta["tags"] == ["a", "b", "c d"]
        assert meta["empty"] == []

    def test_block_list(self):
        meta, _ = frontmatter.parse(
            "---\nrequires:\n  - alpha\n  - beta\n---\n")
        assert meta["requires"] == ["alpha", "beta"]

    def test_trailing_comment_stripped(self):
        meta, _ = frontmatter.parse("---\nversion: 1.0.0 # stable\n---\n")
        assert meta["version"] == "1.0.0"

    def test_comment_lines_ignored(self):
        meta, _ = frontmatter.parse("---\n# a comment\nname: x\n---\n")
        assert meta == {"name": "x"}

    def test_body_preserved(self):
        _, body = frontmatter.parse("---\nname: x\n---\n\n# Title\n\ntext\n")
        assert body.startswith("# Title")
        assert "text" in body

    def test_never_raises_on_junk(self):
        meta, body = frontmatter.parse("---\n:::\n[weird\n- orphan item\n---\nb")
        assert isinstance(meta, dict)
        assert body == "b"


class TestMutationHardening:
    """Precision tests targeting mutmut survivor classes."""

    def test_scalar_boundaries(self):
        s = frontmatter._scalar
        assert s('""') == ""            # len == 2 quoted-empty
        assert s("''") == ""
        assert s('"a"') == "a"
        assert s("'\"") == "'\""        # mismatched quotes stay literal
        assert s("  spaced  ") == "spaced"

    def test_scalar_coerces_yaml12_keywords(self):
        s = frontmatter._scalar
        for word, want in [("true", True), ("TRUE", True), ("True", True),
                           ("false", False), ("FALSE", False), ("False", False),
                           ("null", None), ("NULL", None), ("~", None)]:
            assert s(word) is want, word

    def test_scalar_leaves_yaml11_aliases_as_strings(self):
        # yes/no/on/off/none are ordinary words, not booleans/null: a skill
        # legitimately named "none" or tagged "on" must survive as a string.
        s = frontmatter._scalar
        for word in ("yes", "Yes", "on", "no", "off", "OFF", "none", "None"):
            assert s(word) == word, word
        assert s("maybe") == "maybe"     # not a keyword
        assert s("yess") == "yess"

    def test_scalar_numbers(self):
        s = frontmatter._scalar
        assert s("0") == 0
        assert s("-3") == -3
        assert s("0.0") == 0.0
        assert s("1.2.3") == "1.2.3"     # not a float

    def test_scalar_coerces_only_when_lossless(self):
        # A number is coerced only when str() gives back exactly what the author
        # wrote. `1e3` would round-trip as "1000.0", so it stays text — the same
        # rule that keeps `version: 1.10` from silently becoming 1.1.
        s = frontmatter._scalar
        assert s("1e3") == "1e3"
        assert s("1E3") == "1E3"
        assert s("+5") == "+5"           # str(5) is "5", not "+5"
        assert s("1_000") == "1_000"     # int() accepts it, str() does not emit it

    def test_scalar_preserves_lossy_version_strings(self):
        # The bug this rule exists for: float("1.10") is 1.1, so boost read a
        # skill published at 1.10 as 1.1, decided 1.1 < 1.9, and never offered
        # the update. Leading zeros corrupt identically.
        s = frontmatter._scalar
        assert s("1.10") == "1.10"
        assert s("1.50") == "1.50"
        assert s("007") == "007"
        assert s("00") == "00"

    def test_scalar_still_coerces_the_lossless_cases(self):
        # The narrowing must not turn every number into a string — plain
        # integers and canonical floats still come back as numbers.
        s = frontmatter._scalar
        assert s("42") == 42 and isinstance(s("42"), int)
        assert s("1.0") == 1.0 and isinstance(s("1.0"), float)
        assert s(" 42 ") == 42           # surrounding whitespace is stripped first

    def test_split_commas_quoted_commas(self):
        meta, _ = frontmatter.parse('---\ntags: [a, "b, c", d]\n---\n')
        assert meta["tags"] == ["a", "b, c", "d"]

    def test_split_commas_trailing_and_empty(self):
        meta, _ = frontmatter.parse("---\ntags: [a, b,]\nnone: [ ]\n---\n")
        assert meta["tags"] == ["a", "b"]
        assert meta["none"] == []

    def test_fence_must_be_exactly_dashes(self):
        # "---abc" is not a fence: the whole text is body
        text = "---abc\n---\nbody"
        assert frontmatter.parse(text) == ({}, text)

    def test_orphan_list_item_never_creates_keys(self):
        meta, _ = frontmatter.parse("---\n- orphan\nname: x\n- tail\n---\n")
        assert meta == {"name": ["x", "tail"]} or meta == {"name": "x"} \
            or set(meta) == {"name"}
        assert "" not in meta

    def test_scalar_promoted_to_list_by_block_items(self):
        meta, _ = frontmatter.parse("---\nreq: first\n  - second\n---\n")
        # existing scalar + block items -> list starting with the scalar
        assert meta["req"] == ["first", "second"]

    def test_empty_value_then_block_items(self):
        meta, _ = frontmatter.parse("---\nreq:\n  - a\n---\n")
        assert meta["req"] == ["a"]

    def test_block_scalar_ends_on_dedent(self):
        meta, _ = frontmatter.parse(
            "---\ndesc: |-\n  line one\nafter: 1\n---\n")
        assert meta["desc"] == "line one"
        assert meta["after"] == 1

    def test_block_scalar_all_indicators(self):
        for ind in ("|", "|-", "|+", ">", ">-", ">+"):
            meta, _ = frontmatter.parse(
                "---\ndesc: %s\n  folded text\n---\n" % ind)
            assert meta["desc"] == "folded text", ind

    def test_continuation_requires_indent(self):
        # unindented bare word is not a continuation
        meta, _ = frontmatter.parse("---\nname: x\nnotakey\n---\n")
        assert meta["name"] == "x"

    def test_comment_only_stripped_with_space_hash(self):
        meta, _ = frontmatter.parse("---\nurl: http://x#frag\n---\n")
        assert meta["url"] == "http://x#frag"   # no space before # -> kept

    def test_split_terminator_positions(self):
        # closing fence on the immediate next line -> empty frontmatter
        block, body = frontmatter.split("---\n---\nbody")
        assert block == "" and body == "body"


class TestRoundTrip:
    """Pins parse(dump(meta)) == meta for the value shapes the 2026-08 CLI
    audit found broken: multi-line strings, embedded quotes, punctuation
    that reads as a comment, and strings that collide with a keyword or
    number `_scalar` would otherwise coerce."""

    @staticmethod
    def _round_trips(meta: dict) -> None:
        dumped = frontmatter.dump(meta)
        parsed = frontmatter.parse_block(dumped.strip("-").strip())
        assert parsed == meta, dumped

    def test_plain_scalars(self):
        # `None` is deliberately not included: dump()'s bare `key:` for a
        # None value reads back as "" (test_dump_none_exact pins that shape),
        # a pre-existing gap distinct from the string-quoting bugs this class
        # covers.
        self._round_trips({"name": "x", "version": "1.0.0",
                           "flag": True, "n": 3})

    def test_multiline_description(self):
        self._round_trips({"description": "first line\nsecond line"})

    def test_embedded_quotes_and_backslash(self):
        self._round_trips(
            {"description": 'has: colon and "quotes" and #hash'})
        self._round_trips({"path": "C:\\Users\\x"})

    def test_hash_without_colon(self):
        self._round_trips({"tag": "c#"})

    def test_string_that_looks_like_a_bool_or_null(self):
        self._round_trips({"x": "true"})
        self._round_trips({"x": "false"})
        self._round_trips({"x": "null"})
        self._round_trips({"x": "~"})

    def test_string_that_looks_like_a_number(self):
        self._round_trips({"x": "3"})
        self._round_trips({"x": "1.5"})

    def test_string_that_looks_like_a_flow_list(self):
        self._round_trips({"x": "[a, b]"})

    def test_string_that_looks_like_a_block_scalar_marker(self):
        self._round_trips({"x": "|"})
        self._round_trips({"x": ">"})

    def test_string_already_quote_wrapped(self):
        self._round_trips({"x": "'a'"})
        self._round_trips({"x": '"a"'})

    def test_leading_or_trailing_whitespace(self):
        self._round_trips({"x": "  padded  "})

    def test_list_items_get_the_same_protection(self):
        self._round_trips({"tags": ["true", "a: b", "plain"]})


class TestNeedsQuoting:
    def test_plain_word_is_not_quoted(self):
        assert frontmatter._needs_quoting("brainstorming") is False

    def test_empty_string_is_not_quoted(self):
        assert frontmatter._needs_quoting("") is False

    def test_newline_is_quoted(self):
        assert frontmatter._needs_quoting("a\nb") is True

    def test_hash_is_quoted(self):
        assert frontmatter._needs_quoting("a#b") is True

    def test_keyword_lookalikes_are_quoted(self):
        for s in ("true", "False", "NULL", "~"):
            assert frontmatter._needs_quoting(s) is True

    def test_numeral_lookalike_is_quoted(self):
        assert frontmatter._needs_quoting("42") is True

    def test_non_numeral_is_not_quoted(self):
        assert frontmatter._needs_quoting("v1.2.3-beta") is False


class TestSetField:
    def test_replaces_existing_top_level_key(self):
        text = "---\nname: x\nversion: 1.0.0\n---\n\nbody"
        out = frontmatter.set_field(text, "version", "1.0.1")
        assert out == "---\nname: x\nversion: 1.0.1\n---\n\nbody"

    def test_untouched_lines_are_byte_identical(self):
        # The whole point: a quoted, specially-formatted line the naive
        # parse-dict-dump path would have reformatted survives verbatim.
        text = ('---\nname: x\ndescription: "first\\nsecond"\n'
                'date_added: "2026-02-27"\nversion: 1.0.0\n---\n\nbody')
        out = frontmatter.set_field(text, "version", "1.0.1")
        assert 'description: "first\\nsecond"' in out
        assert 'date_added: "2026-02-27"' in out
        assert "version: 1.0.1" in out

    def test_appends_a_missing_key(self):
        text = "---\nname: x\n---\n\nbody"
        out = frontmatter.set_field(text, "version", "0.0.1")
        meta, body = frontmatter.parse(out)
        assert meta == {"name": "x", "version": "0.0.1"}
        assert body == "body"

    def test_nested_key_is_not_mistaken_for_top_level(self):
        # An indented `version:` under some other block must not shadow the
        # real top-level key.
        text = "---\nreq:\n  version: nested\nversion: 1.0.0\n---\n\nbody"
        out = frontmatter.set_field(text, "version", "1.0.1")
        assert "  version: nested" in out
        assert "version: 1.0.1" in out

    def test_new_value_that_needs_quoting_is_quoted(self):
        text = "---\nversion: 1.0.0\n---\n\nbody"
        out = frontmatter.set_field(text, "version", "true")
        meta, _ = frontmatter.parse(out)
        assert meta["version"] == "true"

    def test_no_frontmatter_returns_text_unchanged(self):
        assert frontmatter.set_field("# just markdown", "version", "1") == \
            "# just markdown"


class TestDump:
    def test_roundtrip_scalars(self):
        meta = {"name": "x", "version": "1.0.0", "flag": True, "n": 3}
        parsed = frontmatter.parse_block(
            frontmatter.dump(meta).strip("-").strip())
        assert parsed["name"] == "x"
        assert parsed["flag"] is True
        assert parsed["n"] == 3

    def test_dump_list_and_none(self):
        text = frontmatter.dump({"tags": ["a", "b"], "empty": None})
        assert "tags:" in text and "  - a" in text
        assert "empty:" in text
        assert text.startswith("---") and text.endswith("---")

    def test_dump_quotes_colon_values(self):
        text = frontmatter.dump({"desc": "a: b"})
        assert '"a: b"' in text


class TestMutationPrecision:
    """Exact-output tests pinning behaviour that substring `in` checks miss.

    Each targets a specific mutmut survivor class in frontmatter.py; the
    assertions are equalities (not `in`) so a mutated literal is observable.
    """

    # --- split() -------------------------------------------------------
    def test_body_lstrip_only_strips_newlines(self):
        # body begins with 'X'; lstrip must strip newlines only, not any char
        _, body = frontmatter.parse("---\nname: a\n---\nXeno body")
        assert body == "Xeno body"

    # --- _scalar() -----------------------------------------------------
    def test_scalar_only_quote_chars_unwrap(self):
        # a value fenced by a non-quote char stays literal
        assert frontmatter._scalar("XfooX") == "XfooX"

    # --- _split_commas() ----------------------------------------------
    def test_flow_list_non_quote_char_does_not_open_quote(self):
        meta, _ = frontmatter.parse("---\ntags: [X, y]\n---\n")
        assert meta["tags"] == ["X", "y"]        # 'X' is not a quote opener

    def test_flow_list_quote_midtoken_keeps_buffer(self):
        # a quote in the middle of a token must not reset the accumulated buf
        meta, _ = frontmatter.parse('---\ntags: [x"y"]\n---\n')
        assert meta["tags"] == ['x"y"']

    def test_flow_list_multichar_unquoted_items(self):
        meta, _ = frontmatter.parse("---\ntags: [abc, def]\n---\n")
        assert meta["tags"] == ["abc", "def"]

    # --- parse_block(): control flow ----------------------------------
    def test_blank_line_is_skipped_not_terminal(self):
        meta, _ = frontmatter.parse("---\nname: a\n\nversion: 2\n---\n")
        assert meta == {"name": "a", "version": 2}   # blank didn't stop parse

    def test_comment_with_colon_is_ignored(self):
        meta, _ = frontmatter.parse("---\n# note: hi\nname: x\n---\n")
        assert meta == {"name": "x"}                 # '# note' not a key

    def test_bare_dash_list_item_is_empty_string(self):
        meta, _ = frontmatter.parse("---\nreq:\n  -\n  - a\n---\n")
        assert meta["req"] == ["", "a"]

    def test_continuation_folds_at_single_space_indent(self):
        meta, _ = frontmatter.parse("---\ndesc: hello\n world\n---\n")
        assert meta["desc"] == "hello world"         # indent > 0, not > 1

    def test_indented_colon_line_under_a_value_is_a_fold(self):
        # `desc` already has a value, so this cannot open a nested map, and
        # it is not a key anywhere either: it is the next line of the scalar.
        meta, _ = frontmatter.parse("---\ndesc: hello\n  key: val\n---\n")
        assert meta == {"desc": "hello key: val"}

    def test_unindented_colonless_word_is_skipped_not_terminal(self):
        # a bare word at indent 0 is skipped; parsing continues past it
        meta, _ = frontmatter.parse("---\nname: a\nbareword\nversion: 2\n---\n")
        assert meta == {"name": "a", "version": 2}

    def test_fold_then_next_key_both_survive(self):
        meta, _ = frontmatter.parse(
            "---\ndesc: hello\n  world\nversion: 2\n---\n")
        assert meta["desc"] == "hello world"
        assert meta["version"] == 2                  # parsing continued

    # --- parse_block(): comment stripping -----------------------------
    def test_double_quoted_value_keeps_inline_hash(self):
        meta, _ = frontmatter.parse('---\nname: "foo # bar"\n---\n')
        assert meta["name"] == "foo # bar"

    def test_comment_strip_splits_on_first_space_hash_only(self):
        meta, _ = frontmatter.parse("---\nname: foo bar # c\n---\n")
        assert meta["name"] == "foo bar"             # keeps internal space

    def test_comment_strip_uses_leftmost_hash(self):
        meta, _ = frontmatter.parse("---\nname: a # b # c\n---\n")
        assert meta["name"] == "a"                   # split, not rsplit

    def test_flow_list_needs_both_brackets(self):
        meta, _ = frontmatter.parse("---\ntags: [unclosed\n---\n")
        assert meta["tags"] == "[unclosed"           # not parsed as a list

    # --- dump(): exact lines ------------------------------------------
    def test_dump_list_exact(self):
        assert frontmatter.dump({"tags": ["a"]}) == "---\ntags:\n  - a\n---"

    def test_dump_bool_true_exact(self):
        assert frontmatter.dump({"x": True}) == "---\nx: true\n---"

    def test_dump_bool_false_exact(self):
        assert frontmatter.dump({"x": False}) == "---\nx: false\n---"

    def test_dump_none_exact(self):
        assert frontmatter.dump({"x": None}) == "---\nx:\n---"

    def test_dump_colon_value_quoted_exact(self):
        assert frontmatter.dump({"d": "a: b"}) == '---\nd: "a: b"\n---'

    def test_dump_escapes_embedded_quote_exact(self):
        # value has a quote AND a colon -> quoted branch escapes the quote
        assert frontmatter.dump({"d": 'a": b'}) == '---\nd: "a\\": b"\n---'


class TestByteOrderMark:
    """A file saved by a Windows editor opens with U+FEFF; it must parse as
    the same file without one, not as a frontmatter-less body."""

    def test_split_strips_a_leading_bom(self):
        block, body = frontmatter.split("﻿---\nname: x\n---\n\n# Body")
        assert block == "name: x"
        assert body == "# Body"

    def test_split_without_frontmatter_drops_the_bom_from_the_body(self):
        assert frontmatter.split("﻿# Just markdown") == ("", "# Just markdown")

    def test_parse_reads_bom_frontmatter(self):
        meta, body = frontmatter.parse(
            "﻿---\nname: x\ndescription: d\nversion: 1.2.0\n---\nbody")
        assert meta == {"name": "x", "description": "d", "version": "1.2.0"}
        assert body == "body"

    def test_unclosed_sees_through_a_bom(self):
        assert frontmatter.unclosed("﻿---\nname: x\nno close\n") is True
        assert frontmatter.unclosed("﻿---\nname: x\n---\n") is False

    def test_only_a_leading_bom_is_stripped(self):
        _meta, body = frontmatter.parse("---\nname: x\n---\na﻿b")
        assert body == "a﻿b"


class TestNestedMaps:
    """Indented `k: v` lines belong to a nested map, kept as a dict under the
    parent key; they never override a top-level key (the Agent Skills spec's
    `metadata:` map, `author:`)."""

    def test_nested_author_name_does_not_rename_the_skill(self):
        meta = frontmatter.parse_block(
            "name: author-skill\ndescription: d\nauthor:\n"
            "  name: Jane Doe\n  email: jane@example.com\n"
            "metadata:\n  version: \"2.0\"\n")
        assert meta == {"name": "author-skill", "description": "d",
                        "author": {"name": "Jane Doe",
                                   "email": "jane@example.com"},
                        "metadata": {"version": "2.0"}}

    def test_nested_values_are_typed_like_top_level_ones(self):
        meta = frontmatter.parse_block(
            "m:\n  n: 3\n  q: \"3\"\n  f: [a, b]\n  t: true\n"
            "  c: x # note\n  l:\n    - one\n    - two\n  m2:\n  - compact\n")
        assert meta == {"m": {"n": 3, "q": "3", "f": ["a", "b"], "t": True,
                              "c": "x", "l": ["one", "two"],
                              "m2": ["compact"]}}

    def test_top_level_keys_after_a_nested_map_still_parse(self):
        meta = frontmatter.parse_block(
            "name: s\nmetadata:\n  version: \"2.0\"\n  tags:\n    - nested\n"
            "    - more\nversion: 1.1.0\ntags:\n  - top\n")
        assert meta == {"name": "s",
                        "metadata": {"version": "2.0",
                                     "tags": ["nested", "more"]},
                        "version": "1.1.0", "tags": ["top"]}

    def test_only_one_level_is_modelled(self):
        meta = frontmatter.parse_block(
            "name: s\nmetadata:\n  notes: |\n    description: no\n"
            "    - not an item\n  deep:\n    k: v\n  plain words\n"
            "description: yes\n")
        assert meta == {"name": "s", "metadata": {"notes": "", "deep": ""},
                        "description": "yes"}

    def test_indented_key_under_a_valued_key_folds_into_the_value(self):
        # Never a nested key and never dropped: the lines fold into the
        # scalar, deeper ones included.
        meta = frontmatter.parse_block(
            "name: s\n  extra: x\n    deeper: y\n  more\nversion: 2\n")
        assert meta == {"name": "s extra: x deeper: y more", "version": 2}

    def test_a_non_string_value_still_skips_an_indented_key(self):
        # Only a plain string can be continued; a flow list or number cannot.
        meta = frontmatter.parse_block(
            "tags: [a]\n  k: v\n  more\nn: 3\n  k: v\nname: s\n")
        assert meta == {"tags": ["a"], "n": 3, "name": "s"}

    def test_a_list_parent_is_not_turned_into_a_map(self):
        meta = frontmatter.parse_block("tags:\n  - a\n  k: v\nname: s\n")
        assert meta == {"tags": ["a"], "name": "s"}

    def test_top_level_is_the_first_key_indent(self):
        # A wholly indented block is still read: its top level is its own
        # first key's column, and only lines deeper than that are nested.
        meta = frontmatter.parse_block(
            "  name: s\n  author:\n    name: other\n  version: 2.0.1\n")
        assert meta == {"name": "s", "author": {"name": "other"},
                        "version": "2.0.1"}

    def test_list_items_and_folds_under_top_keys_are_unchanged(self):
        meta = frontmatter.parse_block(
            "description: one\n  two\nrequires:\n  - a\n  - b\n")
        assert meta == {"description": "one two", "requires": ["a", "b"]}

    def test_dump_round_trips_a_nested_map(self):
        meta = {"name": "a", "author": {"name": "Jane: Doe", "v": "2.0",
                                        "tags": ["x", "y"], "b": False},
                "version": "1.0"}
        text = frontmatter.dump(meta)
        assert "author:\n  name: \"Jane: Doe\"\n  v: \"2.0\"\n" in text
        assert "  tags:\n    - x\n    - y\n  b: false\n" in text
        assert frontmatter.parse(text + "\n")[0] == meta


class TestTagsOf:
    """`tags_of` reads list, comma-string and scalar `tags:` alike."""

    def test_a_scalar_string_is_one_tag_not_its_characters(self):
        assert frontmatter.tags_of({"tags": "testing"}) == ["testing"]

    def test_a_comma_string_splits_and_strips(self):
        assert frontmatter.tags_of({"tags": " a, B ,,c "}) == ["a", "B", "c"]

    def test_a_list_keeps_case_and_drops_blanks(self):
        assert frontmatter.tags_of({"tags": ["Git", " x ", "", 5]}) == ["Git", "x", "5"]

    def test_a_number_is_one_tag(self):
        assert frontmatter.tags_of({"tags": 5}) == ["5"]
        assert frontmatter.tags_of({"tags": 1.5}) == ["1.5"]

    @pytest.mark.parametrize("raw", [None, {"a": 1}, True, [True, {"a": 1}, None]])
    def test_junk_reads_as_no_tags(self, raw):
        assert frontmatter.tags_of({"tags": raw}) == []

    def test_a_non_dict_meta_or_missing_key_is_no_tags(self):
        assert frontmatter.tags_of(None) == []
        assert frontmatter.tags_of({}) == []

    def test_parsed_scalar_frontmatter_round_trip(self):
        meta, _ = frontmatter.parse("---\nname: x\ntags: testing\n---\nbody\n")
        assert frontmatter.tags_of(meta) == ["testing"]


class TestColonInFoldedContinuation:
    """A continuation line carrying ``: `` stays part of the scalar.

    Expectations are written as literals. Where the YAML is valid (``b:c``,
    no space after the colon) they are what PyYAML returns; where it is not
    (``Note: slow``) PyYAML raises "mapping values are not allowed here", and
    this best-effort parser keeps the author's text rather than dropping it.
    """

    def test_finding_repro_keeps_every_line(self):
        meta = frontmatter.parse_block(
            "name: colon\ndescription: Use this skill when\n"
            "  reviewing code: it checks style\n"
            "  and correctness carefully\nversion: 1.0.0")
        assert meta == {
            "name": "colon",
            "description": "Use this skill when reviewing code: it checks "
                           "style and correctness carefully",
            "version": "1.0.0"}

    def test_lines_after_the_colon_line_still_fold(self):
        meta = frontmatter.parse_block(
            "description: Review code\n  for bugs. Note: slow\n"
            "  and thorough\nversion: 1.0.0")
        assert meta == {
            "description": "Review code for bugs. Note: slow and thorough",
            "version": "1.0.0"}

    def test_colon_without_space_matches_pyyaml(self):
        # yaml.safe_load("d: a\n  b:c\n") == {"d": "a b:c"}
        assert frontmatter.parse_block("d: a\n  b:c\n") == {"d": "a b:c"}

    def test_empty_value_still_opens_a_nested_map(self):
        # YAML agrees: under an empty value an indented `k: v` is a mapping.
        assert frontmatter.parse_block(
            "description:\n  Use when: reviewing PRs\nversion: 1.0.0") == {
            "description": {"Use when": "reviewing PRs"}, "version": "1.0.0"}

    def test_a_nested_map_entry_is_unchanged(self):
        meta = frontmatter.parse_block(
            "author:\n  name: Jane\n  site: x\nversion: 2.0.1\n")
        assert meta == {"author": {"name": "Jane", "site": "x"},
                        "version": "2.0.1"}

    def test_description_survives_into_the_catalog(self, sandbox, tmp_path):
        from boost_cli.core import catalog
        skill = tmp_path / "skills" / "colon"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: colon\ndescription: Use this skill when\n"
            "  reviewing code: it checks style\n"
            "  and correctness carefully\nversion: 1.0.0\n---\n\nBody.\n",
            encoding="utf-8")
        entries = [e for e in catalog.scan_dir(tmp_path)
                   if e["name"] == "colon"]
        assert [e["description"] for e in entries] == [
            "Use this skill when reviewing code: it checks style and "
            "correctness carefully"]


class TestDumpUnescape:
    """`_dump_unescape` is a regex, not an index-stepped scan: a scan's
    ``i += 1`` mutant (``i = 1``) grew a list without bound and took the CI
    runner down. These pin the reading the scan defined, edge cases included."""

    @pytest.mark.parametrize("raw, want", [
        ("", ""),
        ("plain", "plain"),
        (r"a\nb", "a\nb"),
        (r"say \"hi\"", 'say "hi"'),
        (r"back\\slash", "back\\slash"),
        # an escaped backslash is consumed whole: the n after it stays an n
        (r"\\n", "\\n"),
        (r"\\\n", "\\\n"),
        # not one of the three escapes: both characters kept verbatim
        (r"tab\t", "tab\\t"),
        # a lone trailing backslash has nothing to guard
        ("end\\", "end\\"),
    ])
    def test_reads_each_escape_once(self, raw, want):
        assert frontmatter._dump_unescape(raw) == want

    @pytest.mark.parametrize("value", [
        "", "x", 'q"uote', "back\\slash", "two\nlines", '\\"\n\\\\', "\\n",
    ])
    def test_inverts_dump_escape(self, value):
        assert frontmatter._dump_unescape(frontmatter._dump_escape(value)) == value
