"""The canonical store (~/.agents/skills) and agent symlinks.

install():  copy skill dir from a tap clone -> store, symlink into every
            enabled agent dir, record in the lock file, log to the journal.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..errors import BoostError
from . import agents, journal, lockfile, paths, policy, registry, util


@dataclass
class InstallResult:
    name: str
    dest: Path
    linked: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    score: int = 0
    upgraded: bool = False


def skill_store_dir(name: str) -> Path:
    return paths.store_dir() / name


def installed() -> dict:
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
    removed = []
    for agent, adir in agents.enabled_agents().items():
        link = adir / name
        if link.is_symlink():
            link.unlink()
            removed.append(agent)
    return removed


def _copy_skill(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"))


def install(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
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
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
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
    plan = {"missing_store": [], "missing_links": [],
            "stale_links": [], "orphaned_store": []}
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
    for agent, adir in agents.enabled_agents().items():
        if not adir.is_dir():
            continue
        for link in adir.iterdir():
            if link.is_symlink():
                points_into_store = str(paths.store_dir()) in str(
                    link.resolve() if link.exists() else link.readlink())
                if not link.exists() or (points_into_store and link.name not in lock):
                    plan["stale_links"].append(str(link))
    return plan


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
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions
