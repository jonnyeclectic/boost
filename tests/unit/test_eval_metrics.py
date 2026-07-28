"""Exact-arithmetic tests for the eval harness metrics (evals/metrics.py).

The eval harness is a measuring instrument, so its own arithmetic has to be
pinned independently of the thing it measures — otherwise a broken metric and a
broken ranker are indistinguishable. Every expected value below is written as
the formula that produces it *and* asserted against a decimal literal, so
neither a refactor of the expression nor a drifted constant can pass alone.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import ClassVar, Dict, List

import pytest

from evals import make_golden, metrics

ROOT = Path(__file__).resolve().parent.parent.parent

LOG2_3 = math.log2(3)          # 1.584962500721156 — the rank-2 discount


class TestDedupe:
    def test_keeps_first_occurrence_order(self):
        assert metrics.dedupe(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]

    def test_empty(self):
        assert metrics.dedupe([]) == []


class TestGain:
    @pytest.mark.parametrize(("rel", "expected"), [(0, 0.0), (1, 1.0),
                                                   (2, 3.0), (3, 7.0)])
    def test_exponential_gain_is_two_to_the_rel_minus_one(self, rel, expected):
        assert metrics.gain(rel) == expected

    @pytest.mark.parametrize(("rel", "expected"), [(0, 0.0), (1, 1.0),
                                                   (2, 2.0), (3, 3.0)])
    def test_linear_gain_is_the_grade(self, rel, expected):
        assert metrics.gain(rel, exponential=False) == expected


class TestRecall:
    labels: ClassVar[Dict[str, int]] = {"a": 3, "b": 2, "c": 1}

    def test_partial_recall_at_5(self):
        # top-5 of this ranking holds a and b, but c sits at rank 6.
        ranked = ["x", "a", "y", "b", "z", "c"]
        assert metrics.recall_at_k(ranked, self.labels, 5) == pytest.approx(2 / 3)

    def test_full_recall_at_10(self):
        ranked = ["x", "a", "y", "b", "z", "c"]
        assert metrics.recall_at_k(ranked, self.labels, 10) == 1.0

    def test_grade_1_counts_as_relevant(self):
        assert metrics.recall_at_k(["c"], {"c": 1}, 5) == 1.0

    def test_duplicates_cannot_inflate_recall(self):
        assert metrics.recall_at_k(["a", "a", "a"], self.labels, 5) == \
            pytest.approx(1 / 3)

    def test_no_labels_is_zero_not_a_crash(self):
        assert metrics.recall_at_k(["a"], {}, 5) == 0.0


class TestReciprocalRank:
    def test_first_relevant_at_rank_3(self):
        assert metrics.reciprocal_rank(["x", "y", "a"], {"a": 3}) == \
            pytest.approx(1 / 3)

    def test_rank_1_is_one(self):
        assert metrics.reciprocal_rank(["a", "b"], {"a": 1}) == 1.0

    def test_marginal_hit_still_counts(self):
        # MRR is binary in relevance: a grade-1 hit at rank 2 scores 0.5.
        assert metrics.reciprocal_rank(["x", "c"], {"a": 3, "c": 1}) == 0.5

    def test_nothing_relevant_is_zero(self):
        assert metrics.reciprocal_rank(["x", "y"], {"a": 3}) == 0.0


class TestDCG:
    def test_discount_is_log2_of_rank_plus_one(self):
        # rank 1 is undiscounted, rank 2 divides by log2(3).
        assert metrics.dcg([1.0, 1.0]) == pytest.approx(1.0 + 1.0 / LOG2_3)
        assert metrics.dcg([1.0, 1.0]) == pytest.approx(1.630929753571, abs=1e-9)

    def test_empty_is_zero(self):
        assert metrics.dcg([]) == 0.0


class TestNDCG:
    """The worked example, computed by hand.

    labels  a=3 (gain 7), b=2 (gain 3), c=1 (gain 1)
    ranked  [b, x, a, c]  with x unlabeled (gain 0)

    DCG@3  = 3/log2(2) + 0/log2(3) + 7/log2(4) = 3 + 0 + 3.5      = 6.5
    IDCG@3 = 7/log2(2) + 3/log2(3) + 1/log2(4) = 7 + 1.89279 + 0.5 = 9.39279
    nDCG@3 = 6.5 / 9.39279                                         = 0.692020
    """
    labels: ClassVar[Dict[str, int]] = {"a": 3, "b": 2, "c": 1}
    ranked: ClassVar[List[str]] = ["b", "x", "a", "c"]

    def test_exponential_gain_worked_example(self):
        expected = (3.0 + 0.0 + 3.5) / (7.0 + 3.0 / LOG2_3 + 0.5)
        got = metrics.ndcg_at_k(self.ranked, self.labels, 3)
        assert got == pytest.approx(expected)
        assert got == pytest.approx(0.6920202, abs=1e-7)

    def test_linear_gain_worked_example(self):
        # Same ranking, gains 2 / 0 / 3 and ideal gains 3 / 2 / 1.
        # DCG  = 2 + 0 + 3/2                 = 3.5
        # IDCG = 3 + 2/log2(3) + 1/2         = 4.761859
        expected = (2.0 + 0.0 + 1.5) / (3.0 + 2.0 / LOG2_3 + 0.5)
        got = metrics.ndcg_at_k(self.ranked, self.labels, 3, exponential=False)
        assert got == pytest.approx(expected)
        assert got == pytest.approx(0.7350070, abs=1e-7)

    def test_ideal_order_scores_one(self):
        assert metrics.ndcg_at_k(["a", "b", "c"], self.labels, 3) == \
            pytest.approx(1.0)

    def test_grade_order_matters_not_just_membership(self):
        """Same three items, wrong order — this is what recall cannot see."""
        assert metrics.recall_at_k(["c", "b", "a"], self.labels, 3) == 1.0
        assert metrics.ndcg_at_k(["c", "b", "a"], self.labels, 3) < 0.75

    def test_ideal_is_truncated_to_k(self):
        """More relevant items than k: returning the best k still scores 1.0."""
        labels = {"a": 3, "b": 3, "c": 3, "d": 3}
        assert metrics.ndcg_at_k(["a", "b"], labels, 2) == pytest.approx(1.0)

    def test_tied_perfect_labels_are_interchangeable(self):
        """Two grade-3 answers (golden q16/q27) must score the same either way."""
        labels = {"a": 3, "b": 3, "c": 1}
        assert metrics.ndcg_at_k(["a", "b"], labels, 2) == \
            pytest.approx(metrics.ndcg_at_k(["b", "a"], labels, 2))

    def test_nothing_relevant_is_zero(self):
        assert metrics.ndcg_at_k(["x", "y"], self.labels, 3) == 0.0

    def test_no_labels_is_zero_not_a_crash(self):
        assert metrics.ndcg_at_k(["a"], {}, 3) == 0.0


class TestScoreQuery:
    def test_reports_all_five_headline_metrics(self):
        got = metrics.score_query(["a"], {"a": 3})
        assert set(got) == set(metrics.METRIC_NAMES)
        assert got["MRR"] == 1.0

    def test_dedupes_before_ranking_metrics(self):
        """A repeated name must not occupy two ranks."""
        dupes = metrics.score_query(["x", "x", "a"], {"a": 3})
        clean = metrics.score_query(["x", "a"], {"a": 3})
        assert dupes == clean


class TestPairedBootstrap:
    def test_identical_arms_have_zero_delta_and_p_one(self):
        scores = [1.0, 0.5, 0.25, 0.0]
        got = metrics.paired_bootstrap(scores, scores, resamples=200)
        assert got["delta"] == 0.0
        assert got["p_value"] == 1.0

    def test_is_deterministic_for_a_fixed_seed(self):
        base = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
        cand = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4]
        a = metrics.paired_bootstrap(base, cand, resamples=500, seed=7)
        b = metrics.paired_bootstrap(base, cand, resamples=500, seed=7)
        assert a == b

    def test_uniform_regression_is_significant(self):
        """Every query drops by the same amount: no resample can reverse it."""
        base = [1.0] * 20
        cand = [0.5] * 20
        got = metrics.paired_bootstrap(base, cand, resamples=1000)
        assert got["delta"] == pytest.approx(-0.5)
        # Not a single resample lands >= 0, so p hits the (0+1)/(B+1) floor.
        assert got["p_value"] == pytest.approx(1 / 1001)
        assert got["ci_high"] < 0

    def test_single_query_noise_is_not_significant(self):
        """One query in twenty regressing must not trip a p<0.05 gate."""
        base = [1.0] * 20
        cand = [1.0] * 19 + [0.0]
        got = metrics.paired_bootstrap(base, cand, resamples=2000)
        assert got["delta"] == pytest.approx(-0.05)
        assert got["p_value"] > 0.05

    def test_improvement_is_one_sided_the_other_way(self):
        got = metrics.paired_bootstrap([0.0] * 20, [1.0] * 20, resamples=1000)
        assert got["delta"] == pytest.approx(1.0)
        assert got["p_value"] == pytest.approx(1 / 1001)

    def test_confidence_interval_brackets_the_delta(self):
        base = [1.0, 0.8, 0.6, 0.9, 0.7, 0.5, 0.4, 1.0]
        cand = [0.9, 0.7, 0.6, 0.8, 0.7, 0.4, 0.4, 0.9]
        got = metrics.paired_bootstrap(base, cand, resamples=2000)
        assert got["ci_low"] <= got["delta"] <= got["ci_high"]

    def test_mismatched_lengths_raise(self):
        with pytest.raises(ValueError, match="equal-length"):
            metrics.paired_bootstrap([1.0, 0.0], [1.0])

    def test_empty_input_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            metrics.paired_bootstrap([], [])


class TestPercentile:
    def test_endpoints_and_midpoint(self):
        data = [0.0, 1.0, 2.0, 3.0, 4.0]
        assert metrics._percentile(data, 0.0) == 0.0
        assert metrics._percentile(data, 1.0) == 4.0
        assert metrics._percentile(data, 0.5) == 2.0

    def test_interpolates_between_samples(self):
        # pos = 0.25 * (2 - 1) = 0.25 -> a quarter of the way from 0 to 4.
        assert metrics._percentile([0.0, 4.0], 0.25) == pytest.approx(1.0)

    def test_single_and_empty(self):
        assert metrics._percentile([7.0], 0.5) == 7.0
        assert metrics._percentile([], 0.5) == 0.0


class TestGoldenSetIntegrity:
    """The committed golden set must agree with its generator and the corpus."""

    def test_committed_json_matches_the_generator(self):
        committed = (ROOT / "evals" / "golden_set.json").read_text(encoding="utf-8")
        assert committed == make_golden.render(make_golden.build()), \
            "evals/golden_set.json is stale — run `python3 evals/make_golden.py`"

    def test_every_cited_skill_exists_in_the_corpus(self):
        from evals import make_corpus
        assert make_golden.validate(make_golden.QUERIES,
                                    make_corpus.skill_names()) == []

    def test_query_count_is_in_the_documented_range(self):
        assert 25 <= len(make_golden.QUERIES) <= 40

    def test_every_query_has_a_perfect_answer(self):
        for qid, _text, labels, _note in make_golden.QUERIES:
            assert 3 in labels.values(), "%s has no grade-3 answer" % qid

    def test_baseline_covers_every_golden_query(self):
        """A baseline missing a query would silently shrink the paired test."""
        baseline = json.loads(
            (ROOT / "evals" / "baseline.json").read_text(encoding="utf-8"))
        pinned = set(baseline["arms"]["bm25"]["per_query"])
        assert pinned == {q[0] for q in make_golden.QUERIES}
