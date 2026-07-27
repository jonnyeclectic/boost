"""The `boost serve` HTTP catalog server — a small read-only view of the
installed skills plus JSON endpoints, extracted from the command layer.

The routing is a pure function (:func:`route`) that maps a request path to a
``(status, content_type, body)`` triple with no socket bound, so the whole
endpoint surface is unit-testable. :func:`serve_http` wires it into a threaded
stdlib HTTP server for the CLI.
"""
from __future__ import annotations

import contextlib
import errno
import html
import json
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Tuple

from .. import __version__
from ..errors import BoostError
from . import catalog, lockfile, logs, registry, store
from . import output as out

SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validated_skill_name(name: str) -> Optional[str]:
    """Return canonical trusted skill name, else None."""
    if not isinstance(name, str):
        return None
    if not SKILL_NAME_RE.fullmatch(name) or name in {".", ".."}:
        return None
    return name


_PAGE_CSS = ("body{background:#111;color:#ddd;font-family:ui-monospace,SFMono-Regular,"
             "Menlo,monospace;max-width:720px;margin:2rem auto;padding:0 1rem}"
             "h1{color:#fff;font-size:1.3rem}a{color:#7dc4ff;text-decoration:none}"
             "a:hover{text-decoration:underline}table{border-collapse:collapse;width:100%}"
             "th,td{text-align:left;padding:.3rem .8rem .3rem 0;"
             "border-bottom:1px solid #2a2a2a}.dim{color:#777}")


def serve_page() -> str:
    """The HTML index: a table of installed skills with JSON-endpoint links."""
    installed = lockfile.installed()
    entries = catalog.all_entries()
    taps = registry.list_taps()
    rows = "".join(
        '<tr><td><a href="/skill/%s">%s</a></td><td>%s</td><td>%s</td></tr>'
        % (urllib.parse.quote(n), html.escape(n),
           html.escape(str(e.get("version", "?"))),
           html.escape(str(e.get("tap", "?"))))
        for n, e in sorted(installed.items()))
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<title>boost — skill catalog</title><style>%s</style></head><body>"
            "<h1>⚡ boost <span class='dim'>v%s</span></h1>"
            "<p class='dim'>%d installed · %d available across %d taps</p>"
            "<table><tr><th>skill</th><th>version</th><th>tap</th></tr>%s</table>"
            "<p><a href='/installed.json'>installed.json</a> · "
            "<a href='/catalog.json'>catalog.json</a></p></body></html>"
            % (_PAGE_CSS, __version__, len(installed), len(entries), len(taps),
               rows or "<tr><td colspan='3' class='dim'>nothing installed</td></tr>"))


def _is_within(base, target) -> bool:
    """True when target resolves inside base (or equals base)."""
    try:
        base_r = base.resolve(strict=False)
        target_r = target.resolve(strict=False)
        target_r.relative_to(base_r)
    except (OSError, ValueError):
        return False
    return True


def _safe_join_within(base, rel):
    """Resolve base/rel and return it only when contained within base."""
    try:
        base_r = base.resolve(strict=False)
        rel_p = rel if hasattr(rel, "is_absolute") else __import__("pathlib").Path(rel)
        if rel_p.is_absolute():
            return None
        candidate = (base_r / rel_p).resolve(strict=False)
        candidate.relative_to(base_r)
    except (OSError, ValueError, TypeError):
        return None
    return candidate


def skill_text(name: str) -> Optional[str]:
    """SKILL.md text for an installed skill, else from a tap. None if unknown."""
    trusted_name = _validated_skill_name(name)
    if trusted_name is None:
        return None
    base = store.skill_store_dir(trusted_name)
    fp = _safe_join_within(base, Path("SKILL.md"))
    if fp is not None and _is_within(base, fp) and fp.is_file():
        return fp.read_text(encoding="utf-8", errors="replace")
    for e in catalog.find(trusted_name):
        try:
            tap_base = registry.get(e["tap"]).path
            rel = Path(e["skill_md"])
            if rel.is_absolute() or ".." in rel.parts:
                continue
            fp = _safe_join_within(tap_base, rel)
        except (BoostError, TypeError, ValueError):
            continue
        if fp is None or not _is_within(tap_base, fp):
            continue
        if fp.is_file():
            return fp.read_text(encoding="utf-8", errors="replace")
    return None


