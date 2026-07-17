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
from pathlib import Path


from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated, MutantDict
mutants_x_home__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_home__mutmut)
def home() -> Path:
    return Path(os.environ.get("HOME") or str(Path.home()))


def x_home__mutmut_orig() -> Path:
    return Path(os.environ.get("HOME") or str(Path.home()))


def x_home__mutmut_1() -> Path:
    return Path(None)


def x_home__mutmut_2() -> Path:
    return Path(os.environ.get("HOME") and str(Path.home()))


def x_home__mutmut_3() -> Path:
    return Path(os.environ.get(None) or str(Path.home()))


def x_home__mutmut_4() -> Path:
    return Path(os.environ.get("XXHOMEXX") or str(Path.home()))


def x_home__mutmut_5() -> Path:
    return Path(os.environ.get("home") or str(Path.home()))


def x_home__mutmut_6() -> Path:
    return Path(os.environ.get("HOME") or str(None))

mutants_x_home__mutmut['_mutmut_orig'] = x_home__mutmut_orig # type: ignore # mutmut generated
mutants_x_home__mutmut['x_home__mutmut_1'] = x_home__mutmut_1 # type: ignore # mutmut generated
mutants_x_home__mutmut['x_home__mutmut_2'] = x_home__mutmut_2 # type: ignore # mutmut generated
mutants_x_home__mutmut['x_home__mutmut_3'] = x_home__mutmut_3 # type: ignore # mutmut generated
mutants_x_home__mutmut['x_home__mutmut_4'] = x_home__mutmut_4 # type: ignore # mutmut generated
mutants_x_home__mutmut['x_home__mutmut_5'] = x_home__mutmut_5 # type: ignore # mutmut generated
mutants_x_home__mutmut['x_home__mutmut_6'] = x_home__mutmut_6 # type: ignore # mutmut generated
mutants_x_expand__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_expand__mutmut)
def expand(p: str) -> Path:
    """Expand a leading ~ against home() (which respects the HOME env var)."""
    if p == "~":
        return home()
    if p.startswith("~/"):
        return home() / p[2:]
    return Path(p)


def x_expand__mutmut_orig(p: str) -> Path:
    """Expand a leading ~ against home() (which respects the HOME env var)."""
    if p == "~":
        return home()
    if p.startswith("~/"):
        return home() / p[2:]
    return Path(p)


def x_expand__mutmut_1(p: str) -> Path:
    """Expand a leading ~ against home() (which respects the HOME env var)."""
    if p != "~":
        return home()
    if p.startswith("~/"):
        return home() / p[2:]
    return Path(p)


def x_expand__mutmut_2(p: str) -> Path:
    """Expand a leading ~ against home() (which respects the HOME env var)."""
    if p == "XX~XX":
        return home()
    if p.startswith("~/"):
        return home() / p[2:]
    return Path(p)


def x_expand__mutmut_3(p: str) -> Path:
    """Expand a leading ~ against home() (which respects the HOME env var)."""
    if p == "~":
        return home()
    if p.startswith(None):
        return home() / p[2:]
    return Path(p)


def x_expand__mutmut_4(p: str) -> Path:
    """Expand a leading ~ against home() (which respects the HOME env var)."""
    if p == "~":
        return home()
    if p.startswith("XX~/XX"):
        return home() / p[2:]
    return Path(p)


def x_expand__mutmut_5(p: str) -> Path:
    """Expand a leading ~ against home() (which respects the HOME env var)."""
    if p == "~":
        return home()
    if p.startswith("~/"):
        return home() * p[2:]
    return Path(p)


def x_expand__mutmut_6(p: str) -> Path:
    """Expand a leading ~ against home() (which respects the HOME env var)."""
    if p == "~":
        return home()
    if p.startswith("~/"):
        return home() / p[3:]
    return Path(p)


def x_expand__mutmut_7(p: str) -> Path:
    """Expand a leading ~ against home() (which respects the HOME env var)."""
    if p == "~":
        return home()
    if p.startswith("~/"):
        return home() / p[2:]
    return Path(None)

