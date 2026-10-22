# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: core.installplan — the install plan `boost install` and MCP share.

Exact strings, because the point of the module is that two surfaces print the
same words: a line that drifts here drifts on both, and a test that only
checks a substring would not notice the drift it exists to stop.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import (
    catalog,
    config,
    deps,
    installplan,
    lockfile,
    mcp,
    paths,
    prereq,
    registry,
)
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
                            lambda n, tap=None: [by[n]] if n in by else [])

        def resolve_one(n):
            if n not in by or by[n].get("ambiguous"):
                raise BoostError("nope")
            return by[n]
        monkeypatch.setattr(catalog, "resolve_one", resolve_one)
        monkeypatch.setattr(
            prereq, "installed_set",
            lambda pbase=None, also=(): prereq.InstalledSet(
                {n: {""} for n in [*installed, *also]}))
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
        # Never announced as pulled in: the plan does not install it.
        assert res.added == []


class TestEntryRelations:
    def test_reads_the_entry_given_not_a_namesake(self):
        meta = {"requires": ["helper"], "conflicts": "rival, other"}
        assert installplan.entry_relations({"meta": meta}, "requires") == \
            ["helper"]
        assert installplan.entry_relations({"meta": meta}, "conflicts") == \
            ["rival", "other"]
        assert installplan.entry_relations({}, "requires") == []


def _entry(name, tap, desc="", meta=None):
    return {"name": name, "description": desc, "version": "1.0.0", "tap": tap,
            "rel_dir": name, "skill_md": name + "/SKILL.md",
            "meta": meta or {}, "content": "%s/%s/%s" % (tap, name, desc)}


def _fake_taps(*specs):
    """Configured taps with pre-baked caches and no clone."""
    paths.ensure_dirs()
    cfg = config.load()
    cfg["taps"] = [{"name": n, "url": "https://example.test/" + n}
                   for n, _ in specs]
    config.save(cfg)
    for n, rows in specs:
        registry.Tap(name=n, url="").cache_file.write_text(
            json.dumps({"skills": rows}), encoding="utf-8")


class TestExpandDependenciesAcrossTaps:
    """`install beta:x` walked alpha's `requires:` — `skill_relations(n)`
    read `catalog.find(n)[0]`, whichever tap sorted first."""

    def _taps(self, sandbox):
        a = _entry("jira", "alpha", desc="a", meta={"requires": ["commit-msg"]})
        b = _entry("jira", "beta", desc="b", meta={"requires": ["node-tips"]})
        _fake_taps(("alpha", [a, _entry("commit-msg", "alpha", desc="c")]),
                   ("beta", [b, _entry("commit-msg", "beta", desc="d"),
                             _entry("node-tips", "beta", desc="n",
                                    meta={"requires": ["deep"]}),
                             _entry("deep", "beta", desc="deep")]))

    def test_the_chosen_tap_s_requires_are_planned(self, sandbox):
        self._taps(sandbox)
        root = catalog.resolve_one("beta:jira")
        ordered, res = installplan.expand_dependencies([root])
        assert [(e["name"], e["tap"]) for e in ordered] == [
            ("deep", "beta"), ("node-tips", "beta"), ("jira", "beta")]
        assert res.added == ["deep", "node-tips"]
        assert res.unresolved == []

    def test_the_other_tap_s_root_keeps_its_own(self, sandbox):
        self._taps(sandbox)
        root = catalog.resolve_one("alpha:jira")
        ordered, res = installplan.expand_dependencies([root])
        # commit-msg is in both taps and differs: the declaring tap's copy,
        # as the prerequisite line resolves it — and named qualified, since
        # the bare name is one `boost install` refuses.
        assert [(e["name"], e["tap"]) for e in ordered] == [
            ("commit-msg", "alpha"), ("jira", "alpha")]
        assert res.added == ["alpha:commit-msg"]
        assert res.unresolved == []


