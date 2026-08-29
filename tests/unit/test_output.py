# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
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
    monkeypatch.delenv("BOOST_COLOR", raising=False)
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

    def test_boost_color_never_beats_clicolor_force(self, monkeypatch):
        monkeypatch.setenv("BOOST_COLOR", "never")
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        assert output.use_color(FakeStream(tty=True)) is False

    def test_boost_color_always_beats_no_color(self, monkeypatch):
        monkeypatch.setenv("BOOST_COLOR", "always")
        monkeypatch.setenv("NO_COLOR", "1")
        assert output.use_color(FakeStream(tty=False)) is True

    def test_boost_color_off_alias(self, monkeypatch):
        monkeypatch.setenv("BOOST_COLOR", "off")
        assert output.use_color(FakeStream(tty=True)) is False

    def test_boost_color_auto_falls_through_to_tty(self, monkeypatch):
        monkeypatch.setenv("BOOST_COLOR", "auto")
        assert output.use_color(FakeStream(tty=True)) is True
        assert output.use_color(FakeStream(tty=False)) is False

    def test_boost_color_all_off_aliases(self, monkeypatch):
        for val in ("never", "off", "0"):
            monkeypatch.setenv("BOOST_COLOR", val)
            assert output.use_color(FakeStream(tty=True)) is False, val

    def test_boost_color_all_on_aliases(self, monkeypatch):
        for val in ("always", "force", "1"):
            monkeypatch.setenv("BOOST_COLOR", val)
            assert output.use_color(FakeStream(tty=False)) is True, val

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
            "\033[38;2;64;203;227mx\033[0m")

    def test_truecolor_pink_exact_hex(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert output.aurora("x", "pink", FakeStream(tty=True)) == (
            "\033[38;2;245;143;215mx\033[0m")

    def test_basic_cyan_uses_16color_fallback(self, monkeypatch):
        monkeypatch.delenv("COLORTERM", raising=False)
        assert output.aurora("x", "cyan", FakeStream(tty=True)) == (
            output.CYAN + "x" + output.RESET)

    def test_basic_violet_falls_back_to_magenta(self, monkeypatch):
        monkeypatch.delenv("COLORTERM", raising=False)
        assert output.aurora("x", "violet", FakeStream(tty=True)) == (
            output.MAGENTA + "x" + output.RESET)


class TestRoles:
    def _truecolor(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        monkeypatch.setenv("CLICOLOR_FORCE", "1")

    def test_role_names_are_the_documented_six(self):
        assert set(output.ROLES) == {
            "accent", "brand", "success", "warn", "danger", "muted"}

    def test_brand_hues_resolve_through_aurora_tokens(self, monkeypatch):
        # accent/brand/success/warn are the Aurora tokens, truecolor exact hex —
        # proving the role table resolves through the palette, not raw copies.
        self._truecolor(monkeypatch)
        for role_name, token in (("accent", "cyan"), ("brand", "violet"),
                                 ("success", "green"), ("warn", "yellow")):
            r, g, b = output.TOKENS[token]
            assert output.role("x", role_name) == (
                output.rgb(r, g, b) + "x" + output.RESET)

    def test_danger_is_base_red(self, monkeypatch):
        # danger/muted have no Aurora token; they use base SGR attributes and
        # so read identically on 16-color and truecolor terminals.
        self._truecolor(monkeypatch)
        assert output.role("x", "danger") == output.RED + "x" + output.RESET

    def test_muted_is_base_dim(self, monkeypatch):
        self._truecolor(monkeypatch)
        assert output.role("x", "muted") == output.DIM + "x" + output.RESET

    def test_aurora_role_degrades_to_16color(self, monkeypatch):
        # a TTY without COLORTERM is level 1 -> the token's 16-color fallback.
        monkeypatch.delenv("COLORTERM", raising=False)
        assert output.role("x", "accent", stream=FakeStream(tty=True)) == (
            output.CYAN + "x" + output.RESET)

    def test_plain_when_color_off(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        for role_name in output.ROLES:
            assert output.role("x", role_name,
                               stream=FakeStream(tty=True)) == "x"

    def test_bold_prepends_bold(self, monkeypatch):
        self._truecolor(monkeypatch)
        r, g, b = output.TOKENS["yellow"]
        assert output.role("x", "warn", bold=True) == (
            output.BOLD + output.rgb(r, g, b) + "x" + output.RESET)

    def test_bold_on_sgr_role(self, monkeypatch):
        self._truecolor(monkeypatch)
        assert output.role("x", "danger", bold=True) == (
            output.BOLD + output.RED + "x" + output.RESET)

    def test_bold_dropped_when_color_off(self, monkeypatch):
        # the weight, like color, is dropped when color is off — no stray escape.
        monkeypatch.setenv("NO_COLOR", "1")
        assert output.role("x", "warn", bold=True,
                           stream=FakeStream(tty=True)) == "x"


class TestTokens:
    def test_known_hexes(self):
        assert output.TOKENS["cyan"] == (0x40, 0xcb, 0xe3)
        assert output.TOKENS["violet"] == (0xcc, 0x9e, 0xff)
        assert output.TOKENS["pink"] == (0xf5, 0x8f, 0xd7)
        assert output.TOKENS["green"] == (0x4a, 0xde, 0x80)
        assert output.TOKENS["yellow"] == (0xfa, 0xcc, 0x15)

    def test_aurora_derives_from_tokens(self, monkeypatch):
        # every brand color resolves to rgb() of its TOKENS triple — proving
        # TOKENS is the single source, not a re-typed copy.
        monkeypatch.setenv("COLORTERM", "truecolor")
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        for name, (r, g, b) in output.TOKENS.items():
            assert output.aurora("x", name) == (
                output.rgb(r, g, b) + "x" + output.RESET)

    def test_gradient_stops_are_tokens(self):
        assert (output.TOKENS["cyan"],
                                      output.TOKENS["violet"],
                                      output.TOKENS["pink"]) == output._GRAD_STOPS


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
            "\033[38;2;64;203;227mb")

    def test_truecolor_last_char_is_pink_stop(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert output.gradient("boost", FakeStream(tty=True)).endswith(
            "\033[38;2;245;143;215mt\033[0m")

    def test_single_char_uses_first_stop(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert output.gradient("Z", FakeStream(tty=True)) == (
            "\033[38;2;64;203;227mZ\033[0m")

    def test_exactly_one_reset_at_end(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert output.gradient("boost", FakeStream(tty=True)).count(
            output.RESET) == 1

    def test_midpoint_char_hits_violet_stop(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        # "abc": i=1 -> t=0.5 -> lands exactly on the middle (violet) stop.
        assert "\033[38;2;204;158;255mb" in output.gradient(
            "abc", FakeStream(tty=True))

    def test_two_char_spans_full_gradient(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        # n == 2 boundary: first char = cyan stop, second = pink stop — not both
        # collapsed onto the first stop.
        assert output.gradient("ab", FakeStream(tty=True)) == (
            "\033[38;2;64;203;227ma\033[38;2;245;143;215mb\033[0m")

    def test_exact_interpolation_across_all_chars(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        # Pins every character's interpolated color so any drift in the
        # per-char gradient math (segment, local-t, lerp rounding) is caught.
        assert output.gradient("abcd", FakeStream(tty=True)) == (
            "\033[38;2;64;203;227ma"
            "\033[38;2;157;173;246mb"
            "\033[38;2;218;153;242mc"
            "\033[38;2;245;143;215md"
            "\033[0m")


class TestHeadingAndVerdictColor:
    def _force_truecolor(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        monkeypatch.setenv("CLICOLOR_FORCE", "1")

    def test_heading_marker_is_cyan_truecolor(self, monkeypatch, capsys):
        self._force_truecolor(monkeypatch)
        output.heading("Section")
        out = capsys.readouterr().out
        assert out.startswith("\033[38;2;64;203;227m==>\033[0m ")
        assert "Section" in out

    def test_verdict_ok_green_dot_and_green_text(self, monkeypatch, capsys):
        self._force_truecolor(monkeypatch)
        output.verdict(True, "healthy")
        # success role for both dot and text -> aurora green (#4ade80) truecolor
        assert capsys.readouterr().out == (
            "  \033[38;2;74;222;128m●\033[0m "
            "\033[38;2;74;222;128mhealthy\033[0m\n")

    def test_verdict_bad_yellow_dot_and_yellow_text(self, monkeypatch, capsys):
        self._force_truecolor(monkeypatch)
        output.verdict(False, "1 issue")
        # warn role for both dot and text -> aurora yellow (#facc15) truecolor
        assert capsys.readouterr().out == (
            "  \033[38;2;250;204;21m●\033[0m "
            "\033[38;2;250;204;21m1 issue\033[0m\n")


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
        assert output.badge("x") == "\033[38;2;64;203;227m[x]\033[0m"

    def test_truecolor_wraps_label_in_brackets(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        # green #4ade80
        assert output.badge("installed", "green") == (
            "\033[38;2;74;222;128m[installed]\033[0m")


class TestVisibleLen:
    def test_plain_string(self):
        assert output.visible_len("hello") == 5

    def test_ignores_ansi_codes(self):
        assert output.visible_len("\033[31mhi\033[0m") == 2

    def test_truecolor_codes_stripped(self):
        assert output.visible_len("\033[38;2;34;211;238m●\033[0m") == 1


class TestPanel:
    def test_single_line_plain(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        assert output.panel("hi") == "╭────╮\n│ hi │\n╰────╯"

    def test_pads_lines_to_widest(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        assert output.panel(["a", "bbb"]) == (
            "╭─────╮\n│ a   │\n│ bbb │\n╰─────╯")

    def test_title_in_top_rule(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        # inner = max(len("hello")=5, len("x")+2=3) = 5
        assert output.panel("hello", title="x") == (
            "╭─ x ───╮\n│ hello │\n╰───────╯")

    def test_wide_title_sets_inner_width(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        # title longer than content: inner = len("widetitle")+2 = 11
        p = output.panel("hi", title="widetitle")
        first, mid, last = p.split("\n")
        assert output.visible_len(first) == output.visible_len(last)
        assert output.visible_len(mid) == output.visible_len(last)

    def test_border_is_aurora_tinted_when_truecolor(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        # top-left corner painted cyan #40cbe3
        assert output.panel("x").startswith("\033[38;2;64;203;227m╭")

    def test_title_is_bold_when_forced(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        assert "\033[1minventory\033[0m" in output.panel("x", title="inventory")


class TestPanelFitsTerminal:
    """`panel()` sized itself to its content and ignored the terminal, so a
    long line produced a box wider than the pane — and a broken box is the
    ugliest overflow there is, because the border wraps into the next row.
    Measured: `boost count` drew 108 columns into an 80-column terminal.
    """

    def _rows(self, monkeypatch, cols, lines, **kw):
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setattr(output, "term_width", lambda: cols)
        return output.panel(lines, **kw).split("\n")

    def test_untouched_when_it_already_fits(self, monkeypatch):
        rows = self._rows(monkeypatch, 40, "x" * 36)
        assert [output.visible_len(r) for r in rows] == [40, 40, 40]
        assert "…" not in rows[1]

    def test_exactly_at_the_limit_is_not_clipped(self, monkeypatch):
        # inner 36 + "│ " + " │" == 40 == the full width: the boundary case a
        # mutant flipping <= to < would break.
        rows = self._rows(monkeypatch, 40, "y" * 36)
        assert rows[1] == "│ " + "y" * 36 + " │"

    def test_one_column_over_is_clipped(self, monkeypatch):
        rows = self._rows(monkeypatch, 40, "z" * 37)
        assert [output.visible_len(r) for r in rows] == [40, 40, 40]
        assert rows[1].endswith("… │")

    def test_every_row_is_the_same_width_after_clipping(self, monkeypatch):
        rows = self._rows(monkeypatch, 30, ["short", "w" * 90, "mid" * 4])
        assert len({output.visible_len(r) for r in rows}) == 1
        assert output.visible_len(rows[0]) <= 30

    def test_title_is_clipped_too(self, monkeypatch):
        rows = self._rows(monkeypatch, 24, "a" * 50, title="t" * 40)
        assert all(output.visible_len(r) <= 24 for r in rows)
        assert len({output.visible_len(r) for r in rows}) == 1

    def test_a_narrow_pane_still_yields_a_box(self, monkeypatch):
        rows = self._rows(monkeypatch, 8, "content that is far too long")
        assert len(rows) == 3
        assert rows[0].startswith("╭") and rows[-1].endswith("╯")
        assert all(output.visible_len(r) <= 8 for r in rows)

    def test_a_zero_width_pane_does_not_crash_or_go_negative(self, monkeypatch):
        rows = self._rows(monkeypatch, 0, "anything")
        assert len(rows) == 3
        assert all(output.visible_len(r) >= 0 for r in rows)


class TestEmptyState:
    def test_message_only_plain(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        assert output.empty_state("nothing here") == "  ○ nothing here"

    def test_message_and_hint_plain(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        assert output.empty_state("empty", hint="try x") == (
            "  ○ empty\n  → try x")

    def test_no_hint_is_single_line(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        assert "\n" not in output.empty_state("solo")

    def test_message_is_dim_when_forced(self, monkeypatch):
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        assert output.empty_state("x") == "  \033[2m○ x\033[0m"

    def test_both_lines_dim_when_forced(self, monkeypatch):
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        assert output.empty_state("x", hint="y") == (
            "  \033[2m○ x\033[0m\n  \033[2m→ y\033[0m")


class TestTitlebar:
    def test_plain_dots_and_title(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        assert output.titlebar("skill") == "  ● ● ●  skill"

    def test_truecolor_dots_exact(self, monkeypatch):
        monkeypatch.setenv("COLORTERM", "truecolor")
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        # exact bar pins the three traffic-light hexes, single-space separators
        # between dots, and the bold title
        assert output.titlebar("x") == (
            "  \033[38;2;255;95;87m●\033[0m"      # #ff5f57 close
            " \033[38;2;254;188;46m●\033[0m"      # #febc2e minimise
            " \033[38;2;40;200;64m●\033[0m"       # #28c840 zoom
            "  \033[1mx\033[0m")

    def test_basic_dots_use_16color_fallback(self, monkeypatch):
        # Force the 16-color tier: dots fall back to basic RED/YELLOW/GREEN.
        monkeypatch.setattr(output, "color_level", lambda: 1)
        bar = output.titlebar("x")
        assert output.RED + "●" + output.RESET in bar
        assert output.YELLOW + "●" + output.RESET in bar
        assert output.GREEN + "●" + output.RESET in bar


class TestMeter:
    def test_full(self):
        assert output.meter(1.0, 4) == "▰▰▰▰"

    def test_empty(self):
        assert output.meter(0.0, 4) == "▱▱▱▱"

    def test_half(self):
        assert output.meter(0.5, 4) == "▰▰▱▱"

    def test_default_width_is_four(self):
        assert output.meter(1.0) == "▰▰▰▰"

    def test_clamps_above_one(self):
        # 1.5 lands in (1, 2] — must still clamp, not overflow to 6 cells
        assert output.meter(1.5, 4) == "▰▰▰▰"
        assert output.meter(2.5, 4) == "▰▰▰▰"

    def test_clamps_below_zero(self):
        assert output.meter(-3.0, 4) == "▱▱▱▱"

    def test_rounds_to_nearest_cell(self):
        # 0.6 * 5 = 3.0 -> exactly three filled
        assert output.meter(0.6, 5) == "▰▰▰▱▱"


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

    def test_warn_and_info_can_be_routed_to_stderr(self, capsys):
        # For commands that also speak JSON on stdout: the notice has to survive
        # `--json`, and the alternatives were corrupting the JSON or dropping
        # the notice. Default stays stdout, so no caller changes behaviour.
        output.warn("routed", stream=sys.stderr)
        output.info("hint", stream=sys.stderr)
        cap = capsys.readouterr()
        assert cap.out == ""
        assert cap.err == "  ! routed\n  hint\n"


class TestPlain:
    """Control characters are stripped from text boost did not author.

    Not cosmetic: `\\x1b[1A\\x1b[2K` moves the cursor up one line and erases it,
    so a single field in a table can rewrite rows already printed above it. The
    terminal decides what an escape means, not boost, so anything arriving from
    a network response or a tapped repo is sanitised at the point of display.
    """

    def test_a_cursor_escape_is_removed_but_the_text_survives(self):
        assert output.plain("evil/\x1b[1A\x1b[2Ktrusted") == "evil/[1A[2Ktrusted"

    def test_the_escape_byte_itself_is_gone(self):
        assert "\x1b" not in output.plain("a\x1b[31mb")

    def test_c0_and_c1_controls_go(self):
        assert output.plain("a\x00b\x07c\x7fd\x9be") == "abcde"

    def test_ordinary_text_is_untouched(self):
        # Including the whitespace the table layer folds itself, and non-ASCII,
        # which must not be mistaken for a control byte.
        assert output.plain("skills/naïve-café/SKILL.md — 3\tcopies\n") == (
            "skills/naïve-café/SKILL.md — 3\tcopies\n")

    def test_a_non_string_is_coerced(self):
        assert output.plain(42) == "42"

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


class TestTableColor:
    def test_pad_uses_visible_width(self, monkeypatch):
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        colored = output.aurora("ab", "cyan")   # visible width 2
        assert output._pad(colored, 5) == colored + "   "   # 3 trailing spaces

    def test_colored_cells_align_by_visible_width(self, capsys, monkeypatch):
        import re
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        # a colored cell must not push the next column out of alignment
        # (color mode joins columns with the dim │ separator)
        output.table([[output.aurora("ab", "cyan"), "x"], ["cd", "y"]])
        vis = [re.sub(r"\x1b\[[0-9;]*m", "", ln)
               for ln in capsys.readouterr().out.splitlines()]
        assert vis == ["ab │ x", "cd │ y"]

    def test_header_row_is_bold_when_forced(self, capsys, monkeypatch):
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        output.table([["x", "1"]], headers=["NAME", "N"])
        assert capsys.readouterr().out.startswith("\033[1mNAME")

    def test_every_header_cell_is_bold(self, capsys, monkeypatch):
        # A whole-line BOLD wrap would be cancelled by the separator's RESET;
        # each header cell must carry its own bold instead.
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        output.table([["x", "y"]], headers=["AA", "BB"])
        header = capsys.readouterr().out.splitlines()[0]
        assert header.count(output.BOLD) == 2
        assert "\033[1mAA" in header and "\033[1mBB" in header

    def test_separator_is_dim_pipe_in_color_mode(self, capsys, monkeypatch):
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        output.table([("a", "b")])
        out = capsys.readouterr().out
        assert " " + output.DIM + "│" + output.RESET + " " in out

    def test_no_separator_glyph_when_color_off(self, capsys, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
        output.table([("a", "b"), ("cc", "d")], headers=["X", "Y"])
        out = capsys.readouterr().out
        assert "│" not in out                       # plain two-space gutter,
        assert out == "X   Y\na   b\ncc  d\n"       # byte-identical to before

    def test_separator_width_counts_in_fit_budget(self, capsys, monkeypatch):
        import os as _os
        import re
        # 3 columns of visible width 4 + two 3-wide separators = 18 > 17,
        # so exactly one text column must shrink; with the old 2-wide gutter
        # (total 16) nothing would shrink. Proves sep=3 reaches _fit_widths.
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        monkeypatch.setattr(output.shutil, "get_terminal_size",
                            lambda fb: _os.terminal_size((17, 24)))
        output.table([("aaaa", "bbbb", "cccc")])
        vis = re.sub(r"\x1b\[[0-9;]*m", "",
                     capsys.readouterr().out.splitlines()[0])
        assert len(vis.rstrip()) <= 17
        assert "…" in vis                            # a cell was clipped


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

    def test_header_arity_exceeds_every_row(self, capsys):
        # a header column with no data cell in any row must not raise: the
        # width generator is guarded by `i < len(r)`, and the header row itself
        # (part of all_rows) always supplies its own columns.
        output.table([("1",)], headers=["A", "B", "C"])
        assert capsys.readouterr().out == "A  B  C\n1\n"

    def test_degenerate_row_shapes_never_raise(self, capsys):
        # empty tuples and all-empty rows are the shapes the (non-)bug feared;
        # assert they render without a `max() arg is empty` crash.
        for rows in ([(), ("a",)], [(), ()], [("a", "b"), ()]):
            output.table(rows)                    # must not raise
        output.table([(), ()], headers=["A", "B"])
        assert "A  B" in capsys.readouterr().out

    def test_non_string_cells_coerced(self, capsys):
        output.table([(1, 22.5)])
        assert capsys.readouterr().out == "1  22.5\n"


class TestRpad:
    def test_pads_left_to_visible_width(self):
        assert output._rpad("42", 5) == "   42"

    def test_no_pad_when_already_wide(self):
        assert output._rpad("12345", 5) == "12345"

    def test_uses_visible_width_with_color(self, monkeypatch):
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        colored = output.aurora("7", "cyan")            # visible width 1
        assert output._rpad(colored, 3) == "  " + colored


class TestNumericCol:
    def test_all_integers_is_numeric(self):
        assert output._numeric_col(["1", "22", "300"]) is True

    def test_floats_and_negatives_are_numeric(self):
        assert output._numeric_col(["-1", "2.5", "0"]) is True

    def test_blanks_are_ignored(self):
        assert output._numeric_col(["1", "", "3"]) is True

    def test_all_blank_is_not_numeric(self):
        # a column of only blanks has nothing to right-align.
        assert output._numeric_col(["", "  ", ""]) is False

    def test_any_text_makes_it_non_numeric(self):
        assert output._numeric_col(["1", "2x", "3"]) is False

    def test_version_strings_are_not_numeric(self):
        assert output._numeric_col(["v1", "1.2.3", "8/10"]) is False

    def test_numeric_measured_ignoring_color(self, monkeypatch):
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        assert output._numeric_col([output.aurora("5", "green"), "10"]) is True


class TestClipVisible:
    def test_noop_when_fits(self):
        assert output._clip_visible("hello", 5) == "hello"

    def test_truncates_with_ellipsis(self):
        assert output._clip_visible("hello world", 8) == "hello w…"

    def test_zero_width_is_empty(self):
        assert output._clip_visible("hello", 0) == ""

    def test_preserves_color_and_closes_with_reset(self, monkeypatch):
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        colored = output.aurora("abcdef", "cyan")       # visible width 6
        clipped = output._clip_visible(colored, 4)
        assert output.visible_len(clipped) == 4          # 3 chars + ellipsis
        assert clipped.endswith(output.RESET)
        assert "abc…" in output._ANSI_RE.sub("", clipped)

    def test_clipped_visible_width_never_exceeds_target(self):
        for w in range(1, 10):
            assert output.visible_len(output._clip_visible("abcdefghij", w)) <= w


class TestFitWidths:
    def test_no_shrink_when_it_fits(self):
        assert output._fit_widths([3, 4], [False, True], avail=80) == [3, 4]

    def test_shrinks_widest_text_column(self):
        # 20 + 2(sep) + 5 = 27 > 20 -> the 20-wide text col shrinks to 13.
        assert output._fit_widths([20, 5], [False, True], avail=20) == [13, 5]

    def test_never_shrinks_numeric_column(self):
        # only the text col may give; the numeric col holds at 10.
        out_w = output._fit_widths([10, 10], [False, True], avail=8)
        assert out_w[1] == 10 and out_w[0] < 10

    def test_stops_at_floor_when_unfittable(self):
        # both text cols bottom out at the floor instead of looping forever.
        assert output._fit_widths([9, 9], [False, False], avail=1,
                                  floor=1) == [1, 1]

    def test_empty_widths_returns_empty(self):
        assert output._fit_widths([], [], avail=80) == []


class TestTableWidthAware:
    @pytest.fixture(autouse=True)
    def plain(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")

    def test_numeric_column_is_right_aligned(self, capsys, monkeypatch):
        monkeypatch.setattr(output, "term_width", lambda: 80)
        output.table([("alpha", "5"), ("b", "100")], headers=("NAME", "N"))
        # the count column is right-justified so 5 and 100 share a right edge.
        assert capsys.readouterr().out == (
            "NAME     N\n"
            "alpha    5\n"
            "b      100\n")

    def test_overflow_shrinks_text_not_numeric(self, capsys, monkeypatch):
        monkeypatch.setattr(output, "term_width", lambda: 24)
        long = "K-Dense-AI/claude-scientific-skills"
        output.table([(long, "3")], headers=("NAME", "N"))
        line = capsys.readouterr().out.splitlines()[1]
        assert "…" in line                       # text column was clipped
        assert line.rstrip().endswith("3")        # the count survived intact
        assert output.visible_len(line) <= 24

    def test_wide_table_stays_within_terminal(self, capsys, monkeypatch):
        monkeypatch.setattr(output, "term_width", lambda: 40)
        rows = [("a-really-long-repository-name-here", "9",
                 "https://example.com/some/deep/path")]
        output.table(rows, headers=("NAME", "N", "URL"))
        for line in capsys.readouterr().out.splitlines():
            assert output.visible_len(line) <= 40


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

    def test_default_is_false_when_unspecified(self, monkeypatch):
        # safety: with no explicit default, an unattended (non-tty) confirm must
        # NOT proceed — pins the `default: bool = False` signature default.
        monkeypatch.setattr(sys, "stdin", FakeStream(tty=False))
        assert output.confirm("delete everything?") is False

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


class TestRoleNamesAreReal:
    """Every semantic role name the command layer uses must exist in ROLES.

    `out.role()` indexes ROLES *after* the color-off early return, so a typo'd
    role name is invisible with NO_COLOR (which conftest sets for the whole
    suite) and a KeyError on a real terminal. That is exactly how
    `provenance.INVALID -> "err"` survived in quality.py: reachable only with
    color on, and nothing here ever turned color on.
    """

    def _assert_renders(self, names):
        for name in sorted(set(names)):
            assert name in output.ROLES, "unknown role %r" % name
            # render it for real with color forced on — the KeyError path
            os.environ["BOOST_COLOR"] = "always"
            try:
                assert output.role("x", name)
            finally:
                os.environ.pop("BOOST_COLOR", None)

    def test_provenance_style_roles_exist(self):
        from boost_cli.commands import quality
        self._assert_renders(quality._PROVENANCE_STYLE.values())

    def test_audit_severity_roles_exist(self):
        from boost_cli.commands import safety
        self._assert_renders(safety._SEV_ROLE.values())
        self._assert_renders(safety._TRUST_ROLE.values())


class TestMeterHue:
    """The search screen's one gradient moment: magnitude rides the Aurora
    ramp. The thresholds are the contract — a drifted boundary silently
    re-tints every result row."""

    def test_top_third_is_cyan(self):
        assert output.meter_hue(1.0) == "cyan"
        assert output.meter_hue(0.66) == "cyan"

    def test_middle_third_is_violet(self):
        assert output.meter_hue(0.659) == "violet"
        assert output.meter_hue(0.33) == "violet"

    def test_bottom_third_is_pink(self):
        assert output.meter_hue(0.329) == "pink"
        assert output.meter_hue(0.0) == "pink"

    def test_out_of_range_clamps_to_the_ends(self):
        assert output.meter_hue(7.5) == "cyan"
        assert output.meter_hue(-1.0) == "pink"

    def test_every_hue_is_an_aurora_token(self):
        for frac in (0.0, 0.33, 0.66, 1.0):
            assert output.meter_hue(frac) in output.TOKENS


class TestKindLabel:
    """One vocabulary for what a catalog kind is called, shared by search
    rows and browse badges — the surfaces can never disagree."""

    def test_the_three_kinds_verbatim(self):
        assert output.kind_label("skill") == "[skill]"
        assert output.kind_label("rule") == "[rule]"
        assert output.kind_label("workflow") == "[workflow]"

    def test_unknown_kind_is_bracketed_verbatim(self):
        assert output.kind_label("agent") == "[agent]"

    def test_missing_kind_defaults_to_skill(self):
        assert output.kind_label("") == "[skill]"

    def test_browse_badges_share_the_vocabulary(self):
        from boost_cli.commands import discovery
        e = {"name": "x", "version": "1.0.0", "tap": "a/b", "kind": "workflow"}
        assert discovery._row_badges(e, {})[0][0] == output.kind_label("workflow")


class TestSearchLayout:
    NAMES = ("commit-messages", "tdd-workflow", "safe-refactors")
    KINDS = ("skill", "workflow", "rule")
    TAPS = ("anthropics/skills", "obra/superpowers", "sdi/agent-rules")

    def test_name_column_fits_the_widest_shown_name(self):
        lay = output.search_layout(100, self.NAMES, self.KINDS, self.TAPS)
        assert lay.name_w == len("commit-messages")

    def test_name_column_caps_at_32(self):
        lay = output.search_layout(120, ["x" * 60], ["skill"], ["a/b"])
        assert lay.name_w == 32

    def test_kind_column_fits_the_widest_kind_shown(self):
        lay = output.search_layout(100, self.NAMES, self.KINDS, self.TAPS)
        assert lay.kind_w == len("[workflow]")

    def test_an_all_skill_page_pays_only_for_skill(self):
        lay = output.search_layout(100, self.NAMES, ["skill"] * 3, self.TAPS)
        assert lay.kind_w == len("[skill]")

    def test_tap_appears_at_84_columns_and_not_below(self):
        wide = output.search_layout(84, self.NAMES, self.KINDS, self.TAPS)
        narrow = output.search_layout(83, self.NAMES, self.KINDS, self.TAPS)
        assert wide.tap_w > 0
        assert narrow.tap_w == 0

    def test_tap_drops_before_the_description_starves(self):
        # 90 cols, a 32-char name and a 20-char tap: keeping the tap would
        # leave the description under 24 columns, so provenance goes first.
        lay = output.search_layout(90, ["x" * 32], ["workflow"], ["o" * 20])
        assert lay.tap_w == 0
        assert lay.desc_w >= 24

    def test_kind_drops_below_48_columns(self):
        assert output.search_layout(47, self.NAMES, self.KINDS, self.TAPS).kind_w == 0
        assert output.search_layout(48, self.NAMES, self.KINDS, self.TAPS).kind_w > 0

    def test_name_tightens_stepwise_before_desc_starves(self):
        lay = output.search_layout(55, ["x" * 32], ["workflow"], ["a/b"])
        assert lay.name_w == 24
        assert lay.desc_w >= 8

    def test_name_never_tightens_below_12(self):
        for cols in range(40, 121):
            lay = output.search_layout(cols, ["x" * 40], ["workflow"], ["o" * 60])
            assert lay.name_w >= 12

    def test_desc_floor_is_8(self):
        for cols in range(40, 121):
            lay = output.search_layout(cols, ["x" * 40], ["workflow"], ["o" * 60])
            assert lay.desc_w >= 8

    def test_empty_inputs_degrade_to_minimal_columns(self):
        # The `default=` guards on the max() calls are contract, not
        # decoration: an empty screen plans 1-wide names and no kind column.
        lay = output.search_layout(80, [], [], [])
        assert (lay.name_w, lay.kind_w, lay.tap_w) == (1, 0, 0)
        assert lay.desc_w >= 8
        # …including on a terminal wide enough for the tap branch to run.
        assert output.search_layout(100, [], [], []).tap_w == 0

    def test_column_caps_are_exact(self):
        # kind caps at [workflow]'s 10 even for a stranger kind; tap at 20.
        assert output.search_layout(100, ["a"], ["extra-long"], []).kind_w == 10
        assert output.search_layout(120, ["a"], ["skill"], ["x" * 25]).tap_w == 20

    def test_desc_gets_every_remaining_cell_when_kind_drops(self):
        # Below 48 columns the kind column costs exactly nothing: at 44 cols
        # a 16-wide name leaves 44 - 2 - 7 - 16 - 2 = 17 cells of prose.
        lay = output.search_layout(44, ["x" * 16], ["skill"], [])
        assert (lay.name_w, lay.kind_w, lay.tap_w, lay.desc_w) == (16, 0, 0, 17)

    def test_every_assembled_row_fits_the_terminal(self):
        """The property behind the pinned COLUMNS=60 clamp test: whatever the
        inputs, a row built from the layout measures within the terminal
        (2-column indent included) at every width from 40 up."""
        extremes = [
            ("x" * 40, "workflow", "o" * 60, "d" * 200),
            ("commit-messages", "skill", "fixture-tap", "short"),
            ("a", "rule", "", ""),
        ]
        for cols in range(40, 121):
            names = [n for n, _k, _t, _d in extremes]
            kinds = [k for _n, k, _t, _d in extremes]
            taps = [t for _n, _k, t, _d in extremes]
            lay = output.search_layout(cols, names, kinds, taps)
            for name, kind, tap, desc in extremes:
                for curated in (False, True):
                    row = output.format_search_row(
                        name, desc, kind, tap, 1.0,
                        curated=curated, installed=True, lay=lay)
                    assert output.visible_len(row) + 2 <= cols, (cols, name, curated)


class TestFormatSearchRow:
    DESC = "Conventional, atomic commit message discipline"

    def _lay(self, cols=60):
        return output.search_layout(
            cols, ["commit-messages", "tdd-workflow"],
            ["skill", "workflow"], ["fixture-tap", "fixture-tap"])

    def test_plain_row_exact_bytes(self):
        row = output.format_search_row(
            "commit-messages", self.DESC, "skill", "fixture-tap", 1.0,
            curated=False, installed=False, lay=self._lay(60))
        expected = ("▰▰▰▰   commit-messages  "
                    + "[skill]".ljust(len("[workflow]")) + "  "
                    + output.truncate(self.DESC, self._lay(60).desc_w))
        assert row == expected

    def test_curated_tail_is_verbatim_with_two_space_lead(self):
        row = output.format_search_row(
            "commit-messages", self.DESC, "skill", "fixture-tap", 1.0,
            curated=True, installed=False, lay=self._lay(60))
        assert row.endswith("  ★ curated")

    def test_curated_pays_for_its_tail_out_of_the_description(self):
        lay = self._lay(60)
        plainr = output.format_search_row(
            "commit-messages", self.DESC, "skill", "fixture-tap", 1.0,
            curated=False, installed=False, lay=lay)
        curated = output.format_search_row(
            "commit-messages", self.DESC, "skill", "fixture-tap", 1.0,
            curated=True, installed=False, lay=lay)
        assert output.visible_len(curated) <= output.visible_len(plainr) + len("  ★ curated")

    def test_installed_mark_fills_its_reserved_column(self):
        lay = self._lay(60)
        on = output.format_search_row(
            "commit-messages", self.DESC, "skill", "fixture-tap", 1.0,
            curated=False, installed=True, lay=lay)
        off = output.format_search_row(
            "commit-messages", self.DESC, "skill", "fixture-tap", 1.0,
            curated=False, installed=False, lay=lay)
        assert on[5] == "●" and off[5] == " "
        # the column is reserved either way, so names still align
        assert on.index("commit-messages") == off.index("commit-messages")

    def test_tap_column_present_at_100_columns(self):
        row = output.format_search_row(
            "commit-messages", self.DESC, "skill", "fixture-tap", 1.0,
            curated=False, installed=False, lay=self._lay(100))
        assert "fixture-tap" in row

    def test_tap_column_absent_at_60_columns(self):
        row = output.format_search_row(
            "commit-messages", self.DESC, "skill", "fixture-tap", 1.0,
            curated=False, installed=False, lay=self._lay(60))
        assert "fixture-tap" not in row

    def test_no_trailing_whitespace_ever(self):
        for curated in (False, True):
            row = output.format_search_row(
                "tdd-workflow", "", "workflow", "", 0.5,
                curated=curated, installed=False, lay=self._lay(60))
            assert row == row.rstrip()

    def test_color_state_never_changes_the_glyphs(self, monkeypatch):
        lay = self._lay(60)
        plainr = output.format_search_row(
            "commit-messages", self.DESC, "skill", "fixture-tap", 1.0,
            curated=True, installed=True, lay=lay)
        monkeypatch.setenv("BOOST_COLOR", "always")
        monkeypatch.setenv("COLORTERM", "truecolor")
        colored = output.format_search_row(
            "commit-messages", self.DESC, "skill", "fixture-tap", 1.0,
            curated=True, installed=True, lay=lay)
        assert output._ANSI_RE.sub("", colored) == plainr
        assert colored.count("▰") == plainr.count("▰")

    def test_wide_row_exact_bytes_with_kind_and_tap(self):
        # The 100-column shape end to end: a workflow's kind text, the tap
        # cell, and everything before them — one mangled cell breaks the row.
        lay = self._lay(100)
        row = output.format_search_row(
            "tdd-workflow", self.DESC, "workflow", "fixture-tap", 1.0,
            curated=False, installed=False, lay=lay)
        expected = ("▰▰▰▰   " + "tdd-workflow".ljust(lay.name_w) + "  "
                    + "[workflow]".ljust(lay.kind_w) + "  "
                    + "fixture-tap".ljust(lay.tap_w) + "  "
                    + output.truncate(self.DESC, lay.desc_w))
        assert row == expected.rstrip()

    def test_wide_color_row_strips_back_to_the_plain_row(self, monkeypatch):
        # Runs every colored cell (meter, mark, name, kind, tap) through its
        # role for real — a misnamed role raises here instead of shipping.
        lay = self._lay(100)
        plainr = output.format_search_row(
            "tdd-workflow", self.DESC, "workflow", "fixture-tap", 0.5,
            curated=True, installed=True, lay=lay)
        monkeypatch.setenv("BOOST_COLOR", "always")
        monkeypatch.setenv("COLORTERM", "truecolor")
        colored = output.format_search_row(
            "tdd-workflow", self.DESC, "workflow", "fixture-tap", 0.5,
            curated=True, installed=True, lay=lay)
        assert output._ANSI_RE.sub("", colored) == plainr

    def test_trailing_padding_is_actually_stripped(self):
        # A short kind cell ends the row in pad spaces before the rstrip; the
        # stripped row must end on the glyph, not the padding.
        row = output.format_search_row(
            "tdd-workflow", "", "skill", "", 0.5,
            curated=False, installed=False, lay=self._lay(60))
        assert row.endswith("[skill]")

    def test_curated_lead_boundary_exact_bytes(self):
        # The tail's lead shrinks to one space exactly when the description
        # budget cannot cover the 11-cell tail: two spaces at desc_w 10, one
        # at desc_w 9 — asserted as whole rows so the tail cannot detach.
        base = "▰▰▰▰   commit-messages  " + "[skill]".ljust(10)
        two = output.format_search_row(
            "commit-messages", "", "skill", "", 1.0, curated=True,
            installed=False,
            lay=output.SearchLayout(cols=60, name_w=15, kind_w=10, tap_w=0,
                                    desc_w=10))
        assert two == base + "  ★ curated"
        one = output.format_search_row(
            "commit-messages", "", "skill", "", 1.0, curated=True,
            installed=False,
            lay=output.SearchLayout(cols=60, name_w=15, kind_w=10, tap_w=0,
                                    desc_w=9))
        assert one == base + " ★ curated"

    def test_meter_is_tinted_by_magnitude_hue(self, monkeypatch):
        monkeypatch.setenv("BOOST_COLOR", "always")
        monkeypatch.setenv("COLORTERM", "truecolor")
        lay = self._lay(60)
        top = output.format_search_row(
            "a", "d", "skill", "", 1.0, curated=False, installed=False, lay=lay)
        low = output.format_search_row(
            "a", "d", "skill", "", 0.1, curated=False, installed=False, lay=lay)
        assert top.startswith(output.rgb(*output.TOKENS["cyan"]))
        assert low.startswith(output.rgb(*output.TOKENS["pink"]))


class TestWrap:
    """`wrap()` breaks prose to the pane without breaking a copyable command.

    The hints that overflow a narrow pane are prose ending in a backticked
    shell command — `pip install 'boost-skill-cli[rag]'`. A greedy word wrap
    splits that mid-command and the user copies something that does not run, so
    a code span is one atomic token here even though it contains spaces. That
    is the whole reason this is not two lines of `textwrap`.
    """

    def test_short_text_is_one_line_unchanged(self):
        assert output.wrap("a short hint", 40) == ["a short hint"]

    def test_empty_text_wraps_to_nothing(self):
        assert output.wrap("", 40) == []
        assert output.wrap("   ", 40) == []

    def test_exactly_at_the_width_does_not_break(self):
        # 40 columns of content at width 40: the boundary a mutant flipping
        # <= to < would split into two lines.
        text = " ".join(["abcd"] * 8)          # 8*4 + 7 == 39
        assert output.visible_len(text) == 39
        assert output.wrap(text + "z", 40) == [text + "z"]

    def test_one_column_over_breaks(self):
        text = " ".join(["abcd"] * 8) + "zz"   # 41
        assert output.visible_len(text) == 41
        assert len(output.wrap(text, 40)) == 2

    def test_every_line_fits_the_width(self):
        text = " ".join("word%d" % i for i in range(60))
        for line in output.wrap(text, 32):
            assert output.visible_len(line) <= 32

    def test_a_code_span_is_never_split(self):
        text = ("semantic search is off — install the extra: "
                "`pip install 'boost-skill-cli[rag]'`")
        lines = output.wrap(text, 40)
        assert any("`pip install 'boost-skill-cli[rag]'`" in ln for ln in lines)
        # and it is not spread across the break
        for ln in lines:
            assert ln.count("`") % 2 == 0

    def test_a_code_span_wider_than_the_pane_stays_whole(self):
        # Overflowing beats corrupting: a command the user can select and paste
        # is worth one long line; a command cut in half is worth nothing.
        span = "`" + "x" * 50 + "`"
        lines = output.wrap("run " + span + " now", 20)
        assert span in lines

    def test_a_single_word_longer_than_the_width_is_not_broken(self):
        lines = output.wrap("tiny " + "y" * 40, 20)
        assert "y" * 40 in lines

    def test_continuation_lines_carry_the_indent(self):
        text = " ".join(["word"] * 20)
        lines = output.wrap(text, 24, indent="    ")
        assert not lines[0].startswith(" ")
        assert all(ln.startswith("    ") for ln in lines[1:])
        assert all(output.visible_len(ln) <= 24 for ln in lines)

    def test_indent_wider_than_the_width_still_terminates(self):
        # A pathological pane must not loop or emit empty lines forever.
        lines = output.wrap("one two three", 3, indent="        ")
        assert lines
        assert all(ln.strip() for ln in lines)

    def test_width_defaults_to_the_terminal(self, monkeypatch):
        monkeypatch.setattr(output, "term_width", lambda: 24)
        text = " ".join(["word"] * 20)
        assert all(output.visible_len(ln) <= 24 for ln in output.wrap(text))

    def test_it_measures_visible_columns_not_bytes(self, monkeypatch):
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setattr(output, "use_color", lambda *a, **k: True)
        coloured = output.c("word", output.BOLD)
        assert len(coloured) > output.visible_len(coloured)
        lines = output.wrap(" ".join([coloured] * 6), 24)
        assert all(output.visible_len(ln) <= 24 for ln in lines)

    def test_newlines_and_runs_of_space_collapse(self):
        assert output.wrap("a\n\n  b\tc", 40) == ["a b c"]

    def test_no_content_is_lost(self):
        text = "keep every word of this hint including `a b c` intact"
        assert " ".join(output.wrap(text, 12)).split() == text.split()


class TestWrappingEmitters:
    """`warn`/`info`/`dim` wrap only when asked, and to their own prefix."""

    def _out(self, capsys, monkeypatch, fn, text, cols=40, **kw):
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setattr(output, "term_width", lambda: cols)
        fn(text, **kw)
        return capsys.readouterr().out.rstrip("\n").split("\n")

    LONG = " ".join(["word"] * 20)

    def test_warn_does_not_wrap_by_default(self, capsys, monkeypatch):
        lines = self._out(capsys, monkeypatch, output.warn, self.LONG)
        assert len(lines) == 1

    def test_info_does_not_wrap_by_default(self, capsys, monkeypatch):
        lines = self._out(capsys, monkeypatch, output.info, self.LONG)
        assert len(lines) == 1

    def test_dim_does_not_wrap_by_default(self, capsys, monkeypatch):
        lines = self._out(capsys, monkeypatch, output.dim, self.LONG)
        assert len(lines) == 1

    def test_warn_wrapped_fits_including_its_marker(self, capsys, monkeypatch):
        lines = self._out(capsys, monkeypatch, output.warn, self.LONG, wrap=True)
        assert len(lines) > 1
        assert all(output.visible_len(ln) <= 40 for ln in lines)
        assert lines[0].startswith("  ! ")

    def test_warn_continuations_align_under_the_message(self, capsys, monkeypatch):
        lines = self._out(capsys, monkeypatch, output.warn, self.LONG, wrap=True)
        assert all(ln.startswith("    ") for ln in lines[1:])
        assert not lines[1].startswith("    !")

    def test_info_wrapped_fits(self, capsys, monkeypatch):
        lines = self._out(capsys, monkeypatch, output.info, self.LONG, wrap=True)
        assert len(lines) > 1
        assert all(output.visible_len(ln) <= 40 for ln in lines)
        assert all(ln.startswith("  ") for ln in lines)

    def test_dim_wrapped_fits(self, capsys, monkeypatch):
        lines = self._out(capsys, monkeypatch, output.dim, self.LONG, wrap=True)
        assert len(lines) > 1
        assert all(output.visible_len(ln) <= 40 for ln in lines)

    def test_an_empty_wrapped_message_still_prints_a_blank_line(self, capsys,
                                                               monkeypatch):
        monkeypatch.setattr(output, "term_width", lambda: 40)
        output.info("", wrap=True)
        assert capsys.readouterr().out == "\n"

    def test_wrapped_warn_reaches_the_requested_stream(self, capsys, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setattr(output, "term_width", lambda: 40)
        output.warn(self.LONG, stream=sys.stderr, wrap=True)
        cap = capsys.readouterr()
        assert cap.out == ""
        assert len(cap.err.rstrip("\n").split("\n")) > 1


class TestKvWrap:
    """A wrapped `kv` value folds under the value column, not under the key."""

    def _lines(self, capsys, monkeypatch, value, cols=40, **kw):
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setattr(output, "term_width", lambda: cols)
        output.kv("key", value, **kw)
        return capsys.readouterr().out.rstrip("\n").split("\n")

    LONG = " ".join(["value"] * 12)

    def test_it_does_not_wrap_by_default(self, capsys, monkeypatch):
        assert len(self._lines(capsys, monkeypatch, self.LONG)) == 1

    def test_wrapped_lines_fit_the_pane(self, capsys, monkeypatch):
        lines = self._lines(capsys, monkeypatch, self.LONG, wrap=True)
        assert len(lines) > 1
        assert all(output.visible_len(ln) <= 40 for ln in lines)

    def test_continuations_align_under_the_value(self, capsys, monkeypatch):
        lines = self._lines(capsys, monkeypatch, self.LONG, wrap=True)
        col = lines[0].index("value")
        assert col == 16                       # 2 indent + 14 key column
        for ln in lines[1:]:
            assert ln.index("value") == col

    def test_a_non_string_value_still_works(self, capsys, monkeypatch):
        # `boost impact` passes raw ints; wrapping must not reintroduce the
        # TypeError the str() call exists to prevent.
        assert self._lines(capsys, monkeypatch, 42, wrap=True) == [
            "  key           42"]


class TestWrapBoundaries:
    """The two distinctions the shape of `wrap()` turns on."""

    def test_the_first_line_is_not_charged_for_the_indent(self):
        # Four 4-char words plus three spaces is 19. At width 19 with a 6-column
        # indent they all fit line one only if the indent is charged to the
        # *continuations* — charging it up front would break after three.
        text = "aaaa bbbb cccc dddd"
        assert output.visible_len(text) == 19
        assert output.wrap(text, 19, indent="      ") == [text]

    def test_a_coloured_indent_costs_its_columns_not_its_bytes(self, monkeypatch):
        # `wrap` is public and the indent is a caller's string, so it is
        # measured the way every other width in this module is. A plain len()
        # here charges the escape bytes and wraps far short of the pane.
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setattr(output, "use_color", lambda *a, **k: True)
        indent = output.c("  ", output.DIM)
        assert len(indent) > output.visible_len(indent)
        plain = output.wrap(" ".join(["word"] * 12), 20, indent="  ")
        tinted = output.wrap(" ".join(["word"] * 12), 20, indent=indent)
        assert [output.visible_len(x) for x in plain] == \
               [output.visible_len(x) for x in tinted]

    def test_two_code_spans_are_two_tokens_not_one(self):
        # A greedy `` `.*` `` would swallow the prose between them and wrap the
        # pair as a single unbreakable token.
        lines = output.wrap("run `alpha` between `beta` here", 16)
        assert len(lines) > 1
        assert "`alpha`" in " ".join(lines) and "`beta`" in " ".join(lines)
        # Under a greedy regex the two spans and the word between them are one
        # 21-column token, which cannot break and lands on a line of its own.
        assert not any("`alpha` between `beta`" in ln for ln in lines)
        assert all(output.visible_len(ln) <= 16 for ln in lines)
