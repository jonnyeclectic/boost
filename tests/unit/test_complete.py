# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/complete.py — what a shell offers at TAB.

Completion runs on a keystroke, so these tests care about two things the rest of
the suite does not: that the candidate path never reads the full catalogue, and
that it never raises. A completer that prints a traceback into the prompt is
worse than one that returns nothing.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

from boost_cli.cli import COMMANDS
from boost_cli.core import complete, config, paths, registry, util


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


class TestLeadingGlobalFlagsAndHelp:
    """`boost --debug install <TAB>` is a line `cli.main` runs — it peels the
    global flags off before dispatch — so completion must peel them too, or it
    reads `--debug` as the command and offers nothing. And `boost help <TAB>`
    is the documented way to get help, so it offers command names."""

    GLOBALS = frozenset({"--debug", "-v", "--verbose", "-q", "--quiet"})

    def test_a_leading_global_flag_still_completes_the_command(self, sandbox):
        got = complete.candidates(["boost", "--debug", "ins"], COMMANDS,
                                  global_flags=self.GLOBALS)
        assert "install" in got and "search" not in got

    def test_several_leading_globals_are_all_skipped(self, sandbox):
        _tap("t", ["brainstorming", "code-reviewer"])
        got = complete.candidates(["boost", "-q", "--debug", "install", "br"],
                                  COMMANDS, global_flags=self.GLOBALS)
        assert got == ["brainstorming"]

    def test_the_word_being_typed_is_never_peeled(self, sandbox):
        # `boost --debug<TAB>` is a partial word, not a flag already given:
        # peeling it would turn the line into `boost <TAB>` and offer every
        # command as a replacement for what the user typed.
        got = complete.candidates(["boost", "--debug"], COMMANDS,
                                  global_flags=self.GLOBALS)
        assert "install" not in got
        # No real command starts with `-`, so the line above answers [] even
        # if the last word were peeled. A flag set holding a command *prefix*
        # tells the two apart: kept, `ins` completes; peeled, nothing does.
        got = complete.candidates(["boost", "ins"], COMMANDS,
                                  global_flags=frozenset({"ins"}))
        assert got == [c for c in complete._command_names(COMMANDS)
                       if c.startswith("ins")]
        assert "install" in got

    def test_a_global_after_the_command_is_the_command_s_own(self, sandbox):
        # `cli._extract_globals` only peels flags *before* the command, so a
        # `-v` after it belongs to the subcommand and must stay where it is.
        _tap("t", ["brainstorming"])
        got = complete.candidates(["boost", "install", "-v", "br"], COMMANDS,
                                  global_flags=self.GLOBALS)
        assert got == complete.candidates(["boost", "install", "-v", "br"],
                                          COMMANDS)

    def test_without_the_flag_set_nothing_is_peeled(self, sandbox):
        assert complete.candidates(["boost", "--debug", "ins"], COMMANDS) == []

    def test_help_offers_command_names(self, sandbox):
        got = complete.candidates(["boost", "help", "ins"], COMMANDS)
        assert "install" in got and "search" not in got

    def test_help_offers_every_command_for_an_empty_word(self, sandbox):
        got = complete.candidates(["boost", "help", ""], COMMANDS)
        assert set(got) == {n for n, _g, _m, _s in COMMANDS}

    def test_help_takes_one_command_only(self, sandbox):
        assert complete.candidates(["boost", "help", "install", ""],
                                   COMMANDS) == []

    @pytest.mark.parametrize("word", ["help", "--help", "-h"])
    def test_every_spelling_of_help_offers_command_names(self, sandbox, word):
        # `boost --help install` routes like `boost help install`, so TAB
        # after either flag must offer what TAB after `help` does.
        got = complete.candidates(["boost", word, "ins"], COMMANDS)
        assert got == [c for c in complete._command_names(COMMANDS)
                       if c.startswith("ins")]
        assert "install" in got and "search" not in got
        assert complete.candidates(["boost", word, "install", ""],
                                   COMMANDS) == []

    def test_help_after_a_global_flag(self, sandbox):
        got = complete.candidates(["boost", "--debug", "help", "ins"], COMMANDS,
                                  global_flags=self.GLOBALS)
        assert "install" in got

    def test_the_plumbing_passes_the_cli_s_own_flag_set(self, sandbox, capsys):
        from boost_cli import cli
        assert cli.main(["__complete", "boost", "--debug", "ins"]) == 0
        assert "install" in capsys.readouterr().out.split()


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


