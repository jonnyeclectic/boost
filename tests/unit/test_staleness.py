# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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


class TestOutdatedFooter:
    def test_marker_constant_value(self):
        # pins the literal both loops in cmd_outdated key off of
        assert staleness.OUTDATED_SOURCE_MISSING == "source missing"

    def test_no_source_missing_keeps_the_original_wording(self):
        assert staleness.outdated_footer(3, 0) == (
            "3 outdated · `boost update` upgrades (pinned and quarantined items "
            "stay put)")

    def test_all_source_missing_never_mentions_update(self):
        footer = staleness.outdated_footer(2, 2)
        assert "2 outdated" in footer
        assert "source missing" in footer
        assert "boost update` upgrades" not in footer

    def test_mixed_reports_both_counts_distinctly(self):
        footer = staleness.outdated_footer(3, 1)
        assert "3 outdated" in footer
        assert "2 upstream" in footer
        assert "1 source missing" in footer

    def test_total_and_source_missing_counts_are_not_swapped(self):
        # A total/source_missing argument-order mutant would still produce a
        # plausible-looking string, so check the exact numbers land right.
        footer = staleness.outdated_footer(5, 2)
        assert "5 outdated" in footer
        assert "3 upstream" in footer
        assert "2 source missing" in footer
        assert "5 upstream" not in footer
        assert "5 source missing" not in footer


class TestOutdatedFooterRemovedUpstream:
    """A row whose tap is still configured but no longer ships the item was
    worded as a deleted tap, and told the user to re-tap — which restores
    nothing, since the tap is right there."""

    def test_all_removed_never_says_re_tap(self):
        footer = staleness.outdated_footer(1, 1, removed=1)
        assert footer == ("1 outdated · removed upstream — `boost update` "
                          "can't bring it back; `boost uninstall` it, or keep "
                          "this copy as-is")
        assert "re-tap" not in footer
        assert "deleted tap" not in footer

    def test_all_removed_speaks_in_the_plural_for_several_rows(self):
        assert staleness.outdated_footer(2, 2, removed=2) == (
            "2 outdated · removed upstream — `boost update` can't bring them "
            "back; `boost uninstall` them, or keep these copies as-is")

    def test_removed_marker_matches_the_footer_wording(self):
        # The table's LATEST cell and the footer must name the same state.
        assert staleness.OUTDATED_REMOVED_UPSTREAM == "removed upstream"
        assert staleness.OUTDATED_REMOVED_UPSTREAM in (
            staleness.outdated_footer(1, 1, removed=1))

    def test_removed_defaults_to_zero_so_old_callers_keep_their_wording(self):
        assert staleness.outdated_footer(2, 2) == staleness.outdated_footer(
            2, 2, removed=0)
        assert "deleted tap" in staleness.outdated_footer(2, 2)

    def test_untapped_and_removed_are_counted_apart(self):
        footer = staleness.outdated_footer(5, 3, removed=1)
        assert footer == ("5 outdated · 2 upstream (`boost update` upgrades, "
                          "pinned and quarantined items stay put) · 2 source "
                          "missing (re-tap "
                          "or `boost uninstall`) · 1 removed upstream "
                          "(`boost uninstall`, or keep as-is)")

    def test_no_upstream_bucket_when_every_row_is_missing(self):
        footer = staleness.outdated_footer(3, 3, removed=2)
        assert footer == ("3 outdated · 1 source missing (re-tap or `boost "
                          "uninstall`) · 2 removed upstream (`boost "
                          "uninstall`, or keep as-is)")

    def test_upstream_plus_removed_omits_the_untapped_bucket(self):
        footer = staleness.outdated_footer(2, 1, removed=1)
        assert "1 upstream" in footer
        assert "1 removed upstream" in footer
        assert "source missing" not in footer


class TestRemovedUpstreamRemedy:
    """One source for `outdated`'s footer and `drift`'s hint."""

    def test_named_and_plain_for_a_drift_hint(self):
        assert (staleness.removed_upstream_remedy("brainstorming")
                == "boost uninstall brainstorming, or keep as-is")

    def test_unnamed_and_quoted_for_the_footer(self):
        assert (staleness.removed_upstream_remedy(quote=True)
                == "`boost uninstall`, or keep as-is")

    def test_named_and_quoted(self):
        assert (staleness.removed_upstream_remedy("x", quote=True)
                == "`boost uninstall x`, or keep as-is")


