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


@pytest.mark.parametrize("killed, rc", [(10, 0), (8, 0), (7, 1), (0, 1)])
def test_a_plain_plan_gates_byte_for_byte_as_main_gated_without_one(gate, tmp_path, capsys,
                                                                   killed, rc):
    # MUTATION_LEDGER unset: every plan is plain, and `--plan` must change
    # nothing main's `mutation_gate.py --min 80` printed, returned or wrote --
    # whatever shape the plain plan reaching it has.
    codes = {k: (1 if i < killed else 0) for i, k in enumerate(_KEYS)}
    mutants, plan = _gate_tree(tmp_path, codes, killed=killed, total=10)
    assert gate(mutants, None) == rc
    main_out = capsys.readouterr().out
    assert not gate.summary.exists()
    body = json.loads(plan.read_text(encoding="utf-8"))
    full = body["sets"]["full"]
    shapes = [body, {**body, "ledger_eligible": True}, {**body, "ledger_eligible": False},
              {**body, "sets": {"full": full, "diff": {"shards": [["n"]]}}},
              {**body, "advisory": ["diff"], "sets": {"full": full, "diff": {"shards": [["n"]]}}}]
    for shape in shapes:
        plan.write_text(json.dumps(shape), encoding="utf-8")
        assert gate(mutants, plan) == rc, shape
        assert capsys.readouterr().out == main_out, shape
        assert not gate.summary.exists(), shape


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


# --------------------------------------------------------------------------
# a small world: a source tree, its mutants' .meta, a plain plan and a ledger
# --------------------------------------------------------------------------

ml = _load("mutation_ledger_for_tests", "mutation_ledger.py")

from datetime import UTC, datetime, timedelta  # noqa: E402

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
KEY = {"mutmut": "3.8.1", "libcst": "1.9.0", "python": "3.14", "config": "c" * 64}
DIGEST = "d" * 64
FILES = ("a.py", "b.py", "c.py", "d.py", "e.py", "f.py")
WRITE_ENV = {"GITHUB_EVENT_NAME": "schedule", "GITHUB_REF": "refs/heads/main",
             "MUTATION_LEDGER": "write,pull_request,push", "GITHUB_RUN_ID": "4242",
             "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "e" * 40}
PR_ENV = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_RUN_ATTEMPT": "1",
          "MUTATION_LEDGER": "write,pull_request"}


def _status(code):
    return _TABLE.get(code, "suspicious")


def _meta_of(rel: str, nfuncs: int = 4, per: int = 6) -> dict:
    module = ml.module_of(rel)
    codes, durations, hashes = {}, {}, {}
    for f in range(nfuncs):
        mangled = "x_f%d" % f
        hashes[mangled] = ("%s%02d" % (rel[0], f)).encode().hex()[:12].ljust(12, "0")
        for n in range(1, per + 1):
            key = "%s.%s__mutmut_%d" % (module, mangled, n)
            # survivors at 2 and 5 in even functions, a timeout at 6 in f1,
            # one untested mutant, every other one killed
            code = (0 if f % 2 == 0 and n in (2, 5) else 36 if f == 1 and n == 6
                    else 33 if f == 3 and n == 1 else 1)
            codes[key] = code
            if code != 33:
                durations[key] = {0: 2.0, 36: 10.0}.get(code, 0.5)
    return {"codes": codes, "hashes": hashes, "durations": durations}


def _write_meta(mutants: Path, meta: dict, *, none_codes: bool = False) -> None:
    core = mutants / "boost_cli" / "core"
    for rel, data in meta.items():
        dest = core / (rel + ".meta")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps({
            "exit_code_by_key": (dict.fromkeys(data["codes"]) if none_codes else data["codes"]),
            "hash_by_function_name": data["hashes"],
            "durations_by_key": {} if none_codes else data["durations"]}), encoding="utf-8")


