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


def _tree_is_mutated(root: Path = ROOT) -> bool:
    """True when this suite is running inside mutmut's rewritten copy.

    mutmut's ``Running stats`` phase runs ``tests/unit`` from ``mutants/``,
    where every file under ``boost_cli/core`` is the rewritten copy --
    ``store.py`` alone is 16 MB of mutant variants against 164 KB of source.
    The tests marked :data:`real_tree_only` pack ``ROOT``, which there means
    parsing that copy: measured locally they take 245 s in ``mutants/``
    against a few on the checkout, and on CI they were most of the per-job
    preamble ``FIXED_MINUTES`` describes, every shard paying it again. They
    read ``scripts/`` only, which is never mutated, so skipping them there
    kills no fewer mutants. Same rule as ``test_mutation_subfile_shards.py``.
    """
    store = root / "boost_cli" / "core" / "store.py"
    try:
        return "__mutmut_" in store.read_text(encoding="utf-8")
    except OSError:
        return True        # can't tell -- don't pack it


real_tree_only = pytest.mark.skipif(
    _tree_is_mutated(), reason="tree rewritten by mutmut; packing it is the "
                               "per-shard cost FIXED_MINUTES measures")


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

    @real_tree_only
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
        light = 0
        heavy = int((0.60 * cap - ms.FIXED_MINUTES) * ms_per_min)
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
        load = int((0.60 * cap - ms.FIXED_MINUTES) * ms_per_min)
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

    @real_tree_only
    def test_it_is_refused_without_explain(self):
        # ci.yml does PATTERNS="$(plan --shards N --index $SHARD)". Anything
        # this prints on that path becomes an argv word for `mutmut run`, and
        # a stray word there is a pattern matching no mutant -- the shard
        # would run an empty set and report success. Refusing is the only
        # answer that cannot be ignored.
        with pytest.raises(SystemExit) as ei:
            ms.cmd_plan(self._args(index=0, timeout_minutes=75))
        assert "--explain" in str(ei.value)

    @real_tree_only
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

    @real_tree_only
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

#: What the width CI runs at actually did, and the reason there is a second
#: observation constant at all: unlike eight, twelve did not reproduce.
#:
#: The 24 successful jobs of the only two runs at this width -- `d7027cf8`
#: and main's `58ace415`, 2026-10-04 -- have a p50 of 34.55 min and a worst
#: job of 55.8. Frozen like every other measurement in this file: it
#: describes those two runs and no later one can restate it.
TWELVE_SHARD_P50_MIN = 34.55
TWELVE_SHARD_WORST_MIN = 55.8

#: The width those 24 jobs ran at. Spelled out rather than reusing
#: `ms.SHARDS` for the same reason `SHARDS_FOR_FIT` is: `ms.SHARDS` is what
#: CI runs *now*, and pointing a historical measurement at a live constant
#: silently restates what was observed the day someone changes it.
#:
#: It is deliberately NOT `SHARDS_OBSERVED` either, though the two are equal
#: today. That one is a policy ceiling and is meant to move the day a wider
#: matrix runs; this one is the divisor in twelve's two frozen assertions and
#: must never move. Sharing one constant made the ceiling test's own
#: remediation instruction ("raise SHARDS_OBSERVED") red
#: `test_todays_pack_under_predicts_the_worst_twelve_shard_job` -- at
#: sixteen it grades a sixteen-shard prediction against a twelve-shard
#: observation and reports a 19.8-minute shortfall -- while quietly loosening
#: the ratio test from 1.40 to 1.87.
TWELVE_SHARDS = 12

#: The widest matrix width anyone has observed, and a live policy ceiling
#: rather than a measurement: `test_the_committed_width_has_actually_run`
#: refuses an `ms.SHARDS` above it. This is the constant to raise after
#: running a wider matrix; `TWELVE_SHARDS` above is the one to leave alone.
SHARDS_OBSERVED = 12

#: The eight-shard p50 the fit was re-checked against, named so the two
#: widths can be compared in one assertion instead of one of them being a
#: literal inside it. It is the median of the 24 jobs of the THREE
#: eight-shard runs the comment on `FITTED_TOTAL_MS` names; a fourth run
#: (`f3f87c5b`) has since happened and moves it to 42.0, which changes
#: nothing any assertion here depends on.
EIGHT_SHARD_P50_MIN = 41.8

