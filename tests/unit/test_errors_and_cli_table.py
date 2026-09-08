# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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


EXPECTED_GROUP_SIZES = {"pkg": 13, "find": 9, "info": 10, "tap": 5,
                        "ai": 9, "chk": 15, "cfg": 14, "team": 6}


class TestCommandTable:
    def test_exactly_81_commands(self):
        assert len(cli.COMMANDS) == 81

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
        assert len(cli._BY_NAME) == 81

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
                           "hooks", "bmad", "quickstart"}

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


class TestSystemExitLoggedWithRealRc:
    """argparse raises SystemExit for --help and usage errors, which used to
    skip every except clause in cli.main (SystemExit derives from
    BaseException, not Exception) and leave the trail's preset rc=70 in the
    `done:` line even though the real exit was 0 or 2."""

    def test_subcommand_help_logs_rc_0_not_70(self, boost):
        from boost_cli.core import logs
        boost("install", "--help", expect=0)
        line = logs.log_path().read_text(encoding="utf-8")
        assert "done: boost install --help -> rc=0 in" in line
        assert "rc=70" not in line
        assert "WARNING" not in line  # clean exit stays at INFO

    def test_subcommand_usage_error_logs_rc_2_not_70(self, boost):
        from boost_cli.core import logs
        boost("install", expect=2)  # missing required NAME positional
        line = logs.log_path().read_text(encoding="utf-8")
        assert "done: boost install -> rc=2 in" in line
        assert "rc=70" not in line
        assert "WARNING" in line  # non-zero rc still stands out


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
        assert "81 commands · 8 groups" in out
        assert "Homebrew for AI coding skills" in out

    def test_help_flag_lists_every_command(self, sandbox, capsys):
        assert cli.main(["--help"]) == 0
        out = capsys.readouterr().out
        for name, _g, _m, _s in cli.COMMANDS:
            assert "\n  %s" % name in out, name
        for _icon, title, _desc in cli.GROUPS.values():
            assert title in out

    @pytest.mark.parametrize("cols", [60, 80, 100, 120])
    def test_help_never_overflows_the_terminal(self, sandbox, capsys,
                                               monkeypatch, cols):
        """The top-level help was the one screen in the CLI that ignored the
        terminal: `search` drops columns and truncates at 60, while `boost
        --help` emitted a 105-column banner at every width, wrapping mid-word
        for anyone not running a wide pane.
        """
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("COLUMNS", str(cols))
        assert cli.main(["--help"]) == 0
        for line in capsys.readouterr().out.splitlines():
            assert cli.out.visible_len(line) <= cols, line

    def test_help_keeps_the_product_name_and_version_at_60_columns(
            self, sandbox, capsys, monkeypatch):
        """Fitting the banner must not cost the two facts it carries."""
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("COLUMNS", "60")
        assert cli.main(["--help"]) == 0
        out = capsys.readouterr().out
        assert "Homebrew for AI coding skills" in out
        assert cli.__version__ in out
        assert "81 commands · 8 groups" in out

    def test_help_still_names_every_command_when_narrow(self, sandbox, capsys,
                                                        monkeypatch):
        """Summaries may be clipped to fit; command names never are, or the
        help stops being usable as an index."""
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("COLUMNS", "60")
        assert cli.main(["--help"]) == 0
        out = capsys.readouterr().out
        for name, _g, _m, _s in cli.COMMANDS:
            assert "\n  %s" % name in out, name

    def test_help_summaries_are_whole_when_piped(self, sandbox, capsys,
                                                 monkeypatch):
        """A pipe has no pane to fit, so `boost --help | grep` sees the whole
        summary rather than one clipped to an assumed 80 columns."""
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("COLUMNS", raising=False)
        assert cli.main(["--help"]) == 0
        out = capsys.readouterr().out
        assert "…" not in out
        for _n, _g, _m, summary in cli.COMMANDS:
            assert summary in out, summary

    def test_help_word(self, sandbox, capsys):
        assert cli.main(["help"]) == 0
        assert "81 commands · 8 groups" in capsys.readouterr().out

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


class TestBrokenPipeBeforeDispatch:
    """The early-return paths (--help, --version, help, __complete) used to
    sit entirely outside main's try/except, so a BrokenPipeError raised while
    printing them propagated straight out of main() uncaught.

    `_seal_broken_stdout` is stubbed out in these tests: its real job is an
    `os.dup2` onto the process's actual stdout fd, and exercising that for
    real against pytest's own captured fd would corrupt capture for the rest
    of the session. Its own tolerance-of-failure is covered directly below,
    without ever reaching the real dup2.
    """

    def test_help_flag_broken_pipe_is_caught(self, sandbox, monkeypatch):
        monkeypatch.setattr(cli, "print_help",
                            lambda: (_ for _ in ()).throw(BrokenPipeError()))
        monkeypatch.setattr(cli, "_seal_broken_stdout", lambda: None)
        assert cli.main(["--help"]) == 0

    def test_version_broken_pipe_is_caught(self, sandbox, monkeypatch):
        monkeypatch.setattr(cli, "print_version",
                            lambda: (_ for _ in ()).throw(BrokenPipeError()))
        monkeypatch.setattr(cli, "_seal_broken_stdout", lambda: None)
        assert cli.main(["--version"]) == 0

    def test_seal_broken_stdout_tolerates_a_closed_fd(self, sandbox,
                                                      monkeypatch):
        """Even if flush/fileno both raise, the seal must not escalate.

        Swaps the `sys.stdout` *name* for a bare fake rather than mutating
        the real captured stream's attributes, and stubs `fileno()` rather
        than `os.open`/`os.dup2` — pytest's own fd-level capture calls both
        of those for its own bookkeeping, so faking them globally corrupts
        capture for the rest of the session instead of testing anything.
        """
        import sys

        class _AlwaysBroken:
            def flush(self):
                raise OSError("broken")

            def fileno(self):
                raise OSError("no fd")

        monkeypatch.setattr(sys, "stdout", _AlwaysBroken())
        cli._seal_broken_stdout()  # must not raise


