# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A string argument with no ``type=`` reads ``""`` as "not given", so the tree is scanned.

Handlers branch on ``if args.name:``, so an explicit empty value took the
no-argument path: ``attest --verify ""`` verified everything, ``tap ""`` tapped
the current directory, ``export -o ""`` wrote the default filename. Every
string-valued ``add_argument`` in the command layer therefore carries
``type=util.nonempty_str`` (or ``choices=``), and this scan fails on a new one
that does not -- unless it is listed in EXEMPT with the reason ``""`` is a
meaningful value there. Same shape as ``test_count_flags_use_positive_int``.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

COMMANDS_DIR = pathlib.Path(__file__).resolve().parents[2] / "boost_cli" / "commands"

# (module, argument) -> why an empty string must get through argparse here.
EXEMPT = {
    ("configuration.py", "value"):
        "config/policy set KEY VALUE: the setter validates per key, and an "
        "empty list value (`policy set blocked_skills ''`) clears it",
    ("bmad.py", "value"):
        "free text (`bmad route PROMPT`); the action validates it",
    ("discovery.py", "query"):
        "free text joined into one query; an empty query has its own error",
    ("intelligence.py", "question"):
        "free text joined into one question",
    ("intelligence.py", "--feedback"):
        "util.read_text_arg rejects it with a hint about `-` and @FILE",
}

_STORE_ACTIONS = {"store", "append", "extend"}


def _untyped_string_args() -> list[tuple[str, int, str]]:
    """(module, lineno, first name) for each string arg with no type/choices."""
    found: list[tuple[str, int, str]] = []
    for path in sorted(COMMANDS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "add_argument"):
                continue
            kws = {kw.arg: kw.value for kw in node.keywords if kw.arg}
            if "type" in kws or "choices" in kws:
                continue
            action = kws.get("action")
            if (isinstance(action, ast.Constant)
                    and action.value not in _STORE_ACTIONS):
                continue
            names = [a.value for a in node.args
                     if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            found.append((path.name, node.lineno, names[0] if names else "?"))
    return found


def test_no_string_argument_reads_empty_as_not_given():
    offenders = [o for o in _untyped_string_args()
                 if (o[0], o[2]) not in EXEMPT]
    assert not offenders, (
        "a string argument with no `type=` treats \"\" as not given -- add "
        "`type=util.nonempty_str`, or list it in EXEMPT with a reason:\n"
        + "\n".join("  %s:%d  %s" % o for o in offenders))


def test_the_scanner_can_see_an_untyped_argument():
    """A guard that cannot find anything is not a guard."""
    found = {(m, f) for m, _l, f in _untyped_string_args()}
    assert found, "scanner found no untyped add_argument calls at all"
    assert found <= set(EXEMPT)


@pytest.mark.parametrize("key", sorted(EXEMPT))
def test_every_exemption_is_still_used(key):
    assert key in {(m, f) for m, _l, f in _untyped_string_args()}, (
        "%s:%s is exempt but no longer untyped -- drop it from EXEMPT" % key)
