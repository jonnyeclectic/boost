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
`^    timeout-minutes: (\d+)\s*$` and `continue`d when it did not match, which
is how a job could carry a number nobody was checking while both tests stayed
green.

Reading the expression is not a matter of finding digits in it, either. The
condition has digits too — `matrix.os == 'windows-2025' && 45 || 30` is three
numbers to a regex and one cap to GitHub — so `job_timeouts` matches the two
*branch operands* structurally and refuses, loudly, any shape it was not
taught. And matching the source text of the condition proves nothing about
which cells get which cap: `caps_by_os` evaluates it once per entry in the
job's real `os:` list, so a condition that has stopped firing fails the test
instead of silently giving all nine cells the default.
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
# guessed — over the last 40 ci runs (every attempt, 2026-09-28) the slowest
# *successful* job of each kind was mutation-shard 55.7m against a cap of 75,
# tests 24.6m on windows against 45 and 10.3m on macOS against 30,
# patch-coverage 6.0m against 15, and everything else under 3m — but the
# assertion here is only that nobody sets a number so large it defeats the
# point. A timeout that trips on a normal run is worse than none, so
# individual jobs stay free to justify their own headroom.
MAX_REASONABLE = 90

# GitHub-hosted runners are killed at 360 minutes whatever the workflow says,
# so a timeout at or above that is not a bound, it is decoration. (Self-hosted
# runners have no such ceiling; this repo uses none.) Nothing may reach it.
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

# The `<cond> && <yes> || <no>` form reduced to its two branch operands.
# Anchored at the end so the condition — which may hold its own digits, in a
# runner label or a version string — is never mistaken for a cap.
TERNARY = re.compile(r"&&\s*(\d+)\s*\|\|\s*(\d+)\s*$")

# A whole expression that is one context lookup and nothing else — the only
# shape whose cap legitimately lives outside this repo's YAML.
CONTEXT_REF = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_-]+)*")

# The comparison forms a cap's condition is allowed to take, each paired with
# the predicate that evaluates it over one matrix value. Keeping this an
# explicit table is the point: an unlisted shape raises rather than being
# approximated, because a condition this file guesses at is a condition it is
# not really checking.
# GitHub's `==`, `startsWith` and `contains` fold case; these predicates do
# not. Every divergence therefore reads a cell as *not* matching when GitHub
# would match it, which can only turn a real cap into a reported miss — a
# false failure, never a false pass. Tighten it if a runner label ever varies
# in case; do not loosen it.
COMPARISONS = (
    (re.compile(r"^(\S+)\s*==\s*'([^']*)'$"), lambda value, lit: value == lit),
    (re.compile(r"^(\S+)\s*!=\s*'([^']*)'$"), lambda value, lit: value != lit),
    (re.compile(r"^startsWith\((\S+),\s*'([^']*)'\)$"),
     lambda value, lit: value.startswith(lit)),
    (re.compile(r"^!\s*startsWith\((\S+),\s*'([^']*)'\)$"),
     lambda value, lit: not value.startswith(lit)),
    (re.compile(r"^contains\((\S+),\s*'([^']*)'\)$"),
     lambda value, lit: lit in value),
)


def timeout_value(body: str) -> str | None:
    """The declared `timeout-minutes` of a job, comment and padding removed.

    Cutting the trailing YAML comment is not tidiness: reading the whole line
    turned `330        # under the 6 h ceiling, over the ~75 min worst tap`
    into three caps of 330, 6 and 75.
    """
    found = re.search(r"^    timeout-minutes:(.*)$", body, re.M)
    if not found:
        return None
    return re.split(r"\s+#", found.group(1))[0].strip()


def expression_of(value: str) -> str | None:
    """The inside of a `${{ ... }}` wrapper, or None if `value` is not one."""
    if value.startswith("${{") and value.endswith("}}"):
        return value[3:-2].strip()
    return None


