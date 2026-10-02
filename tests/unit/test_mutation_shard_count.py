# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The shard count agrees everywhere, and the pack fits inside the job cap.

Two things this repo cannot derive and therefore has to assert.

**The count.** ``mutation_shards.SHARDS`` is Python's copy of a number also
spelled in the ``mutation-shard`` matrix, in the ``plan --shards`` the shard
step runs, in the ``merge --shards`` the gate runs, and in
``mutation-weights-refresh.yml``. They are not one value with four readers:
a matrix cannot call Python, and ``merge`` reconstructs the same pack from
scratch to know which shard owned which file. Disagreement is silent in the
worst direction — ``merge --shards 6`` over an eight-shard matrix repacks into
six bins, looks for ``mutation-shard-6``/``-7`` that it never asks for, and
gates on whichever files its own re-pack happened to place.

**The headroom.** ``timeout-minutes`` cannot be read through ``${{ }}``, so no
job can check itself against it. The check runs here instead, which is better
anyway: a pack that would be cancelled fails in the ``test`` job in
milliseconds rather than 75 minutes into a matrix.

Why that matters is on the record. On the merge of #1015 ``mutation-shard (4)``
ran the cap out and was cancelled; ``ci`` then concluded ``cancelled`` rather
than ``failure``, and ``publish.yml`` gates on ``success`` — so a merge to main
did not ship and nothing said so.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
REFRESH = ROOT / ".github" / "workflows" / "mutation-weights-refresh.yml"
SCRIPT = ROOT / "scripts" / "mutation_shards.py"

_spec = importlib.util.spec_from_file_location("mutation_shards_count", SCRIPT)
ms = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(ms)


def _ci() -> str:
    return CI.read_text(encoding="utf-8")


def _matrix_indices() -> list[int]:
    """The `index:` list under the mutation-shard matrix.

    Parsed with a regex rather than a YAML loader on purpose: the assertion is
    about the literal a human edits. A loader would normalise `[0, 1]` and
    `["0", "1"]` to the same thing, and the matrix is interpolated into
    `--index "$SHARD"`, where the string form is what reaches the shell.
    """
    body = _ci()
    start = body.index("  mutation-shard:")
    end = body.index("\n  mutation:", start)
    m = re.search(r"^\s+index:\s*\[([^\]]+)\]", body[start:end], re.M)
    assert m, "no `index:` matrix under mutation-shard"
    return [int(x) for x in m.group(1).split(",")]


def test_the_matrix_is_exactly_the_shard_count_zero_indexed():
    # Not just the length. `plan --index` validates `0 <= index < shards` and
    # exits non-zero outside it, so a matrix of [1..8] would fail one job and
    # never run shard 0's units at all -- and the merge would see shard 0's
    # artifact missing, which `mutmut` counts as unrun rather than as absent.
    assert _matrix_indices() == list(range(ms.SHARDS))


@pytest.mark.parametrize("path", [CI, REFRESH], ids=lambda p: p.name)
def test_every_shards_flag_in_the_workflows_matches(path):
    found = [int(n) for n in re.findall(r"--shards\s+(\d+)",
                                        path.read_text(encoding="utf-8"))]
    assert found, "no `--shards N` in %s — did the invocation move?" % path.name
    assert set(found) == {ms.SHARDS}, (
        "%s spells --shards %s against SHARDS=%d"
        % (path.name, sorted(set(found)), ms.SHARDS))


def test_the_step_name_counts_the_same_shards():
    # Cosmetic only, and pinned anyway: "shard 3 of 6" over an eight-way
    # matrix is the kind of thing that is read as evidence later, which is how
    # the stale "planned 24.1 min per shard" comment above `timeout-minutes`
    # survived the move to millisecond weights.
    assert "of %d" % ms.SHARDS in _ci(), \
        "the `mutate shard ... of N` step name disagrees with SHARDS"


