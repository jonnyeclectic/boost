#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Generate and validate evals/golden_set.json — the graded relevance judgments.

The judgments themselves are human work; what this script automates is keeping
them *honest*. It regenerates the JSON from the table below and refuses to emit
a set that cites a skill the corpus does not contain, grades outside the 3/2/1
scale, or has a query with no perfect answer. `--check` fails on drift, so the
committed JSON can never disagree with this file (same contract as
scripts/build_registries.py --check).

  3  perfect   the skill the query is asking for
  2  useful    a competent answer, not the best one
  1  marginal  topically adjacent — better than an unrelated hit, worse than a miss

To extend the set: add a row to QUERIES with a fresh id, grade every skill you
would accept (not just the perfect one — the graded tail is what nDCG measures),
then run `make evals-golden` and commit both this file and golden_set.json.
Adding a query invalidates the committed baseline, so re-run `make evals-baseline`
in the same change and say so in the commit message.

Usage:
  python3 evals/make_golden.py            # regenerate golden_set.json
  python3 evals/make_golden.py --check    # fail if the committed JSON is stale
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals import make_corpus  # noqa: E402

GOLDEN = ROOT / "evals" / "golden_set.json"
VERSION = 1

# (id, query, {skill: grade}, note)
Query = tuple[str, str, dict[str, int], str]

