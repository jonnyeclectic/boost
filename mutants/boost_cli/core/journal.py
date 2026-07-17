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


from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated, MutantDict
mutants_x_log__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_log__mutmut)
def log(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_orig(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_1(action: str, subject: str = "XXXX", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_2(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = None
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_3(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"XXtsXX": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_4(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"TS": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_5(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "XXuserXX": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_6(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "USER": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_7(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "XXactionXX": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_8(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "ACTION": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_9(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "XXsubjectXX": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_10(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "SUBJECT": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_11(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update(None)
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_12(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_13(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = None
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_14(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open(None) as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_15(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("XXaXX") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_16(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("A") as f:
        f.write(json.dumps(event) + "\n")
    _maybe_rotate()


def x_log__mutmut_17(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(None)
    _maybe_rotate()


def x_log__mutmut_18(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) - "\n")
    _maybe_rotate()


def x_log__mutmut_19(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(None) + "\n")
    _maybe_rotate()


def x_log__mutmut_20(action: str, subject: str = "", **fields) -> None:
    paths.ensure_dirs()
    event = {"ts": util.now_iso(), "user": _user(), "action": action,
             "subject": subject}
    event.update({k: v for k, v in fields.items() if v is not None})
    p = paths.pulse_path()
    with p.open("a") as f:
        f.write(json.dumps(event) + "XX\nXX")
    _maybe_rotate()

mutants_x_log__mutmut['_mutmut_orig'] = x_log__mutmut_orig # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_1'] = x_log__mutmut_1 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_2'] = x_log__mutmut_2 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_3'] = x_log__mutmut_3 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_4'] = x_log__mutmut_4 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_5'] = x_log__mutmut_5 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_6'] = x_log__mutmut_6 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_7'] = x_log__mutmut_7 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_8'] = x_log__mutmut_8 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_9'] = x_log__mutmut_9 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_10'] = x_log__mutmut_10 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_11'] = x_log__mutmut_11 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_12'] = x_log__mutmut_12 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_13'] = x_log__mutmut_13 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_14'] = x_log__mutmut_14 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_15'] = x_log__mutmut_15 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_16'] = x_log__mutmut_16 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_17'] = x_log__mutmut_17 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_18'] = x_log__mutmut_18 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_19'] = x_log__mutmut_19 # type: ignore # mutmut generated
mutants_x_log__mutmut['x_log__mutmut_20'] = x_log__mutmut_20 # type: ignore # mutmut generated
mutants_x__user__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x__user__mutmut)
def _user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def x__user__mutmut_orig() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def x__user__mutmut_1() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "XXunknownXX"


def x__user__mutmut_2() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "UNKNOWN"

mutants_x__user__mutmut['_mutmut_orig'] = x__user__mutmut_orig # type: ignore # mutmut generated
mutants_x__user__mutmut['x__user__mutmut_1'] = x__user__mutmut_1 # type: ignore # mutmut generated
mutants_x__user__mutmut['x__user__mutmut_2'] = x__user__mutmut_2 # type: ignore # mutmut generated
mutants_x_events__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_events__mutmut)
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


def x_events__mutmut_orig(n: Optional[int] = None, action: Optional[str] = None,
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


def x_events__mutmut_1(n: Optional[int] = None, action: Optional[str] = None,
           subject: Optional[str] = None) -> List[dict]:
    """Most-recent-first list of journal events."""
    p = None
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


def x_events__mutmut_2(n: Optional[int] = None, action: Optional[str] = None,
           subject: Optional[str] = None) -> List[dict]:
    """Most-recent-first list of journal events."""
    p = paths.pulse_path()
    if p.exists():
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


def x_events__mutmut_3(n: Optional[int] = None, action: Optional[str] = None,
           subject: Optional[str] = None) -> List[dict]:
    """Most-recent-first list of journal events."""
    p = paths.pulse_path()
    if not p.exists():
        return []
    out = None
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


def x_events__mutmut_4(n: Optional[int] = None, action: Optional[str] = None,
           subject: Optional[str] = None) -> List[dict]:
    """Most-recent-first list of journal events."""
    p = paths.pulse_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        try:
            e = None
        except json.JSONDecodeError:
            continue
        if action and e.get("action") != action:
            continue
        if subject and e.get("subject") != subject:
            continue
        out.append(e)
    out.reverse()
    return out[:n] if n else out


def x_events__mutmut_5(n: Optional[int] = None, action: Optional[str] = None,
           subject: Optional[str] = None) -> List[dict]:
    """Most-recent-first list of journal events."""
    p = paths.pulse_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        try:
            e = json.loads(None)
        except json.JSONDecodeError:
            continue
        if action and e.get("action") != action:
            continue
        if subject and e.get("subject") != subject:
            continue
        out.append(e)
    out.reverse()
    return out[:n] if n else out


def x_events__mutmut_6(n: Optional[int] = None, action: Optional[str] = None,
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
            break
        if action and e.get("action") != action:
            continue
        if subject and e.get("subject") != subject:
            continue
        out.append(e)
    out.reverse()
    return out[:n] if n else out


def x_events__mutmut_7(n: Optional[int] = None, action: Optional[str] = None,
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
        if action or e.get("action") != action:
            continue
        if subject and e.get("subject") != subject:
            continue
        out.append(e)
    out.reverse()
    return out[:n] if n else out


def x_events__mutmut_8(n: Optional[int] = None, action: Optional[str] = None,
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
        if action and e.get(None) != action:
            continue
        if subject and e.get("subject") != subject:
            continue
        out.append(e)
    out.reverse()
    return out[:n] if n else out


def x_events__mutmut_9(n: Optional[int] = None, action: Optional[str] = None,
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
        if action and e.get("XXactionXX") != action:
            continue
        if subject and e.get("subject") != subject:
            continue
        out.append(e)
    out.reverse()
    return out[:n] if n else out


def x_events__mutmut_10(n: Optional[int] = None, action: Optional[str] = None,
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
        if action and e.get("ACTION") != action:
            continue
        if subject and e.get("subject") != subject:
            continue
        out.append(e)
    out.reverse()
    return out[:n] if n else out


def x_events__mutmut_11(n: Optional[int] = None, action: Optional[str] = None,
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
        if action and e.get("action") == action:
            continue
        if subject and e.get("subject") != subject:
            continue
        out.append(e)
    out.reverse()
    return out[:n] if n else out


def x_events__mutmut_12(n: Optional[int] = None, action: Optional[str] = None,
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
            break
        if subject and e.get("subject") != subject:
            continue
        out.append(e)
    out.reverse()
    return out[:n] if n else out


def x_events__mutmut_13(n: Optional[int] = None, action: Optional[str] = None,
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
        if subject or e.get("subject") != subject:
            continue
        out.append(e)
    out.reverse()
    return out[:n] if n else out


def x_events__mutmut_14(n: Optional[int] = None, action: Optional[str] = None,
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
        if subject and e.get(None) != subject:
            continue
        out.append(e)
    out.reverse()
    return out[:n] if n else out


def x_events__mutmut_15(n: Optional[int] = None, action: Optional[str] = None,
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
        if subject and e.get("XXsubjectXX") != subject:
            continue
        out.append(e)
    out.reverse()
    return out[:n] if n else out


def x_events__mutmut_16(n: Optional[int] = None, action: Optional[str] = None,
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
        if subject and e.get("SUBJECT") != subject:
            continue
        out.append(e)
    out.reverse()
    return out[:n] if n else out


def x_events__mutmut_17(n: Optional[int] = None, action: Optional[str] = None,
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
        if subject and e.get("subject") == subject:
            continue
        out.append(e)
    out.reverse()
    return out[:n] if n else out


def x_events__mutmut_18(n: Optional[int] = None, action: Optional[str] = None,
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
            break
        out.append(e)
    out.reverse()
    return out[:n] if n else out


def x_events__mutmut_19(n: Optional[int] = None, action: Optional[str] = None,
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
        out.append(None)
    out.reverse()
    return out[:n] if n else out

mutants_x_events__mutmut['_mutmut_orig'] = x_events__mutmut_orig # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_1'] = x_events__mutmut_1 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_2'] = x_events__mutmut_2 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_3'] = x_events__mutmut_3 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_4'] = x_events__mutmut_4 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_5'] = x_events__mutmut_5 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_6'] = x_events__mutmut_6 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_7'] = x_events__mutmut_7 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_8'] = x_events__mutmut_8 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_9'] = x_events__mutmut_9 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_10'] = x_events__mutmut_10 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_11'] = x_events__mutmut_11 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_12'] = x_events__mutmut_12 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_13'] = x_events__mutmut_13 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_14'] = x_events__mutmut_14 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_15'] = x_events__mutmut_15 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_16'] = x_events__mutmut_16 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_17'] = x_events__mutmut_17 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_18'] = x_events__mutmut_18 # type: ignore # mutmut generated
mutants_x_events__mutmut['x_events__mutmut_19'] = x_events__mutmut_19 # type: ignore # mutmut generated
mutants_x_rotation_healthy__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_rotation_healthy__mutmut)
def rotation_healthy() -> bool:
    p = paths.pulse_path()
    if not p.exists():
        return True
    return sum(1 for _ in p.open()) <= ROTATE_AT


def x_rotation_healthy__mutmut_orig() -> bool:
    p = paths.pulse_path()
    if not p.exists():
        return True
    return sum(1 for _ in p.open()) <= ROTATE_AT


def x_rotation_healthy__mutmut_1() -> bool:
    p = None
    if not p.exists():
        return True
    return sum(1 for _ in p.open()) <= ROTATE_AT


def x_rotation_healthy__mutmut_2() -> bool:
    p = paths.pulse_path()
    if p.exists():
        return True
    return sum(1 for _ in p.open()) <= ROTATE_AT


def x_rotation_healthy__mutmut_3() -> bool:
    p = paths.pulse_path()
    if not p.exists():
        return False
    return sum(1 for _ in p.open()) <= ROTATE_AT


def x_rotation_healthy__mutmut_4() -> bool:
    p = paths.pulse_path()
    if not p.exists():
        return True
    return sum(None) <= ROTATE_AT


def x_rotation_healthy__mutmut_5() -> bool:
    p = paths.pulse_path()
    if not p.exists():
        return True
    return sum(2 for _ in p.open()) <= ROTATE_AT


def x_rotation_healthy__mutmut_6() -> bool:
    p = paths.pulse_path()
    if not p.exists():
        return True
    return sum(1 for _ in p.open()) < ROTATE_AT

mutants_x_rotation_healthy__mutmut['_mutmut_orig'] = x_rotation_healthy__mutmut_orig # type: ignore # mutmut generated
mutants_x_rotation_healthy__mutmut['x_rotation_healthy__mutmut_1'] = x_rotation_healthy__mutmut_1 # type: ignore # mutmut generated
mutants_x_rotation_healthy__mutmut['x_rotation_healthy__mutmut_2'] = x_rotation_healthy__mutmut_2 # type: ignore # mutmut generated
mutants_x_rotation_healthy__mutmut['x_rotation_healthy__mutmut_3'] = x_rotation_healthy__mutmut_3 # type: ignore # mutmut generated
mutants_x_rotation_healthy__mutmut['x_rotation_healthy__mutmut_4'] = x_rotation_healthy__mutmut_4 # type: ignore # mutmut generated
mutants_x_rotation_healthy__mutmut['x_rotation_healthy__mutmut_5'] = x_rotation_healthy__mutmut_5 # type: ignore # mutmut generated
mutants_x_rotation_healthy__mutmut['x_rotation_healthy__mutmut_6'] = x_rotation_healthy__mutmut_6 # type: ignore # mutmut generated
mutants_x__maybe_rotate__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x__maybe_rotate__mutmut)
def _maybe_rotate() -> None:
    p = paths.pulse_path()
    try:
        lines = p.read_text().splitlines()
    except OSError:
        return
    if len(lines) > ROTATE_AT:
        p.write_text("\n".join(lines[-ROTATE_KEEP:]) + "\n")


def x__maybe_rotate__mutmut_orig() -> None:
    p = paths.pulse_path()
    try:
        lines = p.read_text().splitlines()
    except OSError:
        return
    if len(lines) > ROTATE_AT:
        p.write_text("\n".join(lines[-ROTATE_KEEP:]) + "\n")


def x__maybe_rotate__mutmut_1() -> None:
    p = None
    try:
        lines = p.read_text().splitlines()
    except OSError:
        return
    if len(lines) > ROTATE_AT:
        p.write_text("\n".join(lines[-ROTATE_KEEP:]) + "\n")


def x__maybe_rotate__mutmut_2() -> None:
    p = paths.pulse_path()
    try:
        lines = None
    except OSError:
        return
    if len(lines) > ROTATE_AT:
        p.write_text("\n".join(lines[-ROTATE_KEEP:]) + "\n")


def x__maybe_rotate__mutmut_3() -> None:
    p = paths.pulse_path()
    try:
        lines = p.read_text().splitlines()
    except OSError:
        return
    if len(lines) >= ROTATE_AT:
        p.write_text("\n".join(lines[-ROTATE_KEEP:]) + "\n")


def x__maybe_rotate__mutmut_4() -> None:
    p = paths.pulse_path()
    try:
        lines = p.read_text().splitlines()
    except OSError:
        return
    if len(lines) > ROTATE_AT:
        p.write_text(None)


def x__maybe_rotate__mutmut_5() -> None:
    p = paths.pulse_path()
    try:
        lines = p.read_text().splitlines()
    except OSError:
        return
    if len(lines) > ROTATE_AT:
        p.write_text("\n".join(lines[-ROTATE_KEEP:]) - "\n")


def x__maybe_rotate__mutmut_6() -> None:
    p = paths.pulse_path()
    try:
        lines = p.read_text().splitlines()
    except OSError:
        return
    if len(lines) > ROTATE_AT:
        p.write_text("\n".join(None) + "\n")


def x__maybe_rotate__mutmut_7() -> None:
    p = paths.pulse_path()
    try:
        lines = p.read_text().splitlines()
    except OSError:
        return
    if len(lines) > ROTATE_AT:
        p.write_text("XX\nXX".join(lines[-ROTATE_KEEP:]) + "\n")


def x__maybe_rotate__mutmut_8() -> None:
    p = paths.pulse_path()
    try:
        lines = p.read_text().splitlines()
    except OSError:
        return
    if len(lines) > ROTATE_AT:
        p.write_text("\n".join(lines[+ROTATE_KEEP:]) + "\n")


def x__maybe_rotate__mutmut_9() -> None:
    p = paths.pulse_path()
    try:
        lines = p.read_text().splitlines()
    except OSError:
        return
    if len(lines) > ROTATE_AT:
        p.write_text("\n".join(lines[-ROTATE_KEEP:]) + "XX\nXX")

mutants_x__maybe_rotate__mutmut['_mutmut_orig'] = x__maybe_rotate__mutmut_orig # type: ignore # mutmut generated
mutants_x__maybe_rotate__mutmut['x__maybe_rotate__mutmut_1'] = x__maybe_rotate__mutmut_1 # type: ignore # mutmut generated
mutants_x__maybe_rotate__mutmut['x__maybe_rotate__mutmut_2'] = x__maybe_rotate__mutmut_2 # type: ignore # mutmut generated
mutants_x__maybe_rotate__mutmut['x__maybe_rotate__mutmut_3'] = x__maybe_rotate__mutmut_3 # type: ignore # mutmut generated
mutants_x__maybe_rotate__mutmut['x__maybe_rotate__mutmut_4'] = x__maybe_rotate__mutmut_4 # type: ignore # mutmut generated
mutants_x__maybe_rotate__mutmut['x__maybe_rotate__mutmut_5'] = x__maybe_rotate__mutmut_5 # type: ignore # mutmut generated
mutants_x__maybe_rotate__mutmut['x__maybe_rotate__mutmut_6'] = x__maybe_rotate__mutmut_6 # type: ignore # mutmut generated
mutants_x__maybe_rotate__mutmut['x__maybe_rotate__mutmut_7'] = x__maybe_rotate__mutmut_7 # type: ignore # mutmut generated
mutants_x__maybe_rotate__mutmut['x__maybe_rotate__mutmut_8'] = x__maybe_rotate__mutmut_8 # type: ignore # mutmut generated
mutants_x__maybe_rotate__mutmut['x__maybe_rotate__mutmut_9'] = x__maybe_rotate__mutmut_9 # type: ignore # mutmut generated
