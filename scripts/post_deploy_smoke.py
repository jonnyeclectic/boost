#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Post-deploy smoke check for the published docs site.

    python3 scripts/post_deploy_smoke.py
    python3 scripts/post_deploy_smoke.py --base-url http://localhost:8000/ -v

Every other docs gate runs against the working tree: ``html-validate`` and
``a11y_check`` parse the files, ``visual_check.mjs`` loads them over ``file://``.
All of them can be green while the *deployed* site is broken, because deployment
is where the paths change — GitHub Pages serves this repo under ``/boost/``, so a
link that resolves fine on disk can 404 in production.

This asserts the three things that make a deploy actually usable:

* every page answers **200**;
* every **local asset** each page references (stylesheet, script, image, icon)
  resolves — a 404 stylesheet is a site that renders as unstyled text;
* every **internal link** resolves, so the nav does not lead into a 404.

Off-site links are not checked: they are somebody else's uptime, and a flaky
third party must never redden boost's deploy. ``links.yml`` (lychee) owns those.

Exit codes: 0 all good, 1 something is broken, 2 the site could not be reached
at all (which is a different problem from a broken page and is reported as one).
"""
from __future__ import annotations

import argparse
import http.client
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import ClassVar

DEFAULT_BASE = "https://jonnyeclectic.github.io/boost/"

# The pages a user can actually reach: the redirecting root, the guide, and
# everything the shared nav links to.
PAGES = (
    "",                       # the bare site root (a meta-refresh to the guide)
    "docs/index.html",
    "docs/roadmap.html",
    "docs/demo.html",
    "docs/chat.html",
    "docs/design-roadmap.html",
    "docs/commands.html",
    "docs/adapters.html",
    "docs/eval.html",
    "docs/langchain.html",
    "docs/mcp-hub.html",
)

TIMEOUT = 20
UA = "boost-post-deploy-smoke"


class _Refs(HTMLParser):
    """Collect the local asset and link URLs a page references."""

    # (tag, attribute) pairs that load a subresource. A 404 in any of these is a
    # visibly broken page, not a dead end the user has to click to find.
    ASSETS: ClassVar[set] = {("link", "href"), ("script", "src"),
                             ("img", "src"), ("source", "src"),
                             ("video", "poster")}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.assets: set = set()
        self.links: set = set()

    def handle_starttag(self, tag, attrs) -> None:
        a = dict(attrs)
        for t, attr in self.ASSETS:
            if tag == t and a.get(attr):
                # preload/prefetch hints and alternate stylesheets are optional
                # by design; only fail on what the page actually needs.
                if tag == "link" and (a.get("rel") or "").lower() in (
                        "preload", "prefetch", "dns-prefetch", "preconnect"):
                    continue
                self.assets.add(a[attr])
        if tag == "a" and a.get("href"):
            self.links.add(a["href"])
        # <meta http-equiv=refresh content="0; url=...">
        if tag == "meta" and (a.get("http-equiv") or "").lower() == "refresh":
            content = a.get("content") or ""
            if "url=" in content.lower():
                self.links.add(content.lower().split("url=", 1)[1].strip())


def is_local(url: str) -> bool:
    """True for a same-site reference worth checking.

    Skips absolute URLs (somebody else's uptime), bare fragments, and the
    non-http schemes a page legitimately uses.
    """
    if not url or url.startswith("#"):
        return False
    parsed = urllib.parse.urlparse(url)
    return not parsed.scheme and not parsed.netloc


def fetch(url: str, want_body: bool = False):
    """``(status, body)`` for a URL; status is None when it could not be reached.

    ``want_body`` is False for the asset/link sweep, where only the status
    matters — not reading the body is faster and sidesteps the truncated-response
    failures a proxy can inject mid-stream.

    ``http.client.HTTPException`` is caught alongside the ``urllib`` errors: an
    ``IncompleteRead`` is neither an ``HTTPError`` nor a ``URLError``, so without
    it a truncated response crashes the run instead of reporting one bad URL.
    """
    request = urllib.request.Request(  # noqa: S310  https:// site URLs only
        url, headers={"User-Agent": UA},
        method="GET" if want_body else "HEAD")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
            if not want_body:
                return response.status, ""
            try:
                body = response.read()
            except http.client.IncompleteRead as exc:
                # The server answered, then the transfer was cut short — a proxy
                # or a flaky connection, NOT a missing page. Keep the status and
                # parse what did arrive: reporting a 200 page as "unreachable"
                # because its last kilobyte was lost is a false alarm, and the
                # biggest pages are exactly the ones that would trip it.
                body = exc.partial
            return response.status, body.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError):
        return None, ""


def check_page(base: str, page: str, verbose: bool) -> list:
    """Findings for one page: its own status, then its assets and links."""
    url = urllib.parse.urljoin(base, page)
    status, body = fetch(url, want_body=True)
    if status is None:
        return [("unreachable", url, "could not be reached")]
    if status != 200:
        return [("page", url, "HTTP %s" % status)]

    parser = _Refs()
    parser.feed(body)
    findings = []
    seen: set = set()
    for kind, refs in (("asset", parser.assets), ("link", parser.links)):
        for ref in sorted(refs):
            if not is_local(ref):
                continue
            # Drop the fragment: /x.html#frag and /x.html are the same document.
            target = urllib.parse.urljoin(url, ref.split("#", 1)[0])
            if not target or target in seen:
                continue
            seen.add(target)
            ref_status, _ = fetch(target)
            if ref_status != 200:
                findings.append((kind, target,
                                 "HTTP %s (referenced by %s)"
                                 % (ref_status or "unreachable", page or "/")))
    if verbose and not findings:
        print("  %s — 200, %d local refs OK" % (page or "/", len(seen)))
    return findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", default=DEFAULT_BASE,
                    help="site root to check (default: the published site)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="report each page even when it passes")
    args = ap.parse_args(argv)

    base = args.base_url if args.base_url.endswith("/") else args.base_url + "/"
    print("post-deploy smoke: %s" % base)

    # If the root itself is unreachable the site is down; that is a different
    # failure from a broken page and should not be reported as eight of them.
    root_status, _ = fetch(base)
    if root_status is None:
        print("post-deploy: UNREACHABLE — %s did not respond" % base)
        return 2

    findings = []
    for page in PAGES:
        findings += check_page(base, page, args.verbose)

    if findings:
        print("\npost-deploy: FAIL — %d broken reference%s"
              % (len(findings), "" if len(findings) == 1 else "s"))
        for kind, url, detail in findings:
            print("  %-11s %s — %s" % (kind, url, detail))
        return 1
    print("post-deploy: OK — %d pages, every local asset and link resolves"
          % len(PAGES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
