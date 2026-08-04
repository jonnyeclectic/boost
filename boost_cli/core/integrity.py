"""Make the lock file's recorded digest binding, not advisory.

Every installed skill carries a ``sha256`` of its content and the ``commit`` it
came from, recorded at install time (:mod:`boost_cli.core.store`). Until now that
digest was only ever *reported* — ``boost verify`` would print "modified" and
move on. This module promotes it to a rule: with enforcement enabled, any boost
command that reads a skill's content first checks the on-disk tree against its
locked digest and refuses to serve a tree that has drifted.

The point is a tamper tripwire. Skills are executed by the agent, not by boost,
so boost cannot police what the agent loads — but it *can* refuse to hand you the
content of a skill whose bytes no longer match what you installed and reviewed,
which is where an editorial or supply-chain change would first show up.

Enforcement is opt-in (``config security.enforce_digest``, default off) so it
never surprises an existing setup; ``boost verify`` reports drift regardless.

This is pure logic over the lock file and the store, which is what makes it the
mutation gate's job to cover — ``store`` writes the digest, this decides whether
to trust it.
"""
from __future__ import annotations

from pathlib import Path

from ..errors import BoostError
from . import config, lockfile, paths, projectlock, scopes, util

STATUS_OK = "ok"
STATUS_MODIFIED = "modified"     # on-disk content no longer matches the lock
STATUS_MISSING = "missing"       # lock says installed, but the store dir is gone
STATUS_UNLOCKED = "unlocked"     # present on disk but no lock digest to check
STATUS_QUARANTINED = "quarantined"  # artifacts removed on purpose; stash holds them

ENFORCE_KEY = "security.enforce_digest"
COMMIT_KEY = "security.enforce_commit"


def _store_dir(name: str) -> Path:
    """The skill's canonical-store directory (no import cycle with store.py)."""
    return paths.store_dir() / name


def status(name: str, entry: dict | None = None) -> str:
    """Classify an installed skill's integrity against its lock entry.

    ``entry`` may be supplied to avoid a re-read when the caller already has it.
    Returns one of the ``STATUS_*`` constants. ``UNLOCKED`` means the lock has no
    recorded ``sha256`` to compare against — an old entry, not a failure.
    """
    if entry is None:
        entry = lockfile.get_skill(name)
    if not entry:
        # Not an installed skill at all — nothing this module can assert about.
        return STATUS_UNLOCKED
    sdir = _store_dir(name)
    if not sdir.is_dir():
        return STATUS_MISSING
    recorded = entry.get("sha256")
    if not recorded:
        return STATUS_UNLOCKED
    return STATUS_OK if util.sha256_dir(sdir) == recorded else STATUS_MODIFIED


def materialized_status(name: str, entry: dict) -> str:
    """Classify a rule/workflow's integrity against its lock entry.

    A materialized kind has no store dir — the artifacts it wrote (a CLAUDE.md
    managed block, a rendered command file) are the content the agent actually
    loads, so that is what gets checked: every recorded materialization must
    still be present and hash to the ``sha256`` recorded when it was written.
    An entry from before per-materialization hashes existed has nothing to
    compare — ``UNLOCKED``, not a failure. Quarantine removes the artifacts on
    purpose, so it short-circuits before "missing" can lie about it.
    """
    import hashlib

    from . import rules
    if entry.get("quarantined"):
        return STATUS_QUARANTINED
    unlocked = False
    for m in entry.get("materializations") or []:
        p = Path(m.get("path", ""))
        if m.get("mode") == rules.MODE_CLAUDE:
            try:
                content = rules.read_block(p.read_text(encoding="utf-8"), name)
            except OSError:
                content = None
        else:
            try:
                content = p.read_text(encoding="utf-8")
            except OSError:
                content = None
        if content is None:
            return STATUS_MISSING
        recorded = m.get("sha256")
        if not recorded:
            unlocked = True
        elif hashlib.sha256(content.encode("utf-8")).hexdigest() != recorded:
            return STATUS_MODIFIED
    return STATUS_UNLOCKED if unlocked else STATUS_OK


