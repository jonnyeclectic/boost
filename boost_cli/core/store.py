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
import tempfile
from dataclasses import dataclass, field
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


def skill_store_dir(name: str) -> Path:
    """Resolve ``name`` to its dir under the canonical store.

    Raises BoostError unless the name is a safe path component.
    """
    if not util.is_safe_component(name):
        raise BoostError("invalid skill name %r" % name)
    return paths.store_dir() / name


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
    """
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
    if entry is not None and entry.get("sidelined_by"):
        del entry["sidelined_by"]
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
            scope: str = "user", base=None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict.

    ``scope`` is ``"user"`` (default — the canonical store, symlinked into the
    agent's user config dirs) or ``"project"`` (real directories inside the
    current repo). Every kind honors it.
    """
    scopes.check_scope(scope)
    _refuse_self_installing(entry)
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
                           only_agents: list[str] | None = None,
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
    _enforce_capability_policy(name, src)
    raw = src.read_text(encoding="utf-8", errors="replace")
    meta, body = frontmatter.parse(raw)
    claude_body = rules.render_claude_body(str(meta.get("name") or name), body)

    paths.ensure_dirs()
    materializations: list[dict] = []
    linked: list[str] = []
    for agent, skills_dir in agents.materializing_agents(resolved_base).items():
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
            # Hash what `rules.read_block` will read back (the stripped body),
            # so `boost verify` can tell an edited managed block from ours.
            written = claude_body.strip("\n")
        else:
            util.atomic_write_text(path, raw)
            written = raw
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
        # Same governance contract as a skill entry: a pin survives a forced
        # reinstall, quarantine does not — the reinstall just re-materialized
        # the content, so a surviving flag would be a lie.
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
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
    removed: list[str] = []
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
    stash: list[dict] = []
    affected: list[str] = []
    for m in entry.get("materializations") or []:
        path = Path(m.get("path", ""))
        content: str | None = None
        if m.get("mode") == rules.MODE_CLAUDE:
            if path.exists():
                content = rules.read_block(
                    path.read_text(encoding="utf-8"), name)
        elif path.is_file():
            content = path.read_text(encoding="utf-8")
        if content is None:
            content = prior.get(m.get("path"))
        stash.append({**m, "content": content})
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
    _enforce_capability_policy(name, src)
    raw = src.read_text(encoding="utf-8", errors="replace")
    slot = workflows.detect_slot(source_rel)

    paths.ensure_dirs()
    materializations: list[dict] = []
    linked: list[str] = []
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
        path.parent.mkdir(parents=True, exist_ok=True)
        rendered = workflows.render(agent, slot, name, raw)
        util.atomic_write_text(path, rendered)
        materializations.append({
            "agent": agent, "slot": slot, "path": str(path),
            "sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest()})
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
        # Same governance contract as a skill entry: a pin survives a forced
        # reinstall, quarantine does not.
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
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
    removed: list[str] = []
    for m in workflow.get("materializations", []):
        path = Path(m.get("path", ""))
        if path.is_file() or path.is_symlink():
            path.unlink()
        if m.get("agent"):
            removed.append(m["agent"])
    lockfile.remove_workflow(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed, "entry": workflow, "kind": "workflow"}


def install_from_path(src_dir: Path, name: str | None = None,
                      tap_label: str = "local",
                      only_agents: list[str] | None = None,
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
    plan: dict[str, list] = {"missing_store": [], "missing_links": [],
            "blocked_links": [], "stale_links": [], "orphaned_store": [],
            "missing_materializations": [], "out_of_scope_links": []}
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
        if not sdir.is_dir() or not (sdir / "SKILL.md").is_file():
            plan["missing_store"].append(name)
            continue
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
            link = adir / name
            # A symlink is boost's to replace even when it dangles; anything
            # else that exists is someone else's file and stays put.
            if link.is_symlink():
                if not link.exists():
                    plan["missing_links"].append((name, agent))
            elif link.exists():
                plan["blocked_links"].append((name, agent, str(link)))
            else:
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
        # A quarantined rule's materializations are ABSENT BY DESIGN — the
        # stash holds them. Repairing here would re-arm what quarantine
        # disarmed, making `boost sync` an accidental release.
        if entry.get("quarantined"):
            continue
        if any(not _rule_materialization_ok(name, m)
               for m in entry.get("materializations") or []):
            plan["missing_materializations"].append(("rule", name))
    for name, entry in lockfile.installed_workflows().items():
        if entry.get("quarantined"):
            continue
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


def sync_apply(plan: dict[str, list]) -> list[str]:
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
                cat_entry, warning = catalog.select_lock_source(matches, entry)
                if warning:
                    actions.append(warning)
                if cat_entry:
                    if _pinned_repair_blocked(entry, _skill_source_sha(cat_entry)):
                        actions.append(
                            "%s is pinned and its tap source has moved — repair "
                            "declined (unpin, or `boost reinstall %s` to accept "
                            "the new content)" % (name, name))
                        continue
                    install(cat_entry, force=True)
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
                cat_entry, warning = catalog.select_lock_source(matches, entry)
                if warning:
                    actions.append(warning)
                if cat_entry:
                    if _pinned_repair_blocked(
                            entry, _source_text_sha(tap_name, cat_entry)):
                        actions.append(
                            "%s %s is pinned and its tap source has moved — "
                            "repair declined (unpin, or `boost reinstall %s` to "
                            "accept the new content)" % (kind, name, name))
                        continue
                    # preserve the original scope/base so a project rule repairs
                    # into its repo, not wherever sync happens to run.
                    install(cat_entry, force=True,
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