class World:
    def __init__(self, tmp_path: Path, shards: int = 3):
        self.root = tmp_path / "repo"
        core = self.root / "boost_cli" / "core"
        core.mkdir(parents=True)
        for i, rel in enumerate(FILES):
            (core / rel).write_text("".join("x = %d\n" % n for n in range(10 + 5 * i)),
                                    encoding="utf-8")
        (core / "__init__.py").write_text("", encoding="utf-8")
        self.meta = {rel: _meta_of(rel) for rel in FILES}
        self.mutants = tmp_path / "mutants"
        # the planner's stats run: every key, every hash, no verdicts
        _write_meta(self.mutants, self.meta, none_codes=True)
        self.shards = shards
        self.plan_path = tmp_path / "plan.json"
        self.ledger_path = tmp_path / "ledger.json"
        self.write_plain_plan()
        self.ledger = ml.build(self.meta, self.plan(), WRITE_ENV, NOW - timedelta(hours=6),
                               _status)
        self.ledger_path.write_text(json.dumps(self.ledger), encoding="utf-8")

    def write_plain_plan(self, **extra) -> None:
        bins = ms.pack(self.root, self.shards)
        plan = {"gate_set": "full", "reasons": ["test"], "ledger_eligible": True,
                "sets": {"full": {"shards": [ms.patterns_for_bin(self.root, b) for b in bins],
                                  "mutants": None}},
                "generator": {"key": KEY, "machinery": DIGEST}, **extra}
        self.plan_path.write_text(json.dumps(plan), encoding="utf-8")

    def plan(self) -> dict:
        return json.loads(self.plan_path.read_text(encoding="utf-8"))

    def apply(self, plan=None, *, env=None, run_id="4242", key=None, machinery=None,
              max_names=1500, now=NOW, ledger_path="default"):
        return ml.apply(plan if plan is not None else self.plan(), root=self.root,
                        ledger_path=self.ledger_path if ledger_path == "default" else ledger_path,
                        run_id=run_id, mutants=self.mutants, env=env or PR_ENV, now=now,
                        key=key or KEY, machinery=machinery or DIGEST, max_names=max_names)

    def keys(self) -> list[str]:
        return sorted(k for d in self.meta.values() for k in d["codes"])

    def survivors(self) -> set[str]:
        return {k for d in self.meta.values() for k, c in d["codes"].items()
                if _status(c) in ("survived", "timeout")}


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


# --------------------------------------------------------------------------
# write
# --------------------------------------------------------------------------

def test_the_writer_carries_only_survived_and_timeout(world):
    ledger = world.ledger
    assert ledger["kind"] == ml.KIND and ledger["schema"] == ml.SCHEMA
    assert ledger["source"]["run_id"] == 4242 and ledger["source"]["event"] == "schedule"
    assert ledger["key"] == KEY and ledger["machinery"] == DIGEST
    a0 = ledger["functions"]["boost_cli.core.a.x_f0"]
    assert (a0["survived"], a0["timeout"], a0["mutants"]) == ([2, 5], [], 6)
    assert a0["ms_carried"] == 4000 and a0["ms_rerun"] == 2000
    a1 = ledger["functions"]["boost_cli.core.a.x_f1"]
    assert (a1["survived"], a1["timeout"]) == ([], [6])
    # killed, no tests: never carried
    a3 = ledger["functions"]["boost_cli.core.a.x_f3"]
    assert (a3["survived"], a3["timeout"]) == ([], [])
    carried = {"%s__mutmut_%d" % (q, n) for q, f in ledger["functions"].items()
               for n in f["survived"] + f["timeout"]}
    assert carried == world.survivors()


@pytest.mark.parametrize("change, said", [
    ({"GITHUB_EVENT_NAME": "push"}, "only a schedule or workflow_dispatch run"),
    ({"GITHUB_EVENT_NAME": "pull_request"}, "only a schedule or workflow_dispatch run"),
    ({"GITHUB_REF": "refs/heads/feature"}, "only a run on main"),
    ({"MUTATION_LEDGER": "pull_request,push"}, "does not name write"),
    ({"MUTATION_LEDGER": ""}, "does not name write"),
])
def test_the_writer_refuses_a_run_that_may_not_write(world, change, said):
    with pytest.raises(ml.LedgerError, match=said):
        ml.build(world.meta, world.plan(), {**WRITE_ENV, **change}, NOW, _status)


def test_the_writer_refuses_a_ledgered_plan_and_an_unstamped_one(world):
    plan = world.plan()
    plan["sets"]["full"]["carried"] = ["boost_cli.core.a.x_f0__mutmut_2"]
    with pytest.raises(ml.LedgerError, match="not a plain full plan"):
        ml.build(world.meta, plan, WRITE_ENV, NOW, _status)
    plan = world.plan()
    del plan["generator"]
    with pytest.raises(ml.LedgerError, match="no generator stamp"):
        ml.build(world.meta, plan, WRITE_ENV, NOW, _status)


def test_the_writer_refuses_an_unrun_row(world):
    meta = json.loads(json.dumps(world.meta))
    meta["a.py"]["codes"]["boost_cli.core.a.x_f0__mutmut_1"] = None
    with pytest.raises(ml.LedgerError, match="unrun"):
        ml.build(meta, world.plan(), WRITE_ENV, NOW, _status)


# --------------------------------------------------------------------------
# apply: the ledgered planner
# --------------------------------------------------------------------------

def _covered(plan: dict, keys: list[str]) -> dict[str, int]:
    import fnmatch

    seen: dict[str, int] = {}
    for shard in plan["sets"]["full"]["shards"]:
        for k in keys:
            if any(fnmatch.fnmatchcase(k, s) for s in shard):
                seen[k] = seen.get(k, 0) + 1
    for k in plan["sets"]["full"]["carried"]:
        seen[k] = seen.get(k, 0) + 1
    return seen


