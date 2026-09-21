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
