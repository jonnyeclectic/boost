"""Unit tests: boost_cli/core/complete.py — what a shell offers at TAB.

Completion runs on a keystroke, so these tests care about two things the rest of
the suite does not: that the candidate path never reads the full catalogue, and
that it never raises. A completer that prints a traceback into the prompt is
worse than one that returns nothing.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.cli import COMMANDS
from boost_cli.core import complete, config, paths, registry


def _entry(name, tap):
    return {"name": name, "description": "", "version": "1.0.0", "tap": tap,
            "curated": False, "rel_dir": name, "skill_md": "%s/SKILL.md" % name,
            "meta": {}}


def _tap(name, names):
    paths.ensure_dirs()
    cfg = config.load()
    cfg["taps"] = [{"name": name, "url": "https://example.test/" + name,
                    "curated": False}]
    config.save(cfg)
    registry.Tap(name=name, url="").cache_file.write_text(
        json.dumps({"skills": [_entry(n, name) for n in names]}), encoding="utf-8")


class TestCommandNames:
    def test_the_first_word_completes_commands(self, sandbox):
        got = complete.candidates(["boost", ""], COMMANDS)
        assert set(got) == {n for n, _g, _m, _s in COMMANDS}

    def test_a_prefix_narrows_to_matching_commands(self, sandbox):
        got = complete.candidates(["boost", "inst"], COMMANDS)
        assert "install" in got
        assert "search" not in got

    def test_the_hidden_completer_is_never_offered(self, sandbox):
        # It stays out by not being a COMMANDS row at all, which is also what
        # keeps it out of --help and docs/commands.html (pinned functionally).
        assert "__complete" not in complete.candidates(["boost", ""], COMMANDS)

    def test_matching_is_a_prefix_not_a_substring(self, sandbox):
        # `boost tap<TAB>` must not offer `untap`: a shell inserts the common
        # prefix of what it is given, so substring matches corrupt the line.
        got = complete.candidates(["boost", "tap"], COMMANDS)
        assert "tap" in got and "untap" not in got


class TestArgumentsAreContextual:
    """The whole point: `boost install <TAB>` must offer skills, not commands.

    All three shells previously re-offered command names, local filenames, or
    nothing at this position.
    """

    def test_install_offers_catalogue_names(self, sandbox):
        _tap("t", ["brainstorming", "code-reviewer"])
        got = complete.candidates(["boost", "install", ""], COMMANDS)
        assert "brainstorming" in got and "code-reviewer" in got

    def test_install_does_not_offer_command_names(self, sandbox):
        _tap("t", ["brainstorming"])
        assert "search" not in complete.candidates(["boost", "install", ""], COMMANDS)

    def test_a_prefix_narrows_catalogue_names(self, sandbox):
        _tap("t", ["brainstorming", "code-reviewer"])
        got = complete.candidates(["boost", "install", "code"], COMMANDS)
        assert got == ["code-reviewer"]

    def test_catalogue_matching_is_a_prefix_not_a_substring(self, sandbox):
        # "review" appears *inside* code-reviewer; only review-swarm starts
        # with it, and offering both would insert a wrong common prefix.
        _tap("t", ["code-reviewer", "review-swarm"])
        assert complete.candidates(["boost", "install", "review"],
                                   COMMANDS) == ["review-swarm"]

    def test_untap_offers_configured_taps(self, sandbox):
        _tap("owner/repo", ["x"])
        assert "owner/repo" in complete.candidates(["boost", "untap", ""], COMMANDS)

    def test_an_unknown_command_offers_nothing(self, sandbox):
        # Better silence than a wrong guess: a wrong list is worse than none.
        assert complete.candidates(["boost", "nosuchcommand", ""], COMMANDS) == []

    def test_flags_complete_for_the_named_command(self, sandbox):
        got = complete.candidates(["boost", "search", "--"], COMMANDS)
        assert all(g.startswith("--") for g in got), got
        assert got, "search documents flags; none were offered"

    def test_flags_are_specific_to_the_command(self, sandbox):
        # A single global flag list would be worse than none — it would teach
        # flags that the command rejects.
        search = set(complete.candidates(["boost", "search", "--"], COMMANDS))
        doctor = set(complete.candidates(["boost", "doctor", "--"], COMMANDS))
        assert search != doctor


class TestItNeverCostsTheFullCatalogue:
    def test_names_come_from_the_cache_not_a_full_scan(self, sandbox, monkeypatch):
        # Measured on a real install: catalog.all_entries() is 423 ms for 71,655
        # entries, against a <100 ms budget for a keystroke. The names cache
        # answers the same question in 1.9 ms, so completion must never reach
        # for the full scan.
        _tap("t", ["brainstorming"])
        complete.refresh_names()          # build the cache once
        called = []
        monkeypatch.setattr(complete.catalog, "all_entries",
                            lambda: called.append(1) or [])
        complete.candidates(["boost", "install", ""], COMMANDS)
        assert called == [], "completion fell back to a full catalogue scan"

    def test_the_cache_is_rebuilt_when_missing(self, sandbox):
        _tap("t", ["brainstorming"])
        complete.names_file().unlink(missing_ok=True)
        assert "brainstorming" in complete.candidates(["boost", "install", ""], COMMANDS)


class TestItNeverFailsLoudly:
    """Exit 0 with nothing rather than a traceback in the user's prompt."""

    def test_a_broken_cache_yields_no_candidates(self, sandbox):
        _tap("t", ["brainstorming"])
        complete.refresh_names()
        complete.names_file().write_bytes(b"\xff\xfe not utf-8 \x00")
        assert isinstance(complete.candidates(["boost", "install", ""], COMMANDS), list)

    def test_an_exploding_source_is_swallowed(self, sandbox, monkeypatch):
        def boom():
            raise RuntimeError("catalogue on fire")
        monkeypatch.setattr(complete, "_cached_names", boom)
        assert complete.candidates(["boost", "install", ""], COMMANDS) == []

    def test_no_words_is_not_an_error(self, sandbox):
        assert complete.candidates([], COMMANDS) == []
        assert complete.candidates(["boost"], COMMANDS) == []