#: The planner's total over the weights measured ON A TWELVE-SHARD RUN, and
#: the reason it has to exist beside `PLANNED_TOTAL_MS`.
#:
#: Grading a width against a total measured at a different width is not like
#: for like, and `PLANNED_TOTAL_MS` is eight's -- #1032's body is where that
#: is said outright ("the cost per mutant was re-timed, this time on a
#: twelve-shard run rather than an eight-shard one"); #1029 records only the
#: width in force at the time. #1032 (`9559440d`) re-timed
#: the same mutants from CI run 37200431822 -- which is `58ace415`, one of
#: the two runs `TWELVE_SHARD_P50_MIN` is drawn from -- and totals
#: 58,969,820 ms over the same 67 files.
#:
#: Frozen like its sibling, and for a sharper reason than usual: it equalled
#: the live weights when it was recorded, and an assertion that read the live
#: file would red the weights bot's own PR the moment it moved. #1038 moved
#: them, which is exactly the event this freezing was for -- the live planner
#: total is no longer this number, and the assertions below are unaffected.
TWELVE_PLANNED_TOTAL_MS = 58_969_820

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


#: The per-job preamble each width actually paid: job duration minus its
#: ``Running mutation testing`` phase, read off the job-log timestamps of every
#: successful ``mutation-shard`` job from 2026-09-26 to 10-06 -- 552 jobs at
#: six, 80 at eight, 229 at twelve. Frozen: they describe those runs. They
#: differ because the suite's planner tests packed mutmut's rewritten tree in
#: every shard's baseline run from eight onward (see `_tree_is_mutated`); a
#: replay of a past width therefore passes that width's own preamble.
SIX_SHARD_FIXED_MIN = 5.11
EIGHT_SHARD_FIXED_MIN = 10.02
TWELVE_SHARD_FIXED_MIN = 12.91

#: The preamble without those tests: the 124 six-shard jobs of 2026-10-01/02,
#: the last before they reached the baseline. `ms.FIXED_MINUTES` is this.
PREAMBLE_WITHOUT_PLANNER_TESTS_MIN = 5.49

#: Mutation-phase minutes per weight-minute, each job graded on its own
#: run's measured durations (the `mutation-weights` artifact) summed over the
#: units that commit's pack gave it: 24 jobs at eight, 192 at twelve, medians.
EIGHT_SHARD_PHASE_RATIO = 0.2528
TWELVE_SHARD_PHASE_RATIO = 0.2555


