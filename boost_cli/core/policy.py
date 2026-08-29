# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Governance policies: ~/.boost/state/policy.json

Consulted by store.install() (when config policy_enforce is true) and by
`boost audit` / `boost policy check`.
"""
from __future__ import annotations

import contextlib
import json

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
    # Least-privilege: capability names (network/shell/filesystem) a skill may
    # not expect. A DECLARED denied capability always blocks; a merely DETECTED
    # one blocks only with enforce_detected_capabilities on (fuzzy, opt-in).
    "denied_capabilities": [],
    "enforce_detected_capabilities": False,
    # Provenance: when true, a tap must carry a signature from a trusted key
    # (see core.provenance) before it can be added.
    "require_signed_taps": False,
}


def load() -> dict:
    """Return the effective policy: DEFAULTS overlaid with policy.json.

    A missing or unparseable file silently yields the defaults.
    """
    p = paths.policy_path()
    base = DEFAULTS.copy()
    if p.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            base.update(json.loads(p.read_text(encoding="utf-8")))
    return base


def save(pol: dict) -> None:
    """Write `pol` to policy.json, restricted to the known DEFAULTS keys.

    Missing keys are filled from DEFAULTS; unknown keys are dropped.
    """
    paths.ensure_dirs()
    known = {k: pol.get(k, DEFAULTS[k]) for k in DEFAULTS}
    paths.policy_path().write_text(json.dumps(known, indent=2) + "\n", encoding="utf-8")


def check_install(entry: dict, installed_count: int) -> list[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    v: list[str] = []
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


def check_capabilities(meta: dict, text: str) -> list[str]:
    """Return capability-policy violations for a skill (empty = allowed).

    Separate from :func:`check_install` because it needs the skill's CONTENT,
    which the caller only has after resolving the source — check_install runs on
    the catalog entry alone. Honors the same ``policy_enforce`` master switch.
    """
    if not config.get("policy_enforce", True):
        return []
    from . import capabilities
    pol = load()
    denied = {str(c).strip().lower() for c in pol["denied_capabilities"]}
    if not denied:
        return []
    return capabilities.violations(
        capabilities.declared(meta), capabilities.detect(text),
        denied, bool(pol["enforce_detected_capabilities"]))


def check_tap_signing(clone_dir) -> list[str]:
    """Return provenance violations for a tap clone (empty = allowed).

    No-op unless ``require_signed_taps`` is on. When on, anything short of a
    signature from a trusted key (:func:`core.provenance.verify_dir`) is a
    violation, worded with the reason so ``boost tap`` can explain the refusal.
    Honors the ``policy_enforce`` master switch.
    """
    if not config.get("policy_enforce", True):
        return []
    pol = load()
    if not pol["require_signed_taps"]:
        return []
    from . import provenance
    result = provenance.verify_dir(clone_dir)
    if result.ok:
        return []
    reason = {
        provenance.UNSIGNED: "tap is unsigned",
        provenance.UNTRUSTED: "tap is signed but by no trusted key",
        provenance.INVALID: "tap signature is invalid",
    }.get(result.status, "tap is not verified")
    if result.detail:
        reason += " (%s)" % result.detail
    return [reason + ", and policy requires a trusted signature"]