mutants_x_expand__mutmut['_mutmut_orig'] = x_expand__mutmut_orig # type: ignore # mutmut generated
mutants_x_expand__mutmut['x_expand__mutmut_1'] = x_expand__mutmut_1 # type: ignore # mutmut generated
mutants_x_expand__mutmut['x_expand__mutmut_2'] = x_expand__mutmut_2 # type: ignore # mutmut generated
mutants_x_expand__mutmut['x_expand__mutmut_3'] = x_expand__mutmut_3 # type: ignore # mutmut generated
mutants_x_expand__mutmut['x_expand__mutmut_4'] = x_expand__mutmut_4 # type: ignore # mutmut generated
mutants_x_expand__mutmut['x_expand__mutmut_5'] = x_expand__mutmut_5 # type: ignore # mutmut generated
mutants_x_expand__mutmut['x_expand__mutmut_6'] = x_expand__mutmut_6 # type: ignore # mutmut generated
mutants_x_expand__mutmut['x_expand__mutmut_7'] = x_expand__mutmut_7 # type: ignore # mutmut generated
mutants_x_boost_home__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_boost_home__mutmut)
def boost_home() -> Path:
    override = os.environ.get("BOOST_HOME")
    return Path(override) if override else home() / ".boost"


def x_boost_home__mutmut_orig() -> Path:
    override = os.environ.get("BOOST_HOME")
    return Path(override) if override else home() / ".boost"


def x_boost_home__mutmut_1() -> Path:
    override = None
    return Path(override) if override else home() / ".boost"


def x_boost_home__mutmut_2() -> Path:
    override = os.environ.get(None)
    return Path(override) if override else home() / ".boost"


def x_boost_home__mutmut_3() -> Path:
    override = os.environ.get("XXBOOST_HOMEXX")
    return Path(override) if override else home() / ".boost"


def x_boost_home__mutmut_4() -> Path:
    override = os.environ.get("boost_home")
    return Path(override) if override else home() / ".boost"


def x_boost_home__mutmut_5() -> Path:
    override = os.environ.get("BOOST_HOME")
    return Path(None) if override else home() / ".boost"


def x_boost_home__mutmut_6() -> Path:
    override = os.environ.get("BOOST_HOME")
    return Path(override) if override else home() * ".boost"


def x_boost_home__mutmut_7() -> Path:
    override = os.environ.get("BOOST_HOME")
    return Path(override) if override else home() / "XX.boostXX"


def x_boost_home__mutmut_8() -> Path:
    override = os.environ.get("BOOST_HOME")
    return Path(override) if override else home() / ".BOOST"

mutants_x_boost_home__mutmut['_mutmut_orig'] = x_boost_home__mutmut_orig # type: ignore # mutmut generated
mutants_x_boost_home__mutmut['x_boost_home__mutmut_1'] = x_boost_home__mutmut_1 # type: ignore # mutmut generated
mutants_x_boost_home__mutmut['x_boost_home__mutmut_2'] = x_boost_home__mutmut_2 # type: ignore # mutmut generated
mutants_x_boost_home__mutmut['x_boost_home__mutmut_3'] = x_boost_home__mutmut_3 # type: ignore # mutmut generated
mutants_x_boost_home__mutmut['x_boost_home__mutmut_4'] = x_boost_home__mutmut_4 # type: ignore # mutmut generated
mutants_x_boost_home__mutmut['x_boost_home__mutmut_5'] = x_boost_home__mutmut_5 # type: ignore # mutmut generated
mutants_x_boost_home__mutmut['x_boost_home__mutmut_6'] = x_boost_home__mutmut_6 # type: ignore # mutmut generated
mutants_x_boost_home__mutmut['x_boost_home__mutmut_7'] = x_boost_home__mutmut_7 # type: ignore # mutmut generated
mutants_x_boost_home__mutmut['x_boost_home__mutmut_8'] = x_boost_home__mutmut_8 # type: ignore # mutmut generated
mutants_x_repos_dir__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_repos_dir__mutmut)
def repos_dir() -> Path:
    return boost_home() / "repos"


def x_repos_dir__mutmut_orig() -> Path:
    return boost_home() / "repos"


def x_repos_dir__mutmut_1() -> Path:
    return boost_home() * "repos"


def x_repos_dir__mutmut_2() -> Path:
    return boost_home() / "XXreposXX"


def x_repos_dir__mutmut_3() -> Path:
    return boost_home() / "REPOS"

