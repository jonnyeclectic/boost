"""The per-project lock file: ``<repo>/.boost/skill-lock.json``.

Project-scoped skills deliberately do **not** share the user lock. Two reasons,
one practical and one about ownership:

* Practical — roughly forty call sites across the command layer read the user
  lock and then look the skill up at ``~/.agents/skills/<name>``. A project skill
  does not live there, so putting it in that lock would hand every one of those
  a path that does not exist.
* Ownership — this file is meant to be **committed**. It is the record a teammate
  gets from ``git clone``, which is the entire point of installing into the repo.

So it is a small, self-contained document with the same shape as the user lock's
``skills`` section and none of its machinery. In particular there is no history
directory: the user lock snapshots itself on every write because nothing else
would remember, whereas this file is versioned by the repo it lives in — git is
its history, and duplicating that inside ``.boost/`` would just be litter in
someone's diff.
"""
from __future__ import annotations

import json
from contextlib import suppress
from pathlib import Path

from . import util

SCHEMA_VERSION = 1
LOCK_DIRNAME = ".boost"
LOCK_FILENAME = "skill-lock.json"


def lock_path(base) -> Path:
    """Path of the project lock for the repo at ``base``."""
    return Path(base) / LOCK_DIRNAME / LOCK_FILENAME


def exists(base) -> bool:
    """True when ``base`` already carries a project lock file."""
    return lock_path(base).is_file()


def _skeleton() -> dict:
    return {"version": SCHEMA_VERSION, "updated": util.now_iso(), "skills": {}}


def read(base) -> dict:
    """Load the project lock, guaranteeing a ``skills`` key.

    A missing file is simply an empty project. A corrupt one is preserved beside
    itself as ``skill-lock.json.corrupt`` before falling back to the skeleton,
    for the same reason the user lock does it: an unparseable file is not an
    empty one, and the next write would otherwise erase the only record of what
    the project had installed.
    """
    p = lock_path(base)
    if not p.is_file():
        return _skeleton()
    try:
        lock = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _preserve_corrupt(p)
        return _skeleton()
    if not isinstance(lock, dict):
        _preserve_corrupt(p)
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    skills = lock.get("skills")
    lock["skills"] = skills if isinstance(skills, dict) else {}
    return lock


def _preserve_corrupt(p: Path) -> None:
    """Copy an unparseable lock aside as ``.corrupt``; never raise."""
    with suppress(OSError):
        import shutil
        shutil.copy(p, p.with_name(p.name + ".corrupt"))


def write(base, lock: dict) -> None:
    """Stamp version/updated onto ``lock`` and write it atomically."""
    p = lock_path(base)
    p.parent.mkdir(parents=True, exist_ok=True)
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    util.atomic_write_text(p, json.dumps(lock, indent=2, sort_keys=True) + "\n")


def installed(base) -> dict:
    """Return the project's ``{name: entry}`` mapping of installed skills."""
    return read(base)["skills"]


def get_skill(base, name: str) -> dict | None:
    """Return the project lock entry for ``name``, or None."""
    return read(base)["skills"].get(name)


def set_skill(base, name: str, entry: dict) -> None:
    """Insert or replace the project lock entry for ``name`` and persist."""
    lock = read(base)
    lock["skills"][name] = entry
    write(base, lock)


def remove_skill(base, name: str) -> bool:
    """Drop ``name`` from the project lock; True if it was present.

    When the last skill goes the file is left in place (empty) rather than
    deleted — it is a tracked file in someone's repo, and removing it would show
    up as a spurious deletion in their next ``git status``.
    """
    lock = read(base)
    if name in lock["skills"]:
        del lock["skills"][name]
        write(base, lock)
        return True
    return False
