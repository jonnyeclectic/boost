#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Render the `--stats --json` significance payload as a Markdown summary.

Turns the ranx paired t-test output from ``eval_retrieval.py --stats --json``
into a GitHub-Step-Summary table: for the best engine vs each other engine, is
each metric's lead statistically significant (p < 0.05) or just noise. Kept
separate from the workflow YAML so it is unit-testable (tests/unit) and so the
significance-reading logic lives in one place.

Usage:
    python3 scripts/eval_stats_summary.py stats.json   # prints Markdown to stdout
"""
from __future__ import annotations

import json
import sys

ALPHA = 0.05
HEADER = "### Tier 1b — retrieval significance (ranx paired t-test)\n"


def _load(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def render(payload: dict | None) -> str:
    """Markdown for a `--stats --json` payload (or a graceful skip note)."""
    sig = (payload or {}).get("significance")
    if not sig:
        return (HEADER + "\n_skipped_ — no significance data "
                "(the `[eval]` extra / `ranx` was unavailable, or fewer than "
                "two engines ran).\n")

    models = sig.get("model_names", [])
    metrics = sig.get("metrics", [])
    if len(models) < 2 or not metrics:
        return HEADER + "\n_only one engine ran — nothing to compare._\n"

    # The best engine is the last row of the comparison (engines are ordered
    # worst→best upstream); every other engine carries the p-values of the best
    # engine's lead over it in its `comparisons` block.
    best = models[-1]
    lines = [HEADER, "", "Best engine: **%s** (α = %.2f).\n" % (best, ALPHA)]
    lines.append("| vs | " + " | ".join(metrics) + " |")
    lines.append("|---|" + "|".join(["---"] * len(metrics)) + "|")

    n_sig = 0
    for other in models[:-1]:
        comps = sig.get(other, {}).get("comparisons", {}).get(best, {})
        cells = []
        for m in metrics:
            p = comps.get(m)
            if p is None:
                cells.append("—")
            elif p < ALPHA:
                cells.append("✅ p=%.4f" % p)
                n_sig += 1
            else:
                cells.append("· p=%.4f" % p)
        lines.append("| %s | %s |" % (other, " | ".join(cells)))

    lines.append("")
    lines.append("_✅ = %s beats that engine on the metric with p < %.2f "
                 "(a statistically real lead, not just a higher number)._"
                 % (best, ALPHA))
    lines.append("\n%d of the compared metrics reach significance." % n_sig)
    return "\n".join(lines) + "\n"


def main(argv: list | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    path = args[0] if args else "stats.json"
    sys.stdout.write(render(_load(path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
