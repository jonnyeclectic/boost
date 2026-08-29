#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Publish boost's golden retrieval set as a LangSmith dataset.

The offline Tier-1 gate floors recall@k / hit@1 / MRR / nDCG@k over
``tests/eval/golden.jsonl`` on every merge. Publishing the same queries as a
LangSmith dataset lets online evals run against real traffic with the same
ground truth — the point is one set of judgments in both places, so an online
regression and an offline regression mean the same thing.

Key-gated and opt-in, like every LangSmith surface here: requires
``LANGSMITH_API_KEY`` and the ``langsmith`` package (``pip install
langsmith``), and exits with a message rather than a traceback when either
is missing. It must never become part of the required gate — a required
check that depends on a SaaS account fails when someone else's billing
lapses.

Run from a boost checkout (the golden set lives in the repo, not the wheel):

    python evals/publish_golden_dataset.py \
        [--golden tests/eval/golden.jsonl] [--name boost-golden-retrieval]

Re-running updates the dataset in place: examples are replaced wholesale so
the dataset always mirrors the file, never accretes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_golden(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(json.loads(line))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--golden", type=Path,
                    default=REPO_ROOT / "tests" / "eval" / "golden.jsonl")
    ap.add_argument("--name", default="boost-golden-retrieval")
    args = ap.parse_args(argv)

    if not os.environ.get("LANGSMITH_API_KEY"):
        print("LANGSMITH_API_KEY is not set — nothing published (this surface "
              "is opt-in, a key is the entry fee only here)", file=sys.stderr)
        return 1
    try:
        from langsmith import Client
    except ImportError:
        print("langsmith is not installed — `pip install langsmith`",
              file=sys.stderr)
        return 1

    rows = load_golden(args.golden)
    client = Client()
    if client.has_dataset(dataset_name=args.name):
        dataset = client.read_dataset(dataset_name=args.name)
        # Replace, never accrete: the dataset mirrors the file.
        for ex in client.list_examples(dataset_id=dataset.id):
            client.delete_example(ex.id)
    else:
        dataset = client.create_dataset(
            dataset_name=args.name,
            description="boost Tier-1 golden retrieval judgments "
                        "(tests/eval/golden.jsonl) — same ground truth as the "
                        "offline recall/hit@1/MRR/nDCG gate")
    client.create_examples(
        dataset_id=dataset.id,
        examples=[{
            "inputs": {"query": r["query"]},
            "outputs": {"relevant": r.get("relevant", []),
                        "kind": r.get("kind")},
            "metadata": {"note": r.get("note", "")},
        } for r in rows])
    print("published %d examples to LangSmith dataset %r"
          % (len(rows), args.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
