"""Configuration: ~/.boost/config.json with deep-merged defaults."""
from __future__ import annotations

import json
from copy import deepcopy

from . import paths

DEFAULTS = {
    "agents": {
        "claude-code": {"dir": "~/.claude/skills", "enabled": True},
        "windsurf": {"dir": "~/.windsurf/skills", "enabled": True},
        "cursor": {"dir": "~/.cursor/skills", "enabled": True},
    },
    "taps": [],  # [{"name": "owner/repo", "url": "...", "curated": bool}]
    "ai": {
        "enabled": True,
        "model": "claude-haiku-4-5-20251001",        # ranking / quick summaries
        "author_model": "claude-sonnet-5",           # authoring (infer/distill/evolve)
    },
    "serve": {"port": 8787},
    "policy_enforce": True,
    "telemetry": False,
}

# Recommended public registries, added via `boost tap --defaults`.
DEFAULT_TAPS = [
    {"name": "anthropics/skills", "url": "https://github.com/anthropics/skills",
     "curated": True,
     "focus": "Official Anthropic skills — docs, artifacts, MCP, agent workflows"},
    {"name": "obra/superpowers", "url": "https://github.com/obra/superpowers",
     "curated": True,
     "focus": "Community powerhouse — TDD, debugging, planning, subagents"},
]


def _merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load() -> dict:
    p = paths.config_path()
    if not p.exists():
        return deepcopy(DEFAULTS)
    try:
        user = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULTS)
    return _merge(DEFAULTS, user)


def save(cfg: dict) -> None:
    paths.ensure_dirs()
    paths.config_path().write_text(json.dumps(cfg, indent=2, sort_keys=False) + "\n")


def get(dotted: str, default=None):
    node = load()
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def set_value(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def unset(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False
