"""The canonical store (~/.agents/skills) and agent symlinks.

install():  copy skill dir from a tap clone -> store, symlink into every
            enabled agent dir, record in the lock file, log to the journal.
"""
from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..errors import BoostError
from . import (
    agents,
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
    linked: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    # Agents that can already use this skill without a symlink because they read
    # the canonical store directly (agents.native_store_agents). Kept apart from
    # `linked` so the lock records only real links, while the install report can
    # still tell the user the skill reached them.
    native: List[str] = field(default_factory=list)
    score: int = 0
    upgraded: bool = False
    kind: str = "skill"
    scope: str = "user"   # "user" or "project" — where a rule/workflow landed
    # For rules/workflows the installed content is a single file (or a merged
    # CLAUDE.md block), not a SKILL.md tree — carry the raw source so the caller
    # scans exactly what it installed instead of a non-existent SKILL.md.
    scan_text: Optional[str] = None
    # MCP servers the skill declares (mcpdecl.servers_for rows). Detected here
    # but never acted on: core stays non-interactive, so the command layer owns
    # the offer to register them — same split as `conflicts` and `score`.
    mcp_servers: List[dict] = field(default_factory=list)
    # Names actually written to the project's .mcp.json — not what was
    # declared. The two differ when the file could not be written, and the
    # install report must show the former.
    mcp_recorded: List[str] = field(default_factory=list)


def skill_store_dir(name: str) -> Path:
    """Resolve ``name`` to its dir under the canonical store.

    Raises BoostError unless the name is a safe path component.
    """
    if not util.is_safe_component(name):
        raise BoostError("invalid skill name %r" % name)
    return paths.store_dir() / name


def installed() -> dict:
    """Return the lock file's installed skills as {name: entry}.

    Skills only; rules/workflows live in their own lock sections.
    """
    return lockfile.installed()


def source_dir_for(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def link_agents(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each linking agent dir. Returns result with
    .linked (agent names), .conflicts (paths that were real files/dirs) and
    .native (agents that read the store directly and needed no link)."""
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
        adir.mkdir(parents=True, exist_ok=True)
        link = adir / name
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            res.conflicts.append(str(link))
            continue
        link.symlink_to(target)
        res.linked.append(agent)
    return res


def preserved_agent_scope(only_agents: Optional[List[str]],
                          existing: Optional[dict]) -> Optional[List[str]]:
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


def declared_agent_scope(only_agents: Optional[List[str]],
                         existing: Optional[dict]) -> Optional[List[str]]:
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


def scoped_agents(entry: dict, enabled: Dict[str, Path]) -> Dict[str, Path]:
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


def unlink_agents(name: str) -> List[str]:
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


def linked_agents(name: str) -> List[str]:
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


def _untouched_materializations(existing: Optional[dict],
                                linked: List[str]) -> List[dict]:
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
    dest.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(dir=str(dest.parent),
                                   prefix="." + dest.name + ".tmp"))
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


def declared_mcp_servers(skill_dir) -> List[dict]:
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


def _load_sidecar(path: Path) -> Optional[dict]:
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


def register_project_mcp(base, rows, skill: str) -> List[str]:
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


def unregister_project_mcp(base, skill: str) -> List[str]:
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


def _enforce_capability_policy(name: str, skill_md: Path) -> None:
    """Raise if the skill's declared/detected capabilities are denied by policy.

    Runs on the skill's own SKILL.md before it is copied anywhere — a skill is a
    bundle of instructions the agent will execute, and least-privilege means the
    user's policy can refuse one that expects a capability they don't grant. A
    no-op unless the policy names a denied capability.
    """
    from . import frontmatter
    try:
        raw = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    meta, _body = frontmatter.parse(raw)
    caps = policy.check_capabilities(meta, raw)
    if caps:
        raise BoostError(
            "policy blocks installing %s: %s" % (name, "; ".join(caps)),
            hint="relax it with `boost policy` (denied_capabilities), or "
                 "install a skill that needs less")


def _resolve_base(scope: str, base) -> Optional[Path]:
    """Directory a project-scoped install materializes under (the repo), or None
    for user scope.

    Delegates to :func:`scopes.resolve_base`, which walks up for the nearest
    project root — running this from ``src/deep/nested`` must write into the
    repo, not scatter a ``.claude/`` three directories down.
    """
    return scopes.resolve_base(scope, base)


def _require_project_base(scope: str, base, what: str) -> Optional[Path]:
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


def install(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None,
            scope: str = "user", base=None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict.

    ``scope`` is ``"user"`` (default — the canonical store, symlinked into the
    agent's user config dirs) or ``"project"`` (real directories inside the
    current repo). Every kind honors it.
    """
    scopes.check_scope(scope)
    kind = entry.get("kind", "skill")
    if kind == "rule":
        return _install_rule(entry, force=force, only_agents=only_agents,
                             scope=scope, base=base)
    if kind == "workflow":
        return _install_workflow(entry, force=force, only_agents=only_agents,
                                 scope=scope, base=base)
    if kind != "skill":
        raise BoostError(
            "%s is a %s, which boost does not know how to install" % (entry["name"], kind),
            hint="known kinds: skill, rule, workflow")
    if scope == scopes.SCOPE_PROJECT:
        return _install_project_skill(entry, force=force, only_agents=only_agents,
                                      base=base)
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
    paths.ensure_dirs()
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
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def _install_project_skill(entry: dict, force: bool = False,
                           only_agents: Optional[List[str]] = None,
                           base=None) -> InstallResult:
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
    targets = [(agent, scopes.skill_target(skills_dir, name, base=resolved_base))
               for agent, skills_dir in agents.enabled_agents().items()
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

    materializations: List[dict] = []
    linked: List[str] = []
    first: Optional[Path] = None
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
                scope=scopes.SCOPE_PROJECT)

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
    removed: List[str] = []
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
            "mcp_unregistered": unregistered,
            "scope": scopes.SCOPE_PROJECT, "base": str(resolved_base)}


def project_sync_plan(base=None) -> Dict[str, list]:
    """Compare the project lock against what is actually on disk.

    Returns ``{missing, orphaned}``: lock entries whose directory is gone, and
    skill directories under the project's agent dirs that no lock entry claims.
    A teammate who clones the repo has the files but may be missing one an
    ``update`` added, so this is the repair list for a shared checkout.
    """
    plan: Dict[str, list] = {"missing": [], "orphaned": []}
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


def project_sync_apply(plan: Dict[str, list], base=None) -> List[str]:
    """Re-materialize the project skills :func:`project_sync_plan` found missing.

    Orphans are reported but never deleted: an unclaimed directory in someone's
    repo is far more likely to be a hand-written skill than boost's litter, and
    a package manager that silently removes files it did not write is one nobody
    should run in their working tree.
    """
    actions: List[str] = []
    resolved_base = _resolve_base(scopes.SCOPE_PROJECT, base)
    if resolved_base is None:
        return actions
    # Group by skill, but keep WHICH agents are missing: these directories are
    # committed files a team edits in place, so repairing one agent must not
    # re-copy over the others. Re-installing the whole skill would silently
    # revert a teammate's edit to a file they had checked in.
    wanted: Dict[str, list] = {}
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
                if matches:
                    install(matches[0], force=True, scope=scopes.SCOPE_PROJECT,
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
                  only_agents: Optional[List[str]] = None,
                  scope: str = "user", base=None) -> InstallResult:
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
    existing = lockfile.get_rule(name)
    if existing and not force:
        raise BoostError("%s is already installed" % name,
                        hint="`boost reinstall %s` to force" % name)
    only_agents = preserved_agent_scope(only_agents, existing)

    violations = policy.check_install(entry, len(lockfile.installed()))
    if violations:
        raise BoostError("policy blocks installing %s: %s" % (name, "; ".join(violations)),
                        hint="inspect with `boost policy list`")

    # Cheap precondition, checked before any tap or filesystem work: if there
    # is nowhere to put this, say so immediately.
    resolved_base = _require_project_base(scope, base, "rule %s" % name)

    tap = registry.get(entry["tap"])
    src = tap.path / entry.get("skill_md", "")
    if not src.is_file():
        raise BoostError("source for rule %s vanished from tap %s" % (name, tap.name),
                        hint="run `boost update %s`" % tap.name)
    raw = src.read_text(encoding="utf-8", errors="replace")
    meta, body = frontmatter.parse(raw)
    claude_body = rules.render_claude_body(str(meta.get("name") or name), body)

    paths.ensure_dirs()
    materializations: List[dict] = []
    linked: List[str] = []
    for agent, skills_dir in agents.enabled_agents().items():
        if only_agents and agent not in only_agents:
            continue
        mode, path = rules.rule_target(agent, skills_dir, name, base=resolved_base)
        # Project scope writes into the repo, so a committed agent dir could be
        # a symlink escaping it (see scopes.ensure_in_base). User scope writes
        # into the user's own ~/.claude, which they control — nothing to guard.
        if resolved_base is not None:
            scopes.ensure_in_base(resolved_base, path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if mode == rules.MODE_CLAUDE:
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            util.atomic_write_text(path, rules.merge_block(current, name, claude_body))
        else:
            util.atomic_write_text(path, raw)
        materializations.append({"agent": agent, "mode": mode, "path": str(path)})
        linked.append(agent)

    # Carry forward the agents this run did not touch — the same reason the
    # project-scope skill path does it, but the stakes are higher here. A
    # rule's materialization is a managed block inside a file the user reads
    # every session (~/.claude/CLAUDE.md); dropping the record does not drop
    # the block, and `_uninstall_rule` is record-driven, so an unrecorded block
    # could never be removed by any boost command again.
    materializations.extend(_untouched_materializations(existing, linked))

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
        "materializations": materializations,
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))

    res = InstallResult(
        name=name,
        dest=Path(materializations[0]["path"]) if materializations else paths.store_dir(),
        kind="rule", scan_text=raw)
    res.linked = linked
    res.upgraded = existing is not None
    res.scope = scope
    return res


def _uninstall_rule(name: str, rule: dict) -> dict:
    """Reverse every materialization recorded for an installed rule."""
    from . import rules
    removed: List[str] = []
    for m in rule.get("materializations", []):
        path = Path(m.get("path", ""))
        if m.get("mode") == rules.MODE_CLAUDE:
            if path.exists():
                stripped = rules.strip_block(path.read_text(encoding="utf-8"), name)
                if stripped:
                    util.atomic_write_text(path, stripped)
                else:
                    path.unlink()  # file held only our block — boost created it
        elif path.is_file() or path.is_symlink():
            path.unlink()
        if m.get("agent"):
            removed.append(m["agent"])
    lockfile.remove_rule(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed, "entry": rule}


def _install_workflow(entry: dict, force: bool = False,
                      only_agents: Optional[List[str]] = None,
                      scope: str = "user", base=None) -> InstallResult:
    """Materialize a workflow (slash command / subagent) into each enabled agent.

    A verbatim Markdown drop into the agent's ``commands/`` or ``agents/`` dir —
    the slot derived from the source path — with no transformation. With
    ``scope="project"`` the drop lands under the repo (``<repo>/.claude/…``).
    Every drop is recorded so ``uninstall`` removes exactly the files it wrote.
    """
    import hashlib

    from . import gitutil, workflows
    name = entry["name"]
    existing = lockfile.get_workflow(name)
    if existing and not force:
        raise BoostError("%s is already installed" % name,
                        hint="`boost reinstall %s` to force" % name)
    only_agents = preserved_agent_scope(only_agents, existing)

    violations = policy.check_install(entry, len(lockfile.installed()))
    if violations:
        raise BoostError("policy blocks installing %s: %s" % (name, "; ".join(violations)),
                        hint="inspect with `boost policy list`")

    resolved_base = _require_project_base(scope, base, "workflow %s" % name)

    tap = registry.get(entry["tap"])
    source_rel = entry.get("skill_md", "")
    src = tap.path / source_rel
    if not src.is_file():
        raise BoostError("source for workflow %s vanished from tap %s" % (name, tap.name),
                        hint="run `boost update %s`" % tap.name)
    raw = src.read_text(encoding="utf-8", errors="replace")
    slot = workflows.detect_slot(source_rel)

    paths.ensure_dirs()
    materializations: List[dict] = []
    linked: List[str] = []
    for agent, skills_dir in agents.enabled_agents().items():
        if only_agents and agent not in only_agents:
            continue
        path = workflows.workflow_target(skills_dir, slot, name,
                                         base=resolved_base, agent=agent)
        # Project scope writes into the repo; a committed agent dir could be a
        # symlink escaping it (see scopes.ensure_in_base). User scope writes into
        # the user's own ~/.claude, which they control — nothing to guard.
        if resolved_base is not None:
            scopes.ensure_in_base(resolved_base, path)
        path.parent.mkdir(parents=True, exist_ok=True)
        util.atomic_write_text(path, workflows.render(agent, slot, name, raw))
        materializations.append({"agent": agent, "slot": slot, "path": str(path)})
        linked.append(agent)

    # As for rules: an unrecorded materialization is a live slash command that
    # `_uninstall_workflow` — driven by this list — can never remove.
    materializations.extend(_untouched_materializations(existing, linked))

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
        "materializations": materializations,
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))

    res = InstallResult(
        name=name,
        dest=Path(materializations[0]["path"]) if materializations else paths.store_dir(),
        kind="workflow", scan_text=raw)
    res.linked = linked
    res.upgraded = existing is not None
    res.scope = scope
    return res


