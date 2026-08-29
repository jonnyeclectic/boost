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

import pytest

from boost_cli.core import mcphost

SHIM = "/usr/local/bin/boost"


class TestHostTable:
    def test_known_hosts_in_order(self):
        assert mcphost.hosts() == ["claude", "gemini"]

    def test_hosts_returns_a_copy_callers_cannot_corrupt(self):
        mcphost.hosts().append("bogus")
        assert mcphost.hosts() == ["claude", "gemini"]

    def test_cli_names(self):
        assert mcphost.cli(mcphost.CLAUDE) == "claude"
        assert mcphost.cli(mcphost.GEMINI) == "gemini"

    def test_labels(self):
        assert mcphost.label(mcphost.CLAUDE) == "Claude Code"
        assert mcphost.label(mcphost.GEMINI) == "Gemini CLI"

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


class TestRegisterArgvOptions:
    def test_scope_is_threaded_through_both_hosts(self):
        for host in mcphost.hosts():
            argv = mcphost.register_argv(host, SHIM, scope="project")
            assert argv[argv.index("--scope") + 1] == "project"

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
    def test_claude_takes_no_scope(self):
        assert mcphost.unregister_argv(mcphost.CLAUDE) == [
            "claude", "mcp", "remove", "boost"]

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
