# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/cliparse.BoostArgumentParser — branded errors."""
from __future__ import annotations

import pytest

from boost_cli import cliparse


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