def _json_body(obj) -> bytes:
    return json.dumps(obj, indent=2).encode()


def route(path: str) -> Tuple[int, str, bytes]:
    """Map a GET path to ``(status, content_type, body)``. Pure — no socket.

    Mirrors the historical dispatch exactly: ``/`` and ``/index.html`` serve the
    HTML page; ``/catalog.json`` and ``/installed.json`` the JSON views; a
    ``/skill/<name>`` path the raw SKILL.md (404 for an invalid or unknown name);
    anything else a JSON ``not found``.
    """
    path = urllib.parse.unquote(path.split("?", 1)[0])
    if path in ("/", "/index.html"):
        return 200, "text/html; charset=utf-8", serve_page().encode()
    if path == "/catalog.json":
        return 200, "application/json", _json_body(catalog.all_entries())
    if path == "/installed.json":
        return 200, "application/json", _json_body(lockfile.read())
    if path.startswith("/skill/"):
        name = path[len("/skill/"):].strip("/")
        if not SKILL_NAME_RE.fullmatch(name):
            return (404, "application/json",
                    json.dumps({"error": "no skill named %r" % name}).encode())
        text = skill_text(name)
        if text is None:
            return (404, "application/json",
                    json.dumps({"error": "no skill named %r" % name}).encode())
        return 200, "text/plain; charset=utf-8", text.encode()
    return 404, "application/json", json.dumps({"error": "not found"}).encode()


class _CatalogHandler(BaseHTTPRequestHandler):
    server_version = "boost/" + __version__

    # `fmt`, not the base class's `format`: the stdlib only ever calls this
    # positionally, and `format` would shadow the builtin (and read as an
    # unused variable to vulture). The name-mismatch override warning is
    # cosmetic here, so it's suppressed at the line rather than repo-wide.
    def log_message(self, fmt, *args):  # pyright: ignore[reportIncompatibleMethodOverride]
        pass  # request logging happens in _send instead

    def _send(self, status: int, ctype: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        out.dim("  %s %s → %d" % (self.command, self.path, status))

    def do_GET(self):
        try:
            status, ctype, body = route(self.path)
            self._send(status, ctype, body)
        except BrokenPipeError:
            pass
        except Exception as e:
            # Never leak internal exception detail (filesystem paths, state) to
            # the HTTP client — it reaches remote callers when the server is
            # exposed with `--host 0.0.0.0`. Log the specifics server-side and
            # return a generic body.
            logs.get_logger().warning("serve: %s %s failed: %s: %s",
                                      self.command, self.path,
                                      type(e).__name__, e)
            with contextlib.suppress(Exception):
                self._send(500, "application/json",
                           json.dumps({"error": "internal server error"}).encode())


def serve_http(host: str, port: int) -> None:
    """Bind and run the catalog server until interrupted (blocks)."""
    try:
        httpd = ThreadingHTTPServer((host, port), _CatalogHandler)
    except OSError as e:
        # Windows can report a bind against an already-LISTENing port as
        # WinError 10013 (WSAEACCES) rather than EADDRINUSE.
        if e.errno == errno.EADDRINUSE or (
            sys.platform == "win32" and getattr(e, "winerror", None) == 10013
        ):
            raise BoostError("port %d is already in use" % port,
                            hint="pick another with --port") from e
        raise BoostError("cannot bind %s:%d — %s" % (host, port, e),
                        hint="check --host and --port") from e
    out.info("⚡ serving skill catalog on http://%s:%d %s"
             % (host, port, out.c("(ctrl-c to stop)", out.DIM)))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()
        out.ok("server stopped")
    finally:
        httpd.server_close()
