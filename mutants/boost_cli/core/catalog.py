"""Skill catalogs: scan tap repos for SKILL.md files -> JSON caches -> search.

A catalog entry (plain dict) has:
  name, description, version, tap, curated,
  rel_dir   -- skill directory relative to the tap repo root
  skill_md  -- path of the SKILL.md relative to the repo root
  meta      -- full parsed frontmatter
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional

from ..errors import BoostError
from . import frontmatter, gitutil, paths, registry, util


from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated, MutantDict
mutants_x_scan_dir__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_scan_dir__mutmut)
def scan_dir(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_orig(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_1(root: Path, tap_name: str = "XXlocalXX", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_2(root: Path, tap_name: str = "LOCAL", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_3(root: Path, tap_name: str = "local", curated: bool = True) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_4(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = None
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_5(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(None)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_6(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = None
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_7(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(None):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_8(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob(None)):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_9(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("XXSKILL.mdXX")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_10(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("skill.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_11(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.MD")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_12(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(None):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_13(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part not in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_14(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            break
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_15(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = None
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_16(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                None)
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_17(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding=None, errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_18(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors=None))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_19(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_20(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", ))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_21(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="XXutf-8XX", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_22(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="UTF-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_23(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="XXreplaceXX"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_24(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="REPLACE"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_25(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            break
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_26(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = None
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_27(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = None
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_28(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() and (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_29(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(None).strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_30(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") and "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_31(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get(None) or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_32(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("XXnameXX") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_33(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("NAME") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_34(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "XXXX").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_35(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir == root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_36(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = None
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_37(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(None).strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_38(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") and "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_39(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get(None) or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_40(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("XXdescriptionXX") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_41(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("DESCRIPTION") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_42(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "XXXX").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_43(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_44(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = None
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_45(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line or not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_46(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_47(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith(None):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_48(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("XX#XX"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_49(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = None
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_50(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:161]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_51(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    return
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_52(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append(None)
    return entries


def x_scan_dir__mutmut_53(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "XXnameXX": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_54(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "NAME": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_55(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(None) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_56(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if "XX XX" in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_57(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " not in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_58(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "XXdescriptionXX": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_59(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "DESCRIPTION": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_60(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "XXversionXX": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_61(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "VERSION": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_62(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(None),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_63(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") and "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_64(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get(None) or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_65(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("XXversionXX") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_66(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("VERSION") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_67(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "XX0.0.0XX"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_68(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "XXtapXX": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_69(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "TAP": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_70(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "XXcuratedXX": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_71(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "CURATED": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_72(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "XXrel_dirXX": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_73(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "REL_DIR": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_74(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(None) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_75(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(None)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_76(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir == root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_77(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else "XX.XX",
            "skill_md": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_78(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "XXskill_mdXX": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_79(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "SKILL_MD": str(skill_md.relative_to(root)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_80(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(None),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_81(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(None)),
            "meta": meta,
        })
    return entries


def x_scan_dir__mutmut_82(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "XXmetaXX": meta,
        })
    return entries


def x_scan_dir__mutmut_83(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in util.IGNORED for part in skill_md.parts):
            continue
        try:
            meta, body = frontmatter.parse(
                skill_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        skill_dir = skill_md.parent
        name = str(meta.get("name") or "").strip() or (
            skill_dir.name if skill_dir != root else root.name)
        desc = str(meta.get("description") or "").strip()
        if not desc:
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
        entries.append({
            "name": util.slugify(name) if " " in name else name,
            "description": desc,
            "version": str(meta.get("version") or "0.0.0"),
            "tap": tap_name,
            "curated": curated,
            "rel_dir": str(skill_dir.relative_to(root)) if skill_dir != root else ".",
            "skill_md": str(skill_md.relative_to(root)),
            "META": meta,
        })
    return entries

mutants_x_scan_dir__mutmut['_mutmut_orig'] = x_scan_dir__mutmut_orig # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_1'] = x_scan_dir__mutmut_1 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_2'] = x_scan_dir__mutmut_2 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_3'] = x_scan_dir__mutmut_3 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_4'] = x_scan_dir__mutmut_4 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_5'] = x_scan_dir__mutmut_5 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_6'] = x_scan_dir__mutmut_6 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_7'] = x_scan_dir__mutmut_7 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_8'] = x_scan_dir__mutmut_8 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_9'] = x_scan_dir__mutmut_9 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_10'] = x_scan_dir__mutmut_10 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_11'] = x_scan_dir__mutmut_11 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_12'] = x_scan_dir__mutmut_12 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_13'] = x_scan_dir__mutmut_13 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_14'] = x_scan_dir__mutmut_14 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_15'] = x_scan_dir__mutmut_15 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_16'] = x_scan_dir__mutmut_16 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_17'] = x_scan_dir__mutmut_17 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_18'] = x_scan_dir__mutmut_18 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_19'] = x_scan_dir__mutmut_19 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_20'] = x_scan_dir__mutmut_20 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_21'] = x_scan_dir__mutmut_21 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_22'] = x_scan_dir__mutmut_22 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_23'] = x_scan_dir__mutmut_23 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_24'] = x_scan_dir__mutmut_24 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_25'] = x_scan_dir__mutmut_25 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_26'] = x_scan_dir__mutmut_26 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_27'] = x_scan_dir__mutmut_27 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_28'] = x_scan_dir__mutmut_28 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_29'] = x_scan_dir__mutmut_29 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_30'] = x_scan_dir__mutmut_30 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_31'] = x_scan_dir__mutmut_31 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_32'] = x_scan_dir__mutmut_32 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_33'] = x_scan_dir__mutmut_33 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_34'] = x_scan_dir__mutmut_34 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_35'] = x_scan_dir__mutmut_35 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_36'] = x_scan_dir__mutmut_36 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_37'] = x_scan_dir__mutmut_37 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_38'] = x_scan_dir__mutmut_38 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_39'] = x_scan_dir__mutmut_39 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_40'] = x_scan_dir__mutmut_40 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_41'] = x_scan_dir__mutmut_41 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_42'] = x_scan_dir__mutmut_42 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_43'] = x_scan_dir__mutmut_43 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_44'] = x_scan_dir__mutmut_44 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_45'] = x_scan_dir__mutmut_45 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_46'] = x_scan_dir__mutmut_46 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_47'] = x_scan_dir__mutmut_47 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_48'] = x_scan_dir__mutmut_48 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_49'] = x_scan_dir__mutmut_49 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_50'] = x_scan_dir__mutmut_50 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_51'] = x_scan_dir__mutmut_51 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_52'] = x_scan_dir__mutmut_52 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_53'] = x_scan_dir__mutmut_53 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_54'] = x_scan_dir__mutmut_54 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_55'] = x_scan_dir__mutmut_55 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_56'] = x_scan_dir__mutmut_56 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_57'] = x_scan_dir__mutmut_57 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_58'] = x_scan_dir__mutmut_58 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_59'] = x_scan_dir__mutmut_59 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_60'] = x_scan_dir__mutmut_60 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_61'] = x_scan_dir__mutmut_61 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_62'] = x_scan_dir__mutmut_62 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_63'] = x_scan_dir__mutmut_63 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_64'] = x_scan_dir__mutmut_64 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_65'] = x_scan_dir__mutmut_65 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_66'] = x_scan_dir__mutmut_66 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_67'] = x_scan_dir__mutmut_67 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_68'] = x_scan_dir__mutmut_68 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_69'] = x_scan_dir__mutmut_69 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_70'] = x_scan_dir__mutmut_70 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_71'] = x_scan_dir__mutmut_71 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_72'] = x_scan_dir__mutmut_72 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_73'] = x_scan_dir__mutmut_73 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_74'] = x_scan_dir__mutmut_74 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_75'] = x_scan_dir__mutmut_75 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_76'] = x_scan_dir__mutmut_76 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_77'] = x_scan_dir__mutmut_77 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_78'] = x_scan_dir__mutmut_78 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_79'] = x_scan_dir__mutmut_79 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_80'] = x_scan_dir__mutmut_80 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_81'] = x_scan_dir__mutmut_81 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_82'] = x_scan_dir__mutmut_82 # type: ignore # mutmut generated
mutants_x_scan_dir__mutmut['x_scan_dir__mutmut_83'] = x_scan_dir__mutmut_83 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_rebuild_tap__mutmut)
def rebuild_tap(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_orig(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_1(tap: "registry.Tap") -> List[dict]:
    if tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_2(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError(None,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_3(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint=None)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_4(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError(hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_5(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        )
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_6(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" / tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_7(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("XXtap %s is not clonedXX" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_8(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("TAP %S IS NOT CLONED" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_9(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" / tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_10(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="XXrun `boost update %s`XX" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_11(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="RUN `BOOST UPDATE %S`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_12(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = None
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_13(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(None, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_14(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, None, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_15(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, None)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_16(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_17(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_18(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, )
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_19(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(None)
    return entries


def x_rebuild_tap__mutmut_20(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps(None, indent=1))
    return entries


def x_rebuild_tap__mutmut_21(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=None))
    return entries


def x_rebuild_tap__mutmut_22(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps(indent=1))
    return entries


def x_rebuild_tap__mutmut_23(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, ))
    return entries


def x_rebuild_tap__mutmut_24(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "XXtapXX": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_25(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "TAP": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_26(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "XXurlXX": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_27(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "URL": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_28(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "XXgeneratedXX": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_29(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "GENERATED": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_30(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "XXcommitXX": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_31(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "COMMIT": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_32(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(None),
        "skills": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_33(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "XXskillsXX": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_34(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "SKILLS": entries,
    }, indent=1))
    return entries


def x_rebuild_tap__mutmut_35(tap: "registry.Tap") -> List[dict]:
    if not tap.is_cloned:
        raise BoostError("tap %s is not cloned" % tap.name,
                        hint="run `boost update %s`" % tap.name)
    entries = scan_dir(tap.path, tap.name, tap.curated)
    paths.ensure_dirs()
    tap.cache_file.write_text(json.dumps({
        "tap": tap.name,
        "url": tap.url,
        "generated": util.now_iso(),
        "commit": gitutil.head_commit(tap.path),
        "skills": entries,
    }, indent=2))
    return entries

mutants_x_rebuild_tap__mutmut['_mutmut_orig'] = x_rebuild_tap__mutmut_orig # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_1'] = x_rebuild_tap__mutmut_1 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_2'] = x_rebuild_tap__mutmut_2 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_3'] = x_rebuild_tap__mutmut_3 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_4'] = x_rebuild_tap__mutmut_4 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_5'] = x_rebuild_tap__mutmut_5 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_6'] = x_rebuild_tap__mutmut_6 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_7'] = x_rebuild_tap__mutmut_7 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_8'] = x_rebuild_tap__mutmut_8 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_9'] = x_rebuild_tap__mutmut_9 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_10'] = x_rebuild_tap__mutmut_10 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_11'] = x_rebuild_tap__mutmut_11 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_12'] = x_rebuild_tap__mutmut_12 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_13'] = x_rebuild_tap__mutmut_13 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_14'] = x_rebuild_tap__mutmut_14 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_15'] = x_rebuild_tap__mutmut_15 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_16'] = x_rebuild_tap__mutmut_16 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_17'] = x_rebuild_tap__mutmut_17 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_18'] = x_rebuild_tap__mutmut_18 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_19'] = x_rebuild_tap__mutmut_19 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_20'] = x_rebuild_tap__mutmut_20 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_21'] = x_rebuild_tap__mutmut_21 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_22'] = x_rebuild_tap__mutmut_22 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_23'] = x_rebuild_tap__mutmut_23 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_24'] = x_rebuild_tap__mutmut_24 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_25'] = x_rebuild_tap__mutmut_25 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_26'] = x_rebuild_tap__mutmut_26 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_27'] = x_rebuild_tap__mutmut_27 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_28'] = x_rebuild_tap__mutmut_28 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_29'] = x_rebuild_tap__mutmut_29 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_30'] = x_rebuild_tap__mutmut_30 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_31'] = x_rebuild_tap__mutmut_31 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_32'] = x_rebuild_tap__mutmut_32 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_33'] = x_rebuild_tap__mutmut_33 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_34'] = x_rebuild_tap__mutmut_34 # type: ignore # mutmut generated
mutants_x_rebuild_tap__mutmut['x_rebuild_tap__mutmut_35'] = x_rebuild_tap__mutmut_35 # type: ignore # mutmut generated
mutants_x_load_tap__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_load_tap__mutmut)
def load_tap(tap: "registry.Tap", rebuild: bool = False) -> List[dict]:
    if not rebuild and tap.cache_file.exists():
        try:
            return json.loads(tap.cache_file.read_text()).get("skills", [])
        except (json.JSONDecodeError, OSError):
            pass
    if tap.is_cloned:
        return rebuild_tap(tap)
    return []


def x_load_tap__mutmut_orig(tap: "registry.Tap", rebuild: bool = False) -> List[dict]:
    if not rebuild and tap.cache_file.exists():
        try:
            return json.loads(tap.cache_file.read_text()).get("skills", [])
        except (json.JSONDecodeError, OSError):
            pass
    if tap.is_cloned:
        return rebuild_tap(tap)
    return []


def x_load_tap__mutmut_1(tap: "registry.Tap", rebuild: bool = True) -> List[dict]:
    if not rebuild and tap.cache_file.exists():
        try:
            return json.loads(tap.cache_file.read_text()).get("skills", [])
        except (json.JSONDecodeError, OSError):
            pass
    if tap.is_cloned:
        return rebuild_tap(tap)
    return []


def x_load_tap__mutmut_2(tap: "registry.Tap", rebuild: bool = False) -> List[dict]:
    if not rebuild or tap.cache_file.exists():
        try:
            return json.loads(tap.cache_file.read_text()).get("skills", [])
        except (json.JSONDecodeError, OSError):
            pass
    if tap.is_cloned:
        return rebuild_tap(tap)
    return []


def x_load_tap__mutmut_3(tap: "registry.Tap", rebuild: bool = False) -> List[dict]:
    if rebuild and tap.cache_file.exists():
        try:
            return json.loads(tap.cache_file.read_text()).get("skills", [])
        except (json.JSONDecodeError, OSError):
            pass
    if tap.is_cloned:
        return rebuild_tap(tap)
    return []


def x_load_tap__mutmut_4(tap: "registry.Tap", rebuild: bool = False) -> List[dict]:
    if not rebuild and tap.cache_file.exists():
        try:
            return json.loads(tap.cache_file.read_text()).get(None, [])
        except (json.JSONDecodeError, OSError):
            pass
    if tap.is_cloned:
        return rebuild_tap(tap)
    return []


def x_load_tap__mutmut_5(tap: "registry.Tap", rebuild: bool = False) -> List[dict]:
    if not rebuild and tap.cache_file.exists():
        try:
            return json.loads(tap.cache_file.read_text()).get("skills", None)
        except (json.JSONDecodeError, OSError):
            pass
    if tap.is_cloned:
        return rebuild_tap(tap)
    return []


def x_load_tap__mutmut_6(tap: "registry.Tap", rebuild: bool = False) -> List[dict]:
    if not rebuild and tap.cache_file.exists():
        try:
            return json.loads(tap.cache_file.read_text()).get([])
        except (json.JSONDecodeError, OSError):
            pass
    if tap.is_cloned:
        return rebuild_tap(tap)
    return []


def x_load_tap__mutmut_7(tap: "registry.Tap", rebuild: bool = False) -> List[dict]:
    if not rebuild and tap.cache_file.exists():
        try:
            return json.loads(tap.cache_file.read_text()).get("skills", )
        except (json.JSONDecodeError, OSError):
            pass
    if tap.is_cloned:
        return rebuild_tap(tap)
    return []


def x_load_tap__mutmut_8(tap: "registry.Tap", rebuild: bool = False) -> List[dict]:
    if not rebuild and tap.cache_file.exists():
        try:
            return json.loads(None).get("skills", [])
        except (json.JSONDecodeError, OSError):
            pass
    if tap.is_cloned:
        return rebuild_tap(tap)
    return []


def x_load_tap__mutmut_9(tap: "registry.Tap", rebuild: bool = False) -> List[dict]:
    if not rebuild and tap.cache_file.exists():
        try:
            return json.loads(tap.cache_file.read_text()).get("XXskillsXX", [])
        except (json.JSONDecodeError, OSError):
            pass
    if tap.is_cloned:
        return rebuild_tap(tap)
    return []


def x_load_tap__mutmut_10(tap: "registry.Tap", rebuild: bool = False) -> List[dict]:
    if not rebuild and tap.cache_file.exists():
        try:
            return json.loads(tap.cache_file.read_text()).get("SKILLS", [])
        except (json.JSONDecodeError, OSError):
            pass
    if tap.is_cloned:
        return rebuild_tap(tap)
    return []


def x_load_tap__mutmut_11(tap: "registry.Tap", rebuild: bool = False) -> List[dict]:
    if not rebuild and tap.cache_file.exists():
        try:
            return json.loads(tap.cache_file.read_text()).get("skills", [])
        except (json.JSONDecodeError, OSError):
            pass
    if tap.is_cloned:
        return rebuild_tap(None)
    return []

mutants_x_load_tap__mutmut['_mutmut_orig'] = x_load_tap__mutmut_orig # type: ignore # mutmut generated
mutants_x_load_tap__mutmut['x_load_tap__mutmut_1'] = x_load_tap__mutmut_1 # type: ignore # mutmut generated
mutants_x_load_tap__mutmut['x_load_tap__mutmut_2'] = x_load_tap__mutmut_2 # type: ignore # mutmut generated
mutants_x_load_tap__mutmut['x_load_tap__mutmut_3'] = x_load_tap__mutmut_3 # type: ignore # mutmut generated
mutants_x_load_tap__mutmut['x_load_tap__mutmut_4'] = x_load_tap__mutmut_4 # type: ignore # mutmut generated
mutants_x_load_tap__mutmut['x_load_tap__mutmut_5'] = x_load_tap__mutmut_5 # type: ignore # mutmut generated
mutants_x_load_tap__mutmut['x_load_tap__mutmut_6'] = x_load_tap__mutmut_6 # type: ignore # mutmut generated
mutants_x_load_tap__mutmut['x_load_tap__mutmut_7'] = x_load_tap__mutmut_7 # type: ignore # mutmut generated
mutants_x_load_tap__mutmut['x_load_tap__mutmut_8'] = x_load_tap__mutmut_8 # type: ignore # mutmut generated
mutants_x_load_tap__mutmut['x_load_tap__mutmut_9'] = x_load_tap__mutmut_9 # type: ignore # mutmut generated
mutants_x_load_tap__mutmut['x_load_tap__mutmut_10'] = x_load_tap__mutmut_10 # type: ignore # mutmut generated
mutants_x_load_tap__mutmut['x_load_tap__mutmut_11'] = x_load_tap__mutmut_11 # type: ignore # mutmut generated
mutants_x_all_entries__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_all_entries__mutmut)
def all_entries() -> List[dict]:
    out: List[dict] = []
    for tap in registry.list_taps():
        out.extend(load_tap(tap))
    return out


def x_all_entries__mutmut_orig() -> List[dict]:
    out: List[dict] = []
    for tap in registry.list_taps():
        out.extend(load_tap(tap))
    return out


def x_all_entries__mutmut_1() -> List[dict]:
    out: List[dict] = None
    for tap in registry.list_taps():
        out.extend(load_tap(tap))
    return out


def x_all_entries__mutmut_2() -> List[dict]:
    out: List[dict] = []
    for tap in registry.list_taps():
        out.extend(None)
    return out


def x_all_entries__mutmut_3() -> List[dict]:
    out: List[dict] = []
    for tap in registry.list_taps():
        out.extend(load_tap(None))
    return out

mutants_x_all_entries__mutmut['_mutmut_orig'] = x_all_entries__mutmut_orig # type: ignore # mutmut generated
mutants_x_all_entries__mutmut['x_all_entries__mutmut_1'] = x_all_entries__mutmut_1 # type: ignore # mutmut generated
mutants_x_all_entries__mutmut['x_all_entries__mutmut_2'] = x_all_entries__mutmut_2 # type: ignore # mutmut generated
mutants_x_all_entries__mutmut['x_all_entries__mutmut_3'] = x_all_entries__mutmut_3 # type: ignore # mutmut generated
mutants_x_find__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_find__mutmut)
def find(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_orig(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_1(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if "XX:XX" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_2(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" not in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_3(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = None
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_4(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(None, 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_5(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", None)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_6(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_7(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", )
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_8(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.split(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_9(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit("XX:XX", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_10(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 2)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_11(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = None
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_12(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["XXnameXX"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_13(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["NAME"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_14(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] != name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_15(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = None
    return matches


def x_find__mutmut_16(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap and e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_17(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["XXtapXX"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_18(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["TAP"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_19(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] != tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_20(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split(None)[-1] == tap]
    return matches


def x_find__mutmut_21(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["XXtapXX"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_22(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["TAP"].split("/")[-1] == tap]
    return matches


def x_find__mutmut_23(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("XX/XX")[-1] == tap]
    return matches


def x_find__mutmut_24(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[+1] == tap]
    return matches


def x_find__mutmut_25(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-2] == tap]
    return matches


def x_find__mutmut_26(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] != tap]
    return matches

mutants_x_find__mutmut['_mutmut_orig'] = x_find__mutmut_orig # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_1'] = x_find__mutmut_1 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_2'] = x_find__mutmut_2 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_3'] = x_find__mutmut_3 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_4'] = x_find__mutmut_4 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_5'] = x_find__mutmut_5 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_6'] = x_find__mutmut_6 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_7'] = x_find__mutmut_7 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_8'] = x_find__mutmut_8 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_9'] = x_find__mutmut_9 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_10'] = x_find__mutmut_10 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_11'] = x_find__mutmut_11 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_12'] = x_find__mutmut_12 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_13'] = x_find__mutmut_13 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_14'] = x_find__mutmut_14 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_15'] = x_find__mutmut_15 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_16'] = x_find__mutmut_16 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_17'] = x_find__mutmut_17 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_18'] = x_find__mutmut_18 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_19'] = x_find__mutmut_19 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_20'] = x_find__mutmut_20 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_21'] = x_find__mutmut_21 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_22'] = x_find__mutmut_22 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_23'] = x_find__mutmut_23 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_24'] = x_find__mutmut_24 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_25'] = x_find__mutmut_25 # type: ignore # mutmut generated
mutants_x_find__mutmut['x_find__mutmut_26'] = x_find__mutmut_26 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_resolve_one__mutmut)
def resolve_one(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_orig(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_1(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = None
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_2(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(None)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_3(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_4(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = None
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_5(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(None)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_6(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:4]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_7(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = ""
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_8(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = None
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_9(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " - ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_10(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "XXclosest matches: XX" + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_11(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "CLOSEST MATCHES: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_12(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(None)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_13(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + "XX, XX".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_14(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["XXnameXX"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_15(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["NAME"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_16(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_17(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = None
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_18(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "XXno taps configured — start with `boost tap --defaults`XX"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_19(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "NO TAPS CONFIGURED — START WITH `BOOST TAP --DEFAULTS`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_20(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError(None, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_21(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=None)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_22(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError(hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_23(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, )
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_24(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" / name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_25(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("XXno skill named %r in any tapXX" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_26(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("NO SKILL NAMED %R IN ANY TAP" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_27(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) >= 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_28(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 2:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_29(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            None,
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_30(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint=None)
    return matches[0]


def x_resolve_one__mutmut_31(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_32(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            )
    return matches[0]


def x_resolve_one__mutmut_33(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" / (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_34(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "XX%r exists in multiple taps: %sXX" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_35(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%R EXISTS IN MULTIPLE TAPS: %S" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_36(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(None)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_37(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, "XX, XX".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_38(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["XXtapXX"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_39(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["TAP"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_40(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" / (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_41(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="XXqualify it, e.g. `%s:%s`XX" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_42(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="QUALIFY IT, E.G. `%S:%S`" % (matches[0]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_43(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[1]["tap"], name))
    return matches[0]


def x_resolve_one__mutmut_44(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["XXtapXX"], name))
    return matches[0]


def x_resolve_one__mutmut_45(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["TAP"], name))
    return matches[0]


def x_resolve_one__mutmut_46(name: str) -> dict:
    """Find exactly one entry or raise with a helpful hint."""
    matches = find(name)
    if not matches:
        scored = search(name)[:3]
        hint = None
        if scored:
            hint = "closest matches: " + ", ".join(e["name"] for e, _ in scored)
        elif not registry.list_taps():
            hint = "no taps configured — start with `boost tap --defaults`"
        raise BoostError("no skill named %r in any tap" % name, hint=hint)
    if len(matches) > 1:
        raise BoostError(
            "%r exists in multiple taps: %s" % (name, ", ".join(e["tap"] for e in matches)),
            hint="qualify it, e.g. `%s:%s`" % (matches[0]["tap"], name))
    return matches[1]

mutants_x_resolve_one__mutmut['_mutmut_orig'] = x_resolve_one__mutmut_orig # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_1'] = x_resolve_one__mutmut_1 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_2'] = x_resolve_one__mutmut_2 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_3'] = x_resolve_one__mutmut_3 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_4'] = x_resolve_one__mutmut_4 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_5'] = x_resolve_one__mutmut_5 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_6'] = x_resolve_one__mutmut_6 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_7'] = x_resolve_one__mutmut_7 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_8'] = x_resolve_one__mutmut_8 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_9'] = x_resolve_one__mutmut_9 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_10'] = x_resolve_one__mutmut_10 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_11'] = x_resolve_one__mutmut_11 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_12'] = x_resolve_one__mutmut_12 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_13'] = x_resolve_one__mutmut_13 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_14'] = x_resolve_one__mutmut_14 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_15'] = x_resolve_one__mutmut_15 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_16'] = x_resolve_one__mutmut_16 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_17'] = x_resolve_one__mutmut_17 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_18'] = x_resolve_one__mutmut_18 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_19'] = x_resolve_one__mutmut_19 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_20'] = x_resolve_one__mutmut_20 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_21'] = x_resolve_one__mutmut_21 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_22'] = x_resolve_one__mutmut_22 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_23'] = x_resolve_one__mutmut_23 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_24'] = x_resolve_one__mutmut_24 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_25'] = x_resolve_one__mutmut_25 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_26'] = x_resolve_one__mutmut_26 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_27'] = x_resolve_one__mutmut_27 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_28'] = x_resolve_one__mutmut_28 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_29'] = x_resolve_one__mutmut_29 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_30'] = x_resolve_one__mutmut_30 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_31'] = x_resolve_one__mutmut_31 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_32'] = x_resolve_one__mutmut_32 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_33'] = x_resolve_one__mutmut_33 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_34'] = x_resolve_one__mutmut_34 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_35'] = x_resolve_one__mutmut_35 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_36'] = x_resolve_one__mutmut_36 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_37'] = x_resolve_one__mutmut_37 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_38'] = x_resolve_one__mutmut_38 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_39'] = x_resolve_one__mutmut_39 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_40'] = x_resolve_one__mutmut_40 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_41'] = x_resolve_one__mutmut_41 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_42'] = x_resolve_one__mutmut_42 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_43'] = x_resolve_one__mutmut_43 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_44'] = x_resolve_one__mutmut_44 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_45'] = x_resolve_one__mutmut_45 # type: ignore # mutmut generated
mutants_x_resolve_one__mutmut['x_resolve_one__mutmut_46'] = x_resolve_one__mutmut_46 # type: ignore # mutmut generated
mutants_x_search__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_search__mutmut)
def search(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_orig(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_1(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = None
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_2(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is not None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_3(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = None
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_4(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.upper().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_5(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = None
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_6(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(None, q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_7(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", None) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_8(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_9(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", ) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_10(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.rsplit(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_11(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"XX[\s,/_-]+XX", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_12(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = None
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_13(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = None
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_14(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].upper()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_15(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["XXnameXX"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_16(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["NAME"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_17(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = None
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_18(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").upper()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_19(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] and "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_20(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["XXdescriptionXX"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_21(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["DESCRIPTION"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_22(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "XXXX").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_23(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = None
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_24(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join(None)
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_25(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = "XX XX".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_26(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).upper()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_27(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(None).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_28(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get(None, {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_29(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", None)).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_30(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get({})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_31(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", )).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_32(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("XXmetaXX", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_33(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("META", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_34(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = None
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_35(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 1
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_36(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q != name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_37(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score = 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_38(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score -= 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_39(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 101
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_40(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(None):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_41(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score = 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_42(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score -= 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_43(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 81
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_44(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q not in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_45(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score = 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_46(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score -= 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_47(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 61
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_48(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q or q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_49(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q not in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_50(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score = 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_51(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score -= 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_52(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 31
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_53(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score = sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_54(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score -= sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_55(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(None)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_56(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(13 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_57(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t not in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_58(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score = sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_59(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score -= sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_60(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(None)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_61(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(7 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_62(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t not in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_63(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score = sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_64(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score -= sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_65(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(None)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_66(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(3 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_67(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t not in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_68(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score >= 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_69(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 1:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_70(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get(None):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_71(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("XXcuratedXX"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_72(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("CURATED"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_73(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score = 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_74(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score -= 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_75(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 4  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_76(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append(None)
    scored.sort(key=lambda x: (-x[1], x[0]["name"]))
    return scored


def x_search__mutmut_77(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=None)
    return scored


def x_search__mutmut_78(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: None)
    return scored


def x_search__mutmut_79(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (+x[1], x[0]["name"]))
    return scored


def x_search__mutmut_80(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[2], x[0]["name"]))
    return scored


def x_search__mutmut_81(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[1]["name"]))
    return scored


def x_search__mutmut_82(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["XXnameXX"]))
    return scored


def x_search__mutmut_83(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        blob = " ".join([name, desc, json.dumps(e.get("meta", {})).lower()])
        score = 0
        if q == name:
            score += 100
        elif name.startswith(q):
            score += 80
        elif q in name:
            score += 60
        if q and q in desc:
            score += 30
        score += sum(12 for t in tokens if t in name)
        score += sum(6 for t in tokens if t in desc)
        score += sum(2 for t in tokens if t in blob)
        if score > 0:
            if e.get("curated"):
                score += 3  # tiebreak only — never lifts a non-match into results
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["NAME"]))
    return scored

mutants_x_search__mutmut['_mutmut_orig'] = x_search__mutmut_orig # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_1'] = x_search__mutmut_1 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_2'] = x_search__mutmut_2 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_3'] = x_search__mutmut_3 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_4'] = x_search__mutmut_4 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_5'] = x_search__mutmut_5 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_6'] = x_search__mutmut_6 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_7'] = x_search__mutmut_7 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_8'] = x_search__mutmut_8 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_9'] = x_search__mutmut_9 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_10'] = x_search__mutmut_10 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_11'] = x_search__mutmut_11 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_12'] = x_search__mutmut_12 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_13'] = x_search__mutmut_13 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_14'] = x_search__mutmut_14 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_15'] = x_search__mutmut_15 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_16'] = x_search__mutmut_16 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_17'] = x_search__mutmut_17 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_18'] = x_search__mutmut_18 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_19'] = x_search__mutmut_19 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_20'] = x_search__mutmut_20 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_21'] = x_search__mutmut_21 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_22'] = x_search__mutmut_22 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_23'] = x_search__mutmut_23 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_24'] = x_search__mutmut_24 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_25'] = x_search__mutmut_25 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_26'] = x_search__mutmut_26 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_27'] = x_search__mutmut_27 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_28'] = x_search__mutmut_28 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_29'] = x_search__mutmut_29 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_30'] = x_search__mutmut_30 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_31'] = x_search__mutmut_31 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_32'] = x_search__mutmut_32 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_33'] = x_search__mutmut_33 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_34'] = x_search__mutmut_34 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_35'] = x_search__mutmut_35 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_36'] = x_search__mutmut_36 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_37'] = x_search__mutmut_37 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_38'] = x_search__mutmut_38 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_39'] = x_search__mutmut_39 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_40'] = x_search__mutmut_40 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_41'] = x_search__mutmut_41 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_42'] = x_search__mutmut_42 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_43'] = x_search__mutmut_43 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_44'] = x_search__mutmut_44 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_45'] = x_search__mutmut_45 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_46'] = x_search__mutmut_46 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_47'] = x_search__mutmut_47 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_48'] = x_search__mutmut_48 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_49'] = x_search__mutmut_49 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_50'] = x_search__mutmut_50 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_51'] = x_search__mutmut_51 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_52'] = x_search__mutmut_52 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_53'] = x_search__mutmut_53 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_54'] = x_search__mutmut_54 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_55'] = x_search__mutmut_55 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_56'] = x_search__mutmut_56 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_57'] = x_search__mutmut_57 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_58'] = x_search__mutmut_58 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_59'] = x_search__mutmut_59 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_60'] = x_search__mutmut_60 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_61'] = x_search__mutmut_61 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_62'] = x_search__mutmut_62 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_63'] = x_search__mutmut_63 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_64'] = x_search__mutmut_64 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_65'] = x_search__mutmut_65 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_66'] = x_search__mutmut_66 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_67'] = x_search__mutmut_67 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_68'] = x_search__mutmut_68 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_69'] = x_search__mutmut_69 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_70'] = x_search__mutmut_70 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_71'] = x_search__mutmut_71 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_72'] = x_search__mutmut_72 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_73'] = x_search__mutmut_73 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_74'] = x_search__mutmut_74 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_75'] = x_search__mutmut_75 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_76'] = x_search__mutmut_76 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_77'] = x_search__mutmut_77 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_78'] = x_search__mutmut_78 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_79'] = x_search__mutmut_79 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_80'] = x_search__mutmut_80 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_81'] = x_search__mutmut_81 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_82'] = x_search__mutmut_82 # type: ignore # mutmut generated
mutants_x_search__mutmut['x_search__mutmut_83'] = x_search__mutmut_83 # type: ignore # mutmut generated
