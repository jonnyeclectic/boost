"""The v3 lock file: ~/.agents/skills/.skill-lock.json

Every write snapshots the previous version into ~/.boost/state/lock-history/
so `boost replay` can show history and roll back.

Skill entry schema (v3):
  version, tap, source_dir, commit, sha256,
  installed_at, updated_at, pinned, quarantined, agents[], tags[]
"""
from __future__ import annotations

import json
import shutil
from typing import List, Optional

from . import paths, util

SCHEMA_VERSION = 3
HISTORY_KEEP = 50


from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated, MutantDict
mutants_x__skeleton__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x__skeleton__mutmut)
def _skeleton() -> dict:
    return {"version": SCHEMA_VERSION, "updated": util.now_iso(), "skills": {}}


def x__skeleton__mutmut_orig() -> dict:
    return {"version": SCHEMA_VERSION, "updated": util.now_iso(), "skills": {}}


def x__skeleton__mutmut_1() -> dict:
    return {"XXversionXX": SCHEMA_VERSION, "updated": util.now_iso(), "skills": {}}


def x__skeleton__mutmut_2() -> dict:
    return {"VERSION": SCHEMA_VERSION, "updated": util.now_iso(), "skills": {}}


def x__skeleton__mutmut_3() -> dict:
    return {"version": SCHEMA_VERSION, "XXupdatedXX": util.now_iso(), "skills": {}}


def x__skeleton__mutmut_4() -> dict:
    return {"version": SCHEMA_VERSION, "UPDATED": util.now_iso(), "skills": {}}


def x__skeleton__mutmut_5() -> dict:
    return {"version": SCHEMA_VERSION, "updated": util.now_iso(), "XXskillsXX": {}}


def x__skeleton__mutmut_6() -> dict:
    return {"version": SCHEMA_VERSION, "updated": util.now_iso(), "SKILLS": {}}

mutants_x__skeleton__mutmut['_mutmut_orig'] = x__skeleton__mutmut_orig # type: ignore # mutmut generated
mutants_x__skeleton__mutmut['x__skeleton__mutmut_1'] = x__skeleton__mutmut_1 # type: ignore # mutmut generated
mutants_x__skeleton__mutmut['x__skeleton__mutmut_2'] = x__skeleton__mutmut_2 # type: ignore # mutmut generated
mutants_x__skeleton__mutmut['x__skeleton__mutmut_3'] = x__skeleton__mutmut_3 # type: ignore # mutmut generated
mutants_x__skeleton__mutmut['x__skeleton__mutmut_4'] = x__skeleton__mutmut_4 # type: ignore # mutmut generated
mutants_x__skeleton__mutmut['x__skeleton__mutmut_5'] = x__skeleton__mutmut_5 # type: ignore # mutmut generated
mutants_x__skeleton__mutmut['x__skeleton__mutmut_6'] = x__skeleton__mutmut_6 # type: ignore # mutmut generated
mutants_x_read__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_read__mutmut)
def read() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault("skills", {})
    return lock


def x_read__mutmut_orig() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault("skills", {})
    return lock


def x_read__mutmut_1() -> dict:
    p = None
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault("skills", {})
    return lock


def x_read__mutmut_2() -> dict:
    p = paths.lockfile_path()
    if p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault("skills", {})
    return lock


def x_read__mutmut_3() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = None
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault("skills", {})
    return lock


def x_read__mutmut_4() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(None)
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault("skills", {})
    return lock


def x_read__mutmut_5() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault(None, SCHEMA_VERSION)
    lock.setdefault("skills", {})
    return lock


def x_read__mutmut_6() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("version", None)
    lock.setdefault("skills", {})
    return lock


def x_read__mutmut_7() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault(SCHEMA_VERSION)
    lock.setdefault("skills", {})
    return lock


def x_read__mutmut_8() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("version", )
    lock.setdefault("skills", {})
    return lock


def x_read__mutmut_9() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("XXversionXX", SCHEMA_VERSION)
    lock.setdefault("skills", {})
    return lock


def x_read__mutmut_10() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("VERSION", SCHEMA_VERSION)
    lock.setdefault("skills", {})
    return lock


