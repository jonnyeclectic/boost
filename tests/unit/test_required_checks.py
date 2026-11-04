# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: scripts/check_required_checks.py — the required-check drift gate.

The gate's whole job is to fail when the required-status-check list stops
matching reality, so the tests drive it against synthetic workflow trees rather
than only asserting that the real repo currently passes — a gate that can only
say "yes" is the failure mode this file exists to prevent.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_required_checks.py"


def load(monkeypatch, root: Path):
    """Import the gate with its ROOT/WORKFLOWS/CONFIG pointed at ``root``."""
    spec = importlib.util.spec_from_file_location("check_required_checks", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ROOT", root)
    monkeypatch.setattr(mod, "WORKFLOWS", root / ".github" / "workflows")
    monkeypatch.setattr(mod, "CONFIG", root / ".github" / "required-checks.txt")
    return mod


def workflow(root: Path, name: str, jobs: str, on_pr: bool = True,
             pr_filter: str = "", merge_group: bool = True) -> None:
    """Write a synthetic workflow.

    ``pr_filter`` is extra YAML nested under the ``pull_request:`` trigger (a
    ``paths:`` or ``types:`` block), used to build the conditionally-triggered
    workflows that must never be requireable.

    ``merge_group`` defaults to True so that every case written before the
    queue rule existed still exercises what it was written to exercise: with
    the opposite default they would all fail on the new rule instead, and the
    trigger cases would stop testing triggers.
    """
    d = root / ".github" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    trigger = "on:\n  push:\n" + ("  pull_request:\n" + pr_filter if on_pr else "")
    if merge_group:
        trigger += "  merge_group:\n"
    (d / name).write_text("name: %s\n%s\njobs:\n%s" % (name[:-4], trigger, jobs),
                          encoding="utf-8")


def matrix_job(job_id: str, matrix: str, extra: str = "") -> str:
    """A job block whose ``strategy.matrix`` is ``matrix`` (YAML at 8 spaces).

    A required leg resolves only if the job's matrix really produces it, so
    every test that requires a leg has to give its job one.
    """
    return ("  %s:\n    runs-on: ubuntu-latest\n%s    strategy:\n"
            "      matrix:\n%s" % (job_id, extra, matrix))


# ci.yml's `tests` job as it stood when the gate learned matrices: 3 OSes x 4
# Pythons, the 3.15 cells advisory through job-level continue-on-error. Kept as
# a fixture: the macOS/Windows 3.15 cells have since moved to compat.yml, and
# these tests are about expansion, not about today's ci.yml.
TESTS_JOB = matrix_job(
    "tests",
    "        os: [ubuntu-latest, macos-latest, windows-latest]\n"
    "        python: [\"3.12\", \"3.13\", \"3.14\", \"3.15\"]\n",
    extra="    continue-on-error: ${{ matrix.python == '3.15' }}\n")
REQUIRED_TESTS_LEGS = "".join(
    "tests (%s, %s)\n" % (os_, py)
    for os_ in ("ubuntu-latest", "macos-latest", "windows-latest")
    for py in ("3.12", "3.13", "3.14"))


# A reusable workflow in another repository, as osv-scanner.yml calls one: its
# jobs cannot be read from here, so any `caller / job` is accepted for it.
REMOTE = "org/repo/.github/workflows/x.yml@v1"


def callee(root: Path, name: str, jobs: str) -> None:
    """Write a reusable workflow: triggered by ``workflow_call`` and nothing else."""
    d = root / ".github" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text("name: %s\non:\n  workflow_call:\njobs:\n%s" % (name[:-4], jobs),
                          encoding="utf-8")


def config(root: Path, body: str) -> None:
    (root / ".github").mkdir(parents=True, exist_ok=True)
    (root / ".github" / "required-checks.txt").write_text(body, encoding="utf-8")


class TestPassing:
    def test_matching_list_passes(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "# comment\n\nlint\n")
        mod = load(monkeypatch, tmp_path)
        assert mod.main([]) == 0
        assert "no ambiguity" in capsys.readouterr().out

    def test_matrix_leg_resolves_to_its_job(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", matrix_job(
            "tests", "        os: [ubuntu-latest]\n        python: [\"3.9\"]\n"))
        config(tmp_path, "tests (ubuntu-latest, 3.9)\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_reusable_workflow_prefix_resolves(self, tmp_path, monkeypatch):
        workflow(tmp_path, "osv.yml", "  scan-pr:\n    uses: %s\n" % REMOTE)
        config(tmp_path, "scan-pr / osv-scan\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_a_job_with_no_body_reports_its_id(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  lint:\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_explicit_name_overrides_the_job_id(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml",
                 "  lint:\n    name: Lint everything\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "Lint everything\n")
        assert load(monkeypatch, tmp_path).main([]) == 0


class TestDrift:
    def test_required_name_with_no_job_fails(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\nmutation\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "'mutation'" in capsys.readouterr().err

    def test_job_that_does_not_run_on_pr_cannot_be_required(self, tmp_path, monkeypatch, capsys):
        # A nightly-only job can never gate a PR, so requiring it would block
        # every merge forever.
        workflow(tmp_path, "nightly.yml", "  slow:\n    runs-on: ubuntu-latest\n",
                 on_pr=False)
        config(tmp_path, "slow\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "pull_request" in capsys.readouterr().err

    def test_renamed_job_is_caught(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  lint-v2:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 1


class TestAmbiguity:
    def test_duplicate_check_name_across_workflows_fails(self, tmp_path, monkeypatch, capsys):
        # The real bug: `lint` existed in three workflows, so branch protection
        # could not require it unambiguously.
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "markdownlint.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "ambiguous" in err and "ci.yml" in err and "markdownlint.yml" in err

    def test_ambiguity_is_reported_even_when_not_required(self, tmp_path, monkeypatch):
        # A collision is a latent trap whether or not the name is required today.
        workflow(tmp_path, "a.yml", "  audit:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "b.yml", "  audit:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 1

    def test_same_name_in_one_workflow_is_not_a_collision(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml",
                 "  lint:\n    runs-on: ubuntu-latest\n  tests:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\ntests\n")
        assert load(monkeypatch, tmp_path).main([]) == 0


class TestConditionalTriggers:
    """A check that runs on only *some* PRs must never be requireable.

    This is the failure that actually bricks a repository: GitHub creates no
    check run at all for a workflow whose `paths:` filter does not match, so
    branch protection waits forever for a status that is never coming. The
    first version of the committed list required four path-filtered checks
    (validate, markdown-lint, theme-lint, vale) and the gate passed it, because
    it only looked for the string `pull_request:` and never at what narrowed it.
    """

    PATHS = "    paths:\n      - \"docs/**.html\"\n"
    LABELED = "    types: [labeled]\n"

    def test_path_filtered_job_cannot_be_required(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "html-validate.yml",
                 "  validate:\n    runs-on: ubuntu-latest\n", pr_filter=self.PATHS)
        config(tmp_path, "validate\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "only runs on SOME pull requests" in err
        # The message must name the culprit, or nobody can act on it.
        assert "html-validate.yml" in err

    def test_paths_ignore_is_a_filter_too(self, tmp_path, monkeypatch):
        workflow(tmp_path, "docs.yml", "  docs:\n    runs-on: ubuntu-latest\n",
                 pr_filter="    paths-ignore:\n      - \"**.md\"\n")
        config(tmp_path, "docs\n")
        assert load(monkeypatch, tmp_path).main([]) == 1

    def test_label_gated_job_cannot_be_required(self, tmp_path, monkeypatch, capsys):
        # `types: [labeled]` never fires on opened/synchronize, so an ordinary
        # PR produces no run — same deadlock, different mechanism.
        workflow(tmp_path, "fuzz.yml", "  fuzz:\n    runs-on: ubuntu-latest\n",
                 pr_filter=self.LABELED)
        config(tmp_path, "fuzz\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "only runs on SOME pull requests" in capsys.readouterr().err

    def test_types_list_covering_the_normal_events_is_still_requireable(self, tmp_path, monkeypatch):
        # Narrowing `types:` is only disqualifying when it drops the events every
        # PR actually emits; spelling them out explicitly must stay allowed.
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n",
                 pr_filter="    types: [opened, synchronize, reopened]\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_block_style_types_are_parsed(self, tmp_path, monkeypatch):
        workflow(tmp_path, "eval.yml", "  faithfulness:\n    runs-on: ubuntu-latest\n",
                 pr_filter="    types:\n      - labeled\n")
        config(tmp_path, "faithfulness\n")
        assert load(monkeypatch, tmp_path).main([]) == 1

    def test_a_filtered_job_nobody_requires_is_not_a_problem(self, tmp_path, monkeypatch):
        # Path-filtered workflows are fine and useful — they just cannot gate.
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "visual.yml", "  sweep:\n    runs-on: ubuntu-latest\n",
                 pr_filter=self.PATHS)
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_filtered_matrix_leg_is_caught(self, tmp_path, monkeypatch, capsys):
        # The matrix-leg spelling must not smuggle a filtered job past the gate.
        # The leg is a real one, so what fails it is the trigger and nothing else.
        workflow(tmp_path, "floors.yml",
                 matrix_job("lowest", "        python: [\"3.9\"]\n"),
                 pr_filter="    paths:\n      - \"pyproject.toml\"\n")
        config(tmp_path, "lowest (3.9)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "'lowest (3.9)' only runs on SOME pull requests" in err
        assert "floors.yml" in err

    def test_filtered_and_missing_are_reported_differently(self, tmp_path, monkeypatch, capsys):
        # "exists but cannot gate" and "does not exist" need different fixes.
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "visual.yml", "  sweep:\n    runs-on: ubuntu-latest\n",
                 pr_filter=self.PATHS)
        config(tmp_path, "lint\nsweep\nghost\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "'sweep' only runs on SOME pull requests" in err
        assert "'ghost' is not a job that runs on pull_request" in err


class TestPullRequestState:
    """Direct coverage of the trigger classifier."""

    def test_unfiltered(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        assert mod.pull_request_state(["on:", "  push:", "  pull_request:"]) == mod.PR_ALWAYS

    def test_absent(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        assert mod.pull_request_state(["on:", "  schedule:"]) == mod.PR_NONE

    def test_paths_filtered(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        assert mod.pull_request_state(
            ["on:", "  pull_request:", "    paths:", "      - \"docs/**\""]
        ) == mod.PR_FILTERED

    def test_a_later_siblings_paths_key_does_not_leak_in(self, tmp_path, monkeypatch):
        # `paths:` under a *different* trigger must not taint pull_request —
        # the block ends where the indentation returns to a sibling key.
        mod = load(monkeypatch, tmp_path)
        assert mod.pull_request_state(
            ["on:", "  pull_request:", "  push:", "    paths:", "      - \"docs/**\""]
        ) == mod.PR_ALWAYS


class TestMergeQueue:
    """A required check must report on the queue's ref, not just on the PR.

    The merge queue evaluates required checks against gh-readonly-queue/*. A
    workflow without `merge_group:` never reports there, so the check stays
    pending forever and nothing in the queue can land. It is invisible until
    someone flips the Settings toggle, which is exactly why it is a gate.
    """

    def test_required_check_without_merge_group_fails(self, tmp_path, monkeypatch,
                                                      capsys):
        workflow(tmp_path, "codeql.yml",
                 "  codeql-analyze:\n    runs-on: ubuntu-latest\n",
                 merge_group=False)
        config(tmp_path, "codeql-analyze\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        # Names the check AND the file to edit: an error that says only
        # "deadlock" sends you looking through 20-odd workflows.
        assert "'codeql-analyze'" in err
        assert "codeql.yml" in err
        assert "merge_group:" in err

    def test_adding_the_trigger_fixes_it(self, tmp_path, monkeypatch):
        workflow(tmp_path, "codeql.yml",
                 "  codeql-analyze:\n    runs-on: ubuntu-latest\n",
                 merge_group=True)
        config(tmp_path, "codeql-analyze\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_a_matrix_leg_resolves_through_its_job(self, tmp_path, monkeypatch):
        # The required entry is `tests (ubuntu-latest, 3.9)` but the trigger
        # lives on the `tests` job. Asserting BOTH directions, so a rule that
        # simply never fires on matrix legs cannot pass this pair.
        workflow(tmp_path, "ci.yml", matrix_job(
            "tests", "        os: [ubuntu-latest]\n        python: [\"3.9\"]\n"),
            merge_group=True)
        config(tmp_path, "tests (ubuntu-latest, 3.9)\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_a_matrix_leg_without_the_trigger_still_fails(self, tmp_path,
                                                          monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", matrix_job(
            "tests", "        os: [ubuntu-latest]\n        python: [\"3.9\"]\n"),
            merge_group=False)
        config(tmp_path, "tests (ubuntu-latest, 3.9)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "'tests (ubuntu-latest, 3.9)' comes from ci.yml" in err
        assert "merge_group:" in err

    def test_a_leg_the_matrix_does_not_produce_is_not_blamed_on_the_trigger(
            self, tmp_path, monkeypatch, capsys):
        # Nothing reports the leg at all, so "add merge_group:" would send the
        # reader to fix the wrong thing: the message must be about the leg.
        workflow(tmp_path, "ci.yml", TESTS_JOB, merge_group=False)
        config(tmp_path, "tests (ubuntu-latest, 3.9)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "is not one of the 12 legs" in err
        assert "merge_group" not in err

    def test_reusable_workflow_prefix_resolves(self, tmp_path, monkeypatch):
        # `scan-pr / osv-scan` is the real shape: the required name is
        # "caller / job", and the trigger is on the caller.
        workflow(tmp_path, "osv.yml", "  scan-pr:\n    uses: %s\n" % REMOTE,
                 merge_group=True)
        config(tmp_path, "scan-pr / osv-scan\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_an_unrequired_workflow_needs_no_trigger(self, tmp_path, monkeypatch):
        # The rule applies to REQUIRED checks only. Advisory path-filtered
        # workflows (vale, markdown-lint, ...) must not be dragged in.
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n",
                 merge_group=True)
        workflow(tmp_path, "prose.yml", "  vale:\n    runs-on: ubuntu-latest\n",
                 merge_group=False)
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_detector_reads_the_trigger_not_the_word(self, tmp_path, monkeypatch):
        # `merge_group` appearing in a comment or as a job id is not a trigger.
        # Without this, the gate passes on a workflow that only mentions it.
        mod = load(monkeypatch, tmp_path)
        assert mod.has_merge_group(["on:", "  merge_group:"]) is True
        assert mod.has_merge_group(["on:", "  push:"]) is False
        assert mod.has_merge_group(["on:", "  # merge_group: someday"]) is False
        assert mod.has_merge_group(["on:", "    merge_group:"]) is False


class TestMatrixLegs:
    """A required leg must be one the job's matrix actually expands to.

    GitHub never reports a matrix job under its bare name, only one check per
    leg. This gate used to accept any `job (anything)` as long as `job` existed,
    so dropping 3.12 from the matrix or renaming macos-latest left required legs
    that would never report — every PR then waits on "Expected — waiting for
    status" while lint stays green.
    """

    def test_a_leg_the_matrix_does_not_produce_fails(self, tmp_path, monkeypatch, capsys):
        # The red case: 3.9 is not in the matrix, so this leg never reports.
        workflow(tmp_path, "ci.yml", TESTS_JOB)
        config(tmp_path, "tests (ubuntu-latest, 3.9)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "'tests (ubuntu-latest, 3.9)' is not one of the 12 legs `tests` in ci.yml" in err
        # It lists what does exist, so the fix is a copy, not a guess.
        assert "tests (ubuntu-latest, 3.12), tests (ubuntu-latest, 3.13)" in err
        assert "tests (windows-latest, 3.15)" in err

    def test_the_nine_blocking_legs_of_the_real_shape_pass(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", TESTS_JOB)
        config(tmp_path, REQUIRED_TESTS_LEGS)
        assert load(monkeypatch, tmp_path).main([]) == 0
        # 12 legs reported, not the bare `tests`.
        assert "9 required, 12 PR check names" in capsys.readouterr().out

    def test_dropping_a_python_from_the_matrix_strands_its_legs(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", matrix_job(
            "tests",
            "        os: [ubuntu-latest, macos-latest, windows-latest]\n"
            "        python: [\"3.13\", \"3.14\"]\n"))
        config(tmp_path, REQUIRED_TESTS_LEGS)
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert err.count("is not one of the 6 legs") == 3
        for os_ in ("ubuntu-latest", "macos-latest", "windows-latest"):
            assert "'tests (%s, 3.12)'" % os_ in err
        assert "'tests (ubuntu-latest, 3.13)'" not in err

    def test_renaming_an_os_label_strands_its_legs(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", matrix_job(
            "tests",
            "        os: [ubuntu-latest, macos-15]\n        python: [\"3.12\"]\n"))
        config(tmp_path, "tests (ubuntu-latest, 3.12)\ntests (macos-latest, 3.12)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "'tests (macos-latest, 3.12)' is not one of the 2 legs" in err
        assert "'tests (ubuntu-latest, 3.12)'" not in err

    def test_the_bare_name_of_a_matrix_job_fails(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", TESTS_JOB)
        config(tmp_path, "tests\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "'tests' is the bare name of `tests` in ci.yml, a matrix job" in err
        assert "Require the legs instead: tests (ubuntu-latest, 3.12)" in err

    def test_a_leg_of_a_job_without_a_matrix_fails(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint (ubuntu-latest)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "'lint (ubuntu-latest)' is written as a matrix leg, but `lint` in ci.yml has no matrix" in err
        assert "reports as 'lint'" in err

    def test_exclude_removes_a_leg(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", matrix_job(
            "tests",
            "        os: [ubuntu-latest, windows-latest]\n"
            "        python: [\"3.12\", \"3.13\"]\n"
            "        exclude:\n          - os: windows-latest\n            python: \"3.12\"\n"))
        config(tmp_path, "tests (windows-latest, 3.13)\ntests (windows-latest, 3.12)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "'tests (windows-latest, 3.12)' is not one of the 3 legs" in err
        assert "'tests (windows-latest, 3.13)'" not in err

    def test_include_extends_a_leg_without_renaming_it(self, tmp_path, monkeypatch, capsys):
        # An include that matches an existing leg adds its key to that leg, but
        # the check name prints the axis values only: pytest-dev/pluggy run
        # 41711073433 reports `test (windows-py310)` for a leg its include
        # extends with python, os and tox_env.
        workflow(tmp_path, "ci.yml", matrix_job(
            "tests",
            "        os: [ubuntu-latest, windows-latest]\n"
            "        python: [\"3.12\"]\n"
            "        include:\n          - os: ubuntu-latest\n            coverage: true\n"))
        config(tmp_path, "tests (ubuntu-latest, 3.12)\ntests (windows-latest, 3.12)\n"
                         "tests (ubuntu-latest, 3.12, true)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "'tests (ubuntu-latest, 3.12, true)' is not one of the 2 legs" in err
        assert "Its legs are: tests (ubuntu-latest, 3.12), tests (windows-latest, 3.12)" in err
        assert "'tests (ubuntu-latest, 3.12)' is not" not in err
        assert "'tests (windows-latest, 3.12)' is not" not in err

    def test_the_pluggy_shape(self, tmp_path, monkeypatch):
        # One axis, every leg extended, plus one include that extends none and
        # so prints every value: the names a live run reported.
        mod = load(monkeypatch, tmp_path)
        names = mod.check_names("test", {
            "name": ["windows-py310", "ubuntu-py312"],
            "include": [
                {"name": "windows-py310", "python": "3.10", "os": "windows-latest",
                 "tox_env": "py310"},
                {"name": "windows-py313", "python": "3.13", "os": "windows-latest",
                 "tox_env": "py313"},
                {"name": "ubuntu-py312", "python": "3.12", "os": "ubuntu-latest",
                 "tox_env": "py312", "use_coverage": True},
            ]}, True)
        assert list(names) == [
            "test (windows-py310)", "test (ubuntu-py312)",
            "test (windows-py313, 3.13, windows-latest, py313)"]
        assert names["test (ubuntu-py312)"]["use_coverage"] is True

    def test_an_added_leg_prints_its_axis_keys_first(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        names = mod.check_names("tests", {
            "os": ["ubuntu-latest"],
            "include": [{"label": "extra", "os": "macos-latest"}]}, True)
        assert list(names) == ["tests (ubuntu-latest)", "tests (macos-latest, extra)"]

    def test_empty_values_are_left_out_of_the_name(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        names = mod.check_names("tests", {"flags": ["", "--x"], "py": ["3.13"]}, True)
        assert list(names) == ["tests (3.13)", "tests (--x, 3.13)"]
        assert list(mod.check_names("t", {"flags": [""]}, True)) == ["t"]

    def test_a_leg_name_over_100_characters_is_refused(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        assert mod.check_names("t", {"x": ["a" * 96]}, True)  # 100 exactly
        with pytest.raises(mod.Unexpandable, match="100 characters"):
            mod.check_names("t", {"x": ["a" * 97]}, True)

    def test_exclude_ignores_case_as_github_does(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", matrix_job(
            "tests",
            "        os: [ubuntu-latest, windows-latest]\n"
            "        python: [\"3.12\", \"3.13\"]\n"
            "        exclude:\n          - os: Windows-Latest\n"))
        config(tmp_path, "tests (windows-latest, 3.13)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "is not one of the 2 legs" in capsys.readouterr().err

    def test_an_include_key_differing_from_an_axis_in_case_is_refused(
            self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        with pytest.raises(mod.Unexpandable, match="differs from the axis os only in case"):
            mod.expand_matrix({"os": ["a"], "include": [{"OS": "a", "x": 1}]})

    def test_include_that_matches_nothing_adds_a_leg(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", matrix_job(
            "tests",
            "        os: [ubuntu-latest]\n        python: [\"3.12\"]\n"
            "        include:\n          - os: macos-latest\n            python: \"3.13\"\n"))
        config(tmp_path, "tests (ubuntu-latest, 3.12)\ntests (macos-latest, 3.13)\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_name_with_matrix_reference_is_substituted_without_a_suffix(
            self, tmp_path, monkeypatch, capsys):
        # licenses.yml's shape: `name: licenses (${{ matrix.name }})`.
        job = matrix_job(
            "licenses",
            "        include:\n          - name: runtime\n            install: \".[rag]\"\n"
            "          - name: eval extra\n            install: \".[eval]\"\n",
            extra="    name: licenses (${{ matrix.name }})\n")
        workflow(tmp_path, "licenses.yml", job)
        config(tmp_path, "licenses (eval extra)\nlicenses (runtime)\n")
        assert load(monkeypatch, tmp_path).main([]) == 0
        # The suffixed spelling is not what GitHub reports for such a job.
        config(tmp_path, "licenses (eval extra) (eval extra, .[eval])\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "legs are: licenses (runtime), licenses (eval extra)" in capsys.readouterr().err

    def test_legs_that_share_a_name_cannot_be_required(self, tmp_path, monkeypatch, capsys):
        # `name:` uses only one of two axes, so two legs report as `t a`: the
        # name would accept whichever finished, and the advisory 2-leg would
        # hide behind the blocking 1-leg if only one combination were kept.
        workflow(tmp_path, "ci.yml", matrix_job(
            "t", "        os: [a, b]\n        python: [1, 2]\n",
            extra="    name: t ${{ matrix.os }}\n"
                  "    continue-on-error: ${{ matrix.python == '2' }}\n"))
        config(tmp_path, "t a\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "two of its legs both report as 't a'" in err
        assert "fails closed" in err

    def test_name_with_matrix_os_on_a_cross_product(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", matrix_job(
            "build", "        os: [ubuntu-latest, macos-latest]\n",
            extra="    name: build on ${{ matrix.os }}\n"))
        config(tmp_path, "build on ubuntu-latest\nbuild on macos-latest\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_a_dynamic_matrix_is_refused_when_required(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", matrix_job(
            "shard", "        include: ${{ fromJSON(needs.plan.outputs.matrix) }}\n"))
        config(tmp_path, "shard (1)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "'shard (1)' looks like `shard` in ci.yml, whose check names cannot be worked out" in err
        assert "matrix.include is the expression ${{ fromJSON(needs.plan.outputs.matrix) }}" in err
        assert "fails closed" in err

    def test_a_dynamic_matrix_nobody_requires_is_not_a_problem(self, tmp_path, monkeypatch):
        # The real tree has two (mutation-shard, shards.yml build); the gate
        # must keep passing around them.
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n" + matrix_job(
            "build", "        registry: ${{ fromJson(needs.plan.outputs.matrix) }}\n"))
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_a_dynamic_matrix_job_is_not_satisfied_by_its_bare_name(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", matrix_job(
            "build", "        registry: ${{ fromJson(needs.plan.outputs.matrix) }}\n"))
        config(tmp_path, "build\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "matrix.registry is the expression" in capsys.readouterr().err

    def test_a_whole_strategy_expression_is_refused(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", "  build:\n    runs-on: ubuntu-latest\n"
                 "    strategy: ${{ fromJSON(needs.plan.outputs.strategy) }}\n")
        config(tmp_path, "build (1)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert ("its strategy is the expression ${{ fromJSON(needs.plan.outputs.strategy) }}"
                in capsys.readouterr().err)

    def test_any_other_expression_in_the_name_is_refused(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml",
                 "  deploy:\n    name: deploy ${{ github.ref_name }}\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "deploy main\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "its name uses ${{ github.ref_name }}, which is not evaluated here" in (
            capsys.readouterr().err)

    def test_booleans_render_lowercase(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", matrix_job(
            "tests", "        experimental: [true, false]\n"))
        config(tmp_path, "tests (true)\ntests (false)\n")
        assert load(monkeypatch, tmp_path).main([]) == 0
        config(tmp_path, "tests (True)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "'tests (True)' is not one of the 2 legs" in capsys.readouterr().err

    def test_a_caller_with_a_matrix_reports_per_leg(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "osv.yml", "  scan:\n    uses: %s\n    strategy:\n"
                 "      matrix:\n        lockfile: [a, b]\n" % REMOTE)
        config(tmp_path, "scan (a) / osv-scan\nscan (b) / osv-scan\n")
        assert load(monkeypatch, tmp_path).main([]) == 0
        config(tmp_path, "scan / osv-scan\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert ("'scan / osv-scan' is not one of the checks `scan` in osv.yml reports "
                "through %s" % REMOTE) in capsys.readouterr().err


class TestAdvisoryLegs:
    """A required check must be able to fail its run.

    Job-level continue-on-error lets the run pass when the job fails, and
    publish.yml releases on a successful ci run — so a required advisory leg is
    a contradiction. ci.yml's 3.15 cells are advisory and must stay unrequired.
    """

    def test_requiring_an_advisory_matrix_leg_fails(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", TESTS_JOB)
        config(tmp_path, REQUIRED_TESTS_LEGS + "tests (ubuntu-latest, 3.15)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "1 problem(s)" in err
        assert "'tests (ubuntu-latest, 3.15)' is advisory: `tests` in ci.yml" in err

    def test_literal_continue_on_error_fails(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", "  canary:\n    continue-on-error: true\n"
                 "    runs-on: ubuntu-latest\n")
        config(tmp_path, "canary\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "'canary' is advisory" in capsys.readouterr().err

    def test_an_advisory_job_nobody_requires_is_not_a_problem(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n"
                 "  canary:\n    continue-on-error: true\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_continue_on_error_false_is_blocking(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  lint:\n    continue-on-error: false\n"
                 "    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_an_unevaluated_expression_fails_closed(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", matrix_job(
            "tests", "        experimental: [false]\n",
            extra="    continue-on-error: ${{ matrix.experimental }}\n"))
        config(tmp_path, "tests (false)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "'tests (false)' cannot be checked: `tests` in ci.yml" in err
        assert "fails closed" in err

    @pytest.mark.parametrize(("coe", "combo", "want"), [
        (None, {}, False),
        (False, {}, False),
        (True, {}, True),
        ("${{ matrix.python == '3.15' }}", {"python": "3.15"}, True),
        ("${{ matrix.python == '3.15' }}", {"python": "3.14"}, False),
        ("${{matrix.python=='3.15'}}", {"python": "3.15"}, True),
        # GitHub ignores case when comparing strings.
        ("${{ matrix.os == 'Ubuntu-Latest' }}", {"os": "ubuntu-latest"}, True),
        # Mismatched types are cast to numbers: the string as a JSON number.
        ("${{ matrix.n == '10' }}", {"n": 10}, True),
        ("${{ matrix.n == '1e1' }}", {"n": 10}, True),
        ("${{ matrix.n == '11' }}", {"n": 10}, False),
        # GitHub looks context properties up ignoring case.
        ("${{ matrix.PYTHON == '3.15' }}", {"python": "3.15"}, True),
        ("${{ matrix.Python == '3.15' }}", {"python": "3.14"}, False),
        # A boolean is 1/0 and 'true' is NaN, so they are never equal.
        ("${{ matrix.experimental == 'true' }}", {"experimental": True}, False),
        ("${{ matrix.experimental == '1' }}", {"experimental": True}, True),
        # A key the leg lacks is null, which casts to 0 — as does ''.
        ("${{ matrix.missing == '0' }}", {}, True),
        ("${{ matrix.missing == '' }}", {}, True),
        ("${{ matrix.missing == 'x' }}", {}, False),
    ])
    def test_leg_is_advisory(self, tmp_path, monkeypatch, coe, combo, want):
        assert load(monkeypatch, tmp_path).leg_is_advisory(coe, combo) is want

    @pytest.mark.parametrize("coe", [
        "${{ matrix.experimental }}",
        "${{ matrix.python != '3.15' }}",
        "${{ matrix.python == \"3.15\" }}",
        "true",
        1,
    ])
    def test_other_forms_are_not_guessed(self, tmp_path, monkeypatch, coe):
        mod = load(monkeypatch, tmp_path)
        with pytest.raises(mod.Unexpandable, match="only expression evaluated"):
            mod.leg_is_advisory(coe, {"python": "3.15"})

    @pytest.mark.parametrize("literal", ["010", "+3", "0x3", "0o3", " 3", "3 ", "3.", ".5"])
    def test_number_shaped_literals_github_may_parse_are_not_guessed(
            self, tmp_path, monkeypatch, literal):
        # A required leg GitHub calls advisory must not pass as blocking.
        mod = load(monkeypatch, tmp_path)
        with pytest.raises(mod.Unexpandable, match="not a plain number"):
            mod.leg_is_advisory("${{ matrix.n == '%s' }}" % literal, {"n": 3})


class TestExpandMatrix:
    """The expansion itself, against the examples on docs.github.com."""

    def test_axes_multiply_first_key_slowest(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        assert mod.expand_matrix({"version": [10, 12], "os": ["ubuntu", "windows"]}) == [
            {"version": 10, "os": "ubuntu"}, {"version": 10, "os": "windows"},
            {"version": 12, "os": "ubuntu"}, {"version": 12, "os": "windows"}]

    def test_the_documented_include_example(self, tmp_path, monkeypatch):
        # "Expanding or adding matrix configurations": six combinations, and
        # `{color: pink, animal: cat}` overwrites the `color: green` an earlier
        # include added — only ORIGINAL values are protected.
        mod = load(monkeypatch, tmp_path)
        assert mod.expand_matrix({
            "fruit": ["apple", "pear"],
            "animal": ["cat", "dog"],
            "include": [
                {"color": "green"},
                {"color": "pink", "animal": "cat"},
                {"fruit": "apple", "shape": "circle"},
                {"fruit": "banana"},
                {"fruit": "banana", "animal": "cat"},
            ],
        }) == [
            {"fruit": "apple", "animal": "cat", "color": "pink", "shape": "circle"},
            {"fruit": "apple", "animal": "dog", "color": "green", "shape": "circle"},
            {"fruit": "pear", "animal": "cat", "color": "pink"},
            {"fruit": "pear", "animal": "dog", "color": "green"},
            {"fruit": "banana"},
            {"fruit": "banana", "animal": "cat"},
        ]

    def test_the_documented_exclude_example(self, tmp_path, monkeypatch):
        # "Excluding matrix configurations": 12 combinations, minus one full
        # match and two partial matches, leaves nine.
        mod = load(monkeypatch, tmp_path)
        combos = mod.expand_matrix({
            "os": ["macos-latest", "windows-latest"],
            "version": [12, 14, 16],
            "environment": ["staging", "production"],
            "exclude": [
                {"os": "macos-latest", "version": 12, "environment": "production"},
                {"os": "windows-latest", "version": 16},
            ],
        })
        assert len(combos) == 9
        assert {"os": "macos-latest", "version": 12, "environment": "staging"} in combos
        assert {"os": "macos-latest", "version": 12, "environment": "production"} not in combos
        assert not any(c["os"] == "windows-latest" and c["version"] == 16 for c in combos)

    def test_include_runs_after_exclude_so_it_can_add_a_leg_back(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        assert mod.expand_matrix({
            "os": ["a", "b"],
            "exclude": [{"os": "b"}],
            "include": [{"os": "b", "extra": 1}],
        }) == [{"os": "a"}, {"os": "b", "extra": 1}]

    def test_an_include_only_matrix_is_one_leg_per_entry(self, tmp_path, monkeypatch):
        # adapter-conformance.yml's shape: no axes, so nothing to extend.
        mod = load(monkeypatch, tmp_path)
        assert mod.expand_matrix({"include": [{"to": "crewai"}, {"to": "langgraph"}]}) == [
            {"to": "crewai"}, {"to": "langgraph"}]

    @pytest.mark.parametrize(("matrix", "why"), [
        ("${{ fromJSON(needs.plan.outputs.matrix) }}", "its matrix is the expression"),
        ({"registry": "${{ fromJson(x) }}"}, "matrix.registry is the expression"),
        ({"include": "${{ fromJSON(x) }}"}, "matrix.include is the expression"),
        ({"os": ["${{ inputs.os }}"]}, "matrix.os is the expression"),
        ({"os": []}, "matrix.os is not a non-empty list"),
        ({"os": [{"name": "x"}]}, "matrix.os is {'name': 'x'}, a dict"),
        ({"os": [3.12]}, "matrix.os is 3.12, a float"),
        ({"os": ["a"], "exclude": [{"os": "${{ x }}"}]}, "matrix.exclude.os is the expression"),
        ({"os": ["a"], "include": ["a"]}, "matrix.include is not a list of mappings"),
        (None, "its matrix is not a mapping"),
    ])
    def test_run_time_matrices_are_refused(self, tmp_path, monkeypatch, matrix, why):
        mod = load(monkeypatch, tmp_path)
        with pytest.raises(mod.Unexpandable, match=re.escape(why)):
            mod.expand_matrix(matrix)

    def test_check_names_leave_include_extras_out_of_extended_legs(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        names = mod.check_names("tests", {
            "os": ["ubuntu-latest", "windows-latest"], "python": ["3.12", "3.10"],
            "include": [{"os": "ubuntu-latest", "coverage": True}],
        }, True)
        assert list(names) == [
            "tests (ubuntu-latest, 3.12)", "tests (ubuntu-latest, 3.10)",
            "tests (windows-latest, 3.12)", "tests (windows-latest, 3.10)"]
        assert names["tests (ubuntu-latest, 3.10)"]["coverage"] is True
        assert "coverage" not in names["tests (windows-latest, 3.12)"]

    def test_a_matrix_excluded_down_to_nothing_is_refused(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        with pytest.raises(mod.Unexpandable, match="expands to no legs at all"):
            mod.check_names("t", {"os": ["a"], "exclude": [{"os": "a"}]}, True)

    def test_check_names_without_a_matrix_is_the_name_alone(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        assert mod.check_names("lint", None, False) == {"lint": {}}

    def test_a_matrix_reference_with_no_matrix_is_refused(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        with pytest.raises(mod.Unexpandable, match="it has no matrix to supply"):
            mod.check_names("t ${{ matrix.os }}", None, False)

    def test_a_matrix_reference_some_leg_lacks_is_refused(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        with pytest.raises(mod.Unexpandable, match=re.escape("matrix.extra, which a leg does not define")):
            mod.check_names("t ${{ matrix.extra }}",
                            {"os": ["a"], "include": [{"os": "b", "extra": 1}]}, True)


class TestAmbiguousLegs:
    def test_the_same_leg_from_two_workflows_is_ambiguous(self, tmp_path, monkeypatch, capsys):
        for wf in ("a.yml", "b.yml"):
            workflow(tmp_path, wf, matrix_job("tests", "        os: [ubuntu-latest]\n"))
        config(tmp_path, "tests (ubuntu-latest)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "'tests (ubuntu-latest)' is produced by 2 workflows (a.yml, b.yml)" in (
            capsys.readouterr().err)

    def test_a_matrix_job_and_a_plain_job_of_one_name_do_not_collide(self, tmp_path, monkeypatch):
        # One reports `lint`, the other only `lint (ubuntu-latest)`.
        workflow(tmp_path, "a.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "b.yml", matrix_job("lint", "        os: [ubuntu-latest]\n"))
        config(tmp_path, "lint\nlint (ubuntu-latest)\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_unexpandable_jobs_still_collide_on_their_raw_name(self, tmp_path, monkeypatch, capsys):
        # Their real legs cannot be listed, so the raw name is all there is to
        # compare — the same check every job got before matrices were expanded.
        for wf in ("a.yml", "b.yml"):
            workflow(tmp_path, wf, "  lint:\n    runs-on: ubuntu-latest\n" if wf == "a.yml"
                     else "  other:\n    runs-on: ubuntu-latest\n")
            workflow(tmp_path, "x" + wf, matrix_job("build", "        r: ${{ fromJson(x) }}\n"))
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "'build' is produced by 2 workflows (xa.yml, xb.yml)" in capsys.readouterr().err

    @pytest.mark.parametrize("job", [
        matrix_job("tests", "        os: ${{ fromJSON(needs.plan.outputs.os) }}\n"),
        matrix_job("tests", "        include: ${{ fromJSON(inputs.m) }}\n"),
        "  tests:\n    runs-on: ubuntu-latest\n    strategy:\n"
        "      matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}\n",
    ])
    def test_a_run_time_matrix_collides_with_another_workflows_legs(
            self, tmp_path, monkeypatch, capsys, job):
        # At run time the fromJSON job can report `tests (ubuntu-latest, 3.13)`
        # too, and GitHub would then accept the other workflow's green run for
        # ci.yml's red leg. Before matrices were expanded both were the raw
        # `tests` and this was caught; it must still be.
        workflow(tmp_path, "ci.yml", matrix_job(
            "tests", "        os: [ubuntu-latest]\n        python: [\"3.13\"]\n"))
        workflow(tmp_path, "other.yml", job)
        config(tmp_path, "tests (ubuntu-latest, 3.13)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert ("check name 'tests (ubuntu-latest, 3.13)' is produced by ci.yml, and "
                "`tests` in other.yml may report it too") in err
        assert "1 problem(s)" in err

    def test_a_run_time_name_collides_with_a_name_it_could_render(
            self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "a.yml", "  deploy:\n    runs-on: ubuntu-latest\n"
                 "    name: deploy ${{ github.ref_name }}\n")
        workflow(tmp_path, "b.yml", "  ship:\n    name: deploy main\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "deploy main\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert ("'deploy main' is produced by b.yml, and `deploy` in a.yml may report it too"
                in capsys.readouterr().err)

    def test_a_run_time_matrix_collides_with_a_bare_name_elsewhere(
            self, tmp_path, monkeypatch, capsys):
        # Which names a fromJson matrix produces is unknown, so the bare name is
        # not ruled out — HEAD flagged this pair through the raw `build`.
        workflow(tmp_path, "a.yml", "  build:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "b.yml", matrix_job("build", "        r: ${{ fromJson(x) }}\n"))
        config(tmp_path, "build\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert ("'build' is produced by a.yml, and `build` in b.yml may report it too"
                in capsys.readouterr().err)

    def test_a_run_time_matrix_leaves_names_it_cannot_take_alone(
            self, tmp_path, monkeypatch, capsys):
        # `build (...)` is its shape; `builder` and `build-docs (x)` are not,
        # and a name in its OWN workflow is not a cross-workflow collision.
        workflow(tmp_path, "a.yml", matrix_job("build", "        r: ${{ fromJson(x) }}\n")
                 + matrix_job("other", "        r: [x]\n", extra="    name: build\n"))
        workflow(tmp_path, "b.yml", "  builder:\n    runs-on: ubuntu-latest\n"
                 + matrix_job("build-docs", "        r: [x]\n"))
        config(tmp_path, "builder\nbuild-docs (x)\nbuild (x)\n")
        assert load(monkeypatch, tmp_path).main([]) == 0
        assert "3 required" in capsys.readouterr().out

    def test_a_remote_call_collides_with_a_local_call_of_the_same_name(
            self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "a.yml", "  scan-pr:\n    uses: %s\n" % REMOTE)
        callee(tmp_path, "r.yml", "  osv-scan:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "b.yml", "  scan-pr:\n    uses: ./.github/workflows/r.yml\n")
        config(tmp_path, "scan-pr / osv-scan\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert ("'scan-pr / osv-scan' is produced by b.yml, and 'scan-pr / <any job>' in "
                "a.yml may report it too") in capsys.readouterr().err


class TestReusableWorkflowCalls:
    """A job that calls a reusable workflow reports only `caller / callee job`.

    The gate used to accept `X / anything` whenever X was any check name, and
    the bare caller name too — neither ever reports, so requiring one waits
    forever. A callee in this repository is read, so its jobs and their
    continue-on-error count; one elsewhere cannot be.
    """

    LOCAL = "  scan-pr:\n    uses: ./.github/workflows/r.yml\n"

    def test_a_job_that_calls_nothing_has_no_caller_form(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint / bogus\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert ("'lint / bogus' is written as `caller / job`, but `lint` in ci.yml calls "
                "no reusable workflow: it reports as lint and nothing else"
                in capsys.readouterr().err)

    def test_the_bare_caller_never_reports(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "osv.yml", "  scan-pr:\n    uses: %s\n" % REMOTE)
        config(tmp_path, "scan-pr\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert ("'scan-pr' is the bare name of `scan-pr` in osv.yml, which calls the "
                "reusable workflow %s" % REMOTE) in capsys.readouterr().err

    def test_a_local_callee_job_resolves(self, tmp_path, monkeypatch, capsys):
        callee(tmp_path, "r.yml", "  osv-scan:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "ci.yml", self.LOCAL)
        config(tmp_path, "scan-pr / osv-scan\n")
        assert load(monkeypatch, tmp_path).main([]) == 0
        # The callee's own job runs on workflow_call alone, so `osv-scan` is
        # not a PR check: only the composed name is.
        assert "1 PR check names" in capsys.readouterr().out

    def test_a_local_callee_job_that_does_not_exist_fails(self, tmp_path, monkeypatch, capsys):
        callee(tmp_path, "r.yml", "  osv-scan:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "ci.yml", self.LOCAL)
        config(tmp_path, "scan-pr / bogus\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert ("'scan-pr / bogus' is not one of the checks `scan-pr` in ci.yml reports "
                "through ./.github/workflows/r.yml, so it would never report and every "
                "PR would wait on it forever. They are: scan-pr / osv-scan"
                in capsys.readouterr().err)

    @pytest.mark.parametrize("prefix", ["./", "$/"])
    def test_both_same_repository_spellings_are_read(self, tmp_path, monkeypatch, capsys, prefix):
        # `$/` is docs.github.com's recommended spelling for a callee in this
        # repository; treating it as remote would accept any `caller / job`.
        callee(tmp_path, "r.yml", "  osv-scan:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "ci.yml", "  scan-pr:\n    uses: %s.github/workflows/r.yml\n" % prefix)
        config(tmp_path, "scan-pr / bogus\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "'scan-pr / bogus' is not one of the checks" in capsys.readouterr().err

    def test_the_remote_placeholder_is_not_a_check_name(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "osv.yml", "  scan-pr:\n    uses: %s\n" % REMOTE)
        config(tmp_path, "scan-pr / <any job>\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "this gate's placeholder" in capsys.readouterr().err

    def test_an_advisory_local_callee_job_fails(self, tmp_path, monkeypatch, capsys):
        callee(tmp_path, "r.yml", "  osv-scan:\n    continue-on-error: true\n"
               "    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "ci.yml", self.LOCAL)
        config(tmp_path, "scan-pr / osv-scan\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "'scan-pr / osv-scan' is advisory: `osv-scan` in r.yml" in capsys.readouterr().err

    def test_a_local_callee_matrix_job_reports_per_leg(self, tmp_path, monkeypatch, capsys):
        callee(tmp_path, "r.yml", matrix_job(
            "test", "        py: [\"3.13\", \"3.15\"]\n",
            extra="    continue-on-error: ${{ matrix.py == '3.15' }}\n"))
        workflow(tmp_path, "ci.yml", self.LOCAL)
        config(tmp_path, "scan-pr / test (3.13)\n")
        assert load(monkeypatch, tmp_path).main([]) == 0
        config(tmp_path, "scan-pr / test (3.15)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "'scan-pr / test (3.15)' is advisory: `test` in r.yml" in capsys.readouterr().err

    def test_a_local_callee_that_is_missing_fails_closed(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", "  scan-pr:\n    uses: ./.github/workflows/nope.yml\n")
        config(tmp_path, "scan-pr / osv-scan\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert ("looks like `scan-pr` in ci.yml, whose check names cannot be worked out: "
                "the reusable workflow ./.github/workflows/nope.yml is not a file in "
                ".github/workflows" in capsys.readouterr().err)

    def test_a_local_path_outside_the_workflows_dir_fails_closed(self, tmp_path, monkeypatch, capsys):
        callee(tmp_path, "r.yml", "  osv-scan:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "ci.yml", "  scan-pr:\n    uses: ./r.yml\n")
        config(tmp_path, "scan-pr / osv-scan\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert ("the reusable workflow ./r.yml is not a file in .github/workflows"
                in capsys.readouterr().err)

    def test_a_local_callee_job_with_run_time_names_fails_closed(
            self, tmp_path, monkeypatch, capsys):
        callee(tmp_path, "r.yml", matrix_job("shard", "        n: ${{ fromJSON(inputs.n) }}\n"))
        workflow(tmp_path, "ci.yml", self.LOCAL)
        config(tmp_path, "scan-pr / shard (1)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "looks like `scan-pr` in ci.yml, whose check names cannot be worked out" in err
        assert ("job `shard` of the reusable workflow ./.github/workflows/r.yml cannot be "
                "worked out: matrix.n is the expression") in err

    def test_a_remote_call_inside_a_local_callee_takes_any_job(self, tmp_path, monkeypatch):
        callee(tmp_path, "r.yml", "  inner:\n    uses: %s\n" % REMOTE)
        workflow(tmp_path, "ci.yml", self.LOCAL)
        config(tmp_path, "scan-pr / inner / anything\n")
        assert load(monkeypatch, tmp_path).main([]) == 0
        config(tmp_path, "scan-pr / outer / anything\n")
        assert load(monkeypatch, tmp_path).main([]) == 1

    def test_nesting_stops_at_githubs_limit(self, tmp_path, monkeypatch, capsys):
        # The caller and nine levels of reusable workflows are allowed; a tenth
        # level — and so any cycle — is not.
        def chain(levels: int) -> None:
            for i in range(1, levels + 1):
                body = ("  j:\n    uses: ./.github/workflows/c%d.yml\n" % (i + 1)
                        if i < levels else "  j:\n    runs-on: ubuntu-latest\n")
                callee(tmp_path, "c%d.yml" % i, body)
            workflow(tmp_path, "ci.yml", "  top:\n    uses: ./.github/workflows/c1.yml\n")
            config(tmp_path, " / ".join(["top"] + ["j"] * levels) + "\n")

        chain(9)
        assert load(monkeypatch, tmp_path).main([]) == 0
        chain(10)
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert ("looks like `top` in ci.yml, whose check names cannot be worked out: the "
                "reusable workflow ./.github/workflows/c10.yml is called more than 9 "
                "levels deep" in capsys.readouterr().err)

    def test_a_cycle_fails_closed(self, tmp_path, monkeypatch, capsys):
        callee(tmp_path, "r.yml", "  j:\n    uses: ./.github/workflows/r.yml\n")
        workflow(tmp_path, "ci.yml", "  j:\n    uses: ./.github/workflows/r.yml\n")
        config(tmp_path, "j / j\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert ("the reusable workflow ./.github/workflows/r.yml is called more than 9 "
                "levels deep — past GitHub's limit, or a cycle" in capsys.readouterr().err)


class TestUnquotedValues:
    """A matrix value PyYAML and GitHub read or print differently is refused.

    PyYAML is YAML 1.1, so `yes` is True, `010` is 8 and `1e3` a string; per
    the review of actions/runner's reader, GitHub keeps `yes`, reads ten and a
    thousand, and prints numbers with 15 significant digits. A leg name this
    gate rendered from its own reading would pass here and never report.
    """

    def _job(self, tmp_path, monkeypatch, body: str):
        workflow(tmp_path, "ci.yml", body)
        mod = load(monkeypatch, tmp_path)
        return mod.parse_workflow(tmp_path / ".github" / "workflows" / "ci.yml")[2]["j"]

    @pytest.mark.parametrize(("value", "loads_as"), [
        ("yes", "True"), ("off", "False"), ("010", "8"), ("1_000", "1000"),
        ("0x1F", "31"), ("+1", "1"), ("1:30", "90"), ("1234567890123456", "1234567890123456"),
        ("8.0", "8.0"), ("3.10", "3.1"), ("1.0e+3", "1000.0"), (".inf", "inf"),
        ("1e3", "'1e3'"), ("09", "'09'"), ("0o17", "'0o17'"), ("1.0e3", "'1.0e3'"),
        ("2026-11-03", "datetime.date(2026, 11, 3)"),
    ])
    def test_a_value_the_two_readers_disagree_on_is_refused(
            self, tmp_path, monkeypatch, value, loads_as):
        job = self._job(tmp_path, monkeypatch, matrix_job("j", "        v: [%s]\n" % value))
        assert job.legs == {}
        assert job.why == ("matrix.v is the unquoted %s, which PyYAML loads as %s and "
                           "GitHub may read or print differently — quote it" % (value, loads_as))

    @pytest.mark.parametrize(("value", "leg"), [
        ("true", "j (true)"), ("False", "j (false)"), ("TRUE", "j (true)"),
        ("10", "j (10)"), ("0", "j (0)"), ("-5", "j (-5)"),
        ("123456789012345", "j (123456789012345)"),
        ("'3.10'", "j (3.10)"), ("\"1e3\"", "j (1e3)"), ("'yes'", "j (yes)"),
        ("ubuntu-latest", "j (ubuntu-latest)"), ("3.12-dev", "j (3.12-dev)"),
        ("tRue", "j (tRue)"),
    ])
    def test_a_value_both_read_alike_is_rendered(self, tmp_path, monkeypatch, value, leg):
        job = self._job(tmp_path, monkeypatch, matrix_job("j", "        v: [%s]\n" % value))
        assert job.why == ""
        assert list(job.legs) == [leg]

    def test_through_the_gate(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", matrix_job("j", "        coverage: [yes, no]\n"))
        config(tmp_path, "j (true)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "'j (true)' looks like `j` in ci.yml" in err
        assert "matrix.coverage is the unquoted yes" in err

    @pytest.mark.parametrize(("name", "why"), [
        ("1e3", "its name is the unquoted 1e3, which PyYAML loads as '1e3'"),
        ("yes", "its name is the unquoted yes, which PyYAML loads as True"),
        ("true", "its name is True, not a string — quote it"),
        ("12", "its name is 12, not a string — quote it"),
        ("[a]", "its name is ['a'], a list"),
    ])
    def test_a_name_that_is_not_a_string_is_refused(self, tmp_path, monkeypatch, name, why):
        job = self._job(tmp_path, monkeypatch,
                        "  j:\n    name: %s\n    runs-on: ubuntu-latest\n" % name)
        assert job.legs == {}
        assert job.why.startswith(why)

    def test_continue_on_error_spelled_yes_is_not_evaluated(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", "  j:\n    continue-on-error: yes\n"
                 "    runs-on: ubuntu-latest\n")
        config(tmp_path, "j\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "its continue-on-error is yes, and the only expression" in (
            capsys.readouterr().err)


class TestMixedTypes:
    """include/exclude never decide a match between values of different types."""

    @pytest.mark.parametrize(("matrix", "why"), [
        ({"py": ["3"], "include": [{"py": 3, "x": "z"}]},
         "matrix.include compares '3' with 3, values of different types"),
        ({"on": [True], "include": [{"on": 1, "x": "z"}]},
         "matrix.include compares True with 1, values of different types"),
        ({"py": ["3"], "exclude": [{"py": 3}]},
         "matrix.exclude compares '3' with 3, values of different types"),
        ({"py": ["3"], "exclude": [{"os": "a"}]},
         "matrix.exclude names os, which is not one of its axes"),
    ])
    def test_refused(self, tmp_path, monkeypatch, matrix, why):
        mod = load(monkeypatch, tmp_path)
        with pytest.raises(mod.Unexpandable, match=re.escape(why)):
            mod.expand_matrix(matrix)

    def test_a_value_of_the_same_type_still_matches(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        assert mod.expand_matrix({"py": [3, 4], "include": [{"py": 3, "x": "z"}],
                                  "exclude": [{"py": 4}]}) == [{"py": 3, "x": "z"}]


class TestMatrixKeyCase:
    def test_continue_on_error_reads_the_key_ignoring_case(self, tmp_path, monkeypatch, capsys):
        # GitHub makes these 3.15 legs advisory; reading `matrix.PYTHON` as a
        # missing key would have called them blocking and let one be required.
        workflow(tmp_path, "ci.yml", matrix_job(
            "t", "        python: [\"3.14\", \"3.15\"]\n",
            extra="    continue-on-error: ${{ matrix.PYTHON == '3.15' }}\n"))
        config(tmp_path, "t (3.14)\nt (3.15)\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "1 problem(s)" in err
        assert "'t (3.15)' is advisory" in err

    def test_a_name_reads_the_key_ignoring_case(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", matrix_job(
            "t", "        os: [ubuntu-latest]\n", extra="    name: t on ${{ matrix.OS }}\n"))
        config(tmp_path, "t on ubuntu-latest\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_keys_that_differ_only_in_case_are_refused(self, tmp_path, monkeypatch):
        mod = load(monkeypatch, tmp_path)
        with pytest.raises(mod.Unexpandable, match=re.escape(
                "matrix.python could be any of python, PYTHON, keys that differ only in case")):
            mod.leg_is_advisory("${{ matrix.python == '3' }}", {"python": "3", "PYTHON": "4"})


class TestYamlIsRequired:
    def test_missing_pyyaml_fails_closed(self, tmp_path, monkeypatch):
        import sys
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        mod = load(monkeypatch, tmp_path)
        monkeypatch.setitem(sys.modules, "yaml", None)
        with pytest.raises(SystemExit, match="PyYAML is not importable"):
            mod.main([])

    @pytest.mark.parametrize(("flag", "printed"), [
        ("--print-api", '"contexts": [\n      "lint"\n    ]'),
        ("--print-ruleset", '"context": "lint"'),
        ("--verify-remote", "--verify-remote skipped"),
    ])
    def test_the_modes_that_read_only_the_list_need_no_pyyaml(
            self, tmp_path, monkeypatch, capsys, flag, printed):
        # CONTRIBUTING.md and required-checks.txt document a bare
        # `python3 scripts/check_required_checks.py --print-api`.
        import sys
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        mod = load(monkeypatch, tmp_path)
        monkeypatch.setitem(sys.modules, "yaml", None)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        assert mod.main([flag]) == 0
        assert printed in capsys.readouterr().out

    def test_invalid_yaml_fails_closed(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: [unclosed\n")
        config(tmp_path, "lint\n")
        with pytest.raises(SystemExit, match=re.escape("ci.yml is not valid YAML")):
            load(monkeypatch, tmp_path).main([])

    def test_a_job_id_yaml_reads_as_a_boolean_fails_closed(self, tmp_path, monkeypatch):
        # PyYAML is YAML 1.1: an unquoted `on:` job id loads as True.
        workflow(tmp_path, "ci.yml", "  on:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "on\n")
        with pytest.raises(SystemExit, match=re.escape(
                "job id on in ci.yml is unquoted, and PyYAML loads it as True")):
            load(monkeypatch, tmp_path).main([])


class TestRefusesToPassVacuously:
    def test_no_workflow_files_is_an_error(self, tmp_path, monkeypatch):
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        config(tmp_path, "lint\n")
        with pytest.raises(SystemExit, match="no workflow files"):
            load(monkeypatch, tmp_path).main([])

    def test_parsing_zero_jobs_is_an_error_not_a_pass(self, tmp_path, monkeypatch):
        # If the parser stops matching, the gate must fail loudly rather than
        # report "no problems found".
        d = tmp_path / ".github" / "workflows"
        d.mkdir(parents=True)
        (d / "ci.yml").write_text("name: ci\non:\n  pull_request:\n", encoding="utf-8")
        config(tmp_path, "lint\n")
        with pytest.raises(SystemExit, match="parsed 0 jobs"):
            load(monkeypatch, tmp_path).main([])

    def test_a_jobs_key_with_nothing_under_it_is_zero_jobs(self, tmp_path, monkeypatch):
        # YAML reads `jobs:` with no body as null, not as a mapping of jobs.
        d = tmp_path / ".github" / "workflows"
        d.mkdir(parents=True)
        (d / "ci.yml").write_text("name: ci\non:\n  pull_request:\njobs:\n", encoding="utf-8")
        config(tmp_path, "lint\n")
        with pytest.raises(SystemExit, match="parsed 0 jobs"):
            load(monkeypatch, tmp_path).main([])

    def test_empty_config_is_an_error(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "# only comments\n\n")
        with pytest.raises(SystemExit, match="lists no checks"):
            load(monkeypatch, tmp_path).main([])

    def test_missing_config_is_an_error(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        with pytest.raises(SystemExit, match="missing"):
            load(monkeypatch, tmp_path).main([])


class TestPrintApi:
    def test_payload_requires_checks_but_not_reviews(self, tmp_path, monkeypatch, capsys):
        import json
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main(["--print-api"]) == 0
        out = capsys.readouterr().out
        payload = json.loads(out[out.index("{"):])
        assert payload["required_status_checks"]["contexts"] == ["lint"]
        assert payload["required_status_checks"]["strict"] is True
        # Reviews stay off on purpose: parallel loop/* branches self-merge, and
        # requiring a second reviewer would deadlock every one of them.
        assert payload["required_pull_request_reviews"] is None


class TestRulesetIsTheOtherHalf:
    """`main` is protected twice, and this gate only ever saw one of them.

    The classic branch protection and the repository ruleset are independent
    objects with independent lists. Applying `--print-api` updates the classic
    one and leaves the ruleset exactly as it was, which is how the ruleset came
    to be missing `bdd`, `evals` and `onnx-inference` while this script reported
    the config clean — it was comparing the file against the *workflows*, and
    the workflows were fine.

    The asymmetry is what made that expensive. Classic protection sets
    `enforce_admins: false`, so it does not bind the identity that merges here;
    the ruleset carries `bypass_actors: []`, so it binds everyone. The three
    checks absent from the ruleset were therefore the three nothing enforced.
    """

    def _mod(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        return load(monkeypatch, tmp_path)

    def test_drift_reports_missing_and_extra(self, tmp_path, monkeypatch):
        m = self._mod(tmp_path, monkeypatch)
        missing, extra = m.drift(["a", "b", "c"], ["b", "z"])
        assert missing == ["a", "c"] and extra == ["z"]

    def test_drift_ignores_order(self, tmp_path, monkeypatch):
        # GitHub returns contexts in its own order; a different sort is not drift.
        m = self._mod(tmp_path, monkeypatch)
        assert m.drift(["a", "b"], ["b", "a"]) == ([], [])

    def test_the_ruleset_rule_is_not_the_classic_payload(self, tmp_path, monkeypatch):
        # The two API shapes differ in ways a human retyping them gets wrong:
        # a ruleset names each context as an object carrying the producing app,
        # and spells `strict` differently. Pinning it here is what stops the
        # translation step being done from memory.
        m = self._mod(tmp_path, monkeypatch)
        rule = m.ruleset_rule(["lint", "bdd"])
        assert rule["type"] == "required_status_checks"
        p = rule["parameters"]
        assert p["strict_required_status_checks_policy"] is True
        assert p["required_status_checks"] == [
            {"context": "lint", "integration_id": m.ACTIONS_APP_ID},
            {"context": "bdd", "integration_id": m.ACTIONS_APP_ID},
        ]

    def test_ruleset_rule_names_github_actions_as_the_producer(self, tmp_path, monkeypatch):
        # Without integration_id any app could satisfy a check by name, which is
        # a weaker gate than the one required-checks.txt describes.
        m = self._mod(tmp_path, monkeypatch)
        assert m.ACTIONS_APP_ID == 15368

    def test_a_ruleset_with_no_status_check_rule_is_distinguishable(self, tmp_path, monkeypatch):
        # "requires nothing" and "requires a drifted list" are different faults
        # and get different messages; collapsing them to an empty list hides the
        # louder one.
        m = self._mod(tmp_path, monkeypatch)
        assert m.ruleset_contexts({"rules": [{"type": "deletion"}]}) == (False, [])
        has, ctx = m.ruleset_contexts({"rules": [
            {"type": "required_status_checks",
             "parameters": {"required_status_checks": [{"context": "lint"}]}}]})
        assert has is True and ctx == ["lint"]

    # ---- verify_remote, driven against a stubbed API ------------------------

    def _stub(self, m, monkeypatch, *, classic, ruleset_ctx, has_rule=True,
              enforcement="active", includes=("refs/heads/main",)):
        rules = [{"type": "deletion"}]
        if has_rule:
            rules.append({"type": "required_status_checks", "parameters": {
                "required_status_checks": [{"context": c} for c in ruleset_ctx]}})
        detail = {"id": 1, "name": "main", "enforcement": enforcement,
                  "conditions": {"ref_name": {"include": list(includes)}},
                  "rules": rules}

        def fake(path, token):
            if path.endswith("/protection"):
                return {"required_status_checks": {"contexts": list(classic)}}
            if path.endswith("/rulesets"):
                return [{"id": 1}]
            return detail
        monkeypatch.setattr(m, "_api", fake)

    def test_it_catches_the_real_regression(self, tmp_path, monkeypatch):
        # The exact production state: classic correct, ruleset short by three.
        m = self._mod(tmp_path, monkeypatch)
        want = ["lint", "bdd", "evals", "onnx-inference"]
        self._stub(m, monkeypatch, classic=want, ruleset_ctx=["lint"])
        problems = m.verify_remote(want, "t")
        assert len(problems) == 1
        assert "ruleset" in problems[0]
        for name in ("bdd", "evals", "onnx-inference"):
            assert name in problems[0]

    def test_it_stays_quiet_when_both_agree(self, tmp_path, monkeypatch):
        m = self._mod(tmp_path, monkeypatch)
        want = ["lint", "bdd"]
        self._stub(m, monkeypatch, classic=want, ruleset_ctx=list(reversed(want)))
        assert m.verify_remote(want, "t") == []

    def test_it_catches_classic_drift_too(self, tmp_path, monkeypatch):
        m = self._mod(tmp_path, monkeypatch)
        want = ["lint", "bdd"]
        self._stub(m, monkeypatch, classic=["lint"], ruleset_ctx=want)
        problems = m.verify_remote(want, "t")
        assert len(problems) == 1 and "classic" in problems[0]

    def test_a_ruleset_that_gates_nothing_is_loud(self, tmp_path, monkeypatch):
        m = self._mod(tmp_path, monkeypatch)
        want = ["lint"]
        self._stub(m, monkeypatch, classic=want, ruleset_ctx=[], has_rule=False)
        problems = m.verify_remote(want, "t")
        assert any("gates nothing" in p for p in problems)

    def test_no_active_ruleset_is_reported_rather_than_passing(self, tmp_path, monkeypatch):
        # Silence here would read as "the rulesets agree" — the exact shape of
        # invisibility this whole check exists to remove.
        m = self._mod(tmp_path, monkeypatch)
        want = ["lint"]
        self._stub(m, monkeypatch, classic=want, ruleset_ctx=want,
                   enforcement="disabled")
        assert any("no active ruleset" in p for p in m.verify_remote(want, "t"))

    def test_a_ruleset_for_another_branch_is_not_mistaken_for_main(self, tmp_path, monkeypatch):
        m = self._mod(tmp_path, monkeypatch)
        want = ["lint"]
        self._stub(m, monkeypatch, classic=want, ruleset_ctx=["something-else"],
                   includes=("refs/heads/release",))
        problems = m.verify_remote(want, "t")
        # It must not grade main against a release ruleset...
        assert not any("disagrees" in p and "ruleset" in p for p in problems)
        # ...but must still say main has no ruleset covering it.
        assert any("no active ruleset" in p for p in problems)

    def test_the_default_branch_alias_counts_as_main(self, tmp_path, monkeypatch):
        # GitHub writes `~DEFAULT_BRANCH` rather than a literal ref when the
        # ruleset was created through the UI's default-branch option.
        m = self._mod(tmp_path, monkeypatch)
        want = ["lint"]
        self._stub(m, monkeypatch, classic=want, ruleset_ctx=want,
                   includes=("~DEFAULT_BRANCH",))
        assert m.verify_remote(want, "t") == []

    def test_verify_remote_without_a_token_skips_rather_than_passes(
            self, tmp_path, monkeypatch, capsys):
        m = self._mod(tmp_path, monkeypatch)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        assert m.main(["--verify-remote"]) == 0
        assert "skipped" in capsys.readouterr().out

    def test_print_ruleset_emits_the_rule(self, tmp_path, monkeypatch, capsys):
        import json
        m = self._mod(tmp_path, monkeypatch)
        assert m.main(["--print-ruleset"]) == 0
        out = capsys.readouterr().out
        rule = json.loads(out[out.index("{"):])
        assert rule["parameters"]["required_status_checks"][0]["context"] == "lint"

    def test_print_api_now_says_it_is_only_half(self, tmp_path, monkeypatch, capsys):
        # The old output invited exactly the mistake that caused this: it read
        # as though applying it made protection correct.
        m = self._mod(tmp_path, monkeypatch)
        assert m.main(["--print-api"]) == 0
        assert "--print-ruleset" in capsys.readouterr().out


class TestRealRepo:
    def test_the_committed_config_matches_the_real_workflows(self):
        import subprocess
        import sys
        r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
