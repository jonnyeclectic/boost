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
  baseline  --save-baseline pins current scores; later runs flag regressions.
            Baselines are keyed by query set (name + content digest), because a
            baseline is a statement about a specific list of questions: grading
            the natural-language set against the keyword set's numbers reported
            eight confident regressions that were only the difference between
            two question sets.
  gate      --fail-under floors mean recall@k; --floor NAME=VALUE floors any
            metric and is repeatable. recall alone could not fail a build for a
            ranker scoring recall@10 1.000 with hit@1 0.000 — always finding the
            answer, never ranking it first (a `make eval` target).

Tier 1b (opt-in, offline): --stats runs a paired Student's t-test between the
engines with `ranx`, so a metric gap is reported as statistically *significant*
or not — a raw recall-vs-recall number can't say whether an engine is genuinely
better or just luckier on the golden set. Needs the [eval] extra; degrades
cleanly if `ranx` is absent (never a core dependency). A scheduled CI monitor
(.github/workflows/eval-stats.yml) runs this and reports each metric's p-value.

Tier 2a (LLM, opt-in, key-gated): --rerank measures the *lift* the LLM rerank
stage (rag.rerank) adds over the raw BM25 order on the same golden set — no
judge needed, the labels do the grading. Skips cleanly when AI is unavailable,
mirroring boost's BOOST_NO_AI contract.

Usage:
  python3 scripts/eval_retrieval.py --build            # build index, then eval
  python3 scripts/eval_retrieval.py --save-baseline    # pin a baseline
  python3 scripts/eval_retrieval.py --fail-under 0.85  # CI gate on recall@k
  python3 scripts/eval_retrieval.py --floor hit@1=0.65 # gate any metric
  python3 scripts/eval_retrieval.py --build --stats    # Tier 1b significance
  python3 scripts/eval_retrieval.py --rerank           # Tier 2a rerank lift
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

# Run from a source checkout without an install.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boost_cli.core import ai, catalog, dense, rag

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GOLDEN = ROOT / "tests" / "eval" / "golden.jsonl"
BASELINE = ROOT / "tests" / "eval" / "baseline.json"
KINDS = ("skill", "rule", "workflow")

# Rankers yield catalog ENTRIES, not names: the grading key depends on the
# row being graded (a name, or a content class when it pins an exemplar),
# so the ranker cannot decide it.
Ranker = Callable[[str], list[dict]]


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


METRICS: dict[str, Callable[[Sequence[str], set, int], float]] = {
    "recall@k": lambda r, rel, k: recall_at_k(r, rel, k),
    "hit@1": lambda r, rel, k: hit_at_1(r, rel),
    "MRR": lambda r, rel, k: reciprocal_rank(r, rel),
    "nDCG@k": lambda r, rel, k: ndcg_at_k(r, rel, k),
}


# --------------------------------------------------------------- data + engines

# --------------------------------------------------------------- grading keys
# Grading was by NAME, and names here are not identifying: measured over a real
# 71,655-entry catalogue, 35 of the 53 golden target names resolve to more than
# one body, and `code-reviewer` alone is 79 copies across 59 distinct skills. A
# query graded against that name scored a hit when any of the 59 ranked first,
# so every number was an upper bound.
#
# A row may now pin an `exemplar` — "tap::skill_md", the entry the query was
# actually written about. Grading then runs on the CONTENT CLASS of that entry:
# byte-identical mirrors from other registries still count (refusing them would
# punish a correct answer for arriving from a mirror), while a different skill
# sharing the name does not.
#
# Rows without an exemplar still decide RELEVANCE by name, so the sets can
# migrate a row at a time. What is no longer name-keyed is IDENTITY: the ranked
# list de-duplicates on the content hash for every row, exemplar or not. Keying
# both on the name collapsed 13 different `code-reviewer`s into one rank slot
# and inflated recall@10 by about one query (0.863 -> 0.852 over the pinned
# corpus); keying an exemplar row's distractors on tap::skill_md did the
# opposite, giving byte-identical mirrors a slot each. Mixed sets could not be
# averaged into one number until both used the same convention.

_EXEMPLAR_SEP = "::"


