# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Coverage is measured once, in ``tests (ubuntu-latest, 3.12)``, and reused.

The suite ran under coverage in all twelve ``tests`` cells and then a
thirteenth time, end to end, in ``patch-coverage`` — only to produce the
``coverage.xml`` the ubuntu-3.12 cell had just thrown away. Tracing is the
expensive part on Windows, where the cells were the critical path, so the
matrix now runs ``-n auto`` everywhere, measures in one cell, publishes that
cell's report as the ``coverage-report`` artifact, and ``patch-coverage``
downloads it instead of re-running anything.

The failure each assertion guards against is a *quiet* one: a second suite
run creeping back into ``patch-coverage``; an upload that runs after a red
test step and hands diff-cover a partial report; a ``needs`` that lets a
failed ``tests`` cell skip the required ``patch-coverage`` check into green;
and ``-n`` in pytest's addopts, which mutmut would inherit.
"""

from __future__ import annotations

import shlex
import tomllib
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT = ROOT / "pyproject.toml"
CELL = "matrix.os == 'ubuntu-latest' && matrix.python == '3.12'"


def jobs() -> dict:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]


def _test_step() -> dict:
    steps = [s for s in jobs()["tests"]["steps"]
             if s.get("name", "").startswith("unit + functional")]
    assert len(steps) == 1, "expected one 'unit + functional' step in tests"
    return steps[0]


def step_run() -> str:
    return _test_step()["run"]


def cov_condition() -> str:
    """The expression that decides whether the test step measures coverage."""
    return " ".join(str(v) for v in (_test_step().get("env") or {}).values())


def _upload_step() -> dict:
    steps = [s for s in jobs()["tests"]["steps"]
             if "upload-artifact" in s.get("uses", "")
             and (s.get("with") or {}).get("name") == "coverage-report"]
    assert len(steps) == 1, "expected one coverage-report upload in tests"
    return steps[0]


def test_only_the_ubuntu_312_cell_measures_coverage():
    run = step_run()
    assert "-n auto" in run
    assert "--cov" in run and CELL in cov_condition()
    # Every report the two consumers read: json for the summary line and the
    # badge, xml for diff-cover and Codecov.
    for flag in ("--cov=boost_cli", "--cov-report=json", "--cov-report=xml"):
        assert flag in run


def test_the_cell_publishes_its_report_only_when_the_suite_passed():
    step = _upload_step()
    cond = step.get("if", "")
    assert CELL in cond
    # The default `success()` is the point: a red test step must leave no
    # artifact, so `patch-coverage` fails on the missing download instead of
    # gating a diff against the partial report of a suite that died midway.
    assert "always()" not in cond and "failure()" not in cond
    with_ = step["with"]
    assert with_["if-no-files-found"] == "error"
    assert int(with_["retention-days"]) == 14
    assert {"coverage.xml", "coverage.json"} <= set(str(with_["path"]).split())


def test_patch_coverage_reuses_the_cells_report():
    job = jobs()["patch-coverage"]
    assert "tests" in job["needs"]
    assert job["if"].startswith("always()") and "pull_request" in job["if"]
    assert not any("pytest" in s.get("run", "") for s in job["steps"])
    dl = [s for s in job["steps"] if "download-artifact" in s.get("uses", "")]
    assert dl and dl[0]["with"]["name"] == "coverage-report"
    # A missing artifact must fail the job, never be tolerated past.
    assert not dl[0].get("continue-on-error")


def test_pytest_addopts_never_parallelise():
    ini = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    addopts = ini["tool"]["pytest"]["ini_options"].get("addopts", "")
    args = shlex.split(addopts if isinstance(addopts, str) else " ".join(addopts))
    assert not any(a == "-n" or a.startswith(("-n", "--numprocesses")) for a in args)
