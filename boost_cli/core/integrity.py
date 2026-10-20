# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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

import os
from itertools import chain, starmap
from pathlib import Path
from typing import NamedTuple

from ..errors import BoostError
from . import agents, catalog, config, lockfile, paths, projectlock, scopes, util

STATUS_OK = "ok"
STATUS_MODIFIED = "modified"     # on-disk content no longer matches the lock
STATUS_MISSING = "missing"       # lock says installed, but the store dir is gone
STATUS_UNLOCKED = "unlocked"     # present on disk but no lock digest to check
STATUS_QUARANTINED = "quarantined"  # artifacts removed on purpose; stash holds them
STATUS_UNREACHABLE = "unreachable"  # rows exist and boost writes none of the
                                    # agents they name: the item reached nothing
STATUS_STRANDED = "stranded"  # installed --local into a repo that is gone
STATUS_OUTDATED = "outdated"  # an agent's copy predates the locked version

ENFORCE_KEY = "security.enforce_digest"
COMMIT_KEY = "security.enforce_commit"


def _store_dir(name: str) -> Path:
    """The skill's canonical-store directory (no import cycle with store.py)."""
    return paths.store_dir() / name


def self_sourced(name: str, entry: dict | None) -> bool:
    """Whether ``entry`` records skill ``name`` as its own source.

    What `boost sync` writes for a skill put in the store by hand: ``tap:
    local``, no URL, and a ``source_dir`` that is the store dir itself. The
    user edits such a skill where it is, so its digest is the content boost
    first saw, not a copy anyone fetched and reviewed, and drifting from it
    is the skill changing rather than being tampered with. A local import
    whose source is elsewhere is not this, even once that source is gone:
    it was copied from something, and differing from the copy still means
    something.
    """
    if not entry or entry.get("tap") != "local" or entry.get("source_url"):
        return False
    raw = str(entry.get("source_dir") or "")
    if not raw:
        return False
    try:
        return os.path.samefile(raw, _store_dir(name))
    except OSError:
        # Either side missing or unreadable: the recorded path still says
        # which dir it named.
        return os.path.realpath(raw) == os.path.realpath(_store_dir(name))


