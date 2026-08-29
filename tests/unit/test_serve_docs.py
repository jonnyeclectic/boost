# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: scripts/serve_docs.py — serving docs the way Pages serves them.

WHY THIS FILE EXISTS. The `lighthouse` job scored `roadmap.html` 0.79 three
times against a 0.80 floor while `uses-text-compression` scored 0 and
`transferSize` equalled `resourceSize` — the harness served the document
uncompressed, which GitHub Pages does not. These tests pin the properties that
makes true: compressible types are compressed, already-compressed types are left
alone, a client that does not ask still gets raw bytes, and the headers describe
the bytes actually sent.

NO SOCKET IS BOUND. The handler is driven over an in-memory pair of buffers
instead of a listening port. That is not only for the sandboxes that refuse to
bind one — a test that needs a free port is a test that fails on a busy machine
for reasons having nothing to do with the code under test.
"""
from __future__ import annotations

import gzip
import importlib.util
import io
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "serve_docs.py"

pytestmark = pytest.mark.skipif(
    not _SCRIPT.exists(), reason="repo-root script not reachable")


def _load():
    spec = importlib.util.spec_from_file_location("serve_docs", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Wire(io.BytesIO):
    """A write buffer the handler is allowed to `close()` without losing it."""

    def close(self):
        # Not discarding the bytes is the whole point: the handler closes its
        # `wfile` in `finish()`, and a real BytesIO would drop the response.
        pass


class _Socket:
    """Just enough socket for `BaseHTTPRequestHandler.setup()`."""

    def __init__(self, request: bytes):
        self._in = io.BytesIO(request)
        self.out = _Wire()

    def makefile(self, mode="r", *args, **kwargs):
        return self.out if "w" in mode else self._in

    def close(self):
        pass

    # `BaseHTTPRequestHandler.finish()` may flush and shut the connection down.
    def shutdown(self, how):
        pass

    def sendall(self, data):
        self.out.write(data)


def _request(mod, target, accept_encoding=None, method="GET"):
    """Run one request through `GzipHandler`; return `(headers, body)`."""
    lines = ["%s %s HTTP/1.0" % (method, target), "Host: 127.0.0.1"]
    if accept_encoding:
        lines.append("Accept-Encoding: %s" % accept_encoding)
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode()
    sock = _Socket(raw)
    mod.GzipHandler(sock, ("127.0.0.1", 41234), None)
    head, _sep, body = sock.out.getvalue().partition(b"\r\n\r\n")
    headers = {}
    for line in head.decode("latin-1").split("\r\n")[1:]:
        if ":" in line:
            k, _c, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()
    return headers, body


@pytest.fixture
def site(tmp_path, monkeypatch):
    """A tiny two-file site as the process CWD, plus the loaded module."""
    (tmp_path / "page.html").write_text("<p>%s</p>" % ("hello " * 400),
                                        encoding="utf-8")
    # A PNG header followed by noise: already-compressed bytes, so gzipping it
    # would spend CPU to make it bigger.
    (tmp_path / "pic.png").write_bytes(
        b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 8)
    monkeypatch.chdir(tmp_path)
    return _load(), tmp_path


class TestWhatGetsCompressed:
    def test_markup_is_gzipped_and_round_trips(self, site):
        mod, root = site
        headers, body = _request(mod, "/page.html", "gzip")
        assert headers["content-encoding"] == "gzip"
        assert gzip.decompress(body) == (root / "page.html").read_bytes()

    def test_the_length_header_describes_the_bytes_sent(self, site):
        # A Content-Length taken from the uncompressed file is how a client
        # ends up waiting for bytes that already arrived.
        mod, _root = site
        headers, body = _request(mod, "/page.html", "gzip")
        assert int(headers["content-length"]) == len(body)

    def test_compression_actually_shrinks_the_document(self, site):
        mod, _root = site
        _h, gz = _request(mod, "/page.html", "gzip")
        _h2, raw = _request(mod, "/page.html")
        assert len(gz) < len(raw) / 4, (
            "the point of this harness is the size difference: %d vs %d"
            % (len(gz), len(raw)))

    def test_an_image_is_not_compressed(self, site):
        # Already-compressed bytes: gzip costs CPU and adds bytes, and Pages
        # does not do it either.
        mod, _root = site
        headers, _body = _request(mod, "/pic.png", "gzip")
        assert "content-encoding" not in headers

    def test_a_client_that_does_not_ask_gets_raw_bytes(self, site):
        # The uncompressed path has to stay reachable — it is what `curl` with
        # no header gets, and what any tool measuring raw weight expects.
        mod, _root = site
        headers, body = _request(mod, "/page.html")
        assert "content-encoding" not in headers
        assert body.startswith(b"<p>hello")

    def test_a_head_reports_the_compressed_length(self, site):
        # HEAD and GET must agree, or a client sizes the response wrong. This
        # is why the override is on `send_head` and not on `do_GET`.
        mod, _root = site
        get_h, get_body = _request(mod, "/page.html", "gzip")
        head_h, head_body = _request(mod, "/page.html", "gzip", method="HEAD")
        assert head_body == b""
        assert head_h["content-length"] == get_h["content-length"]
        assert int(head_h["content-length"]) == len(get_body)

    def test_a_missing_file_is_still_a_404(self, site):
        mod, _root = site
        sock = _Socket(b"GET /nope.html HTTP/1.0\r\nAccept-Encoding: gzip\r\n\r\n")
        mod.GzipHandler(sock, ("127.0.0.1", 41234), None)
        assert b"404" in sock.out.getvalue().split(b"\r\n")[0]


class TestTheTypeTable:
    @pytest.mark.parametrize("ctype", [
        "text/html", "text/html; charset=utf-8", "text/css",
        "application/javascript", "application/json", "image/svg+xml",
    ])
    def test_text_shaped_types_compress(self, ctype):
        assert _load().compressible(ctype)

    @pytest.mark.parametrize("ctype", [
        "image/png", "image/webp", "font/woff2", "application/zip", "", None,
    ])
    def test_binary_types_do_not(self, ctype):
        assert not _load().compressible(ctype)


class TestTheHarnessAgrees:
    def test_the_ready_line_matches_what_lighthouse_waits_for(self):
        """A drift here hangs the job until it times out instead of failing.

        `startServerReadyPattern` is a regex lighthouse-ci watches stdout for
        before it starts collecting. If the script's banner stops matching, the
        job does not say "banner changed" — it waits, then dies of timeout.
        """
        rc = json.loads(
            (_ROOT / ".lighthouserc.json").read_text(encoding="utf-8"))
        collect = rc["ci"]["collect"]
        assert collect["startServerReadyPattern"] in _load().READY

    def test_the_rc_starts_this_script(self):
        rc = json.loads(
            (_ROOT / ".lighthouserc.json").read_text(encoding="utf-8"))
        assert "serve_docs.py" in rc["ci"]["collect"]["startServerCommand"], (
            "plain `http.server` is what served the page uncompressed in the "
            "first place")

    def test_the_port_the_rc_serves_is_the_port_it_audits(self):
        # Two numbers in one file that have to match, and nothing checked them.
        rc = json.loads(
            (_ROOT / ".lighthouserc.json").read_text(encoding="utf-8"))
        collect = rc["ci"]["collect"]
        port = collect["startServerCommand"].split("--port")[1].split()[0]
        for url in collect["url"]:
            assert ":%s/" % port in url, url
