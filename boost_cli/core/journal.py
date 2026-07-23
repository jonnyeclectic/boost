"""The pulse journal: append-only feed of skill-management events.

Powers `boost pulse`, `boost trending`, `boost stats`, and `boost who`.
"""
from __future__ import annotations

import json
from typing import List, Optional

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


def events(n: Optional[int] = None, action: Optional[str] = None,
           subject: Optional[str] = None) -> List[dict]:
    """Most-recent-first list of journal events."""
    p = paths.pulse_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
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
    return out[:n] if n else out


def rotation_healthy() -> bool:
    """True when the pulse feed is absent or at most ROTATE_AT lines long."""
    p = paths.pulse_path()
    if not p.exists():
        return True
    return sum(1 for _ in p.open()) <= ROTATE_AT


def _maybe_rotate() -> None:
    p = paths.pulse_path()
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) > ROTATE_AT:
        # Atomic swap: a bare write_text here races concurrent log() appends and
        # can truncate the feed mid-line if interrupted.
        util.atomic_write_text(p, "\n".join(lines[-ROTATE_KEEP:]) + "\n")