def status(name: str, entry: dict | None = None) -> str:
    """Classify an installed skill's integrity against its lock entry.

    ``entry`` may be supplied to avoid a re-read when the caller already has it.
    Returns one of the ``STATUS_*`` constants. ``UNLOCKED`` means the lock has no
    recorded ``sha256`` to compare against — an old entry, not a failure. A
    skill kept in the store itself (:func:`self_sourced`) is ``OK`` whatever it
    hashes to: editing it is how it changes.
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
    if self_sourced(name, entry):
        return STATUS_OK
    return STATUS_OK if util.sha256_dir(sdir) == recorded else STATUS_MODIFIED


def skill_modified(name: str, entry: dict | None) -> bool:
    """Whether installed skill ``name`` has drifted from its locked digest.

    The one test both doctors ask, so the CLI and the MCP surface cannot
    disagree about it again: ``boost_doctor`` once checked rules and
    workflows only, and called a hand-edited skill "healthy" while ``boost
    doctor`` flagged it on the same machine. A quarantined skill is not
    asked — quarantine is its own report — and :func:`status` already keeps
    a self-sourced skill, a missing store dir and an unlocked row out.
    """
    if not entry or entry.get("quarantined"):
        return False
    return status(name, entry) == STATUS_MODIFIED


def reaches_no_agent(kind: str | None, entry: dict) -> bool:
    """Whether every materialization row names an agent boost no longer writes.

    Skipping such a row is right *per row*: nothing wrote that file and
    nothing ever will, so reading it as ``MISSING`` reported a fault whose
    remedy could not run (:func:`agents.materialization_is_written`).
    Skipping *every* row of an item is a different fact -- the rule reaches
    no agent, the workflow is in no command palette -- and the loop that
    skipped them has nothing left to judge, so it fell through to ``OK`` and
    an install that materialized nowhere read as healthy on every surface but
    ``doctor``'s note.

    An item with **no rows** is not this case and must keep reading ``OK``: a
    rule installed before rows existed has nothing to be unreachable about.
    That is the whole of ``bool(rows)``, and keying on "no row was written"
    instead would condemn every pre-rows entry on five surfaces at once. A
    row carrying no ``agent`` counts as written -- ``agents`` answers ``True``
    for it, preferring a reported gap to a dropped one -- so such an entry is
    judged by the loop, never condemned here.

    One predicate because two surfaces ask it: :func:`materialized_status`
    below, and ``boost doctor``, which walks the rows itself rather than
    re-reading every artifact. Re-deriving it in the command layer is how the
    two would come to disagree -- the same failure the ``kind`` parameter was
    added to :func:`materialized_status` to prevent.
    """
    rows = entry.get("materializations") or []
    kind = str(kind or entry.get("kind") or "rule")
    return bool(rows) and not any(
        agents.materialization_is_written(kind, entry.get("base"),
                                          m.get("agent"))
        for m in rows)


def written_agent_names(kind: str | None, entry: dict | None) -> list[str]:
    """The agents an installed item actually reaches, sorted and deduplicated.

    :func:`lockfile.agent_names` lists every *recorded* row, and a row is kept
    on purpose after boost stops writing its agent (so an uninstall can still
    reverse it). Every surface that names agents read it raw, so a rule
    written for one of five recorded agents still advertised all five in
    `boost list`, `boost info` and `boost stats` while `boost doctor`, on the
    same machine, said four of them were no longer written.

    The filter is :func:`reaches_no_agent`'s own predicate, row for row, so
    the two can't disagree: when that answers ``True`` this answers ``[]``.
    A row with no ``agent`` counts as written, as it does there. A skill
    records a flat ``agents`` list of links, not rows, and passes through.
    """
    if not entry:
        return []
    kind = str(kind or entry.get("kind") or "rule")
    if kind == "skill":
        return lockfile.agent_names(kind, entry)
    written = [m for m in entry.get("materializations") or []
               if agents.materialization_is_written(kind, entry.get("base"),
                                                    m.get("agent"))]
    return lockfile.agent_names(kind, {"materializations": written})


def materialized_status(name: str, entry: dict,
                        kind: str | None = None) -> str:
    """Classify a rule/workflow's integrity against its lock entry.

    A materialized kind has no store dir — the artifacts it wrote (a CLAUDE.md
    managed block, a rendered command file) are the content the agent actually
    loads, so that is what gets checked: every recorded materialization must
    still be present and hash to the ``sha256`` recorded when it was written.
    An entry from before per-materialization hashes existed has nothing to
    compare — ``UNLOCKED``, not a failure. Quarantine removes the artifacts on
    purpose, so it short-circuits before "missing" can lie about it.

    ``kind`` decides which write set a materialization row is judged against,
    and every caller already knows it -- each loops one lock section at a
    time. It is a parameter rather than a read of ``entry["kind"]`` so the
    two can never disagree: doctor passes the section's kind literally, so an
    entry whose field was lost (a lock restored from a snapshot older than
    the field, or hand-edited) would be judged as a rule here and as a
    workflow there, and the two surfaces would report opposite answers for
    one row with no way to tell which was right. The field stays the
    fallback for a caller that has only the entry.
    """
    import hashlib

    from . import rules
    if entry.get("quarantined"):
        return STATUS_QUARANTINED
    kind = str(kind or entry.get("kind") or "rule")
    # The repo a `--local` row was installed into is gone, so every artifact
    # reads as missing -- and MISSING's remedies (`reinstall`, `sync`, `heal`)
    # re-materialize into the recorded base, recreating the directory the
    # user deleted. A fact about the row rather than any one artifact, so it
    # is asked before the loop; and before UNREACHABLE, because which agents a
    # base takes is not a question a base that is gone can answer.
    if scopes.stranded(entry):
        return STATUS_STRANDED
    # Every row skipped means the item reached nothing. Asked before the loop
    # rather than after it because each of the three in-loop outcomes needs a
    # *written* row -- MISSING and MODIFIED return from inside the body and
    # `unlocked` is only set there -- so this is mutually exclusive with all
    # of them and there is no precedence to settle. Quarantine still wins
    # above: those artifacts are gone on purpose, and calling that unreachable
    # would send the user to a remedy that re-arms what quarantine disarmed.
    if reaches_no_agent(kind, entry):
        return STATUS_UNREACHABLE
    unlocked = False
    outdated = False
    for m in entry.get("materializations") or []:
        # A row naming an agent boost no longer writes is a record, not an
        # artifact: nothing wrote that file and nothing ever will, so reading
        # it as MISSING failed `boost verify` forever and sent `boost drift`
        # and `boost health` to a `boost sync` that skips the row by design.
        # `boost doctor` names it once instead -- see
        # `agents.materialization_is_written`.
        if not agents.materialization_is_written(kind, entry.get("base"),
                                                 m.get("agent")):
            continue
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
        # Carried past an upgrade that did not write this agent (it was
        # disabled, say): the file is intact and hashes to its own digest,
        # which is the old version's. After MODIFIED, so a hand edit is
        # still named as one rather than overwritten as merely behind.
        outdated = outdated or bool(m.get("stale"))
    if outdated:
        return STATUS_OUTDATED
    return STATUS_UNLOCKED if unlocked else STATUS_OK



def locally_edited(kind: str, name: str, entry: dict, base=None) -> bool:
    """Whether any installed copy of ``name`` was edited since boost wrote it.

    ``base`` names the project a *skill* row came from: a project skill has no
    store dir, so asking :func:`status` about it would judge whatever user-scope
    copy shares its name (or report it missing) instead of the files in the
    repo. Rules and workflows carry their own ``base`` in the row.

    The question `boost update` asks before overwriting: a skill's store dir,
    or any written rule/workflow artifact, no longer hashing to its recorded
    digest. Not :func:`materialized_status`, which answers with the *first*
    fault it meets -- a rule whose Cursor file was deleted reads ``MISSING``
    there however its CLAUDE.md block was edited, and the refresh would
    overwrite the edit it never looked at. A missing artifact, a row without a
    digest and a quarantined item are no evidence of an edit, and a row for an
    agent boost no longer writes is skipped as everywhere else. Neither is a
    workflow's skill-store copy: install already keeps an edited one in place
    rather than overwriting it, so it must not hold the workflow's own files.
    """
    import hashlib

    from . import rules, workflows
    if kind == "skill":
        if base is not None:
            return project_status(entry, base) == STATUS_MODIFIED
        return status(name, entry) == STATUS_MODIFIED
    if entry.get("quarantined"):
        return False
    for m in entry.get("materializations") or []:
        recorded = m.get("sha256")
        if m.get("slot") == workflows.SLOT_SKILL:
            continue
        if not recorded or not agents.materialization_is_written(
                kind, entry.get("base"), m.get("agent")):
            continue
        try:
            text = Path(m.get("path", "")).read_text(encoding="utf-8")
        except OSError:
            continue
        content = (rules.read_block(text, name)
                   if m.get("mode") == rules.MODE_CLAUDE else text)
        if content is not None and hashlib.sha256(
                content.encode("utf-8")).hexdigest() != recorded:
            return True
    return False

def project_status(entry: dict, base) -> str:
    """Classify a project-scoped skill's integrity against its per-repo lock.

    A project install has no canonical store — it materializes real directories
    into the repo, recorded (relative, committable) in the project lock with one
    ``sha256`` taken at install. The check re-derives each materialization path
    under ``base`` (refusing any that escapes, via
    :func:`scopes.resolve_in_base`) and hashes **every** copy that is present.
    Vendored third-party skills are exactly the ones a review should watch —
    they arrive by PR and run on every teammate's machine — so ``doctor`` and
    ``verify`` need to see drift here the same way they do at user scope.

    Every row, not the first present one: each agent loads its own copy, so an
    edit to ``.cursor/skills/x`` is what Cursor runs however intact the Claude
    copy is, and hashing only the first let that edit through as ``OK``. A
    modified copy outranks a missing one — `boost update` asks this before
    overwriting, and a deleted sibling must not hide an edit from it. A row
    that is gone (or whose path escapes ``base``) is ``MISSING``, the same
    rows `boost sync` (:func:`store.project_sync_plan`) re-materializes, so
    doctor, verify, heal and sync agree about one state.
    """
    recorded = entry.get("sha256")
    rows = project_missing_rows(entry, base)
    present = project_skill_dirs(entry, base)
    if not present:
        return STATUS_MISSING
    if recorded and any(util.sha256_dir(p) != recorded for p in present):
        return STATUS_MODIFIED
    if rows:
        return STATUS_MISSING
    if not recorded:
        return STATUS_UNLOCKED
    return STATUS_OK


def project_skill_dirs(entry: dict, base) -> list[Path]:
    """Every materialized copy of a project skill that is on disk, in row order.

    A row whose path escapes ``base`` is never answered
    (:func:`scopes.resolve_in_base`).
    """
    found = []
    for m in entry.get("materializations") or []:
        path = scopes.resolve_in_base(base, m.get("path"))
        if path is not None and path.is_dir():
            found.append(path)
    return found


def project_missing_rows(entry: dict, base) -> list[str]:
    """The recorded paths of a project skill with no copy on disk.

    The rows :func:`store.project_sync_plan` calls missing: gone, not a
    directory, or escaping ``base`` (which no repair will write either).
    """
    rows = []
    for m in entry.get("materializations") or []:
        path = scopes.resolve_in_base(base, m.get("path"))
        if path is None or not path.is_dir():
            rows.append(str(m.get("path")))
    return rows


def project_skill_dir(entry: dict, base) -> Path | None:
    """The first materialized copy of a project skill that is on disk, or None.

    Each row's path is re-derived under ``base`` through
    :func:`scopes.resolve_in_base`, so a committed path that escapes the repo
    is never answered. A project skill is a real directory per agent, all
    written from one source, so for *reading* it (info, pkg) the first present
    one stands for the install; *judging* it is :func:`project_status`'s, which
    hashes every copy.
    """
    dirs = project_skill_dirs(entry, base)
    return dirs[0] if dirs else None


def project_redirected(entry: dict, base) -> list[str]:
    """The rows of a project skill whose walk a symlink inside ``base`` bends.

    ``boost uninstall --local`` will not delete through such a row
    (:func:`scopes.parent_matches_spelling`), so its copy outlives the
    uninstall while the lock entry goes. ``install --local`` refuses to write
    one now, but a lock written before that still carries them, and a symlink
    committed *after* an install makes one out of a row that was honest — and
    :func:`project_status` cannot see either, because ``is_dir()`` follows the
    link and reports the skill intact. Rows containment already refuses
    (:func:`scopes.resolve_in_base` is ``None``) are not this question.
    """
    rows = []
    for m in entry.get("materializations") or []:
        rel = m.get("path")
        if scopes.resolve_in_base(base, rel) is None:
            continue
        if not scopes.parent_matches_spelling(base, rel):
            rows.append(rel)
    return rows


def project_skills():
    """(base, {name: entry}) for the current repo's project-scoped skills.

    ``(None, {})`` when not inside a project — the single place the rest of the
    CLI asks "does this working directory have committed skills?", so a command
    can fold them into whatever it already does for user-scope skills.

    It resolves the base the way ``install --local`` does, so ``doctor`` and
    ``verify`` see the skills install wrote even in a directory with no VCS
    marker. Reading with ``project_root`` instead is what made them report a
    clean machine while the lock and the agent dirs both sat in the cwd.
    """
    base = scopes.resolve_base(scopes.SCOPE_PROJECT)
    if base is None:
        return None, {}
    return base, projectlock.installed(base)


def installed_skill_rows() -> list[tuple[str, dict, str, Path | None]]:
    """Every installed skill as ``(name, entry, scope, base)``, both scopes.

    The user lock's rows (``base`` None) and the current project's
    (:func:`project_skills`), sorted by name with user scope first. A command
    that walks "installed skills" walks this, because the project lock is a
    different file: walking ``lockfile.installed()`` alone is what had
    ``outdated`` and ``update`` call a stale ``--local`` skill current while
    ``info`` said it had an update. A name installed in both scopes is two
    rows — they are two installs, and either can be the stale one.
    """
    rows = [(name, entry, scopes.SCOPE_USER, None)
            for name, entry in lockfile.installed().items()]
    base, project = project_skills()
    rows += [(name, entry, scopes.SCOPE_PROJECT, base)
             for name, entry in project.items()]
    return sorted(rows, key=lambda r: (r[0], r[2] != scopes.SCOPE_USER))


def find_installed(name: str) -> tuple[str, dict, Path | None] | None:
    """``(kind, entry, base)`` for an installed item, or None.

    ``name`` may be tap-qualified: the locks are keyed by the bare name, so it
    is split first and the qualifier is held against the installed record
    (:func:`catalog.for_tap`), exactly as ``boost info`` does. The user lock
    answers first (``base`` None); a skill installed ``--local`` into the
    current project answers next, with that project's ``base``. Asking only
    the user lock with the unsplit name is what had ``boost_info`` say
    "installed: no" for ``tap:name`` and for every project skill.
    """
    qualifier, bare = catalog.split_name(name)
    found = lockfile.find_any(bare)
    if found is not None:
        entry = catalog.for_tap(found[1], qualifier)
        if entry is not None:
            return found[0], entry, None
    base, project = project_skills()
    entry = catalog.for_tap(project.get(bare), qualifier)
    if entry is not None:
        return "skill", entry, base
    return None


class InstalledSkill(NamedTuple):
    """One installed skill row, with where its content lives.

    ``base`` is None for a user-scope row and the repo for a project one;
    ``dir`` is the copy a reader should open — the canonical store directory
    for user scope, the first materialized copy (:func:`project_skill_dir`)
    for project scope — or None when that copy is not on disk. A reader that
    took ``store.skill_store_dir(name)`` for a project row looked in
    ``~/.agents/skills``, found nothing, and called a skill ``boost list``
    shows "not installed".
    """

    name: str
    entry: dict
    scope: str
    base: Path | None
    dir: Path | None

    @property
    def is_project(self) -> bool:
        """True for a row from the current project's lock."""
        return self.scope == scopes.SCOPE_PROJECT


