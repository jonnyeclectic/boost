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
import sys
from pathlib import Path


def strip_comments(text: str) -> str:
    """``text`` with ``//`` and ``/* */`` comments outside strings blanked.

    The JSONC a host such as Gemini CLI accepts (it parses its settings with
    ``strip-json-comments`` then ``JSON.parse``). Each comment character becomes
    a space and every line break is kept, so a :class:`json.JSONDecodeError`
    on the result still names the line and column of the original file, and
    ``strip_comments(t) != t`` is exactly "``t`` has a comment in it". An
    unterminated block comment runs to the end, as it does upstream.
    """
    out: list[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == nxt == "/":
            end = text.find("\n", i)
            end = n if end == -1 else end
            out.append(" " * (end - i))
            i = end
            continue
        if ch == "/" and nxt == "*":
            end = text.find("*/", i + 2)
            end = n if end == -1 else end + 2
            out.append("".join(c if c in "\r\n" else " " for c in text[i:end]))
            i = end
            continue
        if ch == '"':
            in_str = True
        out.append(ch)
        i += 1
    return "".join(out)


def read_object(path: Path, jsonc: bool = False) -> tuple[dict | None, str | None]:
    """Parse `path` as a JSON object.

    ``jsonc`` parses it the way a host that allows comments does, through
    :func:`strip_comments` first.

    Returns ``(data, None)`` when the file is missing (``data`` is ``None``)
    or holds a valid JSON object. Returns ``(None, message)`` when the file
    exists but can't be read as one — unreadable, not UTF-8, invalid JSON, or
    valid JSON that isn't an object — where ``message`` names the file and
    the underlying error so a caller can warn instead of quietly treating
    corruption the same as "nothing here yet".

    Not UTF-8 is its own branch because a failed decode raises
    ``UnicodeDecodeError``, a ``ValueError`` that is neither an ``OSError``
    nor a ``JSONDecodeError``: two stray bytes in config.json used to crash
    every command, ``boost doctor`` included. Any reader of a state file
    should come through here rather than pair its own ``read_text`` with
    ``json.loads``, so a hole like that is closed in one place.
    """
    if not path.exists():
        return None, None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, "%s: %s" % (path, exc)
    except UnicodeDecodeError as exc:
        return None, "%s: not valid UTF-8 (%s)" % (path, exc)
    try:
        data = json.loads(strip_comments(text) if jsonc else text)
    except json.JSONDecodeError as exc:
        return None, "%s: invalid JSON (%s)" % (path, exc)
    if not isinstance(data, dict):
        return None, "%s: expected a JSON object, found %s" % (
            path, type(data).__name__)
    return data, None


def read_list(path: Path) -> tuple[list | None, str | None]:
    """:func:`read_object` for a state file whose top level is a JSON array.

    Same contract — ``(None, None)`` for a missing file, ``(data, None)`` for
    a valid array, ``(None, message)`` for anything else — so a writer of a
    list-shaped store (``trusted_keys.json``) can tell "nothing here yet" from
    "something here I am about to destroy".
    """
    if not path.exists():
        return None, None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, "%s: %s" % (path, exc)
    except UnicodeDecodeError as exc:
        return None, "%s: not valid UTF-8 (%s)" % (path, exc)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, "%s: invalid JSON (%s)" % (path, exc)
    if not isinstance(data, list):
        return None, "%s: expected a JSON array, found %s" % (
            path, type(data).__name__)
    return data, None


def object_map_error(data: dict, key: str) -> str | None:
    """Why ``data[key]`` is not an object whose every value is an object.

    ``None`` when it is, or when ``key`` is absent. A state file can parse as
    an object and still hold ``{"skills": "x"}`` or ``{"skills": {"a": 1}}``,
    and every reader that then calls ``.get`` on a record crashes with an
    AttributeError — so a reader checks the shape it is about to walk here,
    once, instead of each call site meeting it as exit 70.
    """
    if key not in data:
        return None
    value = data[key]
    if not isinstance(value, dict):
        return "%r is a %s, not an object" % (key, type(value).__name__)
    for name, record in value.items():
        if not isinstance(record, dict):
            return "%r entry %r is a %s, not an object" % (
                key, name, type(record).__name__)
    return None


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


def save(path: Path, text: str, *, corrupt: bool, noun: str = "file",
         show=str, wrap: bool = False) -> None:
    """Replace state file `path` with `text`, moving a `corrupt` one aside first.

    Every small state writer (focus and context, policy, trusted keys,
    cohorts, profiles, bmad) used to end in a bare ``write_text``: under a
    ``~/.boost/state`` that refuses writes each one crashed at exit 70 with a
    ``PermissionError`` traceback. Here the quarantine and the write share one
    ``try``, so a refusal is a :class:`BoostError` naming the file and the
    ``chmod`` that clears it (:func:`paths.save_refused`, the wording
    ``config.save`` uses), and the write is atomic, so a reader never sees a
    half-written file. `noun` and `show` word the quarantine warning the way
    each caller always has.
    """
    from . import output, paths, util
    paths.create_dirs((*paths.boost_dirs(), path.parent))
    try:
        if corrupt:
            dest = quarantine(path)
            output.warn("%s was corrupt and has been moved to %s before "
                        "writing the new %s" % (show(path), show(dest), noun),
                        stream=sys.stderr, wrap=wrap)
        util.atomic_write_text(path, text)
    except OSError as e:
        raise paths.save_refused(path, e) from e

