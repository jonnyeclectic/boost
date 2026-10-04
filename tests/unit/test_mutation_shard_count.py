# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The shard count agrees everywhere, and the pack fits inside the job cap.

Two things this repo cannot derive and therefore has to assert.

**The count.** ``mutation_shards.SHARDS`` is Python's copy of a number also
spelled in the ``mutation-shard`` matrix, in the ``plan --shards`` the shard
step runs, in the ``merge --shards`` the gate runs, and in
``mutation-weights-refresh.yml``. They are not one value with four readers:
a matrix cannot call Python, and ``merge`` reconstructs the same pack from
scratch to know which shard owned which file.

Disagreement is *loud*, and that is still worth a test. ``cmd_merge`` fails
closed — it collects the shards whose ``.meta`` it cannot find and returns 1
naming them, so ``merge --shards 6`` over a twelve-shard matrix is a red
required check rather than a gate quietly scored on half the mutants.
What it is not is *legible*: the failure arrives 40 minutes into the matrix,
names artifacts rather than the mismatch, and reads like a lost upload. The
test turns that into a one-line failure in the ``test`` job before any of it
runs.

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

    Regex, not a YAML loader, and the honest reason is that the repo's test
    tier is stdlib-only — there is no YAML dependency to import here. So this
    only understands the flow-sequence form the file actually uses
    (``index: [0, 1, ...]``); a block sequence, or a list split over lines,
    is equally valid YAML and would make this *fail*, not silently pass. That
    is the acceptable direction for a mis-parse, and the assertion below says
    which form it wants, so the failure explains itself.
    """
    body = _ci()
    start = body.index("  mutation-shard:")
    end = body.index("\n  mutation:", start)
    m = re.search(r"^\s+index:\s*\[([^\]]+)\]", body[start:end], re.M)
    assert m, ("no inline `index: [...]` matrix under mutation-shard — if it "
               "was reformatted as a block sequence, teach this helper that "
               "form rather than deleting the check")
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
        # The regression that justifies the change, kept executable: six
        # shards of the weights the constants were fitted against is a
        # 72.3-minute tail under a 75-minute cap, and `mutation-shard (4)`
        # really was cancelled at 75 on the merge of #1015.
        #
        # Scored on LEGACY_SIX_SHARD_TOTAL_MS, not on the live weights and
        # not on FITTED_TOTAL_MS, because this is a claim about the past: the
        # 72.3 above is six shards of *the weights the constants were fitted
        # against*, and only that frozen total reproduces it. Scoring it on
        # FITTED_TOTAL_MS worked only while the two were the same number --
        # after the 2026-10-02 re-anchor the same line computes a 104.3-minute
        # tail, so the comment and the code would have quietly disagreed. A
        # weights refresh that legitimately made six shards viable again must
        # not red the bot's own PR; whether six is viable TODAY is
        # `test_the_real_pack_fits_with_margin`'s business, at whatever
        # `SHARDS` says.
        safe, _ = ms.headroom_report([int(LEGACY_SIX_SHARD_TOTAL_MS / 6)], 75)
        assert not safe, "the pack that was cancelled now scores as safe"

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
        # Checked as SHAPE, not by hunting for substrings. `"min" not in out`
        # is the obvious spelling and it is wrong twice over:
        # `boost_cli.core.minisign.*` is a real pattern containing "min", so
        # it fails or passes depending on which shard the packer happens to
        # give minisign.py -- a test that flips on a weights refresh while
        # testing nothing about this change.
        #
        # What must hold is that every word is a mutant pattern, on one line,
        # since each word becomes an argv entry for `mutmut run`.
        assert out.count("\n") == 1, "more than one line reaches mutmut's argv"
        for word in out.split():
            assert word.startswith("boost_cli."), \
                "%r is not a mutant pattern, and would become one" % word

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


#: The committed weights' total **at the moment the constants were fitted**.
#:
#: Frozen on purpose, and this is the important part of this file. The
#: calibration tests below check that the model reproduces measurements taken
#: against *this* total; the live `scripts/mutation_weights.json` is a
#: different question and is allowed to move. It does move, on its own:
#: `mutation-weights-refresh.yml` runs after every `ci` on main and opens a PR
#: when the committed plan has fallen 5% behind the measured best. Reading the
#: live file here would mean that bot's PR -- whose entire purpose is to change
#: this number -- reds the required `tests` check, and the prescribed response
#: to a tight pack ("re-measure the weights and re-pack", per the comment above
#: ci.yml's `timeout-minutes`) would do the same. A gate that fires on the fix
#: it recommends is worse than no gate.
#:
#: Re-anchored 2026-10-02 from 44,346,245, because the drift assertion in
#: `test_the_fitted_total_is_still_close_to_the_committed_weights` fired at
#: 44%. That test prescribes re-fitting from the job API rather than widening
#: the bound, so this is a re-fit and `FIT_DRIFT_LIMIT` is untouched.
#:
#: **The re-anchor also fixes a mixed basis, and that is why the old number
#: looks off by more than the weights moved.** 44,346,245 was a *planned*
#: total -- `sum(unit_weight)` over a pack, which is also where ci.yml's
#: 7,391,040 ms even share comes from -- but the assertion compares it against
#: `sum(load_durations)`, which counts only the files a run has timed. The two
#: were close enough to pass while the gap was 4%, so the mismatch went
#: unnoticed. 63,989,009 is a `load_durations` sum, the same basis the
#: assertion uses; `PLANNED_TOTAL_MS` below carries the other one.
#:
#: Like for like the weights moved **1.50x**, not the 44% the assertion
#: printed: timed 42,506,911 -> 63,989,009 (1.505) and planned 44,346,245 ->
#: 66,708,651 (1.504). Nearly all of that is re-measured *cost per mutant*,
#: not new mutants -- the count rose 27,219 -> 28,084 (+3.2%) while ms/mutant
#: rose 1,562 -> 2,279 (+46%), unevenly across files (per-file ratio median
#: 1.21, range 0.78 to 4.52). Do not read it as mutation growth.
#:
#: What the re-fit did NOT find is any error in the constants. Over the 24
#: successful `mutation-shard` jobs of the three eight-shard runs on main
#: (e9718617, 6aef52c4, dd416340) the observed p50 is 41.8 min against a
#: predicted 42.7, an implied `RUNNER_EFFICIENCY` of 0.832 where 0.814 is
#: committed. So the drift was the weights moving, not the model coming
#: apart, and nothing but this anchor needed to change.
#:
#: `TAIL_MULTIPLIER` is deliberately NOT re-fitted. It is a max over 28 samples
#: per shard and there are 3 per shard at this width -- the worst per-shard
#: ratio in those 24 jobs is 1.49 against the committed 1.91, so the committed
#: value over-estimates the tail, which is the safe direction for a cap check.
#: Re-fit it when a comparable sample exists at the current shard count.
FITTED_TOTAL_MS = 63_989_009

#: What the *planner* totals over the same committed file, which is larger, and
#: the two are not interchangeable. `load_durations` sums the 63 files with a
#: recorded time; `pack` covers every file that has mutants, imputing the three
#: that have never been timed -- 66,708,651 ms against 63,989,009, 4.2% more.
#: `FITTED_TOTAL_MS` has to be the former, because the drift check below
#: compares it against `sum(load_durations(...).values())`. A prediction to be
#: held against a real job has to be the latter, because a real job runs the
#: untimed files too.
#:
#: FROZEN, exactly like the two totals around it, and for the same reason:
#: nothing may assert it against a live `pack`. It is the planner's total on
#: 2026-10-02 at EIGHT shards -- the width the 24 observed jobs ran at -- and
#: it exists so a historical prediction stays reproducible, not so the current
#: pack can be checked against it. It is also mildly width-dependent, since
#: `unit_weight` rounds each split unit: ten or twelve total 66,708,650, one
#: ms less.
PLANNED_TOTAL_MS = 66_708_651

#: The shard count `PLANNED_TOTAL_MS` and the median prediction are anchored
#: to: what main actually ran for the three runs the 24 jobs come from. It is
#: deliberately NOT `ms.SHARDS` -- that is the width CI uses *now* (twelve),
#: and re-pointing a historical measurement at it would silently restate what
#: was observed.
SHARDS_FOR_FIT = 8

#: The six-shard fit this file used to be anchored on, kept so the two
#: measurements taken against it stay checkable. Frozen: it describes what was
#: observed on 2026-09-30..10-01 and no later run can change that.
LEGACY_SIX_SHARD_TOTAL_MS = 44_346_245

#: How far the committed weights may drift from the fit before the
#: calibration counts as extrapolating. Named rather than inlined so the
#: bound itself is testable: against the live weights alone, widening it to
#: anything is a change no assertion can see.
FIT_DRIFT_LIMIT = 0.25


def fit_drift(live_total_ms: float) -> float:
    """How far a weights total has moved from the one the constants were fitted at."""
    return abs(live_total_ms - FITTED_TOTAL_MS) / FITTED_TOTAL_MS


class TestConversion:
    """`runner_minutes` reproduces what the runners were measured doing.

    Against :data:`FITTED_TOTAL_MS`, never against the live weights file --
    see its comment. What the live file must still satisfy is
    :class:`TestHeadroom`, which is a *relative* question (does the pack fit?)
    and so stays true across a refresh, and is supposed to go red when a
    refresh genuinely makes the gate too slow.
    """

    def test_it_matches_the_observed_median(self):
        # 169 successful shard jobs, 26 complete six-shard runs, 2026-09-30 to
        # 2026-10-01: observed p50 was 37.5 min per shard over the six-shard
        # pack of FITTED_TOTAL_MS. Asserting the model reproduces that to
        # within a minute is what makes it a calibration rather than a fudge
        # factor -- a constant chosen to make the arithmetic come out would
        # pass the headroom tests above and fail this one.
        predicted = ms.runner_minutes(LEGACY_SIX_SHARD_TOTAL_MS / 6)
        assert abs(predicted - 37.5) < 1.0, (
            "predicted %.1f min against a measured p50 of 37.5" % predicted)

    def test_it_matches_the_observed_median_at_the_current_fit(self):
        # The same check one weights generation later: 24 successful jobs over
        # the three eight-shard runs on main, observed p50 41.8 min. Two
        # different widths, across a 1.50x change in the weights, both landing
        # inside a minute on one unchanged pair of constants, is what says the
        # model is a calibration and not a curve bent through a single point.
        # It is `PLANNED_TOTAL_MS` and not `FITTED_TOTAL_MS` because a real job
        # runs the untimed files too; see those two definitions.
        predicted = ms.runner_minutes(PLANNED_TOTAL_MS / SHARDS_FOR_FIT)
        assert abs(predicted - 41.8) < 1.0, (
            "predicted %.1f min against a measured p50 of 41.8" % predicted)

    def test_the_planner_counts_more_than_the_files_a_run_has_timed(self):
        # The invariant `PLANNED_TOTAL_MS` rests on, asserted against the LIVE
        # weights because -- unlike the constant -- it is true of any weights
        # file: `pack` covers every mutatable file, `load_durations` covers
        # only the ones some run has actually timed, so the planner's total is
        # the larger exactly when something is untimed.
        #
        # Deliberately NOT `planned == PLANNED_TOTAL_MS`. That equality was
        # written here first and is the trap this file already warns about 60
        # lines up: `pack` reads the live `scripts/mutation_weights.json`, so
        # pinning its total to a frozen number reds the required `tests` check
        # on the weights bot's own PR -- every one of them, since changing
        # that file is the PR's entire purpose. Measured before removing it: a
        # 1% bump to one file's millis fails the equality while the 25%
        # staleness gate stays green.
        timed = ms.load_durations(ROOT)
        bins = ms.pack(ROOT, ms.SHARDS)
        planned = sum(ms.unit_weight(ROOT, u) for b in bins for u in b)
        untimed = {ms.rel_name(ROOT, f) for f in ms.source_files(ROOT)
                   if not ms.is_init(f)} - set(timed)
        assert planned >= sum(timed.values())
        if untimed:
            assert planned > sum(timed.values()), (
                "%d mutatable file(s) carry no recorded time (%s), so the "
                "planner must impute them and total more than the timed sum"
                % (len(untimed), ", ".join(sorted(untimed))))

    def test_the_tail_reproduces_the_job_that_was_cancelled(self):
        # Observed worst successful job: 72.5 min (shard 2). Same six-shard
        # total, same constants -- so the model is checked against the single
        # data point the whole change is about, not only against the middle.
        assert abs(ms.tail_minutes(LEGACY_SIX_SHARD_TOTAL_MS / 6) - 72.5) < 1.5

    def test_the_fitted_total_is_still_close_to_the_committed_weights(self):
        # Not a gate on the weights -- a staleness check on the *fit*. The
        # constants are a ratio against FITTED_TOTAL_MS, so once the real
        # weights have moved far from it the calibration is extrapolating.
        # 25% is deliberately loose: the refresh bot's own threshold is a 5%
        # makespan regression, so several ordinary refreshes pass this, and
        # only a change of scale (a file added to or dropped from
        # source_paths, a runner image change) reaches it. When it fires the
        # answer is to re-fit from the job API, not to widen the bound.
        live = sum(ms.load_durations(ROOT).values())
        assert live, "no measured durations committed — cannot judge the fit"
        assert fit_drift(live) < FIT_DRIFT_LIMIT, (
            "committed weights total %d ms against a fit made at %d (%.0f%% "
            "off) — re-fit RUNNER_EFFICIENCY/TAIL_MULTIPLIER from the Actions "
            "job API" % (live, FITTED_TOTAL_MS, 100 * fit_drift(live)))

    @pytest.mark.parametrize("factor, within", [
        (1.00, True),    # the fit itself
        (1.20, True),    # several ordinary refreshes
        (0.80, True),    # ...in the other direction
        (1.30, False),   # a change of scale
        (0.70, False),
    ], ids=["exact", "up-20", "down-20", "up-30", "down-30"])
    def test_the_staleness_bound_is_where_it_claims_to_be(self, factor, within):
        # The bound pinned directly, because the test above cannot see it: it
        # reads one live number that happens to sit near the fit, so widening
        # FIT_DRIFT_LIMIT to any value at all leaves it passing. Driving both
        # sides of the threshold is what makes the 25% a decision rather than
        # a number nobody can change wrongly.
        assert (fit_drift(FITTED_TOTAL_MS * factor) < FIT_DRIFT_LIMIT) is within

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