class TestANamesFileBoostCannotWrite:
    """`_names.txt` is rewritten by tap, untap, update and heal. Written in
    place, a copy one `sudo boost` run left read-only made all four exit 70
    while doctor said healthy (cache-writers-that-still-crash-on-a-read-only-
    cache). The completion list is a convenience: failing to keep it must
    never fail the command that asked for it."""

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="Windows refuses to replace a read-only file")
    @pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                        reason="root ignores mode bits")
    def test_a_read_only_names_file_is_replaced_not_refused(self, sandbox,
                                                            capsys):
        _tap("t", ["one", "two"])
        complete.refresh_names()
        complete.names_file().chmod(0o444)
        _tap("t", ["one", "three", "two"])
        capsys.readouterr()
        assert complete.refresh_names() == 3
        assert complete.names_file().read_text(encoding="utf-8") \
            == "one\nthree\ntwo"
        assert os.access(complete.names_file(), os.W_OK)   # boost owns it now
        assert capsys.readouterr().err == ""

    def test_a_read_only_dir_falls_back_to_the_in_place_write(
            self, sandbox, monkeypatch, capsys):
        # A replace needs the directory writable; an in-place write does not,
        # so a writable file in a read-only dir must still be kept current.
        _tap("t", ["one", "two"])
        complete.refresh_names()
        _tap("t", ["one", "three", "two"])
        capsys.readouterr()

        def refuse(path, text, encoding="utf-8"):
            raise PermissionError(13, "Permission denied", str(path))

        monkeypatch.setattr(util, "atomic_write_text", refuse)
        assert complete.refresh_names() == 3
        assert complete.names_file().read_text(encoding="utf-8") \
            == "one\nthree\ntwo"
        assert capsys.readouterr().err == ""

    def test_a_cache_dir_it_cannot_create_is_not_a_crash(
            self, sandbox, monkeypatch, capsys):
        # A read-only ~/.boost with no cache dir refuses the mkdir itself;
        # that has to land in the same tolerance as a refused write.
        _tap("t", ["one", "two"])
        capsys.readouterr()

        def refuse():
            raise PermissionError(13, "Permission denied",
                                  str(paths.cache_dir()))

        monkeypatch.setattr(Path, "mkdir", lambda self, *a, **k: refuse())
        monkeypatch.setattr(Path, "write_text",
                            lambda self, *a, **k: refuse())
        assert complete.refresh_names() == 2
        assert "could not save the completion list" \
            in " ".join(capsys.readouterr().err.split())

    def test_a_write_that_fails_warns_once_and_carries_on(
            self, sandbox, monkeypatch, capsys):
        _tap("t", ["one", "two"])
        capsys.readouterr()

        def refuse(path, text, encoding="utf-8"):
            raise PermissionError(13, "Permission denied", str(path))

        monkeypatch.setattr(util, "atomic_write_text", refuse)
        monkeypatch.setattr(Path, "write_text",
                            lambda self, *a, **k: refuse(self, ""))
        assert complete.refresh_names() == 2
        assert complete.refresh_names() == 2       # a second call, same run
        cap = capsys.readouterr()
        assert cap.out == ""                       # stdout may be --json
        err = " ".join(cap.err.split())
        assert "! could not save the completion list (Permission denied)" \
            in err
        assert "tab completion may offer stale names; make %s writable" \
            % paths.tilde(complete.names_file().parent) in err
        assert err.count("could not save") == 1    # once, not per call
        # With no file to read, TAB offers nothing rather than a traceback.
        assert complete.candidates(["boost", "install", ""], COMMANDS) == []

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="chmod can't remove the owner's own read access "
                               "on Windows")
    @pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                        reason="root ignores mode bits")
    def test_an_unreadable_names_file_is_rebuilt_not_read_as_empty(
            self, sandbox):
        # What a root-owned 0600 copy looks like to the user: TAB offered
        # nothing, silently, because only a missing file was rebuilt.
        _tap("t", ["one", "two"])
        complete.refresh_names()
        complete.names_file().chmod(0o000)
        try:
            got = complete.candidates(["boost", "install", ""], COMMANDS)
        finally:
            if not os.access(complete.names_file(), os.R_OK):
                complete.names_file().chmod(0o600)
        assert got == ["one", "two"]
        assert os.access(complete.names_file(), os.R_OK)   # replaced

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="chmod can't make a directory unwritable on Windows")
    @pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                        reason="root ignores mode bits")
    def test_an_unreadable_file_it_cannot_replace_offers_nothing(
            self, sandbox, capsys):
        _tap("t", ["one", "two"])
        complete.refresh_names()
        complete.names_file().chmod(0o000)
        paths.cache_dir().chmod(0o500)
        try:
            got = complete._cached_names()
        finally:
            paths.cache_dir().chmod(0o700)
            complete.names_file().chmod(0o600)
        assert got == []
        assert "could not save the completion list" \
            in " ".join(capsys.readouterr().err.split())


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

    def test_installed_rules_and_workflows_complete_too(self, sandbox):
        # pin / uninstall / verify govern rules and workflows now, so TAB must
        # offer their names — store.installed() alone is the skills section.
        from boost_cli.core import lockfile
        lockfile.set_skill("a-skill", {})
        lockfile.set_rule("z-rule", {"kind": "rule"})
        lockfile.set_workflow("m-flow", {"kind": "workflow"})
        assert complete.candidates(["boost", "pin", ""], COMMANDS) == [
            "a-skill", "m-flow", "z-rule"]
        assert complete.candidates(["boost", "uninstall", "z"], COMMANDS) == [
            "z-rule"]

    def test_tap_names_are_sorted(self, sandbox):
        _tap("zzz/repo", ["x"])
        cfg = config.load()
        cfg["taps"].append({"name": "aaa/repo", "url": "u", "curated": False})
        config.save(cfg)
        assert complete.candidates(["boost", "untap", ""], COMMANDS) == [
            "aaa/repo", "zzz/repo"]


