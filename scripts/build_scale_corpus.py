#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Generate the Tier 1b *scale* corpus list: the required corpus plus distractors.

WHY A SECOND CORPUS. The required `eval` gate measures the twenty repositories
in tests/eval/taps.txt, whose header states their size. A real install is far
larger — the machine this was measured on carries 71,655 across
445 taps — and the metrics do not survive the difference: at that size all four
floors fail (0.709 / 0.341 / 0.451 / 0.504 against 0.780 / 0.400 / 0.520 /
0.580). So every retrieval decision validated against the small corpus is
validated at a scale users leave behind after their third tap.

WHY THIS IS "A" SCALE AND NOT "THE" SCALE. Holding the golden queries fixed and
growing the corpus, hit@1 decays continuously — roughly halving for every 4x —
rather than settling on a floor a larger fixed corpus would capture:

    53 -> 0.420   253 -> 0.380   753 -> 0.240   2,053 -> 0.220
    6,053 -> 0.080   20,053 -> 0.040   60,053 -> 0.020

There is no plateau, so "pick a bigger number" has no principled stopping point
and this corpus must not be described as the definitive one. What a second tier
buys is a *second point on that curve*, measured on real registries rather than
random distractors, run on a schedule so the curve is watched rather than
assumed.

THE SELECTION RULE, and why it is not "the biggest registries".

  1. Every row of the required corpus, verbatim, pin and count included. This is
     the load-bearing part: those rows are what contain the golden targets, and
     a scale corpus missing them would collapse recall for a reason that has
     nothing to do with scale. Measured on the required corpus at the #410
     pins, dropping one target-bearing repo took recall@10 from 0.852 to 0.676
     — indistinguishable from a retrieval regression.

     It also makes the two tiers *comparable*: the scale corpus is the required
     one plus distractors, so a metric difference between them isolates the
     effect of the added candidates instead of confounding it with a different
     target set.

  2. Distractors from `boost_cli/data/registries.json` — the project's own
     curated list, where every repository was verified to exist before it was
     added — largest first *within each item type*, drawn round-robin across
     types. Straight largest-first would not do: the curated set is 341 skill /
     76 workflow / 26 rule registries, so the skill tail crowds the others out,
     and a corpus that is 95% skills is not what an install looks like. The
     required list's own header records what that costs — `boost tap --defaults`
     taps only skill repos and scores 0.000 on every rule and workflow query.

  3. No one distractor may carry more than MAX_SHARE of the target. Largest-
     first is a fine rule while the largest registry is a few percent of the
     target and a bad one once a single repository is a fifth of it: the
     corpus then measures that repository's vocabulary, and the required
     corpus already shows the cost — one third-party repo is 62% of its
     entries. Holding the selection hostage to that was the only reason
     `jeremylongshore/tons-of-skills-marketplace` sat at `est_items` 1 against
     a measured 4,253. A registry over the cap is skipped, named in the
     header, and the next largest is taken.

  4. Stop at a target expressed in `est_items`. The default is arbitrary and
     says so; it is chosen to land the same order of magnitude as a real install
     while keeping the clone count survivable on a CI runner.

`est_items` UNDER-REPORTS, and the projection here says by how much rather than
pretending otherwise: the curated set estimates 28,225 items across 443
scannable registries, while a real 445-tap install scans to 71,655 — about
2.5x. So a 20,000-est target projects to roughly 50,000 actual entries. That is
a projection, not a measurement; the real count is written into the file by
`eval_corpus.py --refresh` on the first run, which is also what pins it.

Usage:
  python3 scripts/build_scale_corpus.py            # write tests/eval/taps-scale.txt
  python3 scripts/build_scale_corpus.py --check    # fail if it would change
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRIES = ROOT / "boost_cli" / "data" / "registries.json"
REQUIRED_TAPS = ROOT / "tests" / "eval" / "taps.txt"
OUT = ROOT / "tests" / "eval" / "taps-scale.txt"

#: Ratio between what `est_items` claims and what the scanner actually finds,
#: from the one place both numbers exist: 443 scannable registries estimate
#: 28,225 items, and a real 445-tap install scans to 71,655.
EST_TO_ACTUAL = 71_655 / 28_225

