# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: every CI job declares a timeout-minutes.

Without one a hung step — a stalled tap clone, a wedged smoke-test subprocess —
burns GitHub's default job timeout instead of failing fast, and the bill lands
hardest on the 3 OS x 3 Python `tests` matrix. This is a guard, not a
one-time cleanup: the point is that a job added next month cannot quietly
arrive without one.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"

# A job that delegates to a reusable workflow (`uses:` at job level) cannot
# carry timeout-minutes — GitHub rejects the key outright, so the timeout has
# to live inside the called workflow, which is not ours.
REUSABLE = re.compile(r"^    uses: ", re.M)

# The values themselves were chosen from observed job durations rather than
# guessed — mutation's slowest run was 24.8m, the tests matrix 8.3m, everything
# else under 2m — but the assertion here is only that nobody sets a number so
# large it defeats the point. A timeout that trips on a normal run is worse
# than none, so individual jobs stay free to justify their own headroom.
MAX_REASONABLE = 90


def jobs_in(path: Path):
    """Yield (job_name, job_body) for each top-level job in a workflow file."""
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^jobs:\s*$", text, re.M)
    if not match:
        return
    body = text[match.end():]
    for job in re.finditer(r"^  ([A-Za-z][\w-]*):\s*$\n((?:(?!^  \S).*\n)*)",
                           body, re.M):
        yield job.group(1), job.group(2)


def workflow_files():
    return sorted(WORKFLOWS.glob("*.yml"))


def test_there_are_workflows_to_check():
    # A parser that silently matches nothing would make every assertion below
    # vacuously true — the failure mode a config gate must not have.
    assert len(workflow_files()) >= 20


@pytest.mark.parametrize("path", workflow_files(), ids=lambda p: p.name)
def test_every_job_declares_a_timeout(path):
    found = list(jobs_in(path))
    assert found, "%s: parsed no jobs — the parser is broken, not the file" % path.name
    for name, body in found:
        if REUSABLE.search(body):
            continue
        assert "timeout-minutes:" in body, (
            "%s / %s has no timeout-minutes" % (path.name, name))


@pytest.mark.parametrize("path", workflow_files(), ids=lambda p: p.name)
def test_no_timeout_is_large_enough_to_be_pointless(path):
    for name, body in jobs_in(path):
        found = re.search(r"^    timeout-minutes: (\d+)\s*$", body, re.M)
        if not found:
            continue
        minutes = int(found.group(1))
        assert 0 < minutes <= MAX_REASONABLE, (
            "%s / %s: timeout-minutes %d is not a bound anyone would notice"
            % (path.name, name, minutes))