QUERIES: tuple[Query, ...] = (
    # ---- testing ----------------------------------------------------------
    ("q01", "my tests pass locally but fail randomly in CI",
     {"flaky-test-triage": 3, "integration-test-harness": 1,
      "github-actions-ci": 1},
     "intermittency, not coverage — the near-neighbor trap is unit-test-authoring"),
    ("q02", "how do I know whether my tests actually check anything",
     {"mutation-testing": 3, "test-coverage-gates": 2, "unit-test-authoring": 1},
     "coverage-vs-strength distinction; both testing skills are defensible"),
    ("q03", "write a focused test for one function",
     {"unit-test-authoring": 3, "tdd-workflow": 2, "property-based-testing": 2},
     "three testing skills all apply, in a clear preference order"),
    ("q04", "write the test before writing the implementation",
     {"tdd-workflow": 3, "unit-test-authoring": 2, "cowboy-coding": 1},
     "cowboy-coding is the fixture's deliberate anti-skill — marginal, not wrong"),
    ("q05", "spin up a real database for my test suite instead of mocking it",
     {"integration-test-harness": 3, "unit-test-authoring": 1,
      "database-index-tuning": 1},
     "cross-cluster distractor: the database skill shares vocabulary, not intent"),

    # ---- version control ---------------------------------------------------
    ("q06", "what format should our commit messages follow",
     {"commit-messages": 3, "changelog-discipline": 2, "branch-naming": 1},
     "changelog is genuinely useful here — commits feed it"),
    ("q07", "naming convention for git branches tied to tickets",
     {"branch-naming": 3, "jira-integration": 2, "commit-messages": 1},
     "two-cluster query: naming plus tracker integration"),
    ("q08", "should I rebase my feature branch or merge trunk into it",
     {"rebase-vs-merge": 3, "branch-naming": 1, "commit-messages": 1},
     "one clear answer with two weak neighbors"),
    ("q09", "find which commit introduced a regression",
     {"git-bisect-hunt": 3, "stack-trace-triage": 1, "flaky-test-triage": 1},
     "debugging vocabulary overlaps three clusters"),

    # ---- code review -------------------------------------------------------
    ("q10", "how should I review a pull request properly",
     {"code-review-checklist": 3, "review-comment-tone": 2,
      "pr-description-writer": 2, "sql-injection-review": 1},
     "widest graded tail in the set — good nDCG discriminator"),
    ("q11", "giving critical feedback without discouraging the author",
     {"review-comment-tone": 3, "code-review-checklist": 2},
     "tone, not correctness"),
    ("q12", "write a pull request description reviewers will actually read",
     {"pr-description-writer": 3, "code-review-checklist": 1,
      "changelog-discipline": 1},
     "authoring side of review"),

    # ---- CI/CD -------------------------------------------------------------
    ("q13", "my continuous integration pipeline is too slow",
     {"github-actions-ci": 3, "docker-build-optimization": 2,
      "test-coverage-gates": 1},
     "perf question answered by a ci skill — cross-cluster on purpose"),
    ("q14", "publish a release automatically when I push a tag",
     {"release-automation": 3, "changelog-discipline": 2, "github-actions-ci": 2},
     "three plausible answers, clear ordering"),
    ("q15", "my container image is enormous and rebuilds from scratch every time",
     {"docker-build-optimization": 3, "github-actions-ci": 1},
     "layer caching — narrow, should be an easy #1"),
    ("q16", "roll out a risky change to production safely",
     {"deployment-rollback": 3, "feature-flag-hygiene": 3,
      "production-incident-response": 2, "observability-metrics": 1},
     "two equally-perfect answers — tests that nDCG handles ties sanely"),
    ("q17", "we have hundreds of old feature toggles nobody removed",
     {"feature-flag-hygiene": 3, "dead-code-removal": 2},
     "flag debt reads as dead code — deliberate second-place"),

    # ---- security ----------------------------------------------------------
    ("q18", "someone committed an API key to the repository",
     {"secret-scanning": 3, "auth-token-handling": 2, "dependency-audit": 1},
     "rotation vs detection; both security skills are relevant"),
    ("q19", "enumerate the ways an attacker could abuse this service design",
     {"threat-modeling": 3, "sql-injection-review": 2, "auth-token-handling": 2},
     "design-time security, with two implementation-level neighbors"),
    ("q20", "review data access code for unsafe query construction",
     {"sql-injection-review": 3, "code-review-checklist": 2, "threat-modeling": 1},
     "security review sits across the review and security clusters"),
    ("q21", "where should access tokens be stored and how often rotated",
     {"auth-token-handling": 3, "secret-scanning": 2, "threat-modeling": 1},
     "storage and lifecycle"),

    # ---- performance -------------------------------------------------------
    ("q22", "my python program is slow and I don't know which part",
     {"profiling-python": 3, "memory-leak-hunt": 1, "caching-strategy": 1},
     "measure-first; the two neighbors are the wrong-but-tempting answers"),
    ("q23", "queries against a large table have gotten slow",
     {"database-index-tuning": 3, "caching-strategy": 2, "profiling-python": 1},
     "indexing beats caching here, but caching is a real answer"),
    ("q24", "the page takes too long to load in the browser",
     {"frontend-bundle-size": 3, "caching-strategy": 2},
     "front-end perf — the only query targeting this skill"),
    ("q25", "the service's memory usage climbs until it gets restarted",
     {"memory-leak-hunt": 3, "profiling-python": 2, "observability-metrics": 2},
     "retention, not allocation"),

    # ---- debugging & operations -------------------------------------------
    ("q26", "make sense of this exception traceback",
     {"stack-trace-triage": 3, "logging-discipline": 2, "git-bisect-hunt": 1},
     "reading a failure"),
    ("q27", "what should we be logging in production",
     {"logging-discipline": 3, "observability-metrics": 3,
      "production-incident-response": 2},
     "second tied-perfect pair, in a different cluster than q16"),
    ("q28", "the site is down — what do we do first",
     {"production-incident-response": 3, "deployment-rollback": 3,
      "observability-metrics": 2, "logging-discipline": 1},
     "mitigate before diagnose; four graded levels in one query"),
    ("q29", "which alerts are worth paging someone for",
     {"observability-metrics": 3, "production-incident-response": 2,
      "logging-discipline": 1},
     "symptom-based alerting"),

    # ---- refactoring -------------------------------------------------------
    ("q30", "safely delete code nobody calls anymore",
     {"dead-code-removal": 3, "refactor-legacy-code": 2, "feature-flag-hygiene": 1},
     "deletion confidence"),
    ("q31", "change old code that has no test coverage",
     {"refactor-legacy-code": 3, "unit-test-authoring": 2, "tdd-workflow": 2},
     "characterization tests first — spans refactoring and testing"),
    ("q32", "remove a public function without breaking downstream users",
     {"api-deprecation": 3, "changelog-discipline": 2, "api-reference-docs": 2},
     "deprecation is a schedule, not a warning"),

    # ---- documentation -----------------------------------------------------
    ("q33", "document our HTTP endpoints for other teams",
     {"api-reference-docs": 3, "readme-authoring": 2, "adr-writing": 1},
     "reference vs narrative docs"),
    ("q34", "new users can't figure out how to get started with our project",
     {"readme-authoring": 3, "onboarding-buddy": 2, "api-reference-docs": 1},
     "onboarding reads as both a docs and a people problem"),
    ("q35", "record why we chose this architecture so nobody relitigates it",
     {"adr-writing": 3, "monorepo-workspaces": 1, "threat-modeling": 1},
     "decision records"),

    # ---- planning & collaboration -----------------------------------------
    ("q36", "generate and narrow down ideas for a new feature",
     {"brainstorming": 3, "estimation-poker": 2, "standup-notes": 1},
     "fixture skill as the target — diverge then converge"),
)


