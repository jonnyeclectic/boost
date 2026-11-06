# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Detect typosquatted / confusable skill names (stdlib only).

The classic package-manager attack is a skill named one keystroke away from a
popular one, or a familiar name that quietly resolves to a *different*
owner/repo. These helpers measure how close two names are and flag catalog
entries that are suspiciously similar to — but not the same source as — the one
a user asked for, so a command can warn before installing a look-alike.
"""
from __future__ import annotations

import operator


def edit_distance(a: str, b: str, cap: int = 2) -> int:
    """Levenshtein distance between ``a`` and ``b``, not measured past ``cap``.

    Returns the true distance when it is ``<= cap``, otherwise ``cap + 1`` — a
    sentinel meaning "farther apart than we care about". The row-minimum
    early-exit keeps a comparison against a large catalog cheap: as soon as an
    entire DP row exceeds ``cap`` no completion can come back under it.
    """
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > cap:            # a length gap alone already exceeds cap
        return cap + 1
    if la > lb:                       # iterate over the shorter string's rows
        a, b, la, lb = b, a, lb, la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        row_min = i
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cost = 0 if ca == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if cur[j] < row_min:
                row_min = cur[j]
        if row_min > cap:
            return cap + 1
        prev = cur
    return prev[lb] if prev[lb] <= cap else cap + 1


def confusable_names(name: str, candidates, max_distance: int = 1) -> list[str]:
    """Candidate names within ``1..max_distance`` edits of ``name``.

    Case-insensitive; exact matches (distance 0) and duplicates are dropped.
    Ordered by ascending distance, then name, so the closest look-alike is
    first.
    """
    target = name.lower()
    hits = []
    seen = set()
    for cand in candidates:
        low = cand.lower()
        if low == target or low in seen:
            continue
        d = edit_distance(target, low, max_distance)
        if 1 <= d <= max_distance:
            hits.append((d, cand))
            seen.add(low)
    hits.sort(key=operator.itemgetter(0, 1))
    return [c for _d, c in hits]


def _variants(name: str) -> set[str]:
    """``name`` and every string one character deletion away from it."""
    return {name} | {name[:i] + name[i + 1:] for i in range(len(name))}


def build_index(entries) -> dict[str, list[int]]:
    """Deletion-variant index over ``entries`` for :func:`find_confusions`.

    Maps each lowercased name, and each of its one-character deletions, to the
    positions in ``entries`` carrying it, ascending. Two names within one edit
    always share a variant — equal, one substitution (delete the same
    position from both), or one insertion (the shorter is a deletion of the
    longer) — so a lookup is a handful of dict hits instead of an
    ``edit_distance`` against every entry: ~60 ms per target over a 63k
    catalogue. Sharing a variant is not sufficient (``ab``/``ba`` share ``a``
    and are two edits apart), so candidates are still confirmed.
    """
    index: dict[str, list[int]] = {}
    for pos, e in enumerate(entries):
        for v in _variants(str(e.get("name", "")).lower()):
            index.setdefault(v, []).append(pos)
    return index


def find_confusions(target: dict, entries, max_distance: int = 1,
                    index: dict[str, list[int]] | None = None) -> list[dict]:
    """Catalog entries that are confusable with ``target`` but from another tap.

    Flags both the owner-confusion case (same name, *different* tap → distance
    0) and the typosquat case (name within ``max_distance`` edits, different
    tap). Entries from ``target``'s own tap are never flagged, and ``target``
    itself is excluded by identity. Sorted by ``(distance, name, tap)``.

    ``index`` is :func:`build_index` over the same ``entries`` (a list), worth
    building once when checking several targets. It only narrows which
    entries are compared, in their original order, so the answer is the one
    the full scan gives; it is ignored past one edit, which it cannot answer.
    """
    tname = str(target.get("name", "")).lower()
    ttap = target.get("tap")
    if index is not None and max_distance == 1:
        positions = sorted({pos for v in _variants(tname)
                            for pos in index.get(v, ())})
        entries = [entries[pos] for pos in positions]
    scored = []
    for e in entries:
        if e is target or e.get("tap") == ttap:
            continue
        d = edit_distance(tname, str(e.get("name", "")).lower(), max_distance)
        if d <= max_distance:
            scored.append((d, e))
    scored.sort(key=lambda t: (t[0], str(t[1].get("name")), str(t[1].get("tap"))))
    seen: set[tuple[str, object]] = set()
    deduped = []
    for _d, e in scored:
        key = (str(e.get("name", "")).lower(), e.get("tap"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)
    return deduped
