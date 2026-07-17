"""The pulse journal: append-only feed of skill-management events.

Powers `boost pulse`, `boost trending`, `boost stats`, and `boost who`.
"""
from __future__ import annotations

import getpass
import json
from typing import List, Optional

from . import paths, util

ROTATE_AT = 5000
ROTATE_KEEP = 2500


def log(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def _user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def events(n: Optional[int] = None, action: Optional[str] = None,
           subject: Optional[str] = None) -> List[dict]:
    """Most-recent-first list of journal events."""
    p = paths.pulse_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
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
    p = paths.pulse_path()
    if not p.exists():
        return True
    return sum(1 for _ in p.open()) <= ROTATE_AT


def _maybe_rotate() -> None:
    p = paths.pulse_path()
    try:
        lines = p.read_text().splitlines()
    except OSError:
        return
    if len(lines) > ROTATE_AT:
        p.write_text("\n".join(lines[-ROTATE_KEEP:]) + "\n")
