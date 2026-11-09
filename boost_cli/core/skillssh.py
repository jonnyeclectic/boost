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
from collections.abc import Callable

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
    # `is True`, not truthiness: `config set` coerces "no" to False, but a
    # hand-edited "no" string would read as on, and this switch sends data.
    return config.get("skills_sh.enabled", False) is True


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


#: Where a hit stands against this machine's taps.
UNTAPPED, TAPPED, NOT_IN_COPY = "untapped", "tapped", "not-in-copy"


def state(hit: dict, local: dict[str, set[str]]) -> str:
    """:data:`TAPPED`, :data:`UNTAPPED`, or :data:`NOT_IN_COPY`.

    ``local`` maps a lower-cased tap name to the item names its catalogue
    holds. skills.sh's ``skillId`` is boost's item name for 201 of the 206
    hits measured in locally tapped repos (5 queries, 500 hits, 2026-11-08);
    the five that differ are skills newer than the local clone. So a tapped
    repo that lacks the name gets "update the tap", not a `boost cat` that
    would answer "no skill named ...". Repo names compare without case:
    GitHub's are case-insensitive and a tap keeps whatever case was typed.
    """
    names = local.get(hit["source"].lower())
    if names is None:
        return UNTAPPED
    return TAPPED if hit["name"] in names else NOT_IN_COPY


def install_hint(hit: dict, where: str) -> str:
    """The next step for ``hit``, which is never an unread install.

    Untapped, it is the tap and a read: the body is what tells a debugged
    procedure from a stub, and it cannot be read until the repo is tapped.
    `boost cat` then names the install command.
    """
    qualified = "%s:%s" % (hit["source"], hit["name"])
    if where == TAPPED:
        return "boost cat %s, then boost install %s" % (qualified, qualified)
    if where == NOT_IN_COPY:
        return ("boost update %s, then boost cat %s — your copy of the tap "
                "predates it" % (hit["source"], qualified))
    return "boost tap %s, then boost cat %s" % (hit["source"], qualified)


def hit_line(hit: dict, where: str) -> str:
    """One hit as plain text: name, repo, installs, and the next step."""
    n = hit.get("installs")
    count = ("%s installs" % format(n, ",")) if isinstance(n, int) else \
        "installs unknown"
    return "%s  %s  (%s) — `%s`" % (hit["name"], hit["source"], count,
                                   install_hint(hit, where))


def local_names(sources: set[str]) -> dict[str, set[str]]:
    """Item names per tapped repo, for the repos in ``sources`` only.

    Lower-cased keys. Loads just the taps a reply names, from their cached
    catalogues. Any failure reads as "nothing tapped": the hint then says
    to tap, which is still a command that works.
    """
    try:
        from boost_cli.core import catalog, registry
        want = {s.lower() for s in sources}
        out: dict[str, set[str]] = {}
        for tap in registry.list_taps():
            key = tap.name.lower()
            if key in want:
                out[key] = {str(e.get("name") or "")
                            for e in catalog.load_tap(tap)}
        return out
    except Exception:
        return {}


def section(query: str, *, force: bool = False, owner: str | None = None,
            show: int = SHOW, fetch=None,
            keep: Callable[[str], bool] | None = None) -> list[str]:
    """Plain-text lines that follow a search, or ``[]`` when not enabled.

    One renderer for ``boost search`` and ``boost_search``, so an agent and a
    person read the same block. ``fetch`` replaces :func:`search` in tests.
    """
    if not enabled(force):
        return []
    hits, err = (fetch or search)(query, owner)
    if err:
        return ["skills.sh: " + err]
    if keep is not None:
        # A `--tap` the API has no parameter for: narrow by source here.
        hits = [h for h in hits if keep(h["source"])]
    if not hits:
        return ["skills.sh: no matches for %r" % query]
    hits = hits[:show]
    local = local_names({h["source"] for h in hits})
    lines = ["On skills.sh (installs are its users' counts; nothing there is "
             "reviewed, so read one before installing it):"]
    lines.extend("  " + hit_line(h, state(h, local)) for h in hits)
    return lines
