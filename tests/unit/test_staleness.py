# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: boost_cli/core/staleness.py — the single-source staleness/drift
decision that cmd_update, cmd_outdated and _drift_status now render.

Both functions are pure, so every branch (and the ordering between branches) is
pinned here with assertions specific enough to kill mutants.
"""
from __future__ import annotations

from boost_cli.core import staleness

SHA_A = "a" * 64
SHA_B = "b" * 64


class TestUpstreamReason:
    def test_higher_semver_is_version(self):
        assert staleness.upstream_reason(
            "1.0.0", "1.1.0", "c1", "c2", SHA_A, SHA_B) == staleness.VERSION

    def test_version_constant_value(self):
        # pins the literal so a mutated constant is caught
        assert staleness.VERSION == "version"

    def test_content_constant_value(self):
        assert staleness.CONTENT == "content"

    def test_version_wins_even_when_commit_and_content_also_differ(self):
        # semver must be checked FIRST — a higher version reports "version"
        # regardless of the (also-changed) commit/content signals.
        assert staleness.upstream_reason(
            "1.0.0", "2.0.0", "old", "new", SHA_A, SHA_B) == staleness.VERSION

    def test_same_version_no_commit_move_is_none(self):
        assert staleness.upstream_reason(
            "1.0.0", "1.0.0", "c1", "c1", SHA_A, SHA_B) is None

    def test_empty_tap_head_is_none(self):
        # no HEAD signal (e.g. tap not cloned) → not stale on the content axis
        assert staleness.upstream_reason(
            "1.0.0", "1.0.0", "c1", "", SHA_A, SHA_B) is None

    def test_moved_commit_but_source_unhashable_is_none(self):
        # source_sha None means "no content signal" — must NOT report content
        assert staleness.upstream_reason(
            "1.0.0", "1.0.0", "old", "new", SHA_A, None) is None

    def test_moved_commit_same_content_is_none(self):
        assert staleness.upstream_reason(
            "1.0.0", "1.0.0", "old", "new", SHA_A, SHA_A) is None

    def test_moved_commit_changed_content_is_content(self):
        assert staleness.upstream_reason(
            "1.0.0", "1.0.0", "old", "new", SHA_A, SHA_B) == staleness.CONTENT

    def test_lower_advertised_version_not_stale_by_version(self):
        # a downgrade in the catalog is not an upgrade — no commit move → None
        assert staleness.upstream_reason(
            "2.0.0", "1.0.0", "c1", "c1", SHA_A, SHA_B) is None


class TestDriftState:
    def test_store_missing(self):
        assert staleness.drift_state(
            None, SHA_A, False, SHA_A) == staleness.STORE_MISSING

    def test_store_missing_takes_precedence_over_local(self):
        # a missing store is reported even for a local import
        assert staleness.drift_state(
            None, SHA_A, True, None) == staleness.STORE_MISSING

    def test_local_edits(self):
        assert staleness.drift_state(
            SHA_B, SHA_A, False, SHA_A) == staleness.LOCAL_EDITS

    def test_local_edits_take_precedence_over_na(self):
        # edited store beats the local/upstream split even for local imports
        assert staleness.drift_state(
            SHA_B, SHA_A, True, None) == staleness.LOCAL_EDITS

    def test_local_import_in_sync_is_na(self):
        assert staleness.drift_state(
            SHA_A, SHA_A, True, None) == staleness.NA

    def test_source_missing(self):
        assert staleness.drift_state(
            SHA_A, SHA_A, False, None) == staleness.SOURCE_MISSING

    def test_in_sync(self):
        assert staleness.drift_state(
            SHA_A, SHA_A, False, SHA_A) == staleness.IN_SYNC

    def test_upstream_moved(self):
        assert staleness.drift_state(
            SHA_A, SHA_A, False, SHA_B) == staleness.UPSTREAM_MOVED

    def test_status_constant_values(self):
        assert staleness.IN_SYNC == "in-sync"
        assert staleness.LOCAL_EDITS == "local-edits"
        assert staleness.UPSTREAM_MOVED == "upstream-moved"
        assert staleness.SOURCE_MISSING == "source-missing"
        assert staleness.STORE_MISSING == "store-missing"
        assert staleness.NA == "n/a"
