# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/deps.py — requirement/conflict facts behind
`boost deps`.

Every function is pure, so each branch and each shape is pinned here with
assertions specific enough to kill mutants.
"""
from __future__ import annotations

from boost_cli.core import deps


class TestAsList:
    def test_none_empty_false_are_no_declaration(self):
        assert deps.as_list(None) == []
        assert deps.as_list("") == []
        assert deps.as_list(False) == []

    def test_yaml_list_strips_blanks(self):
        assert deps.as_list(["a", " b ", "", "  "]) == ["a", "b"]

    def test_comma_string_strips_blanks(self):
        assert deps.as_list("a, b ,, c") == ["a", "b", "c"]

    def test_non_string_scalar_stringified(self):
        # A malformed frontmatter value (e.g. a bare int) must not raise —
        # deps rendering is best-effort, not a schema validator.
        assert deps.as_list(42) == ["42"]


class TestRequirementAndConflictNames:
    def test_requirement_names_reads_requires_key(self):
        assert deps.requirement_names({"requires": ["a", "b"]}) == ["a", "b"]

    def test_requirement_names_none_meta(self):
        assert deps.requirement_names(None) == []

    def test_requirement_names_blind_to_mcp_mapping_hoist(self):
        # The real-world shape: `requires: {mcp: [rube]}` in an author's
        # source never survives frontmatter parsing as a mapping — the
        # parser hoists the nested `mcp:` key to top level, leaving the
        # parsed `requires` an empty string (see core/mcpdecl.py's module
        # docstring). requirement_names must read that as "no requirement",
        # not attempt to treat a string as a mapping.
        assert deps.requirement_names({"requires": "", "mcp": ["rube"]}) == []

    def test_conflict_names_reads_conflicts_key(self):
        assert deps.conflict_names({"conflicts": "x, y"}) == ["x", "y"]


class TestRequirementRow:
    def test_installed_true_false(self):
        have = {"a"}
        assert deps.requirement_row("a", have) == {
            "name": "a", "installed": True, "requires": []}
        assert deps.requirement_row("b", have) == {
            "name": "b", "installed": False, "requires": []}

    def test_nested_sub_names_become_objects(self):
        # This is the fix: a nested requirement used to be a bare string with
        # no `installed` flag, so a --json consumer could not tell an unmet
        # transitive requirement from a met one without re-deriving it.
        have = {"a"}
        row = deps.requirement_row("a", have, ["b", "c"])
        assert row == {
            "name": "a", "installed": True,
            "requires": [{"name": "b", "installed": False, "requires": []},
                         {"name": "c", "installed": False, "requires": []}]}


class TestConflictRow:
    def test_installed_true_false(self):
        have = {"x"}
        assert deps.conflict_row("x", have) == {"name": "x", "installed": True}
        assert deps.conflict_row("y", have) == {"name": "y", "installed": False}


class TestHasUnmet:
    def test_empty_rows_is_false(self):
        assert deps.has_unmet([]) is False

    def test_direct_unmet_is_true(self):
        assert deps.has_unmet([{"name": "a", "installed": False, "requires": []}]) is True

    def test_all_installed_direct_is_false(self):
        assert deps.has_unmet([{"name": "a", "installed": True, "requires": []}]) is False

    def test_transitively_unmet_counts(self):
        # The exact bug: the direct requirement is installed, but ITS
        # requirement is not. Exit code must reflect this, not just the
        # top-level names.
        rows = [{"name": "a", "installed": True, "requires": [
            {"name": "b", "installed": False, "requires": []}]}]
        assert deps.has_unmet(rows) is True

    def test_deeply_nested_installed_is_false(self):
        rows = [{"name": "a", "installed": True, "requires": [
            {"name": "b", "installed": True, "requires": []}]}]
        assert deps.has_unmet(rows) is False


class TestActiveConflicts:
    def test_no_rows_is_false(self):
        assert deps.active_conflicts([]) is False

    def test_any_installed_is_true(self):
        assert deps.active_conflicts([{"name": "a", "installed": False},
                                      {"name": "b", "installed": True}]) is True

    def test_none_installed_is_false(self):
        assert deps.active_conflicts([{"name": "a", "installed": False}]) is False


class TestUnmetNames:
    def test_flattens_and_dedupes_and_sorts(self):
        rows = [
            {"name": "z", "installed": False, "requires": [
                {"name": "a", "installed": False}]},
            {"name": "b", "installed": True, "requires": [
                {"name": "a", "installed": False}]},
        ]
        assert deps.unmet_names(rows) == ["a", "z"]

    def test_installed_rows_excluded(self):
        rows = [{"name": "a", "installed": True, "requires": []}]
        assert deps.unmet_names(rows) == []

    def test_no_requires_key_tolerated(self):
        # A conflict row (no "requires" key at all) must not raise if it
        # were ever passed here by mistake — best-effort, not schema-strict.
        assert deps.unmet_names([{"name": "a", "installed": False}]) == ["a"]
