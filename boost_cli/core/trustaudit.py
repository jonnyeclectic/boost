"""Single source of truth for "is the set of skills I actually run healthy?".

boost already computes every individual trust signal, each in its own command:
``verify`` checks lock-file integrity, ``outdated`` compares an installed skill
against its tap, ``trust`` reports tap-level signing provenance, ``deps`` shows
the ``requires:``/``conflicts:`` graph. What nothing answered is the aggregate
question — *of the skills I have installed, which ones should I stop trusting?*

These functions are the decision layer for ``boost audit --skills``. They are
pure and I/O-free on purpose, exactly like :mod:`boost_cli.core.staleness`: the
command gathers the raw signals (``provenance.verify_dir``, a tap's last-sync
timestamp, ``staleness.upstream_reason``, ``resolve.resolve``) and passes them
in, so every branch of the *decision* is trivially testable and stays reachable
by the mutation gate.
"""
from __future__ import annotations

from collections.abc import Sequence

from . import provenance

# ── severity vocabulary ────────────────────────────────────────────────────
# Mirrors cmd_audit's content scan so one `boost audit` mental model covers
# both halves: HIGH means stop and look, MED means decide, LOW is context.
HIGH = "HIGH"
MED = "MED"
LOW = "LOW"

# ── finding labels ─────────────────────────────────────────────────────────
INVALID_SIGNATURE = "invalid-signature"  # signed, but the signature fails crypto
UNTRUSTED_TAP = "untrusted-tap"          # signed by a key you have not trusted
UNSIGNED_TAP = "unsigned-tap"            # the tap publishes no signature at all
LOCAL_SOURCE = "local-source"            # imported from a path; no tap to trust
STALE_TAP = "stale-tap"                  # the tap clone has not been synced
BEHIND_TAP = "behind-tap"                # the tap has a newer copy than yours
CONFLICT = "conflict"                    # declares conflicts: against a peer

# A tap clone older than this many days is reported as stale. Chosen to be
# quiet: a month of no upstream sync is long enough to be a real signal and
# long enough that a healthy weekly-ish `boost update` never trips it.
STALE_TAP_DAYS = 30

# label -> severity. A malformed signature is the only HIGH: it means the tap
# is actively lying about its provenance, as opposed to merely not claiming any.
SEVERITY = {
    INVALID_SIGNATURE: HIGH,
    UNTRUSTED_TAP: MED,
    CONFLICT: MED,
    UNSIGNED_TAP: LOW,
    LOCAL_SOURCE: LOW,
    STALE_TAP: LOW,
    BEHIND_TAP: LOW,
}

# provenance status -> our label. VERIFIED maps to nothing: a trusted signature
# is the healthy case and must not produce a finding.
_PROVENANCE_LABEL = {
    provenance.INVALID: INVALID_SIGNATURE,
    provenance.UNTRUSTED: UNTRUSTED_TAP,
    provenance.UNSIGNED: UNSIGNED_TAP,
}


def signing_label(status: str | None, is_local: bool = False) -> str | None:
    """The trust finding for a tap's signing ``status``, or ``None`` if healthy.

    ``is_local`` marks a skill imported from a path rather than tapped: there is
    no tap to sign it, so it reports :data:`LOCAL_SOURCE` rather than being
    silently treated as unsigned upstream content. A ``status`` of ``None``
    (tap recorded but its clone is gone) reports as unsigned — boost cannot
    show a signature it cannot read.
    """
    if is_local:
        return LOCAL_SOURCE
    if status == provenance.VERIFIED:
        return None
    if status is None:
        return UNSIGNED_TAP
    return _PROVENANCE_LABEL.get(status, UNSIGNED_TAP)


def stale_tap_label(age_days: int | None,
                    limit: int = STALE_TAP_DAYS) -> str | None:
    """:data:`STALE_TAP` when a tap clone's last sync is older than ``limit``.

    ``age_days`` is ``None`` when the age could not be determined (no clone, no
    cache timestamp); that is treated as "no signal", not as stale, so a
    missing timestamp never manufactures a finding. The comparison is strictly
    greater-than, so a tap synced exactly ``limit`` days ago is still fresh.
    """
    if age_days is None:
        return None
    return STALE_TAP if age_days > limit else None


