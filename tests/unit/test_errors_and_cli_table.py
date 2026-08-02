"""Unit tests: boost_cli/errors.py and the boost_cli/cli.py command table."""
from __future__ import annotations

import importlib
import re
from collections import Counter

import pytest

from boost_cli import cli
from boost_cli.errors import BoostError


class TestBoostError:
    def test_message_and_hint_attrs(self):
        e = BoostError("boom", hint="try this")
        assert e.message == "boom"
        assert e.hint == "try this"
        assert str(e) == "boom"

    def test_hint_defaults_to_none(self):
        e = BoostError("plain failure")
        assert e.message == "plain failure"
        assert e.hint is None

    def test_is_an_exception(self):
        assert issubclass(BoostError, Exception)
        with pytest.raises(BoostError):
            raise BoostError("x")


EXPECTED_GROUP_SIZES = {"pkg": 13, "find": 9, "info": 10, "tap": 4,
                        "ai": 9, "chk": 15, "cfg": 12, "team": 6}


class TestCommandTable:
    def test_exactly_78_commands(self):
        assert len(cli.COMMANDS) == 78

    def test_exactly_8_groups(self):
        assert len(cli.GROUPS) == 8
        assert set(cli.GROUPS) == set(EXPECTED_GROUP_SIZES)

    def test_group_sizes(self):
        sizes = Counter(g for _n, g, _m, _s in cli.COMMANDS)
        assert dict(sizes) == EXPECTED_GROUP_SIZES

    def test_no_duplicate_names(self):
        names = [n for n, _g, _m, _s in cli.COMMANDS]
        dupes = [n for n, k in Counter(names).items() if k > 1]
        assert dupes == []
        assert len(cli._BY_NAME) == 78

    def test_every_command_group_exists(self):
        for name, group, _module, _summary in cli.COMMANDS:
            assert group in cli.GROUPS, name

    def test_group_icon_token_matches_key(self):
        for key, (icon, title, desc) in cli.GROUPS.items():
            assert icon == key
            assert title and desc

    def test_every_command_has_a_summary(self):
        for name, _g, _m, summary in cli.COMMANDS:
            assert summary.strip(), name

    def test_expected_module_set(self):
        modules = {m for _n, _g, m, _s in cli.COMMANDS}
        assert modules == {"pkg", "run", "discovery", "info", "taps", "intelligence",
                           "quality", "safety", "configuration", "team",
                           "hooks", "bmad"}

    @pytest.mark.parametrize(
        "name,group,module",
        [(n, g, m) for n, g, m, _s in cli.COMMANDS],
        ids=[n for n, _g, _m, _s in cli.COMMANDS])
    def test_command_function_exists(self, name, group, module):
        mod = importlib.import_module("boost_cli.commands.%s" % module)
        func = getattr(mod, "cmd_%s" % name.replace("-", "_"), None)
        assert callable(func), (
            "boost_cli.commands.%s lacks cmd_%s" % (module,
                                                   name.replace("-", "_")))


class TestResolve:
    def test_hit(self):
        assert cli.resolve("install") == (
            "pkg", "pkg", "Install a skill from a tap registry")
        assert cli.resolve("self-update") == (
            "cfg", "configuration",
            "Update boost itself to the latest version")

    def test_miss_returns_none(self):
        assert cli.resolve("definitely-not-a-command") is None
        assert cli.resolve("") is None


