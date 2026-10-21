# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Governance policies: ~/.boost/state/policy.json

Consulted by store.install() (when config policy_enforce is true) and by
`boost audit` / `boost policy check`.
"""
from __future__ import annotations

import copy
import json
import sys
from collections.abc import Callable, Collection

from . import config, jsonstate, output, paths, typedvalue, util

# Once per process: install consults the policy several times, and the fault
# is the same each time.
_WARNED_CORRUPT = False

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


# Inclusive (low, high) bounds for the numeric keys; ``high`` None is unbounded.
# The type alone let `policy set min_quality_score 500` and `max_skills -1`
# through with a check mark, and the next audit or install then failed against
# a limit no skill could meet. Scores run 0-100, as `boost lint --min` says.
RANGES: dict[str, tuple[int, int | None]] = {
    "min_quality_score": (0, 100),
    "max_skills": (0, None),
}


def spec_for(key: str) -> str:
    """The value type of a policy key; :data:`typedvalue.ANY` if unknown."""
    return VALUE_TYPES.get(key, typedvalue.ANY)


def parse_value(key: str, raw: str):
    """Read a typed value for `key` out of the string a user typed.

    Raises :class:`typedvalue.ValueTypeError` when the text cannot be read at
    the key's type — at the setter, where the user can still fix it, rather
    than as a traceback out of the middle of the next install.
    """
    return _in_range(key, typedvalue.coerce(key, raw, spec_for(key)), raw)


def _range_phrase(key: str, low: int, high: int | None) -> str:
    phrase = ("a whole number from %d to %d" % (low, high) if high is not None
              else "a whole number of %d or more" % low)
    if spec_for(key) == typedvalue.INT_OR_NONE:
        phrase += ", or null for no limit"
    return phrase


def _in_range(key: str, value, raw):
    """``value`` if it is inside the key's :data:`RANGES`, else raise.

    Raises :class:`typedvalue.ValueTypeError` naming the range, so the
    setter's usage error and :func:`invalid_values` word it the same way.
    ``None`` (no limit) is never out of range.
    """
    bounds = RANGES.get(key)
    if bounds is None or value is None:
        return value
    low, high = bounds
    if value < low or (high is not None and value > high):
        raise typedvalue.ValueTypeError(key, raw, spec_for(key),
                                        expected=_range_phrase(key, low, high))
    return value


def _read_stored(key: str, value):
    """A stored value at its declared type and range, or raise."""
    return _in_range(key, typedvalue.adapt(key, value, spec_for(key)), value)


def check() -> str | None:
    """Why policy.json cannot be read, or None when it reads or is absent.

    Never prints: `boost doctor` reports it as an issue, and the enforcement
    checks turn it into a violation (:func:`corrupt_violation`).
    """
    return jsonstate.read_object(paths.policy_path())[1]


def corrupt_violation(action: str = "install") -> str | None:
    """The violation a policy.json that exists but does not parse amounts to.

    A policy that cannot be read is not "no policy": a truncated write of a
    blocklist used to read as an empty one, so the blocked skill installed
    and `boost policy check` passed. Enforcement fails closed instead.
    """
    err = check()
    if err is None:
        return None
    return ("%s — boost cannot read the policy, so it will not %s until "
            "the file is repaired" % (err, action))


def invalid_violation(action: str = "install") -> str | None:
    """The violation stored values unreadable at their type amount to.

    :func:`load` reads such a value as its default, and every default is the
    permissive one: a blocklist written as an object read as an empty list,
    ``"pin_only": "frozen"`` as False, so the blocked skill installed and
    `boost policy check` passed. Enforcement fails closed instead, naming
    each key and the type it expects.
    """
    bad = invalid_values()
    if not bad:
        return None
    return ("policy.json holds %s — boost cannot read %s, so it will not %s "
            "until %s fixed with `boost policy set` or `boost policy unset`"
            % ("; ".join("%s = %s, which expects %s"
                         % (key, json.dumps(value), expected)
                         for key, value, expected in bad),
               "it" if len(bad) == 1 else "them", action,
               "it is" if len(bad) == 1 else "they are"))


def unreadable_violation(action: str = "install") -> str | None:
    """:func:`corrupt_violation`, else :func:`invalid_violation`, else None."""
    return corrupt_violation(action) or invalid_violation(action)


def _read_file() -> dict:
    """The raw contents of policy.json; ``{}`` when missing or unusable.

    Unusable is warned about once per process on stderr, never silently
    folded into "missing".
    """
    global _WARNED_CORRUPT
    data, err = jsonstate.read_object(paths.policy_path())
    if err is not None and not _WARNED_CORRUPT:
        _WARNED_CORRUPT = True
        output.warn("%s — reading the policy as defaults; installs are "
                    "refused until it is repaired, and the next `boost policy "
                    "set` moves it aside to policy.json.corrupt" % err,
                    stream=sys.stderr, wrap=True)
    return data or {}


def load() -> dict:
    """Return the effective policy: DEFAULTS overlaid with policy.json.

    A missing file yields the defaults; an unparseable one does too, with a
    warning, and :func:`check_install` refuses while it stays so. Every stored
    value is read at its declared type, so a hand-edited (or older-boost)
    ``"pin_only": "no"`` is the boolean the user meant and not a truthy string
    that freezes the machine. A value that cannot be read at its type falls
    back to the default — as does one outside its :data:`RANGES` — and is
    reported by :func:`invalid_values`, never raised into the middle of an
    install. The default is for display only: :func:`check_install` and
    :func:`check_tap_signing` refuse while any value is unreadable
    (:func:`invalid_violation`), and :func:`mutate` never writes the default
    over it.
    """
    base = copy.deepcopy(DEFAULTS)     # its lists are mutated by mutate()
    for key, value in _read_file().items():
        if key not in DEFAULTS:
            base[key] = value
            continue
        try:
            base[key] = _read_stored(key, value)
        except typedvalue.ValueTypeError:
            base[key] = DEFAULTS[key]
    return base


def invalid_values() -> list[tuple[str, object, str]]:
    """Stored policy values that could not be read at their declared type or range.

    Each row is ``(key, stored value, expected phrase)``. :func:`load` has
    already substituted the default for these, so this is what lets `boost
    policy` say which keys are being ignored and why.
    """
    bad: list[tuple[str, object, str]] = []
    for key, value in _read_file().items():
        if key not in DEFAULTS:
            continue
        try:
            _read_stored(key, value)
        except typedvalue.ValueTypeError as e:
            bad.append((key, value, e.expected))
    return bad


def save(pol: dict) -> None:
    """Write `pol` to policy.json, restricted to the known DEFAULTS keys.

    Missing keys are filled from DEFAULTS; unknown keys are dropped. A
    policy.json that does not parse is moved aside with
    :func:`jsonstate.quarantine` first, so the rules it still held are kept
    rather than overwritten by a file built from the defaults.
    """
    p = paths.policy_path()
    known = {k: pol.get(k, DEFAULTS[k]) for k in DEFAULTS}
    jsonstate.save(p, json.dumps(known, indent=2) + "\n",
                   corrupt=jsonstate.is_corrupt(p), noun="policy", wrap=True)


def guard_path():
    """The sidecar :func:`mutate` locks: beside policy.json, never it."""
    p = paths.policy_path()
    return p.with_name(p.name + ".lock")


def mutate(fn: Callable[[dict], bool | None],
           repairs: Collection[str] = ()) -> bool:
    """Apply ``fn`` to a fresh :func:`load` and :func:`save` it, atomically.

    `boost policy set` used to `load()`, change one key and `save()` the
    whole file with nothing between processes, so two shells setting
    different keys reverted each other behind a check mark — and a
    blocklist entry another shell had just added could vanish, failing the
    policy open. The read happens inside an exclusive cross-process lock.
    ``fn`` returning False skips the write; returns whether it wrote.

    ``repairs`` names the keys this write replaces outright. Every *other*
    key whose stored value is unreadable is written back exactly as it was
    stored: :func:`load` read it as its default, and saving that would have
    replaced a blocklist written by hand with an empty one behind a check
    mark — while keeping it leaves enforcement refusing until it is fixed.
    """
    with util.file_lock(guard_path(), what="the policy file", strict=False):
        keep = {key: value for key, value, _ in invalid_values()
                if key not in repairs}
        pol = load()
        if fn(pol) is False:
            return False
        pol.update(keep)
        save(pol)
        return True


def set_key(key: str, value) -> None:
    """Set one policy key on a fresh read, under :func:`mutate`."""
    def put(pol: dict) -> None:
        pol[key] = value
    mutate(put, repairs=(key,))


def is_blocked(name: str, tap: str | None, blocked) -> bool:
    """Whether ``blocked_skills`` names this item, bare or tap-qualified.

    ``boost install`` takes ``tap:name``, so a blocklist entry written the same
    way has to match too: comparing only the bare name stored
    ``fx:cowboy-coding`` with a check mark and then never enforced it.
    A bare entry still blocks the name from every tap.
    """
    blocked = blocked or []
    return name in blocked or (bool(tap) and "%s:%s" % (tap, name) in blocked)


def check_install(entry: dict, installed_count: int) -> list[str]:
    """Return a list of violation strings (empty = allowed)."""
    if not config.get("policy_enforce", True):
        return []
    unreadable = unreadable_violation()
    if unreadable is not None:
        return [unreadable]
    pol = load()
    v: list[str] = []
    name, tap = entry.get("name", ""), entry.get("tap", "")
    if pol["pin_only"]:
        v.append("environment is pin-only (frozen)")
    if is_blocked(name, tap, pol["blocked_skills"]):
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


def check_installed_version(entry: dict) -> list[str]:
    """require_version violation for an already-installed lock entry.

    Companion to :func:`check_install`, run retrospectively by ``boost policy
    check`` instead of at install time. The lock entry already carries the
    installed version for every kind (skill, rule, workflow — see
    ``lockfile``'s schema note), so unlike description/capability checks this
    needs no store read. Honors the same ``policy_enforce`` master switch.
    """
    if not config.get("policy_enforce", True):
        return []
    if load()["require_version"] and entry.get("version") in (None, "", "0.0.0"):
        return ["skill has no version (required by policy)"]
    return []


def check_installed_meta(meta: dict, text: str) -> list[str]:
    """require_description + denied_capabilities violations from a store copy.

    ``meta``/``text`` are a skill's parsed frontmatter and body, as read from
    its canonical store directory (there is no equivalent on-disk body for a
    rule or workflow, so callers restrict this to skills). A caller that
    could not read the store copy honestly must not call this at all — a
    missing or unreadable file is "not checked", never a silent pass or a
    false violation. Honors ``policy_enforce``.
    """
    if not config.get("policy_enforce", True):
        return []
    v: list[str] = []
    if load()["require_description"] and not meta.get("description"):
        v.append("skill has no description (required by policy)")
    v.extend(check_capabilities(meta, text))
    return v


def max_skills_violation(skill_count: int) -> str | None:
    """A single violation when the installed skill count exceeds max_skills.

    Kept apart from the per-item checks above: the cap is a property of the
    whole environment, not any one skill, so it must be reported once — not
    once per installed skill. Honors ``policy_enforce``.
    """
    if not config.get("policy_enforce", True):
        return None
    pol = load()
    if pol["max_skills"] is not None and skill_count > int(pol["max_skills"]):
        return "max_skills limit (%s) exceeded (%s installed)" % (
            pol["max_skills"], skill_count)
    return None


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


def source_violations(name: str, pol: dict) -> list[str]:
    """``blocked_taps``/``allowed_taps`` violations for a non-tap source.

    ``name`` is the tap name the source's URL would get from ``boost tap``
    (``registry.parse_spec``). A `boost import <URL>` is recorded as tap
    ``local``, which the allowlist exempts because a directory on this disk
    names no source to allow. A clone does name one, so it gets the gates
    its tap would — with no ``local`` exemption. ``pol`` is a :func:`load`.
    """
    v: list[str] = []
    if name in pol["blocked_taps"]:
        v.append("source %r is blocked" % name)
    if pol["allowed_taps"] and name not in pol["allowed_taps"]:
        v.append("source %r is not on the allowlist" % name)
    return v


def check_source(name: str, clone_dir) -> list[str]:
    """Every tap gate for a clone installed without a tap (`boost import`).

    :func:`source_violations` plus :func:`check_tap_signing` on the clone, so
    an import of a URL that `boost tap` would refuse is refused too. Fails
    closed on an unreadable policy and honors ``policy_enforce``.
    """
    if not config.get("policy_enforce", True):
        return []
    unreadable = unreadable_violation()
    if unreadable is not None:
        return [unreadable]
    return source_violations(name, load()) + check_tap_signing(clone_dir,
                                                               what="source")


def check_tap_signing(clone_dir, what: str = "tap",
                      commit: str | None = None) -> list[str]:
    """Return provenance violations for a tap clone (empty = allowed).

    No-op unless ``require_signed_taps`` is on. When on, anything short of a
    signature from a trusted key (:func:`core.provenance.verify_dir`) is a
    violation, worded with the reason so ``boost tap`` can explain the refusal.
    ``what`` is the noun the reason starts with (``source`` for an import).
    Honors the ``policy_enforce`` master switch.

    ``commit`` checks that commit's signed files, read from the clone's object
    store, instead of the working tree — so ``boost update`` can refuse a
    fetched commit before the clone moves onto it.
    """
    if not config.get("policy_enforce", True):
        return []
    # Fail closed like check_install: a truncated policy.json, or a
    # "require_signed_taps": "maybe", reads as the default, False, and would
    # admit any tap.
    unreadable = unreadable_violation("tap")
    if unreadable is not None:
        return [unreadable]
    pol = load()
    if not pol["require_signed_taps"]:
        return []
    from . import provenance
    result = (provenance.verify_dir(clone_dir) if commit is None
              else provenance.verify_commit(clone_dir, commit))
    if result.ok:
        return []
    reason = {
        provenance.UNSIGNED: "%s is unsigned",
        provenance.UNTRUSTED: "%s is signed but by no trusted key",
        provenance.INVALID: "%s signature is invalid",
    }.get(result.status, "%s is not verified") % what
    if result.detail:
        reason += " (%s)" % result.detail
    return [reason + ", and policy requires a trusted signature"]
