# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the mutation survivor ledger (docs/superpowers/specs/2026-11-24-mutation-survivor-ledger.md).

The property everything here protects: carrying a survivor never adds a kill.
A carried row is merged in as the constant ``CARRIED_EXIT``, which mutmut reads
as "survived", so it adds nothing to ``killed`` and one to the denominator,
whatever the ledger says, however old it is and whoever wrote it. The other
tests pin the guards around that: the gate re-checks every carried row, the
writer carries only survived and timeout, the planner falls back to the plain
plan on any doubt, and the reader uses no ledger past a red whole-codebase run.

The tests that need mutmut use the ``needs_mutmut`` fixture: they skip in the
``tests`` cells (no mutmut there) and run in ``mutation-plan``'s
``BOOST_REQUIRE_MUTMUT`` step, which lists this file, where a skip is an error.
"""
from __future__ import annotations

import importlib.util
import json
import os
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mg = _load("mutation_gate_for_ledger", "mutation_gate.py")
ms = _load("mutation_shards_for_ledger", "mutation_shards.py")


@pytest.fixture
def needs_mutmut():
    """Skip without mutmut, except under BOOST_REQUIRE_MUTMUT=1 (see the module docstring)."""
    if os.environ.get("BOOST_REQUIRE_MUTMUT") == "1":
        import mutmut

        return mutmut
    return pytest.importorskip("mutmut")


# --------------------------------------------------------------------------
# the constant, and the property it buys
# --------------------------------------------------------------------------

def test_mutmut_reads_the_carried_exit_as_survived(needs_mutmut):
    # I1: the injected code is a constant, and the installed mutmut's own
    # table says what it means.
    from mutmut.stats import status_by_exit_code

    assert ms.CARRIED_EXIT == 0
    assert status_by_exit_code[ms.CARRIED_EXIT] == "survived"
    assert mg._status_of(ms.CARRIED_EXIT) == "survived"


#: mutmut 3.8.x's exit-code table (mutmut/stats.py), as the gate scores it:
#: killed is 1 and 3; skipped (34) leaves the denominator; everything else,
#: including any unknown code ("suspicious"), counts against the score.
_TABLE = {1: "killed", 3: "killed", 0: "survived", 5: "no tests", 33: "no tests",
          34: "skipped", 35: "suspicious", 36: "timeout", 37: "caught by type check",
          -24: "timeout", 24: "timeout", 152: "timeout", 255: "timeout",
          -11: "segfault", -9: "segfault", 2: "check was interrupted by user", 99: "suspicious"}


def _count(codes: dict[str, int]) -> tuple[int, int]:
    killed = sum(1 for c in codes.values() if _TABLE[c] == "killed")
    denominator = sum(1 for c in codes.values() if _TABLE[c] != "skipped")
    return killed, denominator


@pytest.mark.parametrize("seed", range(40))
def test_carrying_never_adds_a_kill(seed):
    # Whatever a plain run measured, and whichever subset is carried, the
    # carried run never has more kills, never a smaller denominator, and so
    # never a higher score. It is a property of the merge's arithmetic only:
    # it says nothing about what the rows that WERE run would measure.
    rng = random.Random(seed)  # noqa: S311  seeded test data, not a secret
    plain = {"k%d" % i: rng.choice(list(_TABLE)) for i in range(rng.randint(1, 60))}
    carried = {k for k in plain if rng.random() < 0.4}
    ledgered = {k: (ms.CARRIED_EXIT if k in carried else c) for k, c in plain.items()}
    pk, pd = _count(plain)
    lk, ld = _count(ledgered)
    assert lk <= pk
    assert ld >= pd
    if ld and pd:
        assert lk / ld <= pk / pd
    # the identities the design states
    assert lk == pk - sum(1 for k in carried if _TABLE[plain[k]] == "killed")
    assert ld == pd + sum(1 for k in carried if _TABLE[plain[k]] == "skipped")


# --------------------------------------------------------------------------
# the gate
# --------------------------------------------------------------------------

_KEYS = ["boost_cli.core.a.x_f__mutmut_%d" % n for n in range(1, 11)]
_LEDGER = {"used": True, "run_id": 45290191649, "event": "schedule",
           "created_at": "2026-11-25T09:31:02Z", "head_sha": "a" * 40, "age_hours": 18.4,
           "carried_survived": 2, "carried_timeouts": 1}


def _gate_tree(tmp_path, codes, *, killed, total, carried=None, ledger=None):
    mutants = tmp_path / "mutants"
    core = mutants / "boost_cli" / "core"
    core.mkdir(parents=True, exist_ok=True)
    (core / "a.py.meta").write_text(json.dumps({"exit_code_by_key": codes}), encoding="utf-8")
    (mutants / mg.STATS_NAME).write_text(json.dumps(
        {"killed": killed, "total": total, "skipped": 0, "survived": total - killed}),
        encoding="utf-8")
    full = {"shards": [["boost_cli.core.a.*"]], "mutants": None}
    if carried is not None:
        full["carried"] = carried
        full["ledger"] = dict(_LEDGER if ledger is None else ledger)
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"gate_set": "full", "sets": {"full": full}}), encoding="utf-8")
    return mutants, plan


@pytest.fixture
def gate(monkeypatch, tmp_path):
    monkeypatch.setattr(mg, "sh", lambda *a: 0)
    monkeypatch.setattr(mg, "_status_of", lambda code: _TABLE.get(code, "suspicious"))
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    def run(mutants, plan, *extra):
        argv = ["--mutants", str(mutants), *extra]
        if plan is not None:
            argv += ["--plan", str(plan)]
        return mg.main(argv)

    run.summary = summary
    return run


def test_a_plain_plan_gates_exactly_as_before(gate, tmp_path, capsys):
    codes = dict.fromkeys(_KEYS, 1)
    mutants, plan = _gate_tree(tmp_path, codes, killed=10, total=10)
    assert gate(mutants, plan) == 0
    out = capsys.readouterr().out
    assert "ledgered" not in out and "PASS" in out
    # A plain run writes nothing new to the summary.
    assert not gate.summary.exists()


def test_a_ledgered_pass_says_where_the_carried_rows_came_from(gate, tmp_path, capsys):
    codes = {k: (0 if i < 3 else 1) for i, k in enumerate(_KEYS)}
    mutants, plan = _gate_tree(tmp_path, codes, killed=9, total=10, carried=_KEYS[:1])
    assert gate(mutants, plan) == 0
    out = capsys.readouterr().out
    assert ("mutation gate: ledgered — 1 of 10 mutants carried as survived (2 survived and "
            "1 timeout on record) from whole-codebase run 45290191649 (schedule, "
            "2026-11-25T09:31:02Z, 18 h old, commit aaaaaaaaaaaa); not re-run on this commit"
            in out)
    # Provenance before the score, and both in the summary.
    assert out.index("ledgered") < out.index("killed (")
    summary = gate.summary.read_text(encoding="utf-8")
    assert "ledgered" in summary and "PASS" in summary


@pytest.mark.parametrize("code", [1, 3, 33, 36, None])
def test_a_carried_row_that_is_not_the_constant_is_exit_2(gate, tmp_path, capsys, code):
    # I4: a carried row merged as anything but CARRIED_EXIT -- a kill above
    # all -- means the merge did not do what the plan said.
    codes = dict.fromkeys(_KEYS, 1)
    codes[_KEYS[0]] = code
    mutants, plan = _gate_tree(tmp_path, codes, killed=10, total=10, carried=_KEYS[:1])
    assert gate(mutants, plan) == 2
    assert "are not exactly 0" in capsys.readouterr().out


def test_a_carried_row_missing_from_the_merge_is_exit_2(gate, tmp_path, capsys):
    codes = dict.fromkeys(_KEYS, 1)
    mutants, plan = _gate_tree(tmp_path, codes, killed=10, total=10,
                               carried=["boost_cli.core.a.x_gone__mutmut_1"])
    assert gate(mutants, plan) == 2
    assert "missing from the merged results" in capsys.readouterr().out


def test_a_mutmut_that_does_not_read_0_as_survived_is_exit_2(gate, tmp_path, capsys,
                                                             monkeypatch):
    monkeypatch.setattr(mg, "_status_of", lambda code: "killed")
    codes = {k: (0 if i == 0 else 1) for i, k in enumerate(_KEYS)}
    mutants, plan = _gate_tree(tmp_path, codes, killed=9, total=10, carried=_KEYS[:1])
    assert gate(mutants, plan) == 2
    assert "reads exit code 0 as 'killed'" in capsys.readouterr().out


def test_a_ledgered_fail_says_what_it_does_and_does_not_know(gate, tmp_path, capsys):
    codes = {k: (0 if i < 4 else 1) for i, k in enumerate(_KEYS)}
    mutants, plan = _gate_tree(tmp_path, codes, killed=6, total=10, carried=_KEYS[:3])
    assert gate(mutants, plan) == 1
    out = capsys.readouterr().out
    assert "FAIL — 60.0% < 80.0% minimum" in out
    assert "this FAIL is ledgered: 3 carried survivors were not re-run" in out
    assert "would score 90.0%" in out and "not a forecast of a plain run" in out
    assert "`mutation-no-ledger`" in out and "Re-run all jobs" in out
    assert "MUTATION_LEDGER" in out
    # Claims the review struck: a ledgered score bounds nothing a plain run
    # measures, so the gate never calls a red conclusive.
    assert "conclusive" not in out and "must lie in" not in out
    assert "this FAIL is ledgered" in gate.summary.read_text(encoding="utf-8")


def test_a_plain_fail_prints_no_ledger_advice(gate, tmp_path, capsys):
    codes = {k: (0 if i < 4 else 1) for i, k in enumerate(_KEYS)}
    mutants, plan = _gate_tree(tmp_path, codes, killed=6, total=10)
    assert gate(mutants, plan) == 1
    assert "ledgered" not in capsys.readouterr().out


@pytest.mark.parametrize("body", ["{not json", json.dumps(
    {"sets": {"full": {"shards": [], "carried": []}}})])
def test_a_plan_the_gate_cannot_read_is_exit_2(gate, tmp_path, body):
    mutants, plan = _gate_tree(tmp_path, dict.fromkeys(_KEYS, 1), killed=10, total=10)
    plan.write_text(body, encoding="utf-8")
    assert gate(mutants, plan) == 2


def test_provenance_never_echoes_a_string_it_did_not_validate(gate, tmp_path, capsys):
    hostile = {"run_id": "1; ::error::x", "event": "::warning::y",
               "created_at": "\n::error::z", "head_sha": "::add-mask::q",
               "age_hours": "1e9", "carried_survived": True, "carried_timeouts": 1}
    codes = {k: (0 if i == 0 else 1) for i, k in enumerate(_KEYS)}
    mutants, plan = _gate_tree(tmp_path, codes, killed=9, total=10, carried=_KEYS[:1],
                               ledger=hostile)
    assert gate(mutants, plan) == 0
    out = capsys.readouterr().out
    assert "::" not in out
    assert "whole-codebase run ? (?, ?, ? h old, commit ?)" in out