def prepare_row(row: dict, hashes: dict) -> dict:
    """Attach grading state to a golden row. Raises on an unresolvable exemplar.

    Failing loudly is the point: a silent fall back to name grading would turn a
    typo into a quietly weaker gate that still reports a number.
    """
    row = dict(row)
    row["relevant_set"] = set(row["relevant"])
    row.setdefault("kind", "skill")
    spec = row.get("exemplar")
    if not spec:
        row["class_hashes"] = None
        return row
    specs = [spec] if isinstance(spec, str) else list(spec)
    classes = set()
    for one in specs:
        if _EXEMPLAR_SEP not in one:
            raise SystemExit(
                "golden exemplar %r must be 'tap%sskill_md'" % (one, _EXEMPLAR_SEP))
        tap, path = one.split(_EXEMPLAR_SEP, 1)
        digest = hashes.get((tap, path))
        if not digest:
            raise SystemExit(
                "golden exemplar %r resolves to no indexed entry — check the "
                "tap is cloned and the path is exact" % one)
        classes.add(digest)
    row["class_hashes"] = classes
    return row


def grade_key(row: dict, entry: dict, hashes: dict) -> str:
    """The token this entry contributes to a ranked list, for scoring.

    The key does two jobs, and they need different answers. It decides whether
    an entry is RELEVANT — by name, or by content class when the row pins an
    exemplar — and it is the IDENTITY the ranked list is de-duplicated on.

    Keying both on the name conflated them: 13 genuinely different skills named
    `code-reviewer` collapsed into one rank slot, so the eval credited the
    ranker with a compression that exists only here. Measured over the pinned
    corpus that was worth about one query of recall@10 (0.863 against 0.852).
    Exemplar rows had the inverse bug — their distractors keyed on
    ``tap::skill_md``, so byte-identical mirrors each took a slot and pushed the
    target later.

    So: relevance by name or class, identity always by content hash. One
    convention for every row, which is what allows an exemplar-graded row and a
    name-graded row to be averaged into the same number.

    ``hashes`` is passed rather than read from module state: the map is the
    thing that decides whether two entries are the same skill, so a caller must
    not be able to grade against a different one by accident.
    """
    digest = hashes.get((entry.get("tap", ""), entry.get("skill_md", "")))
    classes = row.get("class_hashes")
    if classes:
        if digest and digest in classes:
            return "cls:%s" % sorted(classes)[0]
    elif str(entry.get("name", "")) in row["relevant_set"]:
        return str(entry.get("name", ""))
    if digest:
        return "body:%s" % digest
    # No hash (an entry the index never saw): fall back to a key that is unique
    # per entry. Colliding here would silently shorten the ranked list and
    # flatter every metric computed from it.
    return "nohash:%s::%s" % (entry.get("tap", ""), entry.get("skill_md", ""))


def relevant_keys(row: dict) -> set:
    classes = row.get("class_hashes")
    if not classes:
        return set(row["relevant_set"])
    return {"cls:%s" % sorted(classes)[0]}


def exemplar_worksheet(rows: list[dict], entries: list[dict],
                       hashes: dict) -> list[dict]:
    """Rows still graded by name whose name resolves to several bodies.

    Pinning those is a judgment about what the question meant, not a lookup, so
    this hands over the menu rather than guessing: for each undecided row, every
    distinct body a relevant name resolves to, with its description.

    Generated rather than committed as a comment in the golden file, because the
    candidate list is a fact about the corpus that is currently tapped. Written
    down, it would be wrong the first time a pin moves.
    """
    by_name: dict[str, list[dict]] = {}
    for entry in entries:
        by_name.setdefault(str(entry.get("name", "")), []).append(entry)
    sheet: list[dict] = []
    for row in rows:
        if row.get("class_hashes"):
            continue                       # already decided
        seen: dict[str, dict] = {}
        for name in row["relevant_set"]:
            for entry in by_name.get(name, []):
                digest = hashes.get((entry.get("tap", ""), entry.get("skill_md", "")))
                if digest and digest not in seen:
                    seen[digest] = entry
        if len(seen) < 2:
            continue                       # determined, or absent entirely
        sheet.append({
            "query": row["query"],
            "candidates": [
                {"spec": "%s%s%s" % (e.get("tap", ""), _EXEMPLAR_SEP,
                                     e.get("skill_md", "")),
                 "description": (e.get("description") or "").strip().split("\n")[0]}
                for e in sorted(seen.values(),
                                key=lambda x: (x.get("tap", ""), x.get("skill_md", "")))
            ],
        })
    return sheet


def dedupe_keys(keys):
    """Collapse to the first (best-ranked) occurrence of each key."""
    seen: set = set()
    out: list[str] = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def load_golden(path: Path, hashes: dict | None = None) -> list[dict]:
    # One pass over the BM25 index, not one per row.
    hashes = rag.content_hashes() if hashes is None else hashes
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(prepare_row(json.loads(line), hashes))
    if not rows:
        raise SystemExit("no golden cases in %s" % path)
    return rows


