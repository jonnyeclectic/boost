# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Corruption-aware read/quarantine for boost's small JSON state files.

Several files under ``~/.boost`` and each agent's dotdir (``config.json``,
``settings.json``, ``context.json``, a saved profile, ...) are read as "the
merged view, or defaults/empty if the file is missing" and then, on the next
write, replaced outright. Before this module every one of those read sites
folded "missing" and "exists but fails to parse" into the same branch, so a
truncated write or a hand-edited trailing comma degraded to an empty object
with no warning — and the next save then overwrote the corrupt bytes with a
fresh file built from that empty view, discarding whatever was still sitting
on disk. :func:`read_object` keeps those two cases apart so a caller can warn
on the one that means something was actually lost; :func:`quarantine` gives a
writer a way to get the bad bytes out of the way, rather than over them,
before it writes the replacement.
"""
from __future__ import annotations

import json
from pathlib import Path


def read_object(path: Path) -> tuple[dict | None, str | None]:
    """Parse `path` as a JSON object.

    Returns ``(data, None)`` when the file is missing (``data`` is ``None``)
    or holds a valid JSON object. Returns ``(None, message)`` when the file
    exists but can't be read as one — unreadable, invalid JSON, or valid JSON
    that isn't an object — where ``message`` names the file and the
    underlying error so a caller can warn instead of quietly treating
    corruption the same as "nothing here yet".
    """
    if not path.exists():
        return None, None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, "%s: %s" % (path, exc)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, "%s: invalid JSON (%s)" % (path, exc)
    if not isinstance(data, dict):
        return None, "%s: expected a JSON object, found %s" % (
            path, type(data).__name__)
    return data, None


def is_corrupt(path: Path) -> bool:
    """True when `path` exists but :func:`read_object` can't parse it.

    A missing file is not corrupt — callers that only care about "is there a
    bad file sitting here" (rather than the error text) use this instead of
    unpacking the tuple.
    """
    _, err = read_object(path)
    return err is not None


def quarantine(path: Path) -> Path:
    """Move a corrupt `path` aside so a fresh write can land on its name
    without destroying the bad bytes underneath it.

    Picks `<name>.corrupt`, or `<name>.corrupt.N` for the first `N >= 2` that
    doesn't already exist, so repeated corruption never overwrites an earlier
    quarantined copy. Returns the destination. Caller's job to have already
    established `path` is worth quarantining; this itself doesn't parse it.
    """
    dest = path.with_name(path.name + ".corrupt")
    n = 2
    while dest.exists():
        dest = path.with_name("%s.corrupt.%d" % (path.name, n))
        n += 1
    path.rename(dest)
    return dest
