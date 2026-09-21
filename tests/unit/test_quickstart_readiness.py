# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: `boost quickstart`'s readiness verdict (core.bootstrap).

The defect these pin: on a machine that could reach no registry at all,
quickstart failed 0-for-7 clones, printed "✓ indexed 0 items for keyword
search" and "✓ ready — try `boost search brainstorming`", and exited 0 — while
the very next line of README's install snippet, `boost search`, exits 1 with
"no taps configured — nothing to search".

The rule is NOT "any clone failed". A first-run command that exits non-zero on
one transient registry 404 would be worse than the bug it fixed, and a rerun on
a fully configured machine carries *zero* ``ok`` results (``add_many`` answers
``skipped`` for a registry already tapped), so "no clone succeeded" is not the
test either. The run fails when every registry it attempted failed, or when it
left nothing to search. The command end of this lives in
tests/functional/test_cli_quickstart.py.
"""
from __future__ import annotations

from boost_cli.core import bootstrap


def _outcome(**kw) -> bootstrap.SetupOutcome:
    kw.setdefault("entries", 1)
    return bootstrap.SetupOutcome(**kw)


class TestSetupOutcomeVerdict:
    """The decision itself, exercised without the CLI around it.

    Single-field flips at each boundary on purpose: the clauses are an `and`
    of three emptiness tests plus a count, and a test that only drives the two
    extremes leaves `and`→`or` and `> 0`→`>= 0` alive.
    """

    def test_a_clean_run_is_ready(self):
        assert _outcome(tapped=["a", "b"]).ok is True

    def test_every_attempted_registry_failing_is_not_ready(self):
        assert _outcome(failed=["a", "b"], entries=0).ok is False

    def test_one_failure_beside_a_success_is_still_ready(self):
        # The transient 404. Named, never fatal.
        assert _outcome(tapped=["a"], failed=["b"]).ok is True

    def test_one_failure_beside_an_already_tapped_registry_is_still_ready(self):
        # A rerun that tops up a machine: six were already there, the seventh
        # 404s. Nothing was lost, so nothing is broken.
        assert _outcome(already=["a"], failed=["b"]).ok is True

    def test_a_rerun_where_everything_was_already_tapped_is_ready(self):
        # The case a naive `count(ok) == 0 -> return 1` would fail: on a clean
        # rerun add_many returns `skipped` for all seven, so zero results carry
        # ok=True while the machine is perfectly set up.
        assert _outcome(already=["a", "b"]).ok is True

    def test_a_run_that_attempted_nothing_has_not_failed_at_anything(self):
        # An empty selection (a catalogue with no tappable rows) over a working
        # index: no registry failed, so this is not "every attempt failed".
        res = _outcome()
        assert res.every_attempt_failed is False
        assert res.ok is True

    def test_an_empty_keyword_index_is_not_ready(self):
        # "✓ indexed 0 items" beside "✓ ready" is the self-contradiction the
        # card names; nothing is searchable, whatever the clones did.
        assert _outcome(tapped=["a"], entries=0).ok is False

    def test_one_indexed_item_is_enough_to_be_ready(self):
        assert _outcome(tapped=["a"], entries=1).searchable is True
        assert _outcome(tapped=["a"], entries=1).ok is True

    def test_a_failed_run_on_a_machine_with_an_index_is_still_not_ready(self):
        # quickstart accomplished nothing; the index it reports is somebody
        # else's work from an earlier run.
        assert _outcome(failed=["a", "b"], entries=500).ok is False

    def test_selected_counts_every_bucket(self):
        res = _outcome(tapped=["a"], already=["b", "c"], failed=["d"])
        assert res.selected == 4


class TestSetupOutcomeMessages:
    """Each not-ready state has its own cause, so each names its own remedy."""

    def test_the_ready_line_is_the_one_quickstart_has_always_printed(self):
        assert _outcome(tapped=["a"]).verdict() == (
            "ready — try `boost search brainstorming`", "")

    def test_total_failure_says_nothing_is_searchable(self):
        msg, hint = _outcome(failed=["a", "b", "c"], entries=0).verdict()
        assert msg == ("not ready — none of the 3 registries could be tapped, "
                       "so nothing is searchable")
        assert hint == "check the network, then run `boost quickstart` again"

    def test_total_failure_beside_an_existing_index_does_not_claim_it_is_empty(
            self):
        msg, hint = _outcome(failed=["a", "b"], entries=1500).verdict()
        assert msg == ("not ready — none of the 2 registries could be tapped; "
                       "the 1,500 items already indexed are unaffected")
        assert "network" in hint

    def test_an_empty_index_after_registries_arrived_points_at_doctor(self):
        # Pulling again cannot fill registries that hold nothing boost indexes,
        # and `doctor` names the clone/catalog gaps per tap with their fixes.
        msg, hint = _outcome(tapped=["a"], entries=0).verdict()
        assert msg.startswith("not ready — the keyword index is empty")
        assert "boost doctor" in hint
        assert "network" not in hint

    def test_a_clean_run_has_no_failure_note(self):
        assert _outcome(tapped=["a", "b"]).failure_note() == ""

    def test_the_failure_note_names_the_registries_that_failed(self):
        note = _outcome(tapped=["a"], already=["x"],
                        failed=["b/c", "d/e"]).failure_note()
        assert note == "2 of 4 registries could not be tapped: b/c, d/e"

    def test_total_failure_leaves_the_note_to_the_verdict(self):
        # "none of the 7 could be tapped" is the error line; "7 of 7 could not
        # be tapped" directly above it would be the same fact twice.
        assert _outcome(failed=["a", "b"], entries=0).failure_note() == ""

    def test_up_to_the_threshold_every_failure_is_named(self):
        cap = bootstrap.MAX_NAMED_REGISTRIES
        failed = ["r%d" % i for i in range(cap)]
        note = _outcome(tapped=["a"], failed=failed).failure_note()
        assert note == ("%d of %d registries could not be tapped: %s"
                        % (cap, cap + 1, ", ".join(failed)))

    def test_past_the_threshold_the_note_reports_the_count_not_the_list(self):
        # `--catalog` is 463 registries; a line naming every failure is a wall
        # of text, exactly as the dry run already decided at this threshold.
        cap = bootstrap.MAX_NAMED_REGISTRIES
        failed = ["r%d" % i for i in range(cap + 1)]
        note = _outcome(tapped=["a"], failed=failed).failure_note()
        assert note == ("%d of %d registries could not be tapped"
                        % (cap + 1, cap + 2))

    def test_the_threshold_is_a_handful(self):
        # The dry run used a literal 12 before it shared this constant; the
        # shared value must not drift away from that without a decision.
        assert bootstrap.MAX_NAMED_REGISTRIES == 12
