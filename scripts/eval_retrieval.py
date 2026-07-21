#!/usr/bin/env python3
"""Golden-set retrieval eval for boost's RAG engines.

Tier 1 (deterministic given a pinned corpus): grades the always-on retrieval
stack against a fixed set of query -> expected-skill judgments. The judgments
name real catalog items, so the corpus must contain them — CI and `make eval`
first tap the pinned repo list (tests/eval/taps.txt) via
scripts/ensure_eval_corpus.sh. It is the semantic-quality gate
the exact-arithmetic unit tests in tests/unit/test_rag.py cannot be — those pin
the math, this asks "does the right skill actually come back for a real question."

  engines   catalog.search (frontmatter baseline) · rag.retrieve (BM25) ·
            dense.retrieve (cosine, auto-skipped when no embeddings provider)
  metrics   recall@k · hit@1 · MRR · nDCG@k  (binary relevance, averaged;
            also sliced per item kind: skill / rule / workflow)
  baseline  --save-baseline pins current scores; later runs flag regressions
  gate      --fail-under floors mean recall@k for CI (a `make eval` target)

Tier 1b (opt-in, offline): --stats runs a paired Student's t-test between the
engines with `ranx`, so a metric gap is reported as statistically *significant*
or not — a raw 0.919-vs-0.756 number can't say whether an engine is genuinely
better or just luckier on 43 queries. Needs the [eval] extra; degrades cleanly
if `ranx` is absent (never a core dependency).

Tier 2a (LLM, opt-in, key-gated): --rerank measures the *lift* the LLM rerank
stage (rag.rerank) adds over the raw BM25 order on the same golden set — no
judge needed, the labels do the grading. Skips cleanly when AI is unavailable,
mirroring boost's BOOST_NO_AI contract.

Usage:
  python3 scripts/eval_retrieval.py --build            # build index, then eval
  python3 scripts/eval_retrieval.py --save-baseline    # pin a baseline
  python3 scripts/eval_retrieval.py --fail-under 0.85  # CI gate on recall@k
  python3 scripts/eval_retrieval.py --build --stats    # Tier 1b significance
  python3 scripts/eval_retrieval.py --rerank           # Tier 2a rerank lift
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# Run from a source checkout without an install.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boost_cli.core import ai, catalog, dense, rag  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GOLDEN = ROOT / "tests" / "eval" / "golden.jsonl"
BASELINE = ROOT / "tests" / "eval" / "baseline.json"
KINDS = ("skill", "rule", "workflow")

Ranker = Callable[[str], List[str]]


# --------------------------------------------------------------- metrics
# Pure functions over a ranked list of names and the set of relevant names.
# `ranked` is best-first (already de-duplicated by name); `relevant` is the
# gold set for one query.

def recall_at_k(ranked: Sequence[str], relevant: set, k: int) -> float:
    if not relevant:
        return 0.0
    found = len(set(ranked[:k]) & relevant)
    return found / len(relevant)


def hit_at_1(ranked: Sequence[str], relevant: set) -> float:
    return 1.0 if ranked and ranked[0] in relevant else 0.0


def reciprocal_rank(ranked: Sequence[str], relevant: set) -> float:
    for i, name in enumerate(ranked):
        if name in relevant:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(ranked: Sequence[str], relevant: set, k: int) -> float:
    dcg = 0.0
    for i, name in enumerate(ranked[:k]):
        if name in relevant:
            dcg += 1.0 / math.log2(i + 2)          # gain 1, discount log2(rank+1)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return (dcg / idcg) if idcg else 0.0


METRICS: Dict[str, Callable[[Sequence[str], set, int], float]] = {
    "recall@k": lambda r, rel, k: recall_at_k(r, rel, k),
    "hit@1": lambda r, rel, k: hit_at_1(r, rel),
    "MRR": lambda r, rel, k: reciprocal_rank(r, rel),
    "nDCG@k": lambda r, rel, k: ndcg_at_k(r, rel, k),
}


# --------------------------------------------------------------- data + engines

def load_golden(path: Path) -> List[dict]:
    rows: List[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        obj = json.loads(line)
        obj["relevant_set"] = set(obj["relevant"])
        obj.setdefault("kind", "skill")
        rows.append(obj)
    if not rows:
        raise SystemExit("no golden cases in %s" % path)
    return rows


def _dedupe(names: Sequence[str]) -> List[str]:
    """Collapse to first (best-ranked) occurrence of each name.

    The same skill name ships from several taps, so retrieval returns one hit
    per (name, tap); grading is by name, so a repeat would otherwise be counted
    twice (recall > 1).
    """
    seen: set = set()
    out: List[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def catalog_ranker(k: int) -> Ranker:
    return lambda q: _dedupe([e["name"] for e, _s in catalog.search(q)])


def bm25_ranker(k: int) -> Ranker:
    return lambda q: _dedupe(
        [h["entry"]["name"] for h in rag.retrieve(q, k=max(k * 4, 60))])


def dense_ranker(k: int) -> Ranker:
    return lambda q: _dedupe(
        [h["entry"]["name"] for h in (dense.retrieve(q, k=max(k * 4, 60)) or [])])


def rerank_ranker(k: int) -> Ranker:
    """BM25 shortlist reordered by the LLM rerank stage (Tier 2a)."""
    def rank(q: str) -> List[str]:
        hits = rag.retrieve(q, k=max(k * 4, 60))
        reranked, _label = rag.rerank(q, hits, limit=max(k, 15))
        return _dedupe([h["entry"]["name"] for h in reranked])
    return rank


# --------------------------------------------------------------- eval loop

def evaluate(rows: List[dict], ranker: Ranker, k: int) -> Tuple[List[dict], dict]:
    """Run every golden query through `ranker`; return per-case + aggregates."""
    per_case: List[dict] = []
    for row in rows:
        ranked = ranker(row["query"])
        rel = row["relevant_set"]
        per_case.append({
            "query": row["query"], "kind": row["kind"],
            "relevant": sorted(rel), "top": ranked[:k],
            "rank": _first_rank(ranked, rel),
            "scores": {m: fn(ranked, rel, k) for m, fn in METRICS.items()},
        })
    return per_case, _aggregate(per_case)


def _aggregate(per_case: List[dict]) -> dict:
    overall = {m: _mean(c["scores"][m] for c in per_case) for m in METRICS}
    by_kind: Dict[str, dict] = {}
    for kind in KINDS:
        cases = [c for c in per_case if c["kind"] == kind]
        if cases:
            by_kind[kind] = {
                "n": len(cases),
                "recall@k": _mean(c["scores"]["recall@k"] for c in cases),
                "hit@1": _mean(c["scores"]["hit@1"] for c in cases),
            }
    return {"overall": overall, "by_kind": by_kind}


def _first_rank(ranked: Sequence[str], relevant: set) -> Optional[int]:
    for i, name in enumerate(ranked):
        if name in relevant:
            return i + 1
    return None


def _mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


# --------------------------------------------------------------- reporting

def _row(label: str, m: dict) -> str:
    return "  %-22s %8.3f %8.3f %8.3f %8.3f" % (
        label, m["recall@k"], m["hit@1"], m["MRR"], m["nDCG@k"])


def print_compare(k: int, results: List[dict]) -> None:
    print("\n=== engine comparison (k=%d, %d queries) ===" % (k, results[0]["n"]))
    print("  %-22s %8s %8s %8s %8s" % ("engine", "recall", "hit@1", "MRR", "nDCG"))
    for r in results:
        print(_row(r["engine"], r["agg"]["overall"]))
    # per-kind recall@k / hit@1 for the primary (last) engine
    primary = results[-1]
    print("\n=== %s by kind ===" % primary["engine"])
    for kind, m in primary["agg"]["by_kind"].items():
        print("  %-10s n=%-3d recall@k=%.3f  hit@1=%.3f"
              % (kind, m["n"], m["recall@k"], m["hit@1"]))


def print_misses(engine: str, per_case: List[dict], k: int) -> None:
    misses = [c for c in per_case if c["rank"] != 1]
    if not misses:
        return
    print("\n--- %s: not ranked #1 (%d) ---" % (engine, len(misses)))
    for c in misses:
        where = ("@%d" % c["rank"]) if c["rank"] else "MISS(>k)"
        print("  %-6s %-52s -> %s" % (where, c["query"][:52],
                                      ", ".join(c["top"][:4])))


# --------------------------------------------------------------- baseline

def load_baseline() -> Optional[dict]:
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_baseline(k: int, results: List[dict]) -> None:
    payload = {"k": k, "engines": {r["engine"]: r["agg"]["overall"]
                                   for r in results}}
    BASELINE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("\nbaseline written -> %s" % BASELINE.relative_to(ROOT))


def check_regressions(results: List[dict], eps: float) -> List[str]:
    base = load_baseline()
    if not base:
        return []
    problems: List[str] = []
    for r in results:
        prev = base.get("engines", {}).get(r["engine"])
        if not prev:
            continue
        for m in METRICS:
            drop = prev.get(m, 0.0) - r["agg"]["overall"][m]
            if drop > eps:
                problems.append("%s %s: %.3f -> %.3f (-%.3f)"
                                % (r["engine"], m, prev[m],
                                   r["agg"]["overall"][m], drop))
    return problems


# --------------------------------------------------------------- Tier 2a

def run_rerank_lift(rows: List[dict], k: int, json_out: bool) -> int:
    """Compare raw BM25 vs LLM-reranked BM25 on the same golden set."""
    if not ai.available():
        print("rerank lift needs the `claude` CLI on PATH or ANTHROPIC_API_KEY "
              "— skipping (AI unavailable)", file=sys.stderr)
        return 0
    if not rag.ready():
        raise SystemExit("no BM25 index — run with --build first")

    print("scoring %d queries x2 (BM25 baseline vs LLM rerank) ..." % len(rows),
          file=sys.stderr, flush=True)
    _b, base = evaluate(rows, bm25_ranker(k), k)
    _r, rerank = evaluate(rows, rerank_ranker(k), k)

    if json_out:
        print(json.dumps({"k": k, "baseline": base["overall"],
                          "rerank": rerank["overall"]}, indent=2))
        return 0

    print("\n=== Tier 2a: rerank lift (k=%d, %d queries) ===" % (k, len(rows)))
    print("  %-22s %8s %8s %8s %8s" % ("arm", "recall", "hit@1", "MRR", "nDCG"))
    print(_row("BM25 (no rerank)", base["overall"]))
    print(_row("BM25 + LLM rerank", rerank["overall"]))
    lift = {m: rerank["overall"][m] - base["overall"][m] for m in METRICS}
    print("  %-22s %+8.3f %+8.3f %+8.3f %+8.3f"
          % ("lift", lift["recall@k"], lift["hit@1"], lift["MRR"], lift["nDCG@k"]))
    print("\nnote: recall is unchanged by design — rerank only reorders the "
          "retrieved shortlist. The lift lives in hit@1 / MRR / nDCG.")
    return 0


# --------------------------------------------------------------- Tier 1b (stats)

def _stats_metrics(k: int) -> List[str]:
    return ["recall@%d" % k, "hit_rate@1", "mrr", "ndcg@%d" % k]


def build_stats_report(per_cases: Dict[str, List[dict]], rows: List[dict],
                       k: int, order: List[str]):
    """Compare the engines with `ranx` + a paired Student's t-test; return the
    ranx Report, or None if unavailable.

    A raw metric gap ("BM25 0.919 vs 0.756") doesn't say whether the engine is
    actually better or just luckier on 43 queries. The t-test says whether the
    difference is *significant*. Reuses the already-computed Tier 1 rankings —
    no re-retrieval. Degrades cleanly when `ranx` is absent (an opt-in [eval]
    extra, never a core dependency), mirroring boost's offline-first contract.
    """
    try:
        from ranx import Qrels, Run, compare
    except ImportError:
        print("\n--stats needs `ranx` — `pip install boost-skill-cli[eval]` "
              "(or `pip install ranx`); skipping.", file=sys.stderr)
        return None
    if len(order) < 2:
        print("\n--stats needs >=2 engines to compare — skipping.",
              file=sys.stderr)
        return None

    qrels = Qrels({"q%d" % i: {n: 1 for n in row["relevant_set"]}
                   for i, row in enumerate(rows)})
    runs = []
    for label in order:
        run_d: Dict[str, Dict[str, float]] = {}
        for i, pc in enumerate(per_cases[label]):
            top = pc["top"]
            # position-derived descending scores: ranx orders docs by score, so
            # this reproduces the engine's ranking (the @k metrics depend only
            # on the order, not the raw retrieval scores).
            run_d["q%d" % i] = ({n: float(len(top) - p)
                                 for p, n in enumerate(top)}
                                if top else {"__none__": 0.0})
        runs.append(Run(run_d, name=label))

    return compare(qrels, runs, metrics=_stats_metrics(k),
                   stat_test="student", make_comparable=True)


def print_stats_human(report, order: List[str], k: int) -> None:
    print("\n=== Tier 1b: statistical significance (ranx · paired t-test) ===")
    print(report)
    # Plain-language verdict for the best engine vs each other, at p<0.05.
    d = report.to_dict()
    rkey = "recall@%d" % k
    best = max(order, key=lambda m: d[m]["scores"].get(rkey, 0.0))
    print("\nbest engine: %s" % best)
    for other in order:
        if other == best:
            continue
        for metric in _stats_metrics(k):
            p = d[best]["comparisons"][other][metric]
            wtl = d[best]["win_tie_loss"][other][metric]
            verdict = "SIGNIFICANT" if p < 0.05 else "not significant"
            print("  vs %-20s %-12s p=%.4f  %-15s  W/T/L=%d/%d/%d"
                  % (other, metric, p, verdict, wtl["W"], wtl["T"], wtl["L"]))


# --------------------------------------------------------------- main

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    ap.add_argument("-k", type=int, default=10, help="cutoff for @k metrics")
    ap.add_argument("--engines", default="auto",
                    help="comma list of catalog,bm25,dense (default: auto)")
    ap.add_argument("--build", action="store_true",
                    help="(re)build the BM25 index before evaluating")
    ap.add_argument("--rerank", action="store_true",
                    help="Tier 2a: measure LLM rerank lift over BM25")
    ap.add_argument("--save-baseline", action="store_true",
                    help="pin current scores to tests/eval/baseline.json")
    ap.add_argument("--fail-under", type=float, default=None, metavar="X",
                    help="exit 1 if primary-engine mean recall@k < X")
    ap.add_argument("--regression-eps", type=float, default=0.02, metavar="E",
                    help="fail if any metric drops > E below the baseline")
    ap.add_argument("--misses", action="store_true", help="list non-#1 cases")
    ap.add_argument("--stats", action="store_true",
                    help="Tier 1b: ranx significance test between engines "
                         "(opt-in [eval] extra; degrades if ranx absent)")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON")
    args = ap.parse_args(argv)

    rows = load_golden(args.golden)

    if args.build or not rag.ready():
        if not args.json:
            print("building BM25 index over the tapped catalog ...", flush=True)
        stats = rag.build(catalog.all_entries(), force=args.build)
        if not args.json:
            print("  indexed %d entries -> %d chunks across %d taps"
                  % (stats["entries"], stats["docs"], stats["taps"]))

    if args.rerank:
        return run_rerank_lift(rows, args.k, args.json)

    # ---- Tier 1: engine comparison ----
    wanted = ["catalog", "bm25"] if args.engines == "auto" \
        else [e.strip() for e in args.engines.split(",") if e.strip()]
    if (args.engines == "auto" or "dense" in wanted) and dense.ready():
        if "dense" not in wanted:
            wanted.append("dense")
    factory = {"catalog": catalog_ranker, "bm25": bm25_ranker,
               "dense": dense_ranker}
    labels = {"catalog": "catalog.search", "bm25": "BM25 full-content",
              "dense": "dense vectors"}

    results: List[dict] = []
    per_cases: Dict[str, List[dict]] = {}
    for name in wanted:
        if name == "dense" and not dense.ready():
            print("dense engine not ready (needs [rag] extra + embeddings) — "
                  "skipping", file=sys.stderr)
            continue
        if name not in factory:
            raise SystemExit("unknown engine: %s" % name)
        pc, agg = evaluate(rows, factory[name](args.k), args.k)
        results.append({"engine": labels[name], "agg": agg, "n": len(rows)})
        per_cases[labels[name]] = pc

    if not results:
        raise SystemExit("no engines evaluated")

    order = [r["engine"] for r in results]
    if args.json:
        payload: dict = {"k": args.k, "results":
                         [{"engine": r["engine"], **r["agg"]} for r in results]}
        if args.stats:
            report = build_stats_report(per_cases, rows, args.k, order)
            if report is not None:
                payload["significance"] = report.to_dict()
        print(json.dumps(payload, indent=2, default=str))
    else:
        print_compare(args.k, results)
        if args.misses:
            print_misses(results[-1]["engine"], per_cases[results[-1]["engine"]],
                         args.k)
        if args.stats:
            report = build_stats_report(per_cases, rows, args.k, order)
            if report is not None:
                print_stats_human(report, order, args.k)

    if args.save_baseline:
        save_baseline(args.k, results)

    # ---- gates ----
    exit_code = 0
    primary = results[-1]                       # BM25 is the always-on baseline
    problems = check_regressions(results, args.regression_eps)
    if problems and not args.save_baseline:
        print("\nREGRESSION vs baseline:", file=sys.stderr)
        for p in problems:
            print("  - %s" % p, file=sys.stderr)
        exit_code = 1
    if args.fail_under is not None:
        got = primary["agg"]["overall"]["recall@k"]
        ok = got >= args.fail_under
        if not args.json:
            print("\nGATE recall@%d = %.3f  (min %.3f)  ->  %s"
                  % (args.k, got, args.fail_under, "PASS" if ok else "FAIL"))
        if not ok:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