mutants_x_repos_dir__mutmut['_mutmut_orig'] = x_repos_dir__mutmut_orig # type: ignore # mutmut generated
mutants_x_repos_dir__mutmut['x_repos_dir__mutmut_1'] = x_repos_dir__mutmut_1 # type: ignore # mutmut generated
mutants_x_repos_dir__mutmut['x_repos_dir__mutmut_2'] = x_repos_dir__mutmut_2 # type: ignore # mutmut generated
mutants_x_repos_dir__mutmut['x_repos_dir__mutmut_3'] = x_repos_dir__mutmut_3 # type: ignore # mutmut generated
mutants_x_cache_dir__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_cache_dir__mutmut)
def cache_dir() -> Path:
    return boost_home() / "cache"


def x_cache_dir__mutmut_orig() -> Path:
    return boost_home() / "cache"


def x_cache_dir__mutmut_1() -> Path:
    return boost_home() * "cache"


def x_cache_dir__mutmut_2() -> Path:
    return boost_home() / "XXcacheXX"


def x_cache_dir__mutmut_3() -> Path:
    return boost_home() / "CACHE"

mutants_x_cache_dir__mutmut['_mutmut_orig'] = x_cache_dir__mutmut_orig # type: ignore # mutmut generated
mutants_x_cache_dir__mutmut['x_cache_dir__mutmut_1'] = x_cache_dir__mutmut_1 # type: ignore # mutmut generated
mutants_x_cache_dir__mutmut['x_cache_dir__mutmut_2'] = x_cache_dir__mutmut_2 # type: ignore # mutmut generated
mutants_x_cache_dir__mutmut['x_cache_dir__mutmut_3'] = x_cache_dir__mutmut_3 # type: ignore # mutmut generated
mutants_x_logs_dir__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_logs_dir__mutmut)
def logs_dir() -> Path:
    return boost_home() / "logs"


def x_logs_dir__mutmut_orig() -> Path:
    return boost_home() / "logs"


def x_logs_dir__mutmut_1() -> Path:
    return boost_home() * "logs"


def x_logs_dir__mutmut_2() -> Path:
    return boost_home() / "XXlogsXX"


def x_logs_dir__mutmut_3() -> Path:
    return boost_home() / "LOGS"

mutants_x_logs_dir__mutmut['_mutmut_orig'] = x_logs_dir__mutmut_orig # type: ignore # mutmut generated
mutants_x_logs_dir__mutmut['x_logs_dir__mutmut_1'] = x_logs_dir__mutmut_1 # type: ignore # mutmut generated
mutants_x_logs_dir__mutmut['x_logs_dir__mutmut_2'] = x_logs_dir__mutmut_2 # type: ignore # mutmut generated
mutants_x_logs_dir__mutmut['x_logs_dir__mutmut_3'] = x_logs_dir__mutmut_3 # type: ignore # mutmut generated
mutants_x_state_dir__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_state_dir__mutmut)
def state_dir() -> Path:
    return boost_home() / "state"


def x_state_dir__mutmut_orig() -> Path:
    return boost_home() / "state"


def x_state_dir__mutmut_1() -> Path:
    return boost_home() * "state"


def x_state_dir__mutmut_2() -> Path:
    return boost_home() / "XXstateXX"


def x_state_dir__mutmut_3() -> Path:
    return boost_home() / "STATE"

mutants_x_state_dir__mutmut['_mutmut_orig'] = x_state_dir__mutmut_orig # type: ignore # mutmut generated
mutants_x_state_dir__mutmut['x_state_dir__mutmut_1'] = x_state_dir__mutmut_1 # type: ignore # mutmut generated
mutants_x_state_dir__mutmut['x_state_dir__mutmut_2'] = x_state_dir__mutmut_2 # type: ignore # mutmut generated
mutants_x_state_dir__mutmut['x_state_dir__mutmut_3'] = x_state_dir__mutmut_3 # type: ignore # mutmut generated
mutants_x_snapshots_dir__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_snapshots_dir__mutmut)
def snapshots_dir() -> Path:
    return state_dir() / "snapshots"


def x_snapshots_dir__mutmut_orig() -> Path:
    return state_dir() / "snapshots"


def x_snapshots_dir__mutmut_1() -> Path:
    return state_dir() * "snapshots"


