#!/usr/bin/env python3
"""Run boost's retrieval evaluation over the hermetic golden set.

Grades the shipped ranker (`boost search`'s BM25 engine, core/rag.py) against
evals/golden_set.json on five metrics — recall@5, recall@10, MRR, nDCG@5,
nDCG@10 — and writes a machine-readable result file for scripts/eval_gate.py to
enforce. The frontmatter engine (core/catalog.search) is scored alongside it as a
reference arm, so a BM25 change that quietly drops below the naive baseline is
visible rather than merely "a bit lower than last time".

Hermetic by default: it generates its own corpus (evals/make_corpus.py), taps it
into a disposable BOOST_HOME, and builds the index there. No network, no API key,
no contact with the developer's real ~/.boost. That is the whole point — a metric
moving must mean the ranker moved, not that a GitHub repo did.

  --online   additionally score the *pinned real-registry* corpus that
             `make eval` uses (tests/eval/taps.txt + tests/eval/golden.jsonl)
             with the same five metrics. Needs the network; reported, never
             gated — same spirit as tests/smoke.sh --online.

Usage:
  python3 evals/run_evals.py                      # run + write evals/results.json
  python3 evals/run_evals.py --save-baseline      # pin the current scores
  python3 evals/run_evals.py --misses             # show what ranked badly
  python3 evals/run_evals.py --faithfulness       # add the Ragas-style Tier 2
  python3 evals/run_evals.py --online             # + real-registry corpus
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals import make_corpus, metrics  # noqa: E402

GOLDEN = ROOT / "evals" / "golden_set.json"
BASELINE = ROOT / "evals" / "baseline.json"
RESULTS = ROOT / "evals" / "results.json"
# Disposable BOOST_HOME for the corpus + index. Lives in the system temp dir,
# not the repo: it holds git clones, and a nested repo inside the project trips
# `git status`, coverage discovery, and mutmut's tree copy. Override with
# BOOST_EVALS_HOME or --home.
DEFAULT_HOME = Path(os.environ.get("BOOST_EVALS_HOME")
                    or Path(tempfile.gettempdir()) / "boost-evals-home")

# The arm the gate enforces. The other arm is context, not a gate.
PRIMARY = "bm25"
ARM_LABELS = {"catalog": "catalog.search (frontmatter)",
              "bm25": "BM25 full-content (shipped)"}

Ranker = Callable[[str], list[str]]


# ------------------------------------------------------------ sandbox setup

def prepare_home(home: Path, rebuild: bool = True) -> dict:
    """Generate the corpus, tap it into ``home``, and build the BM25 index.

    Sets BOOST_HOME (every boost path resolves from it at call time) and
    BOOST_NO_AI before any boost_cli call, so nothing here can reach the
    developer's real state or an LLM.
    """
    home.mkdir(parents=True, exist_ok=True)
    os.environ["BOOST_HOME"] = str(home)
    os.environ["BOOST_NO_AI"] = "1"       # deterministic: never call an LLM
    os.environ.setdefault("BOOST_NO_LOG", "1")

    from boost_cli.core import catalog, rag, registry

    corpus = make_corpus.build(home / make_corpus.CORPUS_DIRNAME)
    name, _url = registry.parse_spec(str(corpus))
    if not any(t.name == name for t in registry.list_taps()):
        tap = registry.add(str(corpus))
    else:
        tap = registry.get(name)
        registry.update(tap.name)
    entries = catalog.rebuild_tap(tap)
    stats = rag.build(catalog.all_entries(), force=rebuild)
    # A generator identity, not the absolute path it happened to be built at.
    # `corpus` lives under $TMPDIR, so serializing the resolved path baked one
    # machine's scratch directory into the committed baseline — a value that is
    # meaningless everywhere else and ships in the PyPI sdist. The online arm
    # below already reports a stable label; this matches it.
    return {"corpus": "evals/make_corpus.py (generated, hermetic)",
            "entries": len(entries),
            "docs": stats["docs"], "taps": stats["taps"]}


def prepare_online_home(home: Path) -> dict:
    """Tap the pinned real-registry corpus `make eval` uses. Needs the network."""
    home.mkdir(parents=True, exist_ok=True)
    os.environ["BOOST_HOME"] = str(home)
    os.environ["BOOST_NO_AI"] = "1"
    env = dict(os.environ, PYTHON=sys.executable, BOOST_HOME=str(home))
    subprocess.run(["bash", str(ROOT / "scripts" / "ensure_eval_corpus.sh")],
                   cwd=str(ROOT), env=env, check=True)

    from boost_cli.core import catalog, rag

    stats = rag.build(catalog.all_entries(), force=True)
    return {"corpus": "tests/eval/taps.txt (pinned registries)",
            "entries": stats["entries"], "docs": stats["docs"],
            "taps": stats["taps"]}


# ----------------------------------------------------------------- rankers

def build_rankers() -> dict[str, Ranker]:
    """The engines under test, each mapping a query to a ranked list of names."""
    from boost_cli.core import catalog, rag

    def catalog_rank(q: str) -> list[str]:
        return metrics.dedupe([e["name"] for e, _s in catalog.search(q)])

    def bm25_rank(q: str) -> list[str]:
        return metrics.dedupe([h["entry"]["name"] for h in rag.retrieve(q, k=60)])

    return {"catalog": catalog_rank, "bm25": bm25_rank}


# ------------------------------------------------------------------- data

def load_golden(path: Path) -> list[dict]:
    """Load the graded golden set (JSON) or a binary .jsonl set (--online)."""
    if path.suffix == ".jsonl":
        rows: list[dict] = []
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            obj = json.loads(line)
            # Binary judgments: every relevant item is a `perfect` answer, which
            # is what binary relevance means once it meets a graded metric.
            rows.append({"id": "b%02d" % (i + 1), "query": obj["query"],
                         "labels": dict.fromkeys(obj["relevant"], 3)})
        return rows
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data["queries"])


def evaluate(rows: list[dict], ranker: Ranker) -> dict:
    """Score every golden query; return per-query scores, means, and the ranks."""
    per_query: dict[str, dict[str, float]] = {}
    ranks: dict[str, dict] = {}
    for row in rows:
        ranked = ranker(row["query"])
        labels = {k: int(v) for k, v in row["labels"].items()}
        per_query[row["id"]] = metrics.score_query(ranked, labels)
        relevant = metrics.relevant_ids(labels)
        first = next((i + 1 for i, n in enumerate(ranked) if n in relevant), None)
        ranks[row["id"]] = {"query": row["query"], "first_relevant_rank": first,
                            "top": ranked[:5]}
    means = {m: metrics.mean([per_query[q][m] for q in per_query])
             for m in metrics.METRIC_NAMES}
    return {"mean": means, "per_query": per_query, "ranks": ranks}


def run_suite(rows: list[dict], rankers: dict[str, Ranker]) -> dict:
    return {arm: evaluate(rows, rank) for arm, rank in rankers.items()}


# ---------------------------------------------------------------- reporting

def print_table(title: str, arms: dict, n: int) -> None:
    print("\n=== %s (%d queries) ===" % (title, n))
    print("  %-32s %8s %9s %8s %8s %9s"
          % ("engine", "R@5", "R@10", "MRR", "nDCG@5", "nDCG@10"))
    for arm, res in arms.items():
        m = res["mean"]
        print("  %-32s %8.3f %9.3f %8.3f %8.3f %9.3f"
              % (ARM_LABELS.get(arm, arm), m["recall@5"], m["recall@10"],
                 m["MRR"], m["nDCG@5"], m["nDCG@10"]))


def print_misses(arm: str, res: dict) -> None:
    bad = [(qid, r) for qid, r in res["ranks"].items()
           if r["first_relevant_rank"] != 1]
    if not bad:
        print("\n--- %s: every query put a relevant skill at rank 1 ---"
              % ARM_LABELS.get(arm, arm))
        return
    print("\n--- %s: not ranked #1 (%d/%d) ---"
          % (ARM_LABELS.get(arm, arm), len(bad), len(res["ranks"])))
    for qid, r in bad:
        where = ("@%d" % r["first_relevant_rank"]) if r["first_relevant_rank"] \
            else "MISS"
        print("  %-5s %-6s %-46s -> %s"
              % (qid, where, r["query"][:46], ", ".join(r["top"][:3])))


def print_significance(arms: dict, baseline: dict | None) -> None:
    """Paired bootstrap of the primary arm against the committed baseline."""
    if not baseline:
        print("\nno baseline yet — run `make evals-baseline` to pin one")
        return
    base_arm = baseline.get("arms", {}).get(PRIMARY)
    if not base_arm:
        print("\nbaseline has no %r arm — re-pin it" % PRIMARY)
        return
    shared = sorted(set(arms[PRIMARY]["per_query"]) & set(base_arm["per_query"]))
    print("\n=== paired bootstrap vs baseline (%d resamples, %d shared queries) ==="
          % (metrics.RESAMPLES, len(shared)))
    print("  %-10s %9s %9s %9s %9s   %s"
          % ("metric", "baseline", "current", "delta", "p", "95% CI on delta"))
    for m in metrics.METRIC_NAMES:
        b = [base_arm["per_query"][q][m] for q in shared]
        c = [arms[PRIMARY]["per_query"][q][m] for q in shared]
        r = metrics.paired_bootstrap(b, c)
        print("  %-10s %9.3f %9.3f %+9.3f %9.4f   [%+.3f, %+.3f]"
              % (m, metrics.mean(b), metrics.mean(c), r["delta"], r["p_value"],
                 r["ci_low"], r["ci_high"]))


# ----------------------------------------------------------------- baseline

def load_baseline() -> dict | None:
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def payload(arms: dict, rows: list[dict], corpus: dict,
            online: dict | None = None) -> dict:
    return {
        "version": 1,
        "primary": PRIMARY,
        "metrics": list(metrics.METRIC_NAMES),
        "corpus": corpus,
        "golden": {"queries": len(rows),
                   "judgments": sum(len(r["labels"]) for r in rows)},
        "arms": {arm: {"mean": res["mean"], "per_query": res["per_query"]}
                 for arm, res in arms.items()},
        "online": online,
    }


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _rel(path: Path) -> str:
    """Repo-relative path for display, falling back to the absolute one."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


