#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Bound how large the generated docs pages are allowed to get.

WHY THIS EXISTS. `docs/roadmap.html` scored 0.810, 0.840 and 0.850 across the
three runs of one Lighthouse job against a `minScore` of 0.85. It passed because
`aggregationMethod: median-run` picked the 0.850 — two of its three runs were
below the floor. Nothing local could see any of it: `build_roadmap.py --check`,
`a11y_check.py`, `check_anchors.py` and `test_roadmap_fresh.py` all pass on a
page that fails CI, because none of them models render cost, and `lighthouse` is
not a required check, so the signal was both too late to act on and too quiet to
enforce.

WHAT THIS IS NOT. It is not a predictor of the Lighthouse score, and it must not
be described as one. That was measured, twice, and both times the answer was no:
collapsing `declined` bodies into `<details>` cut laid-out body text 33% below
main and moved the score by 0.00, and trimming 3,066 characters of card prose
also moved it by 0.00. A page of this size is simply not sensitive to a percent
of content. Claiming a correlation here would be inventing one.

WHAT IT IS. A growth budget. The roadmap board's own closing observation is that
it "only grows" — 200 cards and half a megabyte of markup, one card at a time,
each increment too small to argue with. This makes the size a number that is
printed on every run and a ceiling that has to be raised deliberately, so a step
change is a decision someone made rather than a drift nobody watched.

WHY ELEMENT COUNT LEADS. Lighthouse scores DOM size as a diagnostic with
published thresholds — a warning above 800 elements and a failure above 1,400.
`roadmap.html` carries 7,484, which is 5x the failing threshold and an order of
magnitude past every other page here (`commands.html`, the next largest, is
1,512). So this is the one dimension where the page is known to be off the scale
by the tool's own published standard, rather than by inference.

WHY THE CEILINGS ARE LOOSE. A ceiling set just above today's measurement would
fire on the next shipped card and be raised reflexively, which is worse than no
check: it teaches people that the number is noise. These are set to catch a step
change — roughly a doubling — not ordinary growth.

TWO NUMBERS GATE, NOT ONE. `test_the_board_still_has_headroom_to_grow` fails the
board at 80% of its ceiling, so the number that actually stops a build is
`elements * 0.8`, not `elements`. Choosing the ceiling without that factor is
how the first pair of numbers here missed its own stated intent: 10,000 was set
against a measured 7,484, which reads as 1.34x but gated at 8,000 — 516 elements
of usable room, about ten cards, for a budget whose docstring said it bounded a
doubling. It was reached in a day. Pick the ceiling so that FOUR FIFTHS of it is
the step change worth waking up for.

