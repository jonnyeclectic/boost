"""Steps for the `boost mcp` scenarios — never shell out to a real `claude`
CLI; shutil.which/subprocess.run are patched exactly as
tests/functional/test_cli_configuration.py::TestMcp does.
"""
from __future__ import annotations

from unittest import mock

from behave import given


def _patch(context, target, replacement):
    patcher = mock.patch(target, replacement)
    patcher.start()
    context._patchers.append(patcher)


@given('the "claude" CLI is not on PATH')
def step_claude_missing(context):
    _patch(context, "boost_cli.commands.configuration.shutil.which",
           lambda c: None)


@given('the "claude" CLI is on PATH and succeeds')
def step_claude_present_succeeds(context):
    _patch(context, "boost_cli.commands.configuration.shutil.which",
           lambda c: "/usr/local/bin/claude" if c == "claude" else None)

    def fake_run(cmd, **kw):
        import types
        return types.SimpleNamespace(
            args=cmd, returncode=0, stdout="Added stdio MCP server boost\n",
            stderr="")

    _patch(context, "boost_cli.commands.configuration.subprocess.run", fake_run)


@given('the "claude" CLI is on PATH but fails with "{message}"')
def step_claude_present_fails(context, message):
    _patch(context, "boost_cli.commands.configuration.shutil.which",
           lambda c: "/usr/local/bin/claude" if c == "claude" else None)

    def fake_run(cmd, **kw):
        import types
        return types.SimpleNamespace(
            args=cmd, returncode=1, stdout="", stderr=message)

    _patch(context, "boost_cli.commands.configuration.subprocess.run", fake_run)