# --------------------------------------------------------------------- main

def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--golden", type=Path, default=GOLDEN)
    ap.add_argument("--home", type=Path, default=DEFAULT_HOME,
                    help="disposable BOOST_HOME for the corpus (default %s)"
                         % DEFAULT_HOME)
    ap.add_argument("--out", type=Path, default=RESULTS,
                    help="where to write the result JSON")
    ap.add_argument("--save-baseline", action="store_true",
                    help="pin the current scores to evals/baseline.json")
    ap.add_argument("--misses", action="store_true",
                    help="list queries whose first relevant hit was not rank 1")
    ap.add_argument("--online", action="store_true",
                    help="also score the pinned real-registry corpus (network)")
    ap.add_argument("--faithfulness", action="store_true",
                    help="also run the Ragas-methodology faithfulness eval")
    ap.add_argument("--faithfulness-scorer", choices=("builtin", "ragas"),
                    default="builtin",
                    help="builtin (stdlib, default) or the real ragas package")
    ap.add_argument("--json", action="store_true",
                    help="print the result JSON instead of the tables")
    ap.add_argument("--quiet", action="store_true",
                    help="skip the significance block (scripts/eval_gate.py "
                         "prints its own, and prints the verdict with it)")
    args = ap.parse_args(argv)

    rows = load_golden(args.golden)
    corpus = prepare_home(args.home)
    arms = run_suite(rows, build_rankers())

    # Faithfulness runs BEFORE the --online block on purpose: its targets are
    # corpus skills, and prepare_online_home repoints BOOST_HOME at the real
    # registries, where those names do not exist. Reordering these two would
    # turn `make evals-online` (which passes both flags) into a silent skip.
    faith = None
    if args.faithfulness:
        from evals import faithfulness
        # prepare_home sets BOOST_NO_AI=1 so the retrieval arms can never make a
        # model call. Faithfulness is the one part that needs one, and asking for
        # it is explicit (--faithfulness), so lift the flag just for this step.
        os.environ.pop("BOOST_NO_AI", None)
        faith = faithfulness.run(scorer=args.faithfulness_scorer)
        os.environ["BOOST_NO_AI"] = "1"

    online = None
    if args.online:
        online_rows = load_golden(ROOT / "tests" / "eval" / "golden.jsonl")
        online_corpus = prepare_online_home(ROOT / ".eval-home")
        online_arms = run_suite(online_rows, build_rankers())
        online = {"corpus": online_corpus,
                  "golden": {"queries": len(online_rows)},
                  "arms": {a: {"mean": r["mean"]} for a, r in online_arms.items()}}

    data = payload(arms, rows, corpus, online)
    if faith is not None:
        data["faithfulness"] = faith

    save(args.out, data)

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print("corpus: %d entries -> %d indexed chunks (%s)"
              % (corpus["entries"], corpus["docs"], args.home))
        print_table("hermetic golden set", arms, len(rows))
        if args.misses:
            print_misses(PRIMARY, arms[PRIMARY])
        if not args.save_baseline and not args.quiet:
            print_significance(arms, load_baseline())
        if online:
            print_table("pinned real-registry corpus (--online, not gated)",
                        online_arms, len(online_rows))
        if faith is not None:
            from evals import faithfulness
            faithfulness.report(faith)
        print("\nwrote %s" % _rel(args.out))

    if args.save_baseline:
        save(BASELINE, payload(arms, rows, corpus))
        print("baseline pinned -> %s" % BASELINE.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
