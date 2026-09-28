# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
r"""Unit tests: every CI job declares a usable timeout-minutes.

Without one a hung step — a stalled tap clone, a wedged smoke-test subprocess —
burns GitHub's default job timeout instead of failing fast, and the bill lands
hardest on the 3 OS x 3 Python `tests` matrix. This is a guard, not a
one-time cleanup: the point is that a job added next month cannot quietly
arrive without one.

The value is the other half, and it is the half that bit. `timeout-minutes`
takes an expression, so `tests` now sets a per-OS cap; the bound check read
`^    timeout-minutes: (\d+)$` and `continue`d when it did not match, which is
how a job could carry a number nobody was checking while both tests stayed
green. `job_timeouts` therefore reads the literal *and* the expression form and
yields every integer in it, and `test_the_parser_reads_the_matrix_expression`
fails if it ever stops finding the one real expression in the repo.
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

# GitHub kills any job at 360 minutes of its own accord, so a timeout at or
# above that is not a bound, it is decoration. Nothing may reach it.
GITHUB_CEILING = 360

# One job legitimately exceeds MAX_REASONABLE, and it is named here rather than
# waved through by loosening the bound for everyone. `shards.yml` / `build`
# embeds a whole bin-packed group of registries per matrix entry; the worst
# single tap measured ~75 minutes, and 330 is what fits several of those under
# the 6-hour ceiling. Its line carries a trailing comment, and that is exactly
# how it escaped: the old parser anchored on `(\d+)\s*$`, did not match, and
# `continue`d — so the one timeout in the repo over the bound was the one
# timeout the bound never saw.
JUSTIFIED_LONGER = {("shards.yml", "build"): 330}


CI = WORKFLOWS / "ci.yml"


def job_timeouts(body: str):
    """Yield every integer minute count a job's `timeout-minutes` can take.

    A literal yields one; the `${{ A && X || Y }}` form yields both branches,
    because both are caps that really apply to some matrix cell. Anything with
    no digits at all (a `${{ inputs.x }}` passthrough, say) yields nothing —
    there is no number here to bound.

    The trailing YAML comment is cut first, and that is not tidiness: reading
    the whole line turned `330        # under the 6 h ceiling, over the ~75 min
    worst tap` into three caps of 330, 6 and 75.
    """
    found = re.search(r"^    timeout-minutes:(.*)$", body, re.M)
    if not found:
        return
    value = re.split(r"\s+#", found.group(1))[0]
    for number in re.findall(r"\b(\d+)\b", value):
        yield int(number)


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
        allowed = JUSTIFIED_LONGER.get((path.name, name), MAX_REASONABLE)
        for minutes in job_timeouts(body):
            assert minutes < GITHUB_CEILING, (
                "%s / %s: timeout-minutes %d is at or over GitHub's own "
                "360-minute kill, so it never fires" % (path.name, name,
                                                        minutes))
            assert 0 < minutes <= allowed, (
                "%s / %s: timeout-minutes %d is not a bound anyone would "
                "notice — justify it in JUSTIFIED_LONGER or lower it"
                % (path.name, name, minutes))


def test_every_justified_exception_is_still_needed():
    """An allowance outlives its reason silently; this is what notices.

    If `shards.yml` / `build` ever drops back under MAX_REASONABLE, the entry
    stops documenting anything and starts hiding a regression, so it has to go.
    """
    for (filename, job), minutes in JUSTIFIED_LONGER.items():
        path = WORKFLOWS / filename
        assert path.exists(), filename
        body = dict(jobs_in(path)).get(job)
        assert body is not None, "%s / %s is gone" % (filename, job)
        assert list(job_timeouts(body)) == [minutes], (
            "%s / %s no longer declares %d" % (filename, job, minutes))
        assert minutes > MAX_REASONABLE, (
            "%s / %s is back under the bound — drop the exception"
            % (filename, job))


def test_the_parser_reads_the_matrix_expression():
    """Non-vacuity: `job_timeouts` must see *both* numbers in the expression.

    The bound check skips what it cannot parse, so a parser that quietly
    stopped matching would leave every expression-valued cap unchecked and
    report nothing. `ci.yml` / `tests` is the repo's one such job; if it ever
    goes back to a bare integer this test is the thing that says so, and the
    reader can delete it rather than discover the hole later.
    """
    body = dict(jobs_in(CI))["tests"]
    assert "${{" in body.split("timeout-minutes:")[1].splitlines()[0], body
    assert sorted(job_timeouts(body)) == [30, 45]


def test_windows_gets_the_wider_cap_and_the_others_do_not():
    """Measured, not guessed — see the comment above the line in ci.yml.

    Over 40 `ci` runs the Windows cells' medians were 18.4-20.6 min against
    3.9-8.1 for Linux and macOS, and the slowest Windows run that still passed
    took 24.6. A flat 30 gave Windows 5.4 minutes of headroom, and on
    2026-09-28 a release train's windows-3.14 job was cancelled at 30.4 min
    with pytest's last output a partial `99%` row.

    So this pins the *shape*: the wider cap is conditional on Windows, and the
    default branch stays tight. Widening the default would make a wedged Linux
    job — the case the timeout exists for — take 50% longer to be killed.
    """
    body = dict(jobs_in(CI))["tests"]
    line = next(ln for ln in body.splitlines() if "timeout-minutes:" in ln)
    assert "matrix.os == 'windows-latest'" in line, line
    # `A && B || C` is truthy-B or C: the Windows branch must be the larger
    # number, or the condition reads right and does the opposite.
    windows, default = (int(n) for n in re.findall(r"\b(\d+)\b", line))
    assert windows > default, line
    assert windows >= 40, (
        "45 is 1.8x the measured Windows worst case (24.6 min); anything much "
        "tighter puts the cap back inside the observed spread")
    assert default == 30, (
        "the non-Windows cells measured 3.9-8.1 min; 30 is already 4x the "
        "slowest of them and does not need widening")
