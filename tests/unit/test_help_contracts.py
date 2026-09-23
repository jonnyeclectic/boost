# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""What a command's ``--help`` must say, beyond "every argument has help".

The 2026-08 CLI audit found contracts that only an error message revealed:
``run`` needing the Agents SDK and a key, ``discover`` reaching GitHub live
for a query, ``conflict`` exiting 1 on findings, ``cohort status`` being
``list`` under another name, and ``policy``'s keys appearing only in the hint
after a wrong ``set``. Each is now in the help screen, and pinned here.
"""
from __future__ import annotations

import importlib

import pytest

from boost_cli import cli
from boost_cli.core import policy


def _help(name: str, capsys) -> str:
    """``boost NAME --help`` with its line wrapping folded away."""
    module = next(m for n, _g, m, _s in cli.COMMANDS if n == name)
    fn = getattr(importlib.import_module("boost_cli.commands.%s" % module),
                 "cmd_" + name.replace("-", "_"))
    with pytest.raises(SystemExit) as exc:
        fn(["--help"])
    assert exc.value.code == 0
    return " ".join(capsys.readouterr().out.split())


@pytest.mark.parametrize("name, phrase", [
    ("run", "openai-agents[litellm]"),
    ("run", "ANTHROPIC_API_KEY"),
    ("discover", "searches GitHub live"),
    ("conflict", "exits 1 when any conflict is found"),
    ("test", "exits 1 when any skill fails"),
    ("verify", "exits 1 when any item fails"),
    ("attest", "exits 1 on a failure"),
    # Both resolve the name through info._resolve_text, which serves every
    # kind, installed or from a tap; the help used to say "skill".
    ("explain", "skill, rule or workflow"),
    ("preview", "skill, rule or workflow"),
    ("cohort", "status is the same as list"),
    ("cohort", "default: list"),
    ("profile", "default: list"),
    ("replay", "default: list"),
    ("protocol", "default: status"),
    ("context", "default: status"),
])
def test_help_states_the_contract(sandbox, capsys, name, phrase):
    assert phrase in _help(name, capsys)


def test_policy_help_names_every_key(sandbox, capsys):
    text = _help("policy", capsys)
    missing = [k for k in policy.DEFAULTS if k not in text]
    assert not missing, missing


def test_list_summary_names_every_kind():
    # `boost list` has listed rules and workflows since they became
    # installable; its row in `boost --help` still said "skills".
    summary = next(s for n, _g, _m, s in cli.COMMANDS if n == "list")
    assert summary == "List installed skills, rules and workflows"