def x_snapshots_dir__mutmut_2() -> Path:
    return state_dir() / "XXsnapshotsXX"


def x_snapshots_dir__mutmut_3() -> Path:
    return state_dir() / "SNAPSHOTS"

mutants_x_snapshots_dir__mutmut['_mutmut_orig'] = x_snapshots_dir__mutmut_orig # type: ignore # mutmut generated
mutants_x_snapshots_dir__mutmut['x_snapshots_dir__mutmut_1'] = x_snapshots_dir__mutmut_1 # type: ignore # mutmut generated
mutants_x_snapshots_dir__mutmut['x_snapshots_dir__mutmut_2'] = x_snapshots_dir__mutmut_2 # type: ignore # mutmut generated
mutants_x_snapshots_dir__mutmut['x_snapshots_dir__mutmut_3'] = x_snapshots_dir__mutmut_3 # type: ignore # mutmut generated
mutants_x_lock_history_dir__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_lock_history_dir__mutmut)
def lock_history_dir() -> Path:
    return state_dir() / "lock-history"


def x_lock_history_dir__mutmut_orig() -> Path:
    return state_dir() / "lock-history"


def x_lock_history_dir__mutmut_1() -> Path:
    return state_dir() * "lock-history"


def x_lock_history_dir__mutmut_2() -> Path:
    return state_dir() / "XXlock-historyXX"


def x_lock_history_dir__mutmut_3() -> Path:
    return state_dir() / "LOCK-HISTORY"

mutants_x_lock_history_dir__mutmut['_mutmut_orig'] = x_lock_history_dir__mutmut_orig # type: ignore # mutmut generated
mutants_x_lock_history_dir__mutmut['x_lock_history_dir__mutmut_1'] = x_lock_history_dir__mutmut_1 # type: ignore # mutmut generated
mutants_x_lock_history_dir__mutmut['x_lock_history_dir__mutmut_2'] = x_lock_history_dir__mutmut_2 # type: ignore # mutmut generated
mutants_x_lock_history_dir__mutmut['x_lock_history_dir__mutmut_3'] = x_lock_history_dir__mutmut_3 # type: ignore # mutmut generated
mutants_x_profiles_dir__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_profiles_dir__mutmut)
def profiles_dir() -> Path:
    return state_dir() / "profiles"


def x_profiles_dir__mutmut_orig() -> Path:
    return state_dir() / "profiles"


def x_profiles_dir__mutmut_1() -> Path:
    return state_dir() * "profiles"


def x_profiles_dir__mutmut_2() -> Path:
    return state_dir() / "XXprofilesXX"


def x_profiles_dir__mutmut_3() -> Path:
    return state_dir() / "PROFILES"

mutants_x_profiles_dir__mutmut['_mutmut_orig'] = x_profiles_dir__mutmut_orig # type: ignore # mutmut generated
mutants_x_profiles_dir__mutmut['x_profiles_dir__mutmut_1'] = x_profiles_dir__mutmut_1 # type: ignore # mutmut generated
mutants_x_profiles_dir__mutmut['x_profiles_dir__mutmut_2'] = x_profiles_dir__mutmut_2 # type: ignore # mutmut generated
mutants_x_profiles_dir__mutmut['x_profiles_dir__mutmut_3'] = x_profiles_dir__mutmut_3 # type: ignore # mutmut generated
mutants_x_config_path__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_config_path__mutmut)
def config_path() -> Path:
    return boost_home() / "config.json"


def x_config_path__mutmut_orig() -> Path:
    return boost_home() / "config.json"


def x_config_path__mutmut_1() -> Path:
    return boost_home() * "config.json"


def x_config_path__mutmut_2() -> Path:
    return boost_home() / "XXconfig.jsonXX"


def x_config_path__mutmut_3() -> Path:
    return boost_home() / "CONFIG.JSON"

mutants_x_config_path__mutmut['_mutmut_orig'] = x_config_path__mutmut_orig # type: ignore # mutmut generated
mutants_x_config_path__mutmut['x_config_path__mutmut_1'] = x_config_path__mutmut_1 # type: ignore # mutmut generated
mutants_x_config_path__mutmut['x_config_path__mutmut_2'] = x_config_path__mutmut_2 # type: ignore # mutmut generated
mutants_x_config_path__mutmut['x_config_path__mutmut_3'] = x_config_path__mutmut_3 # type: ignore # mutmut generated
mutants_x_store_dir__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_store_dir__mutmut)
def store_dir() -> Path:
    """Canonical store for installed skills."""
    override = os.environ.get("BOOST_AGENTS_STORE")
    return Path(override) if override else home() / ".agents" / "skills"