class TestSameTapFirst:
    """`pick_dependency` resolves as the prerequisite line does."""

    def _taps(self):
        _fake_taps(
            ("alpha", [_entry("lib", "alpha", meta={"requires": ["newdep"]}),
                       _entry("newdep", "alpha", desc="a"),
                       _entry("base", "alpha", desc="base"),
                       _entry("qual", "alpha",
                              meta={"requires": ["alpha:base"]})]),
            ("beta", [_entry("newdep", "beta", desc="b"),
                      _entry("solo", "beta", desc="s")]),
            ("gamma", [_entry("twin", "gamma", desc="one"),
                       dict(_entry("twin", "gamma", desc="two"),
                            rel_dir="x/twin", skill_md="x/twin/SKILL.md")]))

    def test_the_declaring_tap_wins(self, sandbox):
        self._taps()
        assert installplan.pick_dependency("newdep", "alpha")["tap"] == \
            "alpha"
        assert installplan.pick_dependency("newdep", "beta")["tap"] == "beta"

    def test_no_declaring_tap_refuses_the_cross_tap_guess(self, sandbox):
        self._taps()
        assert installplan.pick_dependency("newdep") is None
        assert installplan.pick_dependency("newdep", "") is None

    def test_another_tap_s_unique_copy_is_taken(self, sandbox):
        self._taps()
        assert installplan.pick_dependency("solo", "alpha")["tap"] == "beta"

    def test_a_qualifier_beats_the_declaring_tap(self, sandbox):
        self._taps()
        assert installplan.pick_dependency("beta:newdep", "alpha")["tap"] == \
            "beta"

    def test_two_copies_in_the_declaring_tap_stay_unresolved(self, sandbox):
        self._taps()
        assert installplan.pick_dependency("twin", "gamma") is None

    def test_nothing_anywhere_is_none(self, sandbox):
        self._taps()
        assert installplan.pick_dependency("nowhere", "alpha") is None

    def test_labels_qualify_only_the_ambiguous(self, sandbox):
        self._taps()
        assert installplan.dependency_label(
            catalog.resolve_one("alpha:newdep")) == "alpha:newdep"
        assert installplan.dependency_label(
            catalog.resolve_one("solo")) == "solo"

    def test_install_spec(self, sandbox):
        self._taps()
        assert installplan.install_spec("newdep", "beta") == "beta:newdep"
        assert installplan.install_spec("alpha:base") == "base"
        assert installplan.install_spec("newdep") == "newdep"
        assert installplan.install_spec("nowhere", "alpha") == "nowhere"

    def test_the_closure_resolves_in_the_declaring_tap(self, sandbox):
        self._taps()
        ordered, res = installplan.expand_dependencies(
            [catalog.resolve_one("lib")])
        assert [(e["name"], e["tap"]) for e in ordered] == [
            ("newdep", "alpha"), ("lib", "alpha")]
        assert res.added == ["alpha:newdep"]
        assert res.unresolved == []

    def test_a_root_and_its_qualified_spelling_install_once(self, sandbox):
        self._taps()
        roots = [catalog.resolve_one("qual"), catalog.resolve_one("base")]
        ordered, res = installplan.expand_dependencies(roots)
        assert [e["name"] for e in ordered] == ["base", "qual"]
        assert res.added == []

    def test_a_met_qualified_requirement_is_not_replanned(self, sandbox):
        self._taps()
        lockfile.set_skill("base", {"tap": "alpha", "version": "1.0.0"})
        ordered, res = installplan.expand_dependencies(
            [catalog.resolve_one("qual")])
        assert [e["name"] for e in ordered] == ["qual"]
        assert (res.added, res.unresolved) == ([], [])

    def test_installed_from_another_tap_is_not_met(self, sandbox):
        self._taps()
        lockfile.set_skill("base", {"tap": "beta", "version": "1.0.0"})
        ordered, _res = installplan.expand_dependencies(
            [catalog.resolve_one("qual")])
        assert [(e["name"], e["tap"]) for e in ordered] == [
            ("base", "alpha"), ("qual", "alpha")]

    def test_an_installed_name_no_tap_carries_is_met_not_absent(self, sandbox):
        _fake_taps(("alpha", [_entry("app", "alpha",
                                     meta={"requires": ["gone"]})]))
        lockfile.set_skill("gone", {"tap": "dropped", "version": "1.0.0"})
        ordered, res = installplan.expand_dependencies(
            [catalog.resolve_one("app")])
        assert [e["name"] for e in ordered] == ["app"]
        assert res.unresolved == []