def catalog_ranker(k: int) -> Ranker:
    return lambda q: [e for e, _s in catalog.search(q)]


def bm25_ranker(k: int) -> Ranker:
    return lambda q: [h["entry"] for h in rag.retrieve(q, k=max(k * 4, 60))]


def dense_ranker(k: int) -> Ranker:
    return lambda q: [h["entry"] for h in (dense.retrieve(q, k=max(k * 4, 60)) or [])]


def hybrid_ranker(k: int) -> Ranker:
    """BM25 and dense fused by reciprocal rank (rag.rrf_fuse).

    Measured as its own engine rather than inferred from the other two: a
    hybrid win must not be creditable to whichever component did not earn it,
    which is why each engine is also reported alone.
    """
    def rank(q: str) -> list[str]:
        pool = max(k * 4, 60)
        b = rag.retrieve(q, k=pool)
        d = dense.retrieve(q, k=pool) or []
        return [h["entry"] for h in rag.rrf_fuse([b, d], limit=pool)]
    return rank


def rerank_ranker(k: int) -> Ranker:
    """BM25 shortlist reordered by the LLM rerank stage (Tier 2a).

    The rerank cache is disabled for the whole run: a graded rerank must be
    live, or the eval silently measures a stale cached order.
    """
    os.environ["BOOST_NO_RERANK_CACHE"] = "1"
    def rank(q: str) -> list[str]:
        hits = rag.retrieve(q, k=max(k * 4, 60))
        reranked, _label = rag.rerank(q, hits, limit=max(k, 15))
        return [h["entry"] for h in reranked]
    return rank


# --------------------------------------------------------------- eval loop

def evaluate(rows: list[dict], ranker: Ranker, k: int) -> tuple[list[dict], dict]:
    """Run every golden query through `ranker`; return per-case + aggregates."""
    per_case: list[dict] = []
    hashes = rag.content_hashes()
    for row in rows:
        entries = ranker(row["query"])
        ranked = dedupe_keys([grade_key(row, e, hashes) for e in entries])
        rel = relevant_keys(row)
        per_case.append({
            "query": row["query"], "kind": row["kind"],
            "relevant": sorted(rel), "top": ranked[:k],
            "rank": _first_rank(ranked, rel),
            "scores": {m: fn(ranked, rel, k) for m, fn in METRICS.items()},
        })
    return per_case, _aggregate(per_case)


def _aggregate(per_case: list[dict]) -> dict:
    overall = {m: _mean(c["scores"][m] for c in per_case) for m in METRICS}
    by_kind: dict[str, dict] = {}
    for kind in KINDS:
        cases = [c for c in per_case if c["kind"] == kind]
        if cases:
            by_kind[kind] = {
                "n": len(cases),
                "recall@k": _mean(c["scores"]["recall@k"] for c in cases),
                "hit@1": _mean(c["scores"]["hit@1"] for c in cases),
            }
    return {"overall": overall, "by_kind": by_kind}


def _first_rank(ranked: Sequence[str], relevant: set) -> int | None:
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


def print_compare(k: int, results: list[dict]) -> None:
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


def print_misses(engine: str, per_case: list[dict], k: int) -> None:
    misses = [c for c in per_case if c["rank"] != 1]
    if not misses:
        return
    print("\n--- %s: not ranked #1 (%d) ---" % (engine, len(misses)))
    for c in misses:
        where = ("@%d" % c["rank"]) if c["rank"] else "MISS(>k)"
        print("  %-6s %-52s -> %s" % (where, c["query"][:52],
                                      ", ".join(c["top"][:4])))


# --------------------------------------------------------------- baseline

def load_baseline() -> dict | None:
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def golden_key(golden: Path) -> str:
    """Identity of a query set: its name plus a digest of its contents.

    A baseline is a set of numbers about a specific list of questions, so it is
    only comparable to a run over that same list. Keying on the *content* and
    not just the filename matters because editing a query in place changes what
    the numbers mean while leaving the path identical.
    """
    try:
        digest = hashlib.sha256(golden.read_bytes()).hexdigest()[:12]
    except OSError:
        digest = "missing"
    return "%s@%s" % (golden.name, digest)


