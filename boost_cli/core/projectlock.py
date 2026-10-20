# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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
import sys
from pathlib import Path

from ..errors import BoostError
from . import jsonstate, output, util

SCHEMA_VERSION = 1
LOCK_DIRNAME = ".boost"
LOCK_FILENAME = "skill-lock.json"
LOCK_REL = LOCK_DIRNAME + "/" + LOCK_FILENAME

# Lock paths already warned about, so one command that reads a corrupt lock
# several times says so once — per repo, since one process can visit several.
_WARNED_CORRUPT: set[str] = set()
#: How a corrupt project lock is recovered: it is committed, so git has it.
RECOVER_HINT = ("it is tracked by the repo, so `git checkout -- %s` restores "
                "the committed copy; or repair the JSON by hand")


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

    A missing file is simply an empty project. A corrupt one reads as the
    skeleton too, with a warning, and is left exactly where it is: an
    unparseable file is not an empty one, so :func:`write` refuses to replace
    it (:func:`refuse_corrupt`) rather than let the next install record that
    one skill and drop every other.
    """
    p = lock_path(base)
    if not p.is_file():
        return _skeleton()
    lock, err = jsonstate.read_object(p)
    if lock is None:
        _warn_corrupt(p, err or str(p))
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    skills = lock.get("skills")
    lock["skills"] = skills if isinstance(skills, dict) else {}
    return lock


def _warn_corrupt(p: Path, err: str) -> None:
    """Say once, on stderr, that this project lock reads as empty."""
    if str(p) in _WARNED_CORRUPT:
        return
    _WARNED_CORRUPT.add(str(p))
    output.warn("%s — boost sees no project skills here and will not write "
                "over it; %s" % (err, RECOVER_HINT % LOCK_REL),
                stream=sys.stderr, wrap=True)


def check(base) -> str | None:
    """Why the project lock cannot be read, or None when it reads or is absent.

    Never prints: `boost doctor` reports it.
    """
    return jsonstate.read_object(lock_path(base))[1]


def refuse_corrupt(base) -> None:
    """Raise while the project lock on disk is corrupt, so nothing writes over it.

    :func:`read` hands its callers an empty skeleton, so a write would replace
    every record with whatever one change added — `install --scope project`
    did exactly that, and left the other skills' copies on disk unrecorded.
    """
    err = check(base)
    if err is None:
        return
    raise BoostError("project lock is corrupt — boost will not write over it "
                     "(%s)" % err,
                     hint=RECOVER_HINT % LOCK_REL, wrap=True)


def write(base, lock: dict) -> None:
    """Stamp version/updated onto ``lock`` and write it atomically.

    Refuses over a corrupt lock (:func:`refuse_corrupt`).
    """
    refuse_corrupt(base)
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

    Refuses over a corrupt lock even though it reads as holding nothing:
    "not present" would be a false answer about a record boost cannot read.
    """
    refuse_corrupt(base)
    lock = read(base)
    if name in lock["skills"]:
        del lock["skills"][name]
        write(base, lock)
        return True
    return False