class TestMissingDependencies:
    def test_the_roots_are_left_to_the_caller(self, sandbox):
        _fake_taps(("t", [_entry("app", "t", meta={"requires": ["lib"]}),
                          _entry("lib", "t", meta={"requires": ["base"]}),
                          _entry("base", "t")]))
        app = catalog.resolve_one("app")
        pulled, res = installplan.missing_dependencies([app])
        assert [e["name"] for e in pulled] == ["base", "lib"]
        assert res.added == ["base", "lib"]

    def test_also_installed_counts_as_present(self, sandbox):
        _fake_taps(("t", [_entry("app", "t", meta={"requires": ["lib"]}),
                          _entry("lib", "t", meta={"requires": ["base"]}),
                          _entry("base", "t")]))
        pulled, res = installplan.missing_dependencies(
            [catalog.resolve_one("app")], also_installed=["base"])
        assert [e["name"] for e in pulled] == ["lib"]
        assert res.added == ["lib"]

    def test_a_project_lock_is_read_for_pbase(self, sandbox, monkeypatch):
        _fake_taps(("t", [_entry("app", "t", meta={"requires": ["lib"]}),
                          _entry("lib", "t")]))
        monkeypatch.setattr(prereq.projectlock, "installed",
                            lambda base: {"lib": {"tap": "t"}})
        pulled, _res = installplan.missing_dependencies(
            [catalog.resolve_one("app")], "/repo")
        assert pulled == []


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
        assert e.value.qualified == "dup:twin"
        assert e.value.paths == ["a/twin", "b/twin"]
        assert e.value.message == ("'twin' matches 2 different skills in "
                                   "dup: a/twin, b/twin")
        assert e.value.hint == (
            "that registry ships one name twice — install one with `boost "
            "install dup:twin --path <one of the above>`, then retry; raise "
            "it "
            "with the tap")


class TestPlan:
    """`plan` is the one install plan: `boost install`, MCP and browse."""

    def _fake(self, monkeypatch, *, confusions=(), added=(), unresolved=()):
        calls = []
        monkeypatch.setattr(installplan, "confusion_lines",
                            lambda roots: list(confusions))

        def expand(roots, pbase=None):
            calls.append(pbase)
            return ([{"name": "dep"}, *roots],
                    Resolution(order=[], added=list(added),
                               unresolved=list(unresolved)))

        monkeypatch.setattr(installplan, "expand_dependencies", expand)
        monkeypatch.setattr(catalog, "find", lambda n: [])
        monkeypatch.setattr(catalog, "distinct_candidates", lambda rows: rows)
        return calls

    def test_the_closure_and_every_note_in_print_order(self, monkeypatch):
        calls = self._fake(monkeypatch, confusions=["look-alike"],
                           added=["dep"], unresolved=["ghost"])
        p = installplan.plan([{"name": "root"}], pbase="BASE")
        assert calls == ["BASE"]
        assert p.entries == [{"name": "dep"}, {"name": "root"}]
        assert p.confusions == ["look-alike"]
        assert p.added == ("pulling in 1 dependency required by your "
                           "selection: dep")
        assert p.notes() == [
            ("warn", "look-alike"),
            ("info", "pulling in 1 dependency required by your selection: dep"),
            ("warn", "required skill 'ghost' is in no tap — skipped (install "
                     "it manually or `boost tap` its source)")]

    def test_no_deps_keeps_the_request_and_still_warns(self, monkeypatch):
        calls = self._fake(monkeypatch, confusions=["look-alike"])
        p = installplan.plan([{"name": "root"}], deps=False)
        assert calls == []
        assert p == installplan.InstallPlan([{"name": "root"}],
                                            ["look-alike"], None, [])
        assert p.notes() == [("warn", "look-alike")]

    def test_an_empty_request_plans_nothing(self, monkeypatch):
        calls = self._fake(monkeypatch)
        assert installplan.plan([]) == installplan.InstallPlan([], [], None, [])
        assert calls == []
