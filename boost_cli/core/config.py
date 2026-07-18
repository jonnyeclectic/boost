"""Configuration: ~/.boost/config.json with deep-merged defaults."""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from . import paths, util

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
    "logging": {
        # Console verbosity for the diagnostic log on stderr. "OFF" keeps
        # stderr clean (the default); set DEBUG/INFO/WARNING/ERROR to always
        # surface the trail. The rotating file always records at DEBUG.
        # Overridden by --verbose/--debug/--quiet and BOOST_LOG_LEVEL.
        # See core/logs.py and docs/DEBUGGING.md.
        "level": "OFF",
        "file": True,  # set false (or BOOST_NO_LOG=1) to disable the log file
    },
}

# Recommended public registries, added via `boost tap --defaults`.
DEFAULT_TAPS = [
    {"name": "anthropics/skills", "url": "https://github.com/anthropics/skills",
     "curated": True,
     "focus": "Official Anthropic skills — docs, artifacts, MCP, agent workflows"},
    {"name": "obra/superpowers", "url": "https://github.com/obra/superpowers",
     "curated": True,
     "focus": "Community powerhouse — TDD, debugging, planning, subagents"},
    {"name": "trailofbits/skills", "url": "https://github.com/trailofbits/skills",
     "curated": True,
     "focus": "Security auditing from Trail of Bits — CodeQL, Semgrep, vuln hunting"},
    {"name": "expo/skills", "url": "https://github.com/expo/skills",
     "curated": True,
     "focus": "Official Expo team skills — EAS builds, app stores, deployments"},
    {"name": "K-Dense-AI/scientific-agent-skills",
     "url": "https://github.com/K-Dense-AI/scientific-agent-skills",
     "curated": True,
     "focus": "Scientific computing — research libraries, databases, analysis"},
]


# Path to the bundled curated registry catalog (skills + rules + workflows).
REGISTRY_CATALOG = paths.package_root() / "data" / "registries.json"


def load_registry_catalog() -> list:
    """The bundled curated registries, or [] if the data file is missing."""
    try:
        data = json.loads(REGISTRY_CATALOG.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    return data.get("registries", [])


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
    util.atomic_write_text(
        paths.config_path(), json.dumps(cfg, indent=2, sort_keys=False) + "\n")


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
    node: Any = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def unset(dotted: str) -> bool:
    cfg = load()
    node: Any = cfg
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
