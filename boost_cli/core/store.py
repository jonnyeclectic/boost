"""The canonical store (~/.agents/skills) and agent symlinks.

install():  copy skill dir from a tap clone -> store, symlink into every
            enabled agent dir, record in the lock file, log to the journal.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..errors import BoostError
from . import (agents, journal, lockfile, paths, policy, projectlock, registry,
               scopes, util)


@dataclass
class InstallResult:
    """Outcome of one install: dest, linked agents, conflicts, kind."""
    name: str
    dest: Path
    linked: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    score: int = 0
    upgraded: bool = False
    kind: str = "skill"
    scope: str = "user"   # "user" or "project" — where a rule/workflow landed
    # For rules/workflows the installed content is a single file (or a merged
    # CLAUDE.md block), not a SKILL.md tree — carry the raw source so the caller
    # scans exactly what it installed instead of a non-existent SKILL.md.
    scan_text: Optional[str] = None


def skill_store_dir(name: str) -> Path:
    """Resolve ``name`` to its dir under the canonical store.

    Raises BoostError unless the name is a safe path component.
    """
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name in {".", ".."}:
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
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = skill_store_dir(name)
    for agent, adir in agents.enabled_agents().items():
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


def unlink_agents(name: str) -> List[str]:
    """Remove the ``name`` symlink from every enabled agent dir.

    Returns the agents unlinked; non-symlink files are left alone.
    """
    removed = []
    for agent, adir in agents.enabled_agents().items():
        link = adir / name
        if link.is_symlink():
            link.unlink()
            removed.append(agent)
    return removed


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
        if dest.exists():
            backup = staged.with_name(staged.name + ".old")
            os.replace(dest, backup)      # move the old copy aside (atomic)
        os.replace(staged, dest)          # swap the new copy in (atomic)
    except BaseException:
        if backup is not None and not dest.exists():
            os.replace(backup, dest)      # swap-in failed: restore the original
        shutil.rmtree(staged, ignore_errors=True)
        if backup is not None and backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        raise
    if backup is not None:
        shutil.rmtree(backup, ignore_errors=True)


def _resolve_base(scope: str, base) -> Optional[Path]:
    """Directory a project-scoped install materializes under (the repo), or None
    for user scope.

    Delegates to :func:`scopes.resolve_base`, which walks up for the nearest
    project root — running this from ``src/deep/nested`` must write into the
    repo, not scatter a ``.claude/`` three directories down.
    """
    return scopes.resolve_base(scope, base)


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
    dest = skill_store_dir(name)
    paths.ensure_dirs()
    _copy_skill(src, dest)

    res = link_agents(name, only=only_agents)
    res.upgraded = existing is not None
    res.score, _ = util.score_skill(dest)

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
        "agents": res.linked,
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
    resolved_base = _resolve_base(scopes.SCOPE_PROJECT, base)
    if resolved_base is None:                     # unreachable via resolve_base
        raise BoostError("could not resolve a project directory for %s" % name)

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
    targets = [(agent, scopes.skill_target(skills_dir, name, base=resolved_base))
               for agent, skills_dir in agents.enabled_agents().items()
               if not only_agents or agent in only_agents]

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
    kept = [m for m in (existing or {}).get("materializations") or []
            if m.get("agent") not in linked]
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
    journal.log("uninstall", name, scope=scopes.SCOPE_PROJECT)
    return {"name": name, "unlinked": removed, "entry": entry,
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
    for name in sorted({n for n, _agent in plan.get("missing", [])}):
        entry = projectlock.get_skill(resolved_base, name) or {}
        tap_name = entry.get("tap")
        if tap_name and tap_name != "local":
            try:
                from . import catalog
                matches = [e for e in catalog.find(name)
                           if e["tap"] == tap_name and e.get("kind", "skill") == "skill"]
                if matches:
                    install(matches[0], force=True, scope=scopes.SCOPE_PROJECT,
                            base=resolved_base)
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

    violations = policy.check_install(entry, len(lockfile.installed()))
    if violations:
        raise BoostError("policy blocks installing %s: %s" % (name, "; ".join(violations)),
                        hint="inspect with `boost policy list`")

    tap = registry.get(entry["tap"])
    src = tap.path / entry.get("skill_md", "")
    if not src.is_file():
        raise BoostError("source for rule %s vanished from tap %s" % (name, tap.name),
                        hint="run `boost update %s`" % tap.name)
    raw = src.read_text(encoding="utf-8", errors="replace")
    meta, body = frontmatter.parse(raw)
    claude_body = rules.render_claude_body(str(meta.get("name") or name), body)

    resolved_base = _resolve_base(scope, base)
    paths.ensure_dirs()
    materializations: List[dict] = []
    linked: List[str] = []
    for agent, skills_dir in agents.enabled_agents().items():
        if only_agents and agent not in only_agents:
            continue
        mode, path = rules.rule_target(agent, skills_dir, name, base=resolved_base)
        path.parent.mkdir(parents=True, exist_ok=True)
        if mode == rules.MODE_CLAUDE:
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            util.atomic_write_text(path, rules.merge_block(current, name, claude_body))
        else:
            util.atomic_write_text(path, raw)
        materializations.append({"agent": agent, "mode": mode, "path": str(path)})
        linked.append(agent)

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
    raw = src.read_text(encoding="utf-8", errors="replace")
    slot = workflows.detect_slot(source_rel)

    resolved_base = _resolve_base(scope, base)
    paths.ensure_dirs()
    materializations: List[dict] = []
    linked: List[str] = []
    for agent, skills_dir in agents.enabled_agents().items():
        if only_agents and agent not in only_agents:
            continue
        path = workflows.workflow_target(skills_dir, slot, name, base=resolved_base)
        path.parent.mkdir(parents=True, exist_ok=True)
        util.atomic_write_text(path, raw)
        materializations.append({"agent": agent, "slot": slot, "path": str(path)})
        linked.append(agent)

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
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding="utf-8", errors="replace"))
    name = name or str(meta.get("name") or src_dir.name)
    dest = skill_store_dir(name)
    paths.ensure_dirs()
    _copy_skill(src_dir, dest)
    res = link_agents(name, only=only_agents)
    res.score, _ = util.score_skill(dest)
    now = util.now_iso()
    existing = lockfile.get_skill(name)
    lockfile.set_skill(name, {
        "version": str(meta.get("version") or "0.0.0"),
        "tap": tap_label,
        "source_dir": str(src_dir),
        "commit": "",
        "sha256": util.sha256_dir(dest),
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        "pinned": False,
        "quarantined": False,
        "agents": res.linked,
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


def sync_plan() -> Dict[str, list]:
    """Compare lock file <-> store <-> agent symlinks.

    Returns {missing_store, missing_links, stale_links, orphaned_store}
      missing_store:  lock entries whose store dir is gone
      missing_links:  (skill, agent) pairs that should be linked but aren't
      stale_links:    paths in agent dirs that are broken/unmanaged symlinks
      orphaned_store: store dirs not present in the lock file
    """
    lock = lockfile.installed()
    plan: dict[str, list] = {"missing_store": [], "missing_links": [],
            "stale_links": [], "orphaned_store": [],
            "missing_materializations": []}
    for name, entry in lock.items():
        sdir = skill_store_dir(name)
        if not sdir.is_dir():
            plan["missing_store"].append(name)
            continue
        if entry.get("quarantined"):
            continue
        for agent, adir in agents.enabled_agents().items():
            link = adir / name
            if not link.is_symlink() or not link.exists():
                plan["missing_links"].append((name, agent))
    store_root = paths.store_dir()
    if store_root.is_dir():
        for child in store_root.iterdir():
            if child.is_dir() and child.name not in lock:
                plan["orphaned_store"].append(child.name)
    for adir in agents.enabled_agents().values():
        if not adir.is_dir():
            continue
        for link in adir.iterdir():
            if link.is_symlink():
                points_into_store = str(paths.store_dir()) in str(
                    link.resolve() if link.exists() else link.readlink())
                if not link.exists() or (points_into_store and link.name not in lock):
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
            try:
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
            try:
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
