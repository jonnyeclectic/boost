# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Single source of truth for "is an installed skill stale vs its tap?".

``cmd_update`` (pkg.py), ``cmd_outdated`` (taps.py) and ``_drift_status``
(quality.py) each re-derived this from the same three signals — the catalog
version, the tap's HEAD commit and the source tree's ``sha256`` — so the logic
lived in three places that would inevitably drift apart. These two pure
(I/O-free) functions are now the one decision the commands render.

Keeping them free of any filesystem/subprocess access is deliberate: the
commands gather the raw signals (``head_commit``, ``source_dir_for``,
``sha256_dir``) and pass them in, so the *decision* stays trivially testable.
"""
from __future__ import annotations

from collections.abc import Iterable

from . import util

# ── upstream_reason: why a tap's copy is newer than the installed one ──────
VERSION = "version"  # the catalog advertises a higher semver
CONTENT = "content"  # the tap HEAD moved AND the source tree's bytes changed


def upstream_reason(installed_version: str, latest_version: str,
                    installed_commit: str, tap_head: str,
                    installed_sha: str, source_sha: str | None,
                    exec_changed: bool = False) -> str | None:
    """Why the tap's copy is newer than the installed one, else ``None``.

    Mirrors the historical order exactly: a higher advertised semver wins
    immediately; otherwise a *moved* tap HEAD **plus** a changed source tree
    counts as content drift. ``source_sha`` is ``None`` when the source tree
    could not be hashed (missing checkout) — treated as "no content signal",
    i.e. not stale on that axis. ``exec_changed`` says the source's exec bits
    differ from the installed copy's (:func:`store.source_exec_changed`): a
    mode-only commit is content drift too.
    """
    if util.semver_gt(latest_version, installed_version):
        return VERSION
    if (tap_head and tap_head != installed_commit and source_sha is not None
            and (source_sha != installed_sha or exec_changed)):
        return CONTENT
    return None


# ── catalog_relation: installed version against the catalog's ─────────────
BEHIND = "behind"  # the catalog advertises a newer version: an update exists
AHEAD = "ahead"    # the installed copy is newer, as after `evolve --apply`


def catalog_relation(installed_version: str, latest_version: str
                     ) -> str | None:
    """Where the installed version sits against the catalog's, else ``None``.

    Compared as versions, never as strings: ``1.4.1`` against a tap still at
    ``1.4.0`` differs as a string, and `boost info` used to call that an
    "update available" to a lower version while `boost outdated` (which uses
    ``semver_gt``) said up to date. An empty ``latest_version`` means the
    catalog declares none, so there is nothing to compare.
    """
    if not latest_version:
        return None
    if util.semver_gt(latest_version, installed_version):
        return BEHIND
    if util.semver_gt(installed_version, latest_version):
        return AHEAD
    return None


# ── update_hold: why `boost update` must leave an installed copy alone ────
HOLD_LOCAL_EDITS = "local-edits"  # the installed copy was edited after install
HOLD_DOWNGRADE = "downgrade"      # the tap now advertises an older version


def update_hold(locally_modified: bool, installed_version: str,
                latest_version: str, discard_edits: bool,
                allow_downgrade: bool) -> str | None:
    """Why an otherwise-due refresh must be skipped, else ``None``.

    Both holds guard something an overwrite cannot give back. A local edit is
    the one copy of the user's change -- `boost drift` already calls it
    local-edits and update used to overwrite it anyway, unseen. A tap rewound
    to an older release reads as "source changed" to `upstream_reason`, so it
    was followed silently, version and all. Edits outrank the downgrade
    because they are the part that is unrecoverable. An empty
    ``latest_version`` declares nothing and is not a downgrade
    (`catalog_relation`). Each hold has its own release -- ``discard_edits``
    and ``allow_downgrade`` -- because consenting to lose an edit is not
    consenting to walk a version back, and neither is what `--force` (move
    pinned taps) asked for. The caller then says what it did.
    """
    if locally_modified and not discard_edits:
        return HOLD_LOCAL_EDITS
    if (not allow_downgrade
            and catalog_relation(installed_version, latest_version) == AHEAD):
        return HOLD_DOWNGRADE
    return None


# ── drift_state: how an installed skill's store copy relates to lock+tap ───
IN_SYNC = "in-sync"
LOCAL_EDITS = "local-edits"
UPSTREAM_MOVED = "upstream-moved"
SOURCE_MISSING = "source-missing"
#: The tap's name now resolves to another repository than the lock's
#: ``tap_url`` — an outdated reason and a drift state, never an upgrade.
SOURCE_CHANGED = "source-changed"
#: The tap is configured but has no clone: `boost update` clones it.
NOT_CLONED = "not-cloned"
STORE_MISSING = "store-missing"
NA = "n/a"


def drift_state(store_sha: str | None, lock_sha: str,
                is_local: bool, source_sha: str | None,
                source_changed: bool = False,
                exec_changed: bool = False) -> str:
    """Drift of an installed skill's store copy vs its lock entry and tap.

    Signals (all pre-computed by the caller):

    * ``store_sha``  — ``sha256`` of the on-disk store dir, or ``None`` if the
      store dir is missing.
    * ``lock_sha``   — the ``sha256`` recorded in the lock entry.
    * ``is_local``   — ``True`` for local imports (no tap source to compare).
    * ``source_sha`` — ``sha256`` of the tap source dir, or ``None`` if it is
      unavailable (only consulted once the store copy matches the lock and the
      skill has a tap).
    * ``source_changed`` — the configured tap is no longer the repository the
      lock recorded (:func:`registry.source_changed`), so its copy is not
      this skill's upstream at all.
    * ``exec_changed`` — the source's exec bits differ from the copy's, which
      the content hash cannot see.

    The ordering is significant and matches the historical ``_drift_status``:
    a missing store beats local edits, which beat the local/upstream split.
    """
    if store_sha is None:
        return STORE_MISSING
    if store_sha != lock_sha:
        return LOCAL_EDITS
    if is_local:
        return NA
    if source_changed:
        return SOURCE_CHANGED
    if source_sha is None:
        return SOURCE_MISSING
    return (IN_SYNC if source_sha == lock_sha and not exec_changed
            else UPSTREAM_MOVED)


# ── outdated_footer: the one-line summary `cmd_outdated` prints ────────────

#: The exact "latest" value `cmd_outdated` uses for a row whose tap source is
#: gone (untapped, or the file/entry vanished upstream). Shared by both the
#: skill loop and the rule/workflow loop so a row is identified consistently
#: rather than by kind-specific logic, and reused here to count them.
OUTDATED_SOURCE_MISSING = "source missing"
#: The LATEST cell for a missing row whose tap is still configured: the
#: footer's own words, so the row and the summary name one state.
OUTDATED_REMOVED_UPSTREAM = "removed upstream"
#: The LATEST cell for a row whose tap name now points at another repository.
OUTDATED_SOURCE_CHANGED = "source changed"
#: The LATEST cell for a row whose tap is configured but not cloned.
OUTDATED_NOT_CLONED = "not cloned"


def removed_upstream_remedy(name: str = "", quote: bool = False) -> str:
    """What to do about an item its still-configured tap no longer ships.

    One source for the words, so `outdated`'s footer and `drift`'s hint
    cannot drift apart: `boost update` restores nothing here (it answers
    "no longer in tap — leaving as-is"), so neither may suggest it.
    """
    cmd = "boost uninstall %s" % name if name else "boost uninstall"
    return "%s, or keep as-is" % ("`%s`" % cmd if quote else cmd)


def kind_changed_message(label: str, name: str, tap: str,
                         kinds: Iterable[str]) -> str:
    """Why an installed skill is left alone: its tap now ships ``name`` only
    as another kind (``kinds``, e.g. a workflow).

    The skill paths used to match the name across every kind, so a skill that
    became a same-named workflow upstream had the *workflow* installed beside
    it and "upgraded" reported for a skill nobody touched — on every run. The
    switch is the user's to make, so this names it rather than doing it.
    """
    now = " or ".join(sorted(set(kinds)))
    return ("%s is no longer shipped as a skill by tap %s (it is now a %s) — "
            "leaving as-is; `boost uninstall %s --kind skill`, then `boost "
            "install %s:%s`, switches to it" % (label, tap, now, name, tap, name))


def outdated_footer(total: int, source_missing: int, removed: int = 0,
                    source_changed: int = 0, not_cloned: int = 0) -> str:
    """Summary line for `boost outdated`, worded so it never promises
    `boost update` can fix a row whose source is gone.

    ``source_missing`` counts rows carrying ``OUTDATED_SOURCE_MISSING`` as
    their "latest" value. ``removed`` is the subset of those whose tap is
    still configured — the item was dropped upstream — and re-tapping would
    restore nothing, so only the rest are told to re-tap. Every such row used
    to read as a deleted tap, while `boost taps` showed it present.

    ``source_changed`` and ``not_cloned`` count rows `boost update` will not
    upgrade either: one names another repository than the install came from,
    the other has no clone to compare against (`boost update` clones it).
    """
    held = source_changed + not_cloned
    if source_missing == held == 0:
        return ("%d outdated · `boost update` upgrades "
                "(pinned and quarantined items stay put)" % total)
    updatable = total - source_missing - held
    untapped = source_missing - removed
    if held == 0 and updatable == removed == 0:
        return ("%d outdated · source missing — `boost update` can't "
                "restore a deleted tap; re-tap or `boost uninstall`" % total)
    if held == 0 and updatable == untapped == 0:
        them, copies = (("them", "these copies") if total > 1
                        else ("it", "this copy"))
        return ("%d outdated · %s — `boost update` can't bring %s back; "
                "`boost uninstall` %s, or keep %s as-is"
                % (total, OUTDATED_REMOVED_UPSTREAM, them, them, copies))
    parts = ["%d outdated" % total]
    if updatable:
        parts.append("%d upstream (`boost update` upgrades, pinned and "
                     "quarantined items stay put)" % updatable)
    if untapped:
        parts.append("%d source missing (re-tap or `boost uninstall`)"
                     % untapped)
    if removed:
        parts.append("%d removed upstream (%s)"
                     % (removed, removed_upstream_remedy(quote=True)))
    if source_changed:
        parts.append("%d source changed (the tap now points at another "
                     "repo; `boost reinstall` takes its copy)" % source_changed)
    if not_cloned:
        parts.append("%d not cloned (`boost update` clones the tap)"
                     % not_cloned)
    return " · ".join(parts)
