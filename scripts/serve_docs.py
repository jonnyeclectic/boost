#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Serve the repo over HTTP the way GitHub Pages serves it: compressed.

WHY THIS EXISTS. The `lighthouse` job scored `docs/roadmap.html` at 0.79 against
a 0.80 floor — three runs, 0.79 every time, so not the sampling luck that the
floor was lowered to 0.80 to escape. Pulled from that job's own artifact, the
score decomposes exactly:

    FCP  3,638 ms  score 0.31  x10       SI  3,638 ms  score 0.86  x10
    LCP  3,858 ms  score 0.53  x25      TBT    100 ms  score 0.98  x30
    CLS      0     score 1.00  x25   ->  3.1 + 8.6 + 13.25 + 29.4 + 25 = 79.35

The whole 21-point deficit is FCP and LCP. Both are transfer-bound, and the same
report says why: `uses-text-compression` scores **0**, with `transferSize`
567,874 against `resourceSize` 567,685 — the document arrives uncompressed,
because `python3 -m http.server` has never sent `Content-Encoding`. Lighthouse
throttles to 1,474.56 kbps, so 567,685 bytes is 3.08 s of download for the HTML
alone, which is the 3.6 s FCP with nothing left to explain.

GitHub Pages, meanwhile, answers `content-encoding: gzip` for that exact URL —
checked against the live site, not assumed. Lighthouse estimates gzip takes the
document to 173,407 B and the stylesheet to 9,831 B, saving 404 KiB and 1,950 ms.

So the job was scoring a page 3.3x larger than the one any visitor receives, and
every conclusion drawn from it inherited that. Two rounds of work had already
gone into "making the page faster" — collapsing card bodies into `<details>`
(0.00) and trimming 3,066 characters of prose (0.00) — and neither could have
moved the number, because both changed *layout* work while the score was being
decided by *transfer* bytes. `content-visibility: auto` bought 0.01, which is
about all that was available: TBT already scores 0.98.

WHAT THIS IS NOT. It is not a way to make the number look better. It is the
opposite — it makes the number mean something, by measuring the bytes that are
actually sent. If the page is genuinely slow once compressed, this reports that,
and the floor should be raised until it hurts.

WHAT IT COMPRESSES. The types Pages compresses: text/*, JavaScript, JSON, XML
and SVG. Never images or fonts, which are already compressed and would only cost
CPU. And only when the client asks — a client that sends no `Accept-Encoding`
gets the raw bytes, which is what makes the uncompressed path still reachable.

Run:  python3 scripts/serve_docs.py [--port 8099] [--bind 127.0.0.1]
"""
from __future__ import annotations

import argparse
import gzip
import io
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

#: Compressed by GitHub Pages, and worth compressing: markup, styles, scripts
#: and data. `image/svg+xml` is in because SVG is text; every other image type
#: and every font is deliberately out — already-compressed bytes only get bigger.
COMPRESSIBLE = (
    "text/",
    "application/javascript",
    "application/json",
    "application/xml",
    "application/xhtml+xml",
    "image/svg+xml",
)

#: gzip's default. Level 9 costs measurably more CPU for ~1% fewer bytes, and a
#: harness that is slower than the thing it measures gets switched off.
LEVEL = 6

#: `.lighthouserc.json` waits for this substring before it starts collecting.
#: `test_serve_docs.py` pins the two together, because the failure mode when
#: they drift is a job that hangs until it times out rather than one that says
#: what went wrong.
READY = "Serving HTTP"


def compressible(ctype: str | None) -> bool:
    """True if `ctype` is a type Pages would compress."""
    if not ctype:
        return False
    return ctype.split(";")[0].strip().startswith(COMPRESSIBLE)


class GzipHandler(SimpleHTTPRequestHandler):
    """`SimpleHTTPRequestHandler`, plus the `Content-Encoding` Pages sends.

    `protocol_version` is left at the base class's HTTP/1.0 on purpose. Raising
    it to 1.1 would enable keep-alive and cut handshakes, which moves the same
    metrics compression moves — and then the score change this PR reports would
    have two causes and no way to separate them. One variable at a time.
    """

    def send_head(self):  # type: ignore[override]
        """Return the body to send, gzipped when the client asked and it helps.

        Overriding `send_head` rather than `do_GET` keeps HEAD honest: the base
        class calls this for both verbs, so a HEAD reports the same
        `Content-Length` a GET would actually deliver.
        """
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()          # directory index: not worth it
        accepted = self.headers.get("Accept-Encoding", "")
        ctype = self.guess_type(path)
        if "gzip" not in accepted or not compressible(ctype):
            return super().send_head()
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
            mtime = os.stat(path).st_mtime
        except OSError:
            return super().send_head()          # 404/403 wording stays the base
        # mtime=0: the gzip header otherwise carries a timestamp, which would
        # make two runs of the same file differ byte for byte and turn any
        # future "did the payload change?" check into noise.
        body = gzip.compress(raw, LEVEL, mtime=0)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Last-Modified", self.date_time_string(mtime))
        self.end_headers()
        return io.BytesIO(body)

    def log_message(self, fmt, *args):
        """Quiet. Three Lighthouse runs over two pages is a lot of 200 lines."""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="serve_docs.py", description=__doc__)
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--directory", default=os.getcwd())
    args = ap.parse_args(argv)

    os.chdir(args.directory)
    httpd = ThreadingHTTPServer((args.bind, args.port), GzipHandler)
    print("%s on %s port %d (gzip)" % (READY, args.bind, args.port), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