def test_a_ledgered_plan_carries_the_survivors_and_runs_everything_else(world):
    plan = world.apply()
    assert plan["ledger"] == {"used": True}
    full = plan["sets"]["full"]
    assert set(full["carried"]) == world.survivors()
    assert full["mutants"] == len(world.keys())
    assert len(full["shards"]) == world.shards and all(full["shards"])
    # every generated key exactly once, by mutmut's own matching (fnmatch)
    seen = _covered(plan, world.keys())
    assert seen == dict.fromkeys(world.keys(), 1)
    assert full["ledger"]["run_id"] == 4242 and full["ledger"]["age_hours"] == 6.0
    assert full["ledger"]["carried"] == len(world.survivors())
    assert plan["reasons"][-1].startswith("ledgered: %d survivors" % len(world.survivors()))


def test_every_ledgered_shard_has_an_anchor(world):
    # A shard of function patterns alone selects no clean-run tests and pays
    # the whole suite.
    full = world.apply()["sets"]["full"]
    for shard in full["shards"]:
        assert any("*" not in s or (s.endswith(".*") and "__mutmut_" not in s)
                   for s in shard), shard


def test_a_ledgered_plan_merges_through_the_real_merge(world, tmp_path, capsys):
    plan = world.apply()
    full = plan["sets"]["full"]
    ml.simulate_shards(world.meta, full["shards"], tmp_path / "shards")
    world.plan_path.write_text(json.dumps(plan), encoding="utf-8")
    import argparse

    args = argparse.Namespace(root=str(world.root), shards=world.shards,
                              into=str(tmp_path / "merged"), source=str(tmp_path / "shards"),
                              prefix="mutation-full-shard-", plan=str(world.plan_path),
                              set="full")
    assert ms.cmd_merge(args) == 0, capsys.readouterr().out
    got = {k: c for d in ml.read_meta(tmp_path / "merged").values() for k, c in d["codes"].items()}
    for key, code in got.items():
        want = ms.CARRIED_EXIT if key in world.survivors() else world.meta[
            ml.ms.selector_file(key)]["codes"][key]
        assert code == want, key


def test_a_ledgered_plan_reaches_the_gate_through_the_shards_own_commands(world, tmp_path,
                                                                         gate, capsys):
    # End to end through every command a ledgered run's plan passes: the
    # planner's `matrix`, each shard's `patterns` (the argv file mutmut gets),
    # mutmut's filter over that argv, the real `merge --plan`, `gate --plan`.
    # The self-check skips the first two; a planner bug they would catch must
    # show here, not on the first ledgered PR.
    import contextlib
    import fnmatch
    import io

    mp = _load("mutation_plan_for_ledger_tests", "mutation_plan.py")
    plan = world.apply()
    world.plan_path.write_text(json.dumps(plan), encoding="utf-8")

    def cli(*argv: str) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            assert mp.main(list(argv)) == 0, argv
        return out.getvalue()

    entries = json.loads(cli("matrix", "--plan", str(world.plan_path)))
    assert entries == [{"set": "full", "index": i} for i in range(world.shards)]
    assert json.loads(cli("matrix", "--plan", str(world.plan_path), "--advisory")) == []
    argvs = []
    for entry in entries:
        args = tmp_path / ("args-%d" % entry["index"])
        cli("patterns", "--plan", str(world.plan_path), "--set", "full",
            "--index", str(entry["index"]), "--out", str(args))
        argv = [a.decode("utf-8") for a in args.read_bytes().split(b"\0")[:-1]]
        assert argv == plan["sets"]["full"]["shards"][entry["index"]]
        argvs.append(argv)
    # What mutmut runs, read by its own filter: every key outside the carried
    # list in exactly one shard, and no carried key in any.
    every = world.keys()
    ran: dict[str, int] = {}
    for argv in argvs:
        for k in every:
            if any(fnmatch.fnmatchcase(k, s) for s in argv):
                ran[k] = ran.get(k, 0) + 1
    assert ran == dict.fromkeys(sorted(set(every) - world.survivors()), 1)

    ml.simulate_shards(world.meta, argvs, tmp_path / "shards")
    import argparse

    merged = tmp_path / "merged"
    assert ms.cmd_merge(argparse.Namespace(
        root=str(world.root), shards=world.shards, into=str(merged),
        source=str(tmp_path / "shards"), prefix="mutation-full-shard-",
        plan=str(world.plan_path), set="full")) == 0, capsys.readouterr().out
    codes = mg.merged_codes(merged)
    killed, denominator = _count(codes)
    # The world's survivors are its only carried rows, so the score is the
    # plain run's to the mutant.
    assert (killed, denominator) == _count({k: c for d in world.meta.values()
                                            for k, c in d["codes"].items()})
    (merged / mg.STATS_NAME).write_text(json.dumps(
        {"killed": killed, "total": denominator, "skipped": 0}), encoding="utf-8")
    capsys.readouterr()
    assert gate(merged, world.plan_path) == (0 if 100.0 * killed / denominator >= 80 else 1)
    out = capsys.readouterr().out
    assert "mutation gate: ledgered — %d of %d mutants carried as survived" % (
        len(world.survivors()), len(world.keys())) in out


