#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Accessibility gate for the docs pages — WCAG 2.1 AA, no browser required.

    python3 scripts/a11y_check.py           # audit docs/*.html
    python3 scripts/a11y_check.py -v        # list every page checked
    python3 scripts/a11y_check.py --list    # list the rules and exit

Two halves, both pure stdlib so this runs in the lint job beside the other
`--check` gates rather than needing Node, Chrome or a network fetch:

* **Structure** — the WCAG failures that are decidable from the markup alone:
  a missing ``lang``, an image with no ``alt``, a link or button with no
  accessible name, a duplicate ``id``, a skipped heading level, a form control
  with nothing to label it.
* **Contrast** — the 1.4.3 ratios for the Aurora tokens, computed from
  ``style/boost.css`` itself, for the ink/ground pairs the CSS actually puts
  together. The palette leans on muted ``--text-2``/``--text-3`` against dark
  glass, which is exactly where AA slips.

What this deliberately does NOT cover is anything that needs layout or a live
DOM: focus order, visible focus rings, ARIA state as computed, reflow at 320px.
Those are the axe-core sweep's job (tests/visual/), which needs a real browser
and therefore cannot be a cheap always-on gate. Static analysis is the floor,
not the ceiling — see docs/DEBUGGING.md.
"""
from __future__ import annotations

import argparse
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
CSS = ROOT / "style" / "boost.css"

# WCAG 1.4.3: normal text needs 4.5:1, large text (>=24px, or >=18.66px bold)
# needs 3.0:1. Everything audited here is body-sized, so 4.5 is the floor.
AA_NORMAL = 4.5

RULES = {
    "html-has-lang": "<html> carries a lang attribute (WCAG 3.1.1)",
    "image-alt": "every <img> has an alt attribute (WCAG 1.1.1)",
    "link-name": "every <a> has an accessible name (WCAG 2.4.4)",
    "button-name": "every <button> has an accessible name (WCAG 4.1.2)",
    "form-label": "every form control can be labelled (WCAG 3.3.2)",
    "duplicate-id": "ids are unique (WCAG 4.1.1)",
    "heading-order": "heading levels never skip (WCAG 1.3.1)",
    "page-has-h1": "each page has exactly one <h1> (WCAG 1.3.1)",
    "contrast": "text/background pairs meet %.1f:1 (WCAG 1.4.3)" % AA_NORMAL,
}

# Void elements never have an end tag, so the parser must not wait for one.
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}


class _Auditor(HTMLParser):
    """Collect structural WCAG findings from one page's markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.findings: list = []
        self._ids: dict = {}
        self._headings: list = []
        self._link = None
        self._link_text = ""
        self._button = None
        self._button_text = ""

    # -- helpers ---------------------------------------------------------
    def _add(self, rule: str, message: str, line=None) -> None:
        self.findings.append((line or self.getpos()[0], rule, message))

    # -- tag handling ----------------------------------------------------
    def handle_starttag(self, tag, attrs) -> None:
        a = dict(attrs)
        line = self.getpos()[0]

        if tag == "html" and not (a.get("lang") or "").strip():
            self._add("html-has-lang", "<html> has no lang attribute", line)
        if tag == "img" and "alt" not in a:
            self._add("image-alt",
                      "<img src=%r> has no alt attribute" % a.get("src", "?"), line)
        if "id" in a:
            prior = self._ids.get(a["id"])
            if prior:
                self._add("duplicate-id",
                          "id=%r first used on line %d" % (a["id"], prior), line)
            else:
                self._ids[a["id"]] = line
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._headings.append((line, int(tag[1])))
        if tag == "a":
            self._link = (line, a)
            self._link_text = ""
        if tag == "button":
            self._button = (line, a)
            self._button_text = ""
        if tag in ("input", "select", "textarea"):
            # A control is labellable via aria-*, a title, or an id a <label for>
            # can point at. Hidden and submit-style inputs carry their own name.
            kind = (a.get("type") or "").lower()
            if kind in ("hidden", "submit", "reset", "button", "image"):
                return
            if not any(a.get(k) for k in ("aria-label", "aria-labelledby",
                                          "id", "title")):
                self._add("form-label",
                          "<%s> has nothing to associate a label with" % tag, line)

    def handle_startendtag(self, tag, attrs) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data) -> None:
        if self._link is not None:
            self._link_text += data
        if self._button is not None:
            self._button_text += data

    def handle_endtag(self, tag) -> None:
        if tag == "a" and self._link is not None:
            line, a = self._link
            if not self._accessible_name(self._link_text, a):
                self._add("link-name",
                          "<a href=%r> has no accessible name"
                          % a.get("href", "?"), line)
            self._link = None
        if tag == "button" and self._button is not None:
            line, a = self._button
            if not self._accessible_name(self._button_text, a):
                self._add("button-name", "<button> has no accessible name", line)
            self._button = None

    @staticmethod
    def _accessible_name(text: str, attrs: dict) -> str:
        """The name a screen reader would announce, or "" if there is none."""
        return (text.strip()
                or (attrs.get("aria-label") or "").strip()
                or (attrs.get("aria-labelledby") or "").strip()
                or (attrs.get("title") or "").strip())

    # -- whole-document checks -------------------------------------------
    def finish(self) -> list:
        """Findings that need the whole document, appended to the per-tag ones."""
        levels = [lvl for _line, lvl in self._headings]
        if levels.count(1) != 1:
            self._add("page-has-h1",
                      "page has %d <h1> elements, expected exactly 1"
                      % levels.count(1), 1)
        previous = 0
        for line, level in self._headings:
            if previous and level > previous + 1:
                self._add("heading-order",
                          "h%d follows h%d — skips h%d"
                          % (level, previous, previous + 1), line)
            previous = level
        return sorted(self.findings)