class TestKindChangedMessage:
    """A skill its tap now ships only as another kind is named, not swapped."""

    def test_names_the_new_kind_and_both_steps(self):
        assert (staleness.kind_changed_message(
            "cm (project)", "cm", "t", ["workflow", "workflow"])
            == "cm (project) is no longer shipped as a skill by tap t (it is "
               "now a workflow) — leaving as-is; `boost uninstall cm --kind "
               "skill`, then `boost install t:cm`, switches to it")

    def test_several_kinds_are_sorted_and_joined(self):
        msg = staleness.kind_changed_message("cm", "cm", "t",
                                             iter(["workflow", "rule"]))
        assert "(it is now a rule or workflow)" in msg


class TestCatalogRelation:
    """`boost info`'s installed-vs-catalog decision, compared as versions."""

    def test_constant_values(self):
        assert staleness.BEHIND == "behind"
        assert staleness.AHEAD == "ahead"

    def test_newer_catalog_is_behind(self):
        assert staleness.catalog_relation("1.4.0", "1.5.0") == staleness.BEHIND

    def test_older_catalog_is_ahead_not_an_update(self):
        # The audit case: evolve --apply bumped the lock to 1.4.1 while the tap
        # still says 1.4.0. String inequality called that "update available".
        assert staleness.catalog_relation("1.4.1", "1.4.0") == staleness.AHEAD

    def test_equal_versions_have_no_relation(self):
        assert staleness.catalog_relation("1.4.0", "1.4.0") is None

    def test_equal_versions_spelled_differently_have_no_relation(self):
        # "1.4" and "1.4.0" differ as strings and are the same version.
        assert staleness.catalog_relation("1.4", "1.4.0") is None
        assert staleness.catalog_relation("1.4.0", "1.4") is None

    def test_numeric_not_lexicographic(self):
        assert staleness.catalog_relation("1.9.0", "1.10.0") == staleness.BEHIND
        assert staleness.catalog_relation("1.10.0", "1.9.0") == staleness.AHEAD

    def test_empty_catalog_version_is_no_relation(self):
        # A catalog entry that declares no version is nothing to compare, not
        # an "update available" to the empty string.
        assert staleness.catalog_relation("1.4.0", "") is None
        assert staleness.catalog_relation("0.0.0", "") is None

    def test_unknown_installed_version_is_behind_a_real_one(self):
        assert staleness.catalog_relation("?", "1.0.0") == staleness.BEHIND


class TestUpdateHold:
    """Why `boost update` must leave an installed copy alone, else None."""

    def test_constant_values(self):
        assert staleness.HOLD_LOCAL_EDITS == "local-edits"
        assert staleness.HOLD_DOWNGRADE == "downgrade"

    def test_clean_upgrade_is_not_held(self):
        assert staleness.update_hold(False, "1.0.0", "1.1.0", False, False) is None

    def test_same_version_content_refresh_is_not_held(self):
        assert staleness.update_hold(False, "1.0.0", "1.0.0", False, False) is None

    def test_local_edits_hold(self):
        assert staleness.update_hold(True, "1.0.0", "1.1.0", False, False) \
            == staleness.HOLD_LOCAL_EDITS

    def test_lower_upstream_version_holds(self):
        assert staleness.update_hold(False, "1.5.0", "1.4.0", False, False) \
            == staleness.HOLD_DOWNGRADE

    def test_local_edits_outrank_a_downgrade(self):
        # The edits are what cannot be recovered; name them first.
        assert staleness.update_hold(True, "1.5.0", "1.4.0", False, False) \
            == staleness.HOLD_LOCAL_EDITS

    def test_an_undeclared_upstream_version_is_not_a_downgrade(self):
        # No version in the catalog is no signal, not "v0.0.0".
        assert staleness.update_hold(False, "1.5.0", "", False, False) is None

    def test_discard_edits_releases_only_the_edit_hold(self):
        assert staleness.update_hold(True, "1.0.0", "1.1.0", True, False) \
            is None
        # Consenting to lose edits is not consenting to walk a version back.
        assert staleness.update_hold(True, "1.5.0", "1.4.0", True, False) \
            == staleness.HOLD_DOWNGRADE
        assert staleness.update_hold(False, "1.5.0", "1.4.0", True, False) \
            == staleness.HOLD_DOWNGRADE

    def test_allow_downgrade_releases_only_the_downgrade_hold(self):
        assert staleness.update_hold(False, "1.5.0", "1.4.0", False, True) \
            is None
        assert staleness.update_hold(True, "1.5.0", "1.4.0", False, True) \
            == staleness.HOLD_LOCAL_EDITS
        assert staleness.update_hold(True, "1.0.0", "1.1.0", False, True) \
            == staleness.HOLD_LOCAL_EDITS

    def test_both_flags_release_both_holds(self):
        assert staleness.update_hold(True, "1.5.0", "1.4.0", True, True) \
            is None