def _unchanged(world, plan) -> None:
    assert plan["ledger"]["used"] is False
    assert plan["reasons"][-1].startswith("ledger not used: ")
    assert plan["sets"]["full"] == world.plan()["sets"]["full"]


@pytest.mark.parametrize("env, said", [
    ({**PR_ENV, "GITHUB_EVENT_NAME": "schedule"}, "a schedule run never reads a ledger"),
    ({**PR_ENV, "GITHUB_EVENT_NAME": "workflow_dispatch"}, "never reads a ledger"),
    ({**PR_ENV, "MUTATION_LEDGER": "write"}, "does not name pull_request"),
    ({**PR_ENV, "MUTATION_LEDGER": ""}, "does not name pull_request"),
    ({**PR_ENV, "GITHUB_EVENT_NAME": "push"}, "does not name push"),
    ({**PR_ENV, "GITHUB_RUN_ATTEMPT": "2"}, "a re-run never uses a ledger (attempt 2)"),
    ({**PR_ENV, "GITHUB_RUN_ATTEMPT": ""}, "a re-run never uses a ledger (attempt ?)"),
])
def test_only_an_opted_in_first_attempt_pr_or_push_reads_a_ledger(world, env, said):
    plan = world.apply(env=env)
    _unchanged(world, plan)
    assert said in plan["reasons"][-1]


@pytest.mark.parametrize("extra, said", [
    ({"ledger_eligible": False}, "not eligible"),
    ({"advisory": ["diff"]}, "does not gate on a plain full set"),
])
def test_a_plan_the_planner_did_not_mark_eligible_is_never_ledgered(world, extra, said):
    world.write_plain_plan(**extra)
    plan = world.apply()
    _unchanged(world, plan)
    assert said in plan["reasons"][-1]


def test_an_absent_eligibility_is_ineligible(world):
    plan = world.plan()
    del plan["ledger_eligible"]
    plan = world.apply(plan)
    assert plan["ledger"]["used"] is False and "not eligible" in plan["reasons"][-1]


@pytest.mark.parametrize("kwargs, said", [
    ({"ledger_path": None}, "no ledger was downloaded"),
    ({"run_id": ""}, "named no run"),
    ({"run_id": "99"}, "not run 99's"),
    ({"now": NOW + timedelta(days=15)}, "outside 0-14 days"),
    ({"key": {**KEY, "mutmut": "3.9.0"}}, "the generator key differs (mutmut)"),
    ({"key": {**KEY, "config": "0" * 64}}, "the generator key differs (config)"),
    ({"machinery": "0" * 64}, "the mutation machinery changed"),
])
def test_a_ledger_that_does_not_match_this_run_plans_plain(world, kwargs, said):
    plan = world.apply(**kwargs)
    _unchanged(world, plan)
    assert said in plan["reasons"][-1]


@pytest.mark.parametrize("body", ["{not json", "[]", json.dumps({"kind": "x"})])
def test_an_unreadable_ledger_plans_plain(world, body):
    world.ledger_path.write_text(body, encoding="utf-8")
    _unchanged(world, world.apply())


def test_a_changed_function_is_not_carried(world):
    meta = json.loads(json.dumps(world.meta))
    meta["a.py"]["hashes"]["x_f0"] = "f" * 12
    _write_meta(world.mutants, meta, none_codes=True)
    carried = set(world.apply()["sets"]["full"]["carried"])
    assert not {k for k in carried if k.startswith("boost_cli.core.a.x_f0__")}
    assert "boost_cli.core.c.x_f0__mutmut_2" in carried


def test_a_function_whose_mutant_count_changed_is_not_carried(world):
    # A pragma edit leaves the AST hash alone but renumbers the mutants.
    meta = json.loads(json.dumps(world.meta))
    meta["a.py"]["codes"]["boost_cli.core.a.x_f0__mutmut_7"] = 1
    _write_meta(world.mutants, meta, none_codes=True)
    plan = world.apply()
    carried = set(plan["sets"]["full"]["carried"])
    assert not {k for k in carried if k.startswith("boost_cli.core.a.x_f0__")}
    assert _covered(plan, sorted(k for d in meta.values() for k in d["codes"])) == \
        dict.fromkeys(sorted(k for d in meta.values() for k in d["codes"]), 1)