class TestPositionalChoices:
    """Positional `choices=(...)` tuples now complete too — the hole the
    2026-08 CLI audit found: `boost policy set <TAB>` offered nothing even
    though only `policy.DEFAULTS` keys are valid there. See
    docs/roadmap/items/audit-completions-findings.md, cluster
    completions-choices.
    """

    def test_first_word_of_a_subcommand_offers_its_literal_actions(self, sandbox):
        # `policy`'s own action positional (`choices=("list", "set", "unset",
        # "check")`), read off the parser the same way `_flags_for` is.
        got = complete.candidates(["boost", "policy", ""], COMMANDS)
        assert set(got) == {"list", "set", "unset", "check"}

    def test_a_prefix_narrows_the_action_words(self, sandbox):
        got = complete.candidates(["boost", "policy", "s"], COMMANDS)
        assert set(got) == {"set"}

    def test_config_offers_its_own_actions(self, sandbox):
        got = complete.candidates(["boost", "config", ""], COMMANDS)
        assert set(got) == {"list", "get", "set", "unset"}

    def test_policy_set_offers_policy_default_keys(self, sandbox):
        from boost_cli.core import policy
        got = complete.candidates(["boost", "policy", "set", ""], COMMANDS)
        assert set(got) == set(policy.DEFAULTS)

    def test_policy_unset_offers_the_same_keys_as_set(self, sandbox):
        from boost_cli.core import policy
        got = complete.candidates(["boost", "policy", "unset", ""], COMMANDS)
        assert set(got) == set(policy.DEFAULTS)

    def test_policy_list_does_not_offer_keys(self, sandbox):
        # Only `set`/`unset` take a KEY; `list` and `check` take nothing more.
        assert complete.candidates(["boost", "policy", "list", ""], COMMANDS) == []

    def test_policy_set_key_prefix_narrows(self, sandbox):
        got = complete.candidates(["boost", "policy", "set", "pin"], COMMANDS)
        assert got == ["pin_only"]

    def test_policy_set_value_position_offers_nothing(self, sandbox):
        # The VALUE (position 2) is never a static choice — no guessing.
        got = complete.candidates(
            ["boost", "policy", "set", "pin_only", ""], COMMANDS)
        assert got == []

    def test_config_set_offers_dotted_default_keys(self, sandbox):
        got = complete.candidates(["boost", "config", "set", ""], COMMANDS)
        assert "policy_enforce" in got
        assert "ai.enabled" in got
        # Only leaf keys — a section by itself is not a settable key.
        assert "agents" not in got
        assert "ai" not in got

    def test_config_get_and_unset_offer_the_same_keys_as_set(self, sandbox):
        set_keys = set(complete.candidates(["boost", "config", "set", ""], COMMANDS))
        get_keys = set(complete.candidates(["boost", "config", "get", ""], COMMANDS))
        unset_keys = set(complete.candidates(["boost", "config", "unset", ""], COMMANDS))
        assert set_keys == get_keys == unset_keys
        assert set_keys       # not vacuously equal

    def test_config_list_does_not_offer_keys(self, sandbox):
        assert complete.candidates(["boost", "config", "list", ""], COMMANDS) == []

    def test_hooks_offers_its_actions_but_not_the_free_text_event(self, sandbox):
        assert set(complete.candidates(["boost", "hooks", ""], COMMANDS)) == \
            {"add", "remove", "list"}
        # `event` (position 1) has no `choices=` at all — degrades to nothing
        # rather than guessing at event names.
        assert complete.candidates(["boost", "hooks", "add", ""], COMMANDS) == []

    def test_a_choices_tuple_held_in_a_name_is_offered_too(self, sandbox):
        # bmad's action choices are `choices=_ACTIONS` — a name, which the old
        # source scraper could not resolve and so offered nothing for. Read
        # off the built parser, it is the exact tuple argparse validates.
        from boost_cli.commands import bmad
        assert complete.candidates(["boost", "bmad", ""], COMMANDS) == \
            list(bmad._ACTIONS)

    def test_an_unknown_command_offers_no_positional_choices(self, sandbox):
        assert complete.candidates(["boost", "nosuchcommand", ""], COMMANDS) == []

    def test_install_still_offers_the_catalogue_at_any_position(self, sandbox):
        # The whole-command dynamic sources (catalog/installed/tap) stay
        # position-independent: `install` takes a variadic list of names.
        _tap("t", ["brainstorming", "code-reviewer"])
        first = complete.candidates(["boost", "install", ""], COMMANDS)
        second = complete.candidates(
            ["boost", "install", "brainstorming", ""], COMMANDS)
        assert first == second == ["brainstorming", "code-reviewer"]

    def test_a_choices_lookup_that_explodes_is_swallowed(self, sandbox, monkeypatch):
        monkeypatch.setattr(complete, "_positional_at",
                             lambda p, i: (_ for _ in ()).throw(RuntimeError("boom")))
        assert complete.candidates(["boost", "policy", ""], COMMANDS) == []


