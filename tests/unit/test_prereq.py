# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for prerequisite classification and resolution.

Every token below is a real value from the 461-registry census that decided
the key set — `dspy[mcp]` and `torch>=2.0.0` from `OmidZamani/dspy-skills` and
`Orchestra-Research/AI-Research-SKILLs`, the prose from
`Microck/ordinary-claude-skills`, `01-base-agentic.rules.md` from
`sparesparrow/cursor-rules`, `imbue:proof-of-work` from
`athola/claude-night-market`, `"rex, alex"` from `lingxling/awesome-skills-cn`,
`actions/upload-artifact@v7.0.1` from `dotnet/skills`. A classifier tuned on
invented inputs would have passed while mis-reading the corpus it exists for.
"""
from __future__ import annotations

from typing import ClassVar

import pytest

from boost_cli.core import deps, prereq


class TestClassifyToken:
    @pytest.mark.parametrize("token, name", [
        ("chromadb", "chromadb"),                       # bare, may be an item
        ("brainstorming", "brainstorming"),
        ("imbue:proof-of-work", "proof-of-work"),       # plugin-namespaced
        ("marketing-skill/skills/aeo", "aeo"),          # path-namespaced
        ("superpowers:writing-skills", "writing-skills"),
        ("npm or yarn", "npm or yarn"),                 # 3 words: still a name
    ])
    def test_item_tokens_yield_a_bare_name(self, token, name):
        assert deps.classify_token(token) == (deps.ITEM, name)

    @pytest.mark.parametrize("token", [
        "torch>=2.0.0", "dspy[mcp]", "gepa>=0.1.1,<0.2", "node >= 20.0.0",
        "autogpt-platform>=0.4.0", "transformers<5", "python>=3.8",
        "actions/upload-artifact@v7.0.1", "yt-dlp>=2025.6.30",
        "dspy!=0.3", "black~=24.0",
    ])
    def test_package_coordinates_are_not_names(self, token):
        assert deps.classify_token(token)[0] == deps.PACKAGE

    @pytest.mark.parametrize("token", [
        "GitHub CLI (gh) installed and authenticated",
        "Active Flow Nexus account (register at flow-nexus.ruv.io)",
        "ruv-swarm or claude-flow MCP server configured",
        "Repository access permissions are required.",
        "gh (GitHub CLI)",
    ])
    def test_prose_is_not_a_name(self, token):
        assert deps.classify_token(token)[0] == deps.PROSE

    @pytest.mark.parametrize("token", [
        "01-base-agentic.rules.md", "helper.PY", "setup.sh", "data.json",
        "pyproject.YAML", "notes.txt", "build.yml",
        # boost's own rule extension. `endswith(".md")` does not catch it, so
        # dropping ".mdc" from the list would silently reclassify every
        # `.mdc` path in a `dependencies:` as an installable item name.
        "01-base.rules.mdc", "cursor-rules.MDC",
    ])
    def test_file_paths_are_not_names(self, token):
        assert deps.classify_token(token)[0] == deps.FILE

    @pytest.mark.parametrize("token", [
        "torch==2.0.0", "numpy<=1.26", "dspy[mcp]", "pytest>=8",
        "black!=24.1", "ruff~=0.5", "actions/upload-artifact@v7.0.1",
    ])
    def test_every_pin_operator_is_a_package(self, token):
        # `==` and `<=` had no case, so either could be dropped from the
        # alternation and every test still passed — while `torch==2.0.0`
        # started being reported as a missing skill.
        assert deps.classify_token(token)[0] == deps.PACKAGE

    def test_the_class_names_are_the_values_callers_compare_against(self):
        # Pinned as literals, not as constants compared to themselves: every
        # other assertion in this file reads `deps.ITEM`, so mutating the
        # value is invisible to them and visible in `boost doctor --json`.
        assert (deps.ITEM, deps.PACKAGE, deps.PROSE, deps.FILE) == (
            "item", "package", "prose", "file")

    @pytest.mark.parametrize("token", [
        "https://example.test/skills/x", "http://a.b/c",
        "see docs at https://x.test",
    ])
    def test_a_url_is_never_an_item_name(self, token):
        # `://` is checked before the namespace split, or
        # `https://example.test/skills/x` would resolve to the item `x`.
        assert deps.classify_token(token)[0] == deps.PROSE

    def test_an_scp_style_git_remote_is_not_a_name_either(self):
        # No `://`, but the `@` pin rule catches it first — which class it
        # lands in does not matter, only that it never becomes `repo.git`.
        assert deps.classify_token("git@github.com:owner/repo.git")[0] != (
            deps.ITEM)

    def test_four_words_is_the_last_thing_still_a_name(self):
        # The boundary itself, both sides: skill titles run to four words
        # (`plan and solve prompting`), sentences start at five.
        assert deps.classify_token("plan and solve prompting") == (
            deps.ITEM, "plan and solve prompting")
        assert deps.classify_token("plan and solve the prompt")[0] == deps.PROSE

    def test_a_trailing_full_stop_is_a_sentence(self):
        # No item name ends in a period, and dropping this rule reads
        # `Repository access permissions are required.` as four words.
        assert deps.classify_token("read the docs.")[0] == deps.PROSE
        assert deps.classify_token("read the docs")[0] == deps.ITEM

    def test_blank_is_prose_not_an_empty_name(self):
        # An empty token must never reach a lookup as the name "".
        assert deps.classify_token("   ") == (deps.PROSE, "")
        assert deps.classify_token("") == (deps.PROSE, "")

    def test_a_namespace_with_nothing_after_it_is_not_a_name(self):
        assert deps.classify_token("imbue:")[0] == deps.PROSE

    def test_the_non_name_classes_return_the_token_unchanged(self):
        # So a caller can say what it skipped rather than a mangled fragment.
        for token in ("torch>=2.0.0", "a really long sentence about things",
                      "x.md"):
            assert deps.classify_token(token)[1] == token


class TestPrerequisiteKeySets:
    """The two key tuples, which nothing else in the tree reads."""

    def test_the_two_sets_never_overlap(self):
        # The "excluded by name" claim rests entirely on absence from
        # PREREQUISITE_KEYS, so a key added to both would be silently read.
        assert not (set(deps.PREREQUISITE_KEYS)
                    & set(deps.NON_PREREQUISITE_KEYS))

    @pytest.mark.parametrize("key", deps.NON_PREREQUISITE_KEYS)
    def test_an_excluded_key_declares_nothing(self, key):
        # Parametrized over the tuple itself, so a key that loses its spelling
        # fails here rather than quietly starting to resolve: `required: true`
        # and `tools_required: [Bash, Read]` are the two real shapes, and
        # reading either turns `Bash` into a missing skill.
        assert deps.declared_prerequisites({key: ["helper"]}) == []

    def test_the_same_value_under_a_read_key_does_resolve(self):
        # The control: `helper` is a perfectly good name, so the test above
        # is measuring the key and not the value.
        assert [p.name for p in
                deps.declared_prerequisites({"skills": ["helper"]})] == \
            ["helper"]


class TestItemNames:
    def test_it_keeps_only_the_names(self):
        assert deps.item_names(["a", "torch>=2.0", "b.md", "c"]) == ["a", "c"]

    def test_it_keeps_duplicates_for_the_caller_to_handle(self):
        assert deps.item_names(["a", "a"]) == ["a", "a"]

    def test_empty_in_empty_out(self):
        assert deps.item_names([]) == []


class TestRequirementNamesFilters:
    def test_prose_and_packages_no_longer_read_as_missing_skills(self):
        # The bug: `boost deps` rendered each of these as "✗ not installed"
        # and `boost install` warned each was "in no tap".
        meta = {"requires": ["commit-messages", "gh (GitHub CLI)", "python3",
                             "dspy>=0.34.0"]}
        assert deps.requirement_names(meta) == ["commit-messages", "python3"]

    def test_the_mcp_hoist_still_reads_as_nothing_declared(self):
        assert deps.requirement_names({"requires": "", "mcp": ["rube"]}) == []

    def test_a_qualified_name_stays_qualified(self):
        # This feeds `pkg._expand_dependencies` -> `catalog.find`, which is a
        # *resolver*: `owner/repo:x` is boost's unambiguous form and reducing
        # it to `x` hands the resolver a bare name two taps can carry, which
        # boost refuses rather than guesses. The report path splits the
        # namespace instead, and pairs the tail with `same_tap_only`.
        meta = {"requires": ["acme/skills:brainstorming"]}
        assert deps.requirement_names(meta) == ["acme/skills:brainstorming"]
        assert deps.item_names(["acme/skills:brainstorming"]) == [
            "brainstorming"]

    def test_item_tokens_filters_the_same_values_item_names_does(self):
        toks = ["commit-messages", "gh (GitHub CLI)", "torch>=2.0.0",
                "a/b:c", "x.md"]
        assert deps.item_tokens(toks) == ["commit-messages", "a/b:c"]
        assert deps.item_names(toks) == ["commit-messages", "c"]


class TestDeclaredPrerequisites:
    def test_it_reads_the_widened_key_set(self):
        # `skills:` and `dependencies:` carry 2,388 of the corpus's 2,658
        # declared values and were invisible before.
        meta = {"skills": ["a"], "dependencies": ["b"], "depends-on": "c",
                "prerequisites": ["d"], "uses": ["e"], "needs": ["f"],
                "depends_on": ["g"], "requires": ["h"]}
        assert [p.name for p in deps.declared_prerequisites(meta)] == list(
            "hbcgdeaf")  # PREREQUISITE_KEYS order, not dict order

    @pytest.mark.parametrize("key, value", [
        ("required", True),                       # argument-schema boolean
        ("required", False),
        ("required", ["task_type", "requirements"]),
        ("tools_required", ["Bash", "Read", "mcp__github__*"]),
        ("requires_tools", ["kubectl"]),
        ("requires-extras", ["faiss-cpu"]),
        ("requirements", ["anything"]),
        ("dependency", ["anything"]),
    ])
    def test_the_lookalike_keys_declare_nothing(self, key, value):
        assert deps.declared_prerequisites({key: value}) == []

    def test_a_self_reference_is_dropped(self):
        meta = {"skills": ["itself", "other"]}
        got = deps.declared_prerequisites(meta, "itself")
        assert [p.name for p in got] == ["other"]

    def test_a_namespaced_self_reference_is_dropped_too(self):
        got = deps.declared_prerequisites({"skills": ["imbue:itself"]},
                                          "itself")
        assert got == []

    def test_one_sibling_under_two_keys_is_one_prerequisite(self):
        got = deps.declared_prerequisites({"requires": ["a"], "skills": ["a"]})
        assert [(p.key, p.name) for p in got] == [("requires", "a")]

    def test_a_comma_string_is_the_other_half_of_the_convention(self):
        got = deps.declared_prerequisites({"depends-on": "rex, alex"})
        assert [p.name for p in got] == ["rex", "alex"]

    def test_a_namespaced_token_is_marked_same_tap_only(self):
        got = deps.declared_prerequisites({"skills": ["imbue:x", "y"]})
        assert [(p.name, p.same_tap_only) for p in got] == [
            ("x", True), ("y", False)]
        assert got[0].token == "imbue:x"  # noqa: S105  (a frontmatter token, not a secret)

    def test_no_meta_declares_nothing(self):
        assert deps.declared_prerequisites(None) == []
        assert deps.declared_prerequisites({}) == []


def _pre(name, *, key="skills", token=None, same_tap_only=False):
    return deps.Prerequisite(key, token or name, name, same_tap_only)


class TestUnmetPrerequisites:
    index: ClassVar[dict[str, list[str]]] = {
        "sibling": ["t1"], "elsewhere": ["t9"],
        "twin": ["t1", "t2"], "faraway": ["t7", "t8"]}

    def _unmet(self, prereqs, tap="t1", installed=()):
        return deps.unmet_prerequisites(
            prereqs, tap=tap, installed=set(installed),
            taps_for=lambda n: self.index.get(n, ()))

    def test_a_missing_sibling_is_reported_with_its_tap(self):
        got = self._unmet([_pre("sibling")])
        assert got == [deps.Unmet("sibling", "t1", "sibling", "skills")]

    def test_an_installed_prerequisite_is_not_reported(self):
        assert self._unmet([_pre("sibling")], installed=["sibling"]) == []

    def test_a_name_in_no_tap_is_dropped_silently(self):
        # 413 declared values are bare package names (`chromadb`, `torch`).
        # "required skill 'chromadb' is in no tap" is the failure mode this
        # whole feature has to stay under.
        assert self._unmet([_pre("chromadb")]) == []

    def test_a_unique_other_tap_still_resolves(self):
        assert self._unmet([_pre("elsewhere")]) == [
            deps.Unmet("elsewhere", "t9", "elsewhere", "skills")]

    def test_the_declaring_tap_wins_an_ambiguous_name(self):
        # Measured: the declaring tap also carries the name in 326 of the 422
        # ambiguous values (77%).
        assert self._unmet([_pre("twin")], tap="t2") == [
            deps.Unmet("twin", "t2", "t2:twin", "skills")]

    def test_an_ambiguous_name_the_declaring_tap_lacks_is_dropped(self):
        # boost refuses an unqualified name in two taps, and picking one for
        # the user would be guessing which registry they meant.
        assert self._unmet([_pre("faraway")]) == []

    def test_an_ambiguous_name_is_reported_qualified(self):
        # The hint has to be a command that runs.
        assert self._unmet([_pre("twin")])[0].spec == "t1:twin"

    def test_an_unambiguous_name_is_reported_bare(self):
        assert self._unmet([_pre("sibling")])[0].spec == "sibling"

    def test_a_namespaced_token_resolves_only_inside_its_own_tap(self):
        # `uses: actions/checkout` must not resolve against a registry that
        # happens to ship a skill called `checkout`.
        same_tap = _pre("elsewhere", token="ns:elsewhere",  # noqa: S106
                        same_tap_only=True)
        assert self._unmet([same_tap]) == []
        assert self._unmet([_pre("sibling", token="ns:sibling",  # noqa: S106
                                 same_tap_only=True)])[0].name == "sibling"

    def test_a_name_one_tap_ships_twice_is_dropped(self):
        # `name_index` lists one entry per candidate, so a registry carrying
        # two different skills under one name shows up as ["t1", "t1"] —
        # `boost install <name>` exits 1 on it, and a hint that exits 1 is
        # worse than no hint.
        got = deps.unmet_prerequisites(
            [_pre("homonym")], tap="t1", installed=set(),
            taps_for=lambda n: ["t1", "t1"])
        assert got == []

    def test_a_mirror_carried_by_one_tap_twice_is_still_reportable(self):
        # Contrast: `distinct_candidates` already collapsed the vendored copy,
        # so the index says ["t1"] and the name resolves.
        got = deps.unmet_prerequisites(
            [_pre("mirrored")], tap="t1", installed=set(),
            taps_for=lambda n: ["t1"])
        assert got == [deps.Unmet("mirrored", "t1", "mirrored", "skills")]

    def test_the_declaring_key_is_carried_through(self):
        assert self._unmet([_pre("sibling", key="dependencies")])[0].key == (
            "dependencies")

    def test_nothing_declared_is_nothing_unmet(self):
        assert self._unmet([]) == []


class TestNameIndex:
    def test_it_maps_a_name_to_every_tap_carrying_it(self):
        idx = prereq.name_index([
            {"name": "a", "tap": "t1"}, {"name": "a", "tap": "t2"},
            {"name": "b", "tap": "t1"}])
        assert idx == {"a": ["t1", "t2"], "b": ["t1"]}

    def test_the_taps_come_back_sorted_whatever_order_they_arrive(self):
        # Fed unsorted: the only other multi-tap case supplies t1 before t2,
        # so dropping the `sorted` changed nothing there while making the
        # `tap:name` spec `deps.unmet_prerequisites` builds depend on scan
        # order.
        idx = prereq.name_index([{"name": "a", "tap": "zeta"},
                                 {"name": "a", "tap": "alpha"},
                                 {"name": "a", "tap": "mid"}])
        assert idx == {"a": ["alpha", "mid", "zeta"]}

    def test_only_the_names_asked_for_are_indexed(self):
        # `names=` is what keeps `install` off a whole-corpus walk when the
        # thing being installed declares one prerequisite.
        rows = [{"name": "a", "tap": "t1"}, {"name": "b", "tap": "t1"}]
        assert prereq.name_index(rows, names={"a"}) == {"a": ["t1"]}
        assert prereq.name_index(rows, names=set()) == {}
        assert set(prereq.name_index(rows)) == {"a", "b"}

    def test_it_does_not_copy_or_mutate_the_entries_it_is_handed(self):
        rows = [{"name": "a", "tap": "t1"}]
        before = [dict(r) for r in rows]
        prereq.name_index(rows)
        assert rows == before

    def test_a_tap_listed_twice_collapses(self):
        idx = prereq.name_index([{"name": "a", "tap": "t1"},
                                 {"name": "a", "tap": "t1"}])
        assert idx == {"a": ["t1"]}

    def test_a_vendored_copy_is_one_candidate_not_two(self):
        # Identical rendered metadata inside one tap: `resolve_one` picks the
        # shallowest rather than asking, so the name is installable.
        idx = prereq.name_index([
            {"name": "a", "tap": "t1", "rel_dir": "skills/a"},
            {"name": "a", "tap": "t1", "rel_dir": "plugins/p/skills/a"}])
        assert idx == {"a": ["t1"]}

    def test_two_different_skills_in_one_tap_are_two_candidates(self):
        # And this is why the value is a list rather than a set of taps: the
        # repeated tap is what tells `unmet_prerequisites` to stay quiet.
        idx = prereq.name_index([
            {"name": "a", "tap": "t1", "description": "one"},
            {"name": "a", "tap": "t1", "description": "two"}])
        assert idx == {"a": ["t1", "t1"]}

    def test_a_mirror_across_taps_is_one_candidate(self):
        idx = prereq.name_index([{"name": "a", "tap": "t2", "content": "dead"},
                                 {"name": "a", "tap": "t1", "content": "dead"}])
        assert len(idx["a"]) == 1

    def test_the_default_corpus_is_the_cached_one(self, monkeypatch):
        # Never `all_entries()`: this index is built behind `install` and
        # `doctor`, and rebuilding a tap cache as a side effect of printing a
        # hint is what made `boost heal` afterwards say "nothing to heal".
        called = []
        monkeypatch.setattr(prereq.catalog, "cached_entries",
                            lambda: called.append(1) or [{"name": "a",
                                                          "tap": "t1"}])
        monkeypatch.setattr(prereq.catalog, "all_entries",
                            lambda: pytest.fail("rebuilt the cache"))
        assert prereq.name_index() == {"a": ["t1"]}
        assert called == [1]

    def test_a_nameless_row_is_skipped(self):
        assert prereq.name_index([{"tap": "t1"}, {"name": "", "tap": "t1"}]) == {}


class TestForEntries:
    index: ClassVar[dict[str, list[str]]] = {
        "helper": ["t1"], "needy": ["t1"], "other": ["t1"]}

    def _run(self, entries, installed=(), corpus=None):
        # `corpus` builds the index the way `for_entries` does in production
        # rather than handing it one, so the wiring is under test too.
        return prereq.for_entries(
            entries, installed=frozenset(installed),
            index=None if corpus is not None else self.index,
            corpus=corpus)

    def test_it_names_the_unmet_sibling(self):
        rows = self._run([{"name": "needy", "tap": "t1", "kind": "skill",
                           "meta": {"skills": ["helper"]}}])
        assert len(rows) == 1
        assert rows[0].name == "needy" and rows[0].kind == "skill"
        assert [m.name for m in rows[0].unmet] == ["helper"]

    def test_an_entry_with_nothing_missing_is_left_out(self):
        rows = self._run([{"name": "needy", "tap": "t1", "kind": "skill",
                           "meta": {"skills": ["helper"]}}],
                         installed=["helper"])
        assert rows == []

    def test_siblings_in_one_command_satisfy_each_other(self):
        # `boost install needy helper` must not report helper as missing.
        rows = self._run([
            {"name": "needy", "tap": "t1", "kind": "skill",
             "meta": {"skills": ["helper"]}},
            {"name": "helper", "tap": "t1", "kind": "skill", "meta": {}}])
        assert rows == []

    def test_no_entries_does_no_work(self, sandbox):
        # `sandbox` although the assertion needs no state: unmutated this
        # returns before touching anything, but a mutant that gets past the
        # guard reads the real ~/.boost config and lock, and mutation runs
        # happen on a developer's machine.
        assert prereq.for_entries([]) == []

    def test_nothing_declared_reads_neither_catalog_nor_lock(
            self, sandbox, monkeypatch):
        # The common case — most items declare nothing — and it used to pay
        # for a whole-corpus `name_index()` plus a lock read first.
        monkeypatch.setattr(prereq.catalog, "cached_entries",
                            lambda: pytest.fail("indexed the catalog"))
        monkeypatch.setattr(prereq.lockfile, "all_installed",
                            lambda: pytest.fail("read the lock"))
        assert prereq.for_entries(
            [{"name": "plain", "tap": "t1", "meta": {"description": "d"}}]) == []

    def test_the_declaring_tap_wins_an_ambiguous_prerequisite(self):
        # Exercised *through* `prereq`, not just `deps`: `entry.get("tap")`
        # is what carries the declaring tap in, and blanking it drops the
        # row rather than reporting it — 77% of the ambiguous values in the
        # census are resolved by this rule.
        rows = self._run(
            [{"name": "needy", "tap": "t1", "kind": "skill",
              "meta": {"skills": ["helper"]}}],
            corpus=[{"name": "helper", "tap": "t1"},
                    {"name": "helper", "tap": "t2"}])
        assert [m.spec for m in rows[0].unmet] == ["t1:helper"]

    def test_a_missing_kind_defaults_to_skill(self):
        rows = self._run([{"name": "needy", "tap": "t1",
                           "meta": {"skills": ["helper"]}}])
        assert rows[0].kind == "skill"


class TestInstalledNames:
    def test_all_three_sections_count_as_installed(self, monkeypatch):
        # A prerequisite met by an installed *rule* is met.
        monkeypatch.setattr(prereq.lockfile, "all_installed",
                            lambda: {"skill": {"a": {}}, "rule": {"b": {}},
                                     "workflow": {"c": {}}})
        assert prereq.installed_names() == frozenset({"a", "b", "c"})

    def test_no_project_base_reads_no_project_lock(self, monkeypatch):
        monkeypatch.setattr(prereq.lockfile, "all_installed",
                            lambda: {"skill": {"a": {}}})
        monkeypatch.setattr(prereq.projectlock, "installed",
                            lambda base: pytest.fail("read a project lock"))
        assert prereq.installed_names() == frozenset({"a"})

    def test_a_project_lock_is_unioned_with_the_user_one(self, monkeypatch):
        # `boost install needy --local` after `boost install helper --local`
        # records nothing in the user lock, and used to call helper missing.
        monkeypatch.setattr(prereq.lockfile, "all_installed",
                            lambda: {"skill": {"a": {}}})
        monkeypatch.setattr(prereq.projectlock, "installed",
                            lambda base: {"b": {}})
        assert prereq.installed_names("/repo") == frozenset({"a", "b"})


class TestForInstalled:
    @staticmethod
    def _wire(monkeypatch, installed, entries, seen=None):
        monkeypatch.setattr(prereq.catalog, "cached_entries", lambda: entries)
        monkeypatch.setattr(prereq.lockfile, "all_installed", lambda: installed)

        def find(name, tap=None, pool=None):
            if seen is not None:
                seen.append((name, tap))
            return [e for e in entries
                    if e["name"] == name and (tap is None or e["tap"] == tap)]

        monkeypatch.setattr(prereq.catalog, "find", find)

    def test_the_declaration_read_is_the_tap_the_lock_recorded(
            self, monkeypatch):
        # Two registries ship `needy`; only the installed one's frontmatter
        # may be read, or boost reports a prerequisite nobody declared.
        seen = []
        entries = [
            {"name": "needy", "tap": "t1", "kind": "skill",
             "meta": {"skills": ["helper"]}},
            {"name": "needy", "tap": "t2", "kind": "skill",
             "meta": {"skills": ["intruder"]}},
            {"name": "helper", "tap": "t1", "kind": "skill", "meta": {}},
            {"name": "intruder", "tap": "t2", "kind": "skill", "meta": {}}]
        self._wire(monkeypatch, {"skill": {"needy": {"tap": "t2"}}}, entries,
                   seen)
        rows = prereq.for_installed()
        assert seen == [("needy", "t2")]
        assert [m.name for m in rows[0].unmet] == ["intruder"]

    def test_the_vendored_copy_the_lock_names_is_the_one_read(
            self, monkeypatch):
        # One tap, two copies of a name in different directories, different
        # frontmatter. `matches[0]` is scan order, so the shallower copy's
        # declaration was reported for an install of the deeper one — the
        # same wrong-copy error the cross-tap guard above exists to stop.
        # `catalog.select_lock_source` is what the lock's `source_dir` is for.
        entries = [
            {"name": "dup", "tap": "t1", "kind": "skill",
             "rel_dir": "plugins/p/skills/dup", "meta": {"skills": ["alpha"]}},
            {"name": "dup", "tap": "t1", "kind": "skill",
             "rel_dir": "skills/dup", "meta": {"skills": ["beta"]}},
            {"name": "alpha", "tap": "t1", "kind": "skill", "meta": {}},
            {"name": "beta", "tap": "t1", "kind": "skill", "meta": {}}]
        self._wire(monkeypatch,
                   {"skill": {"dup": {"tap": "t1",
                                      "source_dir": "skills/dup"}}}, entries)
        rows = prereq.for_installed()
        assert [m.name for m in rows[0].unmet] == ["beta"]

    def test_an_old_lock_with_no_source_still_reports(self, monkeypatch):
        # `select_lock_source` falls back to `matches[0]` when the lock
        # cannot say which copy it was; that must stay a report, not a skip.
        entries = [{"name": "dup", "tap": "t1", "kind": "skill",
                    "rel_dir": "skills/dup", "meta": {"skills": ["alpha"]}},
                   {"name": "alpha", "tap": "t1", "kind": "skill", "meta": {}}]
        self._wire(monkeypatch, {"skill": {"dup": {"tap": "t1"}}}, entries)
        assert [m.name for m in prereq.for_installed()[0].unmet] == ["alpha"]

    def test_a_rule_and_a_skill_sharing_a_name_are_both_checked(
            self, monkeypatch):
        # Keyed by name alone, the later lock section overwrote the earlier
        # one and its declarations were never read at all.
        entries = [
            {"name": "same", "tap": "t1", "kind": "skill",
             "rel_dir": "skills/same", "meta": {"skills": ["alpha"]}},
            {"name": "same", "tap": "t1", "kind": "rule",
             "skill_md": "rules/same.mdc", "meta": {"skills": ["beta"]}},
            {"name": "alpha", "tap": "t1", "kind": "skill", "meta": {}},
            {"name": "beta", "tap": "t1", "kind": "skill", "meta": {}}]
        self._wire(monkeypatch, {
            "skill": {"same": {"tap": "t1", "source_dir": "skills/same"}},
            "rule": {"same": {"tap": "t1",
                              "source_file": "rules/same.mdc"}}}, entries)
        rows = prereq.for_installed()
        assert sorted(m.name for r in rows for m in r.unmet) == ["alpha",
                                                                 "beta"]

    def test_a_record_with_no_tap_is_skipped(self, monkeypatch):
        entries = [{"name": "needy", "tap": "t1", "kind": "skill",
                    "meta": {"skills": ["helper"]}},
                   {"name": "helper", "tap": "t1", "kind": "skill", "meta": {}}]
        self._wire(monkeypatch, {"skill": {"needy": {}}}, entries)
        assert prereq.for_installed() == []

    def test_a_non_dict_record_is_skipped_too(self, monkeypatch):
        # Lock records predating the current format are not all mappings.
        entries = [{"name": "needy", "tap": "t1", "kind": "skill",
                    "meta": {"skills": ["helper"]}},
                   {"name": "helper", "tap": "t1", "kind": "skill", "meta": {}}]
        self._wire(monkeypatch, {"skill": {"needy": "1.0.0"}}, entries)
        assert prereq.for_installed() == []

    def test_an_installed_item_whose_tap_is_gone_is_skipped(self, monkeypatch):
        self._wire(monkeypatch, {"skill": {"needy": {"tap": "vanished"}}}, [])
        assert prereq.for_installed() == []

    def test_an_installed_prerequisite_is_not_reported(self, monkeypatch):
        entries = [{"name": "needy", "tap": "t1", "kind": "skill",
                    "meta": {"skills": ["helper"]}},
                   {"name": "helper", "tap": "t1", "kind": "skill", "meta": {}}]
        self._wire(monkeypatch, {"skill": {"needy": {"tap": "t1"},
                                           "helper": {"tap": "t1"}}}, entries)
        assert prereq.for_installed() == []

    def test_the_lock_section_names_the_kind(self, monkeypatch):
        entries = [{"name": "needy", "tap": "t1",
                    "meta": {"dependencies": ["helper"]}},
                   {"name": "helper", "tap": "t1", "meta": {}}]
        self._wire(monkeypatch, {"rule": {"needy": {"tap": "t1"}}}, entries)
        assert prereq.for_installed()[0].kind == "rule"


class TestForEntriesDefaults:
    def test_it_builds_its_own_index_and_lock_read(self, monkeypatch):
        entries = [{"name": "needy", "tap": "t1", "kind": "skill",
                    "meta": {"skills": ["helper"]}},
                   {"name": "helper", "tap": "t1", "kind": "skill",
                    "meta": {}}]
        monkeypatch.setattr(prereq.catalog, "cached_entries", lambda: entries)
        monkeypatch.setattr(prereq.lockfile, "all_installed", lambda: {})
        rows = prereq.for_entries([entries[0]])
        assert [m.spec for m in rows[0].unmet] == ["helper"]

    def test_the_default_installed_set_silences_the_row(self, monkeypatch):
        entries = [{"name": "needy", "tap": "t1", "kind": "skill",
                    "meta": {"skills": ["helper"]}},
                   {"name": "helper", "tap": "t1", "kind": "skill",
                    "meta": {}}]
        monkeypatch.setattr(prereq.catalog, "cached_entries", lambda: entries)
        monkeypatch.setattr(prereq.lockfile, "all_installed",
                            lambda: {"skill": {"helper": {"tap": "t1"}}})
        assert prereq.for_entries([entries[0]]) == []


class TestInstallHint:
    def test_it_is_one_runnable_command(self):
        rows = [prereq.ItemPrereqs("a", "t1", "skill",
                                   [deps.Unmet("x", "t1", "x", "skills")]),
                prereq.ItemPrereqs("b", "t2", "skill",
                                   [deps.Unmet("y", "t2", "t2:y", "skills")])]
        assert prereq.install_hint(rows) == "boost install x t2:y"

    def test_nothing_unmet_is_no_command_at_all(self):
        # Not `"boost install "`: callers interpolate this, and a bare
        # `boost install` is a usage error rather than a fix.
        assert prereq.install_hint([]) == ""
        assert prereq.install_hint(
            [prereq.ItemPrereqs("a", "t1", "skill", [])]) == ""

    def test_one_name_wanted_twice_is_named_once(self):
        miss = deps.Unmet("x", "t1", "x", "skills")
        rows = [prereq.ItemPrereqs("a", "t1", "skill", [miss]),
                prereq.ItemPrereqs("b", "t1", "skill", [miss])]
        assert prereq.install_hint(rows) == "boost install x"
