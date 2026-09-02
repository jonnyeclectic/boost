# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Configuration: ~/.boost/config.json with deep-merged defaults."""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from . import paths, typedvalue, util

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
        # Antigravity CLI (`agy`) is Gemini CLI's successor and shares its
        # `~/.gemini` tree, but it does **not** implement the Agent Skills
        # standard: it reads neither `~/.agents/skills` nor, for CLI scope,
        # anything outside `~/.gemini/antigravity-cli/`. So unlike gemini it
        # needs real symlinks — `links_skills` defaults true and stays true.
        #
        # Why the CLI-scoped dir and not the shared `~/.gemini/skills`: that
        # shared dir is one of *Gemini CLI's* user-tier discovery paths, and
        # Gemini already reads the same skills through the `~/.agents/skills`
        # alias. Linking there would put one skill in two of Gemini's tiers and
        # cost a "Skill conflict detected" line per skill per session — the
        # exact failure `links_skills: false` exists to avoid. Linking into
        # `antigravity-cli/skills` is invisible to Gemini and is the tier the
        # CLI itself reads.
        # `project_scope: false` — its skills dir is two levels under the
        # dotdir, so the repo-local derivation would make a dotless
        # `<repo>/antigravity-cli/` nothing reads. See agents.project_agents.
        # `skills_only`: its rule and workflow formats are unverified, and a
        # rule reaches it anyway through the `gemini` entry above, which writes
        # the ~/.gemini/GEMINI.md Antigravity reads.
        "antigravity": {"dir": "~/.gemini/antigravity-cli/skills",
                        "enabled": True, "project_scope": False,
                        "skills_only": True},
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


def registry_categories() -> dict:
    """tap name ('owner/repo') -> curated category, from the bundled registry
    catalog (`data/registries.json`) — the only place a *tap-level* category
    lives. A catalog entry's own stamped category (`catalog._entry_category`)
    falls back to this when the item declares none of its own."""
    return {e["name"]: e["category"] for e in load_registry_catalog()
            if e.get("category")}


def self_installing_command(tap: str) -> str | None:
    """The repo's own install command, when boost must not copy its items.

    Some registries are real catalogues of Markdown and some are programs that
    happen to ship Markdown entry points. For the second kind boost's install —
    copy the item's directory into the canonical store, symlink it out — yields
    a skill that *looks* installed and cannot run, because the step that makes
    it work is the repo's own build, not a fetch. Returns the upstream command
    so the caller can name it instead of pretending; None for every other tap.

    The tap may be addressed by full ``owner/repo`` or by the bare repo name a
    clone directory carries, so both resolve.
    """
    if not tap:
        return None
    for row in load_registry_catalog():
        cmd = row.get("self_installing")
        if not cmd:
            continue
        name = row.get("name") or ""
        if tap in (name, name.split("/")[-1]):
            return cmd
    return None


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


def _read_raw() -> dict:
    """The on-disk overrides only, with no DEFAULTS merged in.

    A missing or corrupt file reads as no overrides — the same "absent" the
    merged view falls back to, so a caller walking this dict never has to
    special-case the file not existing.
    """
    p = paths.config_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


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


def spec_for(dotted: str) -> str:
    """The value type of a dotted key, derived from :data:`DEFAULTS`.

    A key DEFAULTS does not describe types as :data:`typedvalue.ANY`: `boost
    config set` accepts keys boost has never heard of (integrations write their
    own), and inventing a type for those would refuse values that work today.
    """
    node: Any = DEFAULTS
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return typedvalue.ANY
        node = node[part]
    return typedvalue.spec_for(node)


def get_int(dotted: str, default: int) -> int:
    """Read a config key as an int, or raise :class:`typedvalue.ValueTypeError`.

    The consumers of a numeric setting used to call `int()` on whatever was
    stored, so a hand-edited `serve.port: "abc"` crashed `boost serve --help`
    with a traceback and exit 70 — before argparse had even run. Callers catch
    this and frame it instead.
    """
    value = get(dotted, default)
    if value is None:
        return default
    return typedvalue.adapt(dotted, value, typedvalue.INT)


def set_value(dotted: str, raw: str) -> None:
    """Set a dotted key, reading the value at the type :data:`DEFAULTS` declares.

    Raises :class:`typedvalue.ValueTypeError` when the text cannot be read at
    that type. Keys with no default keep the old lenient behaviour: JSON when
    it parses, the string otherwise.
    """
    value = typedvalue.coerce(dotted, raw, spec_for(dotted))
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
    """Delete a dotted key and save; True if removed, False (no write) if absent.

    Walks the raw on-disk overrides, not the DEFAULTS-merged view `load()`
    returns. A key that is only present via DEFAULTS has nothing on disk to
    remove — walking the merged view instead made every defaulted key
    `in node` forever, so a repeat `unset` (or a first one on a pristine
    machine with no config.json at all) reported success and wrote the whole
    of DEFAULTS to disk, freezing them against future default changes.
    """
    cfg = _read_raw()
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