def x_store_dir__mutmut_orig() -> Path:
    """Canonical store for installed skills."""
    override = os.environ.get("BOOST_AGENTS_STORE")
    return Path(override) if override else home() / ".agents" / "skills"


def x_store_dir__mutmut_1() -> Path:
    """Canonical store for installed skills."""
    override = None
    return Path(override) if override else home() / ".agents" / "skills"


def x_store_dir__mutmut_2() -> Path:
    """Canonical store for installed skills."""
    override = os.environ.get(None)
    return Path(override) if override else home() / ".agents" / "skills"


def x_store_dir__mutmut_3() -> Path:
    """Canonical store for installed skills."""
    override = os.environ.get("XXBOOST_AGENTS_STOREXX")
    return Path(override) if override else home() / ".agents" / "skills"


def x_store_dir__mutmut_4() -> Path:
    """Canonical store for installed skills."""
    override = os.environ.get("boost_agents_store")
    return Path(override) if override else home() / ".agents" / "skills"


def x_store_dir__mutmut_5() -> Path:
    """Canonical store for installed skills."""
    override = os.environ.get("BOOST_AGENTS_STORE")
    return Path(None) if override else home() / ".agents" / "skills"


def x_store_dir__mutmut_6() -> Path:
    """Canonical store for installed skills."""
    override = os.environ.get("BOOST_AGENTS_STORE")
    return Path(override) if override else home() / ".agents" * "skills"


def x_store_dir__mutmut_7() -> Path:
    """Canonical store for installed skills."""
    override = os.environ.get("BOOST_AGENTS_STORE")
    return Path(override) if override else home() * ".agents" / "skills"


def x_store_dir__mutmut_8() -> Path:
    """Canonical store for installed skills."""
    override = os.environ.get("BOOST_AGENTS_STORE")
    return Path(override) if override else home() / "XX.agentsXX" / "skills"


def x_store_dir__mutmut_9() -> Path:
    """Canonical store for installed skills."""
    override = os.environ.get("BOOST_AGENTS_STORE")
    return Path(override) if override else home() / ".AGENTS" / "skills"


def x_store_dir__mutmut_10() -> Path:
    """Canonical store for installed skills."""
    override = os.environ.get("BOOST_AGENTS_STORE")
    return Path(override) if override else home() / ".agents" / "XXskillsXX"


def x_store_dir__mutmut_11() -> Path:
    """Canonical store for installed skills."""
    override = os.environ.get("BOOST_AGENTS_STORE")
    return Path(override) if override else home() / ".agents" / "SKILLS"

mutants_x_store_dir__mutmut['_mutmut_orig'] = x_store_dir__mutmut_orig # type: ignore # mutmut generated
mutants_x_store_dir__mutmut['x_store_dir__mutmut_1'] = x_store_dir__mutmut_1 # type: ignore # mutmut generated
mutants_x_store_dir__mutmut['x_store_dir__mutmut_2'] = x_store_dir__mutmut_2 # type: ignore # mutmut generated
mutants_x_store_dir__mutmut['x_store_dir__mutmut_3'] = x_store_dir__mutmut_3 # type: ignore # mutmut generated
mutants_x_store_dir__mutmut['x_store_dir__mutmut_4'] = x_store_dir__mutmut_4 # type: ignore # mutmut generated
mutants_x_store_dir__mutmut['x_store_dir__mutmut_5'] = x_store_dir__mutmut_5 # type: ignore # mutmut generated
mutants_x_store_dir__mutmut['x_store_dir__mutmut_6'] = x_store_dir__mutmut_6 # type: ignore # mutmut generated
mutants_x_store_dir__mutmut['x_store_dir__mutmut_7'] = x_store_dir__mutmut_7 # type: ignore # mutmut generated
mutants_x_store_dir__mutmut['x_store_dir__mutmut_8'] = x_store_dir__mutmut_8 # type: ignore # mutmut generated
mutants_x_store_dir__mutmut['x_store_dir__mutmut_9'] = x_store_dir__mutmut_9 # type: ignore # mutmut generated
mutants_x_store_dir__mutmut['x_store_dir__mutmut_10'] = x_store_dir__mutmut_10 # type: ignore # mutmut generated
mutants_x_store_dir__mutmut['x_store_dir__mutmut_11'] = x_store_dir__mutmut_11 # type: ignore # mutmut generated
mutants_x_lockfile_path__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_lockfile_path__mutmut)
def lockfile_path() -> Path:
    return store_dir() / ".skill-lock.json"


