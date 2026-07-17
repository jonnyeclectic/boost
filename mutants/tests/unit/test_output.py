"""Unit tests: boost_cli/core/output.py — colors, symbols, tables, confirm."""
from __future__ import annotations

import sys

import pytest

from boost_cli.core import output


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Neutral color/confirm environment; each test opts in explicitly."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
    monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
    monkeypatch.setattr(sys, "argv", ["boost"])


class FakeStream:
    def __init__(self, tty):
        self._tty = tty

    def isatty(self):
        return self._tty


class TestUseColor:
    def test_no_color_wins(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        assert output.use_color(FakeStream(tty=True)) is False

    def test_no_color_beats_clicolor_force(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        assert output.use_color(FakeStream(tty=True)) is False

    def test_clicolor_force_wins_over_non_tty(self, monkeypatch):
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        assert output.use_color(FakeStream(tty=False)) is True

    def test_non_tty_false(self):
        assert output.use_color(FakeStream(tty=False)) is False

    def test_tty_true(self):
        assert output.use_color(FakeStream(tty=True)) is True

    def test_stream_without_isatty_false(self):
        assert output.use_color(object()) is False


class TestC:
    def test_passthrough_without_color(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        assert output.c("hello", output.RED) == "hello"

    def test_no_styles_is_passthrough_even_when_forced(self, monkeypatch):
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        assert output.c("hello") == "hello"

    def test_wraps_with_clicolor_force(self, monkeypatch):
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        assert output.c("hi", output.RED) == "\033[31mhi\033[0m"

    def test_multiple_styles_concatenated(self, monkeypatch):
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        assert output.c("hi", output.RED, output.BOLD) == (
            "\033[31m\033[1mhi\033[0m")


class TestHelpers:
    @pytest.fixture(autouse=True)
    def plain(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")

    def test_ok(self, capsys):
        output.ok("msg")
        assert capsys.readouterr().out == "  ✓ msg\n"

    def test_warn(self, capsys):
        output.warn("msg")
        assert capsys.readouterr().out == "  ! msg\n"

    def test_err_goes_to_stderr(self, capsys):
        output.err("msg")
        cap = capsys.readouterr()
        assert cap.out == ""
        assert cap.err == "Error: msg\n"

    def test_err_with_hint(self, capsys):
        output.err("boom", hint="try again")
        assert capsys.readouterr().err == "Error: boom\n  hint: try again\n"

    def test_info(self, capsys):
        output.info("msg")
        assert capsys.readouterr().out == "  msg\n"

    def test_info_empty_is_blank_line(self, capsys):
        output.info()
        assert capsys.readouterr().out == "\n"

    def test_dim(self, capsys):
        output.dim("msg")
        assert capsys.readouterr().out == "msg\n"

    def test_heading(self, capsys):
        output.heading("Section")
        assert capsys.readouterr().out == "==> Section\n"

    def test_kv_default_width(self, capsys):
        output.kv("key", "value")
        assert capsys.readouterr().out == "  key           value\n"

    def test_kv_custom_width(self, capsys):
        output.kv("k", "v", width=3)
        assert capsys.readouterr().out == "  k  v\n"

    def test_kv_stringifies_value(self, capsys):
        output.kv("n", 42, width=2)
        assert capsys.readouterr().out == "  n 42\n"


class TestTable:
    @pytest.fixture(autouse=True)
    def plain(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")

    def test_alignment_without_headers(self, capsys):
        output.table([("a", "bb"), ("ccc", "d")])
        assert capsys.readouterr().out == "a    bb\nccc  d\n"

    def test_alignment_with_headers(self, capsys):
        output.table([("x", "1")], headers=["NAME", "N"])
        assert capsys.readouterr().out == "NAME  N\nx     1\n"

    def test_header_wider_than_cells_sets_width(self, capsys):
        output.table([("a", "b"), ("c", "d")], headers=["LONGHEAD", "H"])
        assert capsys.readouterr().out == (
            "LONGHEAD  H\n"
            "a         b\n"
            "c         d\n")

    def test_empty_rows_no_headers_is_noop(self, capsys):
        output.table([])
        assert capsys.readouterr().out == ""

    def test_empty_rows_with_headers_prints_header_only(self, capsys):
        output.table([], headers=["A", "B"])
        assert capsys.readouterr().out == "A  B\n"

    def test_ragged_rows_and_trailing_space_stripped(self, capsys):
        output.table([("a",), ("bb", "c")])
        assert capsys.readouterr().out == "a\nbb  c\n"

    def test_non_string_cells_coerced(self, capsys):
        output.table([(1, 22.5)])
        assert capsys.readouterr().out == "1  22.5\n"


class TestConfirm:
    def test_assume_yes_env_wins(self, monkeypatch):
        monkeypatch.setenv("BOOST_ASSUME_YES", "1")
        # even with a non-tty stdin and default False
        monkeypatch.setattr(sys, "stdin", FakeStream(tty=False))
        assert output.confirm("go?", default=False) is True

    def test_yes_flag_in_argv(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["boost", "uninstall", "--yes"])
        monkeypatch.setattr(sys, "stdin", FakeStream(tty=False))
        assert output.confirm("go?", default=False) is True

    def test_short_y_flag_in_argv(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["boost", "-y"])
        monkeypatch.setattr(sys, "stdin", FakeStream(tty=False))
        assert output.confirm("go?", default=False) is True

    def test_non_tty_returns_default_true(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", FakeStream(tty=False))
        assert output.confirm("go?", default=True) is True

    def test_non_tty_returns_default_false(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", FakeStream(tty=False))
        assert output.confirm("go?", default=False) is False

    def _tty(self, monkeypatch, answer):
        monkeypatch.setattr(sys, "stdin", FakeStream(tty=True))
        prompts = []

        def fake_input(prompt):
            prompts.append(prompt)
            if isinstance(answer, BaseException):
                raise answer
            return answer

        monkeypatch.setattr("builtins.input", fake_input)
        return prompts

    def test_tty_y(self, monkeypatch):
        self._tty(monkeypatch, "y")
        assert output.confirm("go?") is True

    def test_tty_yes_uppercase(self, monkeypatch):
        self._tty(monkeypatch, "YES")
        assert output.confirm("go?") is True

    def test_tty_n(self, monkeypatch):
        self._tty(monkeypatch, "n")
        assert output.confirm("go?", default=True) is False

    def test_tty_gibberish_is_no(self, monkeypatch):
        self._tty(monkeypatch, "maybe")
        assert output.confirm("go?", default=True) is False

    def test_tty_empty_returns_default(self, monkeypatch):
        self._tty(monkeypatch, "")
        assert output.confirm("go?", default=True) is True
        assert output.confirm("go?", default=False) is False

    def test_tty_eof_is_false(self, monkeypatch, capsys):
        self._tty(monkeypatch, EOFError())
        assert output.confirm("go?", default=True) is False
        assert capsys.readouterr().out == "\n"  # prints a newline after ^D

    def test_tty_keyboard_interrupt_is_false(self, monkeypatch):
        self._tty(monkeypatch, KeyboardInterrupt())
        assert output.confirm("go?", default=True) is False

    def test_prompt_suffix_reflects_default(self, monkeypatch):
        prompts = self._tty(monkeypatch, "y")
        output.confirm("Proceed", default=True)
        output.confirm("Proceed", default=False)
        assert prompts == ["Proceed [Y/n] ", "Proceed [y/N] "]
