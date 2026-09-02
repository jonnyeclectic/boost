# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Governance policies: ~/.boost/state/policy.json

Consulted by store.install() (when config policy_enforce is true) and by
`boost audit` / `boost policy check`.
"""
from __future__ import annotations

import contextlib
import json

from . import config, paths, typedvalue

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

# Per-key value types, derived from DEFAULTS so the two can never disagree.
# `max_skills` is the one key whose default (None) names no type, so it says
# so explicitly: a cap is a number, and "no cap" is null.
VALUE_TYPES: dict[str, str] = {k: typedvalue.spec_for(v) for k, v in DEFAULTS.items()}
VALUE_TYPES["max_skills"] = typedvalue.INT_OR_NONE


def spec_for(key: str) -> str:
    """The value type of a policy key; :data:`typedvalue.ANY` if unknown."""
    return VALUE_TYPES.get(key, typedvalue.ANY)


def parse_value(key: str, raw: str):
    """Read a typed value for `key` out of the string a user typed.

    Raises :class:`typedvalue.ValueTypeError` when the text cannot be read at
    the key's type — at the setter, where the user can still fix it, rather
    than as a traceback out of the middle of the next install.
    """
    return typedvalue.coerce(key, raw, spec_for(key))


def _read_file() -> dict:
    """The raw contents of policy.json; ``{}`` when missing or unparseable."""
    p = paths.policy_path()
    if not p.exists():
        return {}
    with contextlib.suppress(json.JSONDecodeError, OSError):
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    return {}


def load() -> dict:
    """Return the effective policy: DEFAULTS overlaid with policy.json.

    A missing or unparseable file silently yields the defaults. Every stored
    value is read at its declared type, so a hand-edited (or older-boost)
    ``"pin_only": "no"`` is the boolean the user meant and not a truthy string
    that freezes the machine. A value that cannot be read at its type falls
    back to the default and is reported by :func:`invalid_values` — never
    raised into the middle of an install, and never silently obeyed either.
    """
    base = DEFAULTS.copy()
    for key, value in _read_file().items():
        if key not in DEFAULTS:
            base[key] = value
            continue
        try:
            base[key] = typedvalue.adapt(key, value, spec_for(key))
        except typedvalue.ValueTypeError:
            base[key] = DEFAULTS[key]
    return base


def invalid_values() -> list[tuple[str, object, str]]:
    """Stored policy values that could not be read at their declared type.

    Each row is ``(key, stored value, expected phrase)``. :func:`load` has
    already substituted the default for these, so this is what lets `boost
    policy` say which keys are being ignored and why.
    """
    bad: list[tuple[str, object, str]] = []
    for key, value in _read_file().items():
        if key not in DEFAULTS:
            continue
        try:
            typedvalue.adapt(key, value, spec_for(key))
        except typedvalue.ValueTypeError as e:
            bad.append((key, value, e.expected))
    return bad


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