def baseline_for(golden: Path) -> dict | None:
    """The recorded numbers for this query set, or None if there are none.

    Reads the current keyed layout and the original flat one. A flat baseline
    predates multi-set support, so it can only have come from the default
    keyword set — applying it to any other set is what produced eight confident
    but meaningless "REGRESSION" lines when the natural-language set was run.
    """
    base = load_baseline()
    if not base:
        return None
    if "sets" in base:
        entry = base["sets"].get(golden_key(golden))
        return entry if isinstance(entry, dict) else None
    if golden.name == DEFAULT_GOLDEN.name:
        return base
    return None


def stale_keys(keys: Iterable[str], fresh: str) -> list[str]:
    """Keys for the same query set at a *different* digest, sorted.

    A key is ``name@digest``, and the digest only changes when the file does.
    So an old key can never be read again unless someone reverts the query set
    byte for byte — it is dead weight that accumulates one entry per edit. This
    is what decides which entries a save drops.

    Matching is on the name half only. Splitting on the last ``@`` rather than
    the first keeps a filename containing ``@`` from being mistaken for another
    set and silently surviving forever.
    """
    name = fresh.rsplit("@", 1)[0]
    return sorted(k for k in keys
                  if k != fresh and k.rsplit("@", 1)[0] == name)


def save_baseline(k: int, results: list[dict], golden: Path) -> None:
    """Pin this run's scores under its query set, leaving other sets alone."""
    payload = load_baseline() or {}
    if "sets" not in payload:
        # Migrate a flat baseline in place rather than dropping it: it is the
        # keyword set's history and is still the thing `make eval` compares to.
        migrated = {}
        if payload.get("engines"):
            migrated[golden_key(DEFAULT_GOLDEN)] = payload
        payload = {"sets": migrated}
    # Drop this set's superseded entries. Other sets are untouched — that
    # separation is the whole point of the keyed layout.
    for dead in stale_keys(payload["sets"], golden_key(golden)):
        del payload["sets"][dead]
        print("dropped superseded baseline %s" % dead)
    payload["sets"][golden_key(golden)] = {
        "k": k,
        "golden": golden.name,
        "engines": {r["engine"]: r["agg"]["overall"] for r in results},
    }
    BASELINE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    # relative_to raises when BASELINE has been pointed outside the repo, which
    # is how the unit tests isolate it — the path is cosmetic, so degrade to it.
    try:
        shown = BASELINE.relative_to(ROOT)
    except ValueError:
        shown = BASELINE
    print("\nbaseline written -> %s (%s)" % (shown, golden.name))


def parse_floors(pairs: Sequence[str]) -> dict[str, float]:
    """Turn `--floor name=value` arguments into a metric -> minimum mapping."""
    floors: dict[str, float] = {}
    for raw in pairs:
        name, sep, value = raw.partition("=")
        if not sep:
            raise SystemExit("--floor needs NAME=VALUE, got %r" % raw)
        metric = name.strip()
        # Validated here rather than only at gate time so a typo fails before
        # the run, not after several minutes of tapping and retrieval.
        if metric not in METRICS:
            raise SystemExit("unknown metric %r in --floor (known: %s)"
                             % (metric, ", ".join(sorted(METRICS))))
        try:
            floors[metric] = float(value)
        except ValueError:
            # A usage error: the ValueError context is noise, not evidence.
            raise SystemExit(
                "--floor %s: %r is not a number" % (name, value)) from None
    return floors


def check_floors(result: dict, floors: dict[str, float]) -> list[str]:
    """Every metric below its floor, not just the first.

    `--fail-under` floored `recall@k` alone, so a ranker that found the right
    answer every time and never ranked it first — recall@10 1.000, hit@1 0.000 —
    passed the gate. All four metrics are already computed and printed; the only
    thing missing was the ability to fail on them.
    """
    overall = result["agg"]["overall"]
    breaches: list[str] = []
    for metric, minimum in sorted(floors.items()):
        if metric not in METRICS:
            raise SystemExit("unknown metric %r in --floor (known: %s)"
                             % (metric, ", ".join(sorted(METRICS))))
        got = overall[metric]
        if got < minimum:
            breaches.append("%s = %.3f  (min %.3f)" % (metric, got, minimum))
    return breaches


def check_regressions(results: list[dict], eps: float,
                      golden: Path) -> list[str]:
    base = baseline_for(golden)
    if not base:
        return []
    problems: list[str] = []
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

def run_rerank_lift(rows: list[dict], k: int, json_out: bool) -> int:
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

def _stats_metrics(k: int) -> list[str]:
    return ["recall@%d" % k, "hit_rate@1", "mrr", "ndcg@%d" % k]


