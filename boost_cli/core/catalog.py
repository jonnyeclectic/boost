"""Skill catalogs: scan tap repos for skill/rule/workflow files -> JSON caches.

A catalog entry (plain dict) has:
  name, description, version, tap, curated,
  kind      -- "skill" | "rule" | "workflow" (defaults to "skill")
  rel_dir   -- item directory relative to the tap repo root
  skill_md  -- path of the defining file relative to the repo root
               (SKILL.md for skills, the .mdc/.cursorrules/.md for others)
  meta      -- full parsed frontmatter

Beyond `SKILL.md` skills, boost also indexes two lighter-weight item kinds
that ship in the same GitHub registries:
  * rules     -- Cursor `.mdc` / `.cursorrules` and Windsurf `.windsurfrules`
  * workflows -- Claude Code slash commands / subagents (Markdown + YAML),
                 recognised by living under a commands/agents/workflows dir
                 or by carrying a subagent-style frontmatter signature.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional, Tuple

from ..errors import BoostError
from . import frontmatter, gitutil, paths, registry, util

KIND_SKILL = "skill"
KIND_RULE = "rule"
KIND_WORKFLOW = "workflow"

# Rule files: Cursor MDC + the legacy single-file rule dotfiles.
RULE_SUFFIXES = {".mdc"}
RULE_FILENAMES = {".cursorrules", ".windsurfrules", ".clinerules"}
# Directory names that mark a Markdown file as a command/agent workflow.
WORKFLOW_DIRS = {"commands", "agents", "subagents", "workflows"}
# Frontmatter keys that betray a Claude Code subagent / slash command even
# when the file sits at a repo root rather than under a workflow dir.
WORKFLOW_META_KEYS = {"tools", "model", "argument-hint", "allowed-tools"}
# Markdown filenames that are documentation, never workflow items.
DOC_STEMS = {"readme", "contributing", "license", "changelog", "security",
             "code_of_conduct", "index", "_index", "authors", "notice"}


def _ignored(path: Path) -> bool:
    return any(part in util.IGNORED for part in path.parts)


def _read(path: Path) -> Optional[Tuple[dict, str]]:
    try:
        return frontmatter.parse(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None


def _description(meta: dict, body: str) -> str:
    desc = str(meta.get("description") or "").strip()
    if desc:
        return desc
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:160]
    return ""


def _make_entry(root: Path, defining_file: Path, kind: str, default_name: str,
                tap_name: str, curated: bool, meta: dict, body: str) -> dict:
    name = str(meta.get("name") or "").strip() or default_name
    slug = util.slugify(name) if " " in name else name
    description = _description(meta, body)
    item_dir = defining_file.parent
    return {
        "name": slug,
        "description": description,
        "version": str(meta.get("version") or "0.0.0"),
        "tap": tap_name,
        "curated": curated,
        "kind": kind,
        "rel_dir": str(item_dir.relative_to(root)) if item_dir != root else ".",
        "skill_md": str(defining_file.relative_to(root)),
        "meta": meta,
        # Lowercased substring-search blob, flattened once at index time so
        # search() never re-walks the frontmatter per query (see _search_blob).
        "search_blob": _search_blob(slug, description, meta),
    }


def _classify_rule(path: Path) -> bool:
    return path.name in RULE_FILENAMES or path.suffix.lower() in RULE_SUFFIXES


def _classify_workflow(path: Path, meta: dict) -> bool:
    """A Markdown file is a workflow if it lives under a commands/agents/
    workflows directory, or carries subagent/slash-command frontmatter."""
    if path.suffix.lower() != ".md" or path.name == "SKILL.md":
        return False
    if path.stem.lower() in DOC_STEMS:
        return False
    parent_parts = {p.lower() for p in path.parent.parts}
    if parent_parts & WORKFLOW_DIRS:
        return True
    return bool(meta.get("name") and meta.get("description")
                and (WORKFLOW_META_KEYS & set(meta)))


def scan_dir(root: Path, tap_name: str = "local", curated: bool = False) -> List[dict]:
    root = Path(root)
    entries: List[dict] = []
    skill_dirs: List[Path] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if _ignored(skill_md):
            continue
        parsed = _read(skill_md)
        if parsed is None:
            continue
        meta, body = parsed
        skill_dir = skill_md.parent
        default = skill_dir.name if skill_dir != root else root.name
        entries.append(_make_entry(root, skill_md, KIND_SKILL, default,
                                   tap_name, curated, meta, body))
        skill_dirs.append(skill_dir)

    for path in sorted(root.rglob("*")):
        if not path.is_file() or _ignored(path):
            continue
        # never re-index a file that belongs to a scanned skill directory
        if any(path == d or d in path.parents for d in skill_dirs):
            continue
        is_rule = _classify_rule(path)
        is_md = path.suffix.lower() == ".md" and path.name != "SKILL.md"
        if not is_rule and not is_md:
            continue
        parsed = _read(path)
        if parsed is None:
            continue
        meta, body = parsed
        if is_rule:
            kind = KIND_RULE
        elif _classify_workflow(path, meta):
            kind = KIND_WORKFLOW
        else:
            continue
        if path.name in RULE_FILENAMES:
            default = path.parent.name if path.parent != root else root.name
        else:
            default = path.stem
        entries.append(_make_entry(root, path, kind, default,
                                   tap_name, curated, meta, body))

    entries.sort(key=lambda e: (e["skill_md"], e["name"]))
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


def _meta_text(meta) -> str:
    """Lowercased, space-joined flatten of a frontmatter dict for substring
    search. Cheaper than ``json.dumps(meta).lower()`` — which built and threw
    away a JSON string on every entry of every query just to substring-match —
    while matching the same words (tags, keys, scalar values)."""
    parts: List[str] = []

    def walk(v) -> None:
        if isinstance(v, dict):
            for k, val in v.items():
                parts.append(str(k))
                walk(val)
        elif isinstance(v, (list, tuple)):
            for val in v:
                walk(val)
        elif v is not None:
            parts.append(str(v))

    walk(meta or {})
    return " ".join(parts).lower()


def _search_blob(name: str, description: str, meta) -> str:
    """The full lowercased substring-search text for an entry: its name,
    description and flattened frontmatter. Built once at index time and cached
    on the entry as ``search_blob`` so search() never rebuilds it per query."""
    return " ".join([name.lower(), (description or "").lower(), _meta_text(meta)])


def search(query: str, entries: Optional[List[dict]] = None):
    """Rank entries against a query -> [(entry, score)] best-first."""
    entries = all_entries() if entries is None else entries
    q = query.lower().strip()
    tokens = [t for t in re.split(r"[\s,/_-]+", q) if t]
    scored = []
    for e in entries:
        name = e["name"].lower()
        desc = (e["description"] or "").lower()
        # Precomputed at index time; fall back for older caches / entries
        # constructed without a blob (e.g. tests passing raw dicts).
        blob = e.get("search_blob")
        if blob is None:
            blob = _search_blob(e["name"], e.get("description", ""),
                                e.get("meta", {}))
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