def test_diff_scope_functions_are_never_carried(world):
    plan = world.plan()
    plan["sets"]["diff"] = {"shards": [], "functions": ["boost_cli.core.a.x_f0",
                                                         "boost_cli.core.b.x_f2"]}
    carried = set(world.apply(plan)["sets"]["full"]["carried"])
    assert not {k for k in carried
                if k.startswith(("boost_cli.core.a.x_f0__", "boost_cli.core.b.x_f2__"))}
    assert "boost_cli.core.c.x_f0__mutmut_2" in carried


def test_a_ledger_carrying_a_mutant_that_is_not_generated_plans_plain(world):
    world.ledger["functions"]["boost_cli.core.a.x_f0"]["survived"] = [2, 5, 9]
    world.ledger_path.write_text(json.dumps(world.ledger), encoding="utf-8")
    plan = world.apply()
    _unchanged(world, plan)
    assert "x_f0__mutmut_9, which is not generated here" in plan["reasons"][-1]


def test_nothing_to_carry_leaves_the_plain_set_untouched(world):
    meta = json.loads(json.dumps(world.meta))
    for data in meta.values():
        data["hashes"] = dict.fromkeys(data["hashes"], "f" * 12)
    _write_meta(world.mutants, meta, none_codes=True)
    plan = world.apply()
    _unchanged(world, plan)
    assert "nothing to carry" in plan["reasons"][-1]


def test_over_the_name_cap_functions_are_uncarried_never_dropped(world):
    # 6 files x 2 carried functions x 4 non-carried names = 48 names over 3
    # shards; a cap of 10 a shard forces un-carrying.
    plan = world.apply(max_names=10)
    full = plan["sets"]["full"]
    assert full["ledger"]["uncarried"] > 0
    assert all(sum("*" not in s for s in shard) <= 10 for shard in full["shards"])
    assert _covered(plan, world.keys()) == dict.fromkeys(world.keys(), 1)


def test_a_cap_nothing_fits_under_plans_plain(world):
    plan = world.apply(max_names=0)
    _unchanged(world, plan)


def test_a_pack_that_fails_headroom_plans_plain(world, monkeypatch):
    monkeypatch.setattr(ml.ms, "headroom_report", lambda loads, cap: (False, ["TOO TIGHT"]))
    plan = world.apply()
    _unchanged(world, plan)
    assert "fails headroom: TOO TIGHT" in plan["reasons"][-1]


def test_any_exception_in_ledgered_planning_plans_plain(world, monkeypatch):
    def boom(*a, **k):
        raise ZeroDivisionError("x")

    monkeypatch.setattr(ml, "ledgered_full", boom)
    plan = world.apply()
    _unchanged(world, plan)
    assert "ZeroDivisionError" in plan["reasons"][-1]


def test_the_apply_cli_rewrites_the_plan_in_place_and_exits_0(world, monkeypatch, capsys):
    monkeypatch.setattr(ml, "generator_key", lambda root: KEY)
    monkeypatch.setattr(ml, "machinery_digest", lambda root: DIGEST)
    monkeypatch.setattr(ml, "_now", lambda: NOW)
    monkeypatch.setattr(ml, "_diff", lambda: type("MD", (), {"MAX_NAMES": 1500}))
    for k, v in PR_ENV.items():
        monkeypatch.setenv(k, v)
    assert ml.main(["apply", "--plan", str(world.plan_path), "--ledger", str(world.ledger_path),
                    "--run-id", "4242", "--meta", str(world.mutants),
                    "--root", str(world.root)]) == 0
    assert world.plan()["sets"]["full"]["carried"]
    assert "ledgered:" in capsys.readouterr().out
    # and with no ledger at all: still 0, still a plan
    world.write_plain_plan()
    assert ml.main(["apply", "--plan", str(world.plan_path), "--meta", str(world.mutants),
                    "--root", str(world.root)]) == 0
    assert world.plan()["ledger"]["used"] is False


# --------------------------------------------------------------------------
# the structural selector reading, against fnmatch itself
# --------------------------------------------------------------------------

_TRICKY = sorted([
    "boost_cli.core.store.x_install__mutmut_1", "boost_cli.core.store.x_install__mutmut_12",
    "boost_cli.core.store.x_install_from_path__mutmut_1",
    "boost_cli.core.store.xǁLockǁacquire__mutmut_2",
    "boost_cli.core.storex.x_install__mutmut_1",
    "boost_cli.core.m.xǁA.Bǁm__mutmut_3",
    "boost_cli.core.rag.bm25.x_score__mutmut_1", "boost_cli.core.rag.x_score__mutmut_1"])


