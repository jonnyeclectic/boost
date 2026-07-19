#!/usr/bin/env python3
"""Golden-set recommendation eval for boost's AI pick stage (Tier 2b).

Tier 1 (eval_retrieval.py) grades *retrieval* — does the right skill come back
for a query. This grades *recommendation* — given a detected project stack,
does `boost recommend`'s AI pick stage (`_ai_picks`) suggest relevant skills,
and does it stay honest about it.

Two arms over the same candidate shortlist (built exactly like `cmd_recommend`:
keyword-search the catalog per stack keyword, aggregate, curated +10, top 20):

  heuristic   the deterministic ranking boost prints with no AI — the baseline
  ai          `_ai_picks(stack, cands)` — the LLM's top-5 with reasons

Metrics (per stack, then averaged):

  precision@k   fraction of picks that are in the stack's relevant set
  any-hit@k     did at least one relevant skill get picked
  grounding     HARD gate — every AI pick name must exist in the shortlist.
                The AI contract is fragile free-text JSON; a hallucinated or
                out-of-shortlist name is an objective defect, not a soft miss.

The relevant sets are a lower bound (a good pick outside the set is not counted
wrong), so absolute precision understates quality — but the *comparison* between
arms and the grounding gate are exact. Opt-in and key-gated like Tier 2a: the
AI arm skips cleanly when AI is unavailable; the heuristic arm always runs.

Usage:
  python3 scripts/eval_recommend.py --build          # build index, then eval
  python3 scripts/eval_recommend.py --dump           # print shortlists (author aid)
  python3 scripts/eval_recommend.py --fail-hallucination  # CI gate on grounding
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# Run from a source checkout without an install.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boost_cli.commands.discovery import _ai_picks  # noqa: E402
from boost_cli.core import ai, catalog, rag  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GOLDEN = ROOT / "tests" / "eval" / "recommend.jsonl"
SHORTLIST = 20          # cmd_recommend feeds _ai_picks the top-20 heuristic hits


# --------------------------------------------------------------- data

def load_golden(path: Path) -> List[dict]:
    rows: List[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        obj = json.loads(line)
        obj["relevant_set"] = set(obj["relevant"])
        rows.append(obj)
    if not rows:
        raise SystemExit("no golden stacks in %s" % path)
    return rows


def candidates(stack: dict, entries, n: int = SHORTLIST) -> List[dict]:
    """Rebuild cmd_recommend's heuristic shortlist for a stack (top-n entries).

    Mirrors boost_cli/commands/discovery.cmd_recommend: search the catalog for
    each stack keyword, sum scores per skill, +10 for curated, rank.
    """
    agg: Dict[str, dict] = {}
    for kw in stack["keywords"]:
        for e, s in catalog.search(kw, entries):
            rec = agg.setdefault(e["name"], {"entry": e, "score": 0})
            rec["score"] += s
    for rec in agg.values():
        if rec["entry"].get("curated"):
            rec["score"] += 10
    ranked = sorted(agg.values(),
                    key=lambda r: (-r["score"], r["entry"]["name"]))
    return [r["entry"] for r in ranked[:n]]


# --------------------------------------------------------------- metrics

def precision_at_k(picks: Sequence[str], relevant: set, k: int) -> float:
    top = picks[:k]
    if not top:
        return 0.0
    return len(set(top) & relevant) / len(top)


def any_hit(picks: Sequence[str], relevant: set, k: int) -> float:
    return 1.0 if set(picks[:k]) & relevant else 0.0


def _mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


# --------------------------------------------------------------- arms

def heuristic_names(cands: List[dict], k: int) -> List[str]:
    return [e["name"] for e in cands[:k]]


def ai_names(stack: dict, cands: List[dict]) -> Optional[List[str]]:
    picks = _ai_picks(stack, cands)
    if picks is None:
        return None
    return [str(p["name"]) for p in picks if p.get("name")]


# --------------------------------------------------------------- eval

def eval_stacks(rows: List[dict], k: int, use_ai: bool) -> dict:
    per_case: List[dict] = []
    hallucinated: List[Tuple[str, List[str]]] = []
    ai_ran = 0
    for row in rows:
        stack = row["stack"]
        rel = row["relevant_set"]
        cands = candidates(stack, catalog.all_entries())
        cand_names = {e["name"] for e in cands}

        h = heuristic_names(cands, k)
        rec = {
            "label": row.get("note", ",".join(stack["keywords"])),
            "heuristic": {
                "precision": precision_at_k(h, rel, k),
                "any_hit": any_hit(h, rel, k),
                "picks": h,
            },
        }
        if use_ai:
            a = ai_names(stack, cands)
            if a is None:            # unparseable reply == degraded to heuristic
                rec["ai"] = None
            else:
                ai_ran += 1
                off = [n for n in a if n not in cand_names]
                if off:
                    hallucinated.append((rec["label"], off))
                rec["ai"] = {
                    "precision": precision_at_k(a, rel, k),
                    "any_hit": any_hit(a, rel, k),
                    "grounded": 1.0 if not off else 0.0,
                    "off_shortlist": off,
                    "picks": a,
                }
        per_case.append(rec)

    def agg(arm: str, field: str):
        vals = [c[arm][field] for c in per_case
                if c.get(arm) and field in c[arm]]
        return _mean(vals)

    out = {
        "n": len(rows),
        "heuristic": {"precision": agg("heuristic", "precision"),
                      "any_hit": agg("heuristic", "any_hit")},
        "per_case": per_case,
        "hallucinated": hallucinated,
        "ai_ran": ai_ran,
    }
    if use_ai and ai_ran:
        out["ai"] = {"precision": agg("ai", "precision"),
                     "any_hit": agg("ai", "any_hit"),
                     "grounded": agg("ai", "grounded")}
    return out


# --------------------------------------------------------------- reporting

def print_report(res: dict, k: int, use_ai: bool) -> None:
    print("\n=== Tier 2b: recommendation quality (k=%d, %d stacks) ==="
          % (k, res["n"]))
    print("  %-22s %10s %10s %10s" % ("arm", "precision", "any-hit", "grounded"))
    h = res["heuristic"]
    print("  %-22s %10.3f %10.3f %10s"
          % ("heuristic (no AI)", h["precision"], h["any_hit"], "n/a"))
    if res.get("ai"):
        a = res["ai"]
        print("  %-22s %10.3f %10.3f %10.3f"
              % ("AI picks (_ai_picks)", a["precision"], a["any_hit"],
                 a["grounded"]))
        d = a["precision"] - h["precision"]
        print("  %-22s %+10.3f %+10.3f"
              % ("lift", d, a["any_hit"] - h["any_hit"]))
    elif use_ai:
        print("  (AI arm produced no parseable picks — nothing to score)")

    if res["hallucinated"]:
        print("\n--- grounding failures: picks outside the shortlist ---")
        for label, off in res["hallucinated"]:
            print("  %-28s -> %s" % (label[:28], ", ".join(off)))
    elif res.get("ai"):
        print("\ngrounding: every AI pick was a real shortlisted skill "
              "(0 hallucinations).")


def print_dump(rows: List[dict], k: int) -> None:
    """Print each stack's heuristic shortlist — an aid for authoring goldens."""
    for row in rows:
        stack = row["stack"]
        cands = candidates(stack, catalog.all_entries())
        print("\n# %s  [%s]" % (row.get("note", ""),
                                ", ".join(stack["keywords"])))
        for e in cands[:k]:
            star = "*" if e.get("curated") else " "
            print("  %s %-32s %s" % (star, e["name"],
                                     (e.get("description") or "")[:60]))