def run_main(argv):
    """cli.main, tolerating argparse's SystemExit like the real entrypoint."""
    try:
        return cli.main(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0


# The version token varies by environment (semver from a tag, a dev version,
# or a bare commit SHA in a tag-less shallow checkout) — only assert shape.
VERSION_LINE = re.compile(r"^boost \S+$")


class TestMainDispatch:
    def test_version_flag(self, sandbox, capsys):
        assert cli.main(["--version"]) == 0
        out = capsys.readouterr().out
        assert VERSION_LINE.match(out.rstrip("\n"))
        assert out.endswith("\n")

    def test_version_word_and_short_flag(self, sandbox, capsys):
        assert cli.main(["version"]) == 0
        assert cli.main(["-V"]) == 0
        lines = capsys.readouterr().out.splitlines()
        assert len(lines) == 2
        assert all(VERSION_LINE.match(line) for line in lines)
        assert lines[0] == lines[1]

    def test_no_args_prints_help(self, sandbox, capsys):
        assert cli.main([]) == 0
        out = capsys.readouterr().out
        assert "78 commands · 8 groups" in out
        assert "Homebrew for AI coding skills" in out

    def test_help_flag_lists_every_command(self, sandbox, capsys):
        assert cli.main(["--help"]) == 0
        out = capsys.readouterr().out
        for name, _g, _m, _s in cli.COMMANDS:
            assert "\n  %s" % name in out, name
        for _icon, title, _desc in cli.GROUPS.values():
            assert title in out

    def test_help_word(self, sandbox, capsys):
        assert cli.main(["help"]) == 0
        assert "78 commands · 8 groups" in capsys.readouterr().out

    def test_help_for_command(self, sandbox, capsys):
        rc = run_main(["help", "install"])
        assert rc == 0
        out = capsys.readouterr().out
        assert out.startswith(
            "boost install — Install a skill from a tap registry\n")

    def test_help_for_unknown_command(self, sandbox, capsys):
        assert cli.main(["help", "nope-cmd"]) == 2
        assert "unknown command: nope-cmd" in capsys.readouterr().err

    def test_typo_suggests_closest(self, sandbox, capsys):
        assert cli.main(["instal"]) == 2
        err = capsys.readouterr().err
        assert "unknown command: instal" in err
        assert "did you mean" in err and "install" in err

    def test_unknown_without_close_match_hints_help(self, sandbox, capsys):
        assert cli.main(["zzzqqqxx"]) == 2
        err = capsys.readouterr().err
        assert "unknown command: zzzqqqxx" in err
        assert "see `boost --help`" in err

    def test_boost_error_prints_and_returns_1(self, sandbox, capsys,
                                             monkeypatch):
        import boost_cli.commands.taps as taps_mod

        def boom(argv):
            raise BoostError("it broke", hint="fix it")
        monkeypatch.setattr(taps_mod, "cmd_taps", boom)
        assert cli.main(["taps"]) == 1
        err = capsys.readouterr().err
        assert "Error: it broke" in err
        assert "hint: fix it" in err

    def test_keyboard_interrupt_returns_130(self, sandbox, capsys,
                                            monkeypatch):
        import boost_cli.commands.taps as taps_mod

        def interrupted(argv):
            raise KeyboardInterrupt
        monkeypatch.setattr(taps_mod, "cmd_taps", interrupted)
        assert cli.main(["taps"]) == 130

    def test_none_return_coerced_to_0(self, sandbox, monkeypatch):
        import boost_cli.commands.taps as taps_mod
        monkeypatch.setattr(taps_mod, "cmd_taps", lambda argv: None)
        assert cli.main(["taps"]) == 0

    def test_command_rc_passed_through(self, sandbox, monkeypatch):
        import boost_cli.commands.taps as taps_mod
        monkeypatch.setattr(taps_mod, "cmd_taps", lambda argv: 7)
        assert cli.main(["taps"]) == 7

    def test_broken_pipe_returns_0(self, sandbox, monkeypatch):
        import sys

        import boost_cli.commands.taps as taps_mod

        def pipe(argv):
            raise BrokenPipeError
        monkeypatch.setattr(taps_mod, "cmd_taps", pipe)
        # don't let main() close pytest's captured stdout
        monkeypatch.setattr(sys.stdout, "close", lambda: None, raising=False)
        assert cli.main(["taps"]) == 0

    def test_broken_pipe_tolerates_close_failure(self, sandbox, monkeypatch):
        import sys

        import boost_cli.commands.taps as taps_mod
        monkeypatch.setattr(
            taps_mod, "cmd_taps",
            lambda argv: (_ for _ in ()).throw(BrokenPipeError()))

        def bad_close():
            raise ValueError("already closed")
        monkeypatch.setattr(sys.stdout, "close", bad_close, raising=False)
        assert cli.main(["taps"]) == 0

    def test_missing_function_soft_and_hard(self, sandbox, capsys,
                                            monkeypatch):
        import boost_cli.commands.taps as taps_mod
        monkeypatch.delattr(taps_mod, "cmd_taps")
        assert cli._dispatch("taps", [], soft=True) == 0
        assert cli.main(["taps"]) == 3
        assert "command taps is not implemented yet" in (
            capsys.readouterr().err)
