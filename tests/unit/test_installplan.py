# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: core.installplan — the install plan `boost install` and MCP share.

Exact strings, because the point of the module is that two surfaces print the
same words: a line that drifts here drifts on both, and a test that only
checks a substring would not notice the drift it exists to stop.
"""
from __future__ import annotations

import pytest

from boost_cli.core import catalog, deps, installplan, mcp, prereq
from boost_cli.core.resolve import Resolution
from boost_cli.errors import BoostError


class TestConfusionLines:
    def test_a_cross_tap_lookalike_is_one_exact_line(self, monkeypatch):
        corpus = [{"name": "deploy", "tap": "alice/skills"},
                  {"name": "deployy", "tap": "mallory/evil"}]
        monkeypatch.setattr(catalog, "all_entries", lambda: corpus)
        assert installplan.confusion_lines([corpus[0]]) == [
            "deploy (alice/skills) closely resembles deployy (mallory/evil) "
            "— double-check you meant this one"]

    def test_at_most_three_per_entry(self, monkeypatch):
        corpus = [{"name": "deploy", "tap": "t0"}] + [
            {"name": "deploy", "tap": "t%d" % i} for i in range(1, 6)]
        monkeypatch.setattr(catalog, "all_entries", lambda: corpus)
        assert len(installplan.confusion_lines([corpus[0]])) == 3

    def test_empty_request_never_reads_the_catalog(self, monkeypatch):
        def boom():
            raise AssertionError("catalog read for an empty install")
        monkeypatch.setattr(catalog, "all_entries", boom)
        assert installplan.confusion_lines([]) == []


class TestRelList:
    @pytest.mark.parametrize("val,want", [
        (None, []), ("", []), (False, []), ({"a": 1}, []),
        (["a", " b ", ""], ["a", "b"]), ("a, b,,c", ["a", "b", "c"]),
        (7, ["7"])])
    def test_shapes(self, val, want):
        assert installplan.rel_list({"k": val}, "k") == want

    def test_missing_key(self):
        assert installplan.rel_list({}, "k") == []


class TestSkillRelations:
    def test_unknown_name_has_none(self, monkeypatch):
        monkeypatch.setattr(catalog, "find", lambda n: [])
        assert installplan.skill_relations("x", "requires") == []

    def test_requires_goes_through_the_deps_filter(self, monkeypatch):
        meta = {"requires": ["helper", "gh (GitHub CLI)"],
                "conflicts": "rival, other"}
        monkeypatch.setattr(catalog, "find", lambda n: [{"meta": meta}])
        assert installplan.skill_relations("x", "requires") == \
            deps.requirement_names(meta)
        assert installplan.skill_relations("x", "conflicts") == \
            ["rival", "other"]

    def test_entry_without_meta(self, monkeypatch):
        monkeypatch.setattr(catalog, "find", lambda n: [{}])
        assert installplan.skill_relations("x", "conflicts") == []


class TestExpandDependencies:
    def _catalog(self, monkeypatch, rows, installed=frozenset()):
        by = {r["name"]: r for r in rows}
        monkeypatch.setattr(catalog, "find",
                            lambda n: [by[n]] if n in by else [])

        def resolve_one(n):
            if n not in by or by[n].get("ambiguous"):
                raise BoostError("nope")
            return by[n]
        monkeypatch.setattr(catalog, "resolve_one", resolve_one)
        monkeypatch.setattr(prereq, "installed_names",
                            lambda pbase=None: installed)
        return by

    def test_dependencies_come_first(self, monkeypatch):
        by = self._catalog(monkeypatch, [
            {"name": "app", "meta": {"requires": ["lib"]}},
            {"name": "lib", "meta": {}}])
        ordered, res = installplan.expand_dependencies([by["app"]])
        assert [e["name"] for e in ordered] == ["lib", "app"]
        assert res.added == ["lib"]
        assert res.unresolved == []

    def test_an_installed_dependency_is_left_out(self, monkeypatch):
        by = self._catalog(monkeypatch, [
            {"name": "app", "meta": {"requires": ["lib"]}},
            {"name": "lib", "meta": {}}], installed=frozenset({"lib"}))
        ordered, res = installplan.expand_dependencies([by["app"]])
        assert [e["name"] for e in ordered] == ["app"]
        assert res.added == []

    def test_an_unresolvable_dependency_is_reported_once(self, monkeypatch):
        by = self._catalog(monkeypatch, [
            {"name": "app", "meta": {"requires": ["lib"]}},
            {"name": "lib", "meta": {}, "ambiguous": True}])
        ordered, res = installplan.expand_dependencies([by["app"]])
        assert [e["name"] for e in ordered] == ["app"]
        assert res.unresolved == ["lib"]


class TestAddedLine:
    def test_nothing_added(self):
        assert installplan.added_line(Resolution()) is None

    def test_singular_and_plural(self):
        assert installplan.added_line(Resolution(added=["a"])) == \
            "pulling in 1 dependency required by your selection: a"
        assert installplan.added_line(Resolution(added=["a", "b"])) == \
            "pulling in 2 dependencies required by your selection: a, b"


class TestDependencyWarnings:
    def test_in_no_tap(self, monkeypatch):
        monkeypatch.setattr(catalog, "find", lambda n: [])
        assert installplan.dependency_warnings(Resolution(unresolved=["x"])) \
            == ["required skill 'x' is in no tap — skipped (install it "
                "manually or `boost tap` its source)"]

    def test_several_taps_are_named_qualified(self, monkeypatch):
        rows = [{"name": "x", "tap": "t2", "content": "b"},
                {"name": "x", "tap": "t1", "content": "a"}]
        monkeypatch.setattr(catalog, "find", lambda n: rows)
        assert installplan.dependency_warnings(Resolution(unresolved=["x"])) \
            == ["required skill 'x' matches 2 catalog entries — skipped "
                "(name one of t1:x, t2:x)"]

    def test_one_tap_twice_points_at_search(self, monkeypatch):
        rows = [{"name": "x", "tap": "t", "description": "a"},
                {"name": "x", "tap": "t", "description": "b"}]
        monkeypatch.setattr(catalog, "find", lambda n: rows)
        assert installplan.dependency_warnings(Resolution(unresolved=["x"])) \
            == ["required skill 'x' matches 2 catalog entries — skipped "
                "(`boost search x` and install the one you want)"]

    def test_conflicts_follow(self):
        assert installplan.dependency_warnings(
            Resolution(conflicts=[("a", "b")])) == \
            ["a declares a conflict with b (also present)"]


def _row(*specs):
    return prereq.ItemPrereqs(
        "needy", "t", "skill",
        [deps.Unmet(s.split(":")[-1], "t", s, "skills") for s in specs])


class TestPrerequisiteLines:
    def test_nothing_unmet(self, monkeypatch):
        monkeypatch.setattr(prereq, "for_entries", lambda e, pbase=None: [])
        assert installplan.prerequisite_lines([{}]) == ([], None)

    def test_a_broken_catalog_is_silent(self, monkeypatch):
        def boom(e, pbase=None):
            raise BoostError("unreadable")
        monkeypatch.setattr(prereq, "for_entries", boom)
        assert installplan.prerequisite_lines([{}]) == ([], None)

    @pytest.mark.parametrize("would,lead", [(False, "meet"),
                                            (True, "would meet")])
    def test_exact_lines(self, monkeypatch, would, lead):
        seen = {}

        def rows(e, pbase=None):
            seen["pbase"] = pbase
            return [_row("a", "b")]
        monkeypatch.setattr(prereq, "for_entries", rows)
        assert installplan.prerequisite_lines([{}], pbase="P", would=would) \
            == (["needy declares 2 prerequisites boost cannot see installed: "
                 "a (t), b (t)"],
                "%s them with: boost install a b" % lead)
        assert seen["pbase"] == "P"

    def test_singular(self, monkeypatch):
        monkeypatch.setattr(prereq, "for_entries",
                            lambda e, pbase=None: [_row("a")])
        assert installplan.prerequisite_lines([{}])[0] == [
            "needy declares 1 prerequisite boost cannot see installed: a (t)"]


class TestSummaryLine:
    def test_empty(self):
        assert prereq.summary_line([]) == ""

    def test_one_item_one_prerequisite(self):
        assert prereq.summary_line([_row("a")]) == (
            "1 installed item declares 1 prerequisite not installed (a) — "
            "`boost install a`")

    def test_truncated_names_whole_hint(self):
        rows = [_row("a", "b", "c"), _row("d", "e", "f")]
        assert prereq.summary_line(rows) == (
            "2 installed items declare 6 prerequisites not installed "
            "(a, b, c, d, e, …) — `boost install a b c d e f`")

    def test_exactly_five_is_not_truncated(self):
        assert prereq.summary_line([_row("a", "b", "c", "d", "e")]) == (
            "1 installed item declares 5 prerequisites not installed "
            "(a, b, c, d, e) — `boost install a b c d e`")


class TestStrArg:
    def test_absent_is_none(self):
        assert mcp.str_arg({}, "name") is None

    def test_a_string_passes_through(self):
        assert mcp.str_arg({"name": ""}, "name") == ""
        assert mcp.str_arg({"name": "x"}, "name") == "x"

    @pytest.mark.parametrize("val,label", [
        (None, "null"), ([], "list"), (1.5, "float"), (True, "bool"),
        ({}, "dict")])
    def test_anything_else_is_refused(self, val, label):
        with pytest.raises(BoostError) as e:
            mcp.str_arg({"q": val}, "q")
        assert e.value.message == \
            'invalid argument: "q" must be a string, got %s' % label


class TestHitLinePath:
    def test_path_is_appended(self):
        assert mcp.hit_line({"name": "n", "description": "d", "tap": "t"},
                            path="a/n") == "n — d (t) [path: a/n]"

    def test_no_path_no_marker(self):
        assert mcp.hit_line({"name": "n", "description": "d", "tap": "t"},
                            path="") == "n — d (t)"


class TestSameTapAmbiguity:
    def test_carries_bare_name_and_sorted_paths(self, monkeypatch):
        rows = [{"name": "twin", "tap": "dup", "rel_dir": "b/twin",
                 "description": "two"},
                {"name": "twin", "tap": "dup", "rel_dir": "a/twin",
                 "description": "one"}]
        monkeypatch.setattr(catalog, "find", lambda n: rows)
        with pytest.raises(catalog.SameTapAmbiguity) as e:
            catalog.resolve_one("dup:twin")
        assert e.value.bare == "twin"
        assert e.value.paths == ["a/twin", "b/twin"]
        assert e.value.message == ("'twin' matches 2 different skills in "
                                   "dup: a/twin, b/twin")
        assert e.value.hint == (
            "that registry ships one name twice — install one with `boost "
            "install twin --path <one of the above>`, then retry; raise it "
            "with the tap")
