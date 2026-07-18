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
