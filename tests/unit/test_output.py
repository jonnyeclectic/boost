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