def timeout_minutes() -> int:
    """`mutation-shard`'s own `timeout-minutes`, not some other job's."""
    body = _ci()
    start = body.index("  mutation-shard:")
    end = body.index("\n  mutation:", start)
    m = re.search(r"^\s+timeout-minutes:\s*(\d+)", body[start:end], re.M)
    assert m, "mutation-shard has no timeout-minutes"
    return int(m.group(1))


class TestHeadroom:
    """The committed pack, scored against the committed cap."""

    def test_the_real_pack_fits_with_margin(self):
        # The end-to-end assertion, over the real tree and the real weights:
        # whatever `SHARDS` is today, packing the repo that way must leave the
        # slowest shard's predicted tail inside HEADROOM of the real ceiling.
        bins = ms.pack(ROOT, ms.SHARDS)
        loads = [sum(ms.unit_weight(ROOT, u) for u in b) for b in bins]
        safe, lines = ms.headroom_report(loads, timeout_minutes())
        assert safe, "\n".join(lines)

    def test_the_six_shard_pack_this_replaced_does_not(self):
        # The regression that justifies the change, kept executable. Six shards
        # over the same weights is a 72.3-minute tail against a 75-minute cap,
        # and `mutation-shard (4)` really was cancelled at 75 on the merge of
        # #1015. If this ever starts passing, the gate got cheaper and the move
        # to eight can be revisited -- it should not fail silently either way.
        bins = ms.pack(ROOT, 6)
        loads = [sum(ms.unit_weight(ROOT, u) for u in b) for b in bins]
        safe, _ = ms.headroom_report(loads, timeout_minutes())
        assert not safe, "six shards now fits — re-derive the matrix size"

    def test_it_is_scored_on_the_heaviest_shard_not_the_lightest(self):
        # The real packer balances to within 0.01%, so over the committed tree
        # `max(loads)` and `min(loads)` are the same number to one decimal and
        # every other test here passes with either. An unbalanced pack is the
        # case that separates them, and it is not hypothetical: the weights
        # file is explicitly advisory, so a tree whose hints are missing or
        # stale packs on line counts and spreads much wider.
        cap = 75
        ms_per_min = 60000.0 * ms.RUNNER_WORKERS * ms.RUNNER_EFFICIENCY
        light = int(0.05 * cap * ms_per_min)
        heavy = int(0.60 * cap * ms_per_min)
        safe, lines = ms.headroom_report([light, light, heavy], cap)
        assert not safe, (
            "scored on the lightest shard — a pack is as slow as its slowest\n"
            + "\n".join(lines))
        assert ms.headroom_report([light, light, light], cap)[0], \
            "and a genuinely light pack must still pass"

    def test_the_verdict_turns_on_the_tail_not_the_median(self):
        # A pack whose MEDIAN sits comfortably inside the cap and whose tail
        # does not. This is the whole failure: the cancelled pack's median was
        # 37.8 min against 75 -- half the ceiling, and it died anyway.
        cap = 75
        # Weight whose median lands at 60% of cap, so tail = 1.91 x that.
        ms_per_min = 60000.0 * ms.RUNNER_WORKERS * ms.RUNNER_EFFICIENCY
        load = int(0.60 * cap * ms_per_min)
        assert ms.runner_minutes(load) < cap, "median must look safe"
        safe, lines = ms.headroom_report([load], cap)
        assert not safe, "\n".join(lines)
        assert "TOO TIGHT" in "\n".join(lines)