class TestSourceChangedAndNotCloned:
    """Rows `boost update` will not upgrade: the tap now names another
    repository, or has no clone at all."""

    def test_constant_values(self):
        assert staleness.SOURCE_CHANGED == "source-changed"
        assert staleness.NOT_CLONED == "not-cloned"
        assert staleness.OUTDATED_SOURCE_CHANGED == "source changed"
        assert staleness.OUTDATED_NOT_CLONED == "not cloned"

    def test_drift_source_changed_beats_the_tap_comparison(self):
        # Even a matching source sha says nothing once the tap is another repo.
        assert staleness.drift_state(
            SHA_A, SHA_A, False, SHA_A, source_changed=True
        ) == staleness.SOURCE_CHANGED
        assert staleness.drift_state(
            SHA_A, SHA_A, False, None, source_changed=True
        ) == staleness.SOURCE_CHANGED

    def test_drift_local_edits_and_store_missing_still_come_first(self):
        assert staleness.drift_state(
            SHA_B, SHA_A, False, SHA_A, source_changed=True
        ) == staleness.LOCAL_EDITS
        assert staleness.drift_state(
            None, SHA_A, False, SHA_A, source_changed=True
        ) == staleness.STORE_MISSING
        assert staleness.drift_state(
            SHA_A, SHA_A, True, None, source_changed=True) == staleness.NA

    def test_drift_defaults_to_unchanged(self):
        assert staleness.drift_state(
            SHA_A, SHA_A, False, SHA_A) == staleness.IN_SYNC

    def test_footer_all_source_changed(self):
        assert staleness.outdated_footer(1, 0, source_changed=1) == (
            "1 outdated · 1 source changed (the tap now points at another "
            "repo; `boost reinstall` takes its copy)")

    def test_footer_all_not_cloned(self):
        assert staleness.outdated_footer(2, 0, not_cloned=2) == (
            "2 outdated · 2 not cloned (`boost update` clones the tap)")

    def test_footer_never_counts_held_rows_as_upgradable(self):
        assert staleness.outdated_footer(
            5, 1, removed=0, source_changed=1, not_cloned=2) == (
            "5 outdated · 1 upstream (`boost update` upgrades, pinned and "
            "quarantined items stay put) · 1 source missing (re-tap or "
            "`boost uninstall`) · 1 source changed (the tap now points at "
            "another repo; `boost reinstall` takes its copy) · 2 not cloned "
            "(`boost update` clones the tap)")

    def test_footer_removed_upstream_alongside_not_cloned_is_itemised(self):
        # The whole-line "removed upstream" wording is only for a footer where
        # every row is removed upstream.
        assert staleness.outdated_footer(
            2, 1, removed=1, not_cloned=1) == (
            "2 outdated · 1 removed upstream (`boost uninstall`, or keep "
            "as-is) · 1 not cloned (`boost update` clones the tap)")

    def test_footer_untapped_alongside_source_changed_is_itemised(self):
        assert staleness.outdated_footer(
            2, 1, source_changed=1) == (
            "2 outdated · 1 source missing (re-tap or `boost uninstall`) · "
            "1 source changed (the tap now points at another repo; `boost "
            "reinstall` takes its copy)")
