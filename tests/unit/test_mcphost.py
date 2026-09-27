# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: core.mcphost — per-host MCP registration argv (mutation-gated).

mcphost.py is a pure table: it never runs a command, it only decides what argv
*would* register boost with a given agent CLI. That makes every branch testable,
which matters more here than usual — an argv that is merely plausible fails at
the worst possible moment, silently, on a user's machine, and the failure looks
like "boost's MCP server is broken" rather than "the flag order is wrong".

So these assertions pin the two grammars token-for-token, and specifically pin
the three places they diverge: where the server name sits relative to the
``-e`` flags, whether a ``--`` separator appears, and whether the unregister
side needs an explicit scope. A change that "looks equivalent" to one of them
is a regression.

Which CLI versions those argvs were last checked against, and how to repeat the
check, live in :mod:`boost_cli.core.mcphost`'s own docstring — one home for the
fact, so it cannot go stale in one file while staying current in the other. It
did exactly that once: this file and the module both cited a version, and the
``--`` rationale they shared was wrong at that version.
"""
from __future__ import annotations

import os
import os.path

import pytest

from boost_cli.core import mcphost

SHIM = "/usr/local/bin/boost"


class TestHostTable:
    def test_known_hosts_in_order(self):
        # Appended, never reordered: the order is what hosts are tried and
        # reported in, and an existing user's output should not shuffle.
        assert mcphost.hosts() == ["claude", "gemini", "agy"]

    def test_hosts_returns_a_copy_callers_cannot_corrupt(self):
        mcphost.hosts().append("bogus")
        assert mcphost.hosts() == ["claude", "gemini", "agy"]

    def test_cli_names(self):
        assert mcphost.cli(mcphost.CLAUDE) == "claude"
        assert mcphost.cli(mcphost.GEMINI) == "gemini"
        assert mcphost.cli(mcphost.AGY) == "agy"

    def test_labels(self):
        assert mcphost.label(mcphost.CLAUDE) == "Claude Code"
        assert mcphost.label(mcphost.GEMINI) == "Gemini CLI"
        assert mcphost.label(mcphost.AGY) == "Antigravity CLI"

    def test_only_agy_is_scopeless(self):
        # Claude and Gemini keep local/user/project settings; agy keeps one
        # global file, so reporting "(scope: user)" for it would describe a
        # distinction its CLI does not have.
        assert mcphost.has_scope(mcphost.CLAUDE)
        assert mcphost.has_scope(mcphost.GEMINI)
        assert not mcphost.has_scope(mcphost.AGY)

    def test_unknown_host_raises(self):
        with pytest.raises(KeyError):
            mcphost.cli("copilot")

    def test_server_name_has_no_underscore(self):
        # Gemini assigns MCP tools the FQN `mcp_{server}_{tool}` and its policy
        # parser splits on the first underscore after `mcp_`. An underscore in
        # the server name makes wildcard policy rules silently mis-target.
        assert "_" not in mcphost.SERVER_NAME


class TestRegisterArgvClaude:
    def test_exact_argv(self):
        assert mcphost.register_argv(mcphost.CLAUDE, SHIM) == [
            "claude", "mcp", "add", "boost", "--scope", "user",
            "-e", "OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES",
            "-e", "no_proxy=*",
            "--", SHIM, "mcp", "--stdio",
        ]

    def test_name_precedes_every_env_flag(self):
        # `claude`'s -e is variadic: a name placed after it is swallowed as
        # another env var ("Invalid environment variable format: boost").
        argv = mcphost.register_argv(mcphost.CLAUDE, SHIM)
        assert argv.index("boost") < argv.index("-e")

    def test_separator_precedes_the_command(self):
        argv = mcphost.register_argv(mcphost.CLAUDE, SHIM)
        assert argv[argv.index("--") + 1] == SHIM


class TestRegisterArgvGemini:
    def test_exact_argv(self):
        assert mcphost.register_argv(mcphost.GEMINI, SHIM) == [
            "gemini", "mcp", "add", "--scope", "user",
            "-e", "OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES",
            "-e", "no_proxy=*",
            "boost", SHIM, "mcp", "--stdio",
        ]

    def test_no_separator(self):
        # `gemini mcp add` sets yargs `unknown-options-as-args`, so `--stdio`
        # reaches [args...] on its own and a separator buys nothing. (Gemini
        # does handle a `--` correctly — `populate--` strips it and appends the
        # rest — so this pins the argv boost sends, not a hazard it dodges.)
        assert "--" not in mcphost.register_argv(mcphost.GEMINI, SHIM)

    def test_name_follows_the_flags_and_precedes_the_command(self):
        argv = mcphost.register_argv(mcphost.GEMINI, SHIM)
        assert argv.index("-e") < argv.index("boost") < argv.index(SHIM)

    def test_stdio_trails_the_launcher_as_a_server_arg(self):
        argv = mcphost.register_argv(mcphost.GEMINI, SHIM)
        assert argv[-3:] == [SHIM, "mcp", "--stdio"]


class TestRegisterArgvAgy:
    """`agy mcp add [flags] <name> <commandOrUrl> [args...]`.

    Both of agy's own rules bite here, and each one fails quietly if broken:
    a flag placed after the name is rejected outright, and without `--` before
    the command, `--stdio` is eaten as an agy flag — boost would be registered
    with a command it never receives its own argument for.

    There is also no scope: agy keeps one global file at
    `~/.gemini/config/mcp_config.json` (inherited from Gemini CLI — there is no
    `~/.antigravity`), so passing `--scope` would be an error rather than a
    harmless extra.
    """

    def test_flags_come_before_the_name(self):
        argv = mcphost.register_argv(mcphost.AGY, SHIM)
        assert argv[:3] == ["agy", "mcp", "add"]
        name_at = argv.index(mcphost.SERVER_NAME)
        assert all(argv[i] != mcphost.SERVER_NAME for i in range(3, name_at))
        # every -e pair sits ahead of the name
        assert all(i < name_at for i, tok in enumerate(argv) if tok == "-e")

    def test_the_separator_precedes_the_command(self):
        argv = mcphost.register_argv(mcphost.AGY, SHIM)
        sep = argv.index("--")
        assert argv[sep - 1] == mcphost.SERVER_NAME
        assert argv[sep + 1:] == [SHIM, "mcp", "--stdio"]

    def test_no_scope_flag_is_passed(self):
        assert "--scope" not in mcphost.register_argv(mcphost.AGY, SHIM)
        assert "--scope" not in mcphost.unregister_argv(mcphost.AGY)

    def test_the_whole_argv(self):
        assert mcphost.register_argv(mcphost.AGY, SHIM, env={}) == [
            "agy", "mcp", "add", "boost", "--", SHIM, "mcp", "--stdio"]


class TestAddArgv:
    """`add_argv` is the one copy of the `mcp add` grammar.

    It exists because there were two: `register_argv` here and
    `mcpdecl.register_argv` on the install path, which "mirrored" this one for
    Claude and Gemini and had no agy branch at all — so agy, the single host
    whose CLI rejects Claude's shape, was handed exactly that. The parity is
    asserted across modules in `test_mcpdecl.py`; what is pinned here is the
    generalisation (an arbitrary command, not just boost's own) and the
    refusal.
    """

    def test_an_arbitrary_command_and_tail(self):
        assert mcphost.add_argv(mcphost.CLAUDE, "gh", "npx", ["-y", "pkg"],
                                env={"A": "1"}) == [
            "claude", "mcp", "add", "gh", "--scope", "user", "-e", "A=1",
            "--", "npx", "-y", "pkg"]

    def test_env_defaults_to_none_rather_than_boosts_own(self):
        # `register_argv` substitutes LAUNCH_ENV; the generic builder must not,
        # or every declared server would inherit boost's fork-safety vars.
        assert "-e" not in mcphost.add_argv(
            mcphost.CLAUDE, "gh", "npx", [])

    def test_an_empty_tail_ends_at_the_command(self):
        assert mcphost.add_argv(mcphost.GEMINI, "gh", "npx", [])[-1] == "npx"

    def test_a_host_in_the_table_with_no_grammar_raises(self, monkeypatch):
        # The regression this function exists to prevent: a new HOSTS row used
        # to inherit Claude's argv silently. A fourth host must be given a
        # branch, and until it is, boost says so instead of shipping the wrong
        # command line. ValueError, not KeyError — the host *is* known.
        monkeypatch.setitem(mcphost.HOSTS, "codex",
                            {"cli": "codex", "label": "Codex CLI"})
        with pytest.raises(ValueError, match="grammar"):
            mcphost.add_argv("codex", "gh", "npx", [])

    def test_an_unknown_host_still_raises_keyerror(self):
        with pytest.raises(KeyError):
            mcphost.add_argv("nope", "gh", "npx", [])


class TestRegisterArgvOptions:
    def test_scope_is_threaded_through_every_scoped_host(self):
        # agy is excluded by has_scope: it keeps one global file, so there is
        # no --scope to thread and passing one would be an error.
        for host in mcphost.hosts():
            argv = mcphost.register_argv(host, SHIM, scope="project")
            if mcphost.has_scope(host):
                assert argv[argv.index("--scope") + 1] == "project"
            else:
                assert "--scope" not in argv

    def test_custom_name_replaces_the_default(self):
        argv = mcphost.register_argv(mcphost.GEMINI, SHIM, name="boost-dev")
        assert "boost-dev" in argv
        assert "boost" not in argv

    def test_empty_env_emits_no_flags(self):
        for host in mcphost.hosts():
            assert "-e" not in mcphost.register_argv(host, SHIM, env={})

    def test_env_pairs_are_sorted_for_determinism(self):
        argv = mcphost.register_argv(mcphost.CLAUDE, SHIM,
                                     env={"B": "2", "A": "1", "C": "3"})
        assert [argv[i + 1] for i, tok in enumerate(argv) if tok == "-e"] == \
            ["A=1", "B=2", "C=3"]

    def test_default_env_is_the_fork_safety_pair(self):
        assert mcphost.LAUNCH_ENV == {
            "OBJC_DISABLE_INITIALIZE_FORK_SAFETY": "YES",
            "no_proxy": "*",
        }

    def test_unknown_host_raises(self):
        with pytest.raises(KeyError):
            mcphost.register_argv("copilot", SHIM)


class TestUnregisterArgv:
    def test_claude_is_narrowed_to_the_scope_the_guard_checked(self):
        # `claude mcp remove` needs no scope — 2.1.283 "removes from whichever
        # scope it exists in" — and that is exactly why boost passes one. One
        # of those scopes is `<cwd>/.mcp.json`, a committed file no $HOME
        # contains, so a scope-less remove reaches past `escapes_home`, which
        # vouches for the user-scope file alone. Register only ever writes
        # user scope; remove now matches it.
        assert mcphost.unregister_argv(mcphost.CLAUDE) == [
            "claude", "mcp", "remove", "--scope", "user", "boost"]

    def test_claude_scope_is_threaded_through(self):
        argv = mcphost.unregister_argv(mcphost.CLAUDE, scope="local")
        assert argv[argv.index("--scope") + 1] == "local"

    def test_gemini_needs_an_explicit_scope(self):
        # `gemini mcp remove` defaults to --scope project: without this it
        # reports "not found in project settings" and leaves the user-scope
        # registration in place, so unregister silently does nothing.
        assert mcphost.unregister_argv(mcphost.GEMINI) == [
            "gemini", "mcp", "remove", "--scope", "user", "boost"]

    def test_gemini_scope_is_threaded_through(self):
        argv = mcphost.unregister_argv(mcphost.GEMINI, scope="project")
        assert argv[argv.index("--scope") + 1] == "project"

    def test_custom_name(self):
        assert mcphost.unregister_argv(mcphost.CLAUDE, name="boost-dev")[-1] == \
            "boost-dev"

    def test_unknown_host_raises(self):
        with pytest.raises(KeyError):
            mcphost.unregister_argv("copilot")


class TestArgvDispatch:
    def test_register_matches_register_argv(self):
        for host in mcphost.hosts():
            assert mcphost.argv(host, "register", SHIM) == \
                mcphost.register_argv(host, SHIM)

    def test_unregister_matches_unregister_argv(self):
        for host in mcphost.hosts():
            assert mcphost.argv(host, "unregister") == \
                mcphost.unregister_argv(host)

    def test_scope_and_name_are_forwarded(self):
        assert mcphost.argv(mcphost.GEMINI, "unregister",
                            scope="project", name="x") == \
            ["gemini", "mcp", "remove", "--scope", "project", "x"]

    def test_unknown_action_raises_valueerror(self):
        with pytest.raises(ValueError):
            mcphost.argv(mcphost.CLAUDE, "reinstall", SHIM)


class TestResolve:
    @pytest.mark.parametrize("value", [None, "", "auto", "all"])
    def test_wildcards_select_every_host(self, value):
        assert mcphost.resolve(value) == mcphost.hosts()

    def test_a_named_host_selects_only_itself(self):
        assert mcphost.resolve("gemini") == ["gemini"]
        assert mcphost.resolve("claude") == ["claude"]

    def test_unknown_host_raises(self):
        with pytest.raises(KeyError):
            mcphost.resolve("copilot")

    def test_resolved_list_is_a_copy(self):
        mcphost.resolve("auto").append("bogus")
        assert mcphost.resolve("auto") == mcphost.hosts()


class TestIsNamed:
    @pytest.mark.parametrize("value", [None, "", "auto", "all"])
    def test_wildcards_are_not_named(self, value):
        # `auto` and `all` both tolerate a missing CLI by design — `auto`
        # skips it silently, `all` reports it without failing — so neither
        # may trip the exit-1 fix meant for a single named host.
        assert mcphost.is_named(value) is False

    def test_a_single_host_is_named(self):
        assert mcphost.is_named("gemini") is True
        assert mcphost.is_named("claude") is True
        assert mcphost.is_named("agy") is True

    def test_an_unknown_value_is_still_named(self):
        # is_named only classifies the wildcards; validating the name itself
        # is resolve()'s job, and it runs first in the command layer.
        assert mcphost.is_named("bogus") is True


class TestClassifyResult:
    """`classify_result` pinned as pure text classification — no subprocess,
    no filesystem. `_run_mcp_host` (commands/configuration.py) owns launching
    the process and detecting a missing CLI; this is everything after that,
    reachable without a real `claude`/`gemini`/`agy` on PATH.
    """

    def test_success_is_ran(self):
        assert mcphost.classify_result(
            "register", 0, "Added stdio MCP server boost\n", "") == ("ran", "")

    def test_successful_unregister_with_no_marker_is_ran(self):
        # The common case: something really was registered, and removing it
        # says nothing about "not found". Must not be misread as a no-op.
        assert mcphost.classify_result(
            "unregister", 0, "Removed boost\n", "") == ("ran", "")

    def test_register_already_exists_is_success_worded_differently(self):
        assert mcphost.classify_result(
            "register", 1, "",
            "MCP server boost already exists in local config"
        ) == ("already", "")

    def test_already_marker_is_case_insensitive(self):
        status, _ = mcphost.classify_result(
            "register", 1, "", "ALREADY REGISTERED elsewhere")
        assert status == "already"

    def test_already_marker_is_ignored_on_unregister(self):
        # "already exists" only means success when registering; on the way
        # out it is a real failure, not a no-op worded differently.
        status, detail = mcphost.classify_result(
            "unregister", 1, "", "already exists")
        assert status == "failed"
        assert detail == "already exists"

    def test_unregister_not_found_at_rc0_is_not_registered(self):
        # The exact Gemini message: `mcp remove --scope user boost` against
        # nothing registered prints this on stderr and still exits 0.
        assert mcphost.classify_result(
            "unregister", 0, "",
            'Server "boost" not found in user settings.\n'
        ) == ("not_registered", "")

    def test_not_found_marker_is_ignored_on_register(self):
        # The marker is scoped to unregister; a register success that happens
        # to echo "not found" in unrelated stdout must not be reclassified.
        status, _ = mcphost.classify_result(
            "register", 0, "config not found, creating a new one", "")
        assert status == "ran"

    def test_not_found_at_nonzero_rc_is_still_a_failure(self):
        # Only an rc-0 "not found" is a no-op; a nonzero exit with the same
        # words is a real error and keeps its own message.
        status, detail = mcphost.classify_result(
            "unregister", 1, "", "config file not found")
        assert status == "failed"
        assert detail == "config file not found"

    def test_plain_failure_returns_the_last_stderr_line(self):
        status, detail = mcphost.classify_result(
            "register", 1, "", "line one\nline two\nconnection refused")
        assert status == "failed"
        assert detail == "connection refused"

    def test_failure_with_no_stderr_names_it_unknown(self):
        status, detail = mcphost.classify_result("register", 1, "", "")
        assert status == "failed"
        assert detail == "unknown error"

    def test_blob_checks_both_streams(self):
        # The marker can land on stdout too — some CLIs write status there.
        status, _ = mcphost.classify_result(
            "register", 1, "already configured", "")
        assert status == "already"


class TestConfigHome:
    """Which file each host would write, and how ``HOME`` decides.

    These decide *which* file is at stake; :class:`TestEscapesHome` below
    covers the guard that compares it against boost's own ``HOME``. Both live
    in ``core`` — the guard moved out of the command layer so the mutation
    gate can see it — and every branch here is reachable without an agent CLI
    on PATH. The failure they describe is real and was observed: `boost mcp register` under a sandboxed
    ``HOME`` wrote into a live ``~/.claude-personal/.claude.json``, because the
    child CLI reads ``CLAUDE_CONFIG_DIR`` from the ambient environment and has
    never heard of boost's ``HOME``.

    Absolute-path fixtures are built with ``os.path.join``/``abspath`` rather
    than written as ``/x``: ``ntpath.isabs("/x")`` is True on CPython 3.12 and
    False on 3.13+, and CI runs both.
    """

    def _abs(self, *parts):
        return os.path.abspath(os.path.join(os.sep, *parts))

    def test_only_claude_has_a_config_home_variable(self):
        # Gemini's GEMINI_DIR is a JS constant, not an env var, and agy
        # exposes none at all — so both are anchored at $HOME and the escape
        # is Claude-only. Pinned as a set so a new host has to decide.
        assert mcphost.config_home_env(mcphost.CLAUDE) == "CLAUDE_CONFIG_DIR"
        assert mcphost.config_home_env(mcphost.GEMINI) is None
        assert mcphost.config_home_env(mcphost.AGY) is None

    def test_an_unknown_host_raises_like_the_rest_of_the_table(self):
        with pytest.raises(KeyError):
            mcphost.config_home_env("emacs")
        with pytest.raises(KeyError):
            mcphost.user_config_path("emacs", {}, self._abs("home"))

    def test_an_unset_variable_leaves_the_host_under_home(self):
        home = self._abs("home", "sandbox")
        assert mcphost.config_home(mcphost.CLAUDE, {}, home) == home

    def test_an_empty_variable_leaves_the_host_under_home(self):
        # Exported-but-empty is the shell's way of saying nothing, and the
        # CLI treats it that way too. Whitespace counts as empty.
        home = self._abs("home", "sandbox")
        for value in ("", "   "):
            assert mcphost.config_home(
                mcphost.CLAUDE, {"CLAUDE_CONFIG_DIR": value}, home) == home

    def test_a_relative_variable_falls_back_to_home(self):
        # Claude Code 2.1.283 refuses it in its own words — "the configuration
        # home (CLAUDE_CONFIG_DIR) is not an absolute path" — so nothing is
        # written anywhere and reporting an escape would be a false refusal.
        home = self._abs("home", "sandbox")
        assert mcphost.config_home(
            mcphost.CLAUDE, {"CLAUDE_CONFIG_DIR": "rel/cfg"}, home) == home

    def test_an_absolute_variable_wins_over_home(self):
        home = self._abs("home", "sandbox")
        elsewhere = self._abs("home", "real", ".claude-personal")
        assert mcphost.config_home(
            mcphost.CLAUDE, {"CLAUDE_CONFIG_DIR": elsewhere},
            home) == elsewhere

    def test_the_variable_is_ignored_for_hosts_that_do_not_read_it(self):
        # The exact machine shape that hid the bug: CLAUDE_CONFIG_DIR set,
        # and two hosts for which it means nothing.
        home = self._abs("home", "sandbox")
        env = {"CLAUDE_CONFIG_DIR": self._abs("home", "real", ".cfg")}
        for host in (mcphost.GEMINI, mcphost.AGY):
            assert mcphost.config_home(host, env, home) == home

    def test_each_host_names_its_own_user_scope_file(self):
        home = self._abs("home", "sandbox")
        assert mcphost.user_config_path(mcphost.CLAUDE, {}, home) == \
            os.path.join(home, ".claude.json")
        assert mcphost.user_config_path(mcphost.GEMINI, {}, home) == \
            os.path.join(home, ".gemini", "settings.json")
        assert mcphost.user_config_path(mcphost.AGY, {}, home) == \
            os.path.join(home, ".gemini", "config", "mcp_config.json")

    def test_the_escaping_path_is_the_one_that_was_actually_written(self):
        # The reported incident, as a path: HOME sandboxed, CLAUDE_CONFIG_DIR
        # left pointing at the developer's real config dir.
        real = self._abs("Users", "dev", ".claude-personal")
        cfg = mcphost.user_config_path(
            mcphost.CLAUDE, {"CLAUDE_CONFIG_DIR": real},
            self._abs("tmp", "sandbox-home"))
        assert cfg == os.path.join(real, ".claude.json")

    def test_every_known_host_has_a_user_scope_file(self):
        # A new host with no row would raise KeyError from inside the guard,
        # on the path where the guard is the only thing standing between a
        # sandboxed run and someone's real config.
        home = self._abs("home", "sandbox")
        for host in mcphost.hosts():
            assert mcphost.user_config_path(host, {}, home).startswith(home)


class TestEscapesHome:
    """The containment half of the guard, where the mutation gate can see it.

    :func:`mcphost.user_config_path` decides *which* file is at stake and is
    pure; this decides whether boost may let a child CLI write it. It lives in
    ``core`` for one reason: the required gate mutates ``boost_cli/core`` and
    runs ``tests/unit``, so a mutant that drops ``force`` or inverts the
    containment test is killed here rather than reviewed for.
    """

    def _elsewhere(self, tmp_path):
        out = tmp_path / "real-config"
        out.mkdir()
        return out

    def test_a_config_home_inside_home_is_contained(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        env = {"CLAUDE_CONFIG_DIR": str(home / ".claude-personal")}
        assert mcphost.escapes_home(mcphost.CLAUDE, env, home) is None

    def test_an_unset_variable_is_contained(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        assert mcphost.escapes_home(mcphost.CLAUDE, {}, home) is None

    def test_an_escape_returns_the_file_that_would_be_written(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        elsewhere = self._elsewhere(tmp_path)
        env = {"CLAUDE_CONFIG_DIR": str(elsewhere)}
        assert mcphost.escapes_home(mcphost.CLAUDE, env, home) == \
            str(elsewhere / ".claude.json")

    def test_force_waves_the_escape_through(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        env = {"CLAUDE_CONFIG_DIR": str(self._elsewhere(tmp_path))}
        assert mcphost.escapes_home(
            mcphost.CLAUDE, env, home, force=True) is None

    def test_force_does_not_invent_an_escape(self, tmp_path):
        # `force` may only ever turn a refusal into a pass, never the reverse.
        home = tmp_path / "home"
        home.mkdir()
        assert mcphost.escapes_home(
            mcphost.CLAUDE, {}, home, force=True) is None

    def test_a_link_inside_home_that_leads_out_is_an_escape(self, tmp_path):
        # Why this is `scopes.contains` and not a string prefix test: the
        # path is under $HOME and the write is not.
        home = tmp_path / "home"
        home.mkdir()
        elsewhere = self._elsewhere(tmp_path)
        link = home / "cfg"
        link.symlink_to(elsewhere, target_is_directory=True)
        env = {"CLAUDE_CONFIG_DIR": str(link)}
        assert mcphost.escapes_home(mcphost.CLAUDE, env, home) is not None

    def test_a_home_that_only_resolves_into_itself_still_matches(
            self, tmp_path):
        # macOS puts a tempdir $HOME under /var/folders, which resolves to
        # /private/var/... — resolving one side only would refuse every write.
        home = tmp_path / "home"
        home.mkdir()
        alias = tmp_path / "home-alias"
        alias.symlink_to(home, target_is_directory=True)
        env = {"CLAUDE_CONFIG_DIR": str(home / ".claude-personal")}
        assert mcphost.escapes_home(mcphost.CLAUDE, env, alias) is None

    def test_the_hosts_without_a_variable_are_never_an_escape(self, tmp_path):
        # Anchored at $HOME by construction: a Claude-only variable must not
        # hold back a write that was always landing in the sandbox.
        home = tmp_path / "home"
        home.mkdir()
        env = {"CLAUDE_CONFIG_DIR": str(self._elsewhere(tmp_path))}
        for host in (mcphost.GEMINI, mcphost.AGY):
            assert mcphost.escapes_home(host, env, home) is None

    def test_an_unknown_host_raises_rather_than_passing(self, tmp_path):
        # Fail loudly: a new host silently answering "contained" is the one
        # wrong answer this function must never give.
        with pytest.raises(KeyError):
            mcphost.escapes_home("copilot", {}, tmp_path)
