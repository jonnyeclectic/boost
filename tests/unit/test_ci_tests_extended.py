# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""ci.yml's ``tests-extended``: the macOS/Windows 3.13/3.14 legs no PR runs.

A pull request's ``tests`` matrix is ubuntu on 3.12/3.13/3.14 (plus the
advisory 3.15 cell) and macOS and Windows on 3.12 alone. The other four cells
moved to ``tests-extended``, which runs on every push to main, nightly and on
dispatch. The trade is sound only while a handful of properties hold, and
losing any of them would change no colour on any run, so each is pinned here:

* the two jobs run the same steps. They are duplicated, not shared through an
  anchor, so this equality is the only thing that stops them drifting apart;
* between them they still cover every cell of the old 3 x 3 grid, once each;
* ``tests-extended`` reads nothing from ``proven`` and cannot continue on
  error, so a proven push cannot skip it and a red leg holds the release;
* it is not a required check (it reports on no pull request), and every
  blocking leg of the PR matrix still is.

When it runs, event by event, is in tests/unit/test_ci_proven_tree.py's
table; its timeout is held to its twin's in test_workflow_timeouts.py.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
REQUIRED = ROOT / ".github" / "required-checks.txt"
CHECKER = ROOT / "scripts" / "check_required_checks.py"

#: The grid every pull request ran before the split (3.15 aside).
FULL_GRID = {(os_, py) for os_ in ("ubuntu-latest", "macos-latest", "windows-latest")
             for py in ("3.12", "3.13", "3.14")}
#: What moved off pull requests: macOS and Windows above the floor.
EXTENDED = {(os_, py) for os_ in ("macos-latest", "windows-latest")
            for py in ("3.13", "3.14")}


@pytest.fixture(scope="module")
def jobs() -> dict:
    yaml = pytest.importorskip("yaml")
    if not CI.exists():
        pytest.skip(".github/workflows not reachable (e.g. mutation sandbox)")
    return yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]


@pytest.fixture(scope="module")
def checker():
    """scripts/check_required_checks.py, whose matrix expansion is GitHub's."""
    spec = importlib.util.spec_from_file_location("check_required_checks", CHECKER)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def legs(checker, jobs: dict, name: str) -> dict[str, dict]:
    """``{check name: matrix combination}`` for every leg the job expands to."""
    return checker.check_names(name, jobs[name]["strategy"]["matrix"], True)


def cells(checker, jobs: dict, name: str) -> set[tuple[str, str]]:
    return {(combo["os"], combo["python"]) for combo in legs(checker, jobs, name).values()}


def required() -> set[str]:
    return {line.strip() for line in REQUIRED.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")}


def test_the_two_jobs_run_the_same_steps(jobs):
    # Parsed, so YAML comments may differ (the step comments live in `tests`)
    # and nothing that runs may.
    twin, extended = jobs["tests"], jobs["tests-extended"]
    assert extended["steps"] == twin["steps"]
    for key in ("runs-on", "defaults", "permissions"):
        assert extended[key] == twin[key], key
    assert extended["strategy"]["fail-fast"] is twin["strategy"]["fail-fast"] is False


def test_together_they_cover_the_old_grid_once(checker, jobs):
    pr = cells(checker, jobs, "tests")
    extended = cells(checker, jobs, "tests-extended")
    assert extended == EXTENDED
    assert not pr & extended, "a cell runs twice: %s" % sorted(pr & extended)
    assert (pr | extended) - {("ubuntu-latest", "3.15")} == FULL_GRID, (
        "a cell of the old grid runs nowhere: %s"
        % sorted(FULL_GRID - (pr | extended)))
    # Coverage is measured in ubuntu-3.12, and ubuntu is the platform every
    # PR still runs on every interpreter.
    assert {("ubuntu-latest", py) for py in ("3.12", "3.13", "3.14")} <= pr


def test_the_extended_matrix_is_literal_and_off_linux(jobs):
    # Literal axes only: test_workflow_timeouts.py evaluates the cap over the
    # `os:` list as written and refuses an `include:`. And no Linux runner,
    # which is what keeps the twin's harden-runner and coverage steps inert.
    matrix = jobs["tests-extended"]["strategy"]["matrix"]
    assert set(matrix) == {"os", "python"}, sorted(matrix)
    assert not [o for o in matrix["os"] if o.startswith("ubuntu")], matrix["os"]


def test_nothing_from_proven_can_skip_it(jobs):
    # `proven` skips `tests` because a green PR run already ran those cells
    # on this tree. No PR run ran these, so nothing may let it skip them.
    job = jobs["tests-extended"]
    assert "needs" not in job
    assert "proven" not in json.dumps(job)


def test_a_red_leg_fails_the_run(jobs):
    # publish.yml releases on a *successful* ci push run, and
    # ci-failure-issue.yml alarms on the run's conclusion: both need a red
    # leg to redden the run.
    job = jobs["tests-extended"]
    assert "continue-on-error" not in job
    for step in job["steps"]:
        assert "continue-on-error" not in step, step.get("name")


def test_it_is_not_required_and_every_blocking_pr_leg_is(checker, jobs):
    names = required()
    assert not [n for n in names if n.startswith("tests-extended")], (
        "tests-extended reports on no pull request; requiring it would hold "
        "every PR on a status that never comes")
    blocking = {name for name, combo in legs(checker, jobs, "tests").items()
                if not checker.leg_is_advisory(jobs["tests"].get("continue-on-error"),
                                               combo)}
    assert {n for n in names if n.startswith("tests (")} == blocking


def test_an_extended_only_fix_can_be_tested_before_it_merges(jobs):
    # No pull request runs these legs, and dispatching ci.yml on a branch
    # posts skipped required checks onto the PR's head (ci.yml's note on
    # `workflow_dispatch:`). compat.yml's dispatch is the way in: its choices
    # must offer every tests-extended interpreter, on the same platforms, and
    # a push or the cron (no `inputs`) must still run 3.15.
    yaml = pytest.importorskip("yaml")
    compat = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "compat.yml").read_text(encoding="utf-8"))
    triggers = compat.get("on", compat.get(True))      # PyYAML reads `on:` as True
    choice = triggers["workflow_dispatch"]["inputs"]["python"]
    assert choice["type"] == "choice"
    assert choice["default"] == "3.15"
    extended = jobs["tests-extended"]["strategy"]["matrix"]
    assert set(extended["python"]) <= set(choice["options"]), (
        "a tests-extended interpreter compat.yml cannot be dispatched on")
    matrix = compat["jobs"]["compat"]["strategy"]["matrix"]
    assert matrix["os"] == extended["os"]
    assert matrix["python"] == ["${{ inputs.python || '3.15' }}"]
