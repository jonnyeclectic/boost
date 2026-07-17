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


def load_tap(tap: "registry.Tap", rebuild: bool = False) -> List[dict]:
    if not rebuild and tap.cache_file.exists():
        try:
            return json.loads(tap.cache_file.read_text()).get("skills", [])
        except (json.JSONDecodeError, OSError):
            pass
    if tap.is_cloned:
        return rebuild_tap(tap)
    return []


def all_entries() -> List[dict]:
    out: List[dict] = []
    for tap in registry.list_taps():
        out.extend(load_tap(tap))
    return out


def find(name: str, tap: Optional[str] = None) -> List[dict]:
    """Exact-name lookup. Supports 'owner/repo:skill' qualified form."""
    if ":" in name:
        tap, name = name.rsplit(":", 1)
    matches = [e for e in all_entries() if e["name"] == name]
    if tap:
        matches = [e for e in matches if e["tap"] == tap or
                   e["tap"].split("/")[-1] == tap]
    return matches


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
