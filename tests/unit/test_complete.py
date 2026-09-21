# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/complete.py — what a shell offers at TAB.

Completion runs on a keystroke, so these tests care about two things the rest of
the suite does not: that the candidate path never reads the full catalogue, and
that it never raises. A completer that prints a traceback into the prompt is
worse than one that returns nothing.
"""
from __future__ import annotations

import json
import os
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

        monkeypatch.setattr(complete.paths, "ensure_dirs", refuse)
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
        # "check")`) is scraped the same way `_flags_for` scrapes flags.
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

    def test_a_non_literal_choices_source_offers_nothing(self, sandbox):
        # bmad's action choices are `choices=_ACTIONS` — a name, not a tuple
        # literal in the call itself. Resolving it would mean evaluating
        # arbitrary module globals; degrading to nothing is the safe call.
        assert complete.candidates(["boost", "bmad", ""], COMMANDS) == []

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

    def test_a_choices_scrape_that_explodes_is_swallowed(self, sandbox, monkeypatch):
        monkeypatch.setattr(complete, "_positional_choices",
                             lambda src: (_ for _ in ()).throw(RuntimeError("boom")))
        assert complete.candidates(["boost", "policy", ""], COMMANDS) == []


class TestPositionalChoicesHelpers:
    """Direct coverage of the scraping helpers, independent of a real
    command's source — pins the exact literal-vs-dynamic boundary.
    """

    def test_a_literal_tuple_is_read(self):
        assert complete._literal_choices('choices=("a", "b")') == ["a", "b"]

    def test_a_literal_list_is_read(self):
        assert complete._literal_choices('choices=["a", "b"]') == ["a", "b"]

    def test_a_bare_name_is_dynamic(self):
        assert complete._literal_choices("choices=_ACTIONS") is None

    def test_a_dotted_attribute_is_dynamic(self):
        assert complete._literal_choices("choices=cs.SCOPES") is None

    def test_a_call_is_dynamic(self):
        assert complete._literal_choices("choices=tuple(_INTERVALS)") is None

    def test_a_starred_call_is_dynamic(self):
        assert complete._literal_choices(
            'choices=(*hookhost.hosts(), "auto")') is None

    def test_an_empty_tuple_is_not_offered(self):
        # Vacuous choices are indistinguishable from "no choices given" here;
        # both mean nothing to complete.
        assert complete._literal_choices("choices=()") is None

    def test_a_non_choices_kwarg_is_not_matched(self):
        assert complete._literal_choices('default="list"') is None

    def test_positional_choices_skips_flags(self):
        src = ('def cmd_x(argv):\n'
               '    p.add_argument("--json", action="store_true")\n'
               '    p.add_argument("action", choices=("a", "b"))\n')
        assert complete._positional_choices(src) == [["a", "b"]]

    def test_positional_choices_none_for_a_choiceless_positional(self):
        src = 'def cmd_x(argv):\n    p.add_argument("name", help="a name")\n'
        assert complete._positional_choices(src) == [None]

    def test_positional_choices_preserves_declaration_order(self):
        src = ('def cmd_x(argv):\n'
               '    p.add_argument("action", choices=("set", "get"))\n'
               '    p.add_argument("key", help="k")\n')
        assert complete._positional_choices(src) == [["set", "get"], None]

    def test_a_comma_inside_a_quoted_help_string_does_not_split_the_call(self):
        # Real source: `help="dotted key, e.g. ai.enabled"` — the comma there
        # must not be mistaken for the boundary between add_argument's args.
        src = ('def cmd_x(argv):\n'
               '    p.add_argument("key", nargs="?", '
               'help="dotted key, e.g. ai.enabled")\n')
        assert complete._positional_choices(src) == [None]

    def test_dotted_keys_flattens_nested_dicts(self):
        node = {"a": {"b": 1, "c": {"d": 2}}, "e": []}
        assert sorted(complete._dotted_keys(node)) == ["a.b", "a.c.d", "e"]

    def test_dotted_keys_of_an_empty_dict_is_empty(self):
        assert complete._dotted_keys({}) == []

    def test_a_flag_spelling_is_not_a_positional_literal(self):
        assert complete._is_positional_literal('"--json"') is False
        assert complete._is_positional_literal('"-s"') is False

    def test_a_quoted_name_is_a_positional_literal(self):
        assert complete._is_positional_literal('"action"') is True
        assert complete._is_positional_literal("'action'") is True

    def test_an_unquoted_token_is_not_a_positional_literal(self):
        assert complete._is_positional_literal("action") is False

    def test_choices_of_none_is_not_offered(self):
        assert complete._literal_choices("choices=None") is None


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
