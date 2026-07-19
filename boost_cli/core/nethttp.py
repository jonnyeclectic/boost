"""Fork-safe HTTP requests over ``urllib``.

The stdlib **default opener** resolves proxies with ``getproxies()``. On macOS,
when no ``*_proxy`` environment variables are set, that falls back to
``getproxies_macosx_sysconf()`` → ``_scproxy`` → SystemConfiguration /
CoreFoundation — an Obj-C code path that is **not fork-safe** and aborts
(``SIGABRT``) on the child side of a ``fork()`` before ``exec``.

Harmless in today's single-process CLI, but fragile the moment boost runs
post-fork (a future multiprocessing worker, or a host that forks into an
embedding call). Seeding a ``ProxyHandler`` explicitly from
``getproxies_environment()`` — which only ever parses ``*_proxy`` env vars and
never touches the Obj-C machinery — keeps every request deterministic and
fork-safe while still honoring ``HTTP(S)_PROXY`` and ``NO_PROXY``.
"""
from __future__ import annotations

import urllib.request
from typing import Union

_Request = Union[str, urllib.request.Request]


def build_opener() -> urllib.request.OpenerDirector:
    """Build an opener whose proxy config comes only from the environment.

    ``getproxies_environment()`` reads ``HTTP(S)_PROXY``/``NO_PROXY`` and never
    calls into the macOS SystemConfiguration Obj-C path, so the opener it
    produces is safe to use on the child side of a ``fork()``.
    """
    proxies = urllib.request.getproxies_environment()
    return urllib.request.build_opener(urllib.request.ProxyHandler(proxies))


def urlopen(req: _Request, timeout: float):
    """Fork-safe drop-in for ``urllib.request.urlopen``.

    ``timeout`` is required — callers in this codebase always pass one, and a
    missing timeout on a network call is a bug we don't want to allow silently.
    """
    return build_opener().open(req, timeout=timeout)