def _uninstall_workflow(name: str, workflow: dict) -> dict:
    """Remove every file dropped for an installed workflow."""
    removed: List[str] = []
    for m in workflow.get("materializations", []):
        path = Path(m.get("path", ""))
        if path.is_file() or path.is_symlink():
            path.unlink()
        if m.get("agent"):
            removed.append(m["agent"])
    lockfile.remove_workflow(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed, "entry": workflow}


def install_from_path(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None,
                      force: bool = False) -> InstallResult:
    """Install directly from a local directory (used by `boost import`).

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
    paths.ensure_dirs()
    _copy_skill(src_dir, dest)
    res = link_agents(name, only=preserved_agent_scope(only_agents, existing))
    res.score, _ = util.score_skill(dest)
    res.mcp_servers = declared_mcp_servers(dest)
    now = util.now_iso()
    lockfile.set_skill(name, {
        "version": str(meta.get("version") or "0.0.0"),
        "tap": tap_label,
        "source_dir": str(src_dir),
        "commit": "",
        "sha256": util.sha256_dir(dest),
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        # Was hardcoded False, which did not merely skip the pin check — a
        # re-import silently CLEARED an existing pin. install() preserves it.
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        # What is on disk, not what this run linked — see install().
        "agents": linked_agents(name),
        # `boost import --agent ...` narrows the same way `install` does, so it
        # has to record the same declaration — otherwise the links are narrow
        # but sync sees no scope and widens them right back.
        "only_agents": declared_agent_scope(only_agents, existing),
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def uninstall(name: str) -> dict:
    """Uninstall ``name`` whatever its kind (skill, rule, workflow).

    Reverses everything the install wrote and drops the lock entry;
    returns {name, unlinked, entry}. Raises BoostError if not installed.
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
    return {"name": name, "unlinked": removed_links, "entry": entry}


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