#: Default target, in est_items. Arbitrary, and the header says why no number
#: here can be principled — it buys one more point on a curve with no plateau.
DEFAULT_TARGET = 20_000

#: The most of the target one distractor may carry. 5% of 20,000 is 1,000:
#: above every registry the selection already took (the largest is 880), so the
#: cap moves nothing that was measured, and below the 4,253 that would otherwise
#: be a fifth of the corpus on its own.
MAX_SHARE = 0.05

#: Round-robin order. Rules are scarcest in the curated set and score worst when
#: absent, so they are drawn first each cycle rather than last.
TYPE_ORDER = ("rule", "workflow", "skill")


def required_rows(text: str) -> list[str]:
    """The required corpus's rows, verbatim, in file order."""
    return [ln.rstrip() for ln in text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


def repo_of(row: str) -> str:
    return row.split()[0]


def candidates(registries: Sequence[dict], exclude: Sequence[str]
               ) -> dict[str, list[tuple[str, int]]]:
    """``type -> [(repo, est_items)]``, largest first, excluding what we have.

    ``list_only`` rows are awesome-list indexes rather than skill trees, so they
    contribute nothing to scan and are dropped — the same distinction
    `registries.json` already draws for its own item-count math.
    """
    out: dict[str, list[tuple[str, int]]] = {}
    seen = set(exclude)
    for row in registries:
        name = str(row.get("name", ""))
        if not name or name in seen or row.get("list_only"):
            continue
        kind = str(row.get("type", "skill"))
        out.setdefault(kind, []).append((name, int(row.get("est_items") or 0)))
    for kind in out:
        out[kind].sort(key=lambda pair: (-pair[1], pair[0]))
    return out


def oversized(pools: dict[str, list[tuple[str, int]]], cap: int | None
              ) -> list[tuple[str, int]]:
    """The candidates over ``cap``, largest first — what `select` will skip."""
    if cap is None:
        return []
    return sorted(((n, e) for pool in pools.values() for n, e in pool if e > cap),
                  key=lambda pair: (-pair[1], pair[0]))


def select(pools: dict[str, list[tuple[str, int]]], target: int,
           cap: int | None = None) -> list[tuple[str, int]]:
    """Round-robin across types, largest first within each, until ``target``.

    A candidate whose ``est_items`` exceeds ``cap`` is skipped; ``None`` means
    no cap, which is what the pure-selection tests below want.

    Deterministic: the pools are already sorted, and the cycle order is fixed.
    Two runs over the same committed data must produce the same file or the
    ``--check`` gate is meaningless.
    """
    if cap is not None:
        pools = {k: [(n, e) for n, e in v if e <= cap] for k, v in pools.items()}
    cursors = dict.fromkeys(pools, 0)
    picked: list[tuple[str, int]] = []
    total = 0
    order = [k for k in TYPE_ORDER if k in pools] + \
            [k for k in sorted(pools) if k not in TYPE_ORDER]
    while total < target:
        progressed = False
        for kind in order:
            pool = pools.get(kind, [])
            i = cursors[kind]
            if i >= len(pool):
                continue
            name, est = pool[i]
            cursors[kind] = i + 1
            picked.append((name, est))
            total += est
            progressed = True
            if total >= target:
                break
        if not progressed:          # every pool exhausted before the target
            break
    return picked


def existing_pins(text: str) -> dict[str, str]:
    """``repo -> its committed row``, so a regeneration keeps what was measured.

    Without this the generator and `eval_corpus.py --refresh` fight: the refresh
    writes a commit and an entry count onto every distractor, and the next
    `--check` then calls the file stale because the generator emits bare names.
    One of the two would lose every month.

    So `--check` verifies the *selection* — which registries are in and in what
    order — and leaves the pins to the job that actually measured them.
    """
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        out[line.split()[0]] = line.rstrip()
    return out


def render(required: Sequence[str], picked: Sequence[tuple[str, int]],
           target: int, pinned: dict[str, str] | None = None, *,
           skipped: Sequence[tuple[str, int]] = (),
           cap: int | None = None) -> str:
    """The taps-scale.txt text, header included.

    The required corpus's size is summed from the rows being copied, never
    typed: a literal here was written into the file on every run, including
    the one the monthly refresh makes right after moving those rows.
    """
    pinned = pinned or {}
    est = sum(e for _n, e in picked)
    measured = sum(int(parts[2]) for parts in (row.split() for row in required)
                   if len(parts) > 2)
    lines = [
        "# GENERATED by scripts/build_scale_corpus.py — do not hand-edit.",
        "# Regenerate with that script; CI checks it with --check.",
        "#",
        "# The Tier 1b SCALE corpus: the required corpus (tests/eval/taps.txt)",
        "# plus distractors, so a metric difference between the two tiers isolates",
        "# the effect of the added candidates rather than confounding it with a",
        "# different set of targets. Every golden target lives in the required",
        "# rows, which are copied here verbatim — pins and counts included.",
        "#",
        "# Scheduled, never required. It exists because the required gate measures",
        "# %s entries and a real install carries ~71,655, where all four floors"
        % f"{measured:,}",
        "# fail. It is A scale, not THE scale: hit@1 decays continuously with corpus",
        "# size and never plateaus, so no size here can be canonical.",
        "#",
        "# %d distractor registries, %s est items (the curated list's own estimate)."
        % (len(picked), f"{est:,}"),
        "# est_items under-reports by about %.1fx against a real install, so that"
        % EST_TO_ACTUAL,
        "# projects to roughly %s actual entries — a projection, not a measurement."
        % f"{int(est * EST_TO_ACTUAL):,}",
        "# The real counts are written in by `eval_corpus.py --refresh`, which is",
        "# also what pins these rows. Regenerating KEEPS any pin already here, so",
        "# --check verifies the selection, not the pins.",
        "#",
        "# Target: %s est items. Selection: required rows first, then curated"
        % f"{target:,}",
        "# registries largest-first WITHIN each type, round-robin across types —",
        "# straight largest-first lets the 341-strong skill tail crowd out the 26",
        "# rule registries, and a corpus that is 95% skills is not an install.",
    ]
    if cap is not None:
        lines += [
            "#",
            "# No one distractor may carry more than %s est items (%d%% of the"
            % (f"{cap:,}", round(cap * 100 / target) if target else 0),
            "# target), so the corpus is not one registry's vocabulary. Skipped:",
        ]
        lines += ["#   %s (%s)" % (n, f"{e:,}") for n, e in skipped] or ["#   none"]
    lines += [
        "",
        "# --- the required corpus, verbatim (holds every golden target) ---",
    ]
    lines.extend(required)
    lines += ["", "# --- distractors, curated registries (bare until the "
                  "first --refresh pins them) ---"]
    lines.extend(pinned.get(name, name) for name, _est in picked)
    return "\n".join(lines) + "\n"


def build(target: int) -> str:
    registries = json.loads(REGISTRIES.read_text(encoding="utf-8"))["registries"]
    required = required_rows(REQUIRED_TAPS.read_text(encoding="utf-8"))
    pools = candidates(registries, [repo_of(r) for r in required])
    prior = existing_pins(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    cap = int(target * MAX_SHARE)
    return render(required, select(pools, target, cap), target, prior,
                  skipped=oversized(pools, cap), cap=cap)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="build_scale_corpus.py", description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="fail if the committed file is not what this produces")
    ap.add_argument("--target-est", type=int, default=DEFAULT_TARGET,
                    metavar="N", help="stop once this many est_items are picked "
                                      "(default %d)" % DEFAULT_TARGET)
    args = ap.parse_args(argv)
    text = build(args.target_est)
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("%s is stale — regenerate with "
                  "`python3 scripts/build_scale_corpus.py`"
                  % OUT.relative_to(ROOT), file=sys.stderr)
            return 1
        print("scale corpus list is up to date.")
        return 0
    OUT.write_text(text, encoding="utf-8")
    rows = [ln for ln in text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    print("wrote %s — %d repositories" % (OUT.relative_to(ROOT), len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