def x_lockfile_path__mutmut_orig() -> Path:
    return store_dir() / ".skill-lock.json"


def x_lockfile_path__mutmut_1() -> Path:
    return store_dir() * ".skill-lock.json"


def x_lockfile_path__mutmut_2() -> Path:
    return store_dir() / "XX.skill-lock.jsonXX"


def x_lockfile_path__mutmut_3() -> Path:
    return store_dir() / ".SKILL-LOCK.JSON"

mutants_x_lockfile_path__mutmut['_mutmut_orig'] = x_lockfile_path__mutmut_orig # type: ignore # mutmut generated
mutants_x_lockfile_path__mutmut['x_lockfile_path__mutmut_1'] = x_lockfile_path__mutmut_1 # type: ignore # mutmut generated
mutants_x_lockfile_path__mutmut['x_lockfile_path__mutmut_2'] = x_lockfile_path__mutmut_2 # type: ignore # mutmut generated
mutants_x_lockfile_path__mutmut['x_lockfile_path__mutmut_3'] = x_lockfile_path__mutmut_3 # type: ignore # mutmut generated
mutants_x_pulse_path__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_pulse_path__mutmut)
def pulse_path() -> Path:
    return state_dir() / "pulse.jsonl"


def x_pulse_path__mutmut_orig() -> Path:
    return state_dir() / "pulse.jsonl"


def x_pulse_path__mutmut_1() -> Path:
    return state_dir() * "pulse.jsonl"


def x_pulse_path__mutmut_2() -> Path:
    return state_dir() / "XXpulse.jsonlXX"


def x_pulse_path__mutmut_3() -> Path:
    return state_dir() / "PULSE.JSONL"

mutants_x_pulse_path__mutmut['_mutmut_orig'] = x_pulse_path__mutmut_orig # type: ignore # mutmut generated
mutants_x_pulse_path__mutmut['x_pulse_path__mutmut_1'] = x_pulse_path__mutmut_1 # type: ignore # mutmut generated
mutants_x_pulse_path__mutmut['x_pulse_path__mutmut_2'] = x_pulse_path__mutmut_2 # type: ignore # mutmut generated
mutants_x_pulse_path__mutmut['x_pulse_path__mutmut_3'] = x_pulse_path__mutmut_3 # type: ignore # mutmut generated
mutants_x_policy_path__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_policy_path__mutmut)
def policy_path() -> Path:
    return state_dir() / "policy.json"


def x_policy_path__mutmut_orig() -> Path:
    return state_dir() / "policy.json"


def x_policy_path__mutmut_1() -> Path:
    return state_dir() * "policy.json"


def x_policy_path__mutmut_2() -> Path:
    return state_dir() / "XXpolicy.jsonXX"


def x_policy_path__mutmut_3() -> Path:
    return state_dir() / "POLICY.JSON"

mutants_x_policy_path__mutmut['_mutmut_orig'] = x_policy_path__mutmut_orig # type: ignore # mutmut generated
mutants_x_policy_path__mutmut['x_policy_path__mutmut_1'] = x_policy_path__mutmut_1 # type: ignore # mutmut generated
mutants_x_policy_path__mutmut['x_policy_path__mutmut_2'] = x_policy_path__mutmut_2 # type: ignore # mutmut generated
mutants_x_policy_path__mutmut['x_policy_path__mutmut_3'] = x_policy_path__mutmut_3 # type: ignore # mutmut generated
mutants_x_repo_root__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_repo_root__mutmut)
def repo_root() -> Path:
    """The boost source checkout this module runs from."""
    return Path(__file__).resolve().parent.parent.parent