Run:  python3 scripts/page_budget.py [-v]
"""
from __future__ import annotations

import argparse
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# Elements that never close, so they must not push the depth counter.
VOID = frozenset((
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr"))


class Budget(NamedTuple):
    """Ceilings for one page. ``why`` is printed when one is exceeded."""

    kbytes: int
    elements: int
    depth: int
    why: str


#: Per-page ceilings; ``*`` is the default for any page without its own row.
#: Measured 2026-08-03 (bytes / elements / depth):
#:   roadmap.html 565,883 / 7,951 / 10   ·   commands.html 86,070 / 1,512 /  8
#:   index.html    63,239 /   488 / 12   ·   mcp-hub.html  51,163 /   607 / 10
#:   design-roadmap 48,187 /  746 / 10   ·   eval.html     36,321 /   528 / 10
#:   carousel.html 27,830 /   328 / 14   ·   adapters.html 23,560 /   306 / 11
#:   demo.html     21,348 /   119 /  9   ·   chat.html     11,681 /   126 / 10
#:
#: The board moved 7,484 -> 7,951 elements in the 24 hours after these ceilings
#: shipped, which is the growth rate they were written to tolerate rather than a
#: step change — and it was enough to reach the 8,000 gate. Regenerate this block
#: with `python3 scripts/page_budget.py -v` when you raise a ceiling; a stale
#: measurement is what makes the next raise a guess.
#:
#: Depth is uniform and tight on purpose. Every page here nests 8-14 deep and
#: none has any reason to go deeper, so unlike bytes and elements it is not a
#: growth budget at all — it is a "the markup went structurally strange" alarm,
#: and the roadmap board is no more nested than the smallest page on the site.
BUDGETS: dict[str, Budget] = {
    "roadmap.html": Budget(
        kbytes=1_200, elements=16_000, depth=20,
        why="the code board — already 5x Lighthouse's DOM-size failure "
            "threshold, so this bounds a step change, not ordinary growth; "
            "raised deliberately 2026-08-03 from 720/10,000, which gated at "
            "8,000 and was reached by ordinary card growth in a day"),
    "commands.html": Budget(
        kbytes=180, elements=3_000, depth=20,
        why="generated from COMMANDS, so it grows a block per new command"),
    "*": Budget(
        kbytes=150, elements=2_000, depth=20,
        why="default for a hand-written page; a page that needs more than this "
            "should say why in BUDGETS rather than raise the default for all"),
}


class _Shape(HTMLParser):
    """Element count and maximum nesting depth, from the markup alone.

    Deliberately stdlib and deliberately static. The thing that made the
    Lighthouse signal useless was needing a browser to see it, and a check that
    cannot run in the required `lint` job is a check nobody reads in time.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements = 0
        self.depth = 0
        self._open = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        self.elements += 1
        if tag in VOID:
            return
        self._open += 1
        self.depth = max(self.depth, self._open)

    def handle_startendtag(self, tag: str, attrs) -> None:
        # `<br/>`: counted, but self-closing, so it never nests.
        self.elements += 1

    def handle_endtag(self, tag: str) -> None:
        if tag not in VOID:
            self._open = max(0, self._open - 1)


def measure(text: str) -> tuple[int, int, int]:
    """``(bytes, elements, max_depth)`` for one page's markup."""
    shape = _Shape()
    shape.feed(text)
    shape.close()
    return len(text.encode("utf-8")), shape.elements, shape.depth


def budget_for(name: str) -> Budget:
    return BUDGETS.get(name, BUDGETS["*"])


def check_page(name: str, text: str) -> list[str]:
    """Ceilings this page exceeds, as printable lines. Empty when it fits."""
    nbytes, elements, depth = measure(text)
    budget = budget_for(name)
    out = []
    if nbytes > budget.kbytes * 1000:
        out.append("%s: %d kB of markup, over the %d kB ceiling (%s)"
                   % (name, nbytes // 1000, budget.kbytes, budget.why))
    if elements > budget.elements:
        out.append("%s: %d elements, over the %d ceiling (%s)"
                   % (name, elements, budget.elements, budget.why))
    if depth > budget.depth:
        out.append("%s: nested %d deep, over the %d ceiling (%s)"
                   % (name, depth, budget.depth, budget.why))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="page_budget.py", description=__doc__)
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print every page's measurements, not just failures")
    args = ap.parse_args(argv)

    pages = sorted(DOCS.glob("*.html"))
    if not pages:
        print("no pages under docs/ — nothing to budget", file=sys.stderr)
        return 1
    problems: list[str] = []
    if args.verbose:
        print("%-24s %9s %9s %6s" % ("page", "bytes", "elements", "depth"))
    for path in pages:
        text = path.read_text(encoding="utf-8")
        nbytes, elements, depth = measure(text)
        if args.verbose:
            budget = budget_for(path.name)
            print("%-24s %9d %9d %6d   (ceiling %d kB / %d / %d)"
                  % (path.name, nbytes, elements, depth,
                     budget.kbytes, budget.elements, budget.depth))
        problems.extend(check_page(path.name, text))
    if problems:
        print("\npage budget exceeded:")
        for line in problems:
            print("  %s" % line)
        print("\nThese ceilings bound a STEP CHANGE, not ordinary growth, and "
              "they are not a\nLighthouse predictor — measured, a 33% cut in "
              "laid-out body text moved that\nscore by 0.00. Raising one is a "
              "decision to make deliberately, in BUDGETS,\nwith the reason "
              "written down.")
        return 1
    print("page-budget: OK — %d pages under their markup, DOM and depth ceilings"
          % len(pages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
