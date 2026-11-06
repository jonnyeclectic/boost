# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/profiles.py — `profile use`'s outcome."""
from __future__ import annotations

import pytest

from boost_cli.core import profiles


class TestUseExitCode:
    @pytest.mark.parametrize(("not_found", "failed", "rc"), [
        (0, 0, 0), (1, 0, 1), (0, 1, 1), (2, 3, 1)])
    def test_any_skipped_member_is_one(self, not_found, failed, rc):
        assert profiles.use_exit_code(not_found, failed) == rc


class TestSidelineAllowed:
    def test_clean_switch_sidelines(self):
        assert profiles.sideline_allowed(2, 0, 0) is True

    def test_empty_profile_sidelines(self):
        assert profiles.sideline_allowed(0, 0, 0) is True

    def test_some_resolved_beside_a_skip_sidelines(self):
        assert profiles.sideline_allowed(1, 1, 0) is True
        assert profiles.sideline_allowed(1, 0, 1) is True

    def test_nothing_resolved_and_something_skipped_refuses(self):
        assert profiles.sideline_allowed(0, 1, 0) is False
        assert profiles.sideline_allowed(0, 0, 1) is False


class TestUseSummary:
    def test_clean_switch_has_no_warning(self):
        assert profiles.use_summary("p", 0, 0, 0) is None

    def test_changed_only_keeps_the_old_wording(self):
        assert profiles.use_summary("p", 0, 0, 1) == (
            "applied profile p, but 1 skill differs from it — compare with "
            "`boost profile diff p`")
        assert profiles.use_summary("p", 0, 0, 2) == (
            "applied profile p, but 2 skills differ from it — compare with "
            "`boost profile diff p`")

    def test_not_found(self):
        assert profiles.use_summary("p", 1, 0, 0) == (
            "applied profile p, but 1 skill not found — compare with "
            "`boost profile diff p`")

    def test_failed(self):
        assert profiles.use_summary("p", 0, 2, 0) == (
            "applied profile p, but 2 skills failed to install — compare "
            "with `boost profile diff p`")

    def test_all_three_in_order(self):
        assert profiles.use_summary("q", 2, 1, 1) == (
            "applied profile q, but 2 skills not found, 1 skill failed to "
            "install, 1 skill differs from it — compare with "
            "`boost profile diff q`")