def job_timeouts(body: str, where: str = "") -> list[int]:
    """Every integer minute count a job's `timeout-minutes` can take.

    A literal gives one; the `${{ <cond> && X || Y }}` form gives both
    branches, because both are caps that really apply to some matrix cell. A
    bare context reference (`${{ inputs.cap }}`) gives none — the number lives
    outside the file and there is nothing here to bound. That carve-out is
    deliberately narrow: `${{ cond && vars.WIN_CAP || vars.CAP }}` carries no
    digits either, but it is a decision this file *can* see the shape of, and
    letting it through unchecked is the same hole by another route.

    Anything else raises. Returning an empty list for an unparsed shape is how
    the trailing-comment bug hid a 330-minute cap from its own gate for
    months; a gate that skips what it cannot read reports the same "pass" as
    one that read it.
    """
    value = timeout_value(body)
    if value is None:
        return []
    if value.isdigit():
        return [int(value)]
    inner = expression_of(value)
    if inner is not None:
        branches = TERNARY.search(inner)
        if branches:
            return [int(n) for n in branches.groups()]
        if CONTEXT_REF.fullmatch(inner):
            return []
    raise AssertionError(
        "%s: timeout-minutes %r is neither an integer nor "
        "`${{ <cond> && N || M }}` — teach job_timeouts the shape rather than "
        "leaving the cap unchecked" % (where or "<job>", value))


def matrix_os_values(body: str) -> list[str]:
    """The runner labels a job's `os:` matrix axis actually produces."""
    assert not re.search(r"^ +include:\s*$", body, re.M), (
        "this job's matrix has an `include:`, which adds cells this function "
        "does not read — teach it the block before trusting the result")
    found = re.search(r"^ +os: \[([^\]]*)\]", body, re.M)
    assert found, "no `os:` matrix list in this job"
    return [v.strip().strip("'\"") for v in found.group(1).split(",") if v.strip()]


def caps_by_os(body: str) -> dict[str, int]:
    """Evaluate a job's timeout expression once per real matrix `os:` value.

    This is the whole point of the helper. `matrix.os == 'windows-latest'`
    reads correctly and yet fires for nothing at all once the matrix moves to
    `windows-2025`, and every assertion that matches the source text still
    passes while all nine cells quietly drop back to the default. Only
    evaluating the condition against the list that produces the cells can tell
    those two apart.
    """
    value = timeout_value(body)
    assert value is not None, "job declares no timeout-minutes"
    values = matrix_os_values(body)
    if value.isdigit():
        return {name: int(value) for name in values}
    inner = expression_of(value)
    assert inner is not None, value
    branches = TERNARY.search(inner)
    assert branches, "not a `<cond> && N || M` expression: %r" % value
    yes, no = (int(n) for n in branches.groups())
    condition = inner[:branches.start()].strip()
    for pattern, predicate in COMPARISONS:
        hit = pattern.match(condition)
        if hit:
            operand, literal = hit.groups()
            assert operand == "matrix.os", (
                "condition tests %r, not the os axis: %r" % (operand, condition))
            return {name: (yes if predicate(name, literal) else no)
                    for name in values}
    raise AssertionError("unrecognised condition %r — add it to COMPARISONS "
                         "so it is evaluated, not assumed" % condition)


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
    # Both spellings: GitHub loads `.yaml` too, so globbing only `.yml` would
    # let a whole workflow arrive outside every guard in this file.
    return sorted(set(WORKFLOWS.glob("*.yml")) | set(WORKFLOWS.glob("*.yaml")))


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
        # `"timeout-minutes:" in body` was the old test, and it accepted a
        # *step*-level cap as though it capped the job: eight spaces of indent
        # satisfy the substring while `timeout_value`'s four-space anchor —
        # and so the bound in the next test — never see it. Both guards now
        # ask the same question, so a job cannot be declared capped by one and
        # skipped by the other.
        assert timeout_value(body) is not None, (
            "%s / %s has no job-level timeout-minutes (a step-level one does "
            "not cap the job)" % (path.name, name))


@pytest.mark.parametrize("path", workflow_files(), ids=lambda p: p.name)
def test_no_timeout_is_large_enough_to_be_pointless(path):
    for name, body in jobs_in(path):
        allowed = JUSTIFIED_LONGER.get((path.name, name), MAX_REASONABLE)
        for minutes in job_timeouts(body, "%s / %s" % (path.name, name)):
            assert minutes < GITHUB_CEILING, (
                "%s / %s: timeout-minutes %d is at or over the 360-minute kill "
                "GitHub-hosted runners apply anyway, so it never fires"
                % (path.name, name, minutes))
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
        assert job_timeouts(body, filename) == [minutes], (
            "%s / %s no longer declares %d" % (filename, job, minutes))
        assert minutes > MAX_REASONABLE, (
            "%s / %s is back under the bound — drop the exception"
            % (filename, job))