def x_repo_root__mutmut_orig() -> Path:
    """The boost source checkout this module runs from."""
    return Path(__file__).resolve().parent.parent.parent


def x_repo_root__mutmut_1() -> Path:
    """The boost source checkout this module runs from."""
    return Path(None).resolve().parent.parent.parent

mutants_x_repo_root__mutmut['_mutmut_orig'] = x_repo_root__mutmut_orig # type: ignore # mutmut generated
mutants_x_repo_root__mutmut['x_repo_root__mutmut_1'] = x_repo_root__mutmut_1 # type: ignore # mutmut generated
mutants_x_ensure_dirs__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_ensure_dirs__mutmut)
def ensure_dirs() -> None:
    for d in (
        boost_home(), repos_dir(), cache_dir(), logs_dir(), state_dir(),
        snapshots_dir(), lock_history_dir(), profiles_dir(), store_dir(),
    ):
        d.mkdir(parents=True, exist_ok=True)


def x_ensure_dirs__mutmut_orig() -> None:
    for d in (
        boost_home(), repos_dir(), cache_dir(), logs_dir(), state_dir(),
        snapshots_dir(), lock_history_dir(), profiles_dir(), store_dir(),
    ):
        d.mkdir(parents=True, exist_ok=True)


def x_ensure_dirs__mutmut_1() -> None:
    for d in (
        boost_home(), repos_dir(), cache_dir(), logs_dir(), state_dir(),
        snapshots_dir(), lock_history_dir(), profiles_dir(), store_dir(),
    ):
        d.mkdir(parents=None, exist_ok=True)


def x_ensure_dirs__mutmut_2() -> None:
    for d in (
        boost_home(), repos_dir(), cache_dir(), logs_dir(), state_dir(),
        snapshots_dir(), lock_history_dir(), profiles_dir(), store_dir(),
    ):
        d.mkdir(parents=True, exist_ok=None)


def x_ensure_dirs__mutmut_3() -> None:
    for d in (
        boost_home(), repos_dir(), cache_dir(), logs_dir(), state_dir(),
        snapshots_dir(), lock_history_dir(), profiles_dir(), store_dir(),
    ):
        d.mkdir(exist_ok=True)


def x_ensure_dirs__mutmut_4() -> None:
    for d in (
        boost_home(), repos_dir(), cache_dir(), logs_dir(), state_dir(),
        snapshots_dir(), lock_history_dir(), profiles_dir(), store_dir(),
    ):
        d.mkdir(parents=True, )


def x_ensure_dirs__mutmut_5() -> None:
    for d in (
        boost_home(), repos_dir(), cache_dir(), logs_dir(), state_dir(),
        snapshots_dir(), lock_history_dir(), profiles_dir(), store_dir(),
    ):
        d.mkdir(parents=False, exist_ok=True)


def x_ensure_dirs__mutmut_6() -> None:
    for d in (
        boost_home(), repos_dir(), cache_dir(), logs_dir(), state_dir(),
        snapshots_dir(), lock_history_dir(), profiles_dir(), store_dir(),
    ):
        d.mkdir(parents=True, exist_ok=False)

mutants_x_ensure_dirs__mutmut['_mutmut_orig'] = x_ensure_dirs__mutmut_orig # type: ignore # mutmut generated
mutants_x_ensure_dirs__mutmut['x_ensure_dirs__mutmut_1'] = x_ensure_dirs__mutmut_1 # type: ignore # mutmut generated
mutants_x_ensure_dirs__mutmut['x_ensure_dirs__mutmut_2'] = x_ensure_dirs__mutmut_2 # type: ignore # mutmut generated
mutants_x_ensure_dirs__mutmut['x_ensure_dirs__mutmut_3'] = x_ensure_dirs__mutmut_3 # type: ignore # mutmut generated
mutants_x_ensure_dirs__mutmut['x_ensure_dirs__mutmut_4'] = x_ensure_dirs__mutmut_4 # type: ignore # mutmut generated
mutants_x_ensure_dirs__mutmut['x_ensure_dirs__mutmut_5'] = x_ensure_dirs__mutmut_5 # type: ignore # mutmut generated
mutants_x_ensure_dirs__mutmut['x_ensure_dirs__mutmut_6'] = x_ensure_dirs__mutmut_6 # type: ignore # mutmut generated