class TestPositionalChoicesHelpers:
    """Direct coverage of the defaults-dict key walker."""

    def test_dotted_keys_flattens_nested_dicts(self):
        node = {"a": {"b": 1, "c": {"d": 2}}, "e": []}
        assert sorted(complete._dotted_keys(node)) == ["a.b", "a.c.d", "e"]

    def test_dotted_keys_of_an_empty_dict_is_empty(self):
        assert complete._dotted_keys({}) == []


class TestFlagLookupDegrades:
    """Every branch returns [] rather than raising — it runs on a keystroke."""

    def test_an_unknown_command_has_no_flags(self, sandbox):
        assert complete.candidates(["boost", "nosuch", "--"], COMMANDS) == []

    def test_a_command_whose_function_is_missing_has_no_flags(self, sandbox):
        # A COMMANDS row can name a cmd_* that does not exist yet; the
        # dispatcher already tolerates it, so completion must too.
        rows = [*COMMANDS, ("ghost", "cfg", "configuration", "unbuilt")]
        assert complete.candidates(["boost", "ghost", "--"], rows) == []

    def test_a_parser_that_cannot_be_built_has_no_flags(self, sandbox,
                                                        monkeypatch):
        from boost_cli.commands import discovery
        def boom(_argv):
            raise RuntimeError("fails before it parses")
        monkeypatch.setattr(discovery, "cmd_search", boom)
        assert complete.candidates(["boost", "search", "--"], COMMANDS) == []

    def test_without_a_parser_flags_still_are_not_positionals(
            self, sandbox, monkeypatch):
        from boost_cli.core import policy
        monkeypatch.setattr(complete, "_parser_for", lambda c, r: None)
        assert complete.candidates(["boost", "policy", "--json", "set", ""],
                                   COMMANDS) == sorted(policy.DEFAULTS)

    def test_a_command_that_never_parses_has_no_flags(self, sandbox,
                                                      monkeypatch):
        from boost_cli.commands import discovery
        monkeypatch.setattr(discovery, "cmd_search", lambda argv: 0)
        assert complete.candidates(["boost", "search", "--"], COMMANDS) == []

    def test_a_command_that_exits_before_parsing_has_no_flags(
            self, sandbox, monkeypatch):
        from boost_cli.commands import discovery
        def leave(_argv):
            raise SystemExit(2)
        monkeypatch.setattr(discovery, "cmd_search", leave)
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

    def test_zsh_manual_script_still_self_invokes(self):
        # The fpath/autoload install path (`boost completions zsh > ~/.zfunc/_boost`)
        # relies on this exact trailer: zsh's autoload machinery calls `_boost`
        # for the very first real TAB press, and that call IS the one this line
        # answers. Swapping it for `compdef` here (the eval-script's trailer)
        # would silently break that first completion — see eval_script's tests.
        assert complete.script("zsh").rstrip().endswith('_boost "$@"')


class TestEvalScript:
    """`boost completions --install` eval's this into a running shell rather
    than dropping a static file, so it must be safe to run inline rather than
    autoloaded — see eval_script's docstring for why zsh needs a different
    trailer than the manually-installed script does.
    """

    def test_bash_eval_is_identical_to_the_plain_script(self):
        # complete -F registration behaves the same sourced or eval'd, so
        # bash needs no special variant.
        assert complete.eval_script("bash") == complete.script("bash")

    def test_fish_eval_falls_back_to_the_plain_script(self):
        assert complete.eval_script("fish") == complete.script("fish")

    def test_zsh_eval_registers_via_compdef_not_self_invocation(self):
        got = complete.eval_script("zsh")
        assert got.rstrip().endswith("compdef _boost boost")
        assert '_boost "$@"' not in got

    def test_zsh_eval_still_delegates_to_the_completer(self):
        # Same candidate logic either way — only the trailer differs.
        assert "boost __complete" in complete.eval_script("zsh")