@pytest.mark.parametrize("selector", [
    "boost_cli.core.store.*", "boost_cli.core.store.xǁ*",
    "boost_cli.core.store.x_install__mutmut_*", "boost_cli.core.store.x_install__mutmut_1",
    "boost_cli.core.m.xǁA.Bǁm__mutmut_*", "boost_cli.core.rag.*",
    "boost_cli.core.rag.bm25.*", "boost_cli.core.nothing.*",
])
def test_the_structural_reading_is_fnmatch(selector):
    import fnmatch

    assert ml.selector_keys([selector], _TRICKY) == [
        k for k in _TRICKY if fnmatch.fnmatchcase(k, selector)]


@pytest.mark.parametrize("selector", ["boost_cli.core.*.x_a__mutmut_*", "a?b", "a[b]*", "*", ""])
def test_a_selector_the_planner_never_writes_is_refused(selector):
    with pytest.raises(ml.LedgerError):
        ml.selector_keys([selector], _TRICKY)


def test_the_partition_check_catches_an_overlap_a_gap_and_an_empty_shard():
    keys = ["m.x_a__mutmut_1", "m.x_a__mutmut_2", "m.x_b__mutmut_1"]
    assert ml.partition_problems([["m.x_a__mutmut_*"], ["m.x_b__mutmut_1"]], [], keys) == []
    assert any("selected twice" in p for p in ml.partition_problems(
        [["m.x_a__mutmut_*"], ["m.x_b__mutmut_1"]], ["m.x_a__mutmut_2"], keys))
    assert any("selected by nothing" in p for p in ml.partition_problems(
        [["m.x_a__mutmut_1"], ["m.x_b__mutmut_1"]], [], keys))
    assert any("matches no mutant" in p for p in ml.partition_problems(
        [["m.x_a__mutmut_*", "m.x_b__mutmut_1"], ["m.x_c__mutmut_*"]], [], keys))
    assert any("not generated" in p for p in ml.partition_problems(
        [["m.*"]], ["m.x_z__mutmut_9"], keys))


# --------------------------------------------------------------------------
# selfcheck: the nightly's dry run
# --------------------------------------------------------------------------

def test_the_selfcheck_passes_on_a_correct_ledger(world, capsys):
    assert ml.selfcheck(world.root, world.meta, world.ledger, world.plan(), _status,
                        max_names=1500) == []
    assert "merge --plan gave back every verdict" in capsys.readouterr().out


def _merge_then_inject(code):
    """The real merge, with every carried row then rewritten to ``code``: a wrong injection."""
    def merge(args):
        rc = ms.cmd_merge(args)
        carried = set(json.loads(Path(args.plan).read_text(encoding="utf-8"))
                      ["sets"]["full"]["carried"])
        for meta in Path(args.into).rglob("*.py.meta"):
            data = json.loads(meta.read_text(encoding="utf-8"))
            for k in data["exit_code_by_key"]:
                if k in carried:
                    data["exit_code_by_key"][k] = code
            meta.write_text(json.dumps(data), encoding="utf-8")
        return rc
    return merge


def test_the_selfcheck_bites_when_the_injection_is_wrong(world):
    # The design's proof that the check is not vacuous: a merge that injects
    # 1 (a kill) where it should inject CARRIED_EXIT changes the rows and the score.
    problems = ml.selfcheck(world.root, world.meta, world.ledger, world.plan(), _status,
                            max_names=1500, merge=_merge_then_inject(1))
    assert any("came back changed" in p for p in problems)
    assert any("killed/denominator moved" in p for p in problems)


def test_the_selfcheck_bites_when_the_carried_exit_means_a_kill(world, monkeypatch):
    # A CARRIED_EXIT that mutmut scores as killed: merge and expectation agree
    # with each other, and the meaning check and the score check still catch it.
    monkeypatch.setattr(ml.ms, "CARRIED_EXIT", 1)
    problems = ml.selfcheck(world.root, world.meta, world.ledger, world.plan(), _status,
                            max_names=1500)
    assert any("does not read 1 as survived" in p for p in problems)
    assert any("killed/denominator moved" in p for p in problems)


def test_the_selfcheck_bites_when_the_merge_refuses(world):
    problems = ml.selfcheck(world.root, world.meta, world.ledger, world.plan(), _status,
                            max_names=1500, merge=lambda args: 1)
    assert problems == ["merge --plan refused the ledgered dry run (exit 1)"]


def test_the_selfcheck_fails_when_the_dry_run_cannot_be_ledgered(world):
    with pytest.raises(ml.LedgerError):
        ml.selfcheck(world.root, world.meta, world.ledger, world.plan(), _status, max_names=0)


# --------------------------------------------------------------------------
# find: the reader, against a fake API, on a fixed clock
# --------------------------------------------------------------------------

def _run(ident, event="schedule", hours_ago=10, branch="main"):
    return {"id": ident, "event": event, "head_branch": branch, "status": "completed",
            "created_at": ml._iso(NOW - timedelta(hours=hours_ago))}