class TestBrokenPipeSurfacedByTheFinalFlush:
    """A write that merely fits the pipe's kernel buffer (`--help`, `count`,
    small dispatch output) does not raise BrokenPipeError until something
    explicitly flushes. `_route` now forces that flush itself, still inside
    main's own handler, instead of leaving it to the interpreter's own
    unhandled exit-time flush."""

    def test_flush_only_broken_pipe_is_still_caught(self, sandbox, monkeypatch):
        # Wraps (rather than mutates) the real captured stream: writes still
        # reach pytest's own capture through __getattr__ delegation, only
        # flush() is faulty — mutating the real stream's .flush attribute
        # directly risks pytest's own capture machinery calling it too.
        import sys

        import boost_cli.commands.taps as taps_mod

        class _BrokenFlush:
            def __init__(self, real):
                self._real = real

            def flush(self):
                raise BrokenPipeError

            def __getattr__(self, name):
                return getattr(self._real, name)

        monkeypatch.setattr(taps_mod, "cmd_taps", lambda argv: 0)
        monkeypatch.setattr(sys, "stdout", _BrokenFlush(sys.stdout))
        monkeypatch.setattr(cli, "_seal_broken_stdout", lambda: None)
        assert cli.main(["taps"]) == 0


class TestHelpRoutingAliases:
    """`boost help <X>` must resolve main's own aliases the same way `boost
    <X>` does, rather than treating them as unknown commands and
    difflib-guessing an unrelated one (`--help` -> "heal", `version` ->
    "verify")."""

    def test_help_dash_dash_help(self, sandbox, capsys):
        assert cli.main(["help", "--help"]) == 0
        out = capsys.readouterr().out
        assert "81 commands · 8 groups" in out

    def test_help_dash_h(self, sandbox, capsys):
        assert cli.main(["help", "-h"]) == 0
        assert "81 commands · 8 groups" in capsys.readouterr().out

    def test_help_version_word(self, sandbox, capsys):
        assert cli.main(["help", "version"]) == 0
        assert VERSION_LINE.match(capsys.readouterr().out.rstrip("\n"))

    def test_help_dash_capital_v(self, sandbox, capsys):
        assert cli.main(["help", "-V"]) == 0
        assert VERSION_LINE.match(capsys.readouterr().out.rstrip("\n"))

    def test_help_help(self, sandbox, capsys):
        assert cli.main(["help", "help"]) == 0
        assert "boost help [COMMAND]" in capsys.readouterr().out


class TestUnknownOptionVsCommand:
    """A dash-prefixed typo is a mistyped flag, not a command guess — nothing
    in COMMANDS is a plausible correction for `--hepl`."""

    def test_dash_token_reports_unknown_option(self, sandbox, capsys):
        assert cli.main(["--hepl"]) == 2
        err = capsys.readouterr().err
        assert "unknown option: --hepl" in err
        assert "did you mean" not in err

    def test_dash_token_hints_help(self, sandbox, capsys):
        assert cli.main(["--nope"]) == 2
        assert "see `boost --help`" in capsys.readouterr().err

    def test_bare_word_typo_is_unaffected(self, sandbox, capsys):
        # regression guard: only dash-prefixed tokens change behavior
        assert cli.main(["instal"]) == 2
        err = capsys.readouterr().err
        assert "unknown command: instal" in err
        assert "did you mean" in err


class TestGlobalOptionsLine:
    def test_help_documents_the_global_flags(self, sandbox, capsys):
        assert cli.main(["--help"]) == 0
        out = capsys.readouterr().out
        assert "-V/--version" in out
        assert "-v/--verbose" in out
        assert "--debug" in out
        assert "-q/--quiet" in out


class TestPrintHelpColorRole:
    """The command-name column is the same semantic role ("accent") as every
    other command name in the CLI — search results, `boost info`'s badges,
    etc. — all of which resolve through out.role("accent") to Aurora
    truecolor cyan. print_help painted it with a raw 16-color ANSI CYAN
    instead, so on a truecolor terminal the top-level help screen's command
    names are a visibly different cyan than everywhere else."""

    def test_command_names_use_the_accent_role_not_raw_cyan(
            self, capsys, monkeypatch):
        from boost_cli.core import output as out
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        monkeypatch.delenv("NO_COLOR", raising=False)
        cli.print_help()
        rendered = capsys.readouterr().out
        accent_code = out.rgb(*out.TOKENS["cyan"])
        assert accent_code in rendered
        # the raw 16-color escape must not appear standing in for it
        assert out.CYAN not in rendered
