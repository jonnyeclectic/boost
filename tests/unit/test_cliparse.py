# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/cliparse.BoostArgumentParser — branded errors."""
from __future__ import annotations

import io
import sys

import pytest

from boost_cli import cliparse
from boost_cli.core import output


class _TtyBuffer(io.StringIO):
    """A buffer that claims to be a terminal, so `use_color` says yes."""

    def isatty(self):
        return True


@pytest.fixture(autouse=True)
def plain(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")


def test_parser_returns_boost_subclass():
    p = cliparse.parser(prog="boost demo")
    assert isinstance(p, cliparse.BoostArgumentParser)


def test_error_is_branded_and_exits_2(capsys):
    p = cliparse.parser(prog="boost demo")
    p.add_argument("name")
    with pytest.raises(SystemExit) as exc:
        p.parse_args([])            # missing required positional
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert err.startswith("Error: ")           # branded, not bare "usage:"
    assert "the following arguments are required" in err
    assert "usage: boost demo" in err          # usage still shown, below


def test_valid_args_do_not_error(capsys):
    p = cliparse.parser(prog="boost demo")
    p.add_argument("--flag", action="store_true")
    ns = p.parse_args(["--flag"])
    assert ns.flag is True
    assert capsys.readouterr().err == ""


def test_subparsers_inherit_branding():
    p = cliparse.parser(prog="boost demo")
    sub = p.add_subparsers()
    child = sub.add_parser("go")
    assert isinstance(child, cliparse.BoostArgumentParser)


class TestHelpWrapKeepsBacktickSpansAtomic:
    """--help text wraps like every other long line in this CLI: a backtick
    span is one atomic token, never split across lines (out.wrap's rule,
    reused here instead of argparse's plain textwrap.wrap).

    `boost replay --help` at a narrow terminal split `boost replay list`
    across two lines — a command the user cannot select and paste intact.
    """

    def test_argument_help_never_splits_a_backtick_command(self, monkeypatch,
                                                            capsys):
        monkeypatch.setenv("COLUMNS", "60")
        p = cliparse.parser(prog="boost replay")
        p.add_argument("id", nargs="?",
                       help="history entry id (from `boost replay list`)")
        with pytest.raises(SystemExit):
            p.parse_args(["--help"])
        out = capsys.readouterr().out
        assert "`boost replay list`" in out
        # the backtick span must appear whole on one physical line
        assert any("`boost replay list`" in ln for ln in out.split("\n"))

    def test_argument_help_still_wraps_plain_prose(self, monkeypatch,
                                                    capsys):
        monkeypatch.setenv("COLUMNS", "40")
        p = cliparse.parser(prog="boost demo")
        p.add_argument("--flag", action="store_true",
                       help=" ".join(["word"] * 15))
        with pytest.raises(SystemExit):
            p.parse_args(["--help"])
        lines = capsys.readouterr().out.rstrip("\n").split("\n")
        assert any(ln.count("word") > 1 for ln in lines)  # actually wrapped
        assert all(len(ln) <= 40 for ln in lines)

    def test_description_with_backtick_command_stays_atomic(self, monkeypatch,
                                                             capsys):
        monkeypatch.setenv("COLUMNS", "50")
        p = cliparse.parser(
            prog="boost demo",
            description="Some prose ahead of `boost demo really long command`")
        with pytest.raises(SystemExit):
            p.parse_args(["--help"])
        out = capsys.readouterr().out
        assert any("`boost demo really long command`" in ln
                   for ln in out.split("\n"))


class TestUsageColourFollowsStderr:
    """The dimmed usage block is written to stderr, so stderr decides it.

    `error()` prints two lines to the same stream and used to ask two
    different questions about them: `out.err` consults stderr, while the
    `out.c(..., DIM)` around the usage consulted stdout. `boost demo 2>log`
    on a terminal wrote a bare `Error:` into the log and then an escape
    sequence around the usage right under it; `boost demo >out` printed a red
    `Error:` on the terminal and an undimmed usage below. One error report,
    two answers.
    """

    @pytest.fixture(autouse=True)
    def colour_on(self, monkeypatch, plain):
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
        monkeypatch.delenv("BOOST_COLOR", raising=False)

    @staticmethod
    def _fail(monkeypatch, stdout, stderr):
        monkeypatch.setattr(sys, "stdout", stdout)
        monkeypatch.setattr(sys, "stderr", stderr)
        p = cliparse.parser(prog="boost demo")
        p.add_argument("name")
        with pytest.raises(SystemExit):
            p.parse_args([])

    def test_a_redirected_stderr_gets_no_escape_at_all(self, monkeypatch):
        e = io.StringIO()
        self._fail(monkeypatch, _TtyBuffer(), e)
        assert "\x1b[" not in e.getvalue()
        assert "usage: boost demo" in e.getvalue()

    def test_a_terminal_stderr_dims_the_usage_too(self, monkeypatch):
        e = _TtyBuffer()
        self._fail(monkeypatch, io.StringIO(), e)
        text = e.getvalue()
        # the branded `Error: ` span, then a DIM span per line of the usage
        # block -- `format_usage` ends in a newline, so the last of those is
        # the empty trailing line. Three spans, all on stderr.
        assert text.count(output.RESET) == 3
        assert text.startswith(output.RED + output.BOLD + "Error: ")
        assert output.DIM + "usage: boost demo" in text

    def test_argparse_does_not_paint_the_usage_before_boost_does(
            self, monkeypatch):
        """3.14's argparse asks the same wrong question, so boost turns it off.

        `ArgumentParser(color=True)` is the 3.14 default and it decides by
        calling `_colorize.can_colorize()`, whose `file` defaults to
        **stdout** -- for text `error()` writes to stderr. On top of the
        redirect bug this whole class is about, the two paints nest: the
        usage goes out inside one `out.c(..., DIM)` span, and argparse's own
        reset after `usage: ` ends the dim two words in. So the text must
        reach `out.c` bare, whatever the environment says.
        """
        monkeypatch.setenv("PYTHON_COLORS", "1")
        monkeypatch.setenv("FORCE_COLOR", "1")
        p = cliparse.parser(prog="boost demo")
        p.add_argument("name")
        assert "\x1b[" not in p.format_usage()
        assert "\x1b[" not in p.format_help()

    def test_a_subparser_does_not_paint_it_either(self, monkeypatch):
        """Every `boost <cmd> --help` is a sub-parser, so the property has to
        hold there too.

        It holds by inheritance rather than by the `setdefault`: unlike
        `formatter_class`, argparse forwards `color` down explicitly, filling
        `add_parser`'s kwargs from the parent (3.14's argparse.py:1252) and
        stamping `action._color` at :1979. So this pins argparse's forwarding
        and the user-visible result -- not where boost sets the default,
        which the test cannot distinguish.
        """
        monkeypatch.setenv("PYTHON_COLORS", "1")
        sub = cliparse.parser(prog="boost").add_subparsers().add_parser("demo")
        sub.add_argument("name")
        assert "\x1b[" not in sub.format_usage()


class TestAnUnknownOptionOutranksAMissingArgument:
    """argparse checks required arguments before unknown ones, so a typo'd
    flag with no positional (`boost install -x`) was reported as a missing
    NAME. The unknown option is named instead; a bare missing argument still
    says what it always said."""

    def _parser(self):
        p = cliparse.parser(prog="boost demo")
        p.add_argument("name")
        p.add_argument("--json", action="store_true")
        p.add_argument("-n", "--count", type=int)
        return p

    def _err(self, capsys, argv):
        with pytest.raises(SystemExit) as exc:
            self._parser().parse_args(argv)
        assert exc.value.code == 2
        return capsys.readouterr().err.splitlines()[0]

    def test_an_unknown_short_flag_is_named(self, capsys):
        assert self._err(capsys, ["-x"]) == "Error: unrecognized arguments: -x"

    def test_every_unknown_option_is_named_in_order(self, capsys):
        assert (self._err(capsys, ["--bogus=1", "--json", "-x"])
                == "Error: unrecognized arguments: --bogus=1 -x")

    def test_no_unknown_option_keeps_the_required_error(self, capsys):
        assert (self._err(capsys, ["--json"])
                == "Error: the following arguments are required: name")

    @pytest.mark.parametrize("argv", [
        ["--count=3"],          # a known option spelled with `=`
        ["--cou", "3"],         # an abbreviation argparse accepts
        ["-n3"],                # a short option with its value glued on
    ])
    def test_known_options_are_not_unknown(self, capsys, argv):
        assert (self._err(capsys, argv)
                == "Error: the following arguments are required: name")

    @pytest.mark.parametrize("tok", ["-", "-5", "plain", "-x not a flag"])
    def test_values_are_not_options(self, tok):
        # stdin's `-`, a negative number, a bare word and a token holding a
        # space are positionals, as argparse decides.
        p = self._parser()
        p._boost_argv = [tok]
        assert p._unknown_options() == []

    def test_a_spaced_option_value_keeps_the_required_error(self, capsys):
        p = self._parser()
        p.add_argument("--note")
        with pytest.raises(SystemExit):
            p.parse_args(["--note", "-x not a flag"])
        assert (capsys.readouterr().err.splitlines()[0]
                == "Error: the following arguments are required: name")

    def test_tokens_after_a_double_dash_are_positional(self):
        p = self._parser()
        p._boost_argv = ["--", "-x"]
        assert p._unknown_options() == []

    def test_a_long_option_is_not_read_as_a_glued_short_one(self):
        # `--nope`'s first two characters are `--`, never a short option;
        # the glued-short rule must not wave a long option through.
        p = self._parser()
        p._boost_argv = ["--nope"]
        assert p._unknown_options() == ["--nope"]

    def test_a_hinted_error_is_left_alone(self, capsys):
        p = self._parser()
        p._boost_argv = ["-x"]
        with pytest.raises(SystemExit):
            p.error("the following arguments are required: KEY", hint="eg")
        assert capsys.readouterr().err.splitlines()[0] == (
            "Error: the following arguments are required: KEY")

    def test_a_required_group_error_is_replaced_too(self, capsys):
        p = cliparse.parser(prog="boost demo")
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--a", action="store_true")
        g.add_argument("--b", action="store_true")
        with pytest.raises(SystemExit):
            p.parse_args(["-x"])
        assert (capsys.readouterr().err.splitlines()[0]
                == "Error: unrecognized arguments: -x")

    def test_subparser_sees_its_own_argv(self, capsys):
        p = cliparse.parser(prog="boost demo")
        sub = p.add_subparsers(dest="cmd")
        go = sub.add_parser("go")
        go.add_argument("name")
        with pytest.raises(SystemExit):
            p.parse_args(["go", "-x"])
        assert (capsys.readouterr().err.splitlines()[0]
                == "Error: unrecognized arguments: -x")
