#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Reduce an eval run to the small public JSON the docs site and the portfolio read.

    python3 scripts/publish_eval_json.py                    # from evals/baseline.json
    python3 scripts/publish_eval_json.py --results r.json   # from a fresh run
    python3 scripts/publish_eval_json.py --check            # verify committed output is current

Why a separate, tiny file rather than serving ``evals/baseline.json`` directly:
that file is ~120KB of per-query detail for 36 queries across two arms, and a
page that fetches it to show five numbers would pull all of it. This is under
1KB, has a stable shape a page can rely on, and carries the one thing the raw
results do not — the floors from ``scripts/eval_gate.py``, so a reader can see
not just the score but the bar it had to clear.

The floors are imported from eval_gate rather than copied. A floor that drifted
between the gate and the published number would be worse than publishing
nothing: the site would show a threshold CI is not actually enforcing.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "evals" / "baseline.json"
OUT = ROOT / "docs" / "eval-latest.json"

sys.path.insert(0, str(ROOT / "scripts"))
from eval_gate import FLOORS  # noqa: E402  (path set above)

# The order the site renders them in: the two recall metrics, then the ranking
# metrics. Not sorted alphabetically, which would put MRR between them.
ORDER = ["recall@5", "recall@10", "MRR", "nDCG@5", "nDCG@10"]


def _commit() -> str:
    """Short SHA of the commit these numbers were produced from, or '' if unknown."""
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=ROOT, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def build(source: Path, generated: str) -> dict:
    data = json.loads(source.read_text(encoding="utf-8"))
    primary = data.get("primary", "bm25")
    means = data["arms"][primary]["mean"]

    metrics = []
    for name in ORDER:
        if name not in means:
            continue
        floor = FLOORS.get(name)
        metrics.append({
            "name": name,
            "value": round(means[name], 4),
            "floor": floor,
            # Headroom is what a reader actually wants: not "0.69" but "0.05
            # above the bar". Rounded to the same precision as the value so the
            # arithmetic on the page is checkable by eye.
            "headroom": round(means[name] - floor, 4) if floor is not None else None,
        })

    return {
        "schema": 1,
        "generated": generated,
        "commit": _commit(),
        "engine": primary,
        "corpus": {
            "entries": data.get("corpus", {}).get("entries"),
            "queries": data.get("golden", {}).get("queries"),
            "judgments": data.get("golden", {}).get("judgments"),
        },
        "metrics": metrics,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", type=Path, default=BASELINE,
                    help="results JSON to reduce (default: evals/baseline.json)")
    ap.add_argument("--generated", default="",
                    help="ISO-8601 UTC timestamp to stamp; default: keep the "
                         "committed one, so a no-op run is a no-op diff")
    ap.add_argument("--check", action="store_true",
                    help="verify the committed file matches a fresh build; exit 1 on drift")
    args = ap.parse_args(argv)

    if not args.results.exists():
        print("publish-eval: %s does not exist" % args.results, file=sys.stderr)
        return 2

    # Default to the committed timestamp so that re-running without new numbers
    # produces a byte-identical file. Otherwise every scheduled run would commit
    # a diff of exactly one line and the history would fill with noise.
    generated = args.generated
    if not generated and OUT.exists():
        try:
            generated = json.loads(OUT.read_text(encoding="utf-8")).get("generated", "")
        except ValueError:
            generated = ""

    fresh = build(args.results, generated)
    text = json.dumps(fresh, indent=2) + "\n"

    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("ERROR: docs/eval-latest.json is out of date — regenerate with\n"
                  "    python3 scripts/publish_eval_json.py\n"
                  "and commit the result.", file=sys.stderr)
            return 1
        print("eval-latest.json is up to date.")
        return 0

    OUT.write_text(text, encoding="utf-8")
    print("wrote %s (%d bytes)" % (OUT.relative_to(ROOT), len(text)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