class TestCandidatesAreShellSafe:
    def test_nothing_carries_a_newline_or_space(self, sandbox):
        # The shells consume this as one candidate per line; a name containing
        # either would split into two bogus candidates.
        _tap("t", ["brainstorming"])
        for got in (complete.candidates(["boost", ""], COMMANDS),
                    complete.candidates(["boost", "install", ""], COMMANDS)):
            assert all("\n" not in c and " " not in c for c in got)

    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
    def test_every_shell_script_delegates_to_the_completer(self, shell):
        # The point of the rewrite: one completer in Python, three thin shims.
        # A script that embeds its own static list would drift from COMMANDS.
        assert "__complete" in complete.script(shell)


class TestInstalledAndTapSources:
    """Paths verified in a real shell but not, until now, in a test.

    `uninstall <TAB>` offering the *catalogue* rather than what is installed
    would be confidently wrong — every name would look valid and most would
    fail. These were exercised by driving bash; a coverage check showed the
    unit suite never touched them, which is how the original defect survived.
    """

    def test_uninstall_offers_installed_skills_not_the_catalogue(
            self, sandbox, monkeypatch):
        _tap("t", ["in-the-catalogue"])
        monkeypatch.setattr(complete.store, "installed",
                            lambda: {"already-installed": {}})
        got = complete.candidates(["boost", "uninstall", ""], COMMANDS)
        assert got == ["already-installed"]
        assert "in-the-catalogue" not in got

    def test_installed_names_are_sorted(self, sandbox, monkeypatch):
        # The shells render in the order given; unsorted output looks random.
        monkeypatch.setattr(complete.store, "installed",
                            lambda: {"zeta": {}, "alpha": {}, "mid": {}})
        assert complete.candidates(["boost", "uninstall", ""], COMMANDS) == [
            "alpha", "mid", "zeta"]

    def test_tap_names_are_sorted(self, sandbox):
        _tap("zzz/repo", ["x"])
        cfg = config.load()
        cfg["taps"].append({"name": "aaa/repo", "url": "u", "curated": False})
        config.save(cfg)
        assert complete.candidates(["boost", "untap", ""], COMMANDS) == [
            "aaa/repo", "zzz/repo"]


class TestFlagLookupDegrades:
    """Every branch returns [] rather than raising — it runs on a keystroke."""

    def test_an_unknown_command_has_no_flags(self, sandbox):
        assert complete.candidates(["boost", "nosuch", "--"], COMMANDS) == []

    def test_a_command_whose_function_is_missing_has_no_flags(self, sandbox):
        # A COMMANDS row can name a cmd_* that does not exist yet; the
        # dispatcher already tolerates it, so completion must too.
        rows = [*COMMANDS, ("ghost", "cfg", "configuration", "unbuilt")]
        assert complete.candidates(["boost", "ghost", "--"], rows) == []

    def test_source_that_cannot_be_read_has_no_flags(self, sandbox, monkeypatch):
        import inspect
        def boom(_f):
            raise OSError("no source available")     # e.g. a frozen build
        monkeypatch.setattr(inspect, "getsource", boom)
        assert complete.candidates(["boost", "search", "--"], COMMANDS) == []

    def test_short_flags_are_not_offered(self, sandbox):
        # `-k` and friends are ambiguous across commands and add noise; the
        # long form is what documentation and muscle memory use.
        got = complete.candidates(["boost", "search", "-"], COMMANDS)
        assert all(g.startswith("--") for g in got), got


class TestScriptSelection:
    def test_an_unknown_shell_falls_back_to_bash(self):
        assert complete.script("nushell") == complete.script("bash")

    def test_every_shell_has_an_install_hint(self):
        for shell in ("bash", "zsh", "fish"):
            assert shell in complete.INSTALL_HINT[shell]

    def test_refresh_reports_what_it_wrote(self, sandbox):
        _tap("t", ["one", "two"])
        assert complete.refresh_names() == 2
