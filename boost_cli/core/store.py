# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The canonical store (~/.agents/skills) and agent symlinks.

install():  copy skill dir from a tap clone -> store, symlink into every
            enabled agent dir, record in the lock file, log to the journal.
"""
from __future__ import annotations

import contextlib
import os
import shutil
import stat
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import starmap
from pathlib import Path

from ..errors import BoostError
from . import (
    agents,
    catalog,
    config,
    gitutil,
    journal,
    lockfile,
    paths,
    policy,
    projectlock,
    registry,
    scopes,
    util,
)


@dataclass
class InstallResult:
    """Outcome of one install: dest, linked agents, conflicts, kind."""
    name: str
    dest: Path
    linked: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    # Agent dirs the link, or a rule or workflow file, could not be written
    # into (a dir restored with the wrong owner, say). Kept apart from
    # `conflicts`: nothing is in the way, the directory itself refuses, and
    # the remedy is different.
    unwritable: list[str] = field(default_factory=list)
    # (agent dir, what blocks it) where something that is not a directory sits
    # at or above the agent's skills, rules or commands dir: a dangling
    # ``~/.claude/skills`` symlink, or a file at ``~/.cursor``. No mode change
    # clears that, so it is kept apart from `unwritable` and worded with
    # `link_refusal`.
    blocked: list[tuple[str, str]] = field(default_factory=list)
    # Agents that can already use this skill without a symlink because they read
    # the canonical store directly (agents.native_store_agents). Kept apart from
    # `linked` so the lock records only real links, while the install report can
    # still tell the user the skill reached them.
    native: list[str] = field(default_factory=list)
    score: int = 0
    upgraded: bool = False
    kind: str = "skill"
    scope: str = "user"   # "user" or "project" — where a rule/workflow landed
    # For rules/workflows the installed content is a single file (or a merged
    # CLAUDE.md block), not a SKILL.md tree — carry the raw source so the caller
    # scans exactly what it installed instead of a non-existent SKILL.md.
    scan_text: str | None = None
    # MCP servers the skill declares (mcpdecl.servers_for rows). Detected here
    # but never acted on: core stays non-interactive, so the command layer owns
    # the offer to register them — same split as `conflicts` and `score`.
    mcp_servers: list[dict] = field(default_factory=list)
    # Names actually written to the project's .mcp.json — not what was
    # declared. The two differ when the file could not be written, and the
    # install report must show the former.
    mcp_recorded: list[str] = field(default_factory=list)
    # The tap an import just replaced (`install_from_path` only). Importing over
    # a tapped skill rewrites its lock entry to `local` and so drops the only
    # thing `boost update` refreshes it from; the caller says so.
    replaced_tap: str | None = None
    # Agents still linked outside a declared `--agent` scope after the run
    # (`install_from_path` only). Narrowing links into fewer agents but never
    # removes a link — pruning stays `boost sync --prune`'s decision — so these
    # are exactly what the next `sync --diff` reports as out of scope.
    out_of_scope: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RemoteSource:
    """A git URL `boost import` cloned, and the commit the clone checked out.

    The clone is a temporary directory removed as soon as the import returns,
    so its path is the one thing the lock must not record: `boost info` showed
    it and `boost reinstall` looked for it long after it was gone. The lock
    records this instead — the URL, the commit, and each skill's directory
    inside the repo, which is enough to clone it again.
    """

    url: str
    root: Path
    commit: str


def repo_path(remote: RemoteSource, skill_dir: Path) -> str:
    """``skill_dir`` relative to the clone, POSIX-style; ``.`` for the root.

    A module function, not a ``RemoteSource`` method, on purpose: the mutation
    gate splits this file per top-level function and refuses to split a module
    holding any class with a method (`scripts/mutation_shards.py`), which
    would put the whole of store.py back on the critical path.
    """
    return Path(skill_dir).relative_to(remote.root).as_posix()


@contextlib.contextmanager
def cloned_source(url: str) -> Iterator[RemoteSource]:
    """Clone ``url`` into a temporary directory for the length of the block.

    A full checkout, not a tap's Markdown cone: an import copies whatever the
    repo ships, assets included. The directory is removed on the way out
    whether or not the clone or the install inside the block succeeded.
    """
    tmp = Path(tempfile.mkdtemp(prefix="boost-import-"))
    try:
        root = tmp / "repo"
        gitutil.clone_shallow(url, root, sparse=False)
        yield RemoteSource(url=url, root=root, commit=gitutil.head_commit(root))
    finally:
        with contextlib.suppress(OSError):
            util.rmtree(tmp)


def is_url_import(entry: dict) -> bool:
    """Whether a lock entry is a `boost import` of a git URL.

    Only a fresh clone can restore one, and sync never touches the network, so
    its repair is `boost reinstall` where every other skill's is `boost heal`.
    ``sync``/``heal`` and ``doctor`` both ask here, so they name the same one.
    """
    return entry.get("tap") == "local" and bool(entry.get("source_url"))


def local_source_dir(entry: dict) -> Path | None:
    """The directory a local import can be read again from, else None.

    None for a URL import: its ``source_dir`` is a path inside the repo, and
    read as a local path it would resolve against whatever directory boost
    happens to run in. None for an empty one too, which ``Path`` turns into
    the cwd. Otherwise the recorded directory, if it still holds a SKILL.md.
    """
    raw = str(entry.get("source_dir") or "")
    if not raw or entry.get("source_url"):
        return None
    src = Path(raw)
    return src if (src / "SKILL.md").is_file() else None


def reinstall_from_url(name: str, entry: dict) -> InstallResult:
    """Clone a URL import's repo again and reinstall ``name`` from it.

    Reads the recorded path at the repo's current HEAD — the same thing a tap
    skill's reinstall does with the tap's current checkout — and records the
    new commit. ``force`` as for any reinstall: replacing a pinned skill is
    what the command is for. A path that leaves the clone is refused; the lock
    is a file anyone can edit, and ``../`` would otherwise reach whatever sits
    beside the temporary directory.
    """
    url = str(entry.get("source_url") or "")
    rel = str(entry.get("source_dir") or ".")
    with cloned_source(url) as remote:
        src = remote.root / rel
        inside = src.resolve().is_relative_to(remote.root.resolve())
        if not inside or not (src / "SKILL.md").is_file():
            raise BoostError("%s has no SKILL.md at %s" % (url, rel),
                             hint="re-import it from wherever it lives now")
        return install_from_path(src, name=name, force=True, remote=remote)


def skill_store_dir(name: str) -> Path:
    """Resolve ``name`` to its dir under the canonical store.

    Raises BoostError unless the name is a safe path component.
    """
    if not util.is_safe_component(name):
        raise BoostError("invalid skill name %r" % name)
    return paths.store_dir() / name


def read_skill_meta(name: str) -> tuple[dict, str] | None:
    """(frontmatter, body) for an installed skill's store copy, or None.

    None on anything that keeps the content from being read honestly: no
    store dir, no ``SKILL.md``, an unreadable file, or an unclosed
    frontmatter fence (:func:`frontmatter.unclosed` — every field would read
    as absent, which is not the same fact as the skill declaring none).
    Callers that use this for policy enforcement (``boost policy check``)
    must treat ``None`` as *not checked*, never as a violation — a store read
    failing is not evidence the skill lacks a version or description.
    """
    from . import frontmatter

    skill_md = skill_store_dir(name) / "SKILL.md"
    if not skill_md.exists():
        return None
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if frontmatter.unclosed(text):
        return None
    return frontmatter.parse(text)


def resolve_lock_entry(name: str) -> tuple[str, str | None, dict | None]:
    """(bare_name, kind, entry) for a possibly tap-qualified ``name``.

    Splits an ``owner/repo:skill`` qualifier (:func:`catalog.split_name`) and
    looks the *bare* name up across every lock section
    (:func:`lockfile.find_any`) — the lock keys installed items by their bare
    name, and :func:`skill_store_dir` rejects the qualified string outright
    since ``:`` (and ``/``) is not a safe path component. A command that
    probes the store or the lock with the still-qualified string before
    splitting gets "invalid skill name" or "not installed" for the very
    string an ambiguity hint just told it to type.

    When a qualifier is given, it is checked against the entry's own ``tap``
    (:func:`catalog.tap_matches`): an item installed from a *different* tap
    is not this qualifier's answer, so ``kind``/``entry`` come back
    ``(None, None)`` rather than reporting another tap's install under this
    name — the same rule ``commands/info.py``'s ``_for_tap`` applies. A
    caller that also accepts a not-yet-installed name falls through to
    :func:`catalog.resolve_one` in that case, which already parses the
    qualified grammar; a caller that only operates on installed items reports
    "not installed", same as a bare miss.
    """
    qualifier, bare = catalog.split_name(name)
    found = lockfile.find_any(bare)
    if found is None:
        return bare, None, None
    kind, entry = found
    if qualifier and not catalog.tap_matches(str(entry.get("tap") or ""), qualifier):
        return bare, None, None
    return bare, kind, entry


def upstream_source(name: str) -> tuple[str, str, str, str]:
    """``(bare, kind, tap, rel)``: where item ``name`` lives in its tap.

    The installed copy comes first. The lock records exactly which file or
    directory was installed, while the catalog can only guess from a name.
    A registry that ships ``csharp-reviewer`` three times makes
    :func:`catalog.resolve_one` refuse, telling the user to install one copy
    with ``--path`` and retry. Asking the catalog first meant that retry
    failed the same way. Only a name that is not installed, or whose tap
    qualifier names another tap, falls through to the catalog.

    ``rel`` is :func:`catalog.upstream_path`: the defining file for a rule or
    workflow, the directory for a skill. A lock entry with no ``tap`` counts
    as ``local``, an import with no upstream.
    """
    bare, kind, lk = resolve_lock_entry(name)
    if lk is not None:
        # `kind` is always set when an entry is: it names the lock section.
        return (bare, str(kind), str(lk.get("tap") or "local"),
                catalog.upstream_path(lk))
    entry = catalog.resolve_one(name)
    return (bare, str(entry.get("kind") or "skill"), str(entry["tap"]),
            catalog.upstream_path(entry))


def lock_drift(entry: dict, qualifier: str | None,
               version: str | None) -> list[tuple[str, str, str]]:
    """How an installed lock ``entry`` differs from a requested ``tap:name@ver``.

    Returns ``(field, installed, wanted)`` for each of ``"tap"`` and
    ``"version"`` that the request pins and the entry does not satisfy; an
    empty list means the install is what was asked for. A field the request
    leaves out (no qualifier, no ``@version``) is never drift.

    The tap test is :func:`catalog.tap_matches`, the same one
    :func:`resolve_lock_entry` applies, so ``skills:x`` still matches an
    install from ``owner/skills``. The fallbacks mirror what
    ``boost bundle dump`` writes for an entry missing either field — no tap is
    ``local``, no version is ``0.0.0`` — so a Boostfile dumped from this lock
    reads back with no drift at all.
    """
    drift: list[tuple[str, str, str]] = []
    tap = str(entry.get("tap") or "local")
    if qualifier and not catalog.tap_matches(tap, qualifier):
        drift.append(("tap", tap, qualifier))
    have = str(entry.get("version", "0.0.0"))
    if version and have != version:
        drift.append(("version", have, version))
    return drift


def installed() -> dict:
    """Return the lock file's installed skills as {name: entry}.

    Skills only; rules/workflows live in their own lock sections.
    """
    return lockfile.installed()


def has_content() -> bool:
    """True if the canonical store holds any skill directory at all.

    Independent of the lock file: a store dir survives even when
    ``.skill-lock.json`` goes missing or corrupt, so this is how a caller
    tells a genuinely fresh install (nothing installed, nothing to report)
    apart from one whose lock record vanished out from under a populated
    store (a fault `boost verify`/`drift`/`doctor` must not stay quiet
    about).
    """
    root = paths.store_dir()
    if not root.is_dir():
        return False
    return any(c.is_dir() and not c.name.startswith(".") for c in root.iterdir())


def source_dir_for(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone.

    Clones the tap first if it is only *registered* and not yet cloned — the
    state `boost catalog --import` deliberately leaves a tap in (a bundle
    ships the catalogue, not the repo, precisely so the receiver can search
    before paying for any clone). `catalog --import`'s own hint promises
    "`boost install` clones just the one registry it needs"; without this, a
    tap that was imported rather than tapped raised "source vanished from
    tap" — a message that implies the source *used to* exist, when really it
    was never fetched.

    Materializes the directory next. Taps check out Markdown only, so a skill
    that ships `scripts/` or `assets/` has them in the index and not on disk;
    `_copy_skill` is a copytree, and handed a partial directory it copies what
    is there and reports success. Every consumer of a tap's real files — both
    install paths, `sha256_dir`, `boost info` — comes through here, so this is
    the one place that has to get it right.

    Only a skill has a source directory. A rule or workflow is one file, read
    through ``entry["skill_md"]`` by its own installer, so it is refused here
    before the tap is cloned or widened: `boost info` and `boost deps` ask
    about every not-installed entry, and checking SKILL.md after materializing
    had them write ``/rules/*`` into the sparse cone for a dir they discarded.
    An entry with no ``kind`` (an old cache, or one `quality` builds by hand)
    is a skill.
    """
    kind = entry.get("kind") or catalog.KIND_SKILL
    if kind != catalog.KIND_SKILL:
        raise BoostError("%s is a %s, not a skill: it has no source directory"
                         % (entry["name"], kind))
    tap = registry.get(entry["tap"])
    if not tap.is_cloned:
        gitutil.clone_shallow(tap.url, tap.path)
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    gitutil.materialize(tap.path, entry["rel_dir"])
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def link_agents(name: str, only: list[str] | None = None) -> InstallResult:
    """Symlink store/<name> into each linking agent dir. Returns result with
    .linked (agent names), .conflicts (paths that were real files/dirs) and
    .native (agents that read the store directly and needed no link).

    A link that already leads to the store copy is left alone and counts as
    linked, so a dir that refuses writes only refuses a link that needs one:
    a missing link, or one pointing elsewhere."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = skill_store_dir(name)
    # Deliberately NOT filtered by `only`. That list scopes which agents get a
    # *link*, but a native-store agent's access follows from the store itself,
    # which every install writes no matter how narrow the scope — so even
    # `--agent cursor` really does leave the skill visible to Gemini, and
    # saying otherwise would be a lie. Filtering here also silently broke
    # reinstall: `preserved_agent_scope` replays the lock's recorded *links*,
    # which by construction never contain a native agent.
    res.native = list(agents.native_store_agents())
    for agent, adir in agents.linking_agents().items():
        if only and agent not in only:
            continue
        link = adir / name
        try:
            adir.mkdir(parents=True, exist_ok=True)
            if link.is_symlink():
                if _already_links(link, target):
                    # Already right, so there is nothing to write. Re-creating
                    # it anyway needed a writable dir: in one that refuses
                    # writes, the unlink raised PermissionError and a reinstall
                    # printed "not linked" over a link still on disk, still
                    # pointing at the store, and still in the lock's `agents`.
                    res.linked.append(agent)
                    continue
                link.unlink()
            elif link.exists():
                res.conflicts.append(str(link))
                continue
            link.symlink_to(target)
        except PermissionError:
            # One unwritable agent dir used to abort the whole install at
            # exit 70 — after the store copy and the other agents' links, so
            # the lock recorded none of it. Skip the agent and say so; the
            # caller names the remedy.
            res.unwritable.append(str(adir))
            continue
        except OSError:
            # A dangling symlink or a file where the agent dir belongs: the
            # mkdir raises FileExistsError or NotADirectoryError. It escaped
            # here after `_copy_skill` had run, so the install exited 70 with
            # the skill in the store and no lock entry. Skip it the same way.
            # Anything else is not understood, so it stays loud.
            block = paths.refuses_writes(adir)
            if block is None or not paths.in_the_way(block):
                raise
            res.blocked.append((str(adir), str(block)))
            continue
        res.linked.append(agent)
    return res


def _already_links(link: Path, target: Path) -> bool:
    """True if the symlink ``link`` already leads to ``target``.

    Asks about this one skill's store dir, not the store as a whole the way
    :func:`resolves_into_store` does: a link to another skill's copy is wrong
    and must still be replaced.

    **Both sides are resolved**, for the reason :func:`resolves_into_store`
    gives: under macOS's ``/tmp`` or ``/var/folders`` a link written as
    ``/tmp/.../x`` resolves to ``/private/tmp/.../x``, so comparing it against
    a nominal ``target`` never matches. The whole chain is followed, so a link
    that reaches the store through an alias counts too.

    Fails closed: a dangling link, a loop, or a target that is not there is
    not linked, and takes the old unlink-and-recreate path. Only the
    *target*'s strictness carries that: a dangling link resolves leniently to
    a path nothing is at, which cannot equal a store dir that resolved
    strictly, while a store dir that is missing raises and answers False for
    every link at once.
    """
    try:
        have = normalize_link_target(link.resolve())
        want = normalize_link_target(target.resolve(strict=True))
    except (OSError, RuntimeError):
        # RuntimeError: Python 3.12 raises it for a symlink loop, and it is
        # not an OSError (see resolves_into_store).
        return False
    return have == want


def link_refusal(adir: str, block: str) -> tuple[str, str]:
    """Why a write in `adir` was refused, and the one step that clears it.

    For a ``res.blocked`` pair. Every surface that reports one words it here,
    so none of them tells the user to ``chmod`` a dangling symlink.
    """
    return (paths.not_writable(Path(adir), Path(block)),
            paths.write_remedy(Path(block)))


def preserved_agent_scope(only_agents: list[str] | None,
                          existing: dict | None) -> list[str] | None:
    """Agent scope for a re-install: the caller's if given, else the lock's.

    ``boost install foo --agent claude-code`` records exactly that subset. But
    ``update`` and ``reinstall`` force-reinstall with ``only_agents=None``, and
    ``link_agents(None)`` fans out to *every* enabled agent — so a deliberate
    narrowing silently became a full install, and the lock entry was rewritten
    to match. Falling back to what the lock already records keeps the scope a
    property of the install rather than of whichever agents happen to be
    enabled the next time something updates.

    An explicit ``only_agents`` still wins, so re-running install with
    ``--agent`` remains the way to widen the scope again. Skills record their
    scope as ``agents``; rules and workflows record one ``materializations``
    row per agent. An empty record means "nothing was linked", not "link
    nothing", so it falls back to every enabled agent — exactly what
    ``link_agents`` does with ``None``.
    """
    if only_agents is not None:
        return only_agents
    if not existing:
        return None
    # A recorded declaration outranks the link list. Now that ``agents``
    # describes disk, it can legitimately name agents *outside* a narrowing —
    # and replaying it would make `update`/`reinstall` recreate a link the
    # declaration excludes, including one the user had just deleted by hand.
    # `sync` already refuses to do that (``scoped_agents``); these have to
    # agree, or which command you run decides what your agent set is.
    declared = existing.get("only_agents")
    if declared:
        return list(declared)
    recorded = existing.get("agents")
    if recorded is None:
        recorded = [m.get("agent")
                    for m in existing.get("materializations") or ()]
    return [a for a in recorded if a] or None


def declared_agent_scope(only_agents: list[str] | None,
                         existing: dict | None) -> list[str] | None:
    """The scope to RECORD in the lock: an explicit narrowing, or the last one.

    Deliberately *not* :func:`preserved_agent_scope`. That one answers "which
    agents should this install link into", and falls back to the lock's
    ``agents`` — which records what happens to be linked right now. Writing
    that back as a declared scope would promote "these were the enabled agents
    at install time" into "the user asked for exactly these", permanently
    freezing a skill out of any agent enabled later. The two questions look
    alike and are not, so they get separate functions.

    Only an explicit ``--agent`` narrows. Absent that, an earlier declaration
    is carried forward so ``update``/``reinstall`` don't drop it, and a skill
    that was never narrowed keeps no scope at all (``None``).
    """
    if only_agents is not None:
        return list(only_agents)
    return (existing or {}).get("only_agents")


def scoped_agents(entry: dict, enabled: dict[str, Path]) -> dict[str, Path]:
    """The enabled agents a locked skill is supposed to be linked into.

    Fails **open**: an entry with no ``only_agents`` — every entry written
    before this field existed — means "not narrowed", so it gets every enabled
    agent. That keeps ``boost sync`` doing its other job, which is linking
    already-installed skills into an agent that was enabled afterwards.
    """
    scope = entry.get("only_agents")
    if not scope:
        return enabled.copy()
    return {a: d for a, d in enabled.items() if a in scope}


def unlink_agents(name: str) -> list[str]:
    """Remove the ``name`` symlink from every linking agent dir.

    Returns the agents unlinked; non-symlink files are left alone. Agents that
    read the canonical store directly never had a link, so there is nothing
    here to reverse for them — uninstalling the store dir is what removes the
    skill from their view.
    """
    removed = []
    for agent, adir in agents.linking_agents().items():
        link = adir / name
        if link.is_symlink():
            link.unlink()
            removed.append(agent)
    return removed


def sideline(name: str, by: str) -> list[str]:
    """Unlink ``name`` and record *why*, so other commands stop fighting it.

    ``focus``, ``profile use`` and ``context apply`` all set a skill's links
    aside deliberately, and used to do it by calling :func:`unlink_agents`
    alone — leaving the lock's ``agents`` field pointing at links that no
    longer exist. Every reader of that field (``list``, ``doctor``,
    ``sync_plan``) took the stale record at face value: ``doctor`` called the
    gap damage and told the user to run ``boost sync``, and ``sync_apply``
    obeyed, silently re-linking the very skill that was just set aside.

    Recording ``sidelined_by`` closes the loop: it names the mechanism
    responsible (``"focus"``, ``"profile"`` or ``"context"``) so a later
    sideline overwrites an earlier one rather than stacking, and so
    :func:`unsideline` and every consulting reader have one flag to check
    instead of re-deriving "should this be linked" from a disk state that
    lockfile.write() itself does not read.
    """
    removed = unlink_agents(name)
    entry = lockfile.get_skill(name)
    if entry is not None:
        entry["sidelined_by"] = by
        # `agents` is defined as the links measured from disk, and the links
        # have just been removed — so leaving the old list had `boost list`
        # keep advertising the skill to agents that could no longer see it.
        # `quarantine` clears it for the same reason; :func:`unsideline`
        # recomputes it, exactly as `quarantine --release` does.
        entry["agents"] = []
        lockfile.set_skill(name, entry)
    return removed


def unsideline(name: str) -> InstallResult:
    """Relink ``name`` and clear any recorded sideline.

    The inverse of :func:`sideline`, used by ``focus --clear``, a skill
    re-entering an active focus/profile/context selection, and ``context
    disable``. Clears the flag regardless of which mechanism set it — only
    one can be true of a skill at a time, and whichever command relinks it is
    the one ending it.
    """
    res = link_agents(name)
    entry = lockfile.get_skill(name)
    if entry is not None:
        # Record the links this just made, since sideline() emptied the list.
        entry["agents"] = res.linked
        entry.pop("sidelined_by", None)
        lockfile.set_skill(name, entry)
    return res


def linked_agents(name: str) -> list[str]:
    """The linking agents that currently hold a symlink for ``name``.

    Measured from disk, not inherited from the lock, because this is what the
    lock's ``agents`` field is *defined* to mean. Writing back only the links a
    given run created made ``agents`` record the request instead of the result:
    ``install X --agent cursor --force`` on a skill linked into three agents
    left three symlinks and a lock claiming one, and every reporting surface
    believed the lock.

    Deliberately the same ``is_symlink()`` test :func:`unlink_agents` uses, so
    what an install records is exactly what an uninstall will remove. A regular
    file sitting where a link should be is a conflict, not a link, and is
    excluded by both.
    """
    return [agent for agent, adir in agents.linking_agents().items()
            if (adir / name).is_symlink()]


def refusing_dir(path: Path) -> Path:
    """The directory to make writable so a write under ``path`` can succeed.

    ``path`` itself when it exists; otherwise its nearest existing ancestor,
    which is the one that refused to create it. Naming a missing directory in
    a `chmod u+w` remedy hands the user a command that fails.

    A path boost may not even look at counts as not there: under a parent with
    no search bit, ``exists()`` raises PermissionError on Python 3.12 and 3.13
    (3.14 answers False), and raising here turned the named refusal it was
    wording into exit 70.
    """
    while path.parent != path:
        with contextlib.suppress(PermissionError):
            if path.exists():
                break
        path = path.parent
    return path


def _untouched_materializations(existing: dict | None,
                                linked: list[str]) -> list[dict]:
    """Recorded materializations for agents a run did not write to.

    Rules and workflows rebuild ``materializations`` from scratch on every
    install, so a narrowed re-install used to drop the rows for the agents it
    skipped — while leaving their files exactly where they were. Since
    ``_uninstall_rule`` and ``_uninstall_workflow`` are driven by this list and
    never sweep the agent dirs, those files became unremovable: a managed block
    in ``CLAUDE.md`` or a live slash command that no record claimed and no
    command could reverse.
    """
    return [m for m in (existing or {}).get("materializations") or []
            if m.get("agent") not in linked]


def unwritable_agent_dirs() -> list[Path]:
    """Existing agent dirs boost writes into and may not.

    Every linking agent's skills dir, where an install symlinks, and each dir
    a recorded rule or workflow row materializes into: ``~/.cursor/rules``,
    ``~/.cursor/commands``, or ``~/.claude`` itself for the ``CLAUDE.md`` a
    rule merges into. Only the dirs a row names: a skills-only user whose
    ``~/.claude/commands`` is read-only on purpose (another tool manages it)
    has nothing boost would write there, so it is not boost's to report.

    A row refused at install names the nearest existing ancestor, as the
    install did, since a ``chmod u+w`` on a dir that was never created fails.
    A dir that does not exist is not reported: an install creates it.
    """
    dirs = list(agents.linking_agents().values())
    dirs += [refusing_dir(d) if refused else d
             for d, refused in _materialized_dirs()]
    return [d for d in dict.fromkeys(dirs)
            if d.is_dir() and not os.access(str(d), os.W_OK)]


def blocked_agent_dirs() -> list[tuple[Path, Path]]:
    """``(dir, block)`` for each dir boost writes into that something blocks.

    The dirs :func:`unwritable_agent_dirs` checks, where a file or a dangling
    symlink sits at the dir or above it: a file at ``~/.cursor``, a
    ``~/.cursor/rules`` link that leads nowhere. Neither is a directory, so
    :func:`unwritable_agent_dirs` never sees one, and a row recorded as
    refused for it was reported by nothing. The pair is what
    :func:`link_refusal` words.

    One pair per block: a file at ``~/.cursor`` stops its skills, rules and
    commands dirs alike, and one move clears all three.
    """
    dirs = [*agents.linking_agents().values(),
            *(d for d, _refused in _materialized_dirs())]
    found: dict[Path, Path] = {}
    for d in dict.fromkeys(dirs):
        block = paths.refuses_writes(d)
        if block is not None and paths.in_the_way(block):
            found.setdefault(block, d)
    return [(d, block) for block, d in found.items()]


def _materialized_dirs() -> Iterator[tuple[Path, bool]]:
    """``(dir, refused)`` for each recorded rule or workflow row with a path:
    the dir it writes into, and whether its install was refused there."""
    for section in (lockfile.installed_rules(), lockfile.installed_workflows()):
        for entry in section.values():
            for m in entry.get("materializations") or []:
                if m.get("path"):
                    yield Path(m["path"]).parent, bool(m.get("unwritable"))


def _refused_target(err: OSError, path: Path, unwritable: list[str],
                    blocked: list[tuple[str, str]]) -> bool:
    """File a refused write under ``path`` as `unwritable` or `blocked`.

    For a rule or workflow target, the same two shapes :func:`link_agents`
    skips for a skills dir. A dir that refuses the write is named for a
    ``chmod``: ``path``'s dir, or its nearest existing ancestor when it was
    never created. A file or a dangling symlink where the dir or a parent
    belongs makes the mkdir raise FileExistsError or NotADirectoryError, and
    no mode change clears it, so it is kept apart and worded with
    :func:`link_refusal`. False for anything else: it is not understood, and
    the caller re-raises it rather than skip an agent in silence.

    ``paths.refuses_writes``, not :func:`refusing_dir`, finds the block:
    ``Path.exists`` follows a dangling link, so it walks past the link to a
    parent that is fine.
    """
    if isinstance(err, PermissionError):
        # Not `refusing_dir`: its `exists()` walk raises PermissionError of its
        # own under a parent with no search bit, after the other agents were
        # written. `refuses_writes` asks `lexists`, which answers False there.
        unwritable.append(str(paths.refuses_writes(path.parent) or path.parent))
        return True
    block = paths.refuses_writes(path.parent)
    if block is None or not paths.in_the_way(block):
        return False
    blocked.append((str(path.parent), str(block)))
    return True


def _refused_materializations(existing: dict | None, linked: list[str],
                              refused: list[dict]) -> list[dict]:
    """The rows to record beside this run's writes: refused, then untouched.

    An agent whose directory refused the write is still recorded, as a row
    marked ``unwritable``. Rules and workflows derive their re-install scope
    from these rows (:func:`preserved_agent_scope`), so an agent with no row
    silently dropped out of every later `sync`, `reinstall` and `update`: the
    first refusal became permanent. The row keeps it in scope, and
    :func:`sync_plan` reads it as a materialization still to write.

    A refused row replaces that agent's old one. The old file, if any, is
    still on disk at the same path, and the new row still names that path, so
    uninstall removes it.
    """
    done = linked + [r["agent"] for r in refused]
    return refused + _untouched_materializations(existing, done)


def _copy_skill(src: Path, dest: Path) -> None:
    """Copy a skill tree into ``dest`` atomically.

    The old rmtree-then-copytree left a window where a crash destroyed the
    previous good copy before the new one finished — on a reinstall/upgrade the
    skill would vanish while the lock file still referenced it, so store and
    lock disagreed. Instead stage the full copy in a temp dir on the same
    filesystem, then swap it in with directory renames: the existing copy stays
    untouched until the new one is complete, the failure window shrinks to two
    fast renames, and a failed swap rolls back to the original.
    """
    dest = Path(dest)
    # Staging needs to *write* next to dest, and a store that cannot be written
    # is an ordinary, fixable condition — a sandboxed shell, a synced folder, a
    # store owned by another user. It used to escape as a raw PermissionError
    # from tempfile.mkdtemp, so boost answered `boost install <skill>` with a
    # stack trace ending in a temp path nobody recognises, and filed a crash
    # report for it. Name the directory instead: that is the whole diagnosis.
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        staged = Path(tempfile.mkdtemp(dir=str(dest.parent),
                                       prefix="." + dest.name + ".tmp"))
    except PermissionError as exc:
        raise BoostError(
            "cannot write to the skill store at %s" % dest.parent,
            hint="check that you own the directory and it is writable "
                 "(`ls -ld %s`); a sandboxed shell is the usual cause"
                 % dest.parent) from exc
    except OSError as exc:
        # Not a permissions problem — disk full, read-only mount, name too
        # long. Say which, rather than describing every one of them as denied.
        raise BoostError(
            "cannot stage a copy in %s: %s"
            % (dest.parent, exc.strerror or exc),
            hint="free space or fix the mount, then re-run") from exc
    backup = None
    try:
        shutil.copytree(
            src, staged, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"))
        # is_symlink() as well as exists(): a dangling symlink is still
        # something in the way that has to be moved aside.
        if dest.exists() or dest.is_symlink():
            backup = staged.with_name(staged.name + ".old")
            os.replace(dest, backup)      # move the old copy aside (atomic)
        os.replace(staged, dest)          # swap the new copy in (atomic)
    except BaseException:
        if backup is not None and not (dest.exists() or dest.is_symlink()):
            os.replace(backup, dest)      # swap-in failed: restore the original
        shutil.rmtree(staged, ignore_errors=True)
        if backup is not None and (backup.exists() or backup.is_symlink()):
            _remove_backup(backup)
        raise
    if backup is not None:
        _remove_backup(backup)


def _remove_backup(backup: Path) -> None:
    """Delete a moved-aside copy, whatever kind of thing it is.

    ``shutil.rmtree`` on a symlink raises, and with ``ignore_errors=True`` it
    fails silently — so when the displaced ``dest`` was a symlink rather than a
    real directory, the ``.<name>.tmpXXXX.old`` staging link was left behind
    forever. Harmless-looking, but it accumulates in the user's agent dirs and
    every one of them is a dangling pointer.
    """
    if backup.is_symlink():
        backup.unlink(missing_ok=True)
    else:
        shutil.rmtree(backup, ignore_errors=True)


def declared_mcp_servers(skill_dir) -> list[dict]:
    """MCP servers an installed skill declares — ``mcpdecl.servers_for`` rows.

    Reads the installed copy's ``SKILL.md`` frontmatter and its bundled
    ``.mcp.json`` sidecar, if either is present. Best-effort by design: an
    unreadable file yields no rows rather than failing an install that has
    otherwise already succeeded.
    """
    from . import frontmatter, mcpdecl
    skill_dir = Path(skill_dir)
    meta: dict = {}
    with contextlib.suppress(OSError):
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8",
                                                  errors="replace")
        meta, _body = frontmatter.parse(text)
    sidecar = None
    with contextlib.suppress(OSError):
        sidecar = (skill_dir / mcpdecl.SIDECAR).read_text(encoding="utf-8",
                                                          errors="replace")
    return mcpdecl.servers_for(meta, sidecar)


def project_mcp_sidecar(base) -> Path:
    """The repo's ``.mcp.json`` — where a project-scoped install records servers.

    The committable file agents already read, which is the whole point of
    project scope over shelling out to ``<host> mcp add``: a registration that
    lives here is reviewable in a diff and arrives with a teammate's clone,
    where one made through a host CLI exists only on the machine that ran it.
    """
    from . import mcpdecl
    return Path(base) / mcpdecl.SIDECAR


def _load_sidecar(path: Path) -> dict | None:
    """The sidecar document, or None if absent or unreadable.

    Best-effort by design, exactly like :func:`declared_mcp_servers`: by the
    time this runs the skill is already on disk, so a corrupt ``.mcp.json`` must
    not turn a completed install into a traceback. ``merge_into`` treats a
    non-dict as empty, so a damaged file is rebuilt rather than propagated.
    """
    import json
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_sidecar(path: Path, doc: dict) -> bool:
    """Write the sidecar as indented JSON. False if it could not be written.

    Best-effort on the way OUT as well as in. ``_load_sidecar`` already refuses
    to turn a corrupt file into a traceback, but the write is the half that runs
    *after* the skill is materialized, the lock is written and the journal is
    logged — so an unwritable ``.mcp.json`` (read-only checkout, a root-owned
    file, a full disk) would crash an install that had already succeeded. The
    caller reports what was actually recorded rather than what was declared, so
    a failure here is visible instead of silent.
    """
    import json
    try:
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        return True
    except OSError:
        return False


def register_project_mcp(base, rows, skill: str) -> list[str]:
    """Record ``skill``'s declared MCP servers in the repo. Returns names added.

    Never overwrites a server already present — one the user configured by hand,
    or one another skill declared first — and never creates the file for a skill
    that declares nothing registrable, so a repo gains an ``.mcp.json`` only
    when there is genuinely something in it.
    """
    from . import mcpdecl as _decl
    if not _decl.registrable(rows):
        return []
    path = project_mcp_sidecar(base)
    doc, added = _decl.merge_into(_load_sidecar(path), rows, skill)
    if added and not _write_sidecar(path, doc):
        return []          # nothing was recorded; do not claim otherwise
    return added


def unregister_project_mcp(base, skill: str) -> list[str]:
    """Remove the servers boost recorded for ``skill``. Returns names removed.

    Marker-keyed entries only, so a hand-configured server and another skill's
    server both survive. Writes nothing when it owns nothing, which keeps an
    uninstall from rewriting — and reformatting — a file it has no claim on.
    """
    from . import mcpdecl as _decl
    path = project_mcp_sidecar(base)
    existing = _load_sidecar(path)
    if existing is None:
        return []
    doc, removed = _decl.strip_owned(existing, skill)
    if removed and not _write_sidecar(path, doc):
        return []
    return removed


def _enforce_capability_policy(name: str, source_md: Path) -> None:
    """Raise if the item's declared/detected capabilities are denied by policy.

    Runs on the item's own source Markdown (a skill's ``SKILL.md``, or a rule's
    or workflow's source file) before anything is materialized — a skill, rule
    or workflow is alike a bundle of instructions the agent will execute (a
    rule is merged into a context file read every session; a workflow becomes
    a slash command or subagent run verbatim), and least-privilege means the
    user's policy can refuse any of them for a capability they don't grant. A
    no-op unless the policy names a denied capability.
    """
    from . import frontmatter
    try:
        raw = source_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    meta, _body = frontmatter.parse(raw)
    caps = policy.check_capabilities(meta, raw)
    if caps:
        raise BoostError(
            "policy blocks installing %s: %s" % (name, "; ".join(caps)),
            hint="relax it with `boost policy` (denied_capabilities), or "
                 "install a skill that needs less")


def _resolve_base(scope: str, base) -> Path | None:
    """Directory a project-scoped install materializes under (the repo), or None
    for user scope.

    Delegates to :func:`scopes.resolve_base`, which walks up for the nearest
    project root — running this from ``src/deep/nested`` must write into the
    repo, not scatter a ``.claude/`` three directories down.
    """
    return scopes.resolve_base(scope, base)


def _require_project_base(scope: str, base, what: str) -> Path | None:
    """``_resolve_base``, but a project scope that resolves to nothing is fatal.

    ``resolve_base`` returns ``None`` for project scope in ``$HOME`` with no
    repo above it. Passing that through would quietly materialize into the
    user's own config while the CLI reported "this repo" — the two scopes
    silently becoming one place, which is the outcome the split exists to
    prevent. Refuse instead.
    """
    resolved = _resolve_base(scope, base)
    if scope == scopes.SCOPE_PROJECT and resolved is None:
        raise BoostError(
            "there is no project here to install %s into" % what,
            hint="cd into a repo, or drop --local to install for your user")
    return resolved


def _lock_location(entry: dict) -> str:
    """Describe where a rule/workflow lock ``entry`` lives, for an error message."""
    if entry.get("scope") == scopes.SCOPE_PROJECT:
        base = entry.get("base")
        return "project scope (%s)" % base if base else "project scope"
    return "user scope"


def _check_scope_conflict(name: str, existing: dict | None, scope: str,
                          resolved_base: Path | None, force: bool) -> None:
    """Refuse a name collision across install scopes before it corrupts state.

    Rule/workflow lock entries are keyed by bare name with no per-scope
    storage (unlike skills, which get their own project lock) — so a name
    already recorded under a *different* scope/base is never "the same
    install, seen twice". Letting ``force`` through in that case would
    overwrite one scope's lock entry with the other's, orphaning the first
    scope's materializations with nothing left in the lock to uninstall them.
    Refuse the cross-scope case outright, ``force`` or not; only a same-scope,
    same-base match falls through to the ordinary already-installed check.
    """
    if not existing:
        return
    requested_base = str(resolved_base) if resolved_base is not None else None
    if existing.get("scope", "user") == scope and existing.get("base") == requested_base:
        if not force:
            raise BoostError("%s is already installed" % name,
                            hint="`boost reinstall %s` to force" % name)
        return
    raise BoostError(
        "%s is already installed at %s" % (name, _lock_location(existing)),
        hint="uninstall it there first — a different scope cannot force-overwrite it")


def _require_writable(name: str) -> None:
    """Refuse an install before its first write if its record cannot be kept.

    The lock file lives in the store, so an install that cannot write there
    can copy a skill, link it, or merge a rule into ``~/.claude/CLAUDE.md``
    and then fail at the record: files on disk that `boost uninstall` and
    `boost sync` never see. Asking first costs one ``access`` call, and names
    the directory to fix rather than a temp path deep in a traceback.

    The store only. An agent dir that refuses is that agent's problem: the
    install skips it and records the skip (:func:`link_agents`,
    :func:`_refused_target`), so the agents that can be written are, and
    `boost sync` writes the rest once the dir allows it.
    """
    d = paths.store_dir()
    block = paths.refuses_writes(d)
    if block is not None:
        raise BoostError("cannot install %s: %s"
                         % (name, paths.not_writable(d, block)),
                         hint="%s, then re-run" % paths.write_remedy(block))


def _refuse_self_installing(entry: dict) -> None:
    """Refuse to half-copy an item whose repo installs itself.

    Checked before the kind dispatch because the property belongs to the repo,
    not the item: every kind it ships has the same missing build step. Naming
    the upstream command is the whole point — a refusal that only says "no"
    leaves the user exactly where `boost install` pretending would have.
    """
    cmd = config.self_installing_command(entry.get("tap") or "")
    if not cmd:
        return
    raise BoostError(
        "%s comes from %s, which installs itself — boost would copy its "
        "Markdown and leave a skill that cannot run"
        % (entry.get("name", "?"), entry.get("tap", "?")),
        hint="run the registry's own installer: %s" % cmd)


def install(entry: dict, force: bool = False,
            only_agents: list[str] | None = None,
            scope: str = "user", base=None,
            via: str | None = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict.

    ``scope`` is ``"user"`` (default — the canonical store, symlinked into the
    agent's user config dirs) or ``"project"`` (real directories inside the
    current repo). Every kind honors it.

    ``via`` names the caller for the journal entry (e.g. ``"protocol"`` for a
    one-click install), the same way a tap's journal entry already can — see
    ``registry.add``'s ``via=`` kwarg to ``journal.log``. ``None`` means an
    ordinary ``boost install``, and is dropped from the event like any other
    ``None``-valued field (``journal.log``).
    """
    scopes.check_scope(scope)
    _refuse_self_installing(entry)
    kind = entry.get("kind", "skill")
    if kind == "rule":
        return _install_rule(entry, force=force, only_agents=only_agents,
                             scope=scope, base=base, via=via)
    if kind == "workflow":
        return _install_workflow(entry, force=force, only_agents=only_agents,
                                 scope=scope, base=base, via=via)
    if kind != "skill":
        raise BoostError(
            "%s is a %s, which boost does not know how to install" % (entry["name"], kind),
            hint="known kinds: skill, rule, workflow")
    if scope == scopes.SCOPE_PROJECT:
        return _install_project_skill(entry, force=force, only_agents=only_agents,
                                      base=base, via=via)
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" % (name, existing.get("version")),
                        hint="`boost reinstall %s` to force, `boost update` to upgrade" % name)

    violations = policy.check_install(entry, len(lockfile.installed()))
    if violations:
        raise BoostError("policy blocks installing %s: %s" % (name, "; ".join(violations)),
                        hint="inspect with `boost policy list`")

    src = source_dir_for(entry)
    _enforce_capability_policy(name, src / "SKILL.md")
    dest = skill_store_dir(name)
    _require_writable(name)
    _copy_skill(src, dest)

    res = link_agents(name, only=preserved_agent_scope(only_agents, existing))
    res.upgraded = existing is not None
    res.score, _ = util.score_skill(dest)
    res.mcp_servers = declared_mcp_servers(dest)

    tap = registry.get(entry["tap"])
    from . import gitutil
    now = util.now_iso()
    lockfile.set_skill(name, {
        "version": entry.get("version", "0.0.0"),
        "tap": entry["tap"],
        "source_dir": entry.get("rel_dir", "."),
        "commit": gitutil.head_commit(tap.path),
        "sha256": util.sha256_dir(dest),
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        # `agents` is what IS linked; `only_agents` is what the user ASKED for.
        # sync needs the second: it links a skill into every enabled agent, and
        # without a record of the request it cannot tell a deliberate `--agent`
        # narrowing from a skill that simply predates a newly enabled agent.
        #
        # Read back off disk rather than taken from `res.linked`, which is only
        # what THIS run linked. A narrowing re-install (`--agent cursor
        # --force`) links cursor and *skips* the others without unlinking them,
        # so recording res.linked made `agents` describe the request while the
        # other symlinks lived on — a divergence no boost command could see.
        "agents": linked_agents(name),
        "only_agents": declared_agent_scope(only_agents, existing),
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"), via=via)
    return res


def _install_project_skill(entry: dict, force: bool = False,
                           only_agents: list[str] | None = None,
                           base=None, via: str | None = None) -> InstallResult:
    """Materialize a skill into the repo itself, once per enabled agent.

    Unlike a user install there is no canonical store and no symlink. Each agent
    gets a real copy at ``<repo>/.claude/skills/<name>`` so the tree can be
    committed and a teammate's ``git clone`` brings the skill with it — a
    symlink pointing into *this* machine's ``~/.agents/skills`` would arrive
    dangling. The cost is duplication across agent dirs, which is the right
    trade: repos are cheap, and a checked-in file that only works on the author's
    laptop is worse than no file at all.

    The record goes in the project's own lock, never the user's.
    """
    from . import gitutil
    name = entry["name"]
    resolved_base = _require_project_base(scopes.SCOPE_PROJECT, base, name)
    if resolved_base is None:             # _require_project_base already raised
        raise BoostError("there is no project here to install %s into" % name)

    existing = projectlock.get_skill(resolved_base, name)
    if existing and not force:
        raise BoostError(
            "%s is already installed in this project (v%s)"
            % (name, existing.get("version")),
            hint="`boost reinstall %s --local` to force" % name)

    violations = policy.check_install(entry, len(projectlock.installed(resolved_base)))
    if violations:
        raise BoostError("policy blocks installing %s: %s" % (name, "; ".join(violations)),
                        hint="inspect with `boost policy list`")

    src = source_dir_for(entry)
    _enforce_capability_policy(name, src / "SKILL.md")
    only_agents = preserved_agent_scope(only_agents, existing)
    # agents_for_scope, not enabled_agents: project scope derives a repo-local
    # dotdir from the agent's own, which holds for every agent whose skills dir
    # sits one level under it. Antigravity's sits two, so it is excluded rather
    # than given an invented `<repo>/antigravity-cli/`.
    targets = [(agent, scopes.skill_target(skills_dir, name, base=resolved_base))
               for agent, skills_dir in agents.agents_for_scope(resolved_base).items()
               if not only_agents or agent in only_agents]

    # Refuse to write through a symlink that leaves the repo. An agent dir like
    # ``.claude/skills`` is committed, so a hostile clone can ship it as a
    # symlink to ``~/.ssh`` and the copy below would land on the far side.
    # Checked for every target up front — before existence, force, or any write
    # — so a single escaping dir aborts the whole install rather than writing
    # part of it outside the project first.
    for _agent, dest in targets:
        scopes.ensure_in_base(resolved_base, dest)

    # Refuse to clobber a directory boost did not put there. In user scope the
    # store is boost's alone, but here the destination is inside someone's repo
    # — a same-named hand-written skill is a real possibility, and overwriting
    # it would destroy uncommitted work with no warning.
    if not existing:
        squatters = [str(d) for _agent, d in targets if d.exists()]
        if squatters and not force:
            raise BoostError(
                "%s already exists in this project and boost did not install it: %s"
                % (name, ", ".join(sorted(squatters))),
                hint="move it aside, or `boost install %s --local --force` to "
                     "overwrite it" % name)

    materializations: list[dict] = []
    linked: list[str] = []
    first: Path | None = None
    for agent, dest in targets:
        _copy_skill(src, dest)
        # Relative, because this record is committed and read on machines where
        # the absolute path does not exist.
        materializations.append(
            {"agent": agent, "path": scopes.relative_to_base(resolved_base, dest)})
        linked.append(agent)
        if first is None:
            first = dest

    if first is None:
        raise BoostError("no enabled agents to install %s into" % name,
                        hint="enable one with `boost config`")

    # A filtered reinstall (`--force --agent cursor`) refreshes only the agents
    # it names. Carrying the untouched ones forward keeps the lock describing
    # everything that is actually on disk — dropping them would leave real
    # directories in the repo that no record claims, so uninstall would skip
    # them and sync would call them orphans.
    kept = _untouched_materializations(existing, linked)
    materializations.extend(kept)
    all_agents = linked + [m["agent"] for m in kept if m.get("agent")]

    now = util.now_iso()
    tap = registry.get(entry["tap"])
    projectlock.set_skill(resolved_base, name, {
        "kind": "skill",
        "version": entry.get("version", "0.0.0"),
        "tap": entry["tap"],
        "source_dir": entry.get("rel_dir", "."),
        "commit": gitutil.head_commit(tap.path),
        "sha256": util.sha256_dir(first),
        "scope": scopes.SCOPE_PROJECT,
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        "agents": all_agents,
        "materializations": materializations,
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"),
                scope=scopes.SCOPE_PROJECT, via=via)

    res = InstallResult(name=name, dest=first, kind="skill")
    res.linked = linked
    res.upgraded = existing is not None
    res.scope = scopes.SCOPE_PROJECT
    res.score, _ = util.score_skill(first)
    res.mcp_servers = declared_mcp_servers(first)
    # Project scope registers into the repo's own .mcp.json rather than leaving
    # it to the command layer's `<host> mcp add` offer, which is user-scoped and
    # would put a machine-wide registration behind a --scope project install.
    # Recorded here so it lands with the skill and reverses with it.
    res.mcp_recorded = register_project_mcp(resolved_base, res.mcp_servers, name)
    return res


def uninstall_project(name: str, base=None) -> dict:
    """Remove a project-scoped skill: its per-agent copies and its lock entry.

    Every recorded path is re-derived and checked to sit inside the project
    before it is deleted (:func:`scopes.contains`) — the lock is a committed file
    anyone with merge rights can edit, so a path out of it is input, not truth.
    """
    resolved_base = _resolve_base(scopes.SCOPE_PROJECT, base)
    entry = projectlock.get_skill(resolved_base, name) if resolved_base else None
    if not entry:
        raise BoostError("%s is not installed in this project" % name,
                        hint="see what is with `boost list --local`")
    removed: list[str] = []
    for m in entry.get("materializations") or []:
        path = scopes.resolve_in_base(resolved_base, m.get("path"))
        if path is None or not path.is_dir():
            continue          # refused or already gone — nothing was removed
        util.rmtree(path)
        if m.get("agent"):
            removed.append(m["agent"])
    projectlock.remove_skill(resolved_base, name)
    # Reverse exactly what the install recorded. Marker-keyed entries only, so a
    # server the user configured by hand — or one another skill still needs —
    # survives. Without this a skill tried once keeps launching its server for
    # every project that clones the repo.
    unregistered = unregister_project_mcp(resolved_base, name)
    journal.log("uninstall", name, scope=scopes.SCOPE_PROJECT)
    return {"name": name, "unlinked": removed, "entry": entry,
            "mcp_unregistered": unregistered, "kind": "skill",
            "scope": scopes.SCOPE_PROJECT, "base": str(resolved_base)}


def project_sync_plan(base=None) -> dict[str, list]:
    """Compare the project lock against what is actually on disk.

    Returns ``{missing, orphaned}``: lock entries whose directory is gone, and
    skill directories under the project's agent dirs that no lock entry claims.
    A teammate who clones the repo has the files but may be missing one an
    ``update`` added, so this is the repair list for a shared checkout.
    """
    plan: dict[str, list] = {"missing": [], "orphaned": []}
    resolved_base = _resolve_base(scopes.SCOPE_PROJECT, base)
    # No lock file means this directory does not use project scope at all. Bail
    # before the orphan scan, or every repo with a hand-written
    # ``.claude/skills/`` would be told it has "unclaimed" directories and
    # `boost sync` could never report a clean tree.
    if resolved_base is None or not projectlock.exists(resolved_base):
        return plan
    lock = projectlock.installed(resolved_base)
    for name, entry in lock.items():
        for m in entry.get("materializations") or []:
            path = scopes.resolve_in_base(resolved_base, m.get("path"))
            if path is None or not path.is_dir():
                plan["missing"].append((name, m.get("agent", "?")))
    for skills_dir in agents.enabled_agents().values():
        root = scopes.agent_root(skills_dir, resolved_base) / Path(skills_dir).name
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if child.is_dir() and child.name not in lock:
                plan["orphaned"].append(str(child))
    return plan


def project_sync_apply(plan: dict[str, list], base=None) -> list[str]:
    """Re-materialize the project skills :func:`project_sync_plan` found missing.

    Orphans are reported but never deleted: an unclaimed directory in someone's
    repo is far more likely to be a hand-written skill than boost's litter, and
    a package manager that silently removes files it did not write is one nobody
    should run in their working tree.
    """
    actions: list[str] = []
    resolved_base = _resolve_base(scopes.SCOPE_PROJECT, base)
    if resolved_base is None:
        return actions
    # Group by skill, but keep WHICH agents are missing: these directories are
    # committed files a team edits in place, so repairing one agent must not
    # re-copy over the others. Re-installing the whole skill would silently
    # revert a teammate's edit to a file they had checked in.
    wanted: dict[str, list] = {}
    for name, agent in plan.get("missing", []):
        wanted.setdefault(name, []).append(agent)
    for name in sorted(wanted):
        entry = projectlock.get_skill(resolved_base, name) or {}
        tap_name = entry.get("tap")
        if tap_name and tap_name != "local":
            try:  # noqa: FURB107 - per-item resilience in a loop (see PERF203)
                from . import catalog
                matches = [e for e in catalog.find(name)
                           if e["tap"] == tap_name and e.get("kind", "skill") == "skill"]
                cat_entry, warning = catalog.select_lock_source(matches, entry)
                if warning:
                    actions.append(warning)
                if cat_entry:
                    install(cat_entry, force=True, scope=scopes.SCOPE_PROJECT,
                            base=resolved_base, only_agents=wanted[name])
                    actions.append("re-materialized %s from %s" % (name, tap_name))
                    continue
            except BoostError:
                pass
        actions.append("%s is missing from the project but its source is gone — "
                       "run `boost update` or reinstall" % name)
    if actions:
        journal.log("sync", "%d project fixes" % len(actions))
    return actions


def _install_rule(entry: dict, force: bool = False,
                  only_agents: list[str] | None = None,
                  scope: str = "user", base=None,
                  via: str | None = None) -> InstallResult:
    """Materialize a rule into each enabled agent's native format.

    Cursor/Windsurf/Cline get a verbatim file drop in their ``rules/`` dir
    (frontmatter preserved — it is native rule metadata); Claude Code has no
    rules folder, so the rule merges into ``CLAUDE.md`` as an idempotent managed
    block. With ``scope="project"`` these land under the repo (and Claude uses
    ``CLAUDE.local.md``). Every materialization is recorded so ``uninstall``
    reverses exactly what was written.
    """
    import hashlib

    from . import frontmatter, gitutil, rules
    name = entry["name"]
    # Cheap precondition, checked before any tap or filesystem work: if there
    # is nowhere to put this, say so immediately. Also needed ahead of the
    # existing-install check below, which compares against this scope/base.
    resolved_base = _require_project_base(scope, base, "rule %s" % name)
    existing = lockfile.get_rule(name)
    _check_scope_conflict(name, existing, scope, resolved_base, force)
    only_agents = preserved_agent_scope(only_agents, existing)

    violations = policy.check_install(entry, len(lockfile.installed()))
    if violations:
        raise BoostError("policy blocks installing %s: %s" % (name, "; ".join(violations)),
                        hint="inspect with `boost policy list`")

    tap = registry.get(entry["tap"])
    src = tap.path / entry.get("skill_md", "")
    if not src.is_file():
        raise BoostError("source for rule %s vanished from tap %s" % (name, tap.name),
                        hint="run `boost update %s`" % tap.name)
    _enforce_capability_policy(name, src)
    raw = src.read_text(encoding="utf-8", errors="replace")
    meta, body = frontmatter.parse(raw)
    claude_body = rules.render_claude_body(str(meta.get("name") or name), body)

    # The lock is what makes any write below undoable, so a store that
    # refuses it stops the install before the first one. A target dir that
    # refuses is that agent's problem only: it is skipped and recorded.
    _require_writable(name)
    materializations: list[dict] = []
    linked: list[str] = []
    unwritable: list[str] = []
    blocked: list[tuple[str, str]] = []
    refused: list[dict] = []
    for agent, skills_dir in agents.materializing_agents(resolved_base).items():
        if only_agents and agent not in only_agents:
            continue
        mode, path = rules.rule_target(agent, skills_dir, name, base=resolved_base)
        # Project scope writes into the repo, so a committed agent dir could be
        # a symlink escaping it (see scopes.ensure_in_base). User scope writes
        # into the user's own ~/.claude, which they control — nothing to guard.
        if resolved_base is not None:
            scopes.ensure_in_base(resolved_base, path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if mode == rules.MODE_CLAUDE:
                current = path.read_text(encoding="utf-8") if path.exists() else ""
                util.atomic_write_text(path, rules.merge_block(current, name, claude_body))
                # Hash what `rules.read_block` will read back (the stripped
                # body), so `boost verify` can tell an edited block from ours.
                written = claude_body.strip("\n")
            else:
                util.atomic_write_text(path, raw)
                written = raw
        except OSError as err:
            if not _refused_target(err, path, unwritable, blocked):
                raise
            refused.append({"agent": agent, "mode": mode, "path": str(path),
                            "unwritable": True})
            continue
        materializations.append({
            "agent": agent, "mode": mode, "path": str(path),
            "sha256": hashlib.sha256(written.encode("utf-8")).hexdigest()})
        linked.append(agent)

    # Carry forward the agents this run did not touch — the same reason the
    # project-scope skill path does it, but the stakes are higher here. A
    # rule's materialization is a managed block inside a file the user reads
    # every session (~/.claude/CLAUDE.md); dropping the record does not drop
    # the block, and `_uninstall_rule` is record-driven, so an unrecorded block
    # could never be removed by any boost command again.
    materializations.extend(_refused_materializations(existing, linked, refused))

    now = util.now_iso()
    lockfile.set_rule(name, {
        "kind": "rule",
        "version": entry.get("version", "0.0.0"),
        "tap": entry["tap"],
        "source_file": entry.get("skill_md", ""),
        "commit": gitutil.head_commit(tap.path),
        "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "scope": scope,
        "base": str(resolved_base) if resolved_base is not None else None,
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        # Same governance contract as a skill entry: a pin survives a forced
        # reinstall, quarantine does not — the reinstall just re-materialized
        # the content, so a surviving flag would be a lie.
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "materializations": materializations,
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"), via=via)

    res = InstallResult(
        name=name,
        dest=Path(materializations[0]["path"]) if materializations else paths.store_dir(),
        kind="rule", scan_text=raw)
    res.linked = linked
    res.unwritable = unwritable
    res.blocked = blocked
    res.upgraded = existing is not None
    res.scope = scope
    return res


def _removal_refused(name: str, path: Path) -> BoostError:
    """The named refusal for a removal under ``path`` that its dir forbids."""
    where = paths.tilde(str(refusing_dir(path.parent)))
    return BoostError("cannot uninstall %s: %s is not writable" % (name, where),
                      hint="`chmod u+w %s`, then uninstall again" % where)


@contextlib.contextmanager
def _refused_removal(name: str, path: Path):
    """Turn a locked agent dir into a named refusal, before the lock is touched.

    Uninstall removes what the lock records and then drops the record. A dir
    that refuses the removal used to escape as exit 70; raising here keeps
    the record, so running uninstall again after the `chmod` finishes it.
    """
    try:
        yield
    except PermissionError:
        raise _removal_refused(name, path) from None


def _remove_all_or_nothing(name: str, plan: list[tuple[Path, str]]) -> None:
    """Apply an uninstall's removals, or none of them.

    ``plan`` holds ``(path, new_text)`` for each file to change: ``""`` to
    delete it, other text to rewrite it. Every dir is checked before the
    first change, because a refusal part-way left some agents' files gone and
    the lock still naming them, so a `boost sync` in between wrote them back.
    The per-file guard stays, for what ``os.access`` cannot foresee.

    Two rows can name one file (two enabled agents whose dirs resolve to one
    path), so the plan is de-duplicated on the resolved dir, not the resolved
    file, and a file already gone counts as removed.
    """
    once: dict[Path, tuple[Path, str]] = {}
    for path, text in plan:
        once.setdefault(path.parent.resolve() / path.name, (path, text))
    for path, _text in once.values():
        if not os.access(str(path.parent), os.W_OK):
            raise _removal_refused(name, path)
    for path, text in once.values():
        with _refused_removal(name, path):
            if text:
                util.atomic_write_text(path, text)
            else:
                path.unlink(missing_ok=True)


def _present(path: Path) -> bool:
    """Whether a recorded file is there to remove, asked the same way on every
    Python.

    ``os.lstat`` raises PermissionError under a parent with no search bit, and
    the caller's :func:`_refused_removal` turns that into a named refusal.
    ``Path.exists`` and ``is_file`` raise there on 3.12 and 3.13 but answer
    False on 3.14, where uninstall then planned nothing, dropped the lock row
    and reported success over a file it never removed. A directory at the path
    is not a file boost wrote, so it is not one to remove.
    """
    try:
        st = os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return False
    return not stat.S_ISDIR(st.st_mode)


def _uninstall_rule(name: str, rule: dict) -> dict:
    """Reverse every materialization recorded for an installed rule."""
    from . import rules
    removed: list[str] = []
    plan: list[tuple[Path, str]] = []
    for m in rule.get("materializations", []):
        path = Path(m.get("path", ""))
        with _refused_removal(name, path):
            if m.get("mode") == rules.MODE_CLAUDE:
                if _present(path) and path.exists():
                    text = path.read_text(encoding="utf-8")
                    stripped = rules.strip_block(text, name)
                    # No block of ours (a refused write): no rewrite. An
                    # empty result held only our block: boost created it.
                    if stripped != text:
                        plan.append((path, stripped))
            elif _present(path):
                plan.append((path, ""))
        if m.get("agent"):
            removed.append(m["agent"])
    _remove_all_or_nothing(name, plan)
    lockfile.remove_rule(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed, "entry": rule, "kind": "rule"}


def quarantine_materialized(kind: str, name: str, entry: dict) -> list[str]:
    """Remove every recorded materialization of a rule/workflow, stashing it.

    The counterpart of skill quarantine's "store intact, links removed". These
    kinds have no store copy — the materialization IS the only artifact — so
    what gets removed is stashed on the lock entry and
    :func:`release_materialized` restores it byte-for-byte. Restoring from the
    stash rather than the tap matters: the tap may have moved (or vanished)
    since, and a release must never be a covert update.

    Persists the entry (``quarantined`` + ``quarantine_stash``) and returns the
    agents whose artifacts were removed.
    """
    from . import rules
    # Prior stash contents win over a fresh None: re-running after an
    # interrupted quarantine must never overwrite a saved copy with "the
    # artifact was already gone".
    prior = {m.get("path"): m.get("content")
             for m in entry.get("quarantine_stash") or []}
    prior_full_text = {m.get("path"): m.get("full_text")
                       for m in entry.get("quarantine_stash") or []}
    stash: list[dict] = []
    affected: list[str] = []
    for m in entry.get("materializations") or []:
        path = Path(m.get("path", ""))
        content: str | None = None
        full_text: str | None = None
        if m.get("mode") == rules.MODE_CLAUDE:
            if path.exists():
                # The whole file, not just the block: release_materialized
                # needs it to restore the block at its original position
                # rather than re-appending at end-of-file.
                full_text = path.read_text(encoding="utf-8")
                content = rules.read_block(full_text, name)
        elif path.is_file():
            content = path.read_text(encoding="utf-8")
        if content is None:
            content = prior.get(m.get("path"))
        if full_text is None:
            full_text = prior_full_text.get(m.get("path"))
        stash.append({**m, "content": content, "full_text": full_text})
        if m.get("agent"):
            affected.append(m["agent"])
    # Persist the stash BEFORE removing anything. A crash mid-removal then
    # leaves a lock that already says quarantined-with-stash — release still
    # restores, and re-running quarantine finishes the removal. The reverse
    # order could remove an artifact whose only copy died with the crash.
    entry["quarantined"] = True
    entry["quarantine_stash"] = stash
    lockfile.set_entry(kind, name, entry)
    for m in entry.get("materializations") or []:
        path = Path(m.get("path", ""))
        if m.get("mode") == rules.MODE_CLAUDE:
            if path.exists():
                text = path.read_text(encoding="utf-8")
                if rules.read_block(text, name) is not None:
                    stripped = rules.strip_block(text, name)
                    if stripped:
                        util.atomic_write_text(path, stripped)
                    else:
                        path.unlink()  # file held only our block
        elif path.is_file():
            path.unlink()
    journal.log("quarantine", name)
    return affected


def stale_quarantine_artifacts(name: str, entry: dict) -> bool:
    """True when a quarantined rule/workflow still has artifacts on disk.

    That is the signature of an interrupted quarantine (the stash persisted,
    the removal pass did not finish) — re-running
    :func:`quarantine_materialized` completes it without touching the stash.
    """
    from . import rules
    for m in entry.get("materializations") or []:
        p = Path(m.get("path", ""))
        if m.get("mode") == rules.MODE_CLAUDE:
            try:
                if p.exists() and rules.read_block(
                        p.read_text(encoding="utf-8"), name) is not None:
                    return True
            except OSError:
                continue
        elif p.is_file():
            return True
    return False


def release_materialized(kind: str, name: str, entry: dict) -> list[str]:
    """Restore what :func:`quarantine_materialized` removed, byte-for-byte.

    A stash record whose ``content`` is None (the artifact was already gone at
    quarantine time) is skipped — there is nothing truthful to restore.
    Persists the entry and returns the agents restored.
    """
    from . import rules
    restored: list[str] = []
    for m in entry.get("quarantine_stash") or []:
        content = m.get("content")
        if content is None:
            continue
        path = Path(m.get("path", ""))
        path.parent.mkdir(parents=True, exist_ok=True)
        if m.get("mode") == rules.MODE_CLAUDE:
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            full_text = m.get("full_text")
            # Byte-for-byte only holds when the surrounding text is exactly
            # what quarantine left behind — write the stashed file back
            # whole, restoring the block at its original position instead of
            # re-appending it. Any other surrounding text (the user edited
            # the file, or the stash predates this field) falls back to
            # merge_block's append.
            if full_text is not None and rules.strip_block(full_text, name) == current:
                util.atomic_write_text(path, full_text)
            else:
                util.atomic_write_text(path, rules.merge_block(current, name, content))
        else:
            util.atomic_write_text(path, content)
        if m.get("agent"):
            restored.append(m["agent"])
    entry["quarantined"] = False
    entry.pop("quarantine_stash", None)
    lockfile.set_entry(kind, name, entry)
    journal.log("release", name)
    return restored


def _install_workflow(entry: dict, force: bool = False,
                      only_agents: list[str] | None = None,
                      scope: str = "user", base=None,
                      via: str | None = None) -> InstallResult:
    """Materialize a workflow (slash command / subagent) into each enabled agent.

    A verbatim Markdown drop into the agent's ``commands/`` or ``agents/`` dir —
    the slot derived from the source path — with no transformation. With
    ``scope="project"`` the drop lands under the repo (``<repo>/.claude/…``).
    Every drop is recorded so ``uninstall`` removes exactly the files it wrote.
    """
    import hashlib

    from . import gitutil, workflows
    name = entry["name"]
    resolved_base = _require_project_base(scope, base, "workflow %s" % name)
    existing = lockfile.get_workflow(name)
    _check_scope_conflict(name, existing, scope, resolved_base, force)
    only_agents = preserved_agent_scope(only_agents, existing)

    violations = policy.check_install(entry, len(lockfile.installed()))
    if violations:
        raise BoostError("policy blocks installing %s: %s" % (name, "; ".join(violations)),
                        hint="inspect with `boost policy list`")

    tap = registry.get(entry["tap"])
    source_rel = entry.get("skill_md", "")
    src = tap.path / source_rel
    if not src.is_file():
        raise BoostError("source for workflow %s vanished from tap %s" % (name, tap.name),
                        hint="run `boost update %s`" % tap.name)
    _enforce_capability_policy(name, src)
    raw = src.read_text(encoding="utf-8", errors="replace")
    slot = workflows.detect_slot(source_rel)

    # As for rules: the store refuses the whole install, a target dir only
    # its own agent.
    _require_writable(name)
    materializations: list[dict] = []
    linked: list[str] = []
    unwritable: list[str] = []
    blocked: list[tuple[str, str]] = []
    refused: list[dict] = []
    for agent, skills_dir in agents.materializing_agents(resolved_base).items():
        if only_agents and agent not in only_agents:
            continue
        path = workflows.workflow_target(skills_dir, slot, name,
                                         base=resolved_base, agent=agent)
        # Project scope writes into the repo; a committed agent dir could be a
        # symlink escaping it (see scopes.ensure_in_base). User scope writes into
        # the user's own ~/.claude, which they control — nothing to guard.
        if resolved_base is not None:
            scopes.ensure_in_base(resolved_base, path)
        rendered = workflows.render(agent, slot, name, raw)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            util.atomic_write_text(path, rendered)
        except OSError as err:
            if not _refused_target(err, path, unwritable, blocked):
                raise
            refused.append({"agent": agent, "slot": slot, "path": str(path),
                            "unwritable": True})
            continue
        materializations.append({
            "agent": agent, "slot": slot, "path": str(path),
            "sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest()})
        linked.append(agent)

    # As for rules: an unrecorded materialization is a live slash command that
    # `_uninstall_workflow` — driven by this list — can never remove.
    materializations.extend(_refused_materializations(existing, linked, refused))

    now = util.now_iso()
    lockfile.set_workflow(name, {
        "kind": "workflow",
        "slot": slot,
        "version": entry.get("version", "0.0.0"),
        "tap": entry["tap"],
        "source_file": source_rel,
        "commit": gitutil.head_commit(tap.path),
        "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "scope": scope,
        "base": str(resolved_base) if resolved_base is not None else None,
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        # Same governance contract as a skill entry: a pin survives a forced
        # reinstall, quarantine does not.
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "materializations": materializations,
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"), via=via)

    res = InstallResult(
        name=name,
        dest=Path(materializations[0]["path"]) if materializations else paths.store_dir(),
        kind="workflow", scan_text=raw)
    res.linked = linked
    res.unwritable = unwritable
    res.blocked = blocked
    res.upgraded = existing is not None
    res.scope = scope
    return res


def _uninstall_workflow(name: str, workflow: dict) -> dict:
    """Remove every file dropped for an installed workflow."""
    removed: list[str] = []
    plan: list[tuple[Path, str]] = []
    for m in workflow.get("materializations", []):
        path = Path(m.get("path", ""))
        with _refused_removal(name, path):
            if _present(path):
                plan.append((path, ""))
        if m.get("agent"):
            removed.append(m["agent"])
    _remove_all_or_nothing(name, plan)
    lockfile.remove_workflow(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed, "entry": workflow, "kind": "workflow"}


def install_from_path(src_dir: Path, name: str | None = None,
                      tap_label: str = "local",
                      only_agents: list[str] | None = None,
                      force: bool = False,
                      remote: RemoteSource | None = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`).

    ``remote`` names the clone ``src_dir`` sits in when the import came from a
    URL: the lock then records the URL, the commit and the path inside the
    repo, never the temporary clone. Without it the directory is recorded
    absolute, so a relative ``boost import ./x`` can be reinstalled from
    anywhere rather than only from the directory it was imported in.

    Enforces the same pin, policy and capability gates as ``install``. It used
    to enforce none of them, so every local path in — ``import``, ``create
    --install``, ``distill/infer/absorb --install`` — was a way
    around a blocklist, ``pin_only``, ``max_skills`` and ``denied_capabilities``.

    Deliberately *not* adopted from ``install``: its "already installed" refusal.
    This is the re-import path (``boost reinstall`` on a local skill), so that
    gate would break the function's main use.
    """
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding="utf-8", errors="replace"))
    name = name or str(meta.get("name") or src_dir.name)
    existing = lockfile.get_skill(name)
    # Refuse before `dest` is touched, so a rejected install leaves nothing
    # half-copied over an existing skill.
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    violations = policy.check_install(
        {"name": name, "tap": tap_label,
         "version": str(meta.get("version") or "0.0.0"),
         "description": meta.get("description")},
        # Re-importing a skill that is already counted must not trip max_skills.
        len(lockfile.installed()) - (1 if existing else 0))
    if violations:
        raise BoostError("policy blocks installing %s: %s" % (name, "; ".join(violations)),
                        hint="inspect with `boost policy list`")
    _enforce_capability_policy(name, src_dir / "SKILL.md")
    dest = skill_store_dir(name)
    _require_writable(name)
    _copy_skill(src_dir, dest)
    res = link_agents(name, only=preserved_agent_scope(only_agents, existing))
    res.score, _ = util.score_skill(dest)
    res.mcp_servers = declared_mcp_servers(dest)
    prior_tap = (existing or {}).get("tap")
    res.replaced_tap = prior_tap if prior_tap != tap_label else None
    linked = linked_agents(name)
    declared = declared_agent_scope(only_agents, existing)
    if declared:
        res.out_of_scope = [a for a in linked if a not in declared]
    now = util.now_iso()
    lockfile.set_skill(name, {
        "version": str(meta.get("version") or "0.0.0"),
        "tap": tap_label,
        "source_dir": (repo_path(remote, src_dir) if remote
                       else str(src_dir.absolute())),
        "source_url": remote.url if remote else "",
        "commit": remote.commit if remote else "",
        "sha256": util.sha256_dir(dest),
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        # Was hardcoded False, which did not merely skip the pin check — a
        # re-import silently CLEARED an existing pin. install() preserves it.
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        # What is on disk, not what this run linked — see install().
        "agents": linked,
        # `boost import --agent ...` narrows the same way `install` does, so it
        # has to record the same declaration — otherwise the links are narrow
        # but sync sees no scope and widens them right back.
        "only_agents": declared,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=remote.url if remote else str(src_dir))
    return res


def existing_skill_owner(name: str) -> str | None:
    """Tap label of the skill already installed as ``name``, else None.

    For the generated-install paths (``create``/``distill``/``infer``/``absorb``
    ``--install``) to warn before silently replacing an *unpinned* install and
    flipping its lock provenance to ``local`` — the loss ``list`` would
    otherwise never show. ``install_from_path``'s own gate only refuses a
    *pinned* name (its docstring: that refusal is deliberately not extended to
    the unpinned case, since this is also the re-import path for ``boost
    import`` / ``boost reinstall``). Callers that generate a brand-new skill,
    rather than re-importing an existing one, use this to catch that gap
    themselves.
    """
    existing = lockfile.get_skill(name)
    return existing.get("tap") if existing else None


def uninstall(name: str) -> dict:
    """Uninstall ``name`` whatever its kind (skill, rule, workflow).

    Reverses everything the install wrote and drops the lock entry;
    returns {name, unlinked, entry, kind}. Raises BoostError if not installed.
    The ``kind`` is what tells a caller like ``cmd_uninstall`` whether
    ``unlinked`` names agent *symlinks* (skill) or agent *materializations*
    (rule/workflow) — those are removed from entirely different places, and a
    caller that assumes "skill" for all three narrates a store directory that
    a rule or workflow never had.
    """
    entry = lockfile.get_skill(name)
    if not entry:
        rule = lockfile.get_rule(name)
        if rule:
            return _uninstall_rule(name, rule)
        workflow = lockfile.get_workflow(name)
        if workflow:
            return _uninstall_workflow(name, workflow)
        # Nothing at user scope — but the caller may be standing in a repo that
        # has it installed locally, and "X is not installed" would be a plain
        # falsehood there. Only ever acts on a name the project lock records.
        pbase = scopes.project_root()
        if pbase is not None and projectlock.get_skill(pbase, name):
            return uninstall_project(name, base=pbase)
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        util.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry, "kind": "skill"}


def strip_extended_prefix(text: str) -> str:
    """Drop Windows' ``\\\\?\\`` extended-length prefix from a raw path string.

    Since 3.8, `os.readlink()` on Windows returns the reparse point's
    substitution path, which typically carries that prefix — so boost's own
    link into the store reads back as
    ``\\\\?\\C:\\Users\\...\\.agents\\skills\\x``. Compared by path components
    that is a *different drive* from ``C:\\Users\\...``, and every Windows leg
    of the matrix went red on exactly this. The check it replaced was a
    substring test, which the prefix sailed straight through; comparing
    properly is what exposed it.
    """
    if text.startswith("\\\\?\\UNC\\"):
        return "\\\\" + text[len("\\\\?\\UNC\\"):]
    if text.startswith("\\\\?\\"):
        return text[len("\\\\?\\"):]
    return text


def normalize_link_target(path: Path) -> str:
    """A comparable string form of a `readlink()` result.

    Normalizes separators and case as well as the prefix: Windows paths
    compare case-insensitively, and POSIX `normcase` is a no-op.
    """
    return os.path.normcase(os.path.normpath(strip_extended_prefix(str(path))))


def points_into_store(link: Path) -> bool:
    """True if `link`'s target lands inside boost's canonical store.

    Reads the raw `readlink()` target rather than `resolve()`, because the
    links this has to judge are usually broken — `resolve()` cannot tell us
    where a dangling link was aiming. A relative target is resolved against
    the link's own directory, and containment is decided by `commonpath`
    (the same guard `scopes.contains` uses): a substring test on the store
    path also matches siblings like `~/.agents/skills-backup`, which boost
    does not own either.

    Everything boost deletes under an agent's skills dir is gated on this.
    A user's own broken symlink sitting in `~/.claude/skills` is not ours.
    Fails closed — an unreadable link is not boost's to delete.
    """
    try:
        target = link.readlink()
    except OSError:
        return False
    if not target.is_absolute():
        target = link.parent / target
    target_s = normalize_link_target(target)
    root_s = normalize_link_target(paths.store_dir())
    try:
        # ValueError for paths with no common root — on Windows, two different
        # drives — which means "outside", not "crash out of the delete guard".
        return os.path.commonpath([target_s, root_s]) == root_s
    except ValueError:
        return False


def resolves_into_store(path: Path) -> bool:
    """True if ``path``'s fully resolved real location sits inside the store.

    The companion to :func:`points_into_store`, and deliberately not the same
    question. That one reads a single ``readlink()`` because it judges *broken*
    links, where there is nothing to resolve. This one judges live ones, and
    has to follow the whole chain: the shape that prompted it is
    ``~/.gemini/skills/x -> ../../.claude/skills/x -> ~/.agents/skills/x``,
    where one hop lands in another agent's dir and reads as foreign. Only the
    second hop reaches the store.

    **Both sides are resolved.** Comparing a resolved target against a nominal
    ``store_dir()`` is the bug `_resolve_as_far_as_it_exists` documents in
    ``commands/quality.py``: a $HOME under macOS's ``/var/folders`` resolves to
    ``/private/var/...``, so a genuine hit never prefix-matches. Containment is
    `commonpath`, not `startswith`, so ``~/.agents/skills-backup`` stays out.

    Fails closed — a symlink loop, or anything else ``resolve()`` refuses to
    answer, is not in the store as far as this is concerned.
    """
    try:
        target_s = normalize_link_target(path.resolve(strict=True))
        root_s = normalize_link_target(paths.store_dir().resolve())
    except (OSError, RuntimeError):
        # RuntimeError is not redundant: on Python 3.12 `resolve(strict=True)`
        # raises RuntimeError("Symlink loop from ...") for a cycle, and
        # RuntimeError is NOT an OSError subclass. 3.13+ raises OSError for the
        # same input. Catching only OSError made "fails closed" true on the
        # newer interpreters and false on the oldest supported one — the test
        # passed locally on 3.14 and failed in CI on 3.12.
        return False
    try:
        return os.path.commonpath([target_s, root_s]) == root_s
    except ValueError:
        return False


@dataclass(frozen=True)
class DuplicateDiscovery:
    """One skill a native-store agent can reach through two discovery tiers.

    ``path`` is the entry inside the agent's own skills dir; ``target`` is
    where it really leads, inside the canonical store the agent already reads
    natively.
    """
    agent: str
    name: str
    path: Path
    target: Path


def duplicate_discovery() -> list[DuplicateDiscovery]:
    """Entries in a native-store agent's skills dir that lead into the store.

    A `links_skills: false` agent reads :func:`paths.store_dir` directly, so
    anything in its own skills dir that resolves back into the store is the
    same skill offered twice. Gemini CLI answers that with a "Skill conflict
    detected" line per skill, every session — the symptom this detects.

    Boost does not create these: it stopped linking into a native-store agent,
    and `sync_plan` never asks for such a link. Another installer's copy is far
    likelier, and the warning costs the user the same either way — so the test
    is **topology, not ownership**. Nothing here deletes: see
    :func:`remove_duplicate_discovery`, which is opt-in because removing
    another tool's file on a hunch is worse than the warning.

    A missing agent dir is the normal case (boost never creates one for a
    native-store agent) and yields nothing rather than an error. The store root
    itself is skipped: a link to ``~/.agents/skills`` is the Agent Skills
    alias, not a skill discovered twice.
    """
    found: list[DuplicateDiscovery] = []
    store_root = paths.store_dir()
    for agent, adir in agents.native_store_agents().items():
        if not adir.is_dir():
            continue
        for entry in sorted(adir.iterdir()):
            if not resolves_into_store(entry):
                continue
            target = entry.resolve()
            if target == store_root.resolve():
                continue
            found.append(DuplicateDiscovery(
                agent=agent, name=entry.name, path=entry, target=target))
    return sorted(found, key=lambda d: (d.agent, d.name))


def remove_duplicate_discovery(dup: DuplicateDiscovery) -> bool:
    """Delete one duplicate discovery path. True if it was removed.

    Re-gated against the filesystem rather than trusting the report that
    produced ``dup``: boost did not put this file here, so the two facts that
    make deleting it safe — it is a symlink, and it still leads into the store —
    are checked again at the moment of deletion. Anything else (a real
    directory, a link that has since been repointed, an entry already gone) is
    refused with False rather than an exception, so a caller sweeping a list
    reports what it skipped instead of dying half way.
    """
    path = Path(dup.path)
    if not path.is_symlink() or not resolves_into_store(path):
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True


def restore_preserve_newer_lock_sections(
        pre_rules: dict, pre_workflows: dict) -> dict[str, list[str]]:
    """After a lock file has been replaced wholesale (snapshot restore),
    re-add rule/workflow entries that were installed live but are absent from
    the just-restored lock.

    A snapshot only archives the skill store (which is where the lock file
    itself lives), never the agent context files a rule's or workflow's
    materialization writes into (``CLAUDE.md``, a rendered slash command,
    ...). Restoring an *older* snapshot therefore drops any rule/workflow
    installed since — its lock entry vanishes with the rest of the archived
    lock, but its materialized file is untouched on disk, so the block
    becomes orphaned: still present, no longer traceable, and impossible to
    ``boost uninstall``.

    Filling the gap rather than overwriting the section outright preserves
    the other, already-correct direction: an entry the snapshot *did* carry
    that was later uninstalled comes back through the normal archived lock
    contents, and :func:`sync_plan`/:func:`sync_apply` re-materializes it
    from its tap same as any other missing materialization. Only names
    genuinely absent from the restored lock are filled in here.

    ``pre_rules``/``pre_workflows`` must be captured by the caller *before*
    the store is emptied for extraction. Returns the names actually kept, per
    section, so the caller can report what changed; writes the lock only when
    there is something to add back.
    """
    lock = lockfile.read()
    kept: dict[str, list[str]] = {"rules": [], "workflows": []}
    for name, entry in pre_rules.items():
        if name not in lock["rules"]:
            lock["rules"][name] = entry
            kept["rules"].append(name)
    for name, entry in pre_workflows.items():
        if name not in lock["workflows"]:
            lock["workflows"][name] = entry
            kept["workflows"].append(name)
    if kept["rules"] or kept["workflows"]:
        lockfile.write(lock)
    return kept


def lock_vouches() -> bool:
    """Whether the lock file can say which store dirs and links are boost's.

    It can when it parses, and when it is missing over an empty store — that
    is a fresh install with nothing to disown. It cannot when it is missing
    over a populated store, corrupt, or written in another schema:
    :func:`lockfile.installed` collapses all three into an empty record, and
    reading that as "nothing is installed" turned `boost sync` — the command
    `boost doctor` prescribes for exactly this state — into an uninstaller that
    removed every live link of an intact install with green ticks and exit 0.
    """
    integ = lockfile.check()
    return integ.ok or (integ.problem == "missing" and not has_content())


def sync_plan() -> dict[str, list]:
    """Compare lock file <-> store <-> agent symlinks.

    Returns {missing_store, missing_links, stale_links, orphaned_store}
      missing_store:  lock entries whose store dir is gone
      missing_links:  (skill, agent) pairs that should be linked but aren't,
                      and that sync *can* create
      blocked_links:  (skill, agent, path) where something that is not a boost
                      symlink occupies the link path — sync will not clobber it
      stale_links:    paths in agent dirs that are broken/unmanaged symlinks
      orphaned_store: store dirs not present in the lock file
      unrecorded_store: the same, while the lock cannot vouch for anything
                      (:func:`lock_vouches`) — never pruned, re-recorded by
                      :func:`sync_apply` when the lock is merely missing
      out_of_scope_links: (skill, agent) pairs linked outside a declared
                      ``--agent`` narrowing — reported, never auto-removed

    ``blocked_links`` exists because lumping it into ``missing_links`` made
    ``boost sync`` promise a repair it could never perform. ``link_agents``
    refuses to delete a real file or directory it does not own (right), records
    it in ``.conflicts`` — and ``sync_apply`` dropped that on the floor, so the
    command printed "everything in sync" while ``boost doctor`` went on
    reporting the same skill unlinked and prescribing ``boost sync``. Seen for
    real where another installer had written ``~/.claude/skills/hyperframes``
    as a directory: a closed loop with no exit.
    """
    lock = lockfile.installed()
    vouches = lock_vouches()
    # An agent whose skills dir has a file or a dangling link in the way:
    # `link_agents` skips it, so listing its links as missing made `boost
    # sync` print "everything in sync" over the repair it had just skipped.
    # Its links are blocked, by what is in the way.
    in_the_way = {a: b for a, d in agents.linking_agents().items()
                  if (b := paths.refuses_writes(d)) is not None
                  and paths.in_the_way(b)}
    plan: dict[str, list] = {"missing_store": [], "missing_links": [],
            "blocked_links": [], "stale_links": [], "orphaned_store": [],
            "unrecorded_store": [], "missing_materializations": [],
            "out_of_scope_links": []}
    for name, entry in lock.items():
        sdir = skill_store_dir(name)
        # A directory with no SKILL.md counts as missing, not as healthy. The
        # check used to be `is_dir()` alone, and the gap was reachable: an
        # interrupted copy, a partial rsync or a user deleting the file leaves
        # the directory behind. `boost edit` and `boost evolve` both refuse such
        # a skill with the hint "repair the store with `boost sync`" — and sync
        # would answer "everything in sync", change nothing, and send the reader
        # back to the same error. The remedy named the step they had just run.
        #
        # `missing_store` is the right bucket rather than a new one: its repair
        # is already "reinstall this skill from its tap", which is exactly what
        # a gutted directory needs, and reusing it means sync_apply needs no
        # change at all.
        #
        # This used to `continue` here, which skipped agent-link classification
        # for the entry entirely — so a foreign file already occupying a link
        # path went unreported until a *second* `sync` noticed the repair had
        # not actually relinked that agent. The classification below reads
        # only the agent dir, never the store, so running it costs nothing
        # even while the store copy is still missing — see the `missing_store`
        # check further down, which still lets it feed `blocked_links` but
        # keeps it out of `missing_links`: `sync_apply` repairs a missing
        # store by reinstalling from the tap, which relinks every non-blocked
        # agent as one step, and that reinstall runs *after* this plan is
        # built, so a `missing_links` entry here would have `sync_apply` try
        # to link a store directory that does not exist yet.
        missing_store = not sdir.is_dir() or not (sdir / "SKILL.md").is_file()
        if missing_store:
            plan["missing_store"].append(name)
        if entry.get("quarantined"):
            continue
        # A deliberate sideline (`focus`, `profile use`, `context apply`)
        # unlinks on purpose and records it in `sidelined_by` — so the missing
        # links below are not damage to repair. Without this check `sync`
        # relinked every sidelined skill, undoing the switch it was never told
        # about.
        if entry.get("sidelined_by"):
            continue
        # Only the agents this skill was installed for. Walking every enabled
        # agent made `boost sync` a second path to the scope leak that
        # `preserved_agent_scope` closed on the install side: it reported a
        # missing_link for each agent outside the narrowing, and sync_apply
        # dutifully linked them, undoing `install --agent` in one command.
        # linking_agents, not enabled_agents: an agent that reads the canonical
        # store has no link to be missing, and reporting one would make `boost
        # sync` create the very duplicate `links_skills: false` exists to avoid.
        linking = agents.linking_agents()
        in_scope = scoped_agents(entry, linking)
        for agent, adir in in_scope.items():
            if agent in in_the_way:
                plan["blocked_links"].append(
                    (name, agent, str(in_the_way[agent])))
                continue
            link = adir / name
            # A symlink is boost's to replace even when it dangles; anything
            # else that exists is someone else's file and stays put.
            if link.is_symlink():
                if not link.exists() and not missing_store:
                    plan["missing_links"].append((name, agent))
            elif link.exists():
                plan["blocked_links"].append((name, agent, str(link)))
            elif not missing_store:
                plan["missing_links"].append((name, agent))
        # The other direction, which nothing checked: a link that exists in an
        # agent the declaration excludes. The loop above is narrowed to the
        # declared set, and the stale-link sweep below keys on the skill *name*
        # being absent from the lock — so a live, boost-owned link outside a
        # narrowing fell between the two and no command could see it. Only
        # meaningful when a narrowing was declared; without one `scoped_agents`
        # fails open and every agent is in scope by definition.
        if entry.get("only_agents"):
            for agent, adir in linking.items():
                if agent not in in_scope and (adir / name).is_symlink():
                    plan["out_of_scope_links"].append((name, agent))
    store_root = paths.store_dir()
    if store_root.is_dir():
        for child in sorted(store_root.iterdir()):
            if (child.is_dir() and not child.name.startswith(".")
                    and child.name not in lock):
                plan["orphaned_store" if vouches else "unrecorded_store"].append(
                    child.name)
    for adir in agents.enabled_agents().values():
        if not adir.is_dir():
            continue
        for link in adir.iterdir():
            # Ownership first, for broken links too: the old test short-circuited
            # on `not link.exists()`, so any dangling symlink a user happened to
            # keep in ~/.claude/skills was swept up by `boost sync`.
            #
            # "Not in the lock" means "not installed" only while the lock can
            # vouch. Without that guard a missing lock made every live link
            # into an intact store look stale, and sync removed them all.
            if (link.is_symlink() and points_into_store(link)
                    and (not link.exists()
                         or (vouches and link.name not in lock))):
                plan["stale_links"].append(str(link))
    # Rules/workflows don't live in the store — they materialize into agent dirs.
    # A materialization whose file (or CLAUDE.md block) is gone can be repaired
    # by re-materializing from the tap, same as a missing skill store dir.
    for name, entry in lockfile.installed_rules().items():
        # A quarantined rule's materializations are ABSENT BY DESIGN — the
        # stash holds them. Repairing here would re-arm what quarantine
        # disarmed, making `boost sync` an accidental release.
        if entry.get("quarantined"):
            continue
        if any(m.get("unwritable") or not _rule_materialization_ok(name, m)
               for m in entry.get("materializations") or []):
            plan["missing_materializations"].append(("rule", name))
    for name, entry in lockfile.installed_workflows().items():
        if entry.get("quarantined"):
            continue
        if any(m.get("unwritable") or not Path(m.get("path", "")).is_file()
               for m in entry.get("materializations") or []):
            plan["missing_materializations"].append(("workflow", name))
    return plan


def _rule_materialization_ok(name: str, m: dict) -> bool:
    """True if a rule materialization is still present: a file drop must exist,
    and a Claude rule's CLAUDE.md must still carry its managed block."""
    from . import rules
    p = Path(m.get("path", ""))
    if m.get("mode") == rules.MODE_CLAUDE:
        try:
            return p.exists() and ("boost:rule:%s start" % name) in \
                p.read_text(encoding="utf-8")
        except OSError:
            return False
    return p.is_file()


def prune_out_of_scope_links(plan: dict[str, list]) -> list[str]:
    """Remove the links :func:`sync_plan` found outside a declared scope.

    Kept out of :func:`sync_apply` on purpose. Everything sync_apply does is
    either additive or removes something already broken, so `boost sync` and
    `boost heal` are safe to run blind. These links are neither broken nor
    unowned — they work, and an agent is using them — so deleting one changes
    which agents can run a skill. That is a decision, and it belongs behind the
    same explicit opt-in as deleting an orphaned store dir (`--prune`).
    """
    removed = []
    linking = agents.linking_agents()
    for name, agent in plan.get("out_of_scope_links", []):
        adir = linking.get(agent)
        if adir is None:      # disabled between plan and prune
            continue
        link = adir / name
        if link.is_symlink():
            link.unlink()
            entry = lockfile.get_skill(name)
            if entry:
                entry["agents"] = [a for a in entry.get("agents") or []
                                   if a != agent]
                lockfile.set_skill(name, entry)
            removed.append("unlinked %s → %s (outside declared scope)"
                           % (name, agent))
    if removed:
        journal.log("sync-prune", "%d links" % len(removed))
    return removed


def _skill_source_sha(cat_entry: dict) -> str | None:
    """sha256 of a catalog entry's tap source directory, or None if unreadable."""
    try:
        return util.sha256_dir(source_dir_for(cat_entry))
    except BoostError:
        return None


def _source_text_sha(tap_name: str, cat_entry: dict) -> str | None:
    """sha256 of a rule/workflow's tap source text, or None if unreadable."""
    import hashlib
    try:
        src = registry.get(tap_name).path / cat_entry.get("skill_md", "")
        return hashlib.sha256(src.read_text(
            encoding="utf-8", errors="replace").encode("utf-8")).hexdigest()
    except (OSError, BoostError):
        return None


def _pinned_repair_blocked(entry: dict, source_sha: str | None) -> bool:
    """True when repairing ``entry`` from its tap would bypass a pin.

    sync repairs by re-installing from the tap's CURRENT content. For an
    unpinned entry that is the point of `boost sync`; for a pinned one whose
    source has moved it would be the covert update the pin exists to prevent —
    the same guard the update loops apply, on the repair path. An unreadable
    source fails closed: better to leave a pinned item broken and say so than
    to guess.
    """
    if not entry.get("pinned"):
        return False
    return source_sha is None or source_sha != entry.get("sha256")


def _pin_blocks_repair(entry: dict, source_sha) -> bool:
    """:func:`_pinned_repair_blocked`, with the sha computed only if it matters.

    ``source_sha`` is a *callable*. Hashing a tap source goes through
    :func:`source_dir_for`, which calls ``gitutil.materialize`` — a
    ``sparse-checkout add``, i.e. a write and sometimes a network fetch. The
    eager call was harmless on the apply path (the install materializes anyway)
    and is not on the preview path, where it would make `heal --dry-run` widen
    a clone's cone. An unpinned entry can never be blocked, so it never needs
    the answer.
    """
    if not entry.get("pinned"):
        return False
    return _pinned_repair_blocked(entry, source_sha())


@dataclass(frozen=True)
class StoreRepair:
    """The branch `sync_apply` will take for one missing skill, rule or workflow.

    Both the repair and its preview read this, so they cannot disagree about
    *which* repair happens — the defect it exists to close was `heal --dry-run`
    printing "would restore X from its tap (or drop it from the lock)" on a
    state where the live run demonstrably reinstalls, offering an alternative
    that never fired. Tense is still each caller's business; the decision is not.

    ``preview`` is a prediction, not a promise: an install can still fail (a
    tap clone removed between the two calls), and a failed install falls
    through to the drop. That residue is the honest kind — it names the branch
    the run will *attempt*, rather than listing both and committing to neither.
    """

    action: str                     #: local | tap | declined | drop
    preview: str
    applied: str
    warning: str | None = None
    cat_entry: dict | None = None   #: what a "tap" repair installs
    src: Path | None = None         #: what a "local" repair installs from
    scope: str = "user"             #: where a rule/workflow re-materializes
    base: str | None = None


_DROPPED = "dropped %s from lock (store dir missing, source gone)"
_GONE = ("%s %s has a missing materialization but its source is gone — "
         "run `boost update` or reinstall")


def _declined(label: str, where: str, name: str) -> str:
    return ("%s is pinned and its %s source has moved — repair declined "
            "(unpin, or `boost reinstall %s` to accept the new content)"
            % (label, where, name))


def _lock_source(name: str, tap_name: str, entry: dict,
                 kind: str | None = None) -> tuple[dict | None, str | None]:
    """The catalog entry a repair would reinstall ``name`` from, and a warning.

    ``(None, None)`` when the tap cannot answer, which both callers treat as a
    source that is gone.
    """
    from . import catalog
    try:
        matches = [e for e in catalog.find(name) if e["tap"] == tap_name
                   and (kind is None or e.get("kind", "skill") == kind)]
        return catalog.select_lock_source(matches, entry)
    except BoostError:
        return None, None


def plan_missing_store(name: str) -> StoreRepair:
    """How `sync` will repair `name`, whose store dir is gone. Read-only."""
    entry = lockfile.get_skill(name) or {}
    tap_name = entry.get("tap")
    if is_url_import(entry):
        # A URL import can be repaired only by cloning its repo again, and sync
        # never touches the network. Dropping the entry instead would throw
        # away the one record of where the skill came from, so keep it and
        # name the command that can.
        msg = ("%s's store dir is missing — `boost reinstall %s` clones it "
               "again from %s" % (name, name, entry["source_url"]))
        return StoreRepair("declined", msg, msg)
    if tap_name == "local":
        src = local_source_dir(entry)
        if src is not None:
            if _pin_blocks_repair(entry, lambda: _local_source_sha(src)):
                msg = _declined(name, "local", name)
                return StoreRepair("declined", msg, msg)
            return StoreRepair(
                "local", src=src,
                preview="would reinstall %s from local source %s" % (name, src),
                applied="reinstalled missing %s from local source %s" % (name, src))
    elif tap_name:
        cat_entry, warning = _lock_source(name, tap_name, entry)
        if cat_entry:
            if _pin_blocks_repair(entry, lambda: _skill_source_sha(cat_entry)):
                msg = _declined(name, "tap", name)
                return StoreRepair("declined", msg, msg, warning=warning)
            return StoreRepair(
                "tap", cat_entry=cat_entry, warning=warning,
                preview="would reinstall %s from %s" % (name, tap_name),
                applied="reinstalled missing %s from %s" % (name, tap_name))
    return StoreRepair(
        "drop",
        preview="would drop %s from the lock (store dir missing, source gone)" % name,
        applied=_DROPPED % name)


def plan_missing_materialization(kind: str, name: str) -> StoreRepair:
    """How `sync` will repair a rule/workflow whose files are gone. Read-only."""
    getter = lockfile.get_rule if kind == "rule" else lockfile.get_workflow
    entry = getter(name) or {}
    tap_name = entry.get("tap")
    if tap_name and tap_name != "local":
        cat_entry, warning = _lock_source(name, tap_name, entry, kind=kind)
        if cat_entry:
            if _pin_blocks_repair(
                    entry, lambda: _source_text_sha(tap_name, cat_entry)):
                msg = _declined("%s %s" % (kind, name), "tap", name)
                return StoreRepair("declined", msg, msg, warning=warning)
            # The lock's scope/base, so a project rule repairs into its repo,
            # not wherever sync happens to run.
            return StoreRepair(
                "tap", cat_entry=cat_entry, warning=warning,
                scope=entry.get("scope", "user"), base=entry.get("base"),
                preview="would re-materialize %s %s from %s" % (kind, name, tap_name),
                applied="re-materialized %s %s from %s" % (kind, name, tap_name))
    # One sentence in both tenses because it has only one: this branch repairs
    # nothing, it reports. A "would ..." here would invent an action.
    return StoreRepair("drop", preview=_GONE % (kind, name),
                       applied=_GONE % (kind, name))


def _local_source_sha(src: Path) -> str | None:
    """sha256 of a local skill's source directory, or None if unreadable."""
    try:
        return util.sha256_dir(src)
    except OSError:
        return None


def sync_preview(plan: dict[str, list]) -> list[str]:
    """What :func:`sync_apply` would report, without applying any of it.

    Only the buckets whose repair *branches* live here; `missing_links` and
    `stale_links` do one unconditional thing each and stay with their caller,
    which filters them against the links it has already reported.
    """
    lines = []
    # `sync_apply` re-records only while the lock file is *missing* — a corrupt
    # one is left for `boost replay` — and only a dir that still has a
    # SKILL.md. The preview used to say "would re-record" either way.
    if plan.get("unrecorded_store") and lockfile.check().problem == "missing":
        for name in plan["unrecorded_store"]:
            if (skill_store_dir(name) / "SKILL.md").is_file():
                lines.append("would re-record %s, which the lock file has lost"
                             % name)
            else:
                lines.append("would leave %s unrecorded (no SKILL.md to record)"
                             % name)
    repairs = [plan_missing_store(name) for name in plan.get("missing_store", [])]
    repairs += starmap(plan_missing_materialization,
                       plan.get("missing_materializations", []))
    for repair in repairs:
        if repair.warning:
            lines.append(repair.warning)
        lines.append(repair.preview)
    return lines


def recover_unrecorded(name: str) -> str | None:
    """Re-record one store dir the lock has lost; return how, or None.

    Only ever called while the lock file is missing over a populated store, so
    writing a record cannot overwrite a newer or merely unreadable lock. The
    store copy is authoritative and is never replaced: re-installing would
    have been the obvious repair, and it silently discards any edits made to
    the store copy.

    A dir whose content is byte-identical to exactly one tapped source is
    recorded as installed from that tap, the record a fresh install would have
    written. Anything else — edited, or from a tap no longer tapped — is
    recorded as a local skill whose source is the store dir itself, so nothing
    is lost and nothing is left unrecorded: a dir left out would read as an
    orphan the moment this pass creates a lock, and the next sync would remove
    its links, the defect this function exists to close.
    """
    sdir = skill_store_dir(name)
    if not (sdir / "SKILL.md").is_file():
        return None
    from . import catalog, gitutil
    have = util.sha256_dir(sdir)
    matches = [e for e in catalog.find(name)
               if e.get("kind", "skill") == "skill"
               and _skill_source_sha(e) == have]
    linked = linked_agents(name)
    linking = list(agents.linking_agents())
    # Record what is on disk: a skill linked into fewer agents than are enabled
    # was narrowed, and recording no narrowing would have the next sync link it
    # everywhere behind the user's back.
    narrowed = sorted(linked) if linked and set(linked) != set(linking) else None
    now = util.now_iso()
    record: dict[str, object]
    if len(matches) == 1:
        cat = matches[0]
        tap = registry.get(cat["tap"])
        record = {"version": cat.get("version", "0.0.0"), "tap": cat["tap"],
                  "source_dir": cat.get("rel_dir", "."),
                  "commit": gitutil.head_commit(tap.path)}
        how = "from %s" % cat["tap"]
    else:
        # The shape `import_local` writes for a skill with no tap behind it.
        record = {"version": "0.0.0", "tap": "local", "source_dir": str(sdir),
                  "commit": ""}
        how = ("as a local skill (its content matches %s tapped source; "
               "`boost reinstall %s` replaces it with a tap's copy)"
               % ("no" if not matches else "more than one", name))
    record.update({"sha256": have, "installed_at": now, "updated_at": now,
                   "pinned": False, "quarantined": False, "agents": linked,
                   "only_agents": narrowed, "tags": []})
    lockfile.set_skill(name, record)
    journal.log("recover", name, how=record["tap"])
    return "re-recorded %s %s" % (name, how)


def sync_apply(plan: dict[str, list]) -> list[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    # First, so every re-recorded skill is in the lock before anything else
    # runs; and only when the lock is *missing* — a corrupt or other-schema
    # lock is left for `boost replay`, never overwritten.
    if plan.get("unrecorded_store") and lockfile.check().problem == "missing":
        for name in plan["unrecorded_store"]:
            how = recover_unrecorded(name)
            actions.append(how or "left %s unrecorded (no SKILL.md to record)" % name)
    for name, agent in plan["missing_links"]:
        res = link_agents(name, only=[agent])
        if agent in res.linked:
            actions.append("linked %s → %s" % (name, agent))
    for path in plan["stale_links"]:
        p = Path(path)
        if p.is_symlink():
            p.unlink()
            # `--diff` shows this same path tilde-contracted (`_tilde` in
            # commands/pkg.py); the raw absolute string here made the two
            # views of one path disagree in the exact case a user compares
            # them — planned vs. applied.
            actions.append("removed stale link %s" % paths.tilde(path))
    for name in plan["missing_store"]:
        # The branch is decided in one place, so `sync_preview` words the same
        # decision rather than re-deriving (and mis-deriving) it.
        repair = plan_missing_store(name)
        if repair.warning:
            actions.append(repair.warning)
        if repair.action == "declined":
            actions.append(repair.applied)
            continue
        try:  # noqa: FURB107 - per-item resilience in a loop (see PERF203)
            if repair.src is not None:
                install_from_path(repair.src, name=name, force=True)
                actions.append(repair.applied)
                continue
            if repair.cat_entry is not None:
                install(repair.cat_entry, force=True)
                actions.append(repair.applied)
                continue
        except BoostError:
            # The one place the preview can be wrong, and deliberately: a
            # source readable a moment ago is gone now, so the run falls
            # through to the drop.
            pass
        lockfile.remove_skill(name)
        actions.append(_DROPPED % name)
    for kind, name in plan.get("missing_materializations", []):
        mat = plan_missing_materialization(kind, name)
        if mat.warning:
            actions.append(mat.warning)
        if mat.action == "declined":
            actions.append(mat.applied)
            continue
        if mat.cat_entry is None:
            actions.append(_GONE % (kind, name))
            continue
        try:  # noqa: FURB107 - per-item resilience in a loop (see PERF203)
            res = install(mat.cat_entry, force=True, scope=mat.scope,
                          base=mat.base)
        except BoostError as err:
            # The source is there; the install said why it stopped (a store
            # that refuses the lock, say). Reporting `_GONE` here sent the
            # user to `boost update` for a problem in ~/.agents/skills.
            actions.append("%s %s was not re-materialized: %s%s"
                           % (kind, name, err.message,
                              " — %s" % err.hint if err.hint else ""))
            continue
        # A directory still refusing the write is not a repair, so it is not
        # reported as one; the caller names the dir itself
        # (`unwritable_agent_dirs`, `blocked_agent_dirs`), with its remedy.
        if not res.unwritable and not res.blocked:
            actions.append(mat.applied)
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions
