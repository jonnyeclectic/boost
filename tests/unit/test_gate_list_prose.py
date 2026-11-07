# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: every doc that lists `make check`'s gates lists the Makefile's.

The Makefile runs `lint eval evals test smoke mutation`. CLAUDE.md said five
and left out `evals`, the README said four and left out `lint` and `eval`,
and the PR template's checklist named five. Each was right once; nothing tied
it to the target, so the next gate added would be missing from all three.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

_WORDS = {4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _check_gates() -> list[str]:
    m = re.search(r"^check:([^\n]*)$", _read("Makefile"), re.M)
    assert m, "the Makefile has no `check:` target"
    return m.group(1).split()


def test_claude_md_lists_the_check_targets_in_order():
    m = re.search(r"make check\s+# == ([a-z ]+)$", _read("CLAUDE.md"), re.M)
    assert m, "CLAUDE.md no longer spells out what `make check` runs"
    assert m.group(1).split() == _check_gates()


def test_claude_md_gate_table_has_a_row_per_gate():
    text = _read("CLAUDE.md")
    gates = _check_gates()
    assert "It is %s gates" % _WORDS[len(gates)] in text
    rows = re.findall(r"^\| `([a-z]+)`\s+\|", text, re.M)
    assert [g for g in gates if g not in rows] == []


def test_readme_table_has_a_row_per_gate():
    text = _read("README.md")
    gates = _check_gates()
    assert "%s gates are enforced" % _WORDS[len(gates)].capitalize() in text
    rows = re.findall(r"^\| `make ([a-z]+)` \|", text, re.M)
    assert sorted(rows) == sorted(gates)


def _contributing_gates() -> str:
    text = _read("CONTRIBUTING.md")
    m = re.search(r"^## The gates \(CI runs all of these\)$(.*?)^## ",
                  text, re.M | re.S)
    assert m, "CONTRIBUTING.md lost its gate section"
    return m.group(1)


def test_contributing_lists_every_check_gate():
    # Its table named test, smoke and mutation and spelled lint out tool by
    # tool, but had no row for `eval` or `evals`, both of which `make check`
    # and CI run.
    section = _contributing_gates()
    gates = _check_gates()
    assert "`make check` runs %s of them" % _WORDS[len(gates)] in section
    rows = re.findall(r"^\| `make ([a-z-]+)` \|", section, re.M)
    assert [g for g in gates if g not in rows] == []


def test_contributing_rows_outside_check_are_required_in_ci():
    # The heading says CI runs all of these, so a row `make check` does not
    # run has to be a check CI requires, under the same name.
    required = {line.strip() for line in _read(".github/required-checks.txt")
                .splitlines() if line.strip() and not line.startswith("#")}
    rows = re.findall(r"^\| `make ([a-z-]+)` \|", _contributing_gates(), re.M)
    extra = [r for r in rows if r not in _check_gates()]
    assert extra, "CONTRIBUTING.md no longer names the CI-only gates"
    assert [r for r in extra if r not in required] == []


def test_pr_template_checklist_names_every_gate():
    m = re.search(r"`make check` passes locally \(([^)]*)\)",
                  _read(".github/PULL_REQUEST_TEMPLATE.md"))
    assert m, "the PR template no longer lists the gates"
    assert [g.strip() for g in m.group(1).split("·")] == _check_gates()
