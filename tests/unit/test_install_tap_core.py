# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the core of ``boost install <tap>`` and ``info``'s ``tap_url``.

``registry.named`` decides whether a NAME is a tap at all, ``registry.url_for``
where an item's repository lives, and ``installplan.expand_tap`` which of a
tap's skills an install writes and why the rest are left.
"""
from __future__ import annotations

import pytest

from boost_cli.core import (
    catalog,
    installplan,
    lockfile,
    projectlock,
    registry,
    scopes,
    store,
)
from boost_cli.errors import BoostError

Tap = registry.Tap


@pytest.fixture()
def taps(monkeypatch):
    """Configure exactly the given taps: ``taps(Tap(...), ...)``."""
    def set_(*rows):
        monkeypatch.setattr(registry, "list_taps", lambda: list(rows))
    return set_


# ── registry.named ─────────────────────────────────────────────────────────

def test_named_finds_the_whole_name(taps):
    taps(Tap("obra/superpowers", "https://github.com/obra/superpowers"))
    assert registry.named("obra/superpowers").name == "obra/superpowers"


def test_named_is_case_blind(taps):
    taps(Tap("obra/superpowers", "u"))
    assert registry.named("Obra/SuperPowers").name == "obra/superpowers"


@pytest.mark.parametrize("name", ["superpowers", "obra__superpowers",
                                  "obra/super", "nobody/nothing", ""])
def test_named_ignores_the_tail_the_safe_name_and_misses(taps, name):
    taps(Tap("obra/superpowers", "u"))
    assert registry.named(name) is None


def test_named_with_no_taps_is_none(taps):
    taps()
    assert registry.named("obra/superpowers") is None


def test_named_refuses_to_pick_between_case_twins(taps):
    taps(Tap("foo/bar", "a"), Tap("FOO/BAR", "b"))
    with pytest.raises(BoostError, match="ambiguous"):
        registry.named("Foo/Bar")


def test_named_never_answers_with_a_tail_match(taps):
    taps(Tap("acme/skills", "a"), Tap("Skills", "/home/me/Skills"))
    assert registry.named("skills").name == "Skills"
    assert registry.named("Skills").name == "Skills"


def test_named_never_answers_with_a_safe_name_match(taps):
    taps(Tap("a/b", "x"), Tap("A__B", "y"))
    assert registry.named("a__b").name == "A__B"


def test_named_prefers_the_exact_spelling_of_case_twins(taps):
    taps(Tap("foo/bar", "a"), Tap("FOO/BAR", "b"))
    assert registry.named("FOO/BAR").url == "b"


# ── registry.url_for ───────────────────────────────────────────────────────

def test_url_for_prefers_the_url_the_lock_recorded(taps):
    taps(Tap("o/r", "https://now.example/o/r"))
    assert registry.url_for({"tap": "o/r", "tap_url": "https://then/o/r",
                             "source_url": "https://x"}) == "https://then/o/r"


def test_url_for_falls_back_to_the_configured_tap(taps):
    taps(Tap("a/b", "https://a/b"), Tap("o/r", "https://now/o/r"))
    assert registry.url_for({"tap": "o/r"}) == "https://now/o/r"


def test_url_for_reads_only_an_exact_tap_name(taps):
    taps(Tap("o/r", "https://now/o/r"))
    assert registry.url_for({"tap": "r"}) is None
    assert registry.url_for({"tap": "O/R"}) is None


def test_url_for_an_import_is_its_source_url(taps):
    taps(Tap("o/r", "https://now/o/r"))
    assert registry.url_for({"tap": "local",
                             "source_url": "https://gh/o/r"}) == "https://gh/o/r"


def test_url_for_a_path_import_or_unknown_tap_is_none(taps):
    taps(Tap("o/r", "https://now/o/r"))
    assert registry.url_for({"tap": "local", "source_url": ""}) is None
    assert registry.url_for({"tap": "gone/tap"}) is None
    assert registry.url_for({}) is None


def test_url_for_an_import_ignores_a_tap_named_local(taps):
    taps(Tap("local", "/home/me/c/local"))
    assert registry.url_for({"tap": "local", "source_url": "https://gh/o/r",
                             "tap_url": None}) == "https://gh/o/r"
    assert registry.url_for({"tap": "local", "source_url": ""}) is None
    # A catalog row of that tap carries no source_url key: it is the tap's.
    assert registry.url_for({"tap": "local"}) == "/home/me/c/local"


def test_url_for_a_legacy_row_from_an_earlier_tap_of_that_name(taps,
                                                                monkeypatch):
    monkeypatch.setattr(registry.gitutil, "head_commit", lambda p: "new")
    taps(Tap("reg", "/b/reg", added_at="2026-01-01T00:00:00Z"))
    old = {"tap": "reg", "installed_at": "2025-01-01T00:00:00Z",
           "commit": "old"}
    assert registry.url_for(old) is None
    assert registry.url_for(dict(old, installed_at="2026-02-01T00:00:00Z")) \
        == "/b/reg"
    assert registry.url_for(dict(old, commit="new")) == "/b/reg"


def test_url_for_skips_a_tap_row_with_no_url(taps):
    taps(Tap("o/r", ""))
    assert registry.url_for({"tap": "o/r", "source_url": "https://s"}) \
        == "https://s"


# ── installplan.tap_target / untapped_hint ─────────────────────────────────

def test_tap_target_is_the_configured_tap(taps, monkeypatch):
    taps(Tap("o/r", "u"))
    monkeypatch.setattr(catalog, "find", lambda name: [])
    assert installplan.tap_target("o/r").name == "o/r"


def test_tap_target_an_item_of_that_name_wins(taps, monkeypatch):
    taps(Tap("o/r", "u"), Tap("o/s", "v"))
    monkeypatch.setattr(catalog, "find",
                        lambda name: [{"name": name}] if name == "o/r" else [])
    assert installplan.tap_target("o/r") is None
    assert installplan.tap_target("o/s").name == "o/s"


def test_tap_target_a_qualified_name_is_never_a_tap(taps, monkeypatch):
    taps(Tap("o/r", "u"), Tap("o/r:x", "v"))
    monkeypatch.setattr(catalog, "find", lambda name: [])
    assert installplan.tap_target("o/r:x") is None


def test_tap_target_an_unknown_name_is_none(taps, monkeypatch):
    taps(Tap("o/r", "u"))
    monkeypatch.setattr(catalog, "find", lambda name: [])
    assert installplan.tap_target("o/other") is None


def test_untapped_hint_names_the_tap_step(taps, monkeypatch):
    taps()
    monkeypatch.setattr(catalog, "find", lambda name: [])
    assert installplan.untapped_hint("obra/superpowers") == (
        "if obra/superpowers is a repository, `boost tap obra/superpowers` "
        "first — then `boost install obra/superpowers` lists its skills and "
        "asks before installing them")


@pytest.mark.parametrize("name", ["plain", "a/b/c", "./x", "../x", "a/b:c",
                                  "/abs", "a/", "/b", "a b/c", "~/x"])
def test_untapped_hint_only_for_an_owner_repo_shape(taps, monkeypatch, name):
    taps()
    monkeypatch.setattr(catalog, "find", lambda name: [])
    assert installplan.untapped_hint(name) is None


def test_untapped_hint_allows_dots_dashes_underscores(taps, monkeypatch):
    taps()
    monkeypatch.setattr(catalog, "find", lambda name: [])
    assert installplan.untapped_hint("my.org/re_po-2") is not None


def test_untapped_hint_is_silent_for_a_configured_tap(taps, monkeypatch):
    taps(Tap("o/r", "u"))
    monkeypatch.setattr(catalog, "find", lambda name: [])
    assert installplan.untapped_hint("o/r") is None


def test_untapped_hint_is_silent_for_a_known_item(taps, monkeypatch):
    taps()
    monkeypatch.setattr(catalog, "find", lambda name: [{"name": name}]
                        if name == "front/test" else [])
    assert installplan.untapped_hint("front/test") is None
    assert installplan.untapped_hint("front/other") is not None


# ── installplan.expand_tap ─────────────────────────────────────────────────

def _row(name, tap="o/r", kind="skill", rel=None, desc="d"):
    return {"name": name, "tap": tap, "kind": kind, "description": desc,
            "version": "1.0.0", "meta": {}, "rel_dir": rel or "skills/" + name,
            "skill_md": (rel or "skills/" + name) + "/SKILL.md"}


@pytest.fixture()
def world(monkeypatch):
    """A catalog and empty locks; refusals all pass unless a test says so.

    ``policy`` maps a name to a refusal; ``cap`` refuses once the map the
    policy is weighed against holds that many skills besides the one asked.
    Every fake records its arguments, so a test can tell which lock was read
    and what each check was handed.
    """
    state = {"rows": [], "user": {}, "project": {}, "refuse": {},
             "policy": {}, "cap": None, "calls": [], "policy_calls": [],
             "reads": []}
    monkeypatch.setattr(catalog, "all_entries", lambda: state["rows"])

    def user():
        state["reads"].append("user")
        return state["user"]

    def project(base):
        state["reads"].append(("project", base))
        return state["project"].get(base, {})
    monkeypatch.setattr(lockfile, "installed", user)
    monkeypatch.setattr(projectlock, "installed", project)

    def check(entry, *, force=False, scope="user", base=None):
        state["calls"].append((entry["name"], force, scope, base))
        if entry["name"] in state["refuse"]:
            raise BoostError(state["refuse"][entry["name"]])
        return None
    monkeypatch.setattr(store, "check_existing", check)

    def policy(entry, installed, *, replaces=None):
        others = sorted(n for n in installed if n != entry["name"])
        state["policy_calls"].append((entry["name"], others))
        if entry["name"] in state["policy"]:
            return state["policy"][entry["name"]]
        if state["cap"] is not None and len(others) >= state["cap"]:
            return "max_skills limit (%d) reached" % state["cap"]
        return None
    monkeypatch.setattr(store, "policy_refusal", policy)
    return state


def _names(entries):
    return [e["name"] for e in entries]


def test_expand_takes_every_skill_of_the_tap_sorted(world):
    world["rows"] = [_row("b"), _row("a"), _row("z", tap="other/tap")]
    exp = installplan.expand_tap(Tap("o/r", "u"))
    assert exp.tap == "o/r"
    assert _names(exp.entries) == ["a", "b"]
    assert (exp.installed, exp.skipped, exp.other_kinds) == ([], [], {})
    assert world["calls"] == [("a", False, scopes.SCOPE_USER, None),
                              ("b", False, scopes.SCOPE_USER, None)]


def test_expand_reads_the_lock_once(world):
    world["rows"] = [_row(n) for n in "abcde"]
    installplan.expand_tap(Tap("o/r", "u"))
    assert world["reads"] == ["user"]


def test_expand_counts_rules_and_workflows_by_distinct_name(world):
    world["rows"] = [_row("a"), _row("r", kind="rule"),
                     _row("w1", kind="workflow"), _row("w1", kind="workflow"),
                     _row("w2", kind="workflow"),
                     _row("x", kind="rule", tap="other/tap")]
    exp = installplan.expand_tap(Tap("o/r", "u"))
    assert _names(exp.entries) == ["a"]
    assert exp.other_kinds == {"rule": 1, "workflow": 2}


def test_expand_a_row_with_no_kind_is_a_skill(world):
    row = _row("a")
    del row["kind"]
    world["rows"] = [row]
    assert _names(installplan.expand_tap(Tap("o/r", "u")).entries) == ["a"]


def test_expand_identical_copies_are_one_skill_the_shallowest(world):
    world["rows"] = [_row("a", rel="plugins/p/skills/a"), _row("a")]
    exp = installplan.expand_tap(Tap("o/r", "u"))
    assert [e["rel_dir"] for e in exp.entries] == ["skills/a"]
    assert exp.skipped == []


def test_expand_differing_copies_are_skipped_with_their_paths(world):
    world["rows"] = [_row("a", rel="x/a", desc="one"),
                     _row("a", rel="y/a", desc="two"), _row("b")]
    exp = installplan.expand_tap(Tap("o/r", "u"))
    assert _names(exp.entries) == ["b"]
    assert exp.skipped == [("a", "ships 2 different copies (x/a, y/a) — pick "
                            "one with `boost install o/r:a --path <dir>`")]


def test_expand_a_skill_already_installed_from_the_tap_is_installed(world):
    world["rows"] = [_row("a"), _row("b")]
    world["user"] = {"a": {"tap": "o/r", "pinned": True}}
    exp = installplan.expand_tap(Tap("o/r", "u"))
    assert exp.installed == ["a"]
    assert _names(exp.entries) == ["b"]
    assert [c[0] for c in world["calls"]] == ["b"]


def test_expand_force_sends_an_installed_skill_back_through_the_refusals(world):
    world["rows"] = [_row("a")]
    world["user"] = {"a": {"tap": "o/r"}}
    exp = installplan.expand_tap(Tap("o/r", "u"), force=True)
    assert exp.installed == []
    assert _names(exp.entries) == ["a"]
    assert world["calls"] == [("a", True, scopes.SCOPE_USER, None)]


def test_expand_a_skill_from_another_tap_is_left_to_the_refusal(world):
    world["rows"] = [_row("a"), _row("b")]
    world["user"] = {"a": {"tap": "elsewhere/tap"}}
    world["refuse"] = {"a": "a is already installed from elsewhere/tap"}
    exp = installplan.expand_tap(Tap("o/r", "u"))
    assert exp.installed == []
    assert exp.skipped == [("a", "a is already installed from elsewhere/tap")]
    assert _names(exp.entries) == ["b"]


@pytest.mark.parametrize("blocked, left", [("a", ["b", "c"]),
                                           ("b", ["a", "c"]),
                                           ("c", ["a", "b"])])
def test_expand_a_policy_refusal_skips_only_that_skill(world, blocked, left):
    world["rows"] = [_row("a"), _row("b"), _row("c")]
    world["policy"] = {blocked: "blocked by policy"}
    exp = installplan.expand_tap(Tap("o/r", "u"))
    assert exp.skipped == [(blocked, "blocked by policy")]
    assert _names(exp.entries) == left


def test_expand_weighs_the_policy_against_what_it_already_took(world):
    world["rows"] = [_row(n) for n in "abcd"]
    world["user"] = {"x": {"tap": "elsewhere/tap"}}
    world["cap"] = 2
    exp = installplan.expand_tap(Tap("o/r", "u"))
    assert _names(exp.entries) == ["a"]
    assert exp.skipped == [(n, "max_skills limit (2) reached") for n in "bcd"]
    assert world["policy_calls"][:2] == [("a", ["x"]), ("b", ["a", "x"])]


def test_expand_project_scope_reads_the_project_lock(world):
    world["rows"] = [_row("a"), _row("b")]
    world["user"] = {"b": {"tap": "o/r"}}           # user scope: not relevant
    world["project"] = {"/repo": {"a": {"tap": "o/r"}}}
    exp = installplan.expand_tap(Tap("o/r", "u"), scope=scopes.SCOPE_PROJECT,
                                 base="/repo")
    assert exp.installed == ["a"]
    assert _names(exp.entries) == ["b"]
    assert world["calls"] == [("b", False, scopes.SCOPE_PROJECT, "/repo")]
    assert world["policy_calls"] == [("b", ["a"])]
    assert world["reads"] == [("project", "/repo")]


def test_expand_project_scope_with_no_base_holds_nothing(world):
    world["rows"] = [_row("a")]
    world["user"] = {"a": {"tap": "o/r"}}
    exp = installplan.expand_tap(Tap("o/r", "u"), scope=scopes.SCOPE_PROJECT)
    assert exp.installed == []
    assert _names(exp.entries) == ["a"]
    assert world["reads"] == []


def test_expand_user_scope_ignores_a_base(world):
    world["rows"] = [_row("a")]
    world["user"] = {"a": {"tap": "o/r"}}
    world["project"] = {"/repo": {}}
    exp = installplan.expand_tap(Tap("o/r", "u"), base="/repo")
    assert exp.installed == ["a"]
    assert world["reads"] == ["user"]


def test_expand_a_tap_with_nothing_is_empty(world):
    world["rows"] = [_row("z", tap="other/tap")]
    exp = installplan.expand_tap(Tap("o/r", "u"))
    assert exp == installplan.TapExpansion("o/r", [], [], [], {})


# ── installplan.weigh ──────────────────────────────────────────────────────

def test_weigh_a_second_tap_s_copy_of_a_name_is_skipped(world):
    a, b = _row("x", tap="alpha"), _row("x", tap="beta")
    kept, skipped = installplan.weigh([a, b, _row("y", tap="beta")])
    assert _names(kept) == ["x", "y"] and kept[0]["tap"] == "alpha"
    assert skipped == [("x", "alpha's copy is already part of this install — "
                        "`boost install beta:x --force` afterwards takes this "
                        "one instead")]


def test_weigh_a_name_asked_for_by_name_wins_over_a_tap_s(world):
    tapped, asked = _row("x", tap="alpha"), _row("x", tap="beta")
    kept, skipped = installplan.weigh([tapped, asked], keep=[asked])
    assert kept == [asked]
    assert [s[0] for s in skipped] == ["x"]
    assert "beta's copy" in skipped[0][1]


def test_weigh_passes_named_entries_and_other_kinds_through(world):
    asked, rule = _row("a"), _row("r", kind="rule")
    world["refuse"] = {"a": "nope", "r": "nope"}
    kept, skipped = installplan.weigh([asked, rule], keep=[asked])
    assert kept == [asked, rule]
    assert skipped == [] and world["calls"] == []


def test_weigh_a_refused_dependency_is_dropped(world):
    dep, root = _row("dep"), _row("root")
    world["policy"] = {"dep": "policy blocks installing dep"}
    kept, skipped = installplan.weigh([dep, root], checked=[root])
    assert kept == [root]
    assert skipped == [("dep", "policy blocks installing dep")]
    assert [c[0] for c in world["calls"]] == ["dep"]


def test_weigh_checked_entries_skip_check_existing_not_policy(world):
    root = _row("a")
    world["refuse"] = {"a": "would refuse"}
    world["policy"] = {"a": "policy says no"}
    kept, skipped = installplan.weigh([root], checked=[root])
    assert kept == [] and skipped == [("a", "policy says no")]
    assert world["calls"] == []


def test_weigh_counts_the_whole_install_against_the_cap(world):
    rows = [_row("a", tap="t1"), _row("b", tap="t2"), _row("c", tap="t2")]
    world["cap"] = 2
    asked = _row("n")
    kept, skipped = installplan.weigh([asked, *rows], keep=[asked],
                                      checked=rows)
    assert _names(kept) == ["n", "a"]
    assert [s[0] for s in skipped] == ["b", "c"]
    assert world["policy_calls"][0] == ("a", ["n"])


def test_weigh_reads_the_scope_s_lock_and_passes_scope_on(world):
    world["project"] = {"/repo": {"held": {}}}
    world["cap"] = 1
    kept, skipped = installplan.weigh([_row("a")], force=True,
                                      scope=scopes.SCOPE_PROJECT, base="/repo")
    assert world["calls"] == [("a", True, scopes.SCOPE_PROJECT, "/repo")]
    assert world["policy_calls"] == [("a", ["held"])]
    assert kept == [] and skipped == [("a", "max_skills limit (1) reached")]


# ── installplan.claim_names ────────────────────────────────────────────────

def test_claim_names_first_tap_named_wins():
    a, b = _row("x", tap="alpha"), _row("x", tap="beta")
    only_b = _row("y", tap="beta")
    kept, skipped = installplan.claim_names([a, b, only_b])
    assert kept == [a, only_b]
    assert skipped == [("x", "alpha's copy is already part of this install — "
                        "`boost install beta:x --force` afterwards takes "
                        "this one instead")]


def test_claim_names_a_named_item_claims_first_even_when_listed_later():
    tapped, asked = _row("x", tap="alpha"), _row("x", tap="beta")
    kept, skipped = installplan.claim_names([tapped, asked], keep=[asked])
    assert kept == [asked]
    assert skipped[0][0] == "x" and skipped[0][1].startswith("beta's copy")


def test_claim_names_same_tap_and_other_kinds_pass():
    a1, rule_a = _row("x"), _row("x", tap="beta", kind="rule")
    kept, skipped = installplan.claim_names([a1, dict(a1), rule_a])
    assert kept == [a1, a1, rule_a] and skipped == []


def test_claim_names_two_named_items_both_pass():
    a, b = _row("x", tap="alpha"), _row("x", tap="beta")
    kept, skipped = installplan.claim_names([a, b], keep=[a, b])
    assert kept == [a, b] and skipped == []