def project_status(entry: dict, base) -> str:
    """Classify a project-scoped skill's integrity against its per-repo lock.

    A project install has no canonical store — it materializes real directories
    into the repo, recorded (relative, committable) in the project lock with one
    ``sha256`` taken at install. The check re-derives each materialization path
    under ``base`` (refusing any that escapes, via
    :func:`scopes.resolve_in_base`), hashes the first that is present, and
    compares. Vendored third-party skills are exactly the ones a review should
    watch — they arrive by PR and run on every teammate's machine — so ``doctor``
    and ``verify`` need to see drift here the same way they do at user scope.
    """
    recorded = entry.get("sha256")
    present = None
    for m in entry.get("materializations") or []:
        path = scopes.resolve_in_base(base, m.get("path"))
        if path is not None and path.is_dir():
            present = path
            break
    if present is None:
        return STATUS_MISSING
    if not recorded:
        return STATUS_UNLOCKED
    return STATUS_OK if util.sha256_dir(present) == recorded else STATUS_MODIFIED


def project_skills():
    """(base, {name: entry}) for the current repo's project-scoped skills.

    ``(None, {})`` when not inside a project — the single place the rest of the
    CLI asks "does this working directory have committed skills?", so a command
    can fold them into whatever it already does for user-scope skills.
    """
    base = scopes.project_root()
    if base is None:
        return None, {}
    return base, projectlock.installed(base)


def commit_status(name: str, entry: dict | None = None) -> str | None:
    """Compare the installed commit against a commit pin, if one is set.

    Returns ``None`` when the skill is not commit-pinned (the common case),
    ``STATUS_OK`` when the recorded commit still matches the pin, and
    ``STATUS_MODIFIED`` when they diverge — which means the source moved out from
    under a pin that was supposed to freeze it.
    """
    if entry is None:
        entry = lockfile.get_skill(name)
    if not entry:
        return None
    pin = entry.get("commit_pin")
    if not pin:
        return None
    return STATUS_OK if entry.get("commit") == pin else STATUS_MODIFIED


def enforcement_enabled() -> bool:
    """True when digest enforcement is switched on in config (default False)."""
    return bool(config.get(ENFORCE_KEY, False))


def commit_enforcement_enabled() -> bool:
    """True when commit-pin enforcement is switched on (default False)."""
    return bool(config.get(COMMIT_KEY, False))


def enforce(name: str, entry: dict | None = None) -> None:
    """Raise BoostError if ``name`` fails an *enabled* integrity check.

    A no-op when enforcement is off, when the skill is not installed, or when the
    check passes. This is the guard the content-reading commands call before
    handing over a skill's bytes; ``UNLOCKED`` never blocks (there is nothing to
    compare, and blocking would punish an old lock entry).
    """
    if entry is None:
        entry = lockfile.get_skill(name)
    if not entry:
        return
    if enforcement_enabled():
        st = status(name, entry)
        if st == STATUS_MODIFIED:
            raise BoostError(
                "%s has been modified since install — its content no longer "
                "matches the lock file" % name,
                hint="inspect with `boost verify %s`, then `boost reinstall %s` "
                     "to restore the locked copy" % (name, name))
        if st == STATUS_MISSING:
            raise BoostError(
                "%s is in the lock file but its store directory is gone" % name,
                hint="`boost sync` to restore it, or `boost reinstall %s`" % name)
    if commit_enforcement_enabled() and commit_status(name, entry) == STATUS_MODIFIED:
        raise BoostError(
            "%s is pinned to commit %s but is now recorded at %s"
            % (name, (entry.get("commit_pin") or "")[:12],
               (entry.get("commit") or "")[:12]),
            hint="`boost unpin %s` to release the commit pin, or reinstall at "
                 "the pinned commit" % name)


def set_commit_pin(name: str, entry: dict, kind: str = "skill") -> str:
    """Freeze ``name`` to its currently-installed commit and persist.

    Returns the commit that was pinned. Raises BoostError if the entry has no
    recorded commit to pin (a local ``import`` with no source commit).
    ``kind`` routes persistence: rules and workflows record a source commit
    too, so they commit-pin the same way.
    """
    commit = entry.get("commit")
    if not commit:
        raise BoostError(
            "%s has no recorded source commit to pin" % name,
            hint="commit pinning needs an item installed from a tapped repo")
    entry["commit_pin"] = commit
    lockfile.set_entry(kind, name, entry)
    return commit


def clear_commit_pin(name: str, entry: dict, kind: str = "skill") -> bool:
    """Drop a commit pin from ``name``; True if one was present."""
    if not entry.get("commit_pin"):
        return False
    del entry["commit_pin"]
    lockfile.set_entry(kind, name, entry)
    return True