class TestConversion:
    """`runner_minutes` reproduces what the runners were measured doing.

    Against frozen totals, never against the live weights file -- see
    :data:`FITTED_TOTAL_MS`. What the live file must still satisfy is
    :class:`TestHeadroom`, which is a *relative* question (does the pack fit?)
    and so stays true across a refresh, and is supposed to go red when a
    refresh genuinely makes the gate too slow.
    """

    @pytest.mark.parametrize("ratio", [EIGHT_SHARD_PHASE_RATIO,
                                       TWELVE_SHARD_PHASE_RATIO],
                             ids=["eight", "twelve"])
    def test_the_mutation_phase_divides_the_same_at_both_widths(self, ratio):
        # The calibration the fixed term made possible. Through the origin,
        # whole jobs implied an efficiency of 0.832 at eight and 0.593 at
        # twelve; the mutation phase alone implies the same one at both, to
        # 1%. One weight-minute of work is that many minutes of phase.
        assert ms.parallel_minutes(60000.0) == pytest.approx(ratio, rel=0.03)

    def test_it_matches_the_observed_median(self):
        # 169 successful shard jobs, 26 complete six-shard runs, 2026-09-30 to
        # 2026-10-01: observed p50 was 37.5 min per shard over the six-shard
        # pack of LEGACY_SIX_SHARD_TOTAL_MS, with the preamble six paid.
        predicted = ms.runner_minutes(LEGACY_SIX_SHARD_TOTAL_MS / 6,
                                      SIX_SHARD_FIXED_MIN)
        assert abs(predicted - 37.5) < 1.0, (
            "predicted %.1f min against a measured p50 of 37.5" % predicted)

    def test_twelve_reproduces_its_median(self):
        # What the through-origin model could not do: 34.55 observed against
        # weights timed on one of the two runs graded. Eight is not pinned
        # the same way because PLANNED_TOTAL_MS was timed on a different run
        # from the ones graded -- re-timing the same mutants has moved totals
        # by 12%, and that, not the model, is the 3.7 min it misses eight by.
        # The phase test above grades eight on its own runs' weights instead.
        predicted = ms.runner_minutes(TWELVE_PLANNED_TOTAL_MS / TWELVE_SHARDS,
                                      TWELVE_SHARD_FIXED_MIN)
        assert abs(predicted - TWELVE_SHARD_P50_MIN) < 1.0, (
            "predicted %.1f min against a measured p50 of %.2f"
            % (predicted, TWELVE_SHARD_P50_MIN))

    def test_the_tail_covers_the_worst_twelve_shard_job(self):
        # Through the origin the same pack predicted a 48.0-minute tail and
        # the worst job ran 55.8 -- a 7.8-minute shortfall this file used to
        # pin as a known miss. With the preamble twelve actually paid, the
        # tail clears the worst job; with none, it still would not.
        weight = TWELVE_PLANNED_TOTAL_MS / TWELVE_SHARDS
        assert ms.tail_minutes(weight, TWELVE_SHARD_FIXED_MIN) \
            > TWELVE_SHARD_WORST_MIN
        assert ms.tail_minutes(weight, 0.0) < TWELVE_SHARD_WORST_MIN

    def test_the_committed_preamble_is_the_one_without_planner_tests(self):
        # FIXED_MINUTES describes the tree after `real_tree_only` keeps the
        # planner tests out of mutmut's baseline run, so it is pinned to the
        # last preamble measured without them -- and below what twelve paid
        # with them, which is what this change removes.
        assert abs(ms.FIXED_MINUTES - PREAMBLE_WITHOUT_PLANNER_TESTS_MIN) < 0.1
        assert ms.FIXED_MINUTES < EIGHT_SHARD_FIXED_MIN < TWELVE_SHARD_FIXED_MIN

    def test_widening_cannot_go_below_the_preamble(self):
        # The property the card was about: adding shards divides only the
        # part that divides. Through the origin a wide enough matrix
        # predicted any tail at all.
        weight = TWELVE_PLANNED_TOTAL_MS
        assert ms.runner_minutes(weight / 1000) > ms.FIXED_MINUTES
        assert ms.tail_minutes(weight / 1000) \
            > ms.FIXED_MINUTES * ms.TAIL_MULTIPLIER
        assert ms.runner_minutes(weight / 12) - ms.runner_minutes(weight / 24) \
            == pytest.approx(ms.parallel_minutes(weight / 24))

    def test_the_committed_width_has_actually_run(self):
        # The one executable form of "do not use `plan` to justify a width
        # above twelve", which otherwise exists only as prose in three files.
        # Kept now the model has a fixed term, because that term
        # (FIXED_MINUTES) is the one figure no run has measured yet -- it is
        # the preamble without the planner tests -- and below it every added
        # shard still looks safer to every other assertion here.
        #
        # Widening is still allowed; it just cannot be done on the planner's
        # word alone. Run the wider matrix once, record its p50 and worst
        # here the way twelve is recorded, and raise SHARDS_OBSERVED -- which
        # is this assertion's constant and nothing else's. Leave
        # TWELVE_SHARDS where it is: it is the divisor twelve's frozen
        # observations are graded on, and moving it grades a wider
        # prediction against a twelve-shard measurement.
        assert ms.SHARDS <= SHARDS_OBSERVED, (
            "SHARDS is %d but the widest matrix anyone has observed is %d. "
            "FIXED_MINUTES has not been re-measured since the planner tests "
            "left mutmut's baseline -- see FIXED_MINUTES in "
            "scripts/mutation_shards.py. Run it, record the "
            "p50 and the worst job, then raise SHARDS_OBSERVED."
            % (ms.SHARDS, SHARDS_OBSERVED))

    @real_tree_only
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
        # total, the preamble six paid -- so the model is checked against the
        # single data point the whole change is about, not only the middle.
        # 69.8 predicted: the median lands 1 min under the 37.5 above, and
        # x 1.91 carries that to 2.7.
        tail = ms.tail_minutes(LEGACY_SIX_SHARD_TOTAL_MS / 6, SIX_SHARD_FIXED_MIN)
        assert abs(tail - 72.5) < 3.0

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

    def test_zero_weight_still_pays_the_preamble(self):
        # An empty shard is still a job: checkout, install, mutant
        # generation and mutmut's baseline run all happen before the first
        # mutant. Through the origin it cost nothing.
        assert ms.parallel_minutes(0) == 0.0
        assert ms.runner_minutes(0) == ms.FIXED_MINUTES
        assert ms.runner_minutes(0, 0.0) == 0.0
        assert ms.tail_minutes(0) == ms.FIXED_MINUTES * ms.TAIL_MULTIPLIER

    def test_minutes_scale_with_the_parallelism_they_divide_by(self):
        # Pinned as a relationship, not a number: doubling the workers halves
        # the wall clock. A refactor that dropped the division would leave
        # every absolute assertion above intact only by also moving the
        # constants, and this one catches it on its own.
        before = ms.parallel_minutes(10_000_000)
        assert ms.RUNNER_WORKERS * ms.RUNNER_EFFICIENCY * before * 60000.0 \
            == pytest.approx(10_000_000)