class TestInstallUninstall:
    """`boost completions --install` — the one-shot path that replaces the
    copy-paste-into-your-rc-file dance with an idempotent, reversible edit.
    """

    def test_unsupported_shell_raises_with_a_hint(self, sandbox):
        from boost_cli.errors import BoostError
        with pytest.raises(BoostError) as exc:
            complete.install("fish")
        assert "fish" in exc.value.message
        assert "boost completions fish" in exc.value.hint

    def test_install_creates_the_rc_file_when_absent(self, sandbox):
        rc = complete.install("bash")
        assert rc == sandbox / ".bashrc"
        text = rc.read_text(encoding="utf-8")
        assert "# >>> boost completions >>>" in text
        assert 'eval "$(boost completions bash --eval)"' in text

    def test_install_preserves_existing_content(self, sandbox):
        rc = sandbox / ".zshrc"
        rc.write_text("my existing config\n", encoding="utf-8")
        complete.install("zsh")
        text = rc.read_text(encoding="utf-8")
        assert text.startswith("my existing config\n")
        assert 'eval "$(boost completions zsh --eval)"' in text

    def test_install_twice_is_idempotent(self, sandbox):
        rc = sandbox / ".bashrc"
        rc.write_text("pre-existing\n", encoding="utf-8")
        complete.install("bash")
        once = rc.read_text(encoding="utf-8")
        complete.install("bash")
        twice = rc.read_text(encoding="utf-8")
        assert once == twice
        assert once.count("# >>> boost completions >>>") == 1

    def test_install_then_uninstall_restores_original_content(self, sandbox):
        rc = sandbox / ".bashrc"
        original = "line one\nline two\n"
        rc.write_text(original, encoding="utf-8")
        complete.install("bash")
        assert original.strip() in rc.read_text(encoding="utf-8")
        complete.uninstall("bash")
        assert rc.read_text(encoding="utf-8") == original

    def test_uninstall_without_a_prior_install_is_a_harmless_no_op(self, sandbox):
        assert not (sandbox / ".bashrc").exists()
        complete.uninstall("bash")
        assert not (sandbox / ".bashrc").exists()

    def test_uninstall_leaves_unrelated_rc_content_untouched(self, sandbox):
        rc = sandbox / ".zshrc"
        rc.write_text("unrelated line\n", encoding="utf-8")
        complete.uninstall("zsh")           # never installed here
        assert rc.read_text(encoding="utf-8") == "unrelated line\n"

    def test_uninstall_leaves_a_malformed_block_untouched(self, sandbox):
        # A start marker with no matching end marker means someone hand-edited
        # the file after boost wrote it — guessing at intent here would risk
        # eating content that was never boost's to remove.
        #
        # The file is still untouched; what changed is that boost now *says so*
        # instead of exiting 0 as though it had done the job. Silently doing
        # nothing was only safe while the orphan start was the sole marker: with
        # a well-formed block below it, the old scan paired the orphan with that
        # block's end and deleted everything between. See
        # tests/unit/test_complete_rc_block.py for both preconditions.
        from boost_cli.errors import BoostError
        rc = sandbox / ".bashrc"
        broken = "before\n# >>> boost completions >>>\nno end marker here\n"
        rc.write_text(broken, encoding="utf-8")
        with pytest.raises(BoostError):
            complete.uninstall("bash")
        assert rc.read_text(encoding="utf-8") == broken


class TestDetectShell:
    def test_reads_the_basename_of_shell_env(self, monkeypatch):
        monkeypatch.setenv("SHELL", "/usr/local/bin/zsh")
        assert complete.detect_shell() == "zsh"

    def test_empty_when_shell_env_is_unset(self, monkeypatch):
        monkeypatch.delenv("SHELL", raising=False)
        assert complete.detect_shell() == ""


def _help_long_flags(command, capsys):
    """The long options `boost <command> --help` lists, read off its text."""
    row = next(r for r in COMMANDS if r[0] == command)
    module = importlib.import_module("boost_cli.commands." + row[2])
    func = getattr(module, "cmd_" + command.replace("-", "_"))
    capsys.readouterr()
    with pytest.raises(SystemExit):
        func(["--help"])
    text = capsys.readouterr().out
    flags = set()
    for m in re.finditer(r"(?m)^ {2,}(-\S.*?)(?: {2,}|$)", text):
        flags.update(re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*)", m.group(1)))
    return sorted(flags)


_COMMAND_NAMES = [r[0] for r in COMMANDS]


