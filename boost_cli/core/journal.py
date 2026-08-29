# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The pulse journal: append-only feed of skill-management events.

Powers `boost pulse`, `boost trending`, `boost stats`, and `boost who`.
"""
from __future__ import annotations

import json

from . import paths, util

ROTATE_AT = 5000
ROTATE_KEEP = 2500


def log(action: str, subject: str = "", **fields) -> None:
    """Append one event line to the pulse feed, rotating when oversized.

    None-valued keyword fields are dropped from the record.
    """
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": util.user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def events(n: int | None = None, action: str | None = None,
           subject: str | None = None) -> list[dict]:
    """Most-recent-first list of journal events; ``n=None`` means all of them.

    ``n`` must be >= 0: a negative would become a negative slice and silently
    return every event *but* the oldest ones, so it raises instead.
    """
    if n is not None and n < 0:
        raise ValueError("events(n=%d): n must be >= 0" % n)
    p = paths.pulse_path()
    if not p.exists():
        return []
    out = []
    # errors="replace": one torn append must not make the whole feed
    # unreadable — the corrupt line simply fails to parse as JSON below.
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if action and e.get("action") != action:
            continue
        if subject and e.get("subject") != subject:
            continue
        out.append(e)
    out.reverse()
    return out if n is None else out[:n]


def _line_count(p) -> int:
    """Lines in `p`, closing the handle rather than leaving it to the GC.

    Decodes leniently: the feed carries user-supplied text and a torn append
    can leave a partial multi-byte sequence behind. A strict decode raises
    UnicodeDecodeError, which is a ValueError — it would sail past the OSError
    guard below and take down every command that logs, forever, over one bad
    byte in an advisory feed.
    """
    with p.open(encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def rotation_healthy() -> bool:
    """True when the pulse feed is absent or at most ROTATE_AT lines long."""
    p = paths.pulse_path()
    if not p.exists():
        return True
    return _line_count(p) <= ROTATE_AT


def _maybe_rotate() -> None:
    """Trim the feed to ROTATE_KEEP lines once it passes ROTATE_AT.

    Rotation is a read-modify-write of the whole file, and this repo's own
    working model expects concurrent boost processes. Unserialized, two of
    them could each read the feed, each build a snapshot, and the second
    write would silently drop whatever the first had appended in between.

    So rotation runs under a lock, and a process that cannot take it simply
    returns: another one is already trimming, and doing it twice adds nothing.
    Inside the lock the file is re-read — the count that got us here was taken
    outside it and may already be stale — and anything appended between that
    read and the swap is carried into the new file rather than dropped.
    `log()` itself stays lock-free: O_APPEND writes of a single short record
    do not tear, and making every command contend on a lock to protect an
    advisory feed would be a bad trade.
    """
    p = paths.pulse_path()
    try:
        if _line_count(p) <= ROTATE_AT:
            return
    except OSError:
        return
    with util.try_lock(p.with_name(p.name + ".rotate.lock")) as locked:
        if not locked:
            return
        try:
            raw = p.read_bytes()
            lines = raw.decode("utf-8", "replace").splitlines()
            if len(lines) <= ROTATE_AT:
                return                      # someone else already rotated
            keep = lines[-ROTATE_KEEP:]
            # Re-read past the point we stopped, so an append that landed
            # while we were building the snapshot survives it.
            with p.open("rb") as f:
                f.seek(len(raw))
                keep += f.read().decode("utf-8", "replace").splitlines()
        except OSError:
            return
        util.atomic_write_text(p, "\n".join(keep) + "\n")