def skill_findings(*, is_local: bool, provenance_status: str | None,
                   tap_age_days: int | None,
                   upstream_reason: str | None,
                   conflicts_with: Sequence[str] = (),
                   stale_after: int = STALE_TAP_DAYS) -> list[dict]:
    """Every trust finding for one installed skill, worst severity first.

    Each finding is ``{"severity", "label", "detail"}``. The caller supplies
    pre-computed signals:

    * ``is_local``          — imported from a path (no tap).
    * ``provenance_status`` — a :mod:`boost_cli.core.provenance` status for the
      skill's tap clone, or ``None`` when it could not be read.
    * ``tap_age_days``      — days since the tap clone last synced, or ``None``.
    * ``upstream_reason``   — :func:`staleness.upstream_reason`'s verdict.
    * ``conflicts_with``    — peer skills this one declares a ``conflicts:``
      against, already filtered to skills that are actually installed.

    A locally-imported skill is deliberately not checked for tap staleness or
    upstream drift: it has no upstream, so those axes are not signals about it.
    """
    found: list[dict] = []
    label = signing_label(provenance_status, is_local=is_local)
    if label:
        found.append({"severity": SEVERITY[label], "label": label,
                      "detail": _signing_detail(label, provenance_status)})
    if not is_local:
        # The `is not None` guard is what stale_tap_label already encodes, but
        # spelling it here keeps the %d interpolation below provably non-None.
        if tap_age_days is not None and stale_tap_label(tap_age_days, stale_after):
            found.append({"severity": SEVERITY[STALE_TAP], "label": STALE_TAP,
                          "detail": "tap last synced %d days ago" % tap_age_days})
        if upstream_reason:
            found.append({"severity": SEVERITY[BEHIND_TAP], "label": BEHIND_TAP,
                          "detail": "tap has a newer copy (%s)" % upstream_reason})
    found.extend({"severity": SEVERITY[CONFLICT], "label": CONFLICT,
                  "detail": "declares a conflict with %s" % peer}
                 for peer in conflicts_with)
    return sort_findings(found)


def _signing_detail(label: str, status: str | None) -> str:
    """Human detail for a signing finding."""
    if label == LOCAL_SOURCE:
        return "imported from a path — no tap signature to check"
    if label == UNSIGNED_TAP and status is None:
        return "tap clone is missing — signature cannot be checked"
    if label == UNSIGNED_TAP:
        return "tap publishes no signature"
    if label == UNTRUSTED_TAP:
        return "signed, but by a key that is not in your trusted set"
    return "signature is present but does not validate"


# Sort order for rendering: severity descending, then label, then detail, so
# output is deterministic (two runs of the same state print byte-identically).
_SEVERITY_RANK = {HIGH: 0, MED: 1, LOW: 2}


def sort_findings(findings: Sequence[dict]) -> list[dict]:
    """Findings ordered worst-first, then alphabetically for determinism."""
    return sorted(findings, key=lambda f: (_SEVERITY_RANK[f["severity"]],
                                           f["label"], f["detail"]))


def count_severities(findings_by_skill: dict[str, list[dict]]) -> dict[str, int]:
    """Total findings per severity across every skill."""
    counts = {HIGH: 0, MED: 0, LOW: 0}
    for findings in findings_by_skill.values():
        for finding in findings:
            counts[finding["severity"]] += 1
    return counts


def is_healthy(counts: dict[str, int]) -> bool:
    """True when nothing needs a decision — no HIGH and no MED findings.

    LOW findings alone stay healthy: an unsigned tap is the norm for most of
    the catalog today, so treating it as unhealthy would make the command cry
    wolf on a perfectly ordinary install and train users to ignore it.
    """
    return not counts[HIGH] and not counts[MED]


def exit_code(counts: dict[str, int]) -> int:
    """``0`` when healthy, ``1`` when a HIGH or MED finding needs attention.

    Matches ``cmd_audit``'s content-scan contract, so ``--skills`` composes in
    a CI pipeline the same way the default scan already does.
    """
    return 0 if is_healthy(counts) else 1


def relation_list(meta: dict | None, key: str) -> list[str]:
    """A skill's ``requires:``/``conflicts:`` frontmatter as a clean name list.

    Accepts a YAML list or a comma-separated string, drops blanks, and treats a
    missing/empty/``False`` value as "no relations" — an author writing
    ``conflicts:`` with nothing after it must not read as a conflict with "".

    ``pkg._rel_list`` and ``info._as_list`` are older command-layer copies of
    this that disagree on edge cases; folding them onto this one is a
    worthwhile follow-up, but retargeting three call sites is out of scope here.
    """
    val = (meta or {}).get(key)
    if val in (None, "", False):
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    return [s.strip() for s in str(val).split(",") if s.strip()]


def conflict_pairs(installed: Sequence[str],
                   conflicts_of) -> list[tuple[str, str]]:
    """``(skill, peer)`` pairs where both sides are installed.

    Deliberately independent of :func:`resolve.resolve`: that answers "what
    would break if I installed this", keyed off an install plan, while this
    audits a set that is *already* installed — every member is both a root and
    already present, which ``resolve`` prunes. Self-conflicts and conflicts
    against something not installed are dropped; a mutual conflict is reported
    from both sides, because both skills are equally implicated.
    """
    present = set(installed)
    pairs: list[tuple[str, str]] = []
    for name in sorted(present):
        pairs.extend((name, peer) for peer in conflicts_of(name)
                     if peer and peer != name and peer in present)
    return sorted(set(pairs))
