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


from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated, MutantDict


@dataclass
class InstallResult:
    name: str
    dest: Path
    linked: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    score: int = 0
    upgraded: bool = False
mutants_x_skill_store_dir__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_skill_store_dir__mutmut)
def skill_store_dir(name: str) -> Path:
    return paths.store_dir() / name


def x_skill_store_dir__mutmut_orig(name: str) -> Path:
    return paths.store_dir() / name


def x_skill_store_dir__mutmut_1(name: str) -> Path:
    return paths.store_dir() * name

mutants_x_skill_store_dir__mutmut['_mutmut_orig'] = x_skill_store_dir__mutmut_orig # type: ignore # mutmut generated
mutants_x_skill_store_dir__mutmut['x_skill_store_dir__mutmut_1'] = x_skill_store_dir__mutmut_1 # type: ignore # mutmut generated


def installed() -> dict:
    return lockfile.installed()
mutants_x_source_dir_for__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_source_dir_for__mutmut)
def source_dir_for(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_orig(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_1(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = None
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_2(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(None)
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_3(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["XXtapXX"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_4(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["TAP"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_5(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = None
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_6(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["XXrel_dirXX"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_7(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["REL_DIR"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_8(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] != "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_9(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "XX.XX" else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_10(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path * entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_11(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["XXrel_dirXX"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_12(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["REL_DIR"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_13(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_14(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src * "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_15(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "XXSKILL.mdXX").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_16(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "skill.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_17(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.MD").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_18(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError(None,
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_19(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint=None)
    return src


def x_source_dir_for__mutmut_20(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError(hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_21(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        )
    return src


def x_source_dir_for__mutmut_22(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" / (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_23(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("XXsource for %s vanished from tap %sXX" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_24(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("SOURCE FOR %S VANISHED FROM TAP %S" % (entry["name"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_25(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["XXnameXX"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_26(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["NAME"], tap.name),
                        hint="run `boost update %s`" % tap.name)
    return src


def x_source_dir_for__mutmut_27(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="run `boost update %s`" / tap.name)
    return src


def x_source_dir_for__mutmut_28(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="XXrun `boost update %s`XX" % tap.name)
    return src


def x_source_dir_for__mutmut_29(entry: dict) -> Path:
    """Absolute path of a catalog entry's skill dir inside its tap clone."""
    tap = registry.get(entry["tap"])
    src = tap.path if entry["rel_dir"] == "." else tap.path / entry["rel_dir"]
    if not (src / "SKILL.md").exists():
        raise BoostError("source for %s vanished from tap %s" % (entry["name"], tap.name),
                        hint="RUN `BOOST UPDATE %S`" % tap.name)
    return src

mutants_x_source_dir_for__mutmut['_mutmut_orig'] = x_source_dir_for__mutmut_orig # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_1'] = x_source_dir_for__mutmut_1 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_2'] = x_source_dir_for__mutmut_2 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_3'] = x_source_dir_for__mutmut_3 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_4'] = x_source_dir_for__mutmut_4 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_5'] = x_source_dir_for__mutmut_5 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_6'] = x_source_dir_for__mutmut_6 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_7'] = x_source_dir_for__mutmut_7 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_8'] = x_source_dir_for__mutmut_8 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_9'] = x_source_dir_for__mutmut_9 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_10'] = x_source_dir_for__mutmut_10 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_11'] = x_source_dir_for__mutmut_11 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_12'] = x_source_dir_for__mutmut_12 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_13'] = x_source_dir_for__mutmut_13 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_14'] = x_source_dir_for__mutmut_14 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_15'] = x_source_dir_for__mutmut_15 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_16'] = x_source_dir_for__mutmut_16 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_17'] = x_source_dir_for__mutmut_17 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_18'] = x_source_dir_for__mutmut_18 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_19'] = x_source_dir_for__mutmut_19 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_20'] = x_source_dir_for__mutmut_20 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_21'] = x_source_dir_for__mutmut_21 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_22'] = x_source_dir_for__mutmut_22 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_23'] = x_source_dir_for__mutmut_23 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_24'] = x_source_dir_for__mutmut_24 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_25'] = x_source_dir_for__mutmut_25 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_26'] = x_source_dir_for__mutmut_26 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_27'] = x_source_dir_for__mutmut_27 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_28'] = x_source_dir_for__mutmut_28 # type: ignore # mutmut generated
mutants_x_source_dir_for__mutmut['x_source_dir_for__mutmut_29'] = x_source_dir_for__mutmut_29 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_link_agents__mutmut)
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


def x_link_agents__mutmut_orig(name: str, only: Optional[List[str]] = None) -> InstallResult:
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


def x_link_agents__mutmut_1(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = None
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


def x_link_agents__mutmut_2(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=None, dest=skill_store_dir(name))
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


def x_link_agents__mutmut_3(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=None)
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


def x_link_agents__mutmut_4(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(dest=skill_store_dir(name))
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


def x_link_agents__mutmut_5(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, )
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


def x_link_agents__mutmut_6(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=skill_store_dir(None))
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


def x_link_agents__mutmut_7(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = None
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


def x_link_agents__mutmut_8(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = skill_store_dir(None)
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


def x_link_agents__mutmut_9(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = skill_store_dir(name)
    for agent, adir in agents.enabled_agents().items():
        if only or agent not in only:
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


def x_link_agents__mutmut_10(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = skill_store_dir(name)
    for agent, adir in agents.enabled_agents().items():
        if only and agent in only:
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


def x_link_agents__mutmut_11(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = skill_store_dir(name)
    for agent, adir in agents.enabled_agents().items():
        if only and agent not in only:
            break
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


def x_link_agents__mutmut_12(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = skill_store_dir(name)
    for agent, adir in agents.enabled_agents().items():
        if only and agent not in only:
            continue
        adir.mkdir(parents=None, exist_ok=True)
        link = adir / name
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            res.conflicts.append(str(link))
            continue
        link.symlink_to(target)
        res.linked.append(agent)
    return res


def x_link_agents__mutmut_13(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = skill_store_dir(name)
    for agent, adir in agents.enabled_agents().items():
        if only and agent not in only:
            continue
        adir.mkdir(parents=True, exist_ok=None)
        link = adir / name
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            res.conflicts.append(str(link))
            continue
        link.symlink_to(target)
        res.linked.append(agent)
    return res


def x_link_agents__mutmut_14(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = skill_store_dir(name)
    for agent, adir in agents.enabled_agents().items():
        if only and agent not in only:
            continue
        adir.mkdir(exist_ok=True)
        link = adir / name
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            res.conflicts.append(str(link))
            continue
        link.symlink_to(target)
        res.linked.append(agent)
    return res


def x_link_agents__mutmut_15(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = skill_store_dir(name)
    for agent, adir in agents.enabled_agents().items():
        if only and agent not in only:
            continue
        adir.mkdir(parents=True, )
        link = adir / name
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            res.conflicts.append(str(link))
            continue
        link.symlink_to(target)
        res.linked.append(agent)
    return res


def x_link_agents__mutmut_16(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = skill_store_dir(name)
    for agent, adir in agents.enabled_agents().items():
        if only and agent not in only:
            continue
        adir.mkdir(parents=False, exist_ok=True)
        link = adir / name
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            res.conflicts.append(str(link))
            continue
        link.symlink_to(target)
        res.linked.append(agent)
    return res


def x_link_agents__mutmut_17(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = skill_store_dir(name)
    for agent, adir in agents.enabled_agents().items():
        if only and agent not in only:
            continue
        adir.mkdir(parents=True, exist_ok=False)
        link = adir / name
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            res.conflicts.append(str(link))
            continue
        link.symlink_to(target)
        res.linked.append(agent)
    return res


def x_link_agents__mutmut_18(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = skill_store_dir(name)
    for agent, adir in agents.enabled_agents().items():
        if only and agent not in only:
            continue
        adir.mkdir(parents=True, exist_ok=True)
        link = None
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            res.conflicts.append(str(link))
            continue
        link.symlink_to(target)
        res.linked.append(agent)
    return res


def x_link_agents__mutmut_19(name: str, only: Optional[List[str]] = None) -> InstallResult:
    """Symlink store/<name> into each enabled agent dir. Returns result with
    .linked (agent names) and .conflicts (paths that were real files/dirs)."""
    res = InstallResult(name=name, dest=skill_store_dir(name))
    target = skill_store_dir(name)
    for agent, adir in agents.enabled_agents().items():
        if only and agent not in only:
            continue
        adir.mkdir(parents=True, exist_ok=True)
        link = adir * name
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            res.conflicts.append(str(link))
            continue
        link.symlink_to(target)
        res.linked.append(agent)
    return res


def x_link_agents__mutmut_20(name: str, only: Optional[List[str]] = None) -> InstallResult:
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
            res.conflicts.append(None)
            continue
        link.symlink_to(target)
        res.linked.append(agent)
    return res


def x_link_agents__mutmut_21(name: str, only: Optional[List[str]] = None) -> InstallResult:
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
            res.conflicts.append(str(None))
            continue
        link.symlink_to(target)
        res.linked.append(agent)
    return res


def x_link_agents__mutmut_22(name: str, only: Optional[List[str]] = None) -> InstallResult:
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
            break
        link.symlink_to(target)
        res.linked.append(agent)
    return res


def x_link_agents__mutmut_23(name: str, only: Optional[List[str]] = None) -> InstallResult:
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
        link.symlink_to(None)
        res.linked.append(agent)
    return res


def x_link_agents__mutmut_24(name: str, only: Optional[List[str]] = None) -> InstallResult:
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
        res.linked.append(None)
    return res

mutants_x_link_agents__mutmut['_mutmut_orig'] = x_link_agents__mutmut_orig # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_1'] = x_link_agents__mutmut_1 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_2'] = x_link_agents__mutmut_2 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_3'] = x_link_agents__mutmut_3 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_4'] = x_link_agents__mutmut_4 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_5'] = x_link_agents__mutmut_5 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_6'] = x_link_agents__mutmut_6 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_7'] = x_link_agents__mutmut_7 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_8'] = x_link_agents__mutmut_8 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_9'] = x_link_agents__mutmut_9 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_10'] = x_link_agents__mutmut_10 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_11'] = x_link_agents__mutmut_11 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_12'] = x_link_agents__mutmut_12 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_13'] = x_link_agents__mutmut_13 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_14'] = x_link_agents__mutmut_14 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_15'] = x_link_agents__mutmut_15 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_16'] = x_link_agents__mutmut_16 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_17'] = x_link_agents__mutmut_17 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_18'] = x_link_agents__mutmut_18 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_19'] = x_link_agents__mutmut_19 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_20'] = x_link_agents__mutmut_20 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_21'] = x_link_agents__mutmut_21 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_22'] = x_link_agents__mutmut_22 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_23'] = x_link_agents__mutmut_23 # type: ignore # mutmut generated
mutants_x_link_agents__mutmut['x_link_agents__mutmut_24'] = x_link_agents__mutmut_24 # type: ignore # mutmut generated
mutants_x_unlink_agents__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_unlink_agents__mutmut)
def unlink_agents(name: str) -> List[str]:
    removed = []
    for agent, adir in agents.enabled_agents().items():
        link = adir / name
        if link.is_symlink():
            link.unlink()
            removed.append(agent)
    return removed


def x_unlink_agents__mutmut_orig(name: str) -> List[str]:
    removed = []
    for agent, adir in agents.enabled_agents().items():
        link = adir / name
        if link.is_symlink():
            link.unlink()
            removed.append(agent)
    return removed


def x_unlink_agents__mutmut_1(name: str) -> List[str]:
    removed = None
    for agent, adir in agents.enabled_agents().items():
        link = adir / name
        if link.is_symlink():
            link.unlink()
            removed.append(agent)
    return removed


def x_unlink_agents__mutmut_2(name: str) -> List[str]:
    removed = []
    for agent, adir in agents.enabled_agents().items():
        link = None
        if link.is_symlink():
            link.unlink()
            removed.append(agent)
    return removed


def x_unlink_agents__mutmut_3(name: str) -> List[str]:
    removed = []
    for agent, adir in agents.enabled_agents().items():
        link = adir * name
        if link.is_symlink():
            link.unlink()
            removed.append(agent)
    return removed


def x_unlink_agents__mutmut_4(name: str) -> List[str]:
    removed = []
    for agent, adir in agents.enabled_agents().items():
        link = adir / name
        if link.is_symlink():
            link.unlink()
            removed.append(None)
    return removed

mutants_x_unlink_agents__mutmut['_mutmut_orig'] = x_unlink_agents__mutmut_orig # type: ignore # mutmut generated
mutants_x_unlink_agents__mutmut['x_unlink_agents__mutmut_1'] = x_unlink_agents__mutmut_1 # type: ignore # mutmut generated
mutants_x_unlink_agents__mutmut['x_unlink_agents__mutmut_2'] = x_unlink_agents__mutmut_2 # type: ignore # mutmut generated
mutants_x_unlink_agents__mutmut['x_unlink_agents__mutmut_3'] = x_unlink_agents__mutmut_3 # type: ignore # mutmut generated
mutants_x_unlink_agents__mutmut['x_unlink_agents__mutmut_4'] = x_unlink_agents__mutmut_4 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x__copy_skill__mutmut)
def _copy_skill(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"))


def x__copy_skill__mutmut_orig(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"))


def x__copy_skill__mutmut_1(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(None)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"))


def x__copy_skill__mutmut_2(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(None, dest,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"))


def x__copy_skill__mutmut_3(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, None,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"))


def x__copy_skill__mutmut_4(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=None)


def x__copy_skill__mutmut_5(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(dest,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"))


def x__copy_skill__mutmut_6(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"))


def x__copy_skill__mutmut_7(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    )


def x__copy_skill__mutmut_8(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns(None, "__pycache__", ".DS_Store"))


def x__copy_skill__mutmut_9(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns(".git", None, ".DS_Store"))


def x__copy_skill__mutmut_10(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", None))


def x__copy_skill__mutmut_11(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))


def x__copy_skill__mutmut_12(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns(".git", ".DS_Store"))


def x__copy_skill__mutmut_13(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", ))


def x__copy_skill__mutmut_14(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns("XX.gitXX", "__pycache__", ".DS_Store"))


def x__copy_skill__mutmut_15(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns(".GIT", "__pycache__", ".DS_Store"))


def x__copy_skill__mutmut_16(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns(".git", "XX__pycache__XX", ".DS_Store"))


def x__copy_skill__mutmut_17(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns(".git", "__PYCACHE__", ".DS_Store"))


def x__copy_skill__mutmut_18(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "XX.DS_StoreXX"))


def x__copy_skill__mutmut_19(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", ".ds_store"))


def x__copy_skill__mutmut_20(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_STORE"))

mutants_x__copy_skill__mutmut['_mutmut_orig'] = x__copy_skill__mutmut_orig # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_1'] = x__copy_skill__mutmut_1 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_2'] = x__copy_skill__mutmut_2 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_3'] = x__copy_skill__mutmut_3 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_4'] = x__copy_skill__mutmut_4 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_5'] = x__copy_skill__mutmut_5 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_6'] = x__copy_skill__mutmut_6 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_7'] = x__copy_skill__mutmut_7 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_8'] = x__copy_skill__mutmut_8 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_9'] = x__copy_skill__mutmut_9 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_10'] = x__copy_skill__mutmut_10 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_11'] = x__copy_skill__mutmut_11 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_12'] = x__copy_skill__mutmut_12 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_13'] = x__copy_skill__mutmut_13 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_14'] = x__copy_skill__mutmut_14 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_15'] = x__copy_skill__mutmut_15 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_16'] = x__copy_skill__mutmut_16 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_17'] = x__copy_skill__mutmut_17 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_18'] = x__copy_skill__mutmut_18 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_19'] = x__copy_skill__mutmut_19 # type: ignore # mutmut generated
mutants_x__copy_skill__mutmut['x__copy_skill__mutmut_20'] = x__copy_skill__mutmut_20 # type: ignore # mutmut generated
mutants_x_install__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_install__mutmut)
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


def x_install__mutmut_orig(entry: dict, force: bool = False,
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


def x_install__mutmut_1(entry: dict, force: bool = True,
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


def x_install__mutmut_2(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = None
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


def x_install__mutmut_3(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["XXnameXX"]
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


def x_install__mutmut_4(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["NAME"]
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


def x_install__mutmut_5(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = None
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


def x_install__mutmut_6(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(None)
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


def x_install__mutmut_7(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") or not force:
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


def x_install__mutmut_8(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing or existing.get("pinned") and not force:
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


def x_install__mutmut_9(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get(None) and not force:
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


def x_install__mutmut_10(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("XXpinnedXX") and not force:
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


def x_install__mutmut_11(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("PINNED") and not force:
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


def x_install__mutmut_12(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and force:
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


def x_install__mutmut_13(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError(None, hint="`boost unpin %s` first" % name)
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


def x_install__mutmut_14(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint=None)
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


def x_install__mutmut_15(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError(hint="`boost unpin %s` first" % name)
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


def x_install__mutmut_16(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, )
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


def x_install__mutmut_17(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" / name, hint="`boost unpin %s` first" % name)
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


def x_install__mutmut_18(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("XX%s is pinnedXX" % name, hint="`boost unpin %s` first" % name)
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


def x_install__mutmut_19(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%S IS PINNED" % name, hint="`boost unpin %s` first" % name)
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


def x_install__mutmut_20(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" / name)
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


def x_install__mutmut_21(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="XX`boost unpin %s` firstXX" % name)
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


def x_install__mutmut_22(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`BOOST UNPIN %S` FIRST" % name)
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


def x_install__mutmut_23(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing or not force:
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


def x_install__mutmut_24(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and force:
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


def x_install__mutmut_25(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError(None,
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


def x_install__mutmut_26(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" % (name, existing.get("version")),
                        hint=None)

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


def x_install__mutmut_27(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError(hint="`boost reinstall %s` to force, `boost update` to upgrade" % name)

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


def x_install__mutmut_28(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" % (name, existing.get("version")),
                        )

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


def x_install__mutmut_29(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" / (name, existing.get("version")),
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


def x_install__mutmut_30(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("XX%s is already installed (v%s)XX" % (name, existing.get("version")),
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


def x_install__mutmut_31(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%S IS ALREADY INSTALLED (V%S)" % (name, existing.get("version")),
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


def x_install__mutmut_32(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" % (name, existing.get(None)),
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


def x_install__mutmut_33(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" % (name, existing.get("XXversionXX")),
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


def x_install__mutmut_34(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" % (name, existing.get("VERSION")),
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


def x_install__mutmut_35(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" % (name, existing.get("version")),
                        hint="`boost reinstall %s` to force, `boost update` to upgrade" / name)

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


def x_install__mutmut_36(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" % (name, existing.get("version")),
                        hint="XX`boost reinstall %s` to force, `boost update` to upgradeXX" % name)

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


def x_install__mutmut_37(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" % (name, existing.get("version")),
                        hint="`BOOST REINSTALL %S` TO FORCE, `BOOST UPDATE` TO UPGRADE" % name)

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


def x_install__mutmut_38(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" % (name, existing.get("version")),
                        hint="`boost reinstall %s` to force, `boost update` to upgrade" % name)

    violations = None
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


def x_install__mutmut_39(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" % (name, existing.get("version")),
                        hint="`boost reinstall %s` to force, `boost update` to upgrade" % name)

    violations = policy.check_install(None, len(lockfile.installed()))
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


def x_install__mutmut_40(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" % (name, existing.get("version")),
                        hint="`boost reinstall %s` to force, `boost update` to upgrade" % name)

    violations = policy.check_install(entry, None)
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


def x_install__mutmut_41(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" % (name, existing.get("version")),
                        hint="`boost reinstall %s` to force, `boost update` to upgrade" % name)

    violations = policy.check_install(len(lockfile.installed()))
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


def x_install__mutmut_42(entry: dict, force: bool = False,
            only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install a catalog entry. Raises BoostError on policy block or conflict."""
    name = entry["name"]
    existing = lockfile.get_skill(name)
    if existing and existing.get("pinned") and not force:
        raise BoostError("%s is pinned" % name, hint="`boost unpin %s` first" % name)
    if existing and not force:
        raise BoostError("%s is already installed (v%s)" % (name, existing.get("version")),
                        hint="`boost reinstall %s` to force, `boost update` to upgrade" % name)

    violations = policy.check_install(entry, )
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


def x_install__mutmut_43(entry: dict, force: bool = False,
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
        raise BoostError(None,
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


def x_install__mutmut_44(entry: dict, force: bool = False,
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
                        hint=None)

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


def x_install__mutmut_45(entry: dict, force: bool = False,
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
        raise BoostError(hint="inspect with `boost policy list`")

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


def x_install__mutmut_46(entry: dict, force: bool = False,
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
                        )

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


def x_install__mutmut_47(entry: dict, force: bool = False,
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
        raise BoostError("policy blocks installing %s: %s" / (name, "; ".join(violations)),
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


def x_install__mutmut_48(entry: dict, force: bool = False,
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
        raise BoostError("XXpolicy blocks installing %s: %sXX" % (name, "; ".join(violations)),
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


def x_install__mutmut_49(entry: dict, force: bool = False,
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
        raise BoostError("POLICY BLOCKS INSTALLING %S: %S" % (name, "; ".join(violations)),
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


def x_install__mutmut_50(entry: dict, force: bool = False,
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
        raise BoostError("policy blocks installing %s: %s" % (name, "; ".join(None)),
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


def x_install__mutmut_51(entry: dict, force: bool = False,
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
        raise BoostError("policy blocks installing %s: %s" % (name, "XX; XX".join(violations)),
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


def x_install__mutmut_52(entry: dict, force: bool = False,
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
                        hint="XXinspect with `boost policy list`XX")

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


def x_install__mutmut_53(entry: dict, force: bool = False,
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
                        hint="INSPECT WITH `BOOST POLICY LIST`")

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


def x_install__mutmut_54(entry: dict, force: bool = False,
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

    src = None
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


def x_install__mutmut_55(entry: dict, force: bool = False,
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

    src = source_dir_for(None)
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


def x_install__mutmut_56(entry: dict, force: bool = False,
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
    dest = None
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


def x_install__mutmut_57(entry: dict, force: bool = False,
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
    dest = skill_store_dir(None)
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


def x_install__mutmut_58(entry: dict, force: bool = False,
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
    _copy_skill(None, dest)

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


def x_install__mutmut_59(entry: dict, force: bool = False,
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
    _copy_skill(src, None)

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


def x_install__mutmut_60(entry: dict, force: bool = False,
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
    _copy_skill(dest)

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


def x_install__mutmut_61(entry: dict, force: bool = False,
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
    _copy_skill(src, )

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


def x_install__mutmut_62(entry: dict, force: bool = False,
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

    res = None
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


def x_install__mutmut_63(entry: dict, force: bool = False,
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

    res = link_agents(None, only=only_agents)
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


def x_install__mutmut_64(entry: dict, force: bool = False,
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

    res = link_agents(name, only=None)
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


def x_install__mutmut_65(entry: dict, force: bool = False,
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

    res = link_agents(only=only_agents)
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


def x_install__mutmut_66(entry: dict, force: bool = False,
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

    res = link_agents(name, )
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


def x_install__mutmut_67(entry: dict, force: bool = False,
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
    res.upgraded = None
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


def x_install__mutmut_68(entry: dict, force: bool = False,
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
    res.upgraded = existing is None
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


def x_install__mutmut_69(entry: dict, force: bool = False,
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
    res.score, _ = None

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


def x_install__mutmut_70(entry: dict, force: bool = False,
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
    res.score, _ = util.score_skill(None)

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


def x_install__mutmut_71(entry: dict, force: bool = False,
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

    tap = None
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


def x_install__mutmut_72(entry: dict, force: bool = False,
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

    tap = registry.get(None)
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


def x_install__mutmut_73(entry: dict, force: bool = False,
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

    tap = registry.get(entry["XXtapXX"])
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


def x_install__mutmut_74(entry: dict, force: bool = False,
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

    tap = registry.get(entry["TAP"])
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


def x_install__mutmut_75(entry: dict, force: bool = False,
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
    now = None
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


def x_install__mutmut_76(entry: dict, force: bool = False,
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
    lockfile.set_skill(None, {
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


def x_install__mutmut_77(entry: dict, force: bool = False,
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
    lockfile.set_skill(name, None)
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_78(entry: dict, force: bool = False,
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
    lockfile.set_skill({
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


def x_install__mutmut_79(entry: dict, force: bool = False,
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
    lockfile.set_skill(name, )
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_80(entry: dict, force: bool = False,
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
        "XXversionXX": entry.get("version", "0.0.0"),
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


def x_install__mutmut_81(entry: dict, force: bool = False,
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
        "VERSION": entry.get("version", "0.0.0"),
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


def x_install__mutmut_82(entry: dict, force: bool = False,
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
        "version": entry.get(None, "0.0.0"),
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


def x_install__mutmut_83(entry: dict, force: bool = False,
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
        "version": entry.get("version", None),
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


def x_install__mutmut_84(entry: dict, force: bool = False,
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
        "version": entry.get("0.0.0"),
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


def x_install__mutmut_85(entry: dict, force: bool = False,
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
        "version": entry.get("version", ),
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


def x_install__mutmut_86(entry: dict, force: bool = False,
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
        "version": entry.get("XXversionXX", "0.0.0"),
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


def x_install__mutmut_87(entry: dict, force: bool = False,
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
        "version": entry.get("VERSION", "0.0.0"),
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


def x_install__mutmut_88(entry: dict, force: bool = False,
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
        "version": entry.get("version", "XX0.0.0XX"),
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


def x_install__mutmut_89(entry: dict, force: bool = False,
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
        "XXtapXX": entry["tap"],
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


def x_install__mutmut_90(entry: dict, force: bool = False,
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
        "TAP": entry["tap"],
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


def x_install__mutmut_91(entry: dict, force: bool = False,
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
        "tap": entry["XXtapXX"],
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


def x_install__mutmut_92(entry: dict, force: bool = False,
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
        "tap": entry["TAP"],
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


def x_install__mutmut_93(entry: dict, force: bool = False,
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
        "XXsource_dirXX": entry.get("rel_dir", "."),
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


def x_install__mutmut_94(entry: dict, force: bool = False,
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
        "SOURCE_DIR": entry.get("rel_dir", "."),
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


def x_install__mutmut_95(entry: dict, force: bool = False,
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
        "source_dir": entry.get(None, "."),
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


def x_install__mutmut_96(entry: dict, force: bool = False,
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
        "source_dir": entry.get("rel_dir", None),
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


def x_install__mutmut_97(entry: dict, force: bool = False,
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
        "source_dir": entry.get("."),
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


def x_install__mutmut_98(entry: dict, force: bool = False,
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
        "source_dir": entry.get("rel_dir", ),
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


def x_install__mutmut_99(entry: dict, force: bool = False,
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
        "source_dir": entry.get("XXrel_dirXX", "."),
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


def x_install__mutmut_100(entry: dict, force: bool = False,
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
        "source_dir": entry.get("REL_DIR", "."),
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


def x_install__mutmut_101(entry: dict, force: bool = False,
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
        "source_dir": entry.get("rel_dir", "XX.XX"),
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


def x_install__mutmut_102(entry: dict, force: bool = False,
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
        "XXcommitXX": gitutil.head_commit(tap.path),
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


def x_install__mutmut_103(entry: dict, force: bool = False,
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
        "COMMIT": gitutil.head_commit(tap.path),
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


def x_install__mutmut_104(entry: dict, force: bool = False,
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
        "commit": gitutil.head_commit(None),
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


def x_install__mutmut_105(entry: dict, force: bool = False,
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
        "XXsha256XX": util.sha256_dir(dest),
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_106(entry: dict, force: bool = False,
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
        "SHA256": util.sha256_dir(dest),
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_107(entry: dict, force: bool = False,
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
        "sha256": util.sha256_dir(None),
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_108(entry: dict, force: bool = False,
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
        "XXinstalled_atXX": (existing or {}).get("installed_at", now),
        "updated_at": now,
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_109(entry: dict, force: bool = False,
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
        "INSTALLED_AT": (existing or {}).get("installed_at", now),
        "updated_at": now,
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_110(entry: dict, force: bool = False,
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
        "installed_at": (existing or {}).get(None, now),
        "updated_at": now,
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_111(entry: dict, force: bool = False,
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
        "installed_at": (existing or {}).get("installed_at", None),
        "updated_at": now,
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_112(entry: dict, force: bool = False,
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
        "installed_at": (existing or {}).get(now),
        "updated_at": now,
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_113(entry: dict, force: bool = False,
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
        "installed_at": (existing or {}).get("installed_at", ),
        "updated_at": now,
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_114(entry: dict, force: bool = False,
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
        "installed_at": (existing and {}).get("installed_at", now),
        "updated_at": now,
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_115(entry: dict, force: bool = False,
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
        "installed_at": (existing or {}).get("XXinstalled_atXX", now),
        "updated_at": now,
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_116(entry: dict, force: bool = False,
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
        "installed_at": (existing or {}).get("INSTALLED_AT", now),
        "updated_at": now,
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_117(entry: dict, force: bool = False,
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
        "XXupdated_atXX": now,
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_118(entry: dict, force: bool = False,
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
        "UPDATED_AT": now,
        "pinned": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_119(entry: dict, force: bool = False,
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
        "XXpinnedXX": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_120(entry: dict, force: bool = False,
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
        "PINNED": bool((existing or {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_121(entry: dict, force: bool = False,
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
        "pinned": bool(None),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_122(entry: dict, force: bool = False,
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
        "pinned": bool((existing or {}).get(None)),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_123(entry: dict, force: bool = False,
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
        "pinned": bool((existing and {}).get("pinned")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_124(entry: dict, force: bool = False,
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
        "pinned": bool((existing or {}).get("XXpinnedXX")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_125(entry: dict, force: bool = False,
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
        "pinned": bool((existing or {}).get("PINNED")),
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_126(entry: dict, force: bool = False,
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
        "XXquarantinedXX": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_127(entry: dict, force: bool = False,
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
        "QUARANTINED": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_128(entry: dict, force: bool = False,
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
        "quarantined": True,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_129(entry: dict, force: bool = False,
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
        "XXagentsXX": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_130(entry: dict, force: bool = False,
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
        "AGENTS": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_131(entry: dict, force: bool = False,
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
        "XXtagsXX": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_132(entry: dict, force: bool = False,
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
        "TAGS": (existing or {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_133(entry: dict, force: bool = False,
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
        "tags": (existing or {}).get(None, []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_134(entry: dict, force: bool = False,
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
        "tags": (existing or {}).get("tags", None),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_135(entry: dict, force: bool = False,
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
        "tags": (existing or {}).get([]),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_136(entry: dict, force: bool = False,
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
        "tags": (existing or {}).get("tags", ),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_137(entry: dict, force: bool = False,
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
        "tags": (existing and {}).get("tags", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_138(entry: dict, force: bool = False,
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
        "tags": (existing or {}).get("XXtagsXX", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_139(entry: dict, force: bool = False,
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
        "tags": (existing or {}).get("TAGS", []),
    })
    journal.log("install", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_140(entry: dict, force: bool = False,
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
    journal.log(None, name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_141(entry: dict, force: bool = False,
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
    journal.log("install", None, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_142(entry: dict, force: bool = False,
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
    journal.log("install", name, tap=None, version=entry.get("version"))
    return res


def x_install__mutmut_143(entry: dict, force: bool = False,
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
    journal.log("install", name, tap=entry["tap"], version=None)
    return res


def x_install__mutmut_144(entry: dict, force: bool = False,
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
    journal.log(name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_145(entry: dict, force: bool = False,
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
    journal.log("install", tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_146(entry: dict, force: bool = False,
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
    journal.log("install", name, version=entry.get("version"))
    return res


def x_install__mutmut_147(entry: dict, force: bool = False,
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
    journal.log("install", name, tap=entry["tap"], )
    return res


def x_install__mutmut_148(entry: dict, force: bool = False,
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
    journal.log("XXinstallXX", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_149(entry: dict, force: bool = False,
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
    journal.log("INSTALL", name, tap=entry["tap"], version=entry.get("version"))
    return res


def x_install__mutmut_150(entry: dict, force: bool = False,
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
    journal.log("install", name, tap=entry["XXtapXX"], version=entry.get("version"))
    return res


def x_install__mutmut_151(entry: dict, force: bool = False,
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
    journal.log("install", name, tap=entry["TAP"], version=entry.get("version"))
    return res


def x_install__mutmut_152(entry: dict, force: bool = False,
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
    journal.log("install", name, tap=entry["tap"], version=entry.get(None))
    return res


def x_install__mutmut_153(entry: dict, force: bool = False,
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
    journal.log("install", name, tap=entry["tap"], version=entry.get("XXversionXX"))
    return res


def x_install__mutmut_154(entry: dict, force: bool = False,
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
    journal.log("install", name, tap=entry["tap"], version=entry.get("VERSION"))
    return res

mutants_x_install__mutmut['_mutmut_orig'] = x_install__mutmut_orig # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_1'] = x_install__mutmut_1 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_2'] = x_install__mutmut_2 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_3'] = x_install__mutmut_3 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_4'] = x_install__mutmut_4 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_5'] = x_install__mutmut_5 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_6'] = x_install__mutmut_6 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_7'] = x_install__mutmut_7 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_8'] = x_install__mutmut_8 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_9'] = x_install__mutmut_9 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_10'] = x_install__mutmut_10 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_11'] = x_install__mutmut_11 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_12'] = x_install__mutmut_12 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_13'] = x_install__mutmut_13 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_14'] = x_install__mutmut_14 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_15'] = x_install__mutmut_15 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_16'] = x_install__mutmut_16 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_17'] = x_install__mutmut_17 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_18'] = x_install__mutmut_18 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_19'] = x_install__mutmut_19 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_20'] = x_install__mutmut_20 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_21'] = x_install__mutmut_21 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_22'] = x_install__mutmut_22 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_23'] = x_install__mutmut_23 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_24'] = x_install__mutmut_24 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_25'] = x_install__mutmut_25 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_26'] = x_install__mutmut_26 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_27'] = x_install__mutmut_27 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_28'] = x_install__mutmut_28 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_29'] = x_install__mutmut_29 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_30'] = x_install__mutmut_30 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_31'] = x_install__mutmut_31 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_32'] = x_install__mutmut_32 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_33'] = x_install__mutmut_33 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_34'] = x_install__mutmut_34 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_35'] = x_install__mutmut_35 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_36'] = x_install__mutmut_36 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_37'] = x_install__mutmut_37 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_38'] = x_install__mutmut_38 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_39'] = x_install__mutmut_39 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_40'] = x_install__mutmut_40 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_41'] = x_install__mutmut_41 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_42'] = x_install__mutmut_42 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_43'] = x_install__mutmut_43 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_44'] = x_install__mutmut_44 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_45'] = x_install__mutmut_45 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_46'] = x_install__mutmut_46 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_47'] = x_install__mutmut_47 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_48'] = x_install__mutmut_48 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_49'] = x_install__mutmut_49 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_50'] = x_install__mutmut_50 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_51'] = x_install__mutmut_51 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_52'] = x_install__mutmut_52 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_53'] = x_install__mutmut_53 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_54'] = x_install__mutmut_54 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_55'] = x_install__mutmut_55 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_56'] = x_install__mutmut_56 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_57'] = x_install__mutmut_57 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_58'] = x_install__mutmut_58 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_59'] = x_install__mutmut_59 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_60'] = x_install__mutmut_60 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_61'] = x_install__mutmut_61 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_62'] = x_install__mutmut_62 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_63'] = x_install__mutmut_63 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_64'] = x_install__mutmut_64 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_65'] = x_install__mutmut_65 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_66'] = x_install__mutmut_66 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_67'] = x_install__mutmut_67 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_68'] = x_install__mutmut_68 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_69'] = x_install__mutmut_69 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_70'] = x_install__mutmut_70 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_71'] = x_install__mutmut_71 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_72'] = x_install__mutmut_72 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_73'] = x_install__mutmut_73 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_74'] = x_install__mutmut_74 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_75'] = x_install__mutmut_75 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_76'] = x_install__mutmut_76 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_77'] = x_install__mutmut_77 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_78'] = x_install__mutmut_78 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_79'] = x_install__mutmut_79 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_80'] = x_install__mutmut_80 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_81'] = x_install__mutmut_81 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_82'] = x_install__mutmut_82 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_83'] = x_install__mutmut_83 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_84'] = x_install__mutmut_84 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_85'] = x_install__mutmut_85 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_86'] = x_install__mutmut_86 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_87'] = x_install__mutmut_87 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_88'] = x_install__mutmut_88 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_89'] = x_install__mutmut_89 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_90'] = x_install__mutmut_90 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_91'] = x_install__mutmut_91 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_92'] = x_install__mutmut_92 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_93'] = x_install__mutmut_93 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_94'] = x_install__mutmut_94 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_95'] = x_install__mutmut_95 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_96'] = x_install__mutmut_96 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_97'] = x_install__mutmut_97 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_98'] = x_install__mutmut_98 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_99'] = x_install__mutmut_99 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_100'] = x_install__mutmut_100 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_101'] = x_install__mutmut_101 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_102'] = x_install__mutmut_102 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_103'] = x_install__mutmut_103 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_104'] = x_install__mutmut_104 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_105'] = x_install__mutmut_105 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_106'] = x_install__mutmut_106 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_107'] = x_install__mutmut_107 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_108'] = x_install__mutmut_108 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_109'] = x_install__mutmut_109 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_110'] = x_install__mutmut_110 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_111'] = x_install__mutmut_111 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_112'] = x_install__mutmut_112 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_113'] = x_install__mutmut_113 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_114'] = x_install__mutmut_114 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_115'] = x_install__mutmut_115 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_116'] = x_install__mutmut_116 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_117'] = x_install__mutmut_117 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_118'] = x_install__mutmut_118 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_119'] = x_install__mutmut_119 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_120'] = x_install__mutmut_120 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_121'] = x_install__mutmut_121 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_122'] = x_install__mutmut_122 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_123'] = x_install__mutmut_123 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_124'] = x_install__mutmut_124 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_125'] = x_install__mutmut_125 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_126'] = x_install__mutmut_126 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_127'] = x_install__mutmut_127 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_128'] = x_install__mutmut_128 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_129'] = x_install__mutmut_129 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_130'] = x_install__mutmut_130 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_131'] = x_install__mutmut_131 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_132'] = x_install__mutmut_132 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_133'] = x_install__mutmut_133 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_134'] = x_install__mutmut_134 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_135'] = x_install__mutmut_135 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_136'] = x_install__mutmut_136 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_137'] = x_install__mutmut_137 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_138'] = x_install__mutmut_138 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_139'] = x_install__mutmut_139 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_140'] = x_install__mutmut_140 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_141'] = x_install__mutmut_141 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_142'] = x_install__mutmut_142 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_143'] = x_install__mutmut_143 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_144'] = x_install__mutmut_144 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_145'] = x_install__mutmut_145 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_146'] = x_install__mutmut_146 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_147'] = x_install__mutmut_147 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_148'] = x_install__mutmut_148 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_149'] = x_install__mutmut_149 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_150'] = x_install__mutmut_150 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_151'] = x_install__mutmut_151 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_152'] = x_install__mutmut_152 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_153'] = x_install__mutmut_153 # type: ignore # mutmut generated
mutants_x_install__mutmut['x_install__mutmut_154'] = x_install__mutmut_154 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_install_from_path__mutmut)
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


def x_install_from_path__mutmut_orig(src_dir: Path, name: Optional[str] = None,
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


def x_install_from_path__mutmut_1(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "XXlocalXX",
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


def x_install_from_path__mutmut_2(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "LOCAL",
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


def x_install_from_path__mutmut_3(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = None
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


def x_install_from_path__mutmut_4(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(None)
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


def x_install_from_path__mutmut_5(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if (src_dir / "SKILL.md").exists():
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


def x_install_from_path__mutmut_6(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir * "SKILL.md").exists():
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


def x_install_from_path__mutmut_7(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "XXSKILL.mdXX").exists():
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


def x_install_from_path__mutmut_8(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "skill.md").exists():
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


def x_install_from_path__mutmut_9(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.MD").exists():
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


def x_install_from_path__mutmut_10(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError(None)
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


def x_install_from_path__mutmut_11(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" / src_dir)
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


def x_install_from_path__mutmut_12(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("XX%s has no SKILL.mdXX" % src_dir)
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


def x_install_from_path__mutmut_13(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no skill.md" % src_dir)
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


def x_install_from_path__mutmut_14(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%S HAS NO SKILL.MD" % src_dir)
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


def x_install_from_path__mutmut_15(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = None
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


def x_install_from_path__mutmut_16(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse(None)
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


def x_install_from_path__mutmut_17(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding=None, errors="replace"))
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


def x_install_from_path__mutmut_18(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding="utf-8", errors=None))
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


def x_install_from_path__mutmut_19(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        errors="replace"))
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


def x_install_from_path__mutmut_20(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding="utf-8", ))
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


def x_install_from_path__mutmut_21(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir * "SKILL.md").read_text(
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


def x_install_from_path__mutmut_22(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "XXSKILL.mdXX").read_text(
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


def x_install_from_path__mutmut_23(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "skill.md").read_text(
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


def x_install_from_path__mutmut_24(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.MD").read_text(
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


def x_install_from_path__mutmut_25(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding="XXutf-8XX", errors="replace"))
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


def x_install_from_path__mutmut_26(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding="UTF-8", errors="replace"))
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


def x_install_from_path__mutmut_27(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding="utf-8", errors="XXreplaceXX"))
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


def x_install_from_path__mutmut_28(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding="utf-8", errors="REPLACE"))
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


def x_install_from_path__mutmut_29(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding="utf-8", errors="replace"))
    name = None
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


def x_install_from_path__mutmut_30(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding="utf-8", errors="replace"))
    name = name and str(meta.get("name") or src_dir.name)
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


def x_install_from_path__mutmut_31(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding="utf-8", errors="replace"))
    name = name or str(None)
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


def x_install_from_path__mutmut_32(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding="utf-8", errors="replace"))
    name = name or str(meta.get("name") and src_dir.name)
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


def x_install_from_path__mutmut_33(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding="utf-8", errors="replace"))
    name = name or str(meta.get(None) or src_dir.name)
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


def x_install_from_path__mutmut_34(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding="utf-8", errors="replace"))
    name = name or str(meta.get("XXnameXX") or src_dir.name)
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


def x_install_from_path__mutmut_35(src_dir: Path, name: Optional[str] = None,
                      tap_label: str = "local",
                      only_agents: Optional[List[str]] = None) -> InstallResult:
    """Install directly from a local directory (used by `boost import`)."""
    src_dir = Path(src_dir)
    if not (src_dir / "SKILL.md").exists():
        raise BoostError("%s has no SKILL.md" % src_dir)
    from . import frontmatter
    meta, _ = frontmatter.parse((src_dir / "SKILL.md").read_text(
        encoding="utf-8", errors="replace"))
    name = name or str(meta.get("NAME") or src_dir.name)
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


def x_install_from_path__mutmut_36(src_dir: Path, name: Optional[str] = None,
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
    dest = None
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


def x_install_from_path__mutmut_37(src_dir: Path, name: Optional[str] = None,
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
    dest = skill_store_dir(None)
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


def x_install_from_path__mutmut_38(src_dir: Path, name: Optional[str] = None,
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
    _copy_skill(None, dest)
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


def x_install_from_path__mutmut_39(src_dir: Path, name: Optional[str] = None,
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
    _copy_skill(src_dir, None)
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


def x_install_from_path__mutmut_40(src_dir: Path, name: Optional[str] = None,
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
    _copy_skill(dest)
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


def x_install_from_path__mutmut_41(src_dir: Path, name: Optional[str] = None,
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
    _copy_skill(src_dir, )
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


def x_install_from_path__mutmut_42(src_dir: Path, name: Optional[str] = None,
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
    res = None
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


def x_install_from_path__mutmut_43(src_dir: Path, name: Optional[str] = None,
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
    res = link_agents(None, only=only_agents)
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


def x_install_from_path__mutmut_44(src_dir: Path, name: Optional[str] = None,
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
    res = link_agents(name, only=None)
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


def x_install_from_path__mutmut_45(src_dir: Path, name: Optional[str] = None,
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
    res = link_agents(only=only_agents)
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


def x_install_from_path__mutmut_46(src_dir: Path, name: Optional[str] = None,
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
    res = link_agents(name, )
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


def x_install_from_path__mutmut_47(src_dir: Path, name: Optional[str] = None,
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
    res.score, _ = None
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


def x_install_from_path__mutmut_48(src_dir: Path, name: Optional[str] = None,
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
    res.score, _ = util.score_skill(None)
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


def x_install_from_path__mutmut_49(src_dir: Path, name: Optional[str] = None,
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
    now = None
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


def x_install_from_path__mutmut_50(src_dir: Path, name: Optional[str] = None,
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
    existing = None
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


def x_install_from_path__mutmut_51(src_dir: Path, name: Optional[str] = None,
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
    existing = lockfile.get_skill(None)
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


def x_install_from_path__mutmut_52(src_dir: Path, name: Optional[str] = None,
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
    lockfile.set_skill(None, {
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


def x_install_from_path__mutmut_53(src_dir: Path, name: Optional[str] = None,
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
    lockfile.set_skill(name, None)
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_54(src_dir: Path, name: Optional[str] = None,
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
    lockfile.set_skill({
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


def x_install_from_path__mutmut_55(src_dir: Path, name: Optional[str] = None,
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
    lockfile.set_skill(name, )
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_56(src_dir: Path, name: Optional[str] = None,
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
        "XXversionXX": str(meta.get("version") or "0.0.0"),
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


def x_install_from_path__mutmut_57(src_dir: Path, name: Optional[str] = None,
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
        "VERSION": str(meta.get("version") or "0.0.0"),
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


def x_install_from_path__mutmut_58(src_dir: Path, name: Optional[str] = None,
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
        "version": str(None),
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


def x_install_from_path__mutmut_59(src_dir: Path, name: Optional[str] = None,
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
        "version": str(meta.get("version") and "0.0.0"),
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


def x_install_from_path__mutmut_60(src_dir: Path, name: Optional[str] = None,
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
        "version": str(meta.get(None) or "0.0.0"),
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


def x_install_from_path__mutmut_61(src_dir: Path, name: Optional[str] = None,
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
        "version": str(meta.get("XXversionXX") or "0.0.0"),
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


def x_install_from_path__mutmut_62(src_dir: Path, name: Optional[str] = None,
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
        "version": str(meta.get("VERSION") or "0.0.0"),
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


def x_install_from_path__mutmut_63(src_dir: Path, name: Optional[str] = None,
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
        "version": str(meta.get("version") or "XX0.0.0XX"),
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


def x_install_from_path__mutmut_64(src_dir: Path, name: Optional[str] = None,
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
        "XXtapXX": tap_label,
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


def x_install_from_path__mutmut_65(src_dir: Path, name: Optional[str] = None,
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
        "TAP": tap_label,
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


def x_install_from_path__mutmut_66(src_dir: Path, name: Optional[str] = None,
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
        "XXsource_dirXX": str(src_dir),
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


def x_install_from_path__mutmut_67(src_dir: Path, name: Optional[str] = None,
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
        "SOURCE_DIR": str(src_dir),
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


def x_install_from_path__mutmut_68(src_dir: Path, name: Optional[str] = None,
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
        "source_dir": str(None),
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


def x_install_from_path__mutmut_69(src_dir: Path, name: Optional[str] = None,
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
        "XXcommitXX": "",
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


def x_install_from_path__mutmut_70(src_dir: Path, name: Optional[str] = None,
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
        "COMMIT": "",
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


def x_install_from_path__mutmut_71(src_dir: Path, name: Optional[str] = None,
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
        "commit": "XXXX",
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


def x_install_from_path__mutmut_72(src_dir: Path, name: Optional[str] = None,
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
        "XXsha256XX": util.sha256_dir(dest),
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        "pinned": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_73(src_dir: Path, name: Optional[str] = None,
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
        "SHA256": util.sha256_dir(dest),
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        "pinned": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_74(src_dir: Path, name: Optional[str] = None,
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
        "sha256": util.sha256_dir(None),
        "installed_at": (existing or {}).get("installed_at", now),
        "updated_at": now,
        "pinned": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_75(src_dir: Path, name: Optional[str] = None,
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
        "XXinstalled_atXX": (existing or {}).get("installed_at", now),
        "updated_at": now,
        "pinned": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_76(src_dir: Path, name: Optional[str] = None,
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
        "INSTALLED_AT": (existing or {}).get("installed_at", now),
        "updated_at": now,
        "pinned": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_77(src_dir: Path, name: Optional[str] = None,
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
        "installed_at": (existing or {}).get(None, now),
        "updated_at": now,
        "pinned": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_78(src_dir: Path, name: Optional[str] = None,
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
        "installed_at": (existing or {}).get("installed_at", None),
        "updated_at": now,
        "pinned": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_79(src_dir: Path, name: Optional[str] = None,
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
        "installed_at": (existing or {}).get(now),
        "updated_at": now,
        "pinned": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_80(src_dir: Path, name: Optional[str] = None,
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
        "installed_at": (existing or {}).get("installed_at", ),
        "updated_at": now,
        "pinned": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_81(src_dir: Path, name: Optional[str] = None,
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
        "installed_at": (existing and {}).get("installed_at", now),
        "updated_at": now,
        "pinned": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_82(src_dir: Path, name: Optional[str] = None,
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
        "installed_at": (existing or {}).get("XXinstalled_atXX", now),
        "updated_at": now,
        "pinned": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_83(src_dir: Path, name: Optional[str] = None,
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
        "installed_at": (existing or {}).get("INSTALLED_AT", now),
        "updated_at": now,
        "pinned": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_84(src_dir: Path, name: Optional[str] = None,
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
        "XXupdated_atXX": now,
        "pinned": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_85(src_dir: Path, name: Optional[str] = None,
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
        "UPDATED_AT": now,
        "pinned": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_86(src_dir: Path, name: Optional[str] = None,
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
        "XXpinnedXX": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_87(src_dir: Path, name: Optional[str] = None,
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
        "PINNED": False,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_88(src_dir: Path, name: Optional[str] = None,
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
        "pinned": True,
        "quarantined": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_89(src_dir: Path, name: Optional[str] = None,
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
        "XXquarantinedXX": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_90(src_dir: Path, name: Optional[str] = None,
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
        "QUARANTINED": False,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_91(src_dir: Path, name: Optional[str] = None,
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
        "quarantined": True,
        "agents": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_92(src_dir: Path, name: Optional[str] = None,
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
        "XXagentsXX": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_93(src_dir: Path, name: Optional[str] = None,
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
        "AGENTS": res.linked,
        "tags": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_94(src_dir: Path, name: Optional[str] = None,
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
        "XXtagsXX": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_95(src_dir: Path, name: Optional[str] = None,
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
        "TAGS": (existing or {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_96(src_dir: Path, name: Optional[str] = None,
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
        "tags": (existing or {}).get(None, []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_97(src_dir: Path, name: Optional[str] = None,
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
        "tags": (existing or {}).get("tags", None),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_98(src_dir: Path, name: Optional[str] = None,
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
        "tags": (existing or {}).get([]),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_99(src_dir: Path, name: Optional[str] = None,
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
        "tags": (existing or {}).get("tags", ),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_100(src_dir: Path, name: Optional[str] = None,
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
        "tags": (existing and {}).get("tags", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_101(src_dir: Path, name: Optional[str] = None,
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
        "tags": (existing or {}).get("XXtagsXX", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_102(src_dir: Path, name: Optional[str] = None,
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
        "tags": (existing or {}).get("TAGS", []),
    })
    journal.log("import", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_103(src_dir: Path, name: Optional[str] = None,
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
    journal.log(None, name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_104(src_dir: Path, name: Optional[str] = None,
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
    journal.log("import", None, source=str(src_dir))
    return res


def x_install_from_path__mutmut_105(src_dir: Path, name: Optional[str] = None,
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
    journal.log("import", name, source=None)
    return res


def x_install_from_path__mutmut_106(src_dir: Path, name: Optional[str] = None,
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
    journal.log(name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_107(src_dir: Path, name: Optional[str] = None,
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
    journal.log("import", source=str(src_dir))
    return res


def x_install_from_path__mutmut_108(src_dir: Path, name: Optional[str] = None,
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
    journal.log("import", name, )
    return res


def x_install_from_path__mutmut_109(src_dir: Path, name: Optional[str] = None,
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
    journal.log("XXimportXX", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_110(src_dir: Path, name: Optional[str] = None,
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
    journal.log("IMPORT", name, source=str(src_dir))
    return res


def x_install_from_path__mutmut_111(src_dir: Path, name: Optional[str] = None,
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
    journal.log("import", name, source=str(None))
    return res

mutants_x_install_from_path__mutmut['_mutmut_orig'] = x_install_from_path__mutmut_orig # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_1'] = x_install_from_path__mutmut_1 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_2'] = x_install_from_path__mutmut_2 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_3'] = x_install_from_path__mutmut_3 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_4'] = x_install_from_path__mutmut_4 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_5'] = x_install_from_path__mutmut_5 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_6'] = x_install_from_path__mutmut_6 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_7'] = x_install_from_path__mutmut_7 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_8'] = x_install_from_path__mutmut_8 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_9'] = x_install_from_path__mutmut_9 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_10'] = x_install_from_path__mutmut_10 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_11'] = x_install_from_path__mutmut_11 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_12'] = x_install_from_path__mutmut_12 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_13'] = x_install_from_path__mutmut_13 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_14'] = x_install_from_path__mutmut_14 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_15'] = x_install_from_path__mutmut_15 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_16'] = x_install_from_path__mutmut_16 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_17'] = x_install_from_path__mutmut_17 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_18'] = x_install_from_path__mutmut_18 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_19'] = x_install_from_path__mutmut_19 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_20'] = x_install_from_path__mutmut_20 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_21'] = x_install_from_path__mutmut_21 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_22'] = x_install_from_path__mutmut_22 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_23'] = x_install_from_path__mutmut_23 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_24'] = x_install_from_path__mutmut_24 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_25'] = x_install_from_path__mutmut_25 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_26'] = x_install_from_path__mutmut_26 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_27'] = x_install_from_path__mutmut_27 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_28'] = x_install_from_path__mutmut_28 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_29'] = x_install_from_path__mutmut_29 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_30'] = x_install_from_path__mutmut_30 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_31'] = x_install_from_path__mutmut_31 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_32'] = x_install_from_path__mutmut_32 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_33'] = x_install_from_path__mutmut_33 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_34'] = x_install_from_path__mutmut_34 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_35'] = x_install_from_path__mutmut_35 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_36'] = x_install_from_path__mutmut_36 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_37'] = x_install_from_path__mutmut_37 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_38'] = x_install_from_path__mutmut_38 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_39'] = x_install_from_path__mutmut_39 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_40'] = x_install_from_path__mutmut_40 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_41'] = x_install_from_path__mutmut_41 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_42'] = x_install_from_path__mutmut_42 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_43'] = x_install_from_path__mutmut_43 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_44'] = x_install_from_path__mutmut_44 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_45'] = x_install_from_path__mutmut_45 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_46'] = x_install_from_path__mutmut_46 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_47'] = x_install_from_path__mutmut_47 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_48'] = x_install_from_path__mutmut_48 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_49'] = x_install_from_path__mutmut_49 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_50'] = x_install_from_path__mutmut_50 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_51'] = x_install_from_path__mutmut_51 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_52'] = x_install_from_path__mutmut_52 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_53'] = x_install_from_path__mutmut_53 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_54'] = x_install_from_path__mutmut_54 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_55'] = x_install_from_path__mutmut_55 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_56'] = x_install_from_path__mutmut_56 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_57'] = x_install_from_path__mutmut_57 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_58'] = x_install_from_path__mutmut_58 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_59'] = x_install_from_path__mutmut_59 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_60'] = x_install_from_path__mutmut_60 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_61'] = x_install_from_path__mutmut_61 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_62'] = x_install_from_path__mutmut_62 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_63'] = x_install_from_path__mutmut_63 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_64'] = x_install_from_path__mutmut_64 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_65'] = x_install_from_path__mutmut_65 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_66'] = x_install_from_path__mutmut_66 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_67'] = x_install_from_path__mutmut_67 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_68'] = x_install_from_path__mutmut_68 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_69'] = x_install_from_path__mutmut_69 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_70'] = x_install_from_path__mutmut_70 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_71'] = x_install_from_path__mutmut_71 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_72'] = x_install_from_path__mutmut_72 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_73'] = x_install_from_path__mutmut_73 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_74'] = x_install_from_path__mutmut_74 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_75'] = x_install_from_path__mutmut_75 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_76'] = x_install_from_path__mutmut_76 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_77'] = x_install_from_path__mutmut_77 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_78'] = x_install_from_path__mutmut_78 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_79'] = x_install_from_path__mutmut_79 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_80'] = x_install_from_path__mutmut_80 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_81'] = x_install_from_path__mutmut_81 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_82'] = x_install_from_path__mutmut_82 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_83'] = x_install_from_path__mutmut_83 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_84'] = x_install_from_path__mutmut_84 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_85'] = x_install_from_path__mutmut_85 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_86'] = x_install_from_path__mutmut_86 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_87'] = x_install_from_path__mutmut_87 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_88'] = x_install_from_path__mutmut_88 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_89'] = x_install_from_path__mutmut_89 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_90'] = x_install_from_path__mutmut_90 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_91'] = x_install_from_path__mutmut_91 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_92'] = x_install_from_path__mutmut_92 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_93'] = x_install_from_path__mutmut_93 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_94'] = x_install_from_path__mutmut_94 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_95'] = x_install_from_path__mutmut_95 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_96'] = x_install_from_path__mutmut_96 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_97'] = x_install_from_path__mutmut_97 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_98'] = x_install_from_path__mutmut_98 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_99'] = x_install_from_path__mutmut_99 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_100'] = x_install_from_path__mutmut_100 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_101'] = x_install_from_path__mutmut_101 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_102'] = x_install_from_path__mutmut_102 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_103'] = x_install_from_path__mutmut_103 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_104'] = x_install_from_path__mutmut_104 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_105'] = x_install_from_path__mutmut_105 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_106'] = x_install_from_path__mutmut_106 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_107'] = x_install_from_path__mutmut_107 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_108'] = x_install_from_path__mutmut_108 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_109'] = x_install_from_path__mutmut_109 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_110'] = x_install_from_path__mutmut_110 # type: ignore # mutmut generated
mutants_x_install_from_path__mutmut['x_install_from_path__mutmut_111'] = x_install_from_path__mutmut_111 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_uninstall__mutmut)
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


def x_uninstall__mutmut_orig(name: str) -> dict:
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


def x_uninstall__mutmut_1(name: str) -> dict:
    entry = None
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


def x_uninstall__mutmut_2(name: str) -> dict:
    entry = lockfile.get_skill(None)
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


def x_uninstall__mutmut_3(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if entry:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_4(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError(None,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_5(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint=None)
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_6(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError(hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_7(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        )
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_8(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" / name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_9(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("XX%s is not installedXX" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_10(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%S IS NOT INSTALLED" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_11(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="XXsee what is with `boost list`XX")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_12(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="SEE WHAT IS WITH `BOOST LIST`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_13(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    removed_links = None
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_14(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(None)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_15(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = None
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_16(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(None)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_17(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(None)
    lockfile.remove_skill(name)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_18(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(None)
    journal.log("uninstall", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_19(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log(None, name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_20(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", None)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_21(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log(name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_22(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("uninstall", )
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_23(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("XXuninstallXX", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_24(name: str) -> dict:
    entry = lockfile.get_skill(name)
    if not entry:
        raise BoostError("%s is not installed" % name,
                        hint="see what is with `boost list`")
    removed_links = unlink_agents(name)
    dest = skill_store_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    lockfile.remove_skill(name)
    journal.log("UNINSTALL", name)
    return {"name": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_25(name: str) -> dict:
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
    return {"XXnameXX": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_26(name: str) -> dict:
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
    return {"NAME": name, "unlinked": removed_links, "entry": entry}


def x_uninstall__mutmut_27(name: str) -> dict:
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
    return {"name": name, "XXunlinkedXX": removed_links, "entry": entry}


def x_uninstall__mutmut_28(name: str) -> dict:
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
    return {"name": name, "UNLINKED": removed_links, "entry": entry}


def x_uninstall__mutmut_29(name: str) -> dict:
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
    return {"name": name, "unlinked": removed_links, "XXentryXX": entry}


def x_uninstall__mutmut_30(name: str) -> dict:
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
    return {"name": name, "unlinked": removed_links, "ENTRY": entry}

mutants_x_uninstall__mutmut['_mutmut_orig'] = x_uninstall__mutmut_orig # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_1'] = x_uninstall__mutmut_1 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_2'] = x_uninstall__mutmut_2 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_3'] = x_uninstall__mutmut_3 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_4'] = x_uninstall__mutmut_4 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_5'] = x_uninstall__mutmut_5 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_6'] = x_uninstall__mutmut_6 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_7'] = x_uninstall__mutmut_7 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_8'] = x_uninstall__mutmut_8 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_9'] = x_uninstall__mutmut_9 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_10'] = x_uninstall__mutmut_10 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_11'] = x_uninstall__mutmut_11 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_12'] = x_uninstall__mutmut_12 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_13'] = x_uninstall__mutmut_13 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_14'] = x_uninstall__mutmut_14 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_15'] = x_uninstall__mutmut_15 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_16'] = x_uninstall__mutmut_16 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_17'] = x_uninstall__mutmut_17 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_18'] = x_uninstall__mutmut_18 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_19'] = x_uninstall__mutmut_19 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_20'] = x_uninstall__mutmut_20 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_21'] = x_uninstall__mutmut_21 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_22'] = x_uninstall__mutmut_22 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_23'] = x_uninstall__mutmut_23 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_24'] = x_uninstall__mutmut_24 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_25'] = x_uninstall__mutmut_25 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_26'] = x_uninstall__mutmut_26 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_27'] = x_uninstall__mutmut_27 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_28'] = x_uninstall__mutmut_28 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_29'] = x_uninstall__mutmut_29 # type: ignore # mutmut generated
mutants_x_uninstall__mutmut['x_uninstall__mutmut_30'] = x_uninstall__mutmut_30 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_sync_plan__mutmut)
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


def x_sync_plan__mutmut_orig() -> Dict[str, list]:
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


def x_sync_plan__mutmut_1() -> Dict[str, list]:
    """Compare lock file <-> store <-> agent symlinks.

    Returns {missing_store, missing_links, stale_links, orphaned_store}
      missing_store:  lock entries whose store dir is gone
      missing_links:  (skill, agent) pairs that should be linked but aren't
      stale_links:    paths in agent dirs that are broken/unmanaged symlinks
      orphaned_store: store dirs not present in the lock file
    """
    lock = None
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


def x_sync_plan__mutmut_2() -> Dict[str, list]:
    """Compare lock file <-> store <-> agent symlinks.

    Returns {missing_store, missing_links, stale_links, orphaned_store}
      missing_store:  lock entries whose store dir is gone
      missing_links:  (skill, agent) pairs that should be linked but aren't
      stale_links:    paths in agent dirs that are broken/unmanaged symlinks
      orphaned_store: store dirs not present in the lock file
    """
    lock = lockfile.installed()
    plan = None
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


def x_sync_plan__mutmut_3() -> Dict[str, list]:
    """Compare lock file <-> store <-> agent symlinks.

    Returns {missing_store, missing_links, stale_links, orphaned_store}
      missing_store:  lock entries whose store dir is gone
      missing_links:  (skill, agent) pairs that should be linked but aren't
      stale_links:    paths in agent dirs that are broken/unmanaged symlinks
      orphaned_store: store dirs not present in the lock file
    """
    lock = lockfile.installed()
    plan = {"XXmissing_storeXX": [], "missing_links": [],
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


def x_sync_plan__mutmut_4() -> Dict[str, list]:
    """Compare lock file <-> store <-> agent symlinks.

    Returns {missing_store, missing_links, stale_links, orphaned_store}
      missing_store:  lock entries whose store dir is gone
      missing_links:  (skill, agent) pairs that should be linked but aren't
      stale_links:    paths in agent dirs that are broken/unmanaged symlinks
      orphaned_store: store dirs not present in the lock file
    """
    lock = lockfile.installed()
    plan = {"MISSING_STORE": [], "missing_links": [],
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


def x_sync_plan__mutmut_5() -> Dict[str, list]:
    """Compare lock file <-> store <-> agent symlinks.

    Returns {missing_store, missing_links, stale_links, orphaned_store}
      missing_store:  lock entries whose store dir is gone
      missing_links:  (skill, agent) pairs that should be linked but aren't
      stale_links:    paths in agent dirs that are broken/unmanaged symlinks
      orphaned_store: store dirs not present in the lock file
    """
    lock = lockfile.installed()
    plan = {"missing_store": [], "XXmissing_linksXX": [],
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


def x_sync_plan__mutmut_6() -> Dict[str, list]:
    """Compare lock file <-> store <-> agent symlinks.

    Returns {missing_store, missing_links, stale_links, orphaned_store}
      missing_store:  lock entries whose store dir is gone
      missing_links:  (skill, agent) pairs that should be linked but aren't
      stale_links:    paths in agent dirs that are broken/unmanaged symlinks
      orphaned_store: store dirs not present in the lock file
    """
    lock = lockfile.installed()
    plan = {"missing_store": [], "MISSING_LINKS": [],
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


def x_sync_plan__mutmut_7() -> Dict[str, list]:
    """Compare lock file <-> store <-> agent symlinks.

    Returns {missing_store, missing_links, stale_links, orphaned_store}
      missing_store:  lock entries whose store dir is gone
      missing_links:  (skill, agent) pairs that should be linked but aren't
      stale_links:    paths in agent dirs that are broken/unmanaged symlinks
      orphaned_store: store dirs not present in the lock file
    """
    lock = lockfile.installed()
    plan = {"missing_store": [], "missing_links": [],
            "XXstale_linksXX": [], "orphaned_store": []}
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


def x_sync_plan__mutmut_8() -> Dict[str, list]:
    """Compare lock file <-> store <-> agent symlinks.

    Returns {missing_store, missing_links, stale_links, orphaned_store}
      missing_store:  lock entries whose store dir is gone
      missing_links:  (skill, agent) pairs that should be linked but aren't
      stale_links:    paths in agent dirs that are broken/unmanaged symlinks
      orphaned_store: store dirs not present in the lock file
    """
    lock = lockfile.installed()
    plan = {"missing_store": [], "missing_links": [],
            "STALE_LINKS": [], "orphaned_store": []}
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


def x_sync_plan__mutmut_9() -> Dict[str, list]:
    """Compare lock file <-> store <-> agent symlinks.

    Returns {missing_store, missing_links, stale_links, orphaned_store}
      missing_store:  lock entries whose store dir is gone
      missing_links:  (skill, agent) pairs that should be linked but aren't
      stale_links:    paths in agent dirs that are broken/unmanaged symlinks
      orphaned_store: store dirs not present in the lock file
    """
    lock = lockfile.installed()
    plan = {"missing_store": [], "missing_links": [],
            "stale_links": [], "XXorphaned_storeXX": []}
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


def x_sync_plan__mutmut_10() -> Dict[str, list]:
    """Compare lock file <-> store <-> agent symlinks.

    Returns {missing_store, missing_links, stale_links, orphaned_store}
      missing_store:  lock entries whose store dir is gone
      missing_links:  (skill, agent) pairs that should be linked but aren't
      stale_links:    paths in agent dirs that are broken/unmanaged symlinks
      orphaned_store: store dirs not present in the lock file
    """
    lock = lockfile.installed()
    plan = {"missing_store": [], "missing_links": [],
            "stale_links": [], "ORPHANED_STORE": []}
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


def x_sync_plan__mutmut_11() -> Dict[str, list]:
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
        sdir = None
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


def x_sync_plan__mutmut_12() -> Dict[str, list]:
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
        sdir = skill_store_dir(None)
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


def x_sync_plan__mutmut_13() -> Dict[str, list]:
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
        if sdir.is_dir():
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


def x_sync_plan__mutmut_14() -> Dict[str, list]:
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
            plan["missing_store"].append(None)
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


def x_sync_plan__mutmut_15() -> Dict[str, list]:
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
            plan["XXmissing_storeXX"].append(name)
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


def x_sync_plan__mutmut_16() -> Dict[str, list]:
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
            plan["MISSING_STORE"].append(name)
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


def x_sync_plan__mutmut_17() -> Dict[str, list]:
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
            break
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


def x_sync_plan__mutmut_18() -> Dict[str, list]:
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
        if entry.get(None):
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


def x_sync_plan__mutmut_19() -> Dict[str, list]:
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
        if entry.get("XXquarantinedXX"):
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


def x_sync_plan__mutmut_20() -> Dict[str, list]:
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
        if entry.get("QUARANTINED"):
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


def x_sync_plan__mutmut_21() -> Dict[str, list]:
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
            break
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


def x_sync_plan__mutmut_22() -> Dict[str, list]:
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
            link = None
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


def x_sync_plan__mutmut_23() -> Dict[str, list]:
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
            link = adir * name
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


def x_sync_plan__mutmut_24() -> Dict[str, list]:
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
            if not link.is_symlink() and not link.exists():
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


def x_sync_plan__mutmut_25() -> Dict[str, list]:
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
            if link.is_symlink() or not link.exists():
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


def x_sync_plan__mutmut_26() -> Dict[str, list]:
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
            if not link.is_symlink() or link.exists():
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


def x_sync_plan__mutmut_27() -> Dict[str, list]:
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
                plan["missing_links"].append(None)
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


def x_sync_plan__mutmut_28() -> Dict[str, list]:
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
                plan["XXmissing_linksXX"].append((name, agent))
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


def x_sync_plan__mutmut_29() -> Dict[str, list]:
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
                plan["MISSING_LINKS"].append((name, agent))
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


def x_sync_plan__mutmut_30() -> Dict[str, list]:
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
    store_root = None
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


def x_sync_plan__mutmut_31() -> Dict[str, list]:
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
            if child.is_dir() or child.name not in lock:
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


def x_sync_plan__mutmut_32() -> Dict[str, list]:
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
            if child.is_dir() and child.name in lock:
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


def x_sync_plan__mutmut_33() -> Dict[str, list]:
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
                plan["orphaned_store"].append(None)
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


def x_sync_plan__mutmut_34() -> Dict[str, list]:
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
                plan["XXorphaned_storeXX"].append(child.name)
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


def x_sync_plan__mutmut_35() -> Dict[str, list]:
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
                plan["ORPHANED_STORE"].append(child.name)
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


def x_sync_plan__mutmut_36() -> Dict[str, list]:
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
        if adir.is_dir():
            continue
        for link in adir.iterdir():
            if link.is_symlink():
                points_into_store = str(paths.store_dir()) in str(
                    link.resolve() if link.exists() else link.readlink())
                if not link.exists() or (points_into_store and link.name not in lock):
                    plan["stale_links"].append(str(link))
    return plan


def x_sync_plan__mutmut_37() -> Dict[str, list]:
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
            break
        for link in adir.iterdir():
            if link.is_symlink():
                points_into_store = str(paths.store_dir()) in str(
                    link.resolve() if link.exists() else link.readlink())
                if not link.exists() or (points_into_store and link.name not in lock):
                    plan["stale_links"].append(str(link))
    return plan


def x_sync_plan__mutmut_38() -> Dict[str, list]:
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
                points_into_store = None
                if not link.exists() or (points_into_store and link.name not in lock):
                    plan["stale_links"].append(str(link))
    return plan


def x_sync_plan__mutmut_39() -> Dict[str, list]:
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
                points_into_store = str(None) in str(
                    link.resolve() if link.exists() else link.readlink())
                if not link.exists() or (points_into_store and link.name not in lock):
                    plan["stale_links"].append(str(link))
    return plan


def x_sync_plan__mutmut_40() -> Dict[str, list]:
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
                points_into_store = str(paths.store_dir()) not in str(
                    link.resolve() if link.exists() else link.readlink())
                if not link.exists() or (points_into_store and link.name not in lock):
                    plan["stale_links"].append(str(link))
    return plan


def x_sync_plan__mutmut_41() -> Dict[str, list]:
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
                    None)
                if not link.exists() or (points_into_store and link.name not in lock):
                    plan["stale_links"].append(str(link))
    return plan


def x_sync_plan__mutmut_42() -> Dict[str, list]:
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
                if not link.exists() and (points_into_store and link.name not in lock):
                    plan["stale_links"].append(str(link))
    return plan


def x_sync_plan__mutmut_43() -> Dict[str, list]:
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
                if link.exists() or (points_into_store and link.name not in lock):
                    plan["stale_links"].append(str(link))
    return plan


def x_sync_plan__mutmut_44() -> Dict[str, list]:
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
                if not link.exists() or (points_into_store or link.name not in lock):
                    plan["stale_links"].append(str(link))
    return plan


def x_sync_plan__mutmut_45() -> Dict[str, list]:
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
                if not link.exists() or (points_into_store and link.name in lock):
                    plan["stale_links"].append(str(link))
    return plan


def x_sync_plan__mutmut_46() -> Dict[str, list]:
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
                    plan["stale_links"].append(None)
    return plan


def x_sync_plan__mutmut_47() -> Dict[str, list]:
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
                    plan["XXstale_linksXX"].append(str(link))
    return plan


def x_sync_plan__mutmut_48() -> Dict[str, list]:
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
                    plan["STALE_LINKS"].append(str(link))
    return plan


def x_sync_plan__mutmut_49() -> Dict[str, list]:
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
                    plan["stale_links"].append(str(None))
    return plan

mutants_x_sync_plan__mutmut['_mutmut_orig'] = x_sync_plan__mutmut_orig # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_1'] = x_sync_plan__mutmut_1 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_2'] = x_sync_plan__mutmut_2 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_3'] = x_sync_plan__mutmut_3 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_4'] = x_sync_plan__mutmut_4 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_5'] = x_sync_plan__mutmut_5 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_6'] = x_sync_plan__mutmut_6 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_7'] = x_sync_plan__mutmut_7 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_8'] = x_sync_plan__mutmut_8 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_9'] = x_sync_plan__mutmut_9 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_10'] = x_sync_plan__mutmut_10 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_11'] = x_sync_plan__mutmut_11 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_12'] = x_sync_plan__mutmut_12 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_13'] = x_sync_plan__mutmut_13 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_14'] = x_sync_plan__mutmut_14 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_15'] = x_sync_plan__mutmut_15 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_16'] = x_sync_plan__mutmut_16 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_17'] = x_sync_plan__mutmut_17 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_18'] = x_sync_plan__mutmut_18 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_19'] = x_sync_plan__mutmut_19 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_20'] = x_sync_plan__mutmut_20 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_21'] = x_sync_plan__mutmut_21 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_22'] = x_sync_plan__mutmut_22 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_23'] = x_sync_plan__mutmut_23 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_24'] = x_sync_plan__mutmut_24 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_25'] = x_sync_plan__mutmut_25 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_26'] = x_sync_plan__mutmut_26 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_27'] = x_sync_plan__mutmut_27 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_28'] = x_sync_plan__mutmut_28 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_29'] = x_sync_plan__mutmut_29 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_30'] = x_sync_plan__mutmut_30 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_31'] = x_sync_plan__mutmut_31 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_32'] = x_sync_plan__mutmut_32 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_33'] = x_sync_plan__mutmut_33 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_34'] = x_sync_plan__mutmut_34 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_35'] = x_sync_plan__mutmut_35 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_36'] = x_sync_plan__mutmut_36 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_37'] = x_sync_plan__mutmut_37 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_38'] = x_sync_plan__mutmut_38 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_39'] = x_sync_plan__mutmut_39 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_40'] = x_sync_plan__mutmut_40 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_41'] = x_sync_plan__mutmut_41 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_42'] = x_sync_plan__mutmut_42 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_43'] = x_sync_plan__mutmut_43 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_44'] = x_sync_plan__mutmut_44 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_45'] = x_sync_plan__mutmut_45 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_46'] = x_sync_plan__mutmut_46 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_47'] = x_sync_plan__mutmut_47 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_48'] = x_sync_plan__mutmut_48 # type: ignore # mutmut generated
mutants_x_sync_plan__mutmut['x_sync_plan__mutmut_49'] = x_sync_plan__mutmut_49 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_sync_apply__mutmut)
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


def x_sync_apply__mutmut_orig(plan: Dict[str, list]) -> List[str]:
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


def x_sync_apply__mutmut_1(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = None
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


def x_sync_apply__mutmut_2(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["XXmissing_linksXX"]:
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


def x_sync_apply__mutmut_3(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["MISSING_LINKS"]:
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


def x_sync_apply__mutmut_4(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["missing_links"]:
        res = None
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


def x_sync_apply__mutmut_5(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["missing_links"]:
        res = link_agents(None, only=[agent])
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


def x_sync_apply__mutmut_6(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["missing_links"]:
        res = link_agents(name, only=None)
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


def x_sync_apply__mutmut_7(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["missing_links"]:
        res = link_agents(only=[agent])
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


def x_sync_apply__mutmut_8(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["missing_links"]:
        res = link_agents(name, )
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


def x_sync_apply__mutmut_9(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["missing_links"]:
        res = link_agents(name, only=[agent])
        if agent not in res.linked:
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


def x_sync_apply__mutmut_10(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["missing_links"]:
        res = link_agents(name, only=[agent])
        if agent in res.linked:
            actions.append(None)
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


def x_sync_apply__mutmut_11(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["missing_links"]:
        res = link_agents(name, only=[agent])
        if agent in res.linked:
            actions.append("linked %s → %s" / (name, agent))
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


def x_sync_apply__mutmut_12(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["missing_links"]:
        res = link_agents(name, only=[agent])
        if agent in res.linked:
            actions.append("XXlinked %s → %sXX" % (name, agent))
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


def x_sync_apply__mutmut_13(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["missing_links"]:
        res = link_agents(name, only=[agent])
        if agent in res.linked:
            actions.append("LINKED %S → %S" % (name, agent))
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


def x_sync_apply__mutmut_14(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["missing_links"]:
        res = link_agents(name, only=[agent])
        if agent in res.linked:
            actions.append("linked %s → %s" % (name, agent))
    for path in plan["XXstale_linksXX"]:
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


def x_sync_apply__mutmut_15(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["missing_links"]:
        res = link_agents(name, only=[agent])
        if agent in res.linked:
            actions.append("linked %s → %s" % (name, agent))
    for path in plan["STALE_LINKS"]:
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


def x_sync_apply__mutmut_16(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["missing_links"]:
        res = link_agents(name, only=[agent])
        if agent in res.linked:
            actions.append("linked %s → %s" % (name, agent))
    for path in plan["stale_links"]:
        p = None
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


def x_sync_apply__mutmut_17(plan: Dict[str, list]) -> List[str]:
    """Fix what sync_plan found. Returns human-readable actions taken."""
    actions = []
    for name, agent in plan["missing_links"]:
        res = link_agents(name, only=[agent])
        if agent in res.linked:
            actions.append("linked %s → %s" % (name, agent))
    for path in plan["stale_links"]:
        p = Path(None)
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


def x_sync_apply__mutmut_18(plan: Dict[str, list]) -> List[str]:
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
            actions.append(None)
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


def x_sync_apply__mutmut_19(plan: Dict[str, list]) -> List[str]:
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
            actions.append("removed stale link %s" / path)
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


def x_sync_apply__mutmut_20(plan: Dict[str, list]) -> List[str]:
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
            actions.append("XXremoved stale link %sXX" % path)
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


def x_sync_apply__mutmut_21(plan: Dict[str, list]) -> List[str]:
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
            actions.append("REMOVED STALE LINK %S" % path)
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


def x_sync_apply__mutmut_22(plan: Dict[str, list]) -> List[str]:
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
    for name in plan["XXmissing_storeXX"]:
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


def x_sync_apply__mutmut_23(plan: Dict[str, list]) -> List[str]:
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
    for name in plan["MISSING_STORE"]:
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


def x_sync_apply__mutmut_24(plan: Dict[str, list]) -> List[str]:
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
        entry = None
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


def x_sync_apply__mutmut_25(plan: Dict[str, list]) -> List[str]:
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
        entry = lockfile.get_skill(name) and {}
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


def x_sync_apply__mutmut_26(plan: Dict[str, list]) -> List[str]:
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
        entry = lockfile.get_skill(None) or {}
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


def x_sync_apply__mutmut_27(plan: Dict[str, list]) -> List[str]:
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
        tap_name = None
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


def x_sync_apply__mutmut_28(plan: Dict[str, list]) -> List[str]:
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
        tap_name = entry.get(None)
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


def x_sync_apply__mutmut_29(plan: Dict[str, list]) -> List[str]:
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
        tap_name = entry.get("XXtapXX")
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


def x_sync_apply__mutmut_30(plan: Dict[str, list]) -> List[str]:
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
        tap_name = entry.get("TAP")
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


def x_sync_apply__mutmut_31(plan: Dict[str, list]) -> List[str]:
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
        restored = None
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


def x_sync_apply__mutmut_32(plan: Dict[str, list]) -> List[str]:
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
        restored = True
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


def x_sync_apply__mutmut_33(plan: Dict[str, list]) -> List[str]:
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
        if tap_name or tap_name != "local":
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


def x_sync_apply__mutmut_34(plan: Dict[str, list]) -> List[str]:
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
        if tap_name and tap_name == "local":
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


def x_sync_apply__mutmut_35(plan: Dict[str, list]) -> List[str]:
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
        if tap_name and tap_name != "XXlocalXX":
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


def x_sync_apply__mutmut_36(plan: Dict[str, list]) -> List[str]:
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
        if tap_name and tap_name != "LOCAL":
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


def x_sync_apply__mutmut_37(plan: Dict[str, list]) -> List[str]:
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
                matches = None
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


def x_sync_apply__mutmut_38(plan: Dict[str, list]) -> List[str]:
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
                matches = [e for e in catalog.find(None) if e["tap"] == tap_name]
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


def x_sync_apply__mutmut_39(plan: Dict[str, list]) -> List[str]:
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
                matches = [e for e in catalog.rfind(name) if e["tap"] == tap_name]
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


def x_sync_apply__mutmut_40(plan: Dict[str, list]) -> List[str]:
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
                matches = [e for e in catalog.find(name) if e["XXtapXX"] == tap_name]
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


def x_sync_apply__mutmut_41(plan: Dict[str, list]) -> List[str]:
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
                matches = [e for e in catalog.find(name) if e["TAP"] == tap_name]
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


def x_sync_apply__mutmut_42(plan: Dict[str, list]) -> List[str]:
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
                matches = [e for e in catalog.find(name) if e["tap"] != tap_name]
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


def x_sync_apply__mutmut_43(plan: Dict[str, list]) -> List[str]:
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
                    install(None, force=True)
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


def x_sync_apply__mutmut_44(plan: Dict[str, list]) -> List[str]:
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
                    install(matches[0], force=None)
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


def x_sync_apply__mutmut_45(plan: Dict[str, list]) -> List[str]:
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
                    install(force=True)
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


def x_sync_apply__mutmut_46(plan: Dict[str, list]) -> List[str]:
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
                    install(matches[0], )
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


def x_sync_apply__mutmut_47(plan: Dict[str, list]) -> List[str]:
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
                    install(matches[1], force=True)
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


def x_sync_apply__mutmut_48(plan: Dict[str, list]) -> List[str]:
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
                    install(matches[0], force=False)
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


def x_sync_apply__mutmut_49(plan: Dict[str, list]) -> List[str]:
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
                    actions.append(None)
                    restored = True
            except BoostError:
                pass
        if not restored:
            lockfile.remove_skill(name)
            actions.append("dropped %s from lock (store dir missing, source gone)" % name)
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_50(plan: Dict[str, list]) -> List[str]:
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
                    actions.append("reinstalled missing %s from %s" / (name, tap_name))
                    restored = True
            except BoostError:
                pass
        if not restored:
            lockfile.remove_skill(name)
            actions.append("dropped %s from lock (store dir missing, source gone)" % name)
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_51(plan: Dict[str, list]) -> List[str]:
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
                    actions.append("XXreinstalled missing %s from %sXX" % (name, tap_name))
                    restored = True
            except BoostError:
                pass
        if not restored:
            lockfile.remove_skill(name)
            actions.append("dropped %s from lock (store dir missing, source gone)" % name)
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_52(plan: Dict[str, list]) -> List[str]:
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
                    actions.append("REINSTALLED MISSING %S FROM %S" % (name, tap_name))
                    restored = True
            except BoostError:
                pass
        if not restored:
            lockfile.remove_skill(name)
            actions.append("dropped %s from lock (store dir missing, source gone)" % name)
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_53(plan: Dict[str, list]) -> List[str]:
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
                    restored = None
            except BoostError:
                pass
        if not restored:
            lockfile.remove_skill(name)
            actions.append("dropped %s from lock (store dir missing, source gone)" % name)
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_54(plan: Dict[str, list]) -> List[str]:
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
                    restored = False
            except BoostError:
                pass
        if not restored:
            lockfile.remove_skill(name)
            actions.append("dropped %s from lock (store dir missing, source gone)" % name)
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_55(plan: Dict[str, list]) -> List[str]:
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
        if restored:
            lockfile.remove_skill(name)
            actions.append("dropped %s from lock (store dir missing, source gone)" % name)
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_56(plan: Dict[str, list]) -> List[str]:
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
            lockfile.remove_skill(None)
            actions.append("dropped %s from lock (store dir missing, source gone)" % name)
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_57(plan: Dict[str, list]) -> List[str]:
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
            actions.append(None)
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_58(plan: Dict[str, list]) -> List[str]:
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
            actions.append("dropped %s from lock (store dir missing, source gone)" / name)
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_59(plan: Dict[str, list]) -> List[str]:
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
            actions.append("XXdropped %s from lock (store dir missing, source gone)XX" % name)
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_60(plan: Dict[str, list]) -> List[str]:
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
            actions.append("DROPPED %S FROM LOCK (STORE DIR MISSING, SOURCE GONE)" % name)
    if actions:
        journal.log("sync", "%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_61(plan: Dict[str, list]) -> List[str]:
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
        journal.log(None, "%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_62(plan: Dict[str, list]) -> List[str]:
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
        journal.log("sync", None)
    return actions


def x_sync_apply__mutmut_63(plan: Dict[str, list]) -> List[str]:
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
        journal.log("%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_64(plan: Dict[str, list]) -> List[str]:
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
        journal.log("sync", )
    return actions


def x_sync_apply__mutmut_65(plan: Dict[str, list]) -> List[str]:
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
        journal.log("XXsyncXX", "%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_66(plan: Dict[str, list]) -> List[str]:
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
        journal.log("SYNC", "%d fixes" % len(actions))
    return actions


def x_sync_apply__mutmut_67(plan: Dict[str, list]) -> List[str]:
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
        journal.log("sync", "%d fixes" / len(actions))
    return actions


def x_sync_apply__mutmut_68(plan: Dict[str, list]) -> List[str]:
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
        journal.log("sync", "XX%d fixesXX" % len(actions))
    return actions


def x_sync_apply__mutmut_69(plan: Dict[str, list]) -> List[str]:
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
        journal.log("sync", "%D FIXES" % len(actions))
    return actions

mutants_x_sync_apply__mutmut['_mutmut_orig'] = x_sync_apply__mutmut_orig # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_1'] = x_sync_apply__mutmut_1 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_2'] = x_sync_apply__mutmut_2 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_3'] = x_sync_apply__mutmut_3 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_4'] = x_sync_apply__mutmut_4 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_5'] = x_sync_apply__mutmut_5 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_6'] = x_sync_apply__mutmut_6 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_7'] = x_sync_apply__mutmut_7 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_8'] = x_sync_apply__mutmut_8 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_9'] = x_sync_apply__mutmut_9 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_10'] = x_sync_apply__mutmut_10 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_11'] = x_sync_apply__mutmut_11 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_12'] = x_sync_apply__mutmut_12 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_13'] = x_sync_apply__mutmut_13 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_14'] = x_sync_apply__mutmut_14 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_15'] = x_sync_apply__mutmut_15 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_16'] = x_sync_apply__mutmut_16 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_17'] = x_sync_apply__mutmut_17 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_18'] = x_sync_apply__mutmut_18 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_19'] = x_sync_apply__mutmut_19 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_20'] = x_sync_apply__mutmut_20 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_21'] = x_sync_apply__mutmut_21 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_22'] = x_sync_apply__mutmut_22 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_23'] = x_sync_apply__mutmut_23 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_24'] = x_sync_apply__mutmut_24 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_25'] = x_sync_apply__mutmut_25 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_26'] = x_sync_apply__mutmut_26 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_27'] = x_sync_apply__mutmut_27 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_28'] = x_sync_apply__mutmut_28 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_29'] = x_sync_apply__mutmut_29 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_30'] = x_sync_apply__mutmut_30 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_31'] = x_sync_apply__mutmut_31 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_32'] = x_sync_apply__mutmut_32 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_33'] = x_sync_apply__mutmut_33 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_34'] = x_sync_apply__mutmut_34 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_35'] = x_sync_apply__mutmut_35 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_36'] = x_sync_apply__mutmut_36 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_37'] = x_sync_apply__mutmut_37 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_38'] = x_sync_apply__mutmut_38 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_39'] = x_sync_apply__mutmut_39 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_40'] = x_sync_apply__mutmut_40 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_41'] = x_sync_apply__mutmut_41 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_42'] = x_sync_apply__mutmut_42 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_43'] = x_sync_apply__mutmut_43 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_44'] = x_sync_apply__mutmut_44 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_45'] = x_sync_apply__mutmut_45 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_46'] = x_sync_apply__mutmut_46 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_47'] = x_sync_apply__mutmut_47 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_48'] = x_sync_apply__mutmut_48 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_49'] = x_sync_apply__mutmut_49 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_50'] = x_sync_apply__mutmut_50 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_51'] = x_sync_apply__mutmut_51 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_52'] = x_sync_apply__mutmut_52 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_53'] = x_sync_apply__mutmut_53 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_54'] = x_sync_apply__mutmut_54 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_55'] = x_sync_apply__mutmut_55 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_56'] = x_sync_apply__mutmut_56 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_57'] = x_sync_apply__mutmut_57 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_58'] = x_sync_apply__mutmut_58 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_59'] = x_sync_apply__mutmut_59 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_60'] = x_sync_apply__mutmut_60 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_61'] = x_sync_apply__mutmut_61 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_62'] = x_sync_apply__mutmut_62 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_63'] = x_sync_apply__mutmut_63 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_64'] = x_sync_apply__mutmut_64 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_65'] = x_sync_apply__mutmut_65 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_66'] = x_sync_apply__mutmut_66 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_67'] = x_sync_apply__mutmut_67 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_68'] = x_sync_apply__mutmut_68 # type: ignore # mutmut generated
mutants_x_sync_apply__mutmut['x_sync_apply__mutmut_69'] = x_sync_apply__mutmut_69 # type: ignore # mutmut generated
