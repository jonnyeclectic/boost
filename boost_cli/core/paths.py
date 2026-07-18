"""All filesystem locations boost touches.

Everything derives from $HOME (or explicit env overrides) at call time so
tests can sandbox the whole tool by exporting HOME=/tmp/somewhere.

Layout:
  ~/.boost/repos/           shallow git clones of tap registries
  ~/.boost/cache/           JSON catalogs built from SKILL.md frontmatter
  ~/.boost/logs/            command logs
  ~/.boost/state/           pins, tags, policy, profiles, pulse feed, snapshots
  ~/.boost/config.json      configuration
  ~/.agents/skills/        canonical store — single source of truth
  ~/.agents/skills/.skill-lock.json   v3 lock file
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("HOME") or str(Path.home()))


def expand(p: str) -> Path:
    """Expand a leading ~ against home() (which respects the HOME env var)."""
    if p == "~":
        return home()
    if p.startswith("~/"):
        return home() / p[2:]
    return Path(p)


def boost_home() -> Path:
    override = os.environ.get("BOOST_HOME")
    return Path(override) if override else home() / ".boost"


def repos_dir() -> Path:
    return boost_home() / "repos"


def cache_dir() -> Path:
    return boost_home() / "cache"


def logs_dir() -> Path:
    return boost_home() / "logs"


def state_dir() -> Path:
    return boost_home() / "state"


def snapshots_dir() -> Path:
    return state_dir() / "snapshots"


def lock_history_dir() -> Path:
    return state_dir() / "lock-history"


def profiles_dir() -> Path:
    return state_dir() / "profiles"


def config_path() -> Path:
    return boost_home() / "config.json"


def store_dir() -> Path:
    """Canonical store for installed skills."""
    override = os.environ.get("BOOST_AGENTS_STORE")
    return Path(override) if override else home() / ".agents" / "skills"


def lockfile_path() -> Path:
    return store_dir() / ".skill-lock.json"


def pulse_path() -> Path:
    return state_dir() / "pulse.jsonl"


def policy_path() -> Path:
    return state_dir() / "policy.json"


def repo_root() -> Path:
    """The boost source checkout this module runs from."""
    return Path(__file__).resolve().parent.parent.parent


def launcher() -> Path:
    """Absolute path other processes should use to invoke boost.

    A pip/pipx install has no `boost` shim next to the package (repo_root()
    lands inside site-packages), so prefer the console script on PATH and
    fall back to the source-checkout shim.
    """
    found = shutil.which("boost")
    return Path(found) if found else repo_root() / "boost"


def ensure_dirs() -> None:
    for d in (
        boost_home(), repos_dir(), cache_dir(), logs_dir(), state_dir(),
        snapshots_dir(), lock_history_dir(), profiles_dir(), store_dir(),
    ):
        d.mkdir(parents=True, exist_ok=True)