class FakeAPI:
    def __init__(self, runs, *, jobs=None, artifacts=None, labels=(), fail=None):
        self.runs, self.jobs, self.artifacts = runs, jobs or {}, artifacts or {}
        self.labels, self.fail, self.calls = labels, fail, []

    def __call__(self, path):
        self.calls.append(path)
        if self.fail and self.fail in path:
            raise OSError("boom")
        if path.startswith("pulls/"):
            return {"labels": [{"name": n} for n in self.labels]}
        if path.startswith("actions/workflows/ci.yml/runs"):
            event = "workflow_dispatch" if "event=workflow_dispatch" in path else "schedule"
            found = [r for r in self.runs if r["event"] == event or r.get("lie")]
            return {"total_count": len(found), "workflow_runs": found}
        ident = int(path.split("/")[2])
        if "/jobs" in path:
            conclusion = self.jobs.get(ident, "success")
            return {"total_count": 1, "jobs": [{"name": "mutation", "run_id": ident,
                                                "status": "completed", "conclusion": conclusion}]}
        arts = self.artifacts.get(ident, [])
        return {"total_count": len(arts), "artifacts": [
            {"name": n, "expired": expired, "workflow_run": {"id": ident}} for n, expired in arts]}


_REAL = [("mutated-tree-" + "a" * 40, False), (ml.ARTIFACT, False)]
_IDLE = [("inherited-tree-" + "a" * 40 + "-from-1", False)]
PR_FIND = {**PR_ENV, "PR_NUMBER": "12"}


def test_the_reader_names_the_newest_real_runs_ledger():
    api = FakeAPI([_run(1, hours_ago=30), _run(2, hours_ago=6)],
                  artifacts={1: _REAL, 2: _REAL})
    found = ml.find(api, PR_FIND, NOW)
    assert found.run_id == 2 and "ledger of whole-codebase run 2" in found.reason


def test_the_reader_steps_over_an_idle_night():
    api = FakeAPI([_run(1, hours_ago=30), _run(2, event="workflow_dispatch", hours_ago=6)],
                  artifacts={1: _REAL, 2: _IDLE})
    assert ml.find(api, PR_FIND, NOW).run_id == 1


@pytest.mark.parametrize("runs, jobs, artifacts, said", [
    ([_run(1, hours_ago=30), _run(2)], {2: "failure"}, {1: _REAL},
     "run 2 (schedule, 2026-11-25T02:00:00Z) is red (mutation: failure)"),
    ([_run(1, hours_ago=30), _run(2)], {}, {1: _REAL, 2: [_REAL[0]]},
     "wrote no usable ledger (0 found)"),
    ([_run(2)], {}, {2: [*_REAL, (ml.ARTIFACT, False)]}, "(2 found)"),
    ([_run(2)], {}, {2: [_REAL[0], (ml.ARTIFACT, True)]}, "(1 found, expired)"),
    ([_run(2)], {}, {2: [*_REAL, _IDLE[0]]}, "carries 2 markers"),
    ([_run(2)], {}, {2: []}, "wrote no usable ledger"),
    ([_run(2, hours_ago=15 * 24)], {}, {2: _REAL}, "no green real whole-codebase run"),
    ([], {}, {}, "no green real whole-codebase run on main in the last 14 days"),
    ([{**_run(2, branch="feature")}], {}, {2: _REAL}, "could not be read"),
])
def test_the_reader_uses_no_ledger_when_it_cannot_trust_one(runs, jobs, artifacts, said):
    found = ml.find(FakeAPI(runs, jobs=jobs, artifacts=artifacts), PR_FIND, NOW)
    assert found.run_id is None
    assert said in found.reason


def test_the_reader_never_reaches_past_a_real_run_to_an_older_ledger():
    api = FakeAPI([_run(1, hours_ago=30), _run(2)],
                  artifacts={1: _REAL, 2: [_REAL[0]]})
    assert ml.find(api, PR_FIND, NOW).run_id is None


@pytest.mark.parametrize("env, said", [
    ({**PR_FIND, "MUTATION_LEDGER": "write"}, "does not name pull_request"),
    ({**PR_FIND, "MUTATION_LEDGER": None}, "does not name pull_request"),
    ({**PR_FIND, "GITHUB_EVENT_NAME": "push"}, "does not name push"),
    ({**PR_FIND, "GITHUB_EVENT_NAME": "schedule"}, "never reads a ledger"),
    ({**PR_FIND, "GITHUB_RUN_ATTEMPT": "2"}, "a re-run never uses a ledger"),
    ({**PR_FIND, "PR_NUMBER": ""}, "no pull request number"),
])
def test_the_reader_reads_nothing_unless_asked(env, said):
    api = FakeAPI([_run(2)], artifacts={2: _REAL})
    found = ml.find(api, {k: v for k, v in env.items() if v is not None}, NOW)
    assert found.run_id is None and said in found.reason
    assert api.calls == []