class TestPlanCliContract:
    """What `--timeout-minutes` may and may not do to stdout."""

    @staticmethod
    def _args(**kw):
        base = {"root": str(ROOT), "shards": ms.SHARDS, "index": None,
                "explain": False, "timeout_minutes": None}
        base.update(kw)
        return type("A", (), base)()

    def test_it_is_refused_without_explain(self):
        # ci.yml does PATTERNS="$(plan --shards N --index $SHARD)". Anything
        # this prints on that path becomes an argv word for `mutmut run`, and
        # a stray word there is a pattern matching no mutant -- the shard
        # would run an empty set and report success. Refusing is the only
        # answer that cannot be ignored.
        with pytest.raises(SystemExit) as ei:
            ms.cmd_plan(self._args(index=0, timeout_minutes=75))
        assert "--explain" in str(ei.value)

    def test_the_index_path_prints_patterns_and_only_patterns(self, capsys):
        assert ms.cmd_plan(self._args(index=0)) == 0
        out = capsys.readouterr().out
        assert out.strip(), "shard 0 planned nothing"
        assert "min" not in out and "headroom" not in out, out

    def test_a_pack_that_fits_exits_zero_and_one_that_does_not_exits_one(self,
                                                                        capsys):
        assert ms.cmd_plan(self._args(explain=True, timeout_minutes=75)) == 0
        assert "headroom    : OK" in capsys.readouterr().out
        # Six is the pack that was cancelled; the exit code is what a CI step
        # or a `make` target would act on, so it is asserted, not just the text.
        assert ms.cmd_plan(self._args(shards=6, explain=True,
                                      timeout_minutes=75)) == 1
        assert "TOO TIGHT" in capsys.readouterr().out

    def test_minutes_are_printed_only_where_the_weights_are_time(self, tmp_path,
                                                                 capsys):
        # A repo with no weights file packs on line counts, which are a ratio
        # with no runner behind them. Printing "~N min" against those would be
        # the same unit confusion this change exists to remove, one tier down.
        src = tmp_path / "boost_cli" / "core"
        src.mkdir(parents=True)
        (src / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        (src / "b.py").write_text("def g():\n    return 2\n", encoding="utf-8")
        args = self._args(root=str(tmp_path), shards=2, explain=True,
                          timeout_minutes=75)
        assert ms.cmd_plan(args) == 0, "must not fail a tree it cannot judge"
        out = capsys.readouterr().out
        assert "lines" in out
        assert "min)" not in out, out
        assert "not checked" in out, \
            "silence would read as a pack that passed the check"


class TestConversion:
    """`runner_minutes` reproduces what the runners were measured doing."""

    def test_it_matches_the_observed_median(self):
        # 169 successful shard jobs, 26 complete six-shard runs, 2026-09-30 to
        # 2026-10-01: observed p50 was 37.5 min per shard against the committed
        # six-shard pack. Asserting the model reproduces that to within a
        # minute is what makes it a calibration rather than a fudge factor --
        # a constant chosen to make the arithmetic come out would pass the
        # headroom tests above and fail this one.
        bins = ms.pack(ROOT, 6)
        loads = [sum(ms.unit_weight(ROOT, u) for u in b) for b in bins]
        predicted = ms.runner_minutes(max(loads))
        assert abs(predicted - 37.5) < 1.0, (
            "predicted %.1f min against a measured p50 of 37.5" % predicted)

    def test_the_tail_reproduces_the_job_that_was_cancelled(self):
        # Observed worst successful job: 72.5 min (shard 2). Same six-shard
        # pack, same constants -- so the model is checked against the single
        # data point the whole change is about, not only against the middle.
        bins = ms.pack(ROOT, 6)
        loads = [sum(ms.unit_weight(ROOT, u) for u in b) for b in bins]
        assert abs(ms.tail_minutes(max(loads)) - 72.5) < 1.5

    def test_zero_weight_is_zero_minutes(self):
        assert ms.runner_minutes(0) == 0.0
        assert ms.tail_minutes(0) == 0.0

    def test_minutes_scale_with_the_parallelism_they_divide_by(self):
        # Pinned as a relationship, not a number: doubling the workers halves
        # the wall clock. A refactor that dropped the division would leave
        # every absolute assertion above intact only by also moving the
        # constants, and this one catches it on its own.
        before = ms.runner_minutes(10_000_000)
        assert ms.RUNNER_WORKERS * ms.RUNNER_EFFICIENCY * before * 60000.0 \
            == pytest.approx(10_000_000)
