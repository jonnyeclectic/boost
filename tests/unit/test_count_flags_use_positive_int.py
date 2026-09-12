# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A bare ``type=int`` on a count flag is a bug class, so the tree is scanned.

``util.positive_int``'s docstring names the failure: a count flag "ends up as a
slice bound or a ``git log -n`` argument -- where a negative silently *inverts*
the request instead of failing it". Four flags had drifted off it, and the
consequences ranged from a wrong message to ``tap --catalog --limit 0`` cloning
all 449 registries.

Rather than pin the four, this scans every ``add_argument`` in the command layer
and fails on any new bare ``type=int``. A genuinely unbounded integer option is
fine -- it just has to say so here, with the reason. That way the next count
flag either uses the helper or gets a deliberate exemption, instead of quietly
inheriting the bug.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

COMMANDS_DIR = pathlib.Path(__file__).resolve().parents[2] / "boost_cli" / "commands"

# flag -> why a bare int is correct here. These are not counts and not slice
# bounds, so 0 and negatives are either meaningful or already range-checked.
EXEMPT = {
    "--percent": "a rollout percentage: 0 legitimately means 'nobody'",
}


def _int_typed_flags() -> list[tuple[str, int, str]]:
    """(module, lineno, flag) for every ``add_argument(..., type=int, ...)``."""
    found: list[tuple[str, int, str]] = []
    for path in sorted(COMMANDS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Attribute)
                    and node.func.attr == "add_argument"):
                continue
            bare_int = any(
                kw.arg == "type" and isinstance(kw.value, ast.Name)
                and kw.value.id == "int"
                for kw in node.keywords)
            if not bare_int:
                continue
            flags = [a.value for a in node.args
                     if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            found.append((path.name, node.lineno, flags[0] if flags else "?"))
    return found


def test_no_new_bare_int_count_flag():
    offenders = [
        (mod, line, flag) for mod, line, flag in _int_typed_flags()
        if flag not in EXEMPT
    ]
    assert not offenders, (
        "bare `type=int` on a count flag silently inverts negatives and treats "
        "0 as falsy — use `util.positive_int` (or `util.port_number`), or add "
        "the flag to EXEMPT with a reason:\n"
        + "\n".join("  %s:%d  %s" % o for o in offenders))


def test_the_scanner_can_actually_see_a_bare_int():
    """A guard that cannot find anything is not a guard."""
    assert _int_typed_flags(), "scanner found no add_argument calls at all"
    assert {f for _m, _l, f in _int_typed_flags()} <= set(EXEMPT), (
        "every remaining bare int should be an exempt one")


@pytest.mark.parametrize("flag", sorted(EXEMPT))
def test_every_exemption_is_still_used(flag):
    """Delete an exemption when its flag goes away, so the list stays honest."""
    assert any(f == flag for _m, _l, f in _int_typed_flags()), (
        "%s is exempt but no longer exists — drop it from EXEMPT" % flag)
