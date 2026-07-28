"""Retrieval metrics and paired-bootstrap significance testing. Pure stdlib.

Every function here is a pure function of a ranked list of item ids and a
*graded* relevance map, so the whole file is exactly-testable — the hand-computed
cases in tests/unit/test_eval_metrics.py are the specification.

Relevance grades follow the golden set's 3/2/1 scale:

    3  perfect   this is the skill the query is asking for
    2  useful    a competent answer, not the best one
    1  marginal  topically adjacent; better than an unrelated hit
    0  (absent from the label map) irrelevant

Rank-based metrics assume ``ranked`` is best-first and **de-duplicated** — the
same skill name ships from several taps, so retrieval can return one hit per
(name, tap) and a repeat would otherwise be counted twice. Call ``dedupe`` first;
``recall_at_k`` is set-based and immune, the others are not.
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Mapping, Sequence

# Bootstrap defaults. The seed makes the gate reproducible: the same scores must
# always yield the same p-value, or a flaky CI run could block a clean merge.
RESAMPLES = 10000
SEED = 20240517


def dedupe(ids: Sequence[str]) -> List[str]:
    """Collapse a ranked list to the first (best) occurrence of each id."""
    seen = set()
    out: List[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def relevant_ids(labels: Mapping[str, int]) -> set:
    """The ids counting as relevant at all (grade >= 1)."""
    return {i for i, rel in labels.items() if rel >= 1}


def gain(rel: int, exponential: bool = True) -> float:
    """Graded gain for a relevance label.

    Exponential gain (2**rel - 1, the Burges formulation) is the default: it
    makes a `perfect` hit worth substantially more than two `marginal` ones,
    which is the behavior we want out of a ranker. Linear gain (rel) is kept
    behind the flag because it is the other half of the standard definition and
    the unit tests pin both.
    """
    return (2.0 ** rel - 1.0) if exponential else float(rel)


# ------------------------------------------------------------------ metrics

def recall_at_k(ranked: Sequence[str], labels: Mapping[str, int], k: int) -> float:
    """Fraction of the relevant items retrieved in the top k.

    Grades are binarized here (>=1 counts) — recall asks "did we find it", and
    the graded distinction is what nDCG is for. 0.0 when nothing is relevant.
    """
    relevant = relevant_ids(labels)
    if not relevant:
        return 0.0
    return len(set(ranked[:k]) & relevant) / len(relevant)


def reciprocal_rank(ranked: Sequence[str], labels: Mapping[str, int]) -> float:
    """1/rank of the first relevant hit; 0.0 if none was retrieved."""
    relevant = relevant_ids(labels)
    for i, item in enumerate(ranked):
        if item in relevant:
            return 1.0 / (i + 1)
    return 0.0


def dcg(gains: Sequence[float]) -> float:
    """Discounted cumulative gain with the standard log2(rank + 1) discount.

    ``gains`` is in rank order, so position i (0-based) is rank i+1 and the
    discount is log2(i + 2) — rank 1 is undiscounted, rank 2 divides by 1.585.
    """
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(ranked: Sequence[str], labels: Mapping[str, int], k: int,
              exponential: bool = True) -> float:
    """nDCG@k: DCG of the returned order over DCG of the ideal order.

    The ideal order is every labeled item sorted by grade, truncated to k — so
    a query with more relevant items than k can still score 1.0 by returning the
    best k in the right order. 0.0 when no labeled item exists.
    """
    got = dcg([gain(labels.get(item, 0), exponential) for item in ranked[:k]])
    ideal_grades = sorted(labels.values(), reverse=True)[:k]
    ideal = dcg([gain(rel, exponential) for rel in ideal_grades])
    return (got / ideal) if ideal else 0.0


# ----------------------------------------------------------- significance

def _percentile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile of an already-sorted sequence (q in 0..1)."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return sorted_values[low]
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)


def paired_bootstrap(baseline: Sequence[float], candidate: Sequence[float],
                     resamples: int = RESAMPLES, seed: int = SEED) -> Dict[str, float]:
    """Paired bootstrap over per-query deltas. Returns delta, p_value, 95% CI.

    Why paired and why bootstrap: the two arms answer the *same* queries, so the
    per-query difference cancels out "this query is just hard" and leaves the
    effect of the ranker change. Resampling those differences with replacement
    asks how often a different draw of queries would have reversed the sign —
    no normality assumption, which a 30-query golden set cannot support.

    ``p_value`` is one-sided *against the observed direction*, with the
    (count + 1)/(resamples + 1) correction so it can never be exactly 0:

        observed delta < 0 (a regression)  ->  P(resampled delta >= 0)
        observed delta > 0 (an improvement) ->  P(resampled delta <= 0)
        observed delta == 0                 ->  1.0

    So a regression with p < 0.05 is one that survives resampling — real, not an
    unlucky draw. Callers gate on (size of drop) AND (p < 0.05); see
    scripts/eval_gate.py.
    """
    if len(baseline) != len(candidate):
        raise ValueError("paired bootstrap needs equal-length score vectors "
                         "(%d vs %d)" % (len(baseline), len(candidate)))
    n = len(baseline)
    if n == 0:
        raise ValueError("paired bootstrap needs at least one paired score")

    diffs = [c - b for b, c in zip(baseline, candidate)]
    observed = sum(diffs) / n

    rng = random.Random(seed)  # noqa: S311 — resampling, not a security context
    means: List[float] = []
    for _ in range(resamples):
        total = 0.0
        for _ in range(n):
            total += diffs[rng.randrange(n)]
        means.append(total / n)
    means.sort()

    if observed < 0:
        extreme = sum(1 for m in means if m >= 0)
    elif observed > 0:
        extreme = sum(1 for m in means if m <= 0)
    else:
        return {"delta": 0.0, "p_value": 1.0, "ci_low": 0.0, "ci_high": 0.0,
                "resamples": float(resamples), "n": float(n)}

    return {
        "delta": observed,
        "p_value": (extreme + 1) / (resamples + 1),
        "ci_low": _percentile(means, 0.025),
        "ci_high": _percentile(means, 0.975),
        "resamples": float(resamples),
        "n": float(n),
    }


# --------------------------------------------------------------- the suite

def score_query(ranked: Sequence[str], labels: Mapping[str, int]) -> Dict[str, float]:
    """The five headline metrics for one query, over one ranked list."""
    ranked = dedupe(ranked)
    return {
        "recall@5": recall_at_k(ranked, labels, 5),
        "recall@10": recall_at_k(ranked, labels, 10),
        "MRR": reciprocal_rank(ranked, labels),
        "nDCG@5": ndcg_at_k(ranked, labels, 5),
        "nDCG@10": ndcg_at_k(ranked, labels, 10),
    }


#: Report order for the five headline metrics.
METRIC_NAMES = ("recall@5", "recall@10", "MRR", "nDCG@5", "nDCG@10")


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