# --------------------------------------------------------------- validation

def validate(queries: tuple[Query, ...], corpus_ids: list[str]) -> list[str]:
    """Return a list of problems; empty means the set is well-formed."""
    problems: list[str] = []
    known = set(corpus_ids)
    seen_ids: dict[str, str] = {}
    seen_text: dict[str, str] = {}
    for qid, text, labels, note in queries:
        if qid in seen_ids:
            problems.append("%s: duplicate query id" % qid)
        seen_ids[qid] = text
        key = text.strip().lower()
        if key in seen_text:
            problems.append("%s: duplicate query text (also %s)"
                            % (qid, seen_text[key]))
        seen_text[key] = qid
        if not note.strip():
            problems.append("%s: needs a note explaining the judgment" % qid)
        if not labels:
            problems.append("%s: no labels" % qid)
            continue
        for skill, grade in labels.items():
            if skill not in known:
                problems.append("%s: cites %r, which is not in the corpus"
                                % (qid, skill))
            if grade not in (1, 2, 3):
                problems.append("%s: grade %r for %r is outside the 3/2/1 scale"
                                % (qid, grade, skill))
        if 3 not in labels.values():
            problems.append("%s: no grade-3 (perfect) answer — every query needs "
                            "at least one" % qid)
    return problems


def build(queries: tuple[Query, ...] = QUERIES) -> dict:
    corpus_ids = make_corpus.skill_names()
    problems = validate(queries, corpus_ids)
    if problems:
        raise SystemExit("golden set is invalid:\n  - %s" % "\n  - ".join(problems))
    return {
        "version": VERSION,
        "generated_by": "evals/make_golden.py",
        "corpus": "evals/make_corpus.py",
        "corpus_skills": len(corpus_ids),
        "grades": {"3": "perfect", "2": "useful", "1": "marginal"},
        "queries": [
            {"id": qid, "query": text,
             "labels": {k: labels[k] for k in sorted(labels)},
             "note": note}
            for qid, text, labels, note in queries
        ],
    }


def render(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="fail if the committed golden_set.json is stale")
    args = ap.parse_args(argv)

    text = render(build())
    if args.check:
        try:
            current = GOLDEN.read_text(encoding="utf-8")
        except OSError:
            print("golden set missing — run `python3 evals/make_golden.py`",
                  file=sys.stderr)
            return 1
        if current != text:
            print("evals/golden_set.json is stale — run "
                  "`python3 evals/make_golden.py` and commit the result",
                  file=sys.stderr)
            return 1
        print("golden set up to date (%d queries)" % len(QUERIES))
        return 0

    GOLDEN.write_text(text, encoding="utf-8")
    labeled = sum(len(q[2]) for q in QUERIES)
    print("wrote %s — %d queries, %d graded judgments over %d corpus skills"
          % (GOLDEN.relative_to(ROOT), len(QUERIES), labeled,
             len(make_corpus.skill_names())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