class TestFlagsComeFromTheParser:
    """`--<TAB>` offers what the parser accepts. A regex over each `cmd_*`
    function's source missed every flag a shared helper adds (`install --s`
    offered nothing although `--scope` is valid) and offered `--x` strings
    from git argv lists that the parser rejects (`onboard --fill`)."""

    @pytest.mark.parametrize("command", _COMMAND_NAMES)
    def test_flags_match_the_commands_own_help(self, command, sandbox, capsys,
                                               monkeypatch):
        monkeypatch.setenv("COLUMNS", "400")    # one option per line
        got = complete._flags_for(command, COMMANDS)
        assert got == _help_long_flags(command, capsys)
        assert "--help" in got                  # never vacuously equal

    @pytest.mark.parametrize("command", _COMMAND_NAMES)
    def test_building_the_parser_writes_nothing(self, command, sandbox):
        # Running a cmd_* up to its parse is only safe while each one parses
        # before it touches anything; this is that promise, per command.
        assert complete._parser_for(command, COMMANDS) is not None
        assert list(sandbox.iterdir()) == []

    def test_a_suppressed_alias_is_accepted_but_not_offered(self, sandbox):
        # untap's `-y/--yes` is help=SUPPRESS: valid, deliberately unlisted.
        assert complete.candidates(["boost", "untap", "--y"], COMMANDS) == []
        assert complete.candidates(["boost", "untap", "--f"], COMMANDS) == \
            ["--force"]

    def test_the_parse_methods_are_restored(self, sandbox):
        import argparse
        before = argparse.ArgumentParser.parse_args
        complete._parser_for("search", COMMANDS)
        assert argparse.ArgumentParser.parse_args is before
        assert argparse.ArgumentParser.parse_known_args is not complete._capture

    def test_a_shared_helper_s_flags_are_offered(self, sandbox):
        assert complete.candidates(["boost", "install", "--s"], COMMANDS) == \
            ["--scope"]
        got = complete.candidates(["boost", "uninstall", "--"], COMMANDS)
        assert {"--scope", "--local", "--global"} <= set(got)

    def test_a_literal_the_parser_rejects_is_not_offered(self, sandbox):
        got = complete.candidates(["boost", "onboard", "--"], COMMANDS)
        assert "--fill" not in got and "--porcelain" not in got
        assert got == complete._flags_for("onboard", COMMANDS)

    def test_a_subcommand_offers_its_own_flags(self, sandbox):
        assert complete.candidates(["boost", "context", "status", "--"],
                                   COMMANDS) == ["--help", "--json"]
        assert complete.candidates(["boost", "context", "enable", "--"],
                                   COMMANDS) == ["--help"]

    def test_the_command_s_own_flags_before_its_subcommand(self, sandbox):
        assert complete.candidates(["boost", "context", "--"], COMMANDS) == \
            ["--help", "--json"]

    def test_nothing_the_command_prints_reaches_the_prompt(self, sandbox,
                                                           capsys,
                                                           monkeypatch):
        from boost_cli.commands import discovery
        def noisy(argv):
            print("chatter")
            sys.stderr.write("more chatter\n")
            return 0
        monkeypatch.setattr(discovery, "cmd_search", noisy)
        capsys.readouterr()
        assert complete._parser_for("search", COMMANDS) is None
        assert capsys.readouterr() == ("", "")


