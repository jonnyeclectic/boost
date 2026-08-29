# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: scripts/post_deploy_smoke.py — the deployed-site health check.

The checker's whole job is to notice breakage, so these pin that it *does*: a
404 page, a 404 asset, a 404 internal link and an unreachable site each produce
the right finding, and a healthy site produces none.

``fetch`` is stubbed with a route table rather than standing up a real
``http.server``: the logic under test is the *decision* (which refs to follow,
how to classify a bad one), not urllib. That keeps these hermetic, fast, and
runnable where a socket bind is not permitted — and lets a case produce an
"unreachable" (status ``None``) response on demand, which a live server cannot.
"""
from __future__ import annotations

import http.client
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "post_deploy_smoke.py"

spec = importlib.util.spec_from_file_location("post_deploy_smoke", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
sys.modules["post_deploy_smoke"] = smoke
spec.loader.exec_module(smoke)


@pytest.fixture
def routes(monkeypatch):
    """Stub `fetch` with a {url-suffix: status} table.

    A real `http.server` would need a socket bind, which some sandboxes refuse —
    and the logic under test is the *decision* (which refs to follow, how to
    classify a bad one), not urllib. Stubbing keeps the tests hermetic and fast,
    and lets a case assert on "unreachable" (status None) directly, which a live
    server cannot produce on demand.
    """
    table = {}

    def _fetch(url, want_body=False):
        for suffix, (status, body) in table.items():
            if url.endswith(suffix):
                return status, (body if want_body else "")
        return 404, ""

    monkeypatch.setattr(smoke, "fetch", _fetch)
    return table


BASE = "https://example.test/"

HEALTHY = """<!doctype html><html lang="en"><head>
<link rel="stylesheet" href="style.css"></head>
<body><a href="other.html">other</a></body></html>"""


class TestIsLocal:
    def test_relative_paths_are_local(self):
        assert smoke.is_local("style.css")
        assert smoke.is_local("docs/index.html")
        assert smoke.is_local("/boost/x.html")

    def test_absolute_urls_are_not(self):
        assert not smoke.is_local("https://example.com/x")
        assert not smoke.is_local("//cdn.example.com/x")

    def test_fragments_and_empties_are_not(self):
        assert not smoke.is_local("#top")
        assert not smoke.is_local("")

    def test_non_http_schemes_are_not(self):
        assert not smoke.is_local("mailto:a@b.c")
        assert not smoke.is_local("data:text/plain,x")


class TestRefExtraction:
    def _refs(self, html):
        parser = smoke._Refs()
        parser.feed(html)
        return parser

    def test_collects_stylesheets_scripts_and_images(self):
        refs = self._refs('<link rel="stylesheet" href="a.css">'
                          '<script src="b.js"></script><img src="c.png">')
        assert refs.assets == {"a.css", "b.js", "c.png"}

    def test_collects_anchors(self):
        assert self._refs('<a href="x.html">x</a>').links == {"x.html"}

    def test_preload_hints_are_not_required_assets(self):
        # A preload is an optimisation; a 404 there is not a broken page.
        assert self._refs('<link rel="preload" href="a.woff2">').assets == set()

    def test_meta_refresh_target_is_followed(self):
        refs = self._refs('<meta http-equiv="refresh" content="0; url=docs/index.html">')
        assert "docs/index.html" in refs.links


class TestFindings:
    def test_healthy_site_has_no_findings(self, routes, monkeypatch):
        routes.update({"index.html": (200, HEALTHY), "style.css": (200, ""),
                       "other.html": (200, "")})
        monkeypatch.setattr(smoke, "PAGES", ("index.html",))
        assert smoke.main(["--base-url", BASE]) == 0

    def test_missing_page_is_reported(self, routes, monkeypatch, capsys):
        routes.update({"/": (200, ""), "index.html": (200, "<html lang=en></html>")})
        monkeypatch.setattr(smoke, "PAGES", ("index.html", "gone.html"))
        assert smoke.main(["--base-url", BASE]) == 1
        assert "404" in capsys.readouterr().out

    def test_missing_asset_is_reported(self, routes, monkeypatch, capsys):
        # the stylesheet 404s — the page renders as unstyled text
        routes.update({"index.html": (200, HEALTHY), "other.html": (200, "")})
        monkeypatch.setattr(smoke, "PAGES", ("index.html",))
        assert smoke.main(["--base-url", BASE]) == 1
        out = capsys.readouterr().out
        assert "asset" in out and "style.css" in out

    def test_missing_internal_link_is_reported(self, routes, monkeypatch, capsys):
        routes.update({"index.html": (200, HEALTHY), "style.css": (200, "")})
        monkeypatch.setattr(smoke, "PAGES", ("index.html",))
        assert smoke.main(["--base-url", BASE]) == 1
        out = capsys.readouterr().out
        assert "link" in out and "other.html" in out

    def test_offsite_links_are_not_checked(self, routes, monkeypatch):
        # A third party going down must never redden boost's deploy check.
        routes.update({"index.html": (200,
                       '<html lang="en"><body>'
                       '<a href="https://not-a-real-host.invalid/x">off</a>'
                       '</body></html>')})
        monkeypatch.setattr(smoke, "PAGES", ("index.html",))
        assert smoke.main(["--base-url", BASE]) == 0

    def test_fragment_only_links_are_not_fetched(self, routes, monkeypatch):
        routes.update({"index.html": (200,
                       '<html lang="en"><body><a href="#top">top</a></body></html>')})
        monkeypatch.setattr(smoke, "PAGES", ("index.html",))
        assert smoke.main(["--base-url", BASE]) == 0

    def test_a_target_is_only_fetched_once(self, routes, monkeypatch, capsys):
        routes.update({"index.html": (200,
                       '<html lang="en"><body><a href="x.html">a</a>'
                       '<a href="x.html#frag">b</a></body></html>'),
                       "x.html": (200, "")})
        monkeypatch.setattr(smoke, "PAGES", ("index.html",))
        assert smoke.main(["--base-url", BASE, "-v"]) == 0
        assert "1 local refs OK" in capsys.readouterr().out

    def test_base_url_without_trailing_slash_still_works(self, routes, monkeypatch):
        routes.update({"index.html": (200, "<html lang=en></html>")})
        monkeypatch.setattr(smoke, "PAGES", ("index.html",))
        assert smoke.main(["--base-url", BASE.rstrip("/")]) == 0

    def test_an_unreachable_page_is_distinguished_from_a_404(self, routes,
                                                             monkeypatch, capsys):
        routes.update({"/": (200, ""), "index.html": (None, "")})
        monkeypatch.setattr(smoke, "PAGES", ("index.html",))
        assert smoke.main(["--base-url", BASE]) == 1
        assert "unreachable" in capsys.readouterr().out


class TestUnreachableSite:
    def test_returns_2_not_1(self, monkeypatch, capsys):
        monkeypatch.setattr(smoke, "fetch", lambda *a, **k: (None, ""))
        # A site that is down is a different failure from a broken page, and
        # must not be reported as one finding per page.
        rc = smoke.main(["--base-url", "http://unreachable.invalid/"])
        assert rc == 2
        assert "UNREACHABLE" in capsys.readouterr().out


class TestTruncatedResponses:
    def test_partial_read_keeps_the_status(self, monkeypatch):
        """A cut-short transfer is not a missing page.

        The biggest pages are exactly the ones a proxy truncates, so treating an
        IncompleteRead as "unreachable" would fail the deploy check on the guide
        and the roadmap while they are perfectly fine.
        """
        class _Response:
            status = 200

            def read(self):
                raise http.client.IncompleteRead(b"<html lang='en'>partial", 100)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(smoke.urllib.request, "urlopen",
                            lambda *a, **k: _Response())
        status, body = smoke.fetch("http://example.invalid/x", want_body=True)
        assert status == 200
        assert "partial" in body


class TestPageList:
    def test_every_listed_page_exists_in_the_repo(self):
        # The list is what gets checked after a deploy; a page that was renamed
        # in the repo but not here would go unchecked forever.
        for page in smoke.PAGES:
            if not page:
                continue          # the bare root is the redirect stub
            assert (ROOT / page).is_file(), page

    def test_the_root_redirect_stub_exists(self):
        assert (ROOT / "index.html").is_file()

    def test_default_base_is_the_published_site(self):
        assert smoke.DEFAULT_BASE.startswith("https://")
        assert smoke.DEFAULT_BASE.endswith("/")
