# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Steps for the `boost mcp` scenarios — never shell out to a real agent CLI;
shutil.which/subprocess.run are patched exactly as
tests/functional/test_cli_configuration.py::TestMcp does.

The steps are host-generic because `boost mcp` is: it registers with every
agent CLI it finds, so which CLIs are "installed" is the variable each scenario
sets. `boost` itself is never reported as present, which keeps
``paths.launcher()`` on its checkout-shim fallback and the argv stable.
"""
from __future__ import annotations

import types
from unittest import mock

from behave import given

WHICH = "boost_cli.commands.configuration.shutil.which"
RUN = "boost_cli.commands.configuration.subprocess.run"


def _patch(context, target, replacement):
    patcher = mock.patch(target, replacement)
    patcher.start()
    context._patchers.append(patcher)


def _present(context, *names):
    """Put exactly ``names`` on PATH for the duration of the scenario."""
    found = set(names)
    _patch(context, WHICH, lambda c: "/usr/local/bin/" + c if c in found else None)


def _succeeds(context):
    def fake_run(cmd, **kw):
        return types.SimpleNamespace(
            args=cmd, returncode=0, stdout="Added stdio MCP server boost\n",
            stderr="")

    _patch(context, RUN, fake_run)


@given('no agent CLI is on PATH')
def step_no_agent_cli(context):
    _present(context)


@given('the "{cli}" CLI is not on PATH')
def step_cli_missing(context, cli):
    _present(context)


@given('the "{cli}" CLI is on PATH and succeeds')
def step_cli_present_succeeds(context, cli):
    _present(context, cli)
    _succeeds(context)


@given('the "{first}" and "{second}" CLIs are on PATH and succeed')
def step_both_clis_present(context, first, second):
    _present(context, first, second)
    _succeeds(context)


@given('the "{cli}" CLI is on PATH but fails with "{message}"')
def step_cli_present_fails(context, cli, message):
    _present(context, cli)

    def fake_run(cmd, **kw):
        return types.SimpleNamespace(
            args=cmd, returncode=1, stdout="", stderr=message)

    _patch(context, RUN, fake_run)
