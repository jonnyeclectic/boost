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

import errno
import json
import sys
from collections.abc import Callable
from pathlib import Path


class Unreadable(str):
    """The message :func:`read_object`/:func:`read_list` return for a file
    that exists but could not be *read* — an ``OSError`` such as ``EACCES``
    (mode 000) or ``EISDIR`` (a directory sitting on the name).

    Still a ``str``, so every caller that formats the message keeps working;
    one that must act on the difference asks ``isinstance(err, Unreadable)``.
    The difference is the whole point: corrupt bytes are damage, and moving
    them aside to write a fresh file loses nothing, but an unreadable file's
    bytes may be perfectly good — quarantining them to start from defaults
    drops every record they hold, and a ``.corrupt`` backup cannot even be
    copied from a file that cannot be read. The fix is a permission or a
    stray directory, never a rollback (:func:`read_remedy`).
    """

    path: Path
    errno: int | None
    reason: str  # the OSError's strerror, for "could not read X (reason)"


def _unreadable(path: Path, exc: OSError) -> Unreadable:
    # The strerror, not str(exc): that repeats the path ("[Errno 13]
    # Permission denied: '/…/config.json'") right after naming it.
    reason = exc.strerror or str(exc)
    msg = Unreadable("%s: cannot be read (%s)" % (path, reason))
    msg.path = path
    msg.errno = exc.errno
    msg.reason = reason
    return msg


def read_remedy(err: Unreadable,
                show: Callable[[Path], str] = str) -> str:
    """The one step that makes the file behind ``err`` readable again.

    A directory on the name is moved aside (Windows reports reading one as
    ``EACCES``, so the path is asked too); anything else is a permission,
    cleared by ``chmod u+r``. `show` words the path (``paths.tilde``).
    """
    p = err.path
    try:
        is_dir = err.errno == errno.EISDIR or p.is_dir()
    except OSError:
        is_dir = False
    if is_dir:
        return "move the directory %s aside (it is not a file)" % show(p)
    return "make it readable with `chmod u+r %s`" % show(p)


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
    corruption the same as "nothing here yet". A read that failed (an
    ``OSError``) is an :class:`Unreadable` message, not corruption: the bytes
    were never seen, so nothing may be written over them.

    Not UTF-8 is its own branch because a failed decode raises
    ``UnicodeDecodeError``, a ``ValueError`` that is neither an ``OSError``
    nor a ``JSONDecodeError``: two stray bytes in config.json used to crash
    every command, ``boost doctor`` included. Any reader of a state file
    should come through here rather than pair its own ``read_text`` with
    ``json.loads``, so a hole like that is closed in one place.

    A leading UTF-8 byte-order mark is dropped (``utf-8-sig``), not treated
    as corruption: Windows editors save one routinely, ``json.loads`` rejects
    it, and the corrupt-file fallback then let ``hooks add`` replace a valid
    settings.json with a hooks-only one. A writer that must keep the mark
    (``claude_settings.save``) checks the prior bytes for it itself.
    """
    if not path.exists():
        return None, None
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return None, _unreadable(path, exc)
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
    "something here I am about to destroy". A leading byte-order mark is
    dropped here as it is there.
    """
    if not path.exists():
        return None, None
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return None, _unreadable(path, exc)
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
    from ..errors import BoostError
    from . import output, paths, util
    _, err = read_object(path)
    if isinstance(err, Unreadable):
        # Not corrupt: quarantining it would set good bytes aside and
        # replace them with a file built from the empty view the failed
        # read produced.
        raise BoostError("could not read %s (%s) — boost will not write over "
                         "a file it cannot read" % (show(path), err.reason),
                         hint="%s, then re-run" % read_remedy(err, show),
                         wrap=wrap)
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