class TestFlagsAreNotPositionals:
    """A flag already typed, and the value it takes, are not positional
    words: counting them put every later position off by one per flag."""

    def test_a_switch_before_the_word_is_skipped(self, sandbox):
        assert complete.candidates(["boost", "completions", "--eval", ""],
                                   COMMANDS) == ["bash", "zsh", "fish"]

    def test_a_switch_before_the_action_is_skipped(self, sandbox):
        from boost_cli.core import policy
        assert complete.candidates(["boost", "policy", "--json", "set", ""],
                                   COMMANDS) == sorted(policy.DEFAULTS)

    def test_config_keys_after_a_leading_switch(self, sandbox):
        assert complete.candidates(["boost", "config", "--json", "get", "ai.m"],
                                   COMMANDS) == ["ai.model"]

    def test_a_choices_flag_offers_its_choices(self, sandbox):
        _tap("t", ["brainstorming"])
        assert complete.candidates(["boost", "install", "--scope", ""],
                                   COMMANDS) == ["user", "project"]
        assert complete.candidates(["boost", "install", "--scope", "p"],
                                   COMMANDS) == ["project"]

    def test_the_flag_s_value_is_consumed(self, sandbox):
        _tap("t", ["brainstorming"])
        assert complete.candidates(
            ["boost", "install", "--scope", "user", "br"], COMMANDS) == \
            ["brainstorming"]

    def test_a_free_text_value_offers_nothing(self, sandbox):
        # `search --kind` and the like take free text where they have no
        # choices; offering the command's positional source there is a guess.
        _tap("t", ["brainstorming"])
        assert complete.candidates(["boost", "export", "--out", ""],
                                   COMMANDS) == []

    def test_an_inline_value_consumes_nothing_more(self, sandbox):
        assert complete.candidates(
            ["boost", "completions", "--shell=x", ""], COMMANDS) == \
            ["bash", "zsh", "fish"]

    def test_after_a_double_dash_everything_is_positional(self, sandbox):
        # `--` ends options, so the word after it is position 0 again.
        assert complete.candidates(["boost", "policy", "--", ""],
                                   COMMANDS) == ["list", "set", "unset",
                                                 "check"]

    def test_a_flag_after_a_double_dash_is_a_positional(self, sandbox):
        assert complete.candidates(["boost", "policy", "--", "--json", ""],
                                   COMMANDS) == []

    def test_an_unknown_flag_takes_no_value(self, sandbox):
        assert complete.candidates(["boost", "completions", "--nope", ""],
                                   COMMANDS) == ["bash", "zsh", "fish"]

    def test_a_flag_word_while_a_value_is_owed_offers_flags(self, sandbox):
        assert complete.candidates(["boost", "install", "--scope", "--s"],
                                   COMMANDS) == ["--scope"]

    def test_values_taken(self):
        import argparse
        ap = argparse.ArgumentParser()
        sw = ap.add_argument("--sw", action="store_true")
        one = ap.add_argument("--one")
        opt = ap.add_argument("--opt", nargs="?")
        two = ap.add_argument("--two", nargs=2)
        many = ap.add_argument("--many", nargs="*")
        some = ap.add_argument("--some", nargs="+")
        exact = ap.add_argument("--exact", nargs=1)
        rest = ap.add_argument("--rest", nargs=argparse.REMAINDER)
        assert [complete._values_taken(a) for a in (
            sw, one, opt, two, many, some, exact, rest)] == [
            0, 1, 1, 2, -1, -1, 1, -1]

    def test_a_subcommand_word_in_an_earlier_positional_slot_is_a_value(self):
        # argparse fills `name` first, so `map` there is a name, not the
        # subcommand — only the word at the subparsers' own slot switches.
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("name")
        sub = ap.add_subparsers(dest="action")
        sp = sub.add_parser("map")
        walk = complete._walk(ap, ["map"])
        assert walk.parser is ap and walk.positionals == ["map"]
        walk = complete._walk(ap, ["map", "map"])
        assert walk.parser is sp and walk.positionals == []

    def test_a_fixed_arity_flag_consumes_exactly_its_values(self):
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("--two", nargs=2)
        ap.add_argument("--many", nargs="*")
        ap.add_argument("word", nargs="*")
        walk = complete._walk(ap, ["--two", "a", "b", "c"])
        assert walk.positionals == ["c"] and walk.pending is None
        walk = complete._walk(ap, ["--two", "a"])
        assert walk.positionals == [] and walk.pending is not None
        walk = complete._walk(ap, ["--many", "a", "b"])
        assert walk.positionals == [] and walk.pending is not None
        walk = complete._walk(ap, ["-"])
        assert walk.positionals == ["-"]

    def test_a_variadic_positional_absorbs_later_positions(self):
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("first", choices=("a", "b"))
        ap.add_argument("rest", nargs="*", choices=("x", "y"))
        ap.add_argument("never", choices=("z",))
        assert complete._choices(complete._positional_at(ap, 0)) == ["a", "b"]
        assert complete._choices(complete._positional_at(ap, 1)) == ["x", "y"]
        assert complete._choices(complete._positional_at(ap, 4)) == ["x", "y"]
        ap2 = argparse.ArgumentParser()
        ap2.add_argument("only")
        assert complete._positional_at(ap2, 1) is None
        assert complete._choices(complete._positional_at(ap2, 0)) is None

    def test_a_subcommand_word_only_counts_in_its_own_slot(self):
        import argparse
        ap = argparse.ArgumentParser()
        sub = ap.add_subparsers(dest="action")
        sp = sub.add_parser("map")
        sp.add_argument("pattern", choices=("p", "q"))
        walk = complete._walk(ap, ["map"])
        assert walk.parser is sp and walk.positionals == []
        walk = complete._walk(ap, ["map", "map"])
        assert walk.parser is sp and walk.positionals == ["map"]

    def test_non_string_choices_are_offered_as_text(self):
        import argparse
        ap = argparse.ArgumentParser()
        action = ap.add_argument("--n", type=int, choices=(1, 2))
        assert complete._choices(action) == ["1", "2"]


class TestGlobalOptions:
    """`boost --<TAB>` offers what cli.main accepts before a command."""

    def test_double_dash_offers_every_long_global(self, sandbox, capsys):
        from boost_cli import cli
        assert cli.main(["__complete", "boost", "--"]) == 0
        assert capsys.readouterr().out.split() == [
            "--debug", "--help", "--quiet", "--verbose", "--version"]

    def test_a_prefix_narrows_the_globals(self, sandbox):
        from boost_cli import cli
        assert complete.candidates(["boost", "--deb"], COMMANDS,
                                   frozenset(cli._GLOBAL_FLAGS)) == ["--debug"]

    def test_a_single_dash_offers_short_spellings_too(self, sandbox):
        from boost_cli import cli
        assert complete.candidates(["boost", "-"], COMMANDS,
                                   frozenset(cli._GLOBAL_FLAGS)) == [
            "--debug", "--help", "--quiet", "--verbose", "--version",
            "-V", "-h", "-q", "-v"]

    def test_after_a_global_the_next_dash_word_offers_globals(self, sandbox):
        from boost_cli import cli
        assert complete.candidates(["boost", "--debug", "--q"], COMMANDS,
                                   frozenset(cli._GLOBAL_FLAGS)) == ["--quiet"]