# --------------------------------------------------------------- main

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    ap.add_argument("-k", type=int, default=5, help="cutoff for @k metrics")
    ap.add_argument("--build", action="store_true",
                    help="(re)build the BM25 index before evaluating")
    ap.add_argument("--no-ai", action="store_true",
                    help="score only the deterministic heuristic arm")
    ap.add_argument("--dump", action="store_true",
                    help="print candidate shortlists and exit (authoring aid)")
    ap.add_argument("--fail-hallucination", action="store_true",
                    help="exit 1 if any AI pick falls outside the shortlist")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON")
    args = ap.parse_args(argv)

    rows = load_golden(args.golden)

    if args.build or not rag.ready():
        if not (args.json or args.dump):
            print("building BM25 index over the tapped catalog ...", flush=True)
        rag.build(catalog.all_entries(), force=args.build)

    if args.dump:
        print_dump(rows, max(args.k, 12))
        return 0

    use_ai = not args.no_ai and ai.available()
    if not args.no_ai and not ai.available():
        print("AI arm needs the `claude` CLI on PATH or ANTHROPIC_API_KEY — "
              "scoring the heuristic arm only.", file=sys.stderr)

    if use_ai:
        print("querying _ai_picks for %d stacks ..." % len(rows),
              file=sys.stderr, flush=True)
    res = eval_stacks(rows, args.k, use_ai)

    if args.json:
        slim = {kk: vv for kk, vv in res.items() if kk != "per_case"}
        print(json.dumps(slim, indent=2))
    else:
        print_report(res, args.k, use_ai)

    if args.fail_hallucination and res["hallucinated"]:
        print("\nGATE grounding -> FAIL (%d stacks had off-shortlist picks)"
              % len(res["hallucinated"]), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
