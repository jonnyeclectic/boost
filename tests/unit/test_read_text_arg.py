# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: `util.read_text_arg`, the curl-style `-` / `@FILE` resolver.

`boost evolve --feedback` used to take its value verbatim: `""` became an
empty "## Feedback" heading plus a version bump, `-` became the bullet
`- -.` and `@/dev/null` became `- @/dev/null.`.
"""
from __future__ import annotations

import io
import sys

import pytest

from boost_cli.core import util
from boost_cli.errors import BoostError


class TestLiteral:
    def test_returns_the_text_stripped(self):
        assert util.read_text_arg("  cap ideas at 5 \n", "--feedback") == \
            "cap ideas at 5"

    @pytest.mark.parametrize("value", ["", "   ", "\n\t "])
    def test_empty_or_blank_is_refused(self, value):
        with pytest.raises(BoostError) as e:
            util.read_text_arg(value, "--feedback")
        assert e.value.message == "--feedback is empty"
        assert "`--feedback -` to read stdin" in e.value.hint
        assert "`--feedback @FILE` to read a file" in e.value.hint

    @pytest.mark.parametrize("value", ["--", "a-b", "- x", "x@y", "mail me@x"])
    def test_only_an_exact_dash_or_a_leading_at_is_special(self, value):
        assert util.read_text_arg(value, "--feedback",
                                  stdin=io.StringIO("STDIN")) == value

    def test_flag_name_is_used_in_the_error(self):
        with pytest.raises(BoostError) as e:
            util.read_text_arg("", "--note")
        assert e.value.message == "--note is empty"
        assert "`--note -`" in e.value.hint


class TestStdin:
    def test_dash_reads_the_given_stream(self):
        assert util.read_text_arg(
            "-", "--feedback", stdin=io.StringIO("one.\ntwo\n")) == "one.\ntwo"

    def test_dash_defaults_to_sys_stdin_at_call_time(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", io.StringIO("piped in\n"))
        assert util.read_text_arg("-", "--feedback") == "piped in"

    @pytest.mark.parametrize("data", ["", "  \n\n"])
    def test_empty_stdin_is_refused(self, data):
        with pytest.raises(BoostError) as e:
            util.read_text_arg("-", "--feedback", stdin=io.StringIO(data))
        assert e.value.message == "--feedback - read nothing from stdin"
        assert e.value.hint == "pipe the text in, or pass it as the value itself"


    def test_invalid_utf8_on_stdin_is_replaced_not_a_traceback(self):
        # A real stdin is a text wrapper over bytes, and its strict decode
        # raised UnicodeDecodeError, which is not a BoostError: the `@FILE`
        # arm was hardened against exactly this, and `-` was not.
        stream = io.TextIOWrapper(io.BytesIO(b"\xff ok"), encoding="utf-8")
        assert util.read_text_arg("-", "--feedback", stdin=stream) == "\ufffd ok"

    def test_a_closed_stdin_is_refused_not_a_traceback(self, monkeypatch):
        # `<&-` closes fd 0 before Python starts, and sys.stdin is None.
        monkeypatch.setattr(sys, "stdin", None)
        with pytest.raises(BoostError, match="read nothing from stdin"):
            util.read_text_arg("-", "--feedback")

    def test_a_stream_with_no_byte_layer_is_read_as_text(self):
        assert util.read_text_arg("-", "--feedback",
                                  stdin=io.StringIO("é ok\n")) == "é ok"


class TestFile:
    def test_at_path_reads_the_file(self, tmp_path):
        f = tmp_path / "fb.txt"
        f.write_text("  from a file\n", encoding="utf-8")
        assert util.read_text_arg("@%s" % f, "--feedback") == "from a file"

    def test_at_path_does_not_touch_stdin(self, tmp_path):
        f = tmp_path / "fb.txt"
        f.write_text("file text", encoding="utf-8")

        class Boom(io.StringIO):
            def read(self, *a):
                raise AssertionError("stdin read for an @FILE value")

        assert util.read_text_arg("@%s" % f, "--feedback",
                                  stdin=Boom()) == "file text"

    def test_at_path_expands_home(self, sandbox):
        (sandbox / "fb.txt").write_text("under home", encoding="utf-8")
        assert util.read_text_arg("@~/fb.txt", "--feedback") == "under home"

    def test_at_path_reads_utf8(self, tmp_path):
        f = tmp_path / "fb.txt"
        f.write_bytes("naïve — café".encode())
        assert util.read_text_arg("@%s" % f, "--feedback") == "naïve — café"

    def test_invalid_utf8_is_replaced_not_a_traceback(self, tmp_path):
        # Strict decoding raises UnicodeDecodeError, which is not an OSError,
        # so it would escape the BoostError handler as a traceback.
        f = tmp_path / "fb.txt"
        f.write_bytes(b"\xff\xfe ok")
        assert util.read_text_arg("@%s" % f, "--feedback") == \
            "\ufffd\ufffd ok"

    @pytest.mark.parametrize("value", ["@", "@  "])
    def test_bare_at_needs_a_path(self, value):
        with pytest.raises(BoostError) as e:
            util.read_text_arg(value, "--feedback", stdin=io.StringIO("STDIN"))
        assert e.value.message == "--feedback @ needs a file path"
        assert e.value.hint == ("`--feedback @FILE` reads FILE; pass the text "
                                "itself, or `-` to read stdin")

    def test_one_character_path_is_a_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a").write_text("short name", encoding="utf-8")
        assert util.read_text_arg("@a", "--feedback") == "short name"

    def test_empty_file_is_refused(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("\n  \n", encoding="utf-8")
        with pytest.raises(BoostError) as e:
            util.read_text_arg("@%s" % f, "--feedback")
        assert e.value.message == "--feedback @%s: %s is empty" % (f, f)
        assert e.value.hint == ("write the text into the file, or pass it as "
                                "the value itself")

    def test_missing_file_is_an_error_not_literal_text(self, tmp_path):
        missing = tmp_path / "nope.txt"
        with pytest.raises(BoostError) as e:
            util.read_text_arg("@%s" % missing, "--feedback")
        assert e.value.message.startswith(
            "can't read --feedback @%s: " % missing)
        assert "`--feedback @FILE` reads FILE" in e.value.hint

    def test_directory_is_an_error(self, tmp_path):
        with pytest.raises(BoostError) as e:
            util.read_text_arg("@%s" % tmp_path, "--feedback")
        assert e.value.message.startswith("can't read --feedback @")