def build_stats_report(per_cases: dict[str, list[dict]], rows: list[dict],
                       k: int, order: list[str]):
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

    qrels = Qrels({"q%d" % i: dict.fromkeys(row["relevant_set"], 1)
                   for i, row in enumerate(rows)})
    runs = []
    for label in order:
        run_d: dict[str, dict[str, float]] = {}
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


def print_stats_human(report, order: list[str], k: int) -> None:
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

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    ap.add_argument("-k", type=int, default=10, help="cutoff for @k metrics")
    ap.add_argument("--engines", default="auto",
                    help="comma list of catalog,bm25,dense,hybrid (default: auto)")
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
    ap.add_argument("--floor", action="append", default=[], metavar="NAME=VAL",
                    help="floor a metric, repeatable (e.g. --floor hit@1=0.65). "
                         "Unlike --fail-under this works on any metric.")
    ap.add_argument("--misses", action="store_true", help="list non-#1 cases")
    ap.add_argument("--stats", action="store_true",
                    help="Tier 1b: ranx significance test between engines "
                         "(opt-in [eval] extra; degrades if ranx absent)")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON")
    ap.add_argument("--worksheet", action="store_true",
                    help="list the golden rows still graded by name whose name "
                         "resolves to several bodies, with the candidates")
    args = ap.parse_args(argv)

    floors = parse_floors(args.floor)          # fail fast on a bad --floor
    rows = load_golden(args.golden)

    if args.build or not rag.ready():
        if not args.json:
            print("building BM25 index over the tapped catalog ...", flush=True)
        stats = rag.build(catalog.all_entries(), force=args.build)
        if not args.json:
            print("  indexed %d entries -> %d chunks across %d taps"
                  % (stats["entries"], stats["docs"], stats["taps"]))

    if args.worksheet:
        sheet = exemplar_worksheet(rows, catalog.all_entries(), rag.content_hashes())
        if args.json:
            print(json.dumps(sheet, indent=2))
            return 0
        print("%d of %d rows still graded by name resolve to several bodies.\n"
              % (len(sheet), len(rows)))
        for case in sheet:
            print("  %s" % case["query"])
            for cand in case["candidates"]:
                print("      %s" % cand["spec"])
                if cand["description"]:
                    print("          %s" % cand["description"][:96])
            print()
        return 0

    if args.rerank:
        return run_rerank_lift(rows, args.k, args.json)

    # ---- Tier 1: engine comparison ----
    wanted = ["catalog", "bm25"] if args.engines == "auto" \
        else [e.strip() for e in args.engines.split(",") if e.strip()]
    if ((args.engines == "auto" or "dense" in wanted) and dense.ready()
            and "dense" not in wanted):
        wanted.append("dense")
    if ((args.engines == "auto" or "hybrid" in wanted) and dense.ready()
            and "hybrid" not in wanted):
        wanted.append("hybrid")
    factory = {"catalog": catalog_ranker, "bm25": bm25_ranker,
               "dense": dense_ranker, "hybrid": hybrid_ranker}
    labels = {"catalog": "catalog.search", "bm25": "BM25 full-content",
              "dense": "dense vectors", "hybrid": "hybrid RRF"}

    results: list[dict] = []
    per_cases: dict[str, list[dict]] = {}
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
        save_baseline(args.k, results, args.golden)

    # ---- gates ----
    exit_code = 0
    primary = results[-1]                       # BM25 is the always-on baseline
    problems = check_regressions(results, args.regression_eps, args.golden)
    if problems and not args.save_baseline:
        print("\nREGRESSION vs baseline:", file=sys.stderr)
        for p in problems:
            print("  - %s" % p, file=sys.stderr)
        exit_code = 1
    # --fail-under is the original recall-only gate, kept so existing callers
    # keep working; --floor is the general form and can gate any metric.
    if args.fail_under is not None:
        floors.setdefault("recall@k", args.fail_under)
    if floors:
        breaches = check_floors(primary, floors)
        if not args.json:
            print("\nGATE %s (k=%d)" % (primary["engine"], args.k))
            for metric, minimum in sorted(floors.items()):
                got = primary["agg"]["overall"][metric]
                print("  %-9s %.3f  (min %.3f)  ->  %s"
                      % (metric, got, minimum,
                         "PASS" if got >= minimum else "FAIL"))
        if breaches:
            print("\nFLOOR BREACHED:", file=sys.stderr)
            for b in breaches:
                print("  - %s" % b, file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
