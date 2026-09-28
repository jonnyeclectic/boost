# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: an install never registers a skill's MCP server outside $HOME.

`boost mcp register` is not the only place boost shells out to an agent CLI.
A skill can declare its own MCP servers, and `boost install` offers to wire
them up with the same `<host> mcp add` — through
``pkg._register_mcp_server``, a second ``subprocess.run`` with the same hole.
The child resolves its configuration home from the *ambient* environment
(Claude Code reads ``CLAUDE_CONFIG_DIR``, Codex CLI reads ``CODEX_HOME``),
never from the ``HOME`` boost was started with, so an install run under a
sandboxed ``HOME`` wrote into the developer's real config file.

There is no ``--force`` on this path: it is an install prompt, not a flag
surface, so the refusal prints the argv and leaves the decision with the user.
"""
from __future__ import annotations

import pathlib

import pytest

from boost_cli.commands import pkg
from boost_cli.core import mcpdecl

SPEC = {"command": "npx", "args": ["-y", "gh-mcp"]}


@pytest.fixture()
def clis(monkeypatch):
    """Every agent CLI present; every `mcp add` really writes its config."""
    from boost_cli.core import mcphost
    monkeypatch.setattr("boost_cli.commands.pkg.shutil.which",
                        lambda c: "/usr/local/bin/" + c)
    calls = []

    def fake_run(cmd, **kw):
        import os
        target = pathlib.Path(mcphost.user_config_path(
            cmd[0], os.environ, os.environ["HOME"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}", encoding="utf-8")
        calls.append(list(cmd))

        class _P:
            returncode, stdout, stderr = 0, "", ""
        return _P()

    monkeypatch.setattr("subprocess.run", fake_run)
    return calls


def test_an_install_refuses_a_config_file_outside_this_home(
        sandbox, monkeypatch, tmp_path, clis, capsys):
    elsewhere = tmp_path / "real-config"
    elsewhere.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(elsewhere))
    pkg._register_mcp_server("gh", SPEC, host="claude", scope="user")
    cap = capsys.readouterr()
    assert clis == []
    assert not (elsewhere / ".claude.json").exists()
    assert "outside this $HOME" in cap.out + cap.err
    # Actionable, like the "CLI not found" branch beside it.
    assert " ".join(mcpdecl.register_argv("gh", SPEC, host="claude")) \
        in cap.out + cap.err


def test_an_install_registers_normally_when_the_file_is_inside_home(
        sandbox, monkeypatch, clis, capsys):
    # The ordinary machine: CLAUDE_CONFIG_DIR under $HOME, or unset.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(sandbox / ".claude-personal"))
    pkg._register_mcp_server("gh", SPEC, host="claude", scope="user")
    cap = capsys.readouterr()
    assert clis == [mcpdecl.register_argv("gh", SPEC, host="claude")]
    assert (sandbox / ".claude-personal" / ".claude.json").exists()
    assert "registered MCP server gh" in cap.out


def test_the_variable_does_not_hold_back_the_other_hosts(
        sandbox, monkeypatch, tmp_path, clis, capsys):
    # Gemini and agy are anchored at $HOME; a Claude-only variable must not
    # refuse a write that was always going to land in the sandbox. Codex has
    # a variable of its own, so it is not in this set — see the two tests
    # below, which are this file's Claude pair over again for CODEX_HOME.
    elsewhere = tmp_path / "real-config"
    elsewhere.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(elsewhere))
    pkg._register_mcp_server("gh", SPEC, host="gemini", scope="user")
    cap = capsys.readouterr()
    assert clis == [mcpdecl.register_argv("gh", SPEC, host="gemini")]
    assert "outside this $HOME" not in cap.out + cap.err


def test_an_install_refuses_a_codex_home_outside_this_home(
        sandbox, monkeypatch, tmp_path, clis, capsys):
    # Codex is the second host to read its configuration home from the
    # ambient environment, so the hole this file exists for is open twice.
    # It is a distinct path, not the Claude one under another name: the file
    # is `config.toml` at the root of the home rather than a `.claude.json`
    # under it, so a guard that hard-coded either would vouch for the wrong
    # one.
    elsewhere = tmp_path / "real-codex"
    elsewhere.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(elsewhere))
    pkg._register_mcp_server("gh", SPEC, host="codex", scope="user")
    cap = capsys.readouterr()
    assert clis == []
    assert not (elsewhere / "config.toml").exists()
    assert "outside this $HOME" in cap.out + cap.err
    assert " ".join(mcpdecl.register_argv("gh", SPEC, host="codex")) \
        in cap.out + cap.err


def test_an_install_registers_codex_normally_inside_home(
        sandbox, monkeypatch, clis, capsys):
    # And unset is the ordinary machine, where the home is the $HOME/.codex
    # subdirectory the other three hosts do not have.
    monkeypatch.delenv("CODEX_HOME", raising=False)
    pkg._register_mcp_server("gh", SPEC, host="codex", scope="user")
    cap = capsys.readouterr()
    assert clis == [mcpdecl.register_argv("gh", SPEC, host="codex")]
    assert (sandbox / ".codex" / "config.toml").exists()
    assert "registered MCP server gh" in cap.out


def test_the_codex_variable_does_not_hold_back_the_other_hosts(
        sandbox, monkeypatch, tmp_path, clis, capsys):
    # The mirror of the Claude case: CODEX_HOME must not refuse a Claude
    # write that was always going to land in the sandbox.
    elsewhere = tmp_path / "real-codex"
    elsewhere.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(elsewhere))
    pkg._register_mcp_server("gh", SPEC, host="claude", scope="user")
    cap = capsys.readouterr()
    assert clis == [mcpdecl.register_argv("gh", SPEC, host="claude")]
    assert "outside this $HOME" not in cap.out + cap.err


def test_a_scope_this_guard_cannot_model_is_refused_loudly(sandbox):
    """The guard models the *user-scope* file and nothing else.

    A project registration writes ``<cwd>/.mcp.json``, which no ``$HOME``
    contains, so judging it against the user-scope path would vouch for a
    file nothing was going to write. ``_offer_mcp`` returns early for a
    project install, and this raise is what keeps that an invariant rather
    than a coincidence — the failure it prevents is silent.
    """
    from boost_cli.commands import pkg
    with pytest.raises(ValueError, match="user-scope only"):
        pkg._register_mcp_server("srv", {"command": "x"}, scope="project")