def x_read__mutmut_11() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault(None, {})
    return lock


def x_read__mutmut_12() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault("skills", None)
    return lock


def x_read__mutmut_13() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault({})
    return lock


def x_read__mutmut_14() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault("skills", )
    return lock


def x_read__mutmut_15() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault("XXskillsXX", {})
    return lock


def x_read__mutmut_16() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault("SKILLS", {})
    return lock

mutants_x_read__mutmut['_mutmut_orig'] = x_read__mutmut_orig # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_1'] = x_read__mutmut_1 # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_2'] = x_read__mutmut_2 # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_3'] = x_read__mutmut_3 # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_4'] = x_read__mutmut_4 # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_5'] = x_read__mutmut_5 # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_6'] = x_read__mutmut_6 # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_7'] = x_read__mutmut_7 # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_8'] = x_read__mutmut_8 # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_9'] = x_read__mutmut_9 # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_10'] = x_read__mutmut_10 # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_11'] = x_read__mutmut_11 # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_12'] = x_read__mutmut_12 # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_13'] = x_read__mutmut_13 # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_14'] = x_read__mutmut_14 # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_15'] = x_read__mutmut_15 # type: ignore # mutmut generated
mutants_x_read__mutmut['x_read__mutmut_16'] = x_read__mutmut_16 # type: ignore # mutmut generated
mutants_x_write__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_write__mutmut)
def write(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_orig(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_1(lock: dict) -> None:
    paths.ensure_dirs()
    p = None
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_2(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = None
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_3(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace(None, "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_4(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", None)
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_5(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_6(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", )
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_7(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(None, "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_8(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", None).replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_9(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace("").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_10(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", ).replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_11(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace("XX:XX", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_12(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "XXXX").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_13(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("XX-XX", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_14(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "XXXX")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_15(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = None
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_16(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() * ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_17(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" / stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_18(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("XXlock-%s.jsonXX" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_19(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("LOCK-%S.JSON" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_20(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = None
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_21(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 3
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_22(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = None
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_23(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() * ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_24(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" / (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_25(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("XXlock-%s-%d.jsonXX" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_26(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("LOCK-%S-%D.JSON" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_27(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n = 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_28(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n -= 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_29(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 2
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_30(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(None, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_31(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, None)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_32(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_33(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, )
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_34(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = None
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_35(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["XXversionXX"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_36(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["VERSION"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_37(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = None
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_38(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["XXupdatedXX"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_39(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["UPDATED"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_40(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(None)


def x_write__mutmut_41(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) - "\n")


def x_write__mutmut_42(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(None, indent=2, sort_keys=True) + "\n")


def x_write__mutmut_43(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=None, sort_keys=True) + "\n")


def x_write__mutmut_44(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=None) + "\n")


def x_write__mutmut_45(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(indent=2, sort_keys=True) + "\n")


def x_write__mutmut_46(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, sort_keys=True) + "\n")


def x_write__mutmut_47(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, ) + "\n")


def x_write__mutmut_48(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=3, sort_keys=True) + "\n")


def x_write__mutmut_49(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=False) + "\n")


def x_write__mutmut_50(lock: dict) -> None:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "XX\nXX")

mutants_x_write__mutmut['_mutmut_orig'] = x_write__mutmut_orig # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_1'] = x_write__mutmut_1 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_2'] = x_write__mutmut_2 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_3'] = x_write__mutmut_3 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_4'] = x_write__mutmut_4 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_5'] = x_write__mutmut_5 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_6'] = x_write__mutmut_6 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_7'] = x_write__mutmut_7 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_8'] = x_write__mutmut_8 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_9'] = x_write__mutmut_9 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_10'] = x_write__mutmut_10 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_11'] = x_write__mutmut_11 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_12'] = x_write__mutmut_12 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_13'] = x_write__mutmut_13 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_14'] = x_write__mutmut_14 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_15'] = x_write__mutmut_15 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_16'] = x_write__mutmut_16 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_17'] = x_write__mutmut_17 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_18'] = x_write__mutmut_18 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_19'] = x_write__mutmut_19 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_20'] = x_write__mutmut_20 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_21'] = x_write__mutmut_21 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_22'] = x_write__mutmut_22 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_23'] = x_write__mutmut_23 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_24'] = x_write__mutmut_24 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_25'] = x_write__mutmut_25 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_26'] = x_write__mutmut_26 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_27'] = x_write__mutmut_27 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_28'] = x_write__mutmut_28 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_29'] = x_write__mutmut_29 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_30'] = x_write__mutmut_30 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_31'] = x_write__mutmut_31 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_32'] = x_write__mutmut_32 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_33'] = x_write__mutmut_33 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_34'] = x_write__mutmut_34 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_35'] = x_write__mutmut_35 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_36'] = x_write__mutmut_36 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_37'] = x_write__mutmut_37 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_38'] = x_write__mutmut_38 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_39'] = x_write__mutmut_39 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_40'] = x_write__mutmut_40 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_41'] = x_write__mutmut_41 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_42'] = x_write__mutmut_42 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_43'] = x_write__mutmut_43 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_44'] = x_write__mutmut_44 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_45'] = x_write__mutmut_45 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_46'] = x_write__mutmut_46 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_47'] = x_write__mutmut_47 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_48'] = x_write__mutmut_48 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_49'] = x_write__mutmut_49 # type: ignore # mutmut generated
mutants_x_write__mutmut['x_write__mutmut_50'] = x_write__mutmut_50 # type: ignore # mutmut generated
mutants_x__history_files__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x__history_files__mutmut)
def _history_files() -> List:
    """History snapshots oldest→newest (mtime, then name — '-2' suffixed
    same-second snapshots would sort before their base name otherwise)."""
    return sorted(paths.lock_history_dir().glob("lock-*.json"),
                  key=lambda f: (f.stat().st_mtime, f.name))


def x__history_files__mutmut_orig() -> List:
    """History snapshots oldest→newest (mtime, then name — '-2' suffixed
    same-second snapshots would sort before their base name otherwise)."""
    return sorted(paths.lock_history_dir().glob("lock-*.json"),
                  key=lambda f: (f.stat().st_mtime, f.name))


def x__history_files__mutmut_1() -> List:
    """History snapshots oldest→newest (mtime, then name — '-2' suffixed
    same-second snapshots would sort before their base name otherwise)."""
    return sorted(None,
                  key=lambda f: (f.stat().st_mtime, f.name))


def x__history_files__mutmut_2() -> List:
    """History snapshots oldest→newest (mtime, then name — '-2' suffixed
    same-second snapshots would sort before their base name otherwise)."""
    return sorted(paths.lock_history_dir().glob("lock-*.json"),
                  key=None)


def x__history_files__mutmut_3() -> List:
    """History snapshots oldest→newest (mtime, then name — '-2' suffixed
    same-second snapshots would sort before their base name otherwise)."""
    return sorted(key=lambda f: (f.stat().st_mtime, f.name))


def x__history_files__mutmut_4() -> List:
    """History snapshots oldest→newest (mtime, then name — '-2' suffixed
    same-second snapshots would sort before their base name otherwise)."""
    return sorted(paths.lock_history_dir().glob("lock-*.json"),
                  )


def x__history_files__mutmut_5() -> List:
    """History snapshots oldest→newest (mtime, then name — '-2' suffixed
    same-second snapshots would sort before their base name otherwise)."""
    return sorted(paths.lock_history_dir().glob(None),
                  key=lambda f: (f.stat().st_mtime, f.name))


def x__history_files__mutmut_6() -> List:
    """History snapshots oldest→newest (mtime, then name — '-2' suffixed
    same-second snapshots would sort before their base name otherwise)."""
    return sorted(paths.lock_history_dir().glob("XXlock-*.jsonXX"),
                  key=lambda f: (f.stat().st_mtime, f.name))


def x__history_files__mutmut_7() -> List:
    """History snapshots oldest→newest (mtime, then name — '-2' suffixed
    same-second snapshots would sort before their base name otherwise)."""
    return sorted(paths.lock_history_dir().glob("LOCK-*.JSON"),
                  key=lambda f: (f.stat().st_mtime, f.name))


def x__history_files__mutmut_8() -> List:
    """History snapshots oldest→newest (mtime, then name — '-2' suffixed
    same-second snapshots would sort before their base name otherwise)."""
    return sorted(paths.lock_history_dir().glob("lock-*.json"),
                  key=lambda f: None)

mutants_x__history_files__mutmut['_mutmut_orig'] = x__history_files__mutmut_orig # type: ignore # mutmut generated
mutants_x__history_files__mutmut['x__history_files__mutmut_1'] = x__history_files__mutmut_1 # type: ignore # mutmut generated
mutants_x__history_files__mutmut['x__history_files__mutmut_2'] = x__history_files__mutmut_2 # type: ignore # mutmut generated
mutants_x__history_files__mutmut['x__history_files__mutmut_3'] = x__history_files__mutmut_3 # type: ignore # mutmut generated
mutants_x__history_files__mutmut['x__history_files__mutmut_4'] = x__history_files__mutmut_4 # type: ignore # mutmut generated
mutants_x__history_files__mutmut['x__history_files__mutmut_5'] = x__history_files__mutmut_5 # type: ignore # mutmut generated
mutants_x__history_files__mutmut['x__history_files__mutmut_6'] = x__history_files__mutmut_6 # type: ignore # mutmut generated
mutants_x__history_files__mutmut['x__history_files__mutmut_7'] = x__history_files__mutmut_7 # type: ignore # mutmut generated
mutants_x__history_files__mutmut['x__history_files__mutmut_8'] = x__history_files__mutmut_8 # type: ignore # mutmut generated
mutants_x__prune_history__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x__prune_history__mutmut)
def _prune_history() -> None:
    for old in _history_files()[:-HISTORY_KEEP]:
        old.unlink()


def x__prune_history__mutmut_orig() -> None:
    for old in _history_files()[:-HISTORY_KEEP]:
        old.unlink()


def x__prune_history__mutmut_1() -> None:
    for old in _history_files()[:+HISTORY_KEEP]:
        old.unlink()

mutants_x__prune_history__mutmut['_mutmut_orig'] = x__prune_history__mutmut_orig # type: ignore # mutmut generated
mutants_x__prune_history__mutmut['x__prune_history__mutmut_1'] = x__prune_history__mutmut_1 # type: ignore # mutmut generated
mutants_x_get_skill__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_get_skill__mutmut)
def get_skill(name: str) -> Optional[dict]:
    return read()["skills"].get(name)


def x_get_skill__mutmut_orig(name: str) -> Optional[dict]:
    return read()["skills"].get(name)


def x_get_skill__mutmut_1(name: str) -> Optional[dict]:
    return read()["skills"].get(None)


def x_get_skill__mutmut_2(name: str) -> Optional[dict]:
    return read()["XXskillsXX"].get(name)


def x_get_skill__mutmut_3(name: str) -> Optional[dict]:
    return read()["SKILLS"].get(name)

mutants_x_get_skill__mutmut['_mutmut_orig'] = x_get_skill__mutmut_orig # type: ignore # mutmut generated
mutants_x_get_skill__mutmut['x_get_skill__mutmut_1'] = x_get_skill__mutmut_1 # type: ignore # mutmut generated
mutants_x_get_skill__mutmut['x_get_skill__mutmut_2'] = x_get_skill__mutmut_2 # type: ignore # mutmut generated
mutants_x_get_skill__mutmut['x_get_skill__mutmut_3'] = x_get_skill__mutmut_3 # type: ignore # mutmut generated
mutants_x_set_skill__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_set_skill__mutmut)
def set_skill(name: str, entry: dict) -> None:
    lock = read()
    lock["skills"][name] = entry
    write(lock)


def x_set_skill__mutmut_orig(name: str, entry: dict) -> None:
    lock = read()
    lock["skills"][name] = entry
    write(lock)


def x_set_skill__mutmut_1(name: str, entry: dict) -> None:
    lock = None
    lock["skills"][name] = entry
    write(lock)


def x_set_skill__mutmut_2(name: str, entry: dict) -> None:
    lock = read()
    lock["skills"][name] = None
    write(lock)


def x_set_skill__mutmut_3(name: str, entry: dict) -> None:
    lock = read()
    lock["XXskillsXX"][name] = entry
    write(lock)


def x_set_skill__mutmut_4(name: str, entry: dict) -> None:
    lock = read()
    lock["SKILLS"][name] = entry
    write(lock)


def x_set_skill__mutmut_5(name: str, entry: dict) -> None:
    lock = read()
    lock["skills"][name] = entry
    write(None)

mutants_x_set_skill__mutmut['_mutmut_orig'] = x_set_skill__mutmut_orig # type: ignore # mutmut generated
mutants_x_set_skill__mutmut['x_set_skill__mutmut_1'] = x_set_skill__mutmut_1 # type: ignore # mutmut generated
mutants_x_set_skill__mutmut['x_set_skill__mutmut_2'] = x_set_skill__mutmut_2 # type: ignore # mutmut generated
mutants_x_set_skill__mutmut['x_set_skill__mutmut_3'] = x_set_skill__mutmut_3 # type: ignore # mutmut generated
mutants_x_set_skill__mutmut['x_set_skill__mutmut_4'] = x_set_skill__mutmut_4 # type: ignore # mutmut generated
mutants_x_set_skill__mutmut['x_set_skill__mutmut_5'] = x_set_skill__mutmut_5 # type: ignore # mutmut generated
mutants_x_remove_skill__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_remove_skill__mutmut)
def remove_skill(name: str) -> bool:
    lock = read()
    if name in lock["skills"]:
        del lock["skills"][name]
        write(lock)
        return True
    return False


def x_remove_skill__mutmut_orig(name: str) -> bool:
    lock = read()
    if name in lock["skills"]:
        del lock["skills"][name]
        write(lock)
        return True
    return False


def x_remove_skill__mutmut_1(name: str) -> bool:
    lock = None
    if name in lock["skills"]:
        del lock["skills"][name]
        write(lock)
        return True
    return False


def x_remove_skill__mutmut_2(name: str) -> bool:
    lock = read()
    if name not in lock["skills"]:
        del lock["skills"][name]
        write(lock)
        return True
    return False


def x_remove_skill__mutmut_3(name: str) -> bool:
    lock = read()
    if name in lock["XXskillsXX"]:
        del lock["skills"][name]
        write(lock)
        return True
    return False


def x_remove_skill__mutmut_4(name: str) -> bool:
    lock = read()
    if name in lock["SKILLS"]:
        del lock["skills"][name]
        write(lock)
        return True
    return False


def x_remove_skill__mutmut_5(name: str) -> bool:
    lock = read()
    if name in lock["skills"]:
        del lock["XXskillsXX"][name]
        write(lock)
        return True
    return False


def x_remove_skill__mutmut_6(name: str) -> bool:
    lock = read()
    if name in lock["skills"]:
        del lock["SKILLS"][name]
        write(lock)
        return True
    return False


def x_remove_skill__mutmut_7(name: str) -> bool:
    lock = read()
    if name in lock["skills"]:
        del lock["skills"][name]
        write(None)
        return True
    return False


def x_remove_skill__mutmut_8(name: str) -> bool:
    lock = read()
    if name in lock["skills"]:
        del lock["skills"][name]
        write(lock)
        return False
    return False


def x_remove_skill__mutmut_9(name: str) -> bool:
    lock = read()
    if name in lock["skills"]:
        del lock["skills"][name]
        write(lock)
        return True
    return True

mutants_x_remove_skill__mutmut['_mutmut_orig'] = x_remove_skill__mutmut_orig # type: ignore # mutmut generated
mutants_x_remove_skill__mutmut['x_remove_skill__mutmut_1'] = x_remove_skill__mutmut_1 # type: ignore # mutmut generated
mutants_x_remove_skill__mutmut['x_remove_skill__mutmut_2'] = x_remove_skill__mutmut_2 # type: ignore # mutmut generated
mutants_x_remove_skill__mutmut['x_remove_skill__mutmut_3'] = x_remove_skill__mutmut_3 # type: ignore # mutmut generated
mutants_x_remove_skill__mutmut['x_remove_skill__mutmut_4'] = x_remove_skill__mutmut_4 # type: ignore # mutmut generated
mutants_x_remove_skill__mutmut['x_remove_skill__mutmut_5'] = x_remove_skill__mutmut_5 # type: ignore # mutmut generated
mutants_x_remove_skill__mutmut['x_remove_skill__mutmut_6'] = x_remove_skill__mutmut_6 # type: ignore # mutmut generated
mutants_x_remove_skill__mutmut['x_remove_skill__mutmut_7'] = x_remove_skill__mutmut_7 # type: ignore # mutmut generated
mutants_x_remove_skill__mutmut['x_remove_skill__mutmut_8'] = x_remove_skill__mutmut_8 # type: ignore # mutmut generated
mutants_x_remove_skill__mutmut['x_remove_skill__mutmut_9'] = x_remove_skill__mutmut_9 # type: ignore # mutmut generated
mutants_x_installed__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_installed__mutmut)
def installed() -> dict:
    return read()["skills"]


def x_installed__mutmut_orig() -> dict:
    return read()["skills"]


def x_installed__mutmut_1() -> dict:
    return read()["XXskillsXX"]


def x_installed__mutmut_2() -> dict:
    return read()["SKILLS"]

mutants_x_installed__mutmut['_mutmut_orig'] = x_installed__mutmut_orig # type: ignore # mutmut generated
mutants_x_installed__mutmut['x_installed__mutmut_1'] = x_installed__mutmut_1 # type: ignore # mutmut generated
mutants_x_installed__mutmut['x_installed__mutmut_2'] = x_installed__mutmut_2 # type: ignore # mutmut generated
mutants_x_history_list__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_history_list__mutmut)
def history_list() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_orig() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_1() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = None
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_2() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = None
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_3() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(None)
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_4() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            break
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_5() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append(None)
    return out


def x_history_list__mutmut_6() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "XXidXX": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_7() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "ID": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_8() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace(None, ""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_9() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", None),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_10() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace(""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_11() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_12() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("XXlock-XX", ""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_13() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("LOCK-", ""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_14() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", "XXXX"),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_15() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "XXpathXX": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_16() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "PATH": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_17() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(None),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_18() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "XXupdatedXX": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_19() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "UPDATED": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_20() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get(None, "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_21() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("updated", None),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_22() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_23() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("updated", ),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_24() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("XXupdatedXX", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_25() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("UPDATED", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_26() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("updated", "XX?XX"),
            "count": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_27() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "XXcountXX": len(data.get("skills", {})),
        })
    return out


def x_history_list__mutmut_28() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "COUNT": len(data.get("skills", {})),
        })
    return out

mutants_x_history_list__mutmut['_mutmut_orig'] = x_history_list__mutmut_orig # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_1'] = x_history_list__mutmut_1 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_2'] = x_history_list__mutmut_2 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_3'] = x_history_list__mutmut_3 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_4'] = x_history_list__mutmut_4 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_5'] = x_history_list__mutmut_5 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_6'] = x_history_list__mutmut_6 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_7'] = x_history_list__mutmut_7 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_8'] = x_history_list__mutmut_8 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_9'] = x_history_list__mutmut_9 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_10'] = x_history_list__mutmut_10 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_11'] = x_history_list__mutmut_11 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_12'] = x_history_list__mutmut_12 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_13'] = x_history_list__mutmut_13 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_14'] = x_history_list__mutmut_14 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_15'] = x_history_list__mutmut_15 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_16'] = x_history_list__mutmut_16 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_17'] = x_history_list__mutmut_17 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_18'] = x_history_list__mutmut_18 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_19'] = x_history_list__mutmut_19 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_20'] = x_history_list__mutmut_20 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_21'] = x_history_list__mutmut_21 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_22'] = x_history_list__mutmut_22 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_23'] = x_history_list__mutmut_23 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_24'] = x_history_list__mutmut_24 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_25'] = x_history_list__mutmut_25 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_26'] = x_history_list__mutmut_26 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_27'] = x_history_list__mutmut_27 # type: ignore # mutmut generated
mutants_x_history_list__mutmut['x_history_list__mutmut_28'] = x_history_list__mutmut_28 # type: ignore # mutmut generated
mutants_x_history_read__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_history_read__mutmut)
def history_read(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" % hist_id,
                        hint="list entries with `boost replay`")
    return json.loads(p.read_text())


def x_history_read__mutmut_orig(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" % hist_id,
                        hint="list entries with `boost replay`")
    return json.loads(p.read_text())


def x_history_read__mutmut_1(hist_id: str) -> dict:
    p = None
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" % hist_id,
                        hint="list entries with `boost replay`")
    return json.loads(p.read_text())


def x_history_read__mutmut_2(hist_id: str) -> dict:
    p = paths.lock_history_dir() * ("lock-%s.json" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" % hist_id,
                        hint="list entries with `boost replay`")
    return json.loads(p.read_text())


def x_history_read__mutmut_3(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("lock-%s.json" / hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" % hist_id,
                        hint="list entries with `boost replay`")
    return json.loads(p.read_text())


def x_history_read__mutmut_4(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("XXlock-%s.jsonXX" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" % hist_id,
                        hint="list entries with `boost replay`")
    return json.loads(p.read_text())


def x_history_read__mutmut_5(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("LOCK-%S.JSON" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" % hist_id,
                        hint="list entries with `boost replay`")
    return json.loads(p.read_text())


def x_history_read__mutmut_6(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" % hist_id,
                        hint="list entries with `boost replay`")
    return json.loads(p.read_text())


def x_history_read__mutmut_7(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError(None,
                        hint="list entries with `boost replay`")
    return json.loads(p.read_text())


def x_history_read__mutmut_8(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" % hist_id,
                        hint=None)
    return json.loads(p.read_text())


def x_history_read__mutmut_9(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError(hint="list entries with `boost replay`")
    return json.loads(p.read_text())


def x_history_read__mutmut_10(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" % hist_id,
                        )
    return json.loads(p.read_text())


def x_history_read__mutmut_11(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" / hist_id,
                        hint="list entries with `boost replay`")
    return json.loads(p.read_text())


def x_history_read__mutmut_12(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("XXno lock history entry %sXX" % hist_id,
                        hint="list entries with `boost replay`")
    return json.loads(p.read_text())


def x_history_read__mutmut_13(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("NO LOCK HISTORY ENTRY %S" % hist_id,
                        hint="list entries with `boost replay`")
    return json.loads(p.read_text())


def x_history_read__mutmut_14(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" % hist_id,
                        hint="XXlist entries with `boost replay`XX")
    return json.loads(p.read_text())


def x_history_read__mutmut_15(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" % hist_id,
                        hint="LIST ENTRIES WITH `BOOST REPLAY`")
    return json.loads(p.read_text())


def x_history_read__mutmut_16(hist_id: str) -> dict:
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" % hist_id,
                        hint="list entries with `boost replay`")
    return json.loads(None)

mutants_x_history_read__mutmut['_mutmut_orig'] = x_history_read__mutmut_orig # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_1'] = x_history_read__mutmut_1 # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_2'] = x_history_read__mutmut_2 # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_3'] = x_history_read__mutmut_3 # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_4'] = x_history_read__mutmut_4 # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_5'] = x_history_read__mutmut_5 # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_6'] = x_history_read__mutmut_6 # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_7'] = x_history_read__mutmut_7 # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_8'] = x_history_read__mutmut_8 # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_9'] = x_history_read__mutmut_9 # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_10'] = x_history_read__mutmut_10 # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_11'] = x_history_read__mutmut_11 # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_12'] = x_history_read__mutmut_12 # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_13'] = x_history_read__mutmut_13 # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_14'] = x_history_read__mutmut_14 # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_15'] = x_history_read__mutmut_15 # type: ignore # mutmut generated
mutants_x_history_read__mutmut['x_history_read__mutmut_16'] = x_history_read__mutmut_16 # type: ignore # mutmut generated