def sync_plan() -> Dict[str, list]:
    """Compare lock file <-> store <-> agent symlinks.

    Returns {missing_store, missing_links, stale_links, orphaned_store}
      missing_store:  lock entries whose store dir is gone
      missing_links:  (skill, agent) pairs that should be linked but aren't
      stale_links:    paths in agent dirs that are broken/unmanaged symlinks
      orphaned_store: store dirs not present in the lock file
      out_of_scope_links: (skill, agent) pairs linked outside a declared
                      ``--agent`` narrowing — reported, never auto-removed
    """
    lock = lockfile.installed()
    plan: dict[str, list] = {"missing_store": [], "missing_links": [],
            "stale_links": [], "orphaned_store": [],
            "missing_materializations": [], "out_of_scope_links": []}
    for name, entry in lock.items():
        sdir = skill_store_dir(name)
        if not sdir.is_dir():
            plan["missing_store"].append(name)
            continue
        if entry.get("quarantined"):
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
            link = adir / name
            if not link.is_symlink() or not link.exists():
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
        for child in store_root.iterdir():
            if child.is_dir() and child.name not in lock:
                plan["orphaned_store"].append(child.name)
    for adir in agents.enabled_agents().values():
        if not adir.is_dir():
            continue
        for link in adir.iterdir():
            # Ownership first, for broken links too: the old test short-circuited
            # on `not link.exists()`, so any dangling symlink a user happened to
            # keep in ~/.claude/skills was swept up by `boost sync`.
            if (link.is_symlink() and points_into_store(link)
                    and (not link.exists() or link.name not in lock)):
                plan["stale_links"].append(str(link))
    # Rules/workflows don't live in the store — they materialize into agent dirs.
    # A materialization whose file (or CLAUDE.md block) is gone can be repaired
    # by re-materializing from the tap, same as a missing skill store dir.
    for name, entry in lockfile.installed_rules().items():
        if any(not _rule_materialization_ok(name, m)
               for m in entry.get("materializations") or []):
            plan["missing_materializations"].append(("rule", name))
    for name, entry in lockfile.installed_workflows().items():
        if any(not Path(m.get("path", "")).is_file()
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


def prune_out_of_scope_links(plan: Dict[str, list]) -> List[str]:
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


def sync_apply(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["missing_links"]:
        res = link_agents(name, only=[agent])
        if agent in res.linked:
            actions.append("linked %s → %s" % (name, agent))
    for path in plan["stale_links"]:
        p = Path(path)
        if p.is_symlink():
            p.unlink()
            actions.append("removed stale link %s" % path)
    for name in plan["missing_store"]:
        entry = lockfile.get_skill(name) or {}
        tap_name = entry.get("tap")
        restored = False
        if tap_name and tap_name != "local":
            try:  # noqa: FURB107 - per-item resilience in a loop (see PERF203)
                from . import catalog
                matches = [e for e in catalog.find(name) if e["tap"] == tap_name]
                if matches:
                    install(matches[0], force=True)
                    actions.append("reinstalled missing %s from %s" % (name, tap_name))
                    restored = True
            except BoostError:
                pass
        if not restored:
            lockfile.remove_skill(name)
            actions.append("dropped %s from lock (store dir missing, source gone)" % name)
    for kind, name in plan.get("missing_materializations", []):
        getter = lockfile.get_rule if kind == "rule" else lockfile.get_workflow
        entry = getter(name) or {}
        tap_name = entry.get("tap")
        if tap_name and tap_name != "local":
            try:  # noqa: FURB107 - per-item resilience in a loop (see PERF203)
                from . import catalog
                matches = [e for e in catalog.find(name)
                           if e["tap"] == tap_name and e.get("kind", "skill") == kind]
                if matches:
                    # preserve the original scope/base so a project rule repairs
                    # into its repo, not wherever sync happens to run.
                    install(matches[0], force=True,
                            scope=entry.get("scope", "user"), base=entry.get("base"))
                    actions.append("re-materialized %s %s from %s"
                                   % (kind, name, tap_name))
                    continue
            except BoostError:
                pass
        actions.append("%s %s has a missing materialization but its source is "
                       "gone — run `boost update` or reinstall" % (kind, name))
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions
