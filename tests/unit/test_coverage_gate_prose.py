# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: everything that states the coverage gate agrees with the gate.

WHY THIS FILE EXISTS. `pyproject.toml` decides the gate (`fail_under`), and the
CI job summary restated it as a literal. The two disagreed for the whole life of
the 90% gate: the summary printed `gate: 80%`, so a run at 90.4% read as
comfortably clear when it was four tenths of a point from red. The summary is
the one place the number is read WITHOUT opening the log, which is exactly where
a wrong number does the most damage and is least likely to be checked.

Two halves, matching how the eval floors are pinned in `test_eval_corpus.py`:
the summary must DERIVE the threshold rather than restate it, and every place
that does spell a coverage percentage in prose must spell the current one.

Scope is deliberate. The scanned files are the ones a contributor or an auditor
reads as a statement of the rule in force. Roadmap cards under
`docs/roadmap/items/` are excluded: they are dated write-ups of one change, and
a card that measured a module at 89% is reporting history, not the gate.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# A percentage claimed as coverage. "80% changed-line" and "80% mutation" are
# different gates and deliberately do not match.
STATED = re.compile(r"(?<![\d.])(\d{2,3})\s*%\s+coverage\b")

# Every file that states the rule rather than recording a measurement.
AUTHORITATIVE = (
    ".github/workflows/ci.yml",
    "Makefile",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "README.md",
    "docs/openssf-badge.md",
    "docs/security-design.md",
)


@pytest.fixture(scope="module")
def fail_under() -> float:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["tool"]["coverage"]["report"]["fail_under"]


def test_the_gate_is_a_number_we_can_read(fail_under):
    """If this moves, nothing below can be checked against anything."""
    assert 0 < fail_under <= 100


@pytest.mark.parametrize("rel", AUTHORITATIVE)
def test_a_stated_coverage_percentage_is_the_real_one(rel, fail_under):
    path = ROOT / rel
    assert path.exists(), f"{rel} is in the list but not in the tree"
    text = path.read_text(encoding="utf-8")
    stated = {int(m.group(1)) for m in STATED.finditer(text)}
    wrong = sorted(p for p in stated if p != fail_under)
    assert not wrong, (
        f"{rel} states {wrong} as the coverage gate; pyproject.toml says "
        f"{fail_under}"
    )


def test_the_ci_summary_reads_the_gate_instead_of_restating_it():
    """The literal is what drifted, so the literal is what must not come back."""
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    line = next(
        (ln for ln in ci.splitlines() if "**Coverage:**" in ln),
        None,
    )
    assert line is not None, "the job summary no longer prints a coverage line"
    assert "${GATE}" in line, f"the gate is hard-coded again: {line.strip()}"
    assert re.search(r"gate:\s*\d", line) is None, line.strip()
    assert "fail_under" in ci, "nothing in ci.yml reads the gate from pyproject"


def test_the_derivation_returns_what_pyproject_holds(fail_under, monkeypatch):
    """Run the shell step's own expression, so a typo in it fails here.

    The step runs with the checkout as its working directory and its expression
    opens `pyproject.toml` relatively, so reproduce that rather than inherit
    whatever directory pytest was started from.
    """
    monkeypatch.chdir(ROOT)
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    m = re.search(r"GATE=\$\(\"\$VENV_BIN/python\" -c \"(.+?)\"\)", ci)
    assert m, "the summary's GATE derivation is not in the shape this pins"
    ns: dict[str, object] = {}
    exec(  # noqa: S102 - the expression under test is the point
        m.group(1).replace("print(", "_out = ("),
        {"tomllib": tomllib},
        ns,
    )
    assert ns["_out"] == fail_under