def _skill_row(name: str, entry: dict, scope: str,
               base: Path | None) -> InstalledSkill:
    if scope == scopes.SCOPE_PROJECT:
        d = project_skill_dir(entry, base)
    else:
        sd = paths.store_dir() / name
        d = sd if util.is_safe_component(name) and sd.is_dir() else None
    return InstalledSkill(name, entry, scope, base, d)


def installed_skills() -> list[InstalledSkill]:
    """:func:`installed_skill_rows`, each row carrying its content ``dir``.

    The walk a reader over "every installed skill" uses — ``policy check``,
    ``audit``, ``conflict``, ``count`` — so a ``--local`` install is checked
    from the copy in the repo rather than skipped. A name in both scopes is
    two rows: they are two installs, and either can be the blocked one.
    """
    return list(starmap(_skill_row, installed_skill_rows()))


def resolve_skill(name: str) -> InstalledSkill | None:
    """The installed *skill* ``name`` names, user scope first, else None.

    ``name`` may be tap-qualified; a qualifier is held against the installed
    record (:func:`catalog.for_tap`), so ``other:x`` does not answer with an
    ``x`` installed from elsewhere. Only the lock's skills sections answer —
    a rule or workflow of the same name is the caller's own question
    (:func:`lockfile.find_any`). The user lock answers first, as everywhere
    a bare name resolves; a skill installed ``--local`` into the current
    project answers next, which is the row ``boost list`` shows under
    "project skills".
    """
    qualifier, bare = catalog.split_name(name)
    entry = catalog.for_tap(lockfile.get_skill(bare), qualifier)
    if entry is not None:
        return _skill_row(bare, entry, scopes.SCOPE_USER, None)
    base, project = project_skills()
    entry = catalog.for_tap(project.get(bare), qualifier)
    if entry is not None:
        return _skill_row(bare, entry, scopes.SCOPE_PROJECT, base)
    return None


