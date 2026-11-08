# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Opt-in second opinion from the skills.sh search index.

boost's own search reads only what is tapped on this machine, and never sends
a query anywhere. skills.sh (the index behind ``npx skills find`` and
vercel-labs/skills' find-skills skill) indexes skills across GitHub and
counts installs — the two things a local catalogue cannot know. This module
asks it, and only when the user turned it on:

- ``skills_sh.enabled`` in config.json, or ``BOOST_SKILLS_SH=1`` for one run,
  or ``boost search --skills-sh`` for one search. Off by default, because it
  sends the query text to a third party.
- ``BOOST_NO_NET`` wins over all three, as it does for every request boost
  makes.

The endpoint is the one ``npx skills find`` calls (``vercel-labs/skills``
``src/find.ts``): ``GET https://skills.sh/api/search?q=<query>[&owner=<o>]``,
no auth, answering ``{"skills": [{"id", "source", "skillId", "name",
"installs"}]}``. Every field is third-party data that ends up on a terminal
or in an agent's context, so each is validated rather than trusted: a
``source`` that is not ``owner/repo`` is dropped, control characters are
stripped, and ``installs`` must be a non-negative int.

A failure of any kind — offline, timeout, a 5xx, a changed shape — returns no
hits and a one-line reason. It never takes local search down with it.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

from boost_cli.core import config, nethttp, typedvalue

BASE_URL = "https://skills.sh"
TIMEOUT = 5.0
#: How many skills.sh hits a search shows; its API returns its own page size.
SHOW = 5

#: A GitHub owner/repo, as GitHub allows them. Anything else in ``source`` is
#: not something `boost tap` could clone, so the hit is dropped.
_SOURCE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def enabled(force: bool = False) -> bool:
    """Whether a search may ask skills.sh. ``force`` is ``--skills-sh``."""
    if typedvalue.env_flag("BOOST_NO_NET", unknown=True):
        return False
    if force or typedvalue.env_flag("BOOST_SKILLS_SH"):
        return True
    return bool(config.get("skills_sh.enabled", False))


def _clean(value) -> str:
    return _CONTROL.sub("", str(value or "")).strip()


def parse(payload) -> list[dict]:
    """Validated hits from a decoded response; malformed rows are dropped."""
    rows = payload.get("skills") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("response has no `skills` list")
    hits: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        source = _clean(row.get("source"))
        name = _clean(row.get("skillId") or row.get("name"))
        installs = row.get("installs")
        if not _SOURCE.fullmatch(source) or not _NAME.fullmatch(name):
            continue
        if isinstance(installs, bool) or not isinstance(installs, int) \
                or installs < 0:
            installs = None
        hits.append({"source": source, "name": name, "installs": installs})
    return hits


def search(query: str, owner: str | None = None,
           timeout: float = TIMEOUT) -> tuple[list[dict], str | None]:
    """Ask skills.sh. Returns ``(hits, None)``, or ``([], reason)`` on failure."""
    params = {"q": query}
    if owner:
        params["owner"] = owner
    url = "%s/api/search?%s" % (BASE_URL, urllib.parse.urlencode(params))
    # https and a fixed host, never a caller's URL: BASE_URL is a constant.
    req = urllib.request.Request(url, headers={"Accept": "application/json"})  # noqa: S310
    try:
        with nethttp.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read(2_000_000).decode("utf-8"))
        return parse(payload), None
    except Exception as e:
        return [], "skills.sh did not answer (%s)" % (
            type(e).__name__ if not str(e) else str(e)[:120])


def split_by_tapped(hits: list[dict],
                    tapped: set[str]) -> tuple[list[dict], list[dict]]:
    """Hits whose repo is already tapped here, and hits that would need a tap.

    Compared without case: GitHub names are case-insensitive, and a tap's
    configured name keeps whatever case the user typed.
    """
    low = {t.lower() for t in tapped}
    here = [h for h in hits if h["source"].lower() in low]
    away = [h for h in hits if h["source"].lower() not in low]
    return here, away


def install_hint(hit: dict, tapped: bool) -> str:
    """How to get ``hit``: read then install if tapped, else tap and read.

    Untapped, the next step is the tap and a read, not an install: the body
    is what tells a debugged procedure from a stub, and it cannot be read
    until the repo is tapped. `boost cat` then names the install command.
    """
    qualified = "%s:%s" % (hit["source"], hit["name"])
    if tapped:
        return "boost cat %s, then boost install %s" % (qualified, qualified)
    return "boost tap %s, then boost cat %s" % (hit["source"], qualified)


def hit_line(hit: dict, tapped: bool) -> str:
    """One hit as plain text: name, repo, installs, and how to get it."""
    n = hit.get("installs")
    count = ("%s installs" % format(n, ",")) if isinstance(n, int) else \
        "installs unknown"
    return "%s  %s  (%s) — `%s`" % (hit["name"], hit["source"], count,
                                   install_hint(hit, tapped))


def tapped_names() -> set[str]:
    """The ``owner/repo`` names configured as taps here; empty on any error."""
    try:
        from boost_cli.core import registry
        return {t.name for t in registry.list_taps()}
    except Exception:
        return set()


def section(query: str, *, force: bool = False, owner: str | None = None,
            show: int = SHOW, fetch=None) -> list[str]:
    """Plain-text lines that follow a search, or ``[]`` when not enabled.

    One renderer for ``boost search`` and ``boost_search``, so an agent and a
    person read the same block. ``fetch`` replaces :func:`search` in tests.
    """
    if not enabled(force):
        return []
    hits, err = (fetch or search)(query, owner)
    if err:
        return ["skills.sh: " + err]
    if not hits:
        return ["skills.sh: no matches for %r" % query]
    here = {h["source"].lower() for h in split_by_tapped(
        hits, tapped_names())[0]}
    lines = ["On skills.sh (installs are its users' counts; nothing there is "
             "reviewed, so read one before installing it):"]
    lines.extend("  " + hit_line(h, h["source"].lower() in here)
                 for h in hits[:show])
    return lines
