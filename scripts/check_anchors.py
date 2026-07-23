#!/usr/bin/env python3
"""Verify every local link and #fragment in the docs site resolves.

lychee (the links workflow) checks external URLs and that local files exist,
but it does not resolve fragments into local HTML — and that is exactly where
a dangling anchor hides, because the roadmap boards are GENERATED from card
copy in docs/roadmap/items/*.md. A bad href there is invisible until the page
renders.

Checks, treating docs/ as the Pages root (docs/index.html is the site root, so
`../style/boost.css` correctly resolves to the repo-root stylesheet):
  * in-page `#frag`      -> an element with that id/name exists on the page
  * `other.html#frag`    -> the target file exists AND carries that anchor
  * `path/to/asset.css`  -> the file exists on disk

Usage:  python3 scripts/check_anchors.py [--docs docs]
"""
from __future__ import annotations

import argparse
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_PREFIXES = ("http://", "https://", "mailto:", "data:", "javascript:", "tel:")


class _Page(HTMLParser):
    """Collect anchor ids and every href/src on one page."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: set = set()
        self.refs: list = []

    def handle_starttag(self, tag, attrs) -> None:
        d = dict(attrs)
        for key in ("id", "name"):
            if d.get(key):
                self.ids.add(d[key])
        for key in ("href", "src"):
            if d.get(key):
                self.refs.append(d[key])


def _parse(path: Path) -> _Page:
    page = _Page()
    page.feed(path.read_text(encoding="utf-8"))
    return page


def check(docs_dir: Path) -> list:
    """Return a list of human-readable problems (empty when everything resolves)."""
    problems: list = []
    cache: dict = {}
    for page_path in sorted(docs_dir.glob("*.html")):
        page = _parse(page_path)
        for raw in page.refs:
            ref = raw.strip()
            if not ref or ref.startswith(SKIP_PREFIXES):
                continue
            if ref.startswith("#"):
                frag = ref[1:]
                if frag and frag not in page.ids:
                    problems.append("%s: dangling in-page anchor %s"
                                    % (page_path.name, ref))
                continue
            rel, _, frag = ref.partition("#")
            if not rel:
                continue
            target = (page_path.parent / rel).resolve()
            if not target.exists():
                problems.append("%s: missing local target %s" % (page_path.name, ref))
                continue
            if frag and target.suffix == ".html":
                if target not in cache:
                    cache[target] = _parse(target)
                if frag not in cache[target].ids:
                    problems.append("%s: %s -> no anchor #%s in %s"
                                    % (page_path.name, ref, frag, target.name))
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--docs", default=str(ROOT / "docs"))
    args = ap.parse_args(argv)

    docs_dir = Path(args.docs)
    problems = check(docs_dir)
    pages = len(list(docs_dir.glob("*.html")))
    if problems:
        for p in problems:
            print("  " + p, file=sys.stderr)
        print("check-anchors: FAILED — %d broken reference(s) across %d pages"
              % (len(problems), pages), file=sys.stderr)
        print("hint: the roadmap boards are GENERATED — fix the link in the "
              "matching docs/roadmap/items/*.md, then rerun "
              "scripts/build_roadmap.py", file=sys.stderr)
        return 1
    print("check-anchors: OK — every local link and anchor resolves across "
          "%d pages" % pages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