# --------------------------------------------------------------------------
# contrast
# --------------------------------------------------------------------------
_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _channel(value: int) -> float:
    """One sRGB channel, linearized per WCAG's relative-luminance formula."""
    c = value / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    """Relative luminance of a #rgb / #rrggbb color (WCAG 2.1 definition)."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a: str, b: str) -> float:
    """Contrast ratio between two colors — 1.0 (identical) to 21.0 (b/w)."""
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def read_tokens(css_text: str) -> dict:
    """``{--token: #hex}`` for every plain hex custom property in the CSS."""
    tokens = {}
    for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", css_text):
        value = value.strip()
        if _HEX.match(value):
            tokens[name] = value
    return tokens


# The ink/ground pairs the stylesheet actually renders together. Listing them
# explicitly rather than testing the cross-product keeps the gate honest: a pair
# that never co-occurs is not a real contrast failure, and flagging it would
# train people to ignore this check.
#
# The hover surface is checked as well as the resting one. Only listing the
# resting surface let --text-3 pass at 4.53:1 and then fail at 4.15:1 the moment
# a card lit up under the cursor — the gate was blind to the state a reader is
# actually in while reading a card.
PAIRS = (
    ("--text", "--bg"), ("--text-2", "--bg"), ("--text-3", "--bg"),
    ("--text", "--surface-1"), ("--text-2", "--surface-1"),
    ("--text-3", "--surface-1"),
    ("--text", "--surface-2"), ("--text-2", "--surface-2"),
    ("--text-3", "--surface-2"),
    ("--text", "--surface-3"), ("--text-2", "--surface-3"),
    ("--text-3", "--surface-3"),
    ("--text", "--panel-solid"), ("--text-2", "--panel-solid"),
    ("--text-3", "--panel-solid"),
    ("--cyan", "--bg"), ("--violet", "--bg"), ("--pink", "--bg"),
    ("--blue", "--bg"), ("--sky", "--bg"), ("--green", "--bg"),
    ("--yellow", "--bg"),
    ("--text", "--term-bg"), ("--text-2", "--term-bg"),
)


def check_contrast(css_text: str) -> list:
    """Findings for every declared pair below the AA floor."""
    tokens = read_tokens(css_text)
    findings = []
    for ink, ground in PAIRS:
        if ink not in tokens or ground not in tokens:
            findings.append((0, "contrast",
                             "pair (%s, %s) names a token that no longer exists"
                             % (ink, ground)))
            continue
        ratio = contrast(tokens[ink], tokens[ground])
        if ratio < AA_NORMAL:
            findings.append((0, "contrast",
                             "%s (%s) on %s (%s) is %.2f:1, below %.1f:1"
                             % (ink, tokens[ink], ground, tokens[ground],
                                ratio, AA_NORMAL)))
    return findings


# --------------------------------------------------------------------------
def audit_page(path: Path) -> list:
    """Structural findings for one HTML file."""
    parser = _Auditor()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return parser.finish()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="list every page checked, not just failures")
    ap.add_argument("--list", action="store_true",
                    help="list the rules this gate enforces and exit")
    args = ap.parse_args(argv)

    if args.list:
        for rule, description in sorted(RULES.items()):
            print("  %-16s %s" % (rule, description))
        return 0

    pages = sorted(DOCS.glob("*.html"))
    if not pages:
        print("a11y: no pages found under %s" % DOCS)
        return 2

    failures = 0
    for page in pages:
        findings = audit_page(page)
        if findings:
            failures += len(findings)
            print("%s — %d issue%s"
                  % (page.relative_to(ROOT), len(findings),
                     "" if len(findings) == 1 else "s"))
            for line, rule, message in findings:
                print("  L%-5d %-14s %s" % (line, rule, message))
        elif args.verbose:
            print("%s — clean" % page.relative_to(ROOT))

    contrast_findings = check_contrast(CSS.read_text(encoding="utf-8"))
    if contrast_findings:
        failures += len(contrast_findings)
        print("%s — %d contrast issue%s"
              % (CSS.relative_to(ROOT), len(contrast_findings),
                 "" if len(contrast_findings) == 1 else "s"))
        for _line, rule, message in contrast_findings:
            print("  %-14s %s" % (rule, message))
    elif args.verbose:
        print("%s — %d contrast pairs clean" % (CSS.relative_to(ROOT), len(PAIRS)))

    if failures:
        print("\na11y: FAIL — %d issue%s across %d page%s"
              % (failures, "" if failures == 1 else "s",
                 len(pages), "" if len(pages) == 1 else "s"))
        return 1
    print("a11y: OK — %d pages and %d contrast pairs meet WCAG 2.1 AA"
          % (len(pages), len(PAIRS)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
