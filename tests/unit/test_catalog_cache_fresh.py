# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`catalog.cache_is_fresh` and `catalog.name_index`.

`update` and `heal` ask `cache_is_fresh` before rescanning a tap, so every way
a cache can be stale must answer False (or the CACHE_FORMAT backfill and a
moved tap stop reaching disk), and a current cache must answer True (or both
commands rescan everything and invalidate the search index on a no-op run).
"""
from __future__ import annotations

import json

from boost_cli.core import catalog, gitutil, registry, util


def _tap(boost, tapped):
    return registry.get("fixture-tap")


def _rewrite(tap, **fields):
    data = json.loads(tap.cache_file.read_text(encoding="utf-8"))
    data.update(fields)
    tap.cache_file.write_text(json.dumps(data), encoding="utf-8")
    catalog._ENTRY_CACHE.clear()


def test_a_cache_just_rebuilt_is_fresh(boost, tapped):
    tap = _tap(boost, tapped)
    catalog.rebuild_tap(tap)
    assert catalog.cache_is_fresh(tap) is True


def test_a_missing_cache_is_not_fresh(boost, tapped):
    tap = _tap(boost, tapped)
    tap.cache_file.unlink()
    assert catalog.cache_is_fresh(tap) is False


def test_a_corrupt_cache_is_not_fresh(boost, tapped):
    tap = _tap(boost, tapped)
    tap.cache_file.write_text("{not json", encoding="utf-8")
    catalog._ENTRY_CACHE.clear()
    assert catalog.cache_is_fresh(tap) is False


def test_an_older_format_is_not_fresh_even_at_head(boost, tapped):
    # The backfill path: an old-format cache at the right commit must still
    # be rescanned, or a CACHE_FORMAT bump never reaches it.
    tap = _tap(boost, tapped)
    _rewrite(tap, format=catalog.CACHE_FORMAT - 1)
    assert catalog.cache_is_fresh(tap) is False
    _rewrite(tap, format=catalog.CACHE_FORMAT)
    assert catalog.cache_is_fresh(tap) is True


def test_a_cache_scanned_at_another_commit_is_not_fresh(boost, tapped):
    tap = _tap(boost, tapped)
    _rewrite(tap, commit="0" * 40)
    assert catalog.cache_is_fresh(tap) is False


def test_an_explicit_head_is_compared_without_asking_git(boost, tapped,
                                                         monkeypatch):
    tap = _tap(boost, tapped)
    head = gitutil.head_commit(tap.path)
    calls = []
    monkeypatch.setattr(gitutil, "head_commit",
                        lambda p: calls.append(p) or head)
    assert catalog.cache_is_fresh(tap, head) is True
    assert catalog.cache_is_fresh(tap, "f" * 40) is False
    assert calls == []
    assert catalog.cache_is_fresh(tap) is True
    assert calls == [tap.path]


def test_a_star_changed_since_the_scan_is_not_fresh(boost, tapped):
    # Each entry stamps the tap's ★ at scan time; `heal` unstarring a tap
    # relies on the rescan that this answer triggers.
    tap = _tap(boost, tapped)
    assert tap.curated is False
    data = json.loads(tap.cache_file.read_text(encoding="utf-8"))
    for e in data["skills"]:
        e["curated"] = True
    tap.cache_file.write_text(json.dumps(data), encoding="utf-8")
    catalog._ENTRY_CACHE.clear()
    assert catalog.cache_is_fresh(tap) is False
    for e in data["skills"]:
        e["curated"] = False
    tap.cache_file.write_text(json.dumps(data), encoding="utf-8")
    catalog._ENTRY_CACHE.clear()
    assert catalog.cache_is_fresh(tap) is True


def test_an_empty_cache_at_head_is_fresh(boost, tapped):
    tap = _tap(boost, tapped)
    _rewrite(tap, skills=[])
    assert catalog.cache_is_fresh(tap) is True


def test_two_unknown_commits_are_not_a_match(boost, tapped):
    # A cache that recorded no commit and a HEAD git cannot resolve: equal
    # strings, but nothing proves the tree is the one that was scanned.
    tap = _tap(boost, tapped)
    _rewrite(tap, commit="")
    assert catalog.cache_is_fresh(tap, "") is False
    _rewrite(tap, commit=None)
    assert catalog.cache_is_fresh(tap, "") is False


def test_a_non_string_commit_reads_as_unknown(boost, tapped):
    tap = _tap(boost, tapped)
    _rewrite(tap, commit=12345)
    assert catalog._cache_record(tap)[2] == ""


def test_cached_tap_keeps_its_two_field_shape(boost, tapped):
    tap = _tap(boost, tapped)
    skills, current = catalog._cached_tap(tap)
    assert current is True
    assert {e["name"] for e in skills} >= {"brainstorming"}


def test_name_index_groups_in_order():
    a1 = {"name": "a", "tap": "t1"}
    b = {"name": "b", "tap": "t1"}
    a2 = {"name": "a", "tap": "t2"}
    idx = catalog.name_index([a1, b, a2])
    assert idx == {"a": [a1, a2], "b": [b]}
    assert idx["a"][0] is a1 and idx["a"][1] is a2
    assert catalog.name_index([]) == {}


def test_a_tap_whose_clone_is_gone_is_not_fresh(boost, tapped, monkeypatch):
    # No clone means no HEAD to compare against, and git must not be asked
    # about a directory that is not there.
    tap = _tap(boost, tapped)
    calls = []
    monkeypatch.setattr(gitutil, "head_commit",
                        lambda p: calls.append(p) or "x")
    util.rmtree(tap.path)            # read-only git objects on Windows
    assert tap.is_cloned is False
    assert catalog.cache_is_fresh(tap) is False
    assert calls == []


# ── stale_commit: the staleness load_tap does not repair by itself ─────────
def test_stale_commit_names_both_commits(boost, tapped):
    tap = _tap(boost, tapped)
    head = gitutil.head_commit(tap.path)
    assert catalog.stale_commit(tap) is None
    _rewrite(tap, commit="0" * 40)
    assert catalog.stale_commit(tap) == ("0" * 40, head)
    assert catalog.stale_commit(tap, head="1" * 40) == ("0" * 40, "1" * 40)
    assert catalog.stale_commit(tap, head="0" * 40) is None


def test_stale_commit_needs_both_sides_known(boost, tapped):
    # Two unknowns are not a mismatch, and neither is one: an unrecorded
    # commit (an old cache) or an unresolvable HEAD says nothing either way.
    tap = _tap(boost, tapped)
    assert catalog.stale_commit(tap, head="") is None
    _rewrite(tap, commit="")
    assert catalog.stale_commit(tap) is None
    _rewrite(tap, commit=None)
    assert catalog.stale_commit(tap) is None
    tap.cache_file.unlink()
    catalog._ENTRY_CACHE.clear()
    assert catalog.stale_commit(tap) is None


def test_stale_commit_ignores_an_old_format(boost, tapped):
    # load_tap rescans an old format on its own, so the format is not this
    # fault: the answer turns on the commit alone, whatever the format says.
    tap = _tap(boost, tapped)
    head = gitutil.head_commit(tap.path)
    _rewrite(tap, format=catalog.CACHE_FORMAT - 1)
    assert catalog.cache_is_fresh(tap) is False
    assert catalog.stale_commit(tap) is None
    _rewrite(tap, commit="0" * 40)
    assert catalog.stale_commit(tap) == ("0" * 40, head)


def test_stale_commit_hint_names_the_tap_and_heal(boost, tapped):
    tap = _tap(boost, tapped)
    assert catalog.stale_commit_hint() is None
    _rewrite(tap, commit="0" * 40)
    assert catalog.stale_commit_hint() == (
        "the catalog of fixture-tap was scanned at an older commit than its "
        "clone — `boost heal` rescans it")


def test_join_hints():
    assert catalog.join_hints(None, None) is None
    assert catalog.join_hints("", None) is None
    assert catalog.join_hints("a", None) == "a"
    assert catalog.join_hints(None, "b") == "b"
    assert catalog.join_hints("a", "b") == "a; b"
