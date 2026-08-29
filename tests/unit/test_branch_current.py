# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""A pull request that does not contain main's tip cannot merge.

This is the check that would have stopped the red `main` of 2026-08-29. Two
pull requests were each green against the `main` they were tested on, and the
second merged without re-testing against the first. Their source files did not
conflict; their *generated* roadmap board did, and a squash merge takes one
side of a generated file without ever reporting a conflict.

GitHub can enforce this natively, and the repository asks it to twice — but
classic branch protection has `enforce_admins: false`, so it does not apply to
the one account that merges, and the active ruleset has
`strict_required_status_checks_policy: false`. Between them, nothing was
enforcing it. A required *check* is enforced by the ruleset regardless, which
is why this lives in the repository rather than in a settings page.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = ROOT / "scripts" / "check_branch_current.py"


def _mod():
    spec = importlib.util.spec_from_file_location("check_branch_current", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_branch_containing_main_is_fine() -> None:
    assert _mod().problem("abc1234", contains_base=True) is None


def test_a_branch_behind_main_is_a_problem() -> None:
    out = _mod().problem("abc1234", contains_base=False)
    assert out is not None
    assert "abc1234" in out, "the message must name the commit to rebase onto"


def test_the_problem_names_the_fix() -> None:
    """A failing check that does not say what to run costs a support round."""
    out = _mod().problem("abc1234", contains_base=False)
    assert "git rebase origin/main" in out or "rebase" in out


@pytest.mark.parametrize("contains", [True, False])
def test_verdict_depends_only_on_containment(contains: bool) -> None:
    """The one input that decides it — nothing environmental leaks in."""
    assert (_mod().problem("deadbee", contains_base=contains) is None) is contains
