# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""What an installed item *is*, as opposed to what its tap carries today.

The catalog is a scan of each tap's HEAD. Once `boost update --taps-only`
moves a clone, its row for an installed item describes the next version, not
the one on disk. `boost info`, `boost explain` and the MCP `boost_info` used to
print that row's description beside the lock's older version, so one reply
described two releases. This module separates the two. The installed
description comes from the installed copy (or the lock row install wrote).
The tap's text is kept only as the *upstream* description, and only when it
differs. The update check for a rule or workflow is the one `boost outdated`
makes, so `info` and `outdated` cannot disagree about whether there is one.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from ..errors import BoostError
from . import catalog, frontmatter, registry, staleness, util


def update_of(kind: str, lk: dict, tap: registry.Tap,
              matches: list[dict]) -> tuple[str | None, str | None]:
    """``(reason, latest)`` for an installed rule/workflow against ``tap``.

    ``reason`` is None when the tap's source file still hashes to the lock's
    ``sha256``, ``staleness.SOURCE_MISSING`` when the file cannot be read, and
    otherwise ``staleness.VERSION`` (the tap advertises a higher version) or
    ``staleness.CONTENT``. ``latest`` is the version of the catalog row the lock
    refers to (``matches`` filtered to this tap and kind), or None. ``tap`` must
    already be configured, cloned and the lock's own repository: the caller
    checks that first, since `boost outdated` reports each of those cases by
    name.
    """
    try:
        raw = (tap.path / lk.get("source_file", "")).read_text(
            encoding="utf-8", errors="replace")
    except OSError:
        return staleness.SOURCE_MISSING, None
    if hashlib.sha256(raw.encode("utf-8")).hexdigest() == lk.get("sha256"):
        return None, None
    entry = catalog.installed_row(matches, kind, lk)
    latest = (str(entry["version"])
              if entry and entry.get("version") else None)
    installed_v = str(lk.get("version") or "0.0.0")
    if latest and util.semver_gt(latest, installed_v):
        return staleness.VERSION, latest
    return staleness.CONTENT, latest


def installed_update(kind: str, lk: dict, matches: list[dict]
                     ) -> tuple[str | None, str | None]:
    """:func:`update_of` for a single read, which finds the tap itself.

    A tap that is not configured, not cloned or now names another repository
    returns ``(None, None)``: there is no comparable upstream to report.
    """
    tap_name = lk.get("tap")
    if not tap_name or tap_name == "local":
        return None, None
    try:
        tap = registry.get(str(tap_name))
    except BoostError:
        return None, None
    if not tap.is_cloned or registry.source_changed(lk, tap):
        return None, None
    return update_of(kind, lk, tap, matches)


def split(installed: str, upstream: str) -> tuple[str, str]:
    """``(installed, upstream)`` where upstream is empty unless it differs."""
    return installed, ("" if upstream == installed else upstream)


def skill_description(skill_dir: Path | None, cat: dict | None
                      ) -> tuple[str, str]:
    """``(installed, upstream)`` for an installed skill.

    The installed text is the store (or project) copy's own frontmatter. With
    no copy on disk the installed text is unknown, so the tap's description
    comes back only as upstream, never passed off as the installed one.
    """
    upstream = str((cat or {}).get("description") or "")
    md = skill_dir / "SKILL.md" if skill_dir is not None else None
    if md is None or not md.is_file():
        return "", upstream
    try:
        text = md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", upstream
    meta, body = frontmatter.parse(text)
    return split(catalog.describe(meta, body), upstream)


def materialized_description(lk: dict, cat: dict | None,
                             reason: str | None) -> tuple[str, str]:
    """``(installed, upstream)`` for an installed rule/workflow.

    Install records the description in the lock row. A row written before
    that has none, and then the catalog text counts as the installed one only
    while the tap's source still matches the lock (``reason`` None).
    """
    upstream = str((cat or {}).get("description") or "")
    if "description" in lk:
        return split(str(lk.get("description") or ""), upstream)
    if reason is None:
        return upstream, ""
    return "", upstream
