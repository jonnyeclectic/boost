# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The pulse journal: append-only feed of skill-management events.

Powers `boost pulse`, `boost trending`, `boost stats`, and `boost who`.
"""
from __future__ import annotations

import difflib
import json
import sys
from collections.abc import Sequence

from . import output, paths, util

ROTATE_AT = 5000
ROTATE_KEEP = 2500

# Once per process: a command can log more than once, and the fix is the same.
_WARNED_UNSAVED = False
# Same for reading: `health` reads the feed several times in one run.
_WARNED_UNREADABLE = False

# Fields a row's readers treat as text: `pulse` pads `user`, `log` measures
# it, `trending` sorts on `subject`, `is_new_install` hashes `via`. A row
# that holds any of them as a non-string (or is not an object at all) is
# skipped like a torn line, rather than crashing every reader at exit 70.
_TEXT_FIELDS = ("ts", "user", "action", "subject", "via", "tap")

PULSE_EMPTY = "no activity yet — events appear as you install and manage skills"
WHO_EMPTY = ("no journal activity yet — expertise builds as people install, "
             "edit, and evolve skills")

# Actions that reflect hands-on skill expertise, as opposed to any journal
# subject at all (tap names, cohort names, reindex summaries, ...). `who`'s
# per-skill view already filters to this set; the aggregate view must use the
# same set so a "skill" it counts is actually a skill.
EXPERTISE_ACTIONS = ("install", "edit", "evolve", "distill", "tag")


def is_expertise_event(event: dict) -> bool:
    """True when `event`'s action reflects hands-on skill expertise."""
    return event.get("action") in EXPERTISE_ACTIONS


# `via` values for an "install" event that re-applied an item already
# installed: `boost update` upgrading it, `boost reinstall` repairing it. Both
# go through store.install(force=True), which journals "install" every time,
# so without the tag one install and one upgrade read as two installs.
REFRESH_VIAS = frozenset({"update", "reinstall"})


def is_new_install(event: dict) -> bool:
    """True for an "install" event that put an item on this machine, rather
    than refreshing one already there. An uninstall followed by an install is
    a new install; an upgrade is not."""
    return (event.get("action") == "install"
            and event.get("via") not in REFRESH_VIAS)