def refuse_project_scope(row: InstalledSkill, command: str) -> None:
    """Raise the truth for a user-scope-only ``command`` given a project row.

    Some commands act on what only a user-scope install has — the canonical
    store, the agent symlinks. For a project row the honest answer is which
    scope it is in, not "not installed" beside a ``boost list`` that shows
    it, and never a ``boost install`` hint that would add a second, user-scope
    copy. A user row returns without raising.
    """
    if not row.is_project:
        return
    raise BoostError(
        "%s is installed at project scope (%s) — %s applies to user-scope "
        "skills" % (row.name, paths.tilde(row.base), command),
        hint="see it with `boost list --local`", wrap=True)


def refuse_project_only(name: str, command: str) -> None:
    """:func:`refuse_project_scope` for ``name``, if it resolves to a project row.

    Call it where a user-lock lookup has just missed and the next line says
    "not installed": a name only the current project holds gets the scope
    answer instead, and any other miss returns for the caller to report.
    """
    row = resolve_skill(name)
    if row is not None:
        refuse_project_scope(row, command)


def installed_names() -> set[str]:
    """Every installed name, all three kinds, user lock and current project.

    One read of each lock, for a caller marking many names at once.
    """
    names = set(chain.from_iterable(lockfile.all_installed().values()))
    return names | set(project_skills()[1])


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


