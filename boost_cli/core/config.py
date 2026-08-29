# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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
        # Gemini CLI discovers boost's canonical store directly: its user tier
        # reads `~/.gemini/skills` **or the `~/.agents/skills` alias**, and that
        # alias is exactly paths.store_dir(). So skills need no symlink —
        # `links_skills: false` — and linking anyway would put the same skill in
        # two of Gemini's discovery tiers, where the alias out-ranks the dir we
        # linked into: the link could never win, it would only cost the user a
        # "Skill conflict detected" line per skill at every session start.
        #
        # The dir is still configured because it anchors everything that is NOT
        # a store symlink: `~/.gemini` is where rules (GEMINI.md) and workflows
        # (commands/, agents/) materialize. Set links_skills true to restore the
        # symlink if that alias is ever narrowed.
        "gemini": {"dir": "~/.gemini/skills", "enabled": True,
                   "links_skills": False},
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
        # "text" (default) or "json". json emits one JSON object per line —
        # the same fields, but readable by jq or a log collector without a
        # regex. Overridden by BOOST_LOG_FORMAT.
        "format": "text",
    },
}

# Recommended public registries, added via `boost tap --defaults` and by the
# seed that runs on `boost mcp` (core/bootstrap.py) so one command is the
# whole setup.
#
# The list covers all THREE item kinds on purpose. The five skills-first repos
# measured 302 skills and 41 workflows between them and — the gap this closes
# — zero rules, so the kind whose entire job is steering toward a better path
# and away from an anti-pattern could not be found by a default install at
# all. Adding one canonical rules repo and one commands/agents repo takes the
# default corpus to 946 items (302 skills, 387 workflows, 257 rules) for about
# 14 MB more on disk than the five, measured end-to-end at 14-45s across runs
# (network-bound, hence the range).
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
    {"name": "PatrickJS/awesome-cursorrules",
     "url": "https://github.com/PatrickJS/awesome-cursorrules",
     "curated": True,
     "focus": "Rules — the canonical .cursorrules/.mdc collection: per-stack "
              "conventions and anti-patterns to avoid"},
    {"name": "qdhenry/Claude-Command-Suite",
     "url": "https://github.com/qdhenry/Claude-Command-Suite",
     "curated": True,
     "focus": "Workflows — slash commands and subagents for review, testing, "
              "refactoring and release"},
]


# Path to the bundled curated registry catalog (skills + rules + workflows).
REGISTRY_CATALOG = paths.package_root() / "data" / "registries.json"


def load_registry_catalog() -> list:
    """The bundled curated registries, or [] if the data file is missing."""
    try:
        data = json.loads(REGISTRY_CATALOG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data.get("registries", [])


def _merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    # `or {}`: the only caller feeds this json.loads() of config.json, so a file
    # holding `null` (or `[]`, or any falsy scalar) arrives here as a non-dict —
    # a malformed config must read as "no overrides", never crash the CLI.
    for k, v in (override or {}).items():  # noqa: FURB143
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


# In-process cache of the merged config. get() is on many hot paths
# (ai.enabled, per-skill enabled_agents, log level, policy) and every call
# used to re-read config.json and re-merge/deep-copy DEFAULTS. We cache the
# merged result keyed on the config path + its stat stamp, so any write —
# save(), an external edit, or a HOME/BOOST_HOME switch between tests — is
# picked up automatically without an explicit invalidation call.
_cache: dict | None = None
_cache_key: tuple | None = None


def _stat_stamp(p: Any) -> tuple:
    """Identity of the config file: (path, mtime_ns, size).

    A missing file stamps as (path, None, None); any create/modify/delete
    changes the stamp, which is what invalidates the cache.
    """
    try:
        st = p.stat()
    except OSError:
        return (str(p), None, None)
    return (str(p), st.st_mtime_ns, st.st_size)


def _read() -> dict:
    p = paths.config_path()
    if not p.exists():
        return deepcopy(DEFAULTS)
    try:
        user = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULTS)
    return _merge(DEFAULTS, user)


def _cached() -> dict:
    """The merged config, re-read from disk only when the file changes."""
    global _cache, _cache_key
    key = _stat_stamp(paths.config_path())
    cache = _cache
    if cache is None or _cache_key != key:
        cache = _read()
        _cache = cache
        _cache_key = key
    return cache


def load() -> dict:
    """Return a deep copy of the merged config, safe for callers to mutate."""
    # A defensive copy so callers can mutate the result (set_value/unset do)
    # without corrupting the shared cache.
    return deepcopy(_cached())


def save(cfg: dict) -> None:
    """Atomically write `cfg` to `~/.boost/config.json`, creating dirs first."""
    paths.ensure_dirs()
    util.atomic_write_text(
        paths.config_path(), json.dumps(cfg, indent=2, sort_keys=False) + "\n")


def get(dotted: str, default=None):
    """Look up a dotted key (`ai.model`) in the merged config.

    
    Returns a deep copy of the value, or `default` if any part is missing.
    """
    node = _cached()
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return deepcopy(node)


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
    """Delete a dotted key and save; True if removed, False (no write) if absent."""
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
