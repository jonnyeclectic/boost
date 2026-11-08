# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for core.resolve — the skill dependency resolver.

Mutation-gated: assertions pin install order (deps-first), the requested-root
carve-out, cycle safety, dedup, conflict detection, and unresolved handling.
The resolver is pure and dependency-injected, so a small in-test graph exercises
every branch with no catalog or filesystem.
"""
from boost_cli.core import prereq, resolve


def _graph(deps):
    """A requires_of over an adjacency dict; unknown names -> []."""
    return lambda n: deps.get(n, [])


class TestResolveOrder:
    def test_single_skill_no_deps(self):
        r = resolve.resolve(["a"], _graph({}))
        assert r.order == ["a"]
        assert r.added == []

    def test_dep_installed_before_dependent(self):
        # a requires b -> b must come first
        r = resolve.resolve(["a"], _graph({"a": ["b"]}))
        assert r.order == ["b", "a"]
        assert r.added == ["b"]

    def test_transitive_chain_is_deep_first(self):
        r = resolve.resolve(["a"], _graph({"a": ["b"], "b": ["c"]}))
        assert r.order == ["c", "b", "a"]
        assert r.added == ["c", "b"]

    def test_diamond_dep_appears_once(self):
        # a->b,c ; b->d ; c->d — d installed once, before b and c
        r = resolve.resolve(["a"], _graph({"a": ["b", "c"], "b": ["d"], "c": ["d"]}))
        assert r.order.index("d") < r.order.index("b")
        assert r.order.index("d") < r.order.index("c")
        assert r.order.index("b") < r.order.index("a")
        assert r.order.count("d") == 1
        assert r.order[-1] == "a"

    def test_multiple_roots_share_a_dep(self):
        r = resolve.resolve(["a", "b"], _graph({"a": ["c"], "b": ["c"]}))
        assert r.order.count("c") == 1
        assert r.order.index("c") < r.order.index("a")
        assert r.order.index("c") < r.order.index("b")

    def test_roots_deduped_preserving_order(self):
        r = resolve.resolve(["a", "a", "b"], _graph({}))
        assert r.order == ["a", "b"]


class TestInstalledSkipping:
    def test_installed_dependency_is_not_readded(self):
        # b already installed -> pulled-in dep is skipped, a still installs
        r = resolve.resolve(["a"], _graph({"a": ["b"]}),
                            installed=frozenset({"b"}))
        assert r.order == ["a"]
        assert r.added == []

    def test_requested_root_kept_even_if_installed(self):
        # explicitly naming an installed skill still installs it (reinstall)
        r = resolve.resolve(["a"], _graph({}), installed=frozenset({"a"}))
        assert r.order == ["a"]

    def test_installed_dep_still_traversed_for_deeper_missing(self):
        # b installed but its dep c is NOT -> c must not be pulled in, because an
        # installed skill's own deps were satisfied when it was installed
        r = resolve.resolve(["a"], _graph({"a": ["b"], "b": ["c"]}),
                            installed=frozenset({"b"}))
        assert "c" not in r.order       # b's subtree is considered satisfied
        assert r.order == ["a"]


class TestCycles:
    def test_direct_cycle_terminates(self):
        r = resolve.resolve(["a"], _graph({"a": ["b"], "b": ["a"]}))
        # both appear once, no infinite loop; some order that installs both
        assert sorted(r.order) == ["a", "b"]

    def test_self_require_is_noop(self):
        r = resolve.resolve(["a"], _graph({"a": ["a"]}))
        assert r.order == ["a"]

    def test_self_require_alongside_real_dep_keeps_the_dep(self):
        # a requires [a, b] — the self-entry is skipped but must NOT abort the
        # loop, so b is still pulled in. (Pins `continue`, not `break`.)
        r = resolve.resolve(["a"], _graph({"a": ["a", "b"]}))
        assert r.order == ["b", "a"]

    def test_three_node_cycle_terminates(self):
        r = resolve.resolve(["a"], _graph({"a": ["b"], "b": ["c"], "c": ["a"]}))
        assert sorted(r.order) == ["a", "b", "c"]


class TestUnresolved:
    def test_unknown_dep_recorded_not_installed(self):
        r = resolve.resolve(["a"], _graph({"a": ["ghost"]}),
                            known=lambda n: n != "ghost")
        assert r.order == ["a"]          # a still installs
        assert r.unresolved == ["ghost"]  # ghost flagged, not added
        assert "ghost" not in r.order

    def test_known_default_treats_all_as_resolvable(self):
        r = resolve.resolve(["a"], _graph({"a": ["b"]}))
        assert r.unresolved == []
        assert "b" in r.order

    def test_unresolved_deduped(self):
        r = resolve.resolve(["a", "b"], _graph({"a": ["x"], "b": ["x"]}),
                            known=lambda n: n in ("a", "b"))
        assert r.unresolved == ["x"]

    def test_unknown_dep_does_not_skip_a_later_known_dep(self):
        # a requires [ghost, b]; ghost is unknown -> recorded, but b (listed
        # after it) must still be pulled in. (Pins `continue`, not `break`.)
        r = resolve.resolve(["a"], _graph({"a": ["ghost", "b"]}),
                            known=lambda n: n != "ghost")
        assert r.unresolved == ["ghost"]
        assert r.order == ["b", "a"]


class TestConflicts:
    def test_conflict_against_installed(self):
        r = resolve.resolve(["a"], _graph({}),
                            conflicts_of=lambda n: ["b"] if n == "a" else [],
                            installed=frozenset({"b"}))
        assert ("a", "b") in r.conflicts

    def test_conflict_between_two_being_installed(self):
        # a requires b; a conflicts with b -> flagged even though both are new
        r = resolve.resolve(["a"], _graph({"a": ["b"]}),
                            conflicts_of=lambda n: ["b"] if n == "a" else [])
        assert ("a", "b") in r.conflicts

    def test_no_conflict_when_target_absent(self):
        r = resolve.resolve(["a"], _graph({}),
                            conflicts_of=lambda n: ["z"] if n == "a" else [])
        assert r.conflicts == []

    def test_self_conflict_ignored(self):
        r = resolve.resolve(["a"], _graph({}),
                            conflicts_of=lambda n: ["a"])
        assert r.conflicts == []

    def test_self_conflict_does_not_skip_a_real_conflict(self):
        # a's conflict list is [a, b]: the self-entry is skipped but must not
        # abort the scan, so the real conflict with installed b still fires.
        # (Pins `continue`, not `break`.)
        r = resolve.resolve(["a"], _graph({}),
                            conflicts_of=lambda n: ["a", "b"] if n == "a" else [],
                            installed=frozenset({"b"}))
        assert ("a", "b") in r.conflicts

    def test_conflict_pair_deduped(self):
        r = resolve.resolve(["a"], _graph({"a": ["b"]}),
                            conflicts_of=lambda n: ["b", "b"] if n == "a" else [])
        assert r.conflicts == [("a", "b")]

    def test_an_installed_items_declaration_counts_against_the_plan(self):
        # The declaration was read only off the plan, so installing cowboy
        # beside an installed tdd that declares `conflicts: [cowboy]` said
        # nothing, while the opposite order warned.
        r = resolve.resolve(["cowboy"], _graph({}),
                            conflicts_of=lambda n: ["cowboy"] if n == "tdd"
                            else [],
                            installed=frozenset({"tdd"}))
        assert r.conflicts == [("tdd", "cowboy")]

    def test_both_install_orders_report_the_one_pair(self):
        def decl(n):
            return ["cowboy"] if n == "tdd" else []
        first = resolve.resolve(["tdd"], _graph({}), conflicts_of=decl,
                                installed=frozenset({"cowboy"}))
        second = resolve.resolve(["cowboy"], _graph({}), conflicts_of=decl,
                                 installed=frozenset({"tdd"}))
        assert first.conflicts == second.conflicts == [("tdd", "cowboy")]

    def test_a_dependency_pulled_in_is_checked_too(self):
        r = resolve.resolve(["a"], _graph({"a": ["b"]}),
                            conflicts_of=lambda n: ["b"] if n == "x" else [],
                            installed=frozenset({"x"}))
        assert r.conflicts == [("x", "b")]

    def test_two_installed_items_clashing_are_not_this_installs_news(self):
        # `boost conflict` reports a clash already on disk; an install that
        # touches neither side has nothing to add to it.
        r = resolve.resolve(["a"], _graph({}),
                            conflicts_of=lambda n: ["z"] if n == "x" else [],
                            installed=frozenset({"x", "z"}))
        assert r.conflicts == []

    def test_an_installed_root_is_read_once(self):
        # A reinstall is in the plan, so the forward scan already read it.
        calls = []

        def decl(n):
            calls.append(n)
            return ["b"] if n == "a" else []
        r = resolve.resolve(["a", "b"], _graph({}), conflicts_of=decl,
                            installed=frozenset({"a"}))
        assert r.conflicts == [("a", "b")]
        assert sorted(calls) == ["a", "b"]

    def test_installed_declarations_are_read_in_name_order(self):
        installed = prereq.InstalledSet({"y": [""], "x": [""]})
        r = resolve.resolve(["p"], _graph({}),
                            conflicts_of=lambda n: ["p"] if n != "p" else [],
                            installed=installed)
        assert r.conflicts == [("x", "p"), ("y", "p")]

    def test_a_mutual_conflict_is_reported_from_both_sides(self):
        r = resolve.resolve(["a"], _graph({}),
                            conflicts_of=lambda n: {"a": ["b"],
                                                    "b": ["a"]}.get(n, []),
                            installed=frozenset({"b"}))
        assert r.conflicts == [("a", "b"), ("b", "a")]

    def test_no_conflicts_callable_defaults_empty(self):
        r = resolve.resolve(["a"], _graph({"a": ["b"]}))
        assert r.conflicts == []
