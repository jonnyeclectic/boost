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
from collections.abc import Callable
from pathlib import Path

from ..errors import BoostError
from . import gitutil, jsonstate, output, util

SCHEMA_VERSION = 1
LOCK_DIRNAME = ".boost"
LOCK_FILENAME = "skill-lock.json"
LOCK_REL = LOCK_DIRNAME + "/" + LOCK_FILENAME

# Lock paths already warned about, so one command that reads a corrupt lock
# several times says so once — per repo, since one process can visit several.
_WARNED_CORRUPT: set[str] = set()


def recover_hint(base) -> str:
    """How the corrupt project lock of the repo at ``base`` is recovered.

    A checkout is offered only when git tracks the file, and is run with
    ``-C <base>``: a relative ``git checkout -- .boost/skill-lock.json``
    failed from any subdirectory of the repo (doctor and install resolve the
    root from there), and in a repo that never committed the file it failed
    everywhere, under a hint saying the repo tracked it.
    """
    if gitutil.tracks(Path(base), LOCK_REL):
        return ("it is tracked by the repo, so `git -C %s checkout -- %s` "
                "restores the committed copy; or repair the JSON by hand"
                % (util.shell_arg(str(base)), LOCK_REL))
    return ("git does not track it, so there is no committed copy to restore "
            "— repair the JSON by hand")


def lock_path(base) -> Path:
    """Path of the project lock for the repo at ``base``."""
    return Path(base) / LOCK_DIRNAME / LOCK_FILENAME


def guard_path(base) -> Path:
    """The sidecar :func:`mutate` locks for the repo at ``base``.

    ``util.file_lock`` never deletes its sidecar, and the project lock is a
    committed file, so a sidecar beside it would be a permanent untracked
    entry in every teammate's ``git status``. Inside ``.git/`` nothing sees
    it — the place `gitutil` already keeps its own lock. A linked worktree's
    ``.git`` is a file naming its private git dir, which serves the same.
    With no git dir at all it falls back to ``.boost/skill-lock.json.lock``.
    """
    git = _git_dir(Path(base))
    if git is not None:
        return git / "boost-skill-lock.lock"
    p = lock_path(base)
    return p.with_name(p.name + ".lock")


def _git_dir(base: Path) -> Path | None:
    """``base``'s git directory: ``.git`` itself, or where a ``.git`` file points."""
    dot = base / ".git"
    if dot.is_dir():
        return dot
    try:
        text = dot.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if not text.startswith("gitdir:"):
        return None
    target = base / text[len("gitdir:"):].strip()
    return target if target.is_dir() else None


def mutate(base, fn: Callable[[dict], bool | None]) -> bool:
    """Apply ``fn`` to a fresh read of ``base``'s project lock and persist it.

    The read happens under an exclusive cross-process lock, so ``fn`` sees
    every write another boost process finished first: two `install --scope
    project` runs used to each read, add their row and write, and the second
    write dropped the first's row — leaving a copy on disk that install then
    refused and uninstall disowned. ``fn`` returning False skips the write;
    returns whether it wrote. Refuses over a corrupt lock (:func:`write`).
    """
    with util.file_lock(guard_path(base), what="the project lock",
                        strict=False):
        lock = read(base)
        if fn(lock) is False:
            return False
        write(base, lock)
        return True


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
                "over it; %s" % (err, recover_hint(p.parent.parent)),
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
                     hint=recover_hint(base), wrap=True)


def write(base, lock: dict) -> None:
    """Stamp version/updated onto ``lock`` and write it atomically.

    Refuses over a corrupt lock (:func:`refuse_corrupt`). Takes no lock: a
    read-modify-write goes through :func:`mutate`, which calls this.
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
    def put(lock: dict) -> None:
        lock["skills"][name] = entry
    mutate(base, put)


def remove_skill(base, name: str) -> bool:
    """Drop ``name`` from the project lock; True if it was present.

    When the last skill goes the file is left in place (empty) rather than
    deleted — it is a tracked file in someone's repo, and removing it would show
    up as a spurious deletion in their next ``git status``.

    Refuses over a corrupt lock even though it reads as holding nothing:
    "not present" would be a false answer about a record boost cannot read.
    """
    refuse_corrupt(base)
    if not exists(base):
        return False    # nothing to remove, and no reason to create .boost/

    def drop(lock: dict) -> bool:
        if name not in lock["skills"]:
            return False
        del lock["skills"][name]
        return True
    return mutate(base, drop)