def test_the_label_keeps_a_pull_request_plain():
    api = FakeAPI([_run(2)], artifacts={2: _REAL}, labels=["bug", ml.NO_LEDGER_LABEL])
    found = ml.find(api, PR_FIND, NOW)
    assert found.run_id is None and "mutation-no-ledger" in found.reason


def test_a_push_needs_no_label_lookup():
    api = FakeAPI([_run(2)], artifacts={2: _REAL})
    found = ml.find(api, {**PR_FIND, "GITHUB_EVENT_NAME": "push",
                          "MUTATION_LEDGER": "push"}, NOW)
    assert found.run_id == 2
    assert not any(c.startswith("pulls/") for c in api.calls)


@pytest.mark.parametrize("fail", ["pulls/", "actions/workflows", "/jobs", "/artifacts"])
def test_any_api_error_is_no_ledger(fail):
    api = FakeAPI([_run(2)], artifacts={2: _REAL}, fail=fail)
    found = ml.find(api, PR_FIND, NOW)
    assert found.run_id is None and "could not be read (OSError)" in found.reason


def test_a_truncated_listing_is_no_ledger():
    class Truncated(FakeAPI):
        def __call__(self, path):
            body = super().__call__(path)
            if "workflows" in path:
                body["total_count"] = 500
            return body

    assert ml.find(Truncated([_run(2)], artifacts={2: _REAL}), PR_FIND, NOW).run_id is None


def test_the_find_cli_writes_one_line_outputs_and_exits_0(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setattr(ml, "make_api", lambda repo, token: FakeAPI(
        [_run(2)], artifacts={2: _REAL}))
    monkeypatch.setattr(ml, "_now", lambda: NOW)
    for k, v in PR_FIND.items():
        monkeypatch.setenv(k, v)
    assert ml.main(["find", "--github-output", str(out)]) == 0
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "run_id=2" and lines[1].startswith("reason=ledger of")
    assert lines[2] == "created_at=2026-11-25T02:00:00Z"


# --------------------------------------------------------------------------
# what needs the real toolchain
# --------------------------------------------------------------------------

def test_the_generator_key_names_the_generator_and_never_the_tests(needs_mutmut):
    key = ml.generator_key(ROOT)
    assert set(key) == {"mutmut", "libcst", "python", "config"}
    assert key["python"] == "%d.%d" % sys.version_info[:2]
    assert len(key["config"]) == 64


def test_the_machinery_digest_moves_with_a_mutation_script(tmp_path):
    pytest.importorskip("yaml")
    for rel in ("scripts", "requirements", ".github/workflows"):
        (tmp_path / rel).mkdir(parents=True)
    for name in ("mutation_plan.py", "mutation_ledger.py"):
        (tmp_path / "scripts" / name).write_text("# %s\n" % name, encoding="utf-8")
    (tmp_path / "scripts" / "other.py").write_text("x\n", encoding="utf-8")
    (tmp_path / "requirements/mutation-tools.txt").write_text("mutmut==3.8.1\n",
                                                              encoding="utf-8")
    ci = tmp_path / ".github/workflows/ci.yml"
    ci.write_text("jobs:\n  mutation:\n    runs-on: x\n  lint:\n    runs-on: y\n",
                  encoding="utf-8")
    first = ml.machinery_digest(tmp_path)
    (tmp_path / "scripts" / "other.py").write_text("y\n", encoding="utf-8")
    ci.write_text("jobs:\n  mutation:\n    runs-on: x\n  lint:\n    runs-on: z\n",
                  encoding="utf-8")
    assert ml.machinery_digest(tmp_path) == first
    ci.write_text("jobs:\n  mutation:\n    runs-on: w\n  lint:\n    runs-on: z\n",
                  encoding="utf-8")
    assert ml.machinery_digest(tmp_path) != first
    ci.write_text("jobs:\n  mutation:\n    runs-on: x\n  lint:\n    runs-on: z\n",
                  encoding="utf-8")
    (tmp_path / "scripts" / "mutation_ledger.py").write_text("# changed\n", encoding="utf-8")
    assert ml.machinery_digest(tmp_path) != first


def test_the_name_cap_and_the_step_timeout_are_the_ones_ci_uses():
    yaml = pytest.importorskip("yaml")
    md = ml._diff()
    assert md.MAX_NAMES == 1500
    jobs = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))["jobs"]
    step = next(s for s in jobs["mutation-shard"]["steps"]
                if str(s.get("name", "")).startswith("mutate "))
    assert step["timeout-minutes"] == ml.STEP_TIMEOUT_MINUTES