def test_the_parser_reads_the_matrix_expression():
    """Non-vacuity: `job_timeouts` must see *both* numbers in the expression.

    `ci.yml` / `tests` is the repo's one expression-valued cap; if it ever
    goes back to a bare integer this test is the thing that says so, and the
    reader can delete it rather than discover the hole later.
    """
    body = dict(jobs_in(CI))["tests"]
    assert expression_of(timeout_value(body)) is not None, timeout_value(body)
    assert sorted(job_timeouts(body, "ci.yml / tests")) == [30, 45]


@pytest.mark.parametrize("value, expected", [
    ("30", [30]),
    ("${{ matrix.os == 'windows-2025' && 45 || 30 }}", [45, 30]),
    ("${{ startsWith(matrix.os, 'windows') && 45 || 30 }}", [45, 30]),
    ("${{ matrix.python == '3.14' && 45 || 30 }}", [45, 30]),
    ("${{ inputs.cap }}", []),
])
def test_the_parser_reads_branches_not_digits(value, expected):
    """The condition's own numbers are not caps, and used to be read as caps.

    A runner label (`windows-2025`) or a version string (`3.14`) in the
    condition made the old digit scan report 2025, or 3 and 14, as timeouts —
    a red build with a wrong message, on a config that was fine.
    """
    assert job_timeouts("    timeout-minutes: %s\n" % value) == expected


@pytest.mark.parametrize("value", [
    "${{ fromJSON(inputs.caps)[3] }}",
    # Digit-free, so a "no numbers here" carve-out waves it through — but it
    # is a two-branch decision this file can see, and the branch it does not
    # take is exactly where an unbounded cap would hide.
    "${{ startsWith(matrix.os, 'windows') && vars.WIN_CAP || vars.CAP }}",
])
def test_the_parser_refuses_a_shape_it_cannot_read(value):
    """Silence is the dangerous answer here, so there must not be one."""
    with pytest.raises(AssertionError, match="teach job_timeouts"):
        job_timeouts("    timeout-minutes: %s\n" % value)


def test_windows_gets_the_wider_cap_and_the_others_do_not():
    """Measured, not guessed — see the comment above the line in ci.yml.

    Over 40 `ci` runs the Windows cells' medians were 19.3-20.7 min against
    4.0-8.8 for Linux and macOS, and the slowest Windows run that still passed
    took 24.6. A flat 30 gave Windows 5.4 minutes of headroom, and on
    2026-09-28 windows-3.14 ran out of it twice in one morning — a release
    train's job at 30.4 min and main's own at 30.3, both still printing test
    results when they were killed.

    The assertion is on the *cap each real matrix cell gets*, not on how the
    condition is spelled: an equivalent rewrite (`!= 'windows-latest' && 30 ||
    45`) passes, and a condition that has quietly stopped matching its own
    `os:` list fails. Widening the default instead would make a wedged Linux
    job — the case the timeout exists for — take 50% longer to be killed.
    """
    caps = caps_by_os(dict(jobs_in(CI))["tests"])
    windows = {name: cap for name, cap in caps.items()
               if name.startswith("windows")}
    others = {name: cap for name, cap in caps.items()
              if not name.startswith("windows")}
    assert windows, "no windows runner in the os matrix: %r" % caps
    assert others, "no non-windows runner in the os matrix: %r" % caps
    assert min(windows.values()) > max(others.values()), (
        "the wider cap must land on Windows, not against it: %r" % caps)
    assert min(windows.values()) >= 40, (
        "45 is 1.8x the slowest Windows run that ever *passed* (24.6 min) and "
        "~1.5x the two that were killed at ~30.4; the assertion floors at 40 "
        "rather than pinning 45 so the value stays tunable, but under 40 the "
        "cap is back inside 1.6x of a run that already passed: %r" % caps)
    assert max(others.values()) == 30, (
        "the non-Windows cells measured 4.0-8.8 min with a worst pass of "
        "10.3; 30 is 2.9x the slowest of them and does not need widening: %r"
        % caps)