class TestATabWritesNothing:
    """One TAB in a HOME where boost never ran created the whole ~/.boost
    tree and ~/.agents/skills (the store Gemini CLI auto-discovers)."""

    @pytest.mark.parametrize("line", [
        ["boost", "install", ""], ["boost", "uninstall", ""],
        ["boost", "untap", ""], ["boost", "config", "get", ""],
        ["boost", "doctor", "--"], ["boost", ""], ["boost", "--debug", "in"],
    ])
    def test_the_home_stays_empty(self, sandbox, capsys, line):
        from boost_cli import cli
        assert cli.main(["__complete", *line]) == 0
        assert list(sandbox.iterdir()) == []

    def test_no_cache_dir_offers_nothing_and_builds_nothing(self, sandbox,
                                                            monkeypatch):
        called = []
        monkeypatch.setattr(complete, "refresh_names",
                            lambda: called.append(1) or 0)
        assert complete._cached_names() == []
        assert called == []

    def test_refresh_creates_only_the_cache_dir(self, sandbox):
        assert complete.refresh_names() == 0
        assert complete.names_file().read_text(encoding="utf-8") == ""
        assert sorted(p.relative_to(sandbox).as_posix()
                      for p in sandbox.rglob("*")) == [
            ".boost", ".boost/cache", ".boost/cache/_names.txt"]


_BASH_BIN = "/bin/bash"


@pytest.mark.skipif(sys.platform == "win32" or not os.path.exists(_BASH_BIN),
                    reason="needs a POSIX /bin/bash")
class TestTheBashShim:
    """macOS's /bin/bash is 3.2, where a quoted array slice expanded under
    IFS=$'\\n' joins into ONE word: `boost __complete 'boost install br'`
    got a single argument and every TAB completed nothing."""

    def _run(self, tmp_path, words, cword):
        import subprocess
        bindir = tmp_path / "bin"
        bindir.mkdir()
        fake = bindir / "boost"
        # Echoes each argument it receives, one per line, so COMPREPLY shows
        # exactly how the shim split the line.
        fake.write_text('#!/bin/sh\nfor a in "$@"; do printf "<%s>\\n" "$a"; '
                        'done\n', encoding="utf-8")
        fake.chmod(0o755)
        script = tmp_path / "c.bash"
        script.write_text(complete.script("bash"), encoding="utf-8")
        cmd = ('source "$1"; COMP_WORDS=(%s); COMP_CWORD=%d; _boost_complete; '
               'printf "%%s\\n" "${COMPREPLY[@]}"'
               % (" ".join("'%s'" % w for w in words), cword))
        env = {"PATH": "%s:/usr/bin:/bin" % bindir, "HOME": str(tmp_path)}
        res = subprocess.run([_BASH_BIN, "--norc", "--noprofile", "-c", cmd,
                              "x", str(script)], capture_output=True,
                             text=True, env=env, check=False)
        assert res.stderr == ""
        return res.stdout.splitlines()

    def test_each_word_is_its_own_argument(self, tmp_path):
        assert self._run(tmp_path, ["boost", "install", "br"], 2) == [
            "<__complete>", "<boost>", "<install>", "<br>"]

    def test_an_empty_current_word_survives(self, tmp_path):
        assert self._run(tmp_path, ["boost", "install", ""], 2) == [
            "<__complete>", "<boost>", "<install>", "<>"]

    def test_only_words_up_to_the_cursor_are_sent(self, tmp_path):
        assert self._run(tmp_path, ["boost", "ins", "later"], 1) == [
            "<__complete>", "<boost>", "<ins>"]

    def test_a_word_with_a_space_stays_one_argument(self, tmp_path):
        assert self._run(tmp_path, ["boost", "search", "two words"], 2) == [
            "<__complete>", "<boost>", "<search>", "<two words>"]


@pytest.mark.skipif(sys.platform == "win32" or shutil.which("zsh") is None,
                    reason="needs zsh")
class TestTheZshEvalBlock:
    """Stock macOS zsh never runs compinit, and the eval block called
    `compdef` regardless: `command not found: compdef` at every shell start,
    and TAB stayed dead."""

    def test_eval_without_compinit_is_silent_and_registers(self, tmp_path):
        import subprocess
        env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
               "ZDOTDIR": str(tmp_path)}
        cmd = 'eval "$1"; print -r -- "${_comps[boost]}"'
        res = subprocess.run([shutil.which("zsh"), "-f", "-c", cmd, "x",
                              complete.eval_script("zsh")],
                             capture_output=True, text=True, env=env,
                             check=False)
        assert res.stderr == ""
        assert res.stdout == "_boost\n"
        assert res.returncode == 0

    def test_an_existing_compinit_is_not_rerun(self):
        got = complete.eval_script("zsh")
        assert "(( $+functions[compdef] )) || { autoload -Uz compinit && " \
               "compinit -i; }\ncompdef _boost boost\n" in got
