"""Governance policies: ~/.boost/state/policy.json

Consulted by store.install() (when config policy_enforce is true) and by
`boost audit` / `boost policy check`.
"""
from __future__ import annotations

import json
from typing import List

from . import config, paths

DEFAULTS = {
    "blocked_skills": [],      # names never allowed
    "blocked_taps": [],        # tap names never allowed
    "allowed_taps": [],        # if non-empty, ONLY these taps allowed
    "require_description": False,
    "require_version": False,
    "min_quality_score": 0,    # enforced by `boost audit`, advisory at install
    "max_skills": None,        # cap on installed count
    "pin_only": False,         # block installs/updates entirely (frozen env)
}


from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated, MutantDict
mutants_x_load__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_load__mutmut)
def load() -> dict:
    p = paths.policy_path()
    base = dict(DEFAULTS)
    if p.exists():
        try:
            base.update(json.loads(p.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    return base


def x_load__mutmut_orig() -> dict:
    p = paths.policy_path()
    base = dict(DEFAULTS)
    if p.exists():
        try:
            base.update(json.loads(p.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    return base


def x_load__mutmut_1() -> dict:
    p = None
    base = dict(DEFAULTS)
    if p.exists():
        try:
            base.update(json.loads(p.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    return base


def x_load__mutmut_2() -> dict:
    p = paths.policy_path()
    base = None
    if p.exists():
        try:
            base.update(json.loads(p.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    return base


def x_load__mutmut_3() -> dict:
    p = paths.policy_path()
    base = dict(None)
    if p.exists():
        try:
            base.update(json.loads(p.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    return base


def x_load__mutmut_4() -> dict:
    p = paths.policy_path()
    base = dict(DEFAULTS)
    if p.exists():
        try:
            base.update(None)
        except (json.JSONDecodeError, OSError):
            pass
    return base


def x_load__mutmut_5() -> dict:
    p = paths.policy_path()
    base = dict(DEFAULTS)
    if p.exists():
        try:
            base.update(json.loads(None))
        except (json.JSONDecodeError, OSError):
            pass
    return base

mutants_x_load__mutmut['_mutmut_orig'] = x_load__mutmut_orig # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_1'] = x_load__mutmut_1 # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_2'] = x_load__mutmut_2 # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_3'] = x_load__mutmut_3 # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_4'] = x_load__mutmut_4 # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_5'] = x_load__mutmut_5 # type: ignore # mutmut generated
mutants_x_save__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_save__mutmut)
def save(pol: dict) -> None:
    paths.ensure_dirs()
    known = {k: pol.get(k, DEFAULTS[k]) for k in DEFAULTS}
    paths.policy_path().write_text(json.dumps(known, indent=2) + "\n")


def x_save__mutmut_orig(pol: dict) -> None:
    paths.ensure_dirs()
    known = {k: pol.get(k, DEFAULTS[k]) for k in DEFAULTS}
    paths.policy_path().write_text(json.dumps(known, indent=2) + "\n")


def x_save__mutmut_1(pol: dict) -> None:
    paths.ensure_dirs()
    known = None
    paths.policy_path().write_text(json.dumps(known, indent=2) + "\n")


def x_save__mutmut_2(pol: dict) -> None:
    paths.ensure_dirs()
    known = {k: pol.get(None, DEFAULTS[k]) for k in DEFAULTS}
    paths.policy_path().write_text(json.dumps(known, indent=2) + "\n")


def x_save__mutmut_3(pol: dict) -> None:
    paths.ensure_dirs()
    known = {k: pol.get(k, None) for k in DEFAULTS}
    paths.policy_path().write_text(json.dumps(known, indent=2) + "\n")


def x_save__mutmut_4(pol: dict) -> None:
    paths.ensure_dirs()
    known = {k: pol.get(DEFAULTS[k]) for k in DEFAULTS}
    paths.policy_path().write_text(json.dumps(known, indent=2) + "\n")


def x_save__mutmut_5(pol: dict) -> None:
    paths.ensure_dirs()
    known = {k: pol.get(k, ) for k in DEFAULTS}
    paths.policy_path().write_text(json.dumps(known, indent=2) + "\n")


def x_save__mutmut_6(pol: dict) -> None:
    paths.ensure_dirs()
    known = {k: pol.get(k, DEFAULTS[k]) for k in DEFAULTS}
    paths.policy_path().write_text(None)


def x_save__mutmut_7(pol: dict) -> None:
    paths.ensure_dirs()
    known = {k: pol.get(k, DEFAULTS[k]) for k in DEFAULTS}
    paths.policy_path().write_text(json.dumps(known, indent=2) - "\n")


def x_save__mutmut_8(pol: dict) -> None:
    paths.ensure_dirs()
    known = {k: pol.get(k, DEFAULTS[k]) for k in DEFAULTS}
    paths.policy_path().write_text(json.dumps(None, indent=2) + "\n")


def x_save__mutmut_9(pol: dict) -> None:
    paths.ensure_dirs()
    known = {k: pol.get(k, DEFAULTS[k]) for k in DEFAULTS}
    paths.policy_path().write_text(json.dumps(known, indent=None) + "\n")


def x_save__mutmut_10(pol: dict) -> None:
    paths.ensure_dirs()
    known = {k: pol.get(k, DEFAULTS[k]) for k in DEFAULTS}
    paths.policy_path().write_text(json.dumps(indent=2) + "\n")


def x_save__mutmut_11(pol: dict) -> None:
    paths.ensure_dirs()
    known = {k: pol.get(k, DEFAULTS[k]) for k in DEFAULTS}
    paths.policy_path().write_text(json.dumps(known, ) + "\n")


def x_save__mutmut_12(pol: dict) -> None:
    paths.ensure_dirs()
    known = {k: pol.get(k, DEFAULTS[k]) for k in DEFAULTS}
    paths.policy_path().write_text(json.dumps(known, indent=3) + "\n")


def x_save__mutmut_13(pol: dict) -> None:
    paths.ensure_dirs()
    known = {k: pol.get(k, DEFAULTS[k]) for k in DEFAULTS}
    paths.policy_path().write_text(json.dumps(known, indent=2) + "XX\nXX")

mutants_x_save__mutmut['_mutmut_orig'] = x_save__mutmut_orig # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_1'] = x_save__mutmut_1 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_2'] = x_save__mutmut_2 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_3'] = x_save__mutmut_3 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_4'] = x_save__mutmut_4 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_5'] = x_save__mutmut_5 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_6'] = x_save__mutmut_6 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_7'] = x_save__mutmut_7 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_8'] = x_save__mutmut_8 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_9'] = x_save__mutmut_9 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_10'] = x_save__mutmut_10 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_11'] = x_save__mutmut_11 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_12'] = x_save__mutmut_12 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_13'] = x_save__mutmut_13 # type: ignore # mutmut generated
mutants_x_check_install__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_check_install__mutmut)
def check_install(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_orig(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_1(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_2(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get(None, True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_3(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", None):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_4(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get(True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_5(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", ):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_6(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("XXpolicy_enforceXX", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_7(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("POLICY_ENFORCE", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_8(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", False):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_9(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = None
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_10(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = None
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_11(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = None
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_12(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get(None, ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_13(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", None), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_14(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get(""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_15(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_16(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("XXnameXX", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_17(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("NAME", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_18(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", "XXXX"), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_19(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get(None, "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_20(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", None)
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_21(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_22(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", )
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_23(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("XXtapXX", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_24(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("TAP", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_25(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "XXXX")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_26(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["XXpin_onlyXX"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_27(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["PIN_ONLY"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_28(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append(None)
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_29(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("XXenvironment is pin-only (frozen)XX")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_30(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("ENVIRONMENT IS PIN-ONLY (FROZEN)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_31(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name not in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_32(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["XXblocked_skillsXX"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_33(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["BLOCKED_SKILLS"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_34(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append(None)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_35(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" / name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_36(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("XXskill %r is on the blocklistXX" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_37(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("SKILL %R IS ON THE BLOCKLIST" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_38(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap not in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_39(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["XXblocked_tapsXX"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_40(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["BLOCKED_TAPS"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_41(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append(None)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_42(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" / tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_43(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("XXtap %r is blockedXX" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_44(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("TAP %R IS BLOCKED" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_45(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] or tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_46(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] or tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_47(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["XXallowed_tapsXX"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_48(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["ALLOWED_TAPS"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_49(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_50(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["XXallowed_tapsXX"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_51(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["ALLOWED_TAPS"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_52(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap == "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_53(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "XXlocalXX":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_54(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "LOCAL":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_55(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append(None)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_56(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" / tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_57(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("XXtap %r is not on the allowlistXX" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_58(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("TAP %R IS NOT ON THE ALLOWLIST" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_59(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] or not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_60(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["XXrequire_descriptionXX"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_61(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["REQUIRE_DESCRIPTION"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_62(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_63(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get(None):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_64(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("XXdescriptionXX"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_65(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("DESCRIPTION"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_66(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append(None)
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_67(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("XXskill has no description (required by policy)XX")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_68(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("SKILL HAS NO DESCRIPTION (REQUIRED BY POLICY)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_69(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] or entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_70(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["XXrequire_versionXX"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_71(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["REQUIRE_VERSION"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_72(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get(None) in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_73(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("XXversionXX") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_74(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("VERSION") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_75(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") not in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_76(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "XXXX", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_77(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "XX0.0.0XX"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_78(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append(None)
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_79(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("XXskill has no version (required by policy)XX")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_80(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("SKILL HAS NO VERSION (REQUIRED BY POLICY)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_81(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None or installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_82(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["XXmax_skillsXX"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_83(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["MAX_SKILLS"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_84(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_85(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count > int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_86(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(None):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_87(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["XXmax_skillsXX"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_88(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["MAX_SKILLS"]):
        v.append("max_skills limit (%s) reached" % pol["max_skills"])
    return v


def x_check_install__mutmut_89(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append(None)
    return v


def x_check_install__mutmut_90(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" / pol["max_skills"])
    return v


def x_check_install__mutmut_91(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("XXmax_skills limit (%s) reachedXX" % pol["max_skills"])
    return v


def x_check_install__mutmut_92(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("MAX_SKILLS LIMIT (%S) REACHED" % pol["max_skills"])
    return v


def x_check_install__mutmut_93(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["XXmax_skillsXX"])
    return v


def x_check_install__mutmut_94(entry: dict, installed_count: int) -> List[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: List[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if name in pol["blocked_skills"]:
        v.append("skill %r is on the blocklist" % name)
    if tap in pol["blocked_taps"]:
        v.append("tap %r is blocked" % tap)
    if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
        v.append("tap %r is not on the allowlist" % tap)
    if pol["require_description"] and not entry.get("description"):
        v.append("skill has no description (required by policy)")
    if pol["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        v.append("skill has no version (required by policy)")
    if pol["max_skills"] is not None and installed_count >= int(pol["max_skills"]):
        v.append("max_skills limit (%s) reached" % pol["MAX_SKILLS"])
    return v

mutants_x_check_install__mutmut['_mutmut_orig'] = x_check_install__mutmut_orig # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_1'] = x_check_install__mutmut_1 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_2'] = x_check_install__mutmut_2 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_3'] = x_check_install__mutmut_3 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_4'] = x_check_install__mutmut_4 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_5'] = x_check_install__mutmut_5 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_6'] = x_check_install__mutmut_6 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_7'] = x_check_install__mutmut_7 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_8'] = x_check_install__mutmut_8 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_9'] = x_check_install__mutmut_9 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_10'] = x_check_install__mutmut_10 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_11'] = x_check_install__mutmut_11 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_12'] = x_check_install__mutmut_12 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_13'] = x_check_install__mutmut_13 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_14'] = x_check_install__mutmut_14 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_15'] = x_check_install__mutmut_15 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_16'] = x_check_install__mutmut_16 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_17'] = x_check_install__mutmut_17 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_18'] = x_check_install__mutmut_18 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_19'] = x_check_install__mutmut_19 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_20'] = x_check_install__mutmut_20 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_21'] = x_check_install__mutmut_21 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_22'] = x_check_install__mutmut_22 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_23'] = x_check_install__mutmut_23 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_24'] = x_check_install__mutmut_24 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_25'] = x_check_install__mutmut_25 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_26'] = x_check_install__mutmut_26 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_27'] = x_check_install__mutmut_27 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_28'] = x_check_install__mutmut_28 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_29'] = x_check_install__mutmut_29 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_30'] = x_check_install__mutmut_30 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_31'] = x_check_install__mutmut_31 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_32'] = x_check_install__mutmut_32 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_33'] = x_check_install__mutmut_33 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_34'] = x_check_install__mutmut_34 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_35'] = x_check_install__mutmut_35 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_36'] = x_check_install__mutmut_36 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_37'] = x_check_install__mutmut_37 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_38'] = x_check_install__mutmut_38 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_39'] = x_check_install__mutmut_39 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_40'] = x_check_install__mutmut_40 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_41'] = x_check_install__mutmut_41 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_42'] = x_check_install__mutmut_42 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_43'] = x_check_install__mutmut_43 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_44'] = x_check_install__mutmut_44 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_45'] = x_check_install__mutmut_45 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_46'] = x_check_install__mutmut_46 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_47'] = x_check_install__mutmut_47 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_48'] = x_check_install__mutmut_48 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_49'] = x_check_install__mutmut_49 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_50'] = x_check_install__mutmut_50 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_51'] = x_check_install__mutmut_51 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_52'] = x_check_install__mutmut_52 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_53'] = x_check_install__mutmut_53 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_54'] = x_check_install__mutmut_54 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_55'] = x_check_install__mutmut_55 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_56'] = x_check_install__mutmut_56 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_57'] = x_check_install__mutmut_57 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_58'] = x_check_install__mutmut_58 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_59'] = x_check_install__mutmut_59 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_60'] = x_check_install__mutmut_60 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_61'] = x_check_install__mutmut_61 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_62'] = x_check_install__mutmut_62 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_63'] = x_check_install__mutmut_63 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_64'] = x_check_install__mutmut_64 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_65'] = x_check_install__mutmut_65 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_66'] = x_check_install__mutmut_66 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_67'] = x_check_install__mutmut_67 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_68'] = x_check_install__mutmut_68 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_69'] = x_check_install__mutmut_69 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_70'] = x_check_install__mutmut_70 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_71'] = x_check_install__mutmut_71 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_72'] = x_check_install__mutmut_72 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_73'] = x_check_install__mutmut_73 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_74'] = x_check_install__mutmut_74 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_75'] = x_check_install__mutmut_75 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_76'] = x_check_install__mutmut_76 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_77'] = x_check_install__mutmut_77 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_78'] = x_check_install__mutmut_78 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_79'] = x_check_install__mutmut_79 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_80'] = x_check_install__mutmut_80 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_81'] = x_check_install__mutmut_81 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_82'] = x_check_install__mutmut_82 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_83'] = x_check_install__mutmut_83 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_84'] = x_check_install__mutmut_84 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_85'] = x_check_install__mutmut_85 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_86'] = x_check_install__mutmut_86 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_87'] = x_check_install__mutmut_87 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_88'] = x_check_install__mutmut_88 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_89'] = x_check_install__mutmut_89 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_90'] = x_check_install__mutmut_90 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_91'] = x_check_install__mutmut_91 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_92'] = x_check_install__mutmut_92 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_93'] = x_check_install__mutmut_93 # type: ignore # mutmut generated
mutants_x_check_install__mutmut['x_check_install__mutmut_94'] = x_check_install__mutmut_94 # type: ignore # mutmut generated