def verification_passed(status: str, missing_fields: list, commit_pin: str | None) -> bool:
    """Whether a `boost verify` row is genuinely OK, not just wearing an OK status.

    A row can carry STATUS_OK or STATUS_QUARANTINED and still be broken — missing
    lock fields, or a drifted commit pin — so `status` alone is not "passed". This
    is the single source of truth `cmd_verify` uses both to count failures and to
    color the rendered status token, so the two can never disagree again.
    """
    return (status in (STATUS_OK, STATUS_QUARANTINED)
            and not missing_fields
            and commit_pin != STATUS_MODIFIED)


_VERIFY_ROLE_BY_STATUS = {
    STATUS_OK: "success", STATUS_MODIFIED: "warn", STATUS_MISSING: "danger",
    STATUS_UNLOCKED: "warn", STATUS_QUARANTINED: "muted",
    STATUS_UNREACHABLE: "warn", STATUS_STRANDED: "warn",
    STATUS_OUTDATED: "warn",
}


def verification_role(status: str, passed: bool) -> str:
    """The color role `cmd_verify` paints a row's status token with.

    Mirrors `verification_passed`: STATUS_OK/STATUS_QUARANTINED only keep their
    normal success/muted role when the row actually passed. A row that fails
    for a reason the status text doesn't show — missing lock fields, a drifted
    commit pin — wears the failing color instead, so the token always agrees
    with whether the row is counted in `bad`.
    """
    role = _VERIFY_ROLE_BY_STATUS.get(status, "warn")
    if not passed and role in ("success", "muted"):
        return "danger"
    return role


def enforcement_enabled() -> bool:
    """True when digest enforcement is switched on in config (default False)."""
    return bool(config.get(ENFORCE_KEY, False))


def enforce_row(row: InstalledSkill) -> None:
    """:func:`enforce` for an :class:`InstalledSkill` of either scope.

    A user row is :func:`enforce` exactly. A project row has no store copy to
    hash, so it is judged the way ``verify`` judges it (:func:`project_status`):
    with enforcement on, a copy that drifted from the project lock's digest is
    refused the same as a drifted store copy would be.
    """
    if not row.is_project:
        enforce(row.name, row.entry)
        return
    if (enforcement_enabled()
            and project_status(row.entry, row.base) == STATUS_MODIFIED):
        raise BoostError(
            "%s has been modified since install — its content no longer "
            "matches the project lock file" % row.name,
            hint="inspect with `boost verify %s`" % row.name, wrap=True)


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
                     "to restore the locked copy" % (name, name), wrap=True)
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
