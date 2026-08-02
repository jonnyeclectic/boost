#!/usr/bin/env python3
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

Run:  python3 scripts/page_budget.py [-v]
"""
from __future__ import annotations

import argparse
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple

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
#: Measured 2026-08-02 (bytes / elements / depth):
#:   roadmap.html 525,472 / 7,484 / 10   ·   commands.html 86,026 / 1,512 /  8
#:   index.html    58,352 /   488 / 12   ·   mcp-hub.html  51,162 /   607 / 10
#:   design-roadmap 45,931 /  727 / 10   ·   eval.html     36,320 /   528 / 10
#:   carousel.html 27,829 /   328 / 14   ·   adapters.html 23,559 /   306 / 11
#:
#: Depth is uniform and tight on purpose. Every page here nests 8-14 deep and
#: none has any reason to go deeper, so unlike bytes and elements it is not a
#: growth budget at all — it is a "the markup went structurally strange" alarm,
#: and the roadmap board is no more nested than the smallest page on the site.
BUDGETS: Dict[str, Budget] = {
    "roadmap.html": Budget(
        kbytes=720, elements=10_000, depth=20,
        why="the code board — already 5x Lighthouse's DOM-size failure "
            "threshold, so this bounds a step change, not ordinary growth"),
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


def measure(text: str) -> Tuple[int, int, int]:
    """``(bytes, elements, max_depth)`` for one page's markup."""
    shape = _Shape()
    shape.feed(text)
    shape.close()
    return len(text.encode("utf-8")), shape.elements, shape.depth


def budget_for(name: str) -> Budget:
    return BUDGETS.get(name, BUDGETS["*"])


def check_page(name: str, text: str) -> List[str]:
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
    problems: List[str] = []
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