class TestMutatedTreeGuard:
    """`real_tree_only` must fire inside `mutants/` and nowhere else."""

    @staticmethod
    def _store(tmp_path, text):
        core = tmp_path / "boost_cli" / "core"
        core.mkdir(parents=True)
        (core / "store.py").write_text(text, encoding="utf-8")
        return tmp_path

    def test_mutmuts_rewritten_copy_is_recognised(self, tmp_path):
        root = self._store(tmp_path, "def x_install__mutmut_1():\n    pass\n")
        assert _tree_is_mutated(root)

    def test_an_ordinary_checkout_is_not(self, tmp_path):
        root = self._store(tmp_path, "def install():\n    pass\n")
        assert not _tree_is_mutated(root)

    def test_an_unreadable_tree_is_treated_as_mutated(self, tmp_path):
        assert _tree_is_mutated(tmp_path)

    def test_this_checkout_runs_the_real_tree_tests(self):
        # The guard must not quietly skip them in the ordinary `test` job,
        # where they are the headroom gate. Keyed on the directory mutmut
        # runs from rather than on the guard itself, which would be circular.
        assert _tree_is_mutated() == (ROOT.name == "mutants")


#: The tests that pack the real tree, by (class, name). Each must carry
#: `real_tree_only`: dropping the mark from one brings its share of the
#: ~8-minute per-shard preamble back, and nothing else would notice.
_REAL_TREE_TESTS = [
    ("TestHeadroom", "test_the_real_pack_fits_with_margin"),
    ("TestPlanCliContract", "test_it_is_refused_without_explain"),
    ("TestPlanCliContract", "test_the_index_path_prints_patterns_and_only_patterns"),
    ("TestPlanCliContract",
     "test_a_pack_that_fits_exits_zero_and_one_that_does_not_exits_one"),
    ("TestConversion", "test_the_planner_counts_more_than_the_files_a_run_has_timed"),
]


def _skipif_marks(fn) -> list:
    return [m for m in getattr(fn, "pytestmark", []) if m.name == "skipif"]


@pytest.mark.parametrize("cls, name", _REAL_TREE_TESTS,
                         ids=[n for _, n in _REAL_TREE_TESTS])
def test_every_real_tree_test_skips_inside_mutants(cls, name):
    fn = getattr(globals()[cls], name)
    assert _skipif_marks(fn), "%s.%s packs ROOT without real_tree_only" % (cls, name)


def test_a_tmp_tree_test_is_not_marked():
    # The other direction: the mark is opt-in, not something every test
    # here carries -- this one builds its own tree and runs in mutants/ too.
    fn = TestPlanCliContract.test_minutes_are_printed_only_where_the_weights_are_time
    assert not _skipif_marks(fn)
