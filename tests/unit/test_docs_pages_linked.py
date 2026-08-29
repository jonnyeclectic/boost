# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Every shipped ``docs/*.html`` page is reachable from the main page.

The Visual Guide (``docs/index.html``) is the front door to the docs site. A new
page that nothing on the front door links to is an orphan — reachable only if you
already know its URL (this is exactly how ``mcp-hub.html`` shipped). This test is
the standing enforcement of "a new ``docs/*.html`` means a new nav link": it
fails if any sibling page isn't linked from ``index.html``.

Skips when the repo-root ``docs/`` tree isn't reachable (e.g. the mutation
sandbox, which only copies ``boost_cli/``).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DOCS = _ROOT / "docs"
_INDEX = _DOCS / "index.html"

_HREF = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def linked_pages(html: str) -> set:
    """Basenames of the local ``*.html`` pages linked from ``html``.

    Fragment-only (``#top``) and off-site (``https://…``) hrefs are ignored; a
    query string or fragment on a local link is stripped so ``roadmap.html#foo``
    still counts as linking ``roadmap.html``.
    """
    pages = set()
    for href in _HREF.findall(html):
        if href.startswith("#") or "://" in href:
            continue
        target = href.split("#", 1)[0].split("?", 1)[0]
        if target.lower().endswith(".html"):
            pages.add(Path(target).name)
    return pages


@pytest.mark.skipif(not _INDEX.exists(),
                    reason="repo-root docs/ not reachable (e.g. mutation sandbox)")
def test_every_docs_page_is_linked_from_index():
    linked = linked_pages(_INDEX.read_text(encoding="utf-8"))
    shipped = {p.name for p in _DOCS.glob("*.html") if p.name != "index.html"}
    orphans = sorted(shipped - linked)
    assert not orphans, (
        "these docs/*.html pages are orphaned — nothing in docs/index.html "
        "links to them:\n    " + "\n    ".join(orphans) + "\n"
        "Add a nav link (a new docs page means a new nav link)."
    )


class TestLinkedPages:
    def test_extracts_local_html_basename(self):
        assert linked_pages('<a href="roadmap.html">R</a>') == {"roadmap.html"}

    def test_strips_fragment_and_query(self):
        html = '<a href="mcp-hub.html#top">H</a><a href="x.html?v=1">X</a>'
        assert linked_pages(html) == {"mcp-hub.html", "x.html"}

    def test_ignores_fragment_only_and_offsite(self):
        html = '<a href="#what">W</a><a href="https://x.io/y.html">Y</a>'
        assert linked_pages(html) == set()

    def test_ignores_non_html_targets(self):
        assert linked_pages('<a href="style/boost.css">c</a>') == set()

    def test_case_insensitive_attribute_and_extension(self):
        assert linked_pages("<a HREF='Foo.HTML'>f</a>") == {"Foo.HTML"}

    def test_deduplicates_repeated_links(self):
        html = '<a href="a.html">1</a><a href="a.html#z">2</a>'
        assert linked_pages(html) == {"a.html"}

    def test_empty_html_has_no_links(self):
        assert linked_pages("") == set()
