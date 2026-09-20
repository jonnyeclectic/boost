# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The performance gate must decide about the page, not about runner timing.

`lighthouse` asserts `categories:*` floors on the two hand-authored pages. It
is advisory rather than required, which is how it drifted into a state where
the same `docs/roadmap.html` — byte-identical, sha256 42bdc4f7…, 784,560 bytes
— failed at one commit and passed at the next 60 seconds later.

Two things make it a decision again, and both are pinned here because both are
one careless edit away from being lost:

* **`aggregationMethod: median-run`.** Without it the worst of three runs
  decides, which on a noisy runner is a lottery with three tickets.
* **A floor under the worst median the page actually produces.** Measured
  2026-09-20 over the artifacts of four consecutive jobs (12 runs):
  roadmap.html scores min 0.78, median 0.83, max 0.94, with per-job medians of
  0.80, 0.82, 0.84 and 0.89 — so the old 0.80 floor WAS the worst observed
  median, a zero-margin gate. index.html measures 0.98/1.00/1.00 against its
  0.90 floor and needs no change.

Raising a floor is allowed; raising it without re-measuring is what these
tests stop. The recorded numbers below move in the same commit as the floor,
or the test fails.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RC = ROOT / ".lighthouserc.json"
WORKFLOW = ROOT / ".github" / "workflows" / "lighthouse.yml"
CI = ROOT / ".github" / "workflows" / "ci.yml"

#: Worst per-job MEDIAN observed for each page, and the date it was measured.
#: A floor must sit under this, not on it. Regenerate by downloading the
#: `lighthouse-results` artifact of a few jobs and taking the median of each
#: job's three `categories.performance.score` values.
MEASURED_WORST_MEDIAN = {"index": 0.98, "roadmap": 0.80}
#: How much margin the floor must keep under that worst median. 0.05 is one
#: runner-load sample's worth on this page: the observed spread between a job's
#: worst and best single run is 0.04-0.14.
MARGIN = 0.05


def _matrix() -> list[dict]:
    return json.loads(RC.read_text(encoding="utf-8"))["ci"]["assert"]["assertMatrix"]


def _page(entry: dict) -> str:
    return re.sub(r"[^a-z]", "", entry["matchingUrlPattern"].replace("html", ""))


def test_both_audited_pages_are_in_the_matrix() -> None:
    assert {_page(e) for e in _matrix()} == {"index", "roadmap"}


@pytest.mark.parametrize("entry", _matrix(), ids=_page)
def test_every_page_aggregates_on_the_median_run(entry: dict) -> None:
    """The worst of three runs is a lottery; the median is a measurement."""
    assert entry.get("aggregationMethod") == "median-run", entry


@pytest.mark.parametrize("entry", _matrix(), ids=_page)
def test_every_page_floors_all_four_categories(entry: dict) -> None:
    # A page that quietly drops a category keeps a green tick that means less
    # than it did, which is the same defect as a floor nothing clears.
    assert set(entry["assertions"]) == {
        "categories:performance", "categories:accessibility",
        "categories:best-practices", "categories:seo"}


@pytest.mark.parametrize("entry", _matrix(), ids=_page)
def test_the_performance_floor_keeps_margin_under_the_measured_median(
        entry: dict) -> None:
    floor = entry["assertions"]["categories:performance"][1]["minScore"]
    worst = MEASURED_WORST_MEDIAN[_page(entry)]
    assert floor <= worst - MARGIN, (
        "%s floors performance at %.2f against a worst observed median of "
        "%.2f — raise the floor only with a fresh measurement, and move "
        "MEASURED_WORST_MEDIAN in the same commit"
        % (_page(entry), floor, worst))


def test_the_recorded_measurement_is_also_in_the_workflow() -> None:
    """The rationale lives beside the gate, the way every floor above it does."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "median 0.83" in text and "0.80, 0.82, 0.84 and 0.89" in text


def test_growth_is_bounded_by_a_required_check() -> None:
    """Lowering the perf floor is only honest while growth is gated elsewhere.

    `page_budget.py` is deterministic, pure stdlib and runs in the REQUIRED
    lint job, so the thing eating the margin trips a check that cannot flake —
    which is what makes a loose, non-flaking perf floor the right trade rather
    than a retreat.
    """
    assert "page_budget.py" in CI.read_text(encoding="utf-8")
    import subprocess
    rc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "page_budget.py")],
        capture_output=True, text=True, cwd=ROOT)
    assert rc.returncode == 0, rc.stdout + rc.stderr
