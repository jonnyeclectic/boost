#!/usr/bin/env python3
"""Tier 2c: explain-faithfulness eval (opt-in, LLM-judged via ragas).

`boost explain` generates a plain-English summary of a skill from its SKILL.md.
Its failure mode is *overclaiming* — describing capabilities the skill does not
have. This harness measures that with ragas `faithfulness`: the metric splits an
explanation into individual claims and verifies each against the SKILL.md, so a
hallucinated capability drives the score down.

Two LLMs are involved, both opt-in / key-gated, mirroring boost's degradable-
bridge contract:
  * generation — boost's own ai.ask (the `claude` CLI or ANTHROPIC_API_KEY)
    writes the explanation, with the same prompt `boost explain` uses.
  * judging    — ragas needs a judge LLM configured from an API key:
    OPENAI_API_KEY (langchain-openai), or ANTHROPIC_API_KEY with the optional
    langchain-anthropic package installed.

It skips cleanly (prints a hint, exits 0) when ragas is absent, when boost's AI
is unavailable, or when no judge key is set — so it never blocks a workflow and
is never part of `make check`.

Usage:
  python3 scripts/eval_explain.py                    # score the golden set
  python3 scripts/eval_explain.py --fail-under 0.80  # gate on mean faithfulness
  python3 scripts/eval_explain.py --skill pdf        # one skill
  python3 scripts/eval_explain.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Run from a source checkout without an install.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boost_cli.core import ai, catalog, registry  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GOLDEN = ROOT / "tests" / "eval" / "explain.jsonl"

# Keep in sync with cmd_explain (boost_cli/commands/info.py) — the eval must
# grade the *same* generation the shipped command produces.
EXPLAIN_PROMPT = (
    "Explain in plain English (4-6 sentences, no markdown) what this "
    "AI coding-agent skill makes the agent do differently and when it "
    "triggers:\n\n")
EXPLAIN_SYSTEM = "You summarize agent skills for developers. Be concrete and brief."

# The judge question paired with each explanation (faithfulness scores the
# response against the SKILL.md context; user_input is required by the sample).
JUDGE_QUESTION = "What does this skill do, and when does it trigger?"


def load_golden(path: Path) -> List[dict]:
    rows: List[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(json.loads(line))
    if not rows:
        raise SystemExit("no golden skills in %s" % path)
    return rows


def resolve_skill_md(name: str) -> Optional[str]:
    """Return a skill's SKILL.md text, or None if it isn't tapped/installed.

    ``skill_md`` is stored relative to its tap's repo root, so join it onto the
    tap's local path (repos_dir/<safe_name>) to get an absolute file.
    """
    matches = [e for e in catalog.all_entries() if e["name"] == name]
    if not matches:
        return None
    entry = matches[0]
    tap = next((t for t in registry.list_taps() if t.name == entry["tap"]), None)
    if tap is None:
        return None
    p = tap.path / entry["skill_md"]
    return p.read_text(encoding="utf-8") if p.exists() else None


def generate_explanation(skill_md: str) -> Optional[str]:
    """Generate the explanation exactly as `boost explain` does."""
    return ai.ask(EXPLAIN_PROMPT + skill_md, system=EXPLAIN_SYSTEM)


def build_judge() -> Tuple[object, Optional[str]]:
    """Configure the ragas judge LLM from the environment.

    Returns (judge, None) on success, or (None, reason) so the caller can print
    a single clear hint and skip. OpenAI is preferred (its langchain package
    ships with ragas); Anthropic needs the optional langchain-anthropic.
    """
    try:
        from ragas.llms import LangchainLLMWrapper
    except ImportError:
        return None, ("ragas is not installed — `pip install "
                      "boost-skill-cli[eval]` (or `pip install "
                      "'ragas>=0.2,<0.3'`)")
    model = os.environ.get("BOOST_EVAL_JUDGE_MODEL")
    if os.environ.get("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        return LangchainLLMWrapper(
            ChatOpenAI(model=model or "gpt-4o-mini", temperature=0)), None
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            return None, ("ANTHROPIC_API_KEY is set but langchain-anthropic is "
                          "not installed — `pip install langchain-anthropic`, "
                          "or set OPENAI_API_KEY instead")
        return LangchainLLMWrapper(
            ChatAnthropic(model=model or "claude-3-5-haiku-latest",
                          temperature=0)), None
    return None, ("no judge key — set OPENAI_API_KEY (or ANTHROPIC_API_KEY with "
                  "langchain-anthropic) so ragas can score faithfulness")


def score_faithfulness(samples: List[dict], judge) -> List[Optional[float]]:
    """Run ragas faithfulness over the samples; return one score per sample."""
    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.metrics import faithfulness
    from ragas.run_config import RunConfig

    ds = EvaluationDataset(samples=[
        SingleTurnSample(user_input=JUDGE_QUESTION,
                         retrieved_contexts=[s["context"]],
                         response=s["explanation"])
        for s in samples])
    result = evaluate(ds, metrics=[faithfulness], llm=judge,
                      show_progress=False,
                      run_config=RunConfig(timeout=180, max_workers=2))
    df = result.to_pandas()
    col = ("faithfulness" if "faithfulness" in df.columns
           else next((c for c in df.columns if "faith" in c.lower()), None))
    if col is None:                               # unexpected ragas schema
        return [None] * len(samples)
    return [None if v != v else float(v)          # NaN -> None
            for v in df[col].tolist()]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    ap.add_argument("--skill", help="evaluate a single skill instead of the set")
    ap.add_argument("--fail-under", type=float, default=None, metavar="X",
                    help="exit 1 if mean faithfulness < X")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON")
    args = ap.parse_args(argv)

    rows = ([{"name": args.skill, "note": "single"}] if args.skill
            else load_golden(args.golden))

    # ---- opt-in / key-gated preflight: skip cleanly, never block ----
    judge, reason = build_judge()
    if judge is None:
        print("explain-faithfulness eval skipped: %s." % reason, file=sys.stderr)
        return 0
    if not ai.available():
        print("explain-faithfulness eval skipped: boost AI unavailable "
              "(needs the `claude` CLI or ANTHROPIC_API_KEY to generate "
              "explanations).", file=sys.stderr)
        return 0

    samples: List[dict] = []
    skipped: List[str] = []
    for row in rows:
        name = row["name"]
        skill_md = resolve_skill_md(name)
        if not skill_md:
            skipped.append("%s (not tapped/installed)" % name)
            continue
        explanation = generate_explanation(skill_md)
        if not explanation:
            skipped.append("%s (generation failed)" % name)
            continue
        samples.append({"name": name, "context": skill_md,
                        "explanation": explanation})

    if not samples:
        print("no skills could be evaluated: %s" % "; ".join(skipped),
              file=sys.stderr)
        return 0

    scores = score_faithfulness(samples, judge)
    graded = [(s["name"], sc) for s, sc in zip(samples, scores) if sc is not None]
    mean = sum(sc for _, sc in graded) / len(graded) if graded else 0.0

    if args.json:
        print(json.dumps({
            "metric": "faithfulness",
            "mean": mean,
            "n": len(graded),
            "per_skill": {n: sc for n, sc in graded},
            "skipped": skipped,
        }, indent=2))
    else:
        print("=== Tier 2c: explain faithfulness (ragas · LLM-judged) ===")
        print("  %-28s %s" % ("skill", "faithfulness"))
        for name, sc in graded:
            print("  %-28s %.3f" % (name, sc))
        print("  %-28s %.3f  (n=%d)" % ("MEAN", mean, len(graded)))
        if skipped:
            print("\nskipped: %s" % "; ".join(skipped))

    if args.fail_under is not None:
        ok = mean >= args.fail_under
        if not args.json:
            print("\nGATE mean faithfulness = %.3f  (min %.3f)  ->  %s"
                  % (mean, args.fail_under, "PASS" if ok else "FAIL"))
        if not ok:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
