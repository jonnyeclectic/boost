"""Governance policies: ~/.boost/state/policy.json

Consulted by store.install() (when config policy_enforce is true) and by
`boost audit` / `boost policy check`.
"""
from __future__ import annotations

import json
from typing import List

from . import config, paths
import contextlib

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


def load() -> dict:
    p = paths.policy_path()
    base = dict(DEFAULTS)
    if p.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            base.update(json.loads(p.read_text(encoding="utf-8")))
    return base


def save(pol: dict) -> None:
    paths.ensure_dirs()
    known = {k: pol.get(k, DEFAULTS[k]) for k in DEFAULTS}
    paths.policy_path().write_text(json.dumps(known, indent=2) + "\n", encoding="utf-8")


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
