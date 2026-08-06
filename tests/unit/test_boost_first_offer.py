"""Unit tests: the `boost-first` consent flow in commands/configuration.py.

`_offer_boost_first` proposes the most invasive thing boost ships — standing
text in a file the user reads every session, in every project. Four properties
make that defensible, and none of them were pinned before this file existed:
the body is printed **in full** before the question, the answer **defaults to
No**, the offer is **scoped** to hosts where boost actually registered, and
`BOOST_NO_RULE` is checked **before** `out.confirm`.

That last one is not a style preference. `out.confirm` returns True whenever
`BOOST_ASSUME_YES` is set or `--yes`/`-y` appears anywhere in `sys.argv` — and
the test fixtures set exactly that, as does every unattended provisioning
script. Move the guard below the confirm and the offer stops being an offer:
every existing `boost mcp register` test, and every CI run that ever calls it,
silently writes a managed block into a real `CLAUDE.md`.
"""
from __future__ import annotations

import pytest

from boost_cli.commands import configuration
from boost_cli.core import builtin, lockfile, store
from boost_cli.errors import BoostError

RULE = builtin.BUILTIN_RULES[0]


@pytest.fixture
def offering(sandbox, monkeypatch):
    """A sandbox with the suppression guard lifted, so the offer can run.

    `sandbox` sets BOOST_NO_RULE=1 precisely so the rest of the suite never
    trips this path; a test that means to exercise it has to say so.
    """
    monkeypatch.delenv(configuration.NO_RULE_ENV, raising=False)
    monkeypatch.setattr("sys.argv", ["boost", "mcp", "register"])
    return sandbox


def _body_lines():
    return (builtin.source_dir() / (RULE + ".mdc")).read_text(
        encoding="utf-8").splitlines()


class TestTheEnvGuardIsCheckedBeforeConfirm:
    """The ordering that keeps an offer an offer. See the module docstring."""

    def test_boost_no_rule_suppresses_the_offer_entirely(
            self, sandbox, monkeypatch, capsys):
        monkeypatch.setenv(configuration.NO_RULE_ENV, "1")
        configuration._offer_boost_first(["claude"])
        assert capsys.readouterr().out == ""
        assert lockfile.get_rule(RULE) is None

    def test_the_guard_wins_over_assume_yes(self, sandbox, monkeypatch, capsys):
        # Both are set — exactly the fixture/CI configuration. If the guard
        # ever moves below `out.confirm`, BOOST_ASSUME_YES makes confirm return
        # True and this installs standing text without anyone being asked.
        monkeypatch.setenv(configuration.NO_RULE_ENV, "1")
        monkeypatch.setenv("BOOST_ASSUME_YES", "1")
        configuration._offer_boost_first(["claude", "gemini"])
        assert lockfile.get_rule(RULE) is None
        assert capsys.readouterr().out == ""

    def test_an_empty_value_does_not_suppress(self, offering, monkeypatch,
                                              capsys):
        # `os.environ.get(...)` is falsy for "", so an exported-but-empty
        # BOOST_NO_RULE must still offer. Pins the guard to truthiness rather
        # than mere presence.
        monkeypatch.setenv(configuration.NO_RULE_ENV, "")
        monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
        configuration._offer_boost_first(["claude"])
        assert RULE in capsys.readouterr().out


class TestTheOfferIsScopedToHostsBoostRegistered:
    """Naming `boost_search` to an agent without it advertises a phantom."""

    def test_no_hosts_no_offer(self, offering, capsys):
        configuration._offer_boost_first([])
        assert capsys.readouterr().out == ""

    def test_a_host_boost_does_not_map_yields_no_offer(self, offering, capsys):
        # AGENT_FOR_HOST has no "cursor" key, so the target set is empty even
        # though cursor is an enabled agent with a rules dir.
        configuration._offer_boost_first(["cursor"])
        assert capsys.readouterr().out == ""

    def test_claude_names_the_claude_context_file_and_no_other(
            self, offering, monkeypatch, capsys):
        monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
        configuration._offer_boost_first(["claude"])
        out = capsys.readouterr().out
        assert "CLAUDE.md" in out
        assert ".cursor" not in out and ".windsurf" not in out
        assert "GEMINI.md" not in out

    def test_gemini_names_gemini_md(self, offering, monkeypatch, capsys):
        monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
        configuration._offer_boost_first(["gemini"])
        out = capsys.readouterr().out
        assert "GEMINI.md" in out
        assert "CLAUDE.md" not in out

    def test_both_hosts_name_both_targets(self, offering, monkeypatch, capsys):
        monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
        configuration._offer_boost_first(["claude", "gemini"])
        out = capsys.readouterr().out
        assert "CLAUDE.md" in out and "GEMINI.md" in out


class TestConsentIsRealRatherThanProcedural:
    def test_the_whole_body_is_printed_before_the_question(
            self, offering, monkeypatch, capsys):
        monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
        configuration._offer_boost_first(["claude"])
        out = capsys.readouterr().out
        lines = _body_lines()
        assert lines, "the shipped rule must not be empty"
        for line in lines:
            assert ("  | %s" % line) in out
        # Every line, not merely the first few — a truncating mutant dies here.
        assert out.count("  | ") == len(lines)

    def test_the_default_answer_is_no(self, offering, monkeypatch, capsys):
        # No BOOST_ASSUME_YES, no --yes in argv, stdin is not a tty: confirm
        # returns its `default`. If that default flipped to True this installs.
        monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
        configuration._offer_boost_first(["claude"])
        assert lockfile.get_rule(RULE) is None
        assert "Not installed" in capsys.readouterr().out

    def test_declining_still_shows_how_to_install_later(
            self, offering, monkeypatch, capsys):
        monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
        configuration._offer_boost_first(["claude"])
        assert ("boost install %s" % RULE) in capsys.readouterr().out

    def test_accepting_installs_and_shows_the_reversal_command(
            self, offering, capsys):
        configuration._offer_boost_first(["claude"])   # ASSUME_YES still set
        out = capsys.readouterr().out
        assert lockfile.get_rule(RULE) is not None
        assert ("boost uninstall %s" % RULE) in out


class TestItNeverAsksTwice:
    def test_an_installed_rule_is_not_re_offered(self, offering, capsys):
        configuration._offer_boost_first(["claude"])
        assert lockfile.get_rule(RULE) is not None
        capsys.readouterr()
        configuration._offer_boost_first(["claude"])
        assert capsys.readouterr().out == ""


class TestTheOfferIsNonFatalByConstruction:
    """The user asked to register an MCP server. An optional extra must not
    turn that into a failure."""

    @pytest.mark.parametrize("exc", [BoostError("nope"), OSError("disk")])
    def test_an_install_failure_warns_rather_than_raises(
            self, offering, monkeypatch, capsys, exc):
        def boom(*_a, **_k):
            raise exc
        monkeypatch.setattr(store, "install", boom)
        configuration._offer_boost_first(["claude"])       # must not raise
        out = capsys.readouterr().out
        assert "could not install %s" % RULE in out
        assert "boost uninstall" not in out               # no false success

    def test_a_rule_missing_from_the_wheel_is_skipped_silently(
            self, offering, monkeypatch, capsys):
        # A wheel built without the package-data glob has no .mdc. That is a
        # packaging bug, but for the user it must read as "no offer", not as a
        # traceback out of `boost mcp register`.
        monkeypatch.setattr(builtin, "rule_is_available", lambda: False)
        configuration._offer_boost_first(["claude"])
        assert capsys.readouterr().out == ""
        assert lockfile.get_rule(RULE) is None
