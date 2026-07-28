"""Tier 2: Ragas-methodology faithfulness for `boost explain` and `boost distill`.

Both commands generate prose from a SKILL.md. Their shared failure mode is
*overclaiming* — describing a capability the source skill does not have. Line
coverage cannot see that and neither can a retrieval metric; it needs a judge.

Ragas defines faithfulness as a two-step LLM procedure, which this implements
directly against boost's own `core.ai` bridge rather than pulling in the package:

  1. decompose the generated answer into atomic factual statements
  2. verify each statement against the retrieved context (here, the SKILL.md)
  3. score = supported statements / total statements, averaged over samples

Implementing it on `core.ai` keeps the harness dependency-free and means it uses
the *same* bridge the shipped commands use — the `claude` CLI on PATH, else
ANTHROPIC_API_KEY. When neither is present the whole eval **skips** (never
fails), exactly like boost's own AI-assisted commands degrade to heuristics; a
gate that needs a paid API key must not be able to block a merge.

Two scores are reported per sample, and the distinction matters:

  * **judged**   the Ragas score above, over the *raw* model reply.
  * **guard**    what `boost explain` would actually do with that reply. Since
                 the runtime grounding guardrail landed (core/faithfulness.py),
                 an explanation below a config-tunable threshold is discarded in
                 favor of the deterministic extractive summary. Grading only the
                 raw reply would answer a question nobody asks — how faithful is
                 text the user may never see.

Scope note: `scripts/eval_explain.py` is the *ragas-package* eval for `explain`
over the pinned real-registry corpus (`make eval-explain`), and stays the owner
of that path. This module is the hermetic, key-free counterpart: it needs no
judge key, runs on the generated corpus, covers `distill` as well as `explain`,
and reports the runtime guard alongside the judge. `scorer="ragas"` delegates to
that script rather than keeping a second copy of its judge setup.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The skills the eval generates prose about. Kept small: every sample is two or
# three LLM round-trips, and faithfulness varies far less across skills than
# retrieval quality does across queries.
EXPLAIN_TARGETS = ("tdd-workflow", "threat-modeling", "caching-strategy",
                   "production-incident-response")
DISTILL_TARGETS = (("unit-test-authoring", "flaky-test-triage"),
                   ("secret-scanning", "auth-token-handling"))

# Kept in sync with cmd_explain (boost_cli/commands/info.py) and _distill_ai
# (boost_cli/commands/intelligence.py) — the eval must grade the same generation
# the shipped commands produce, or it is measuring a prompt nobody ships.
EXPLAIN_PROMPT = (
    "Explain in plain English (4-6 sentences, no markdown) what this "
    "AI coding-agent skill makes the agent do differently and when it "
    "triggers:\n\n")
EXPLAIN_SYSTEM = "You summarize agent skills for developers. Be concrete and brief."

DISTILL_SYSTEM = ("You are an expert author of SKILL.md files for AI coding "
                  "agents. Reply with ONLY the complete merged SKILL.md content.")

STATEMENT_SYSTEM = (
    "You decompose text into atomic factual statements for evaluation. "
    "Reply with ONLY a JSON array of strings.")
VERIFY_SYSTEM = (
    "You judge whether each statement is supported by the given context. "
    "Reply with ONLY a JSON array of objects {\"statement\": str, "
    "\"supported\": true|false, \"reason\": str}.")


# ------------------------------------------------------------ ragas steps

def extract_statements(answer: str) -> Optional[List[str]]:
    """Ragas step 1: break the generated answer into atomic claims."""
    from boost_cli.core import ai
    reply = ai.ask(
        "Break the following answer into atomic factual statements. Each "
        "statement must stand alone (resolve every pronoun) and assert exactly "
        "one fact.\n\nANSWER:\n%s" % answer,
        system=STATEMENT_SYSTEM, max_tokens=1200)
    data = _json_value(reply)
    if not isinstance(data, list):
        return None
    return [str(s).strip() for s in data if str(s).strip()]


def verify_statements(statements: List[str], context: str) -> Optional[List[dict]]:
    """Ragas step 2: judge each claim as supported or not by the context."""
    from boost_cli.core import ai
    numbered = "\n".join("%d. %s" % (i + 1, s) for i, s in enumerate(statements))
    reply = ai.ask(
        "Judge each statement strictly against the CONTEXT below. A statement is "
        "supported only if the context directly states or entails it; plausible "
        "but absent claims are NOT supported.\n\nCONTEXT:\n%s\n\nSTATEMENTS:\n%s"
        % (context, numbered),
        system=VERIFY_SYSTEM, max_tokens=2000)
    data = _json_value(reply)
    if not isinstance(data, list):
        return None
    out: List[dict] = [{"statement": str(item.get("statement", "")),
                        "supported": bool(item.get("supported")),
                        "reason": str(item.get("reason", ""))}
                       for item in data if isinstance(item, dict)]
    return out or None


def score_sample(answer: str, context: str) -> Optional[dict]:
    """Faithfulness for one (answer, context) pair: supported / extracted statements.

    The denominator is the number of statements *extracted*, never the number of
    verdicts returned. Dividing by the verdict count is the subtle way this metric
    breaks: the judge reply is capped at max_tokens and non-dict entries are
    dropped, so a truncated or selective reply that judges 3 of 10 statements
    would score 3/3 = 1.0 instead of 3/10 = 0.3 — a hallucinating generator would
    look perfect precisely when the judge struggled most with it.

    A short verdict list is therefore treated as a failed judging pass (None, i.e.
    "not measured") rather than silently scored, keeping the same "could not
    measure is not a zero" contract the rest of this module holds.
    """
    statements = extract_statements(answer)
    if not statements:
        return None
    verdicts = verify_statements(statements, context)
    if not verdicts or len(verdicts) < len(statements):
        return None
    verdicts = verdicts[:len(statements)]     # ignore any spurious extras
    supported = sum(1 for v in verdicts if v["supported"])
    return {"score": supported / len(statements),
            "statements": len(statements), "supported": supported,
            "unsupported": [v["statement"] for v in verdicts
                            if not v["supported"]]}


def _json_value(text: Optional[str]):
    """Parse the first JSON array in a reply, tolerating prose or a code fence."""
    if not text:
        return None
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


# ------------------------------------------------------------- generation

def _skill_md(name: str) -> Optional[str]:
    """The SKILL.md text for a corpus skill, read through the live catalog."""
    from boost_cli.core import catalog, registry
    entry = next((e for e in catalog.all_entries() if e["name"] == name), None)
    if entry is None:
        return None
    tap = next((t for t in registry.list_taps() if t.name == entry["tap"]), None)
    if tap is None:
        return None
    p = tap.path / entry["skill_md"]
    return p.read_text(encoding="utf-8") if p.exists() else None


def generate_explain(name: str) -> Optional[Tuple[str, str]]:
    """(answer, context) for `boost explain <name>` — the raw model reply.

    This is the *pre-guardrail* generation. `cmd_explain` only prints it when it
    clears the runtime grounding check; see ``guardrail_verdict``, which reports
    what the shipped command would actually have done with it.
    """
    from boost_cli.core import ai
    text = _skill_md(name)
    if not text:
        return None
    reply = ai.ask(EXPLAIN_PROMPT + text, system=EXPLAIN_SYSTEM)
    return (reply, text) if reply else None


def guardrail_verdict(answer: str, context: str) -> dict:
    """What the shipped runtime guard (core.faithfulness) would do with a reply.

    `boost explain` does not print whatever the model returns: since the runtime
    grounding guardrail landed, an explanation scoring below a config-tunable
    threshold is discarded in favor of the deterministic extractive summary. So
    the LLM-judged score alone answers a question nobody asks — "how faithful is
    text the user may never see". Recording the guard's verdict alongside it
    closes that gap, and costs nothing: the sample already exists, and the guard
    is pure stdlib with no second model call.
    """
    from boost_cli.commands import info as info_cmd
    from boost_cli.core import faithfulness as runtime
    score = runtime.score(answer, context)
    # The command module owns the threshold (config key + default); reading it
    # from there is what keeps this honest if the default is ever retuned.
    try:
        threshold = info_cmd._faithfulness_threshold()
    except Exception:            # a private helper — never let it be fatal
        threshold = 0.5
    return {"guardrail_score": score, "guardrail_threshold": threshold,
            "would_be_shown": score >= threshold}


def generate_distill(names: Tuple[str, ...]) -> Optional[Tuple[str, str]]:
    """(answer, context) for `boost distill <a> <b>` — context is both sources."""
    from boost_cli.core import ai
    texts = [(n, _skill_md(n)) for n in names]
    if any(t is None for _n, t in texts):
        return None
    blocks = "\n\n".join("### SOURCE SKILL: %s\n\n%s" % (n, t) for n, t in texts)
    new = names[0] + "-distilled"
    reply = ai.ask_author(
        "Merge the following %d skills into ONE skill file.\n"
        "Requirements:\n"
        "- YAML frontmatter with name: %s, a one-line description, "
        "version: 1.0.0, and the union of the source tags\n"
        "- a deduplicated body: keep every distinct rule exactly once under "
        "clear headings, drop redundant or contradictory duplicates\n\n%s"
        % (len(texts), new, blocks), system=DISTILL_SYSTEM)
    if not reply:
        return None
    return ai.extract_markdown(reply), blocks


# ------------------------------------------------------------------ driver

def run(scorer: str = "builtin") -> dict:
    """Score explain + distill faithfulness. Never raises; skips when AI is off.

    Returns a status dict rather than a bare float so the caller (and the gate)
    can tell "0.0, the model overclaimed" apart from "no API key, not measured" —
    conflating those two is how an eval silently stops evaluating.
    """
    from boost_cli.core import ai
    if not ai.available():
        # Distinguish the two ways this can be off. Reporting "no CLI on PATH"
        # when the CLI is right there and boost was merely told not to use it
        # sends the reader hunting for the wrong problem.
        reason = ("boost AI is disabled (BOOST_NO_AI is set, or ai.enabled is "
                  "false in config)" if not ai.enabled() else
                  "no `claude` CLI on PATH and no ANTHROPIC_API_KEY")
        return {"status": "skipped", "scorer": scorer,
                "reason": "%s — faithfulness needs a model to generate and judge"
                          % reason}
    if scorer == "ragas":
        return _run_ragas()

    samples: List[dict] = []
    skipped: List[str] = []
    for name in EXPLAIN_TARGETS:
        gen = generate_explain(name)
        if gen is None:
            skipped.append("explain:%s (generation failed)" % name)
            continue
        result = score_sample(*gen)
        if result is None:
            skipped.append("explain:%s (judging failed)" % name)
            continue
        samples.append({"target": "explain:%s" % name, **result,
                        **guardrail_verdict(*gen)})
    for names in DISTILL_TARGETS:
        gen = generate_distill(names)
        label = "distill:%s" % "+".join(names)
        if gen is None:
            skipped.append("%s (generation failed)" % label)
            continue
        result = score_sample(*gen)
        if result is None:
            skipped.append("%s (judging failed)" % label)
            continue
        samples.append({"target": label, **result})

    if not samples:
        return {"status": "skipped", "scorer": scorer,
                "reason": "no sample could be generated or judged: %s"
                          % "; ".join(skipped)}
    mean = sum(s["score"] for s in samples) / len(samples)
    fell_back = sum(1 for s in samples if s.get("would_be_shown") is False)
    return {"status": "ok", "scorer": "builtin", "mean": mean,
            "n": len(samples), "would_fall_back": fell_back,
            "samples": samples, "skipped": skipped}


def _eval_explain_module():
    """Load scripts/eval_explain.py as a module (it is not an importable package).

    Same importlib pattern tests/unit/test_eval_stats_summary.py uses for the
    other scripts. Delegating to it — rather than copying its judge setup and
    ragas call — is what keeps the two from drifting, and keeps its RunConfig
    timeout, which a hand-rolled second copy silently lost.
    """
    import importlib.util
    path = ROOT / "scripts" / "eval_explain.py"
    spec = importlib.util.spec_from_file_location("boost_eval_explain", path)
    if spec is None or spec.loader is None:      # pragma: no cover - defensive
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_ragas() -> dict:
    """Alternative scorer: the reference `ragas` implementation.

    Thin delegation to scripts/eval_explain.py, which owns the ragas path (its
    own `make eval-explain` target and CI workflow). This runs it over the
    hermetic corpus instead of the pinned registries, so the stdlib scorer above
    can be cross-checked against the reference one on identical inputs.
    """
    try:
        mod = _eval_explain_module()
    except Exception as e:                       # loading a script — never fatal
        return {"status": "skipped", "scorer": "ragas",
                "reason": "could not load scripts/eval_explain.py (%s)" % e}
    if mod is None:
        return {"status": "skipped", "scorer": "ragas",
                "reason": "could not load scripts/eval_explain.py"}

    judge, reason = mod.build_judge()
    if judge is None:
        return {"status": "skipped", "scorer": "ragas", "reason": reason}

    samples, skipped = [], []
    for name in EXPLAIN_TARGETS:
        gen = generate_explain(name)
        if gen is None:
            skipped.append("explain:%s (generation failed)" % name)
            continue
        samples.append({"name": name, "explanation": gen[0], "context": gen[1]})
    if not samples:
        return {"status": "skipped", "scorer": "ragas",
                "reason": "no explanation could be generated: %s"
                          % "; ".join(skipped)}

    scores = mod.score_faithfulness(samples, judge)
    graded = [(s["name"], sc) for s, sc in zip(samples, scores) if sc is not None]
    if not graded:
        return {"status": "skipped", "scorer": "ragas",
                "reason": "ragas returned no usable scores"}
    return {"status": "ok", "scorer": "ragas",
            "mean": sum(sc for _n, sc in graded) / len(graded),
            "n": len(graded),
            "samples": [{"target": "explain:%s" % n, "score": sc}
                        for n, sc in graded],
            "skipped": skipped}


def report(data: Dict[str, object]) -> None:
    """Print the faithfulness block of the run report."""
    print("\n=== Tier 2: faithfulness (Ragas methodology, scorer=%s) ==="
          % data.get("scorer", "?"))
    if data.get("status") != "ok":
        print("  SKIPPED — %s" % data.get("reason", "unknown"))
        return
    samples = data.get("samples") or []
    print("  %-38s %7s %-14s %s"
          % ("target", "judged", "statements", "runtime guard"))
    for s in samples:                                    # type: ignore[union-attr]
        # The guard column is what `boost explain` would actually have done with
        # this generation — "shown" or "fell back to the extractive summary".
        guard = ("%.2f %s" % (s["guardrail_score"],
                              "shown" if s["would_be_shown"] else "FELL BACK")
                 if "guardrail_score" in s else "n/a")
        print("  %-38s %7.3f %-14s %s"
              % (s["target"], s["score"],
                 "%d/%d supported" % (s.get("supported", 0),
                                      s.get("statements", 0)), guard))
    print("  %-38s %7.3f  (n=%d)" % ("MEAN", data["mean"], data["n"]))
    if data.get("would_fall_back"):
        print("  NOTE: %d of %d generations would NOT have reached a user — the "
              "runtime guardrail\n        in `boost explain` discards them. The "
              "judged mean above grades the raw\n        model output, which is "
              "a strictly harsher question than what ships."
              % (data["would_fall_back"], data["n"]))
    for s in samples:                                    # type: ignore[union-attr]
        for claim in s.get("unsupported", []):
            print("    unsupported (%s): %s" % (s["target"], claim[:90]))