def log(action: str, subject: str = "", **fields) -> None:
    """Append one event line to the pulse feed, rotating when oversized.

    None-valued keyword fields are dropped from the record.

    Only the feed's own directory is created. This called ``ensure_dirs``,
    so a cache dir that a read-only ``~/.boost`` refused to create failed
    `update` and `compact` at exit 70 after their work was done. The feed is
    a record, not the work: one it cannot write is a warning, not a failure.
    """
    global _WARNED_UNSAVED
    event = {"ts": util.now_iso(), "user": util.user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError as e:
        if not _WARNED_UNSAVED:
            _WARNED_UNSAVED = True
            # The dir that refuses, or else the feed file itself does.
            where = paths.refuses_writes(p.parent) or p
            output.warn("could not record this in the activity feed (%s) — "
                        "`boost pulse` will not show it; make %s writable"
                        % (e.strerror or e, paths.tilde(where)),
                        stream=sys.stderr, wrap=True)
        return
    _maybe_rotate()


def well_formed(row: object) -> bool:
    """True when `row` is a journal object whose text fields are all text.

    A field may be absent (readers default it); present, it must be a str.
    """
    return isinstance(row, dict) and all(
        isinstance(row[k], str) for k in _TEXT_FIELDS if k in row)


def _read() -> tuple[list[dict], int]:
    """Oldest-first well-formed rows, and how many lines were skipped.

    Raises OSError when the feed exists but cannot be read; a missing feed
    is simply empty.
    """
    try:
        # errors="replace": one torn append must not make the whole feed
        # unreadable — the corrupt line simply fails to parse as JSON below.
        text = paths.pulse_path().read_text(encoding="utf-8",
                                            errors="replace")
    except FileNotFoundError:
        return [], 0
    rows, skipped = [], 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not well_formed(e):
            skipped += 1
            continue
        rows.append(e)
    return rows, skipped


def _warn_unreadable(err: OSError) -> None:
    global _WARNED_UNREADABLE
    if _WARNED_UNREADABLE:
        return
    _WARNED_UNREADABLE = True
    output.warn("could not read the activity feed (%s) — activity is shown "
                "as empty; make %s readable"
                % (err.strerror or err, paths.tilde(paths.pulse_path())),
                stream=sys.stderr, wrap=True)


def events(n: int | None = None, action: str | None = None,
           subject: str | None = None) -> list[dict]:
    """Most-recent-first list of journal events; ``n=None`` means all of them.

    ``n`` must be >= 0: a negative would become a negative slice and silently
    return every event *but* the oldest ones, so it raises instead.

    The feed is advisory, the way `log` treats it: one that cannot be read
    (permissions, a directory in its place) warns once and reads as empty,
    and a row of the wrong shape is skipped (see :func:`well_formed`).
    """
    if n is not None and n < 0:
        raise ValueError("events(n=%d): n must be >= 0" % n)
    try:
        rows, _skipped = _read()
    except OSError as err:
        _warn_unreadable(err)
        return []
    out = [e for e in rows
           if (not action or e.get("action") == action)
           and (not subject or e.get("subject") == subject)]
    out.reverse()
    return out if n is None else out[:n]


def read_error() -> str | None:
    """Why the feed exists but cannot be read, or None when it can (or is
    absent). For `doctor`/`health`, which must report it, not crash on it."""
    try:
        _read()
    except OSError as err:
        return str(err.strerror or err)
    return None


def skipped_rows() -> int:
    """Lines every reader skips: torn, not JSON objects, or mistyped."""
    try:
        return _read()[1]
    except OSError:
        return 0


def activity_counts(evs: Sequence[dict]) -> dict[str, int]:
    """`boost stats` activity for one item's events.

    An upgrade and a reinstall each journal an "install" (tagged by `via`),
    so a raw count of install rows read one install and two reinstalls as
    three installs. `update` rows themselves name a tap or "all", never the
    item, so per item an update is an install row with ``via="update"``.
    """
    installs = [e for e in evs if e.get("action") == "install"]
    return {
        "install": sum(1 for e in installs if is_new_install(e)),
        "update": sum(1 for e in installs if e.get("via") == "update"),
        "reinstall": sum(1 for e in installs if e.get("via") == "reinstall"),
        "uninstall": sum(1 for e in evs if e.get("action") == "uninstall"),
    }


def pulse_empty_state(action: str | None, all_events: Sequence[dict]) -> str:
    """The empty-state line for ``boost pulse --action X`` matching nothing.

    ``all_events`` is the *unfiltered* journal, so a filter that matches
    nothing can be told apart from a genuinely empty journal — before this,
    both printed the identical "no activity yet" line, which asserts a false
    state ("nothing has happened on this machine") when 35 events exist for
    other actions. Pure function: the caller reads the journal once and
    hands the list in, so this needs no file I/O to test.
    """
    if not action or not all_events:
        return PULSE_EMPTY
    actions = sorted({e.get("action", "?") for e in all_events})
    return ("no events with action %r (%d event%s in the journal: %s)"
            % (action, len(all_events), "" if len(all_events) == 1 else "s",
               ", ".join(actions)))


def who_empty_state(skill: str | None, all_events: Sequence[dict],
                    is_installed: bool, known_subjects: Sequence[str] = ()) -> str:
    """The empty-state line for ``boost who SKILL`` with no matching events.

    Distinguishes three cases the old single message collapsed into one:
    a truly empty journal; a skill that IS installed but has no journal
    history (predates journaling, or was installed by a hand-edited lock);
    and a skill that is not installed at all, where a name one typo away
    from something that actually appears in the journal is worth a guess
    rather than a flat "no activity".
    """
    if not skill or not all_events:
        return WHO_EMPTY
    total = len(all_events)
    plural = "" if total == 1 else "s"
    if is_installed:
        return ("%r is installed but has no journal activity "
                "(%d event%s in the journal)" % (skill, total, plural))
    close = difflib.get_close_matches(skill, sorted(set(known_subjects)), n=1)
    if close:
        return "%r is not installed — did you mean %r?" % (skill, close[0])
    return ("%r is not installed (%d event%s in the journal, none for it)"
            % (skill, total, plural))


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
    """True when the pulse feed is absent or at most ROTATE_AT lines long.

    A feed that cannot be read cannot be judged, so it is not called overdue
    here — :func:`read_error` is the check that names it.
    """
    p = paths.pulse_path()
    try:
        return _line_count(p) <= ROTATE_AT
    except OSError:                         # absent, or unreadable
        return True


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
