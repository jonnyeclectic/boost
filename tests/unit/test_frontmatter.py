"""Unit tests: boost_cli/core/frontmatter.py — the SKILL.md YAML-subset parser."""
from __future__ import annotations


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

    def test_scalar_every_keyword(self):
        s = frontmatter._scalar
        for word, want in [("true", True), ("yes", True), ("on", True),
                           ("TRUE", True), ("Yes", True),
                           ("false", False), ("no", False), ("off", False),
                           ("OFF", False),
                           ("null", None), ("~", None), ("none", None)]:
            assert s(word) is want, word
        assert s("maybe") == "maybe"     # not a keyword
        assert s("yess") == "yess"

    def test_scalar_numbers(self):
        s = frontmatter._scalar
        assert s("0") == 0
        assert s("-3") == -3
        assert s("0.0") == 0.0
        assert s("1e3") == 1000.0
        assert s("1.2.3") == "1.2.3"     # not a float

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

    def test_indented_colon_line_is_a_key_not_a_fold(self):
        meta, _ = frontmatter.parse("---\ndesc: hello\n  key: val\n---\n")
        assert meta["desc"] == "hello"
        assert meta["key"] == "val"

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
