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

from . import util

# ── upstream_reason: why a tap's copy is newer than the installed one ──────
VERSION = "version"  # the catalog advertises a higher semver
CONTENT = "content"  # the tap HEAD moved AND the source tree's bytes changed


def upstream_reason(installed_version: str, latest_version: str,
                    installed_commit: str, tap_head: str,
                    installed_sha: str, source_sha: str | None
                    ) -> str | None:
    """Why the tap's copy is newer than the installed one, else ``None``.

    Mirrors the historical order exactly: a higher advertised semver wins
    immediately; otherwise a *moved* tap HEAD **plus** a changed source tree
    counts as content drift. ``source_sha`` is ``None`` when the source tree
    could not be hashed (missing checkout) — treated as "no content signal",
    i.e. not stale on that axis.
    """
    if util.semver_gt(latest_version, installed_version):
        return VERSION
    if tap_head and tap_head != installed_commit and source_sha is not None and source_sha != installed_sha:
        return CONTENT
    return None


# ── drift_state: how an installed skill's store copy relates to lock+tap ───
IN_SYNC = "in-sync"
LOCAL_EDITS = "local-edits"
UPSTREAM_MOVED = "upstream-moved"
SOURCE_MISSING = "source-missing"
STORE_MISSING = "store-missing"
NA = "n/a"


def drift_state(store_sha: str | None, lock_sha: str,
                is_local: bool, source_sha: str | None) -> str:
    """Drift of an installed skill's store copy vs its lock entry and tap.

    Signals (all pre-computed by the caller):

    * ``store_sha``  — ``sha256`` of the on-disk store dir, or ``None`` if the
      store dir is missing.
    * ``lock_sha``   — the ``sha256`` recorded in the lock entry.
    * ``is_local``   — ``True`` for local imports (no tap source to compare).
    * ``source_sha`` — ``sha256`` of the tap source dir, or ``None`` if it is
      unavailable (only consulted once the store copy matches the lock and the
      skill has a tap).

    The ordering is significant and matches the historical ``_drift_status``:
    a missing store beats local edits, which beat the local/upstream split.
    """
    if store_sha is None:
        return STORE_MISSING
    if store_sha != lock_sha:
        return LOCAL_EDITS
    if is_local:
        return NA
    if source_sha is None:
        return SOURCE_MISSING
    return IN_SYNC if source_sha == lock_sha else UPSTREAM_MOVED
