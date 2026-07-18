"""Unit tests: boost_cli/core/output.py — colors, symbols, tables, confirm."""
from __future__ import annotations

import os
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


class TestColorLevel:
    def test_none_when_no_color(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        assert output.color_level(FakeStream(tty=True)) == 0

    def test_none_when_non_tty(self, monkeypatch):
        monkeypatch.delenv("COLORTERM", raising=False)
        assert output.color_level(FakeStream(tty=False)) == 0

    def test_basic_when_tty_without_colorterm(self, monkeypatch):
        monkeypatch.delenv("COLORTERM", raising=False)
        assert output.color_level(FakeStream(tty=True)) == 1

    def test_truecolor_from_colorterm(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert output.color_level(FakeStream(tty=True)) == 2

    def test_truecolor_from_24bit(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "24bit")
        assert output.color_level(FakeStream(tty=True)) == 2

    def test_colorterm_is_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "TrueColor")
        assert output.color_level(FakeStream(tty=True)) == 2

    def test_unrelated_colorterm_is_basic(self, monkeypatch):
        monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
        monkeypatch.setenv("COLORTERM", "8bit")
        assert output.color_level(FakeStream(tty=True)) == 1

    def test_truecolor_when_forced_even_off_tty(self, monkeypatch):
        monkeypatch.delenv("COLORTERM", raising=False)
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        assert output.color_level(FakeStream(tty=False)) == 2


class TestRgb:
    def test_channels_formatted(self):
        assert output.rgb(34, 211, 238) == "\033[38;2;34;211;238m"

    def test_zero_channels(self):
        assert output.rgb(0, 0, 0) == "\033[38;2;0;0;0m"


class TestAurora:
    def test_plain_when_no_color(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        assert output.aurora("boost", "cyan", FakeStream(tty=True)) == "boost"

    def test_truecolor_cyan_exact_hex(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert output.aurora("x", "cyan", FakeStream(tty=True)) == (
            "\033[38;2;34;211;238mx\033[0m")

    def test_truecolor_pink_exact_hex(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert output.aurora("x", "pink", FakeStream(tty=True)) == (
            "\033[38;2;244;114;208mx\033[0m")

    def test_basic_cyan_uses_16color_fallback(self, monkeypatch):
        monkeypatch.delenv("COLORTERM", raising=False)
        assert output.aurora("x", "cyan", FakeStream(tty=True)) == (
            output.CYAN + "x" + output.RESET)

    def test_basic_violet_falls_back_to_magenta(self, monkeypatch):
        monkeypatch.delenv("COLORTERM", raising=False)
        assert output.aurora("x", "violet", FakeStream(tty=True)) == (
            output.MAGENTA + "x" + output.RESET)


class TestGradient:
    def test_plain_when_no_color(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        assert output.gradient("boost", FakeStream(tty=True)) == "boost"

    def test_empty_string_passthrough(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert output.gradient("", FakeStream(tty=True)) == ""

    def test_basic_level_is_single_brand_color(self, monkeypatch):
        monkeypatch.delenv("COLORTERM", raising=False)
        assert output.gradient("ab", FakeStream(tty=True)) == (
            output.MAGENTA + "ab" + output.RESET)

    def test_truecolor_first_char_is_cyan_stop(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert output.gradient("boost", FakeStream(tty=True)).startswith(
            "\033[38;2;34;211;238mb")

    def test_truecolor_last_char_is_pink_stop(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert output.gradient("boost", FakeStream(tty=True)).endswith(
            "\033[38;2;244;114;208mt\033[0m")

    def test_single_char_uses_first_stop(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert output.gradient("Z", FakeStream(tty=True)) == (
            "\033[38;2;34;211;238mZ\033[0m")

    def test_exactly_one_reset_at_end(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert output.gradient("boost", FakeStream(tty=True)).count(
            output.RESET) == 1

    def test_midpoint_char_hits_violet_stop(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        # "abc": i=1 -> t=0.5 -> lands exactly on the middle (violet) stop.
        assert "\033[38;2;168;85;247mb" in output.gradient(
            "abc", FakeStream(tty=True))

    def test_two_char_spans_full_gradient(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        # n == 2 boundary: first char = cyan stop, second = pink stop — not both
        # collapsed onto the first stop.
        assert output.gradient("ab", FakeStream(tty=True)) == (
            "\033[38;2;34;211;238ma\033[38;2;244;114;208mb\033[0m")

    def test_exact_interpolation_across_all_chars(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        # Pins every character's interpolated color so any drift in the
        # per-char gradient math (segment, local-t, lerp rounding) is caught.
        assert output.gradient("abcd", FakeStream(tty=True)) == (
            "\033[38;2;34;211;238ma"
            "\033[38;2;123;127;244mb"
            "\033[38;2;193;95;234mc"
            "\033[38;2;244;114;208md"
            "\033[0m")


class TestHeadingAndVerdictColor:
    def _force_truecolor(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        monkeypatch.setenv("CLICOLOR_FORCE", "1")

    def test_heading_marker_is_cyan_truecolor(self, monkeypatch, capsys):
        self._force_truecolor(monkeypatch)
        output.heading("Section")
        out = capsys.readouterr().out
        assert out.startswith("\033[38;2;34;211;238m==>\033[0m ")
        assert "Section" in out

    def test_verdict_ok_green_dot_and_green_text(self, monkeypatch, capsys):
        self._force_truecolor(monkeypatch)
        output.verdict(True, "healthy")
        # aurora green dot (#4ade80) + green message text
        assert capsys.readouterr().out == (
            "  \033[38;2;74;222;128m●\033[0m \033[32mhealthy\033[0m\n")

    def test_verdict_bad_yellow_dot_and_yellow_text(self, monkeypatch, capsys):
        self._force_truecolor(monkeypatch)
        output.verdict(False, "1 issue")
        # aurora yellow dot (#facc15) + yellow message text
        assert capsys.readouterr().out == (
            "  \033[38;2;250;204;21m●\033[0m \033[33m1 issue\033[0m\n")


class TestTermWidth:
    def test_honors_columns_env(self, monkeypatch):
        monkeypatch.setenv("COLUMNS", "123")
        assert output.term_width() == 123

    def test_detected_columns(self, monkeypatch):
        monkeypatch.setattr(output.shutil, "get_terminal_size",
                            lambda fb: os.terminal_size((93, 24)))
        assert output.term_width() == 93

    def test_default_80_when_undetectable(self, monkeypatch):
        monkeypatch.delenv("COLUMNS", raising=False)
        monkeypatch.setattr(output.shutil, "get_terminal_size",
                            lambda fb: os.terminal_size(fb))
        assert output.term_width() == 80

    def test_custom_default_when_undetectable(self, monkeypatch):
        monkeypatch.delenv("COLUMNS", raising=False)
        monkeypatch.setattr(output.shutil, "get_terminal_size",
                            lambda fb: os.terminal_size(fb))
        assert output.term_width(77) == 77


class TestTruncate:
    def test_short_text_unchanged(self):
        assert output.truncate("hello", 80) == "hello"

    def test_exact_width_not_clipped(self):
        assert output.truncate("abcd", 4) == "abcd"

    def test_clips_with_ellipsis(self):
        assert output.truncate("abcdef", 4) == "abc…"

    def test_collapses_real_whitespace(self):
        assert output.truncate("a\n\n  b\tc", 80) == "a b c"

    def test_collapses_literal_escape_sequences(self):
        # descriptions in the wild carry literal backslash-n blobs
        assert output.truncate("a\\n\\nb", 80) == "a b"

    def test_collapses_literal_tab_escape(self):
        assert output.truncate("a\\tb", 80) == "a b"

    def test_collapses_literal_cr_escape(self):
        assert output.truncate("a\\rb", 80) == "a b"

    def test_zero_width_is_empty(self):
        assert output.truncate("abc", 0) == ""

    def test_width_at_or_below_ellipsis_returns_ellipsis(self):
        assert output.truncate("abcdef", 1) == "…"


class TestBadge:
    def test_plain_when_no_color(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        assert output.badge("installed", "green") == "[installed]"

    def test_default_hue_is_cyan(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        assert output.badge("x") == "\033[38;2;34;211;238m[x]\033[0m"

    def test_truecolor_wraps_label_in_brackets(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        # green #4ade80
        assert output.badge("installed", "green") == (
            "\033[38;2;74;222;128m[installed]\033[0m")


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

    def test_verdict_healthy_plain(self, capsys):
        output.verdict(True, "healthy")
        assert capsys.readouterr().out == "  ● healthy\n"

    def test_verdict_attention_plain(self, capsys):
        output.verdict(False, "2 issues need attention")
        assert capsys.readouterr().out == "  ● 2 issues need attention\n"

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
