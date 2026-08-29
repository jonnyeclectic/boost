# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: boost_cli/core/catalog.py — scanning, tap caches, lookup, search."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from boost_cli.core import catalog, config, paths, registry
from boost_cli.errors import BoostError

FIXTURE_NAMES = ["brainstorming", "commit-messages", "cowboy-coding",
                 "jira-integration", "tdd-workflow"]


def write_skill(dirpath, fm=None, body="Some body line\n"):
    dirpath.mkdir(parents=True, exist_ok=True)
    text = (fm + "\n" if fm else "") + body
    (dirpath / "SKILL.md").write_text(text, encoding="utf-8")


def _entry(name, tap, desc="", curated=False, version="1.0.0", meta=None,
           rel_dir="."):
    return {"name": name, "description": desc, "version": version, "tap": tap,
            "curated": curated, "rel_dir": rel_dir,
            "skill_md": rel_dir.rstrip("/") + "/SKILL.md", "meta": meta or {}}


def _fake_taps(*specs):
    """Configure taps + pre-baked caches with no git clone at all."""
    paths.ensure_dirs()
    cfg = config.load()
    cfg["taps"] = [{"name": n, "url": "https://example.test/" + n,
                    "curated": False} for n, _ in specs]
    config.save(cfg)
    for n, entries in specs:
        registry.Tap(name=n, url="").cache_file.write_text(
            json.dumps({"skills": entries}), encoding="utf-8")


class TestScanDir:
    def test_skill_md_at_repo_root_uses_root_dirname(self, tmp_path):
        root = tmp_path / "solo-tap"
        write_skill(root, "---\nversion: 2.0\n---", "# Solo\n\nRoot level body\n")
        entries = catalog.scan_dir(root)
        assert len(entries) == 1
        e = entries[0]
        assert e["name"] == "solo-tap"
        assert e["rel_dir"] == "."
        assert e["skill_md"] == "SKILL.md"
        assert e["version"] == "2.0"

    def test_nested_skill_name_falls_back_to_dirname(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "skills" / "foo")
        (e,) = catalog.scan_dir(root)
        assert e["name"] == "foo"
        assert e["rel_dir"] == "skills/foo"
        assert e["skill_md"] == "skills/foo/SKILL.md"

    def test_name_from_frontmatter_beats_dirname(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "skills" / "dir-name", "---\nname: real-name\n---")
        (e,) = catalog.scan_dir(root)
        assert e["name"] == "real-name"

    def test_description_from_frontmatter_preferred(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "s", "---\ndescription: from meta\n---",
                    "# H\n\nbody line\n")
        (e,) = catalog.scan_dir(root)
        assert e["description"] == "from meta"

    def test_description_falls_back_to_first_non_heading_line(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "s", None,
                    "# Heading\n\n## Sub heading\n\nThe real description line\nsecond\n")
        (e,) = catalog.scan_dir(root)
        assert e["description"] == "The real description line"

    def test_description_fallback_truncated_at_160(self, tmp_path):
        root = tmp_path / "tap"
        long_line = "x" * 200
        write_skill(root / "s", None, "# T\n\n%s\n" % long_line)
        (e,) = catalog.scan_dir(root)
        assert e["description"] == "x" * 160
        assert len(e["description"]) == 160

    def test_description_empty_when_body_all_headings(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "s", None, "# Only\n## Headings\n")
        (e,) = catalog.scan_dir(root)
        assert e["description"] == ""

    def test_version_defaults_to_0_0_0(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "s", "---\nname: s\n---")
        (e,) = catalog.scan_dir(root)
        assert e["version"] == "0.0.0"

    def test_git_and_pycache_contents_ignored(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / ".git" / "inner")
        write_skill(root / "sub" / "__pycache__")
        write_skill(root / "real")
        entries = catalog.scan_dir(root)
        assert [e["name"] for e in entries] == ["real"]

    def test_name_with_spaces_slugified(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "s", "---\nname: My Cool Skill\n---")
        (e,) = catalog.scan_dir(root)
        assert e["name"] == "my-cool-skill"

    def test_name_without_spaces_kept_verbatim(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "s", "---\nname: WeirdCase\n---")
        (e,) = catalog.scan_dir(root)
        assert e["name"] == "WeirdCase"

    def test_traversal_name_is_slugified_not_kept(self, tmp_path):
        # Slugifying only on " " let this through verbatim, and the name is
        # joined onto the agent's rules/ dir downstream.
        root = tmp_path / "tap"
        write_skill(root / "s", "---\nname: ../../../../.ssh/authorized_keys\n---")
        (e,) = catalog.scan_dir(root)
        assert e["name"] == "ssh-authorized-keys"
        assert ".." not in e["name"] and "/" not in e["name"]

    @pytest.mark.parametrize("raw", ["..", ".", "a/b", "/abs"])
    def test_other_non_component_names_are_neutralized(self, tmp_path, raw):
        root = tmp_path / "tap"
        write_skill(root / "s", "---\nname: '%s'\n---" % raw)
        (e,) = catalog.scan_dir(root)
        assert "/" not in e["name"] and e["name"] not in {".", ".."}

    def test_dotted_and_underscored_names_survive_intact(self, tmp_path):
        # These are safe components; slugify would mangle them to "v1-2-3".
        root = tmp_path / "tap"
        write_skill(root / "s", "---\nname: my_skill.v1.2-3\n---")
        (e,) = catalog.scan_dir(root)
        assert e["name"] == "my_skill.v1.2-3"

    def test_tap_curated_and_meta_propagated(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "s", "---\nname: s\ntags: [a, b]\n---")
        (e,) = catalog.scan_dir(root, "mytap", curated=True)
        assert e["tap"] == "mytap"
        assert e["curated"] is True
        assert e["meta"]["tags"] == ["a", "b"]

    def test_defaults_local_uncurated(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "s")
        (e,) = catalog.scan_dir(root)
        assert e["tap"] == "local"
        assert e["curated"] is False

    def test_entries_sorted_by_path(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "bbb")
        write_skill(root / "aaa")
        assert [e["name"] for e in catalog.scan_dir(root)] == ["aaa", "bbb"]

    def test_empty_tree(self, tmp_path):
        assert catalog.scan_dir(tmp_path) == []

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="chmod can't remove the owner's own read access on Windows")
    def test_unreadable_skill_md_skipped(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "locked")
        write_skill(root / "open")
        (root / "locked" / "SKILL.md").chmod(0o000)
        try:
            entries = catalog.scan_dir(root)
        finally:
            (root / "locked" / "SKILL.md").chmod(0o644)
        assert [e["name"] for e in entries] == ["open"]


class TestScanRulesAndWorkflows:
    def test_skill_entries_carry_skill_kind(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "s", "---\nname: s\n---")
        (e,) = catalog.scan_dir(root)
        assert e["kind"] == "skill"

    def test_mdc_rule_indexed(self, tmp_path):
        root = tmp_path / "tap"
        (root / ".cursor" / "rules").mkdir(parents=True)
        (root / ".cursor" / "rules" / "react.mdc").write_text(
            "---\ndescription: React best practices\nglobs: '*.tsx'\n---\n\nUse hooks.\n", encoding="utf-8")
        (e,) = catalog.scan_dir(root)
        assert e["kind"] == "rule"
        assert e["name"] == "react"
        assert e["description"] == "React best practices"
        assert e["skill_md"] == ".cursor/rules/react.mdc"
        assert e["rel_dir"] == ".cursor/rules"

    def test_cursorrules_dotfile_named_after_parent_dir(self, tmp_path):
        root = tmp_path / "tap"
        (root / "nextjs").mkdir(parents=True)
        (root / "nextjs" / ".cursorrules").write_text("You are a Next.js expert.\n", encoding="utf-8")
        (e,) = catalog.scan_dir(root)
        assert e["kind"] == "rule"
        assert e["name"] == "nextjs"
        assert e["description"] == "You are a Next.js expert."

    def test_windsurfrules_and_clinerules_indexed(self, tmp_path):
        root = tmp_path / "tap"
        (root / "a").mkdir(parents=True)
        (root / "b").mkdir(parents=True)
        (root / "a" / ".windsurfrules").write_text("windsurf rule\n", encoding="utf-8")
        (root / "b" / ".clinerules").write_text("cline rule\n", encoding="utf-8")
        kinds = {e["name"]: e["kind"] for e in catalog.scan_dir(root)}
        assert kinds == {"a": "rule", "b": "rule"}

    def test_workflow_under_commands_dir(self, tmp_path):
        root = tmp_path / "tap"
        (root / "commands").mkdir(parents=True)
        (root / "commands" / "review.md").write_text(
            "---\ndescription: Review the diff\n---\n\nDo a review.\n", encoding="utf-8")
        (e,) = catalog.scan_dir(root)
        assert e["kind"] == "workflow"
        assert e["name"] == "review"

    def test_workflow_under_claude_agents_dir(self, tmp_path):
        root = tmp_path / "tap"
        (root / ".claude" / "agents").mkdir(parents=True)
        (root / ".claude" / "agents" / "backend.md").write_text(
            "---\nname: backend-architect\ndescription: Designs APIs\n---\n\nBody.\n", encoding="utf-8")
        (e,) = catalog.scan_dir(root)
        assert e["kind"] == "workflow"
        assert e["name"] == "backend-architect"

    def test_root_subagent_signature_detected(self, tmp_path):
        root = tmp_path / "tap"
        root.mkdir(parents=True)
        (root / "code-reviewer.md").write_text(
            "---\nname: code-reviewer\ndescription: Reviews code\ntools: Read, Grep\n---\n\nX.\n", encoding="utf-8")
        (e,) = catalog.scan_dir(root)
        assert e["kind"] == "workflow"
        assert e["name"] == "code-reviewer"

    def test_plain_markdown_and_docs_not_indexed(self, tmp_path):
        root = tmp_path / "tap"
        root.mkdir(parents=True)
        (root / "README.md").write_text("# Readme\n\nHello.\n", encoding="utf-8")
        (root / "notes.md").write_text("# Notes\n\nJust prose, no frontmatter.\n", encoding="utf-8")
        (root / "commands").mkdir()
        (root / "commands" / "README.md").write_text("# Commands index\n", encoding="utf-8")
        assert catalog.scan_dir(root) == []

    def test_reference_files_inside_skill_dir_not_double_counted(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "skills" / "s", "---\nname: s\n---")
        # a skill that ships a bundled rule/command as reference material
        (root / "skills" / "s" / "extra.mdc").write_text("bundled rule\n", encoding="utf-8")
        (root / "skills" / "s" / "commands").mkdir()
        (root / "skills" / "s" / "commands" / "helper.md").write_text(
            "---\ndescription: helper\n---\nx\n", encoding="utf-8")
        entries = catalog.scan_dir(root)
        assert [e["name"] for e in entries] == ["s"]
        assert entries[0]["kind"] == "skill"

    def test_rule_entry_carries_tap_and_curated(self, tmp_path):
        root = tmp_path / "tap"
        (root / "nextjs").mkdir(parents=True)
        (root / "nextjs" / ".cursorrules").write_text("Next.js expert.\n", encoding="utf-8")
        (e,) = catalog.scan_dir(root, "mytap", curated=True)
        assert e["kind"] == "rule"
        assert e["tap"] == "mytap"
        assert e["curated"] is True

    def test_ignored_dirs_pruned_for_loose_rules_and_workflows(self, tmp_path):
        root = tmp_path / "tap"
        (root / ".git").mkdir(parents=True)
        (root / "sub" / "__pycache__").mkdir(parents=True)
        (root / ".git" / "hook.mdc").write_text("---\ndescription: x\n---\n", encoding="utf-8")
        (root / "sub" / "__pycache__" / "commands").mkdir()
        (root / "sub" / "__pycache__" / "commands" / "c.md").write_text(
            "---\ndescription: y\n---\nx\n", encoding="utf-8")
        (root / "real").mkdir()
        (root / "real" / ".cursorrules").write_text("real rule\n", encoding="utf-8")
        assert [e["name"] for e in catalog.scan_dir(root)] == ["real"]

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="chmod can't remove the owner's own read access on Windows")
    def test_unreadable_rule_file_skipped(self, tmp_path):
        root = tmp_path / "tap"
        (root / "a").mkdir(parents=True)
        (root / "b").mkdir(parents=True)
        (root / "a" / "locked.mdc").write_text("---\ndescription: x\n---\n", encoding="utf-8")
        (root / "b" / "open.mdc").write_text("---\ndescription: y\n---\n", encoding="utf-8")
        (root / "a" / "locked.mdc").chmod(0o000)
        try:
            entries = catalog.scan_dir(root)
        finally:
            (root / "a" / "locked.mdc").chmod(0o644)
        assert [e["name"] for e in entries] == ["open"]

    def test_classify_workflow_guards(self, tmp_path):
        # non-markdown and SKILL.md never classify as workflow
        assert catalog._classify_workflow(Path("commands/x.txt"), {}) is False
        assert catalog._classify_workflow(Path("agents/SKILL.md"), {}) is False
        # documentation stems are excluded even under a workflow dir
        assert catalog._classify_workflow(Path("commands/README.md"), {}) is False
        # a bare prompt .md with no dir marker and no subagent frontmatter
        assert catalog._classify_workflow(Path("prompts/idea.md"), {}) is False

    def test_classify_workflow_signature_needs_name_and_description(self):
        # Outside a workflow dir, the frontmatter signature requires BOTH a name
        # AND a description AND a workflow meta key. (Pins the `and` between
        # name/description — an `or` would classify a name-only file.)
        loose = Path("prompts/agent.md")
        full = {"name": "a", "description": "d", "tools": ["x"]}
        assert catalog._classify_workflow(loose, full) is True
        assert catalog._classify_workflow(loose, {"name": "a", "tools": ["x"]}) is False
        assert catalog._classify_workflow(
            loose, {"description": "d", "tools": ["x"]}) is False

    def test_classify_workflow_signature_needs_a_workflow_meta_key(self):
        # name+description alone do NOT make a loose .md a workflow — it needs one
        # of the subagent/slash-command keys. (Pins `WORKFLOW_META_KEYS & set` —
        # a `|` would make the set truthy for any frontmatter.)
        loose = Path("prompts/agent.md")
        assert catalog._classify_workflow(loose, {"name": "a", "description": "d"}) is False
        assert catalog._classify_workflow(
            loose, {"name": "a", "description": "d", "model": "opus"}) is True

    def test_mixed_kinds_all_present(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "skills" / "s", "---\nname: s\n---")
        (root / "rules").mkdir()
        (root / "rules" / "py.mdc").write_text("---\ndescription: python\n---\nx\n", encoding="utf-8")
        (root / "commands").mkdir()
        (root / "commands" / "ship.md").write_text("---\ndescription: ship it\n---\nx\n", encoding="utf-8")
        kinds = sorted(e["kind"] for e in catalog.scan_dir(root))
        assert kinds == ["rule", "skill", "workflow"]


class TestTapCaches:
    def test_rebuild_writes_cache(self, sandbox, fixture_tap_src):
        tap = registry.add(str(fixture_tap_src))
        entries = catalog.rebuild_tap(tap)
        assert [e["name"] for e in entries] == FIXTURE_NAMES
        cache = json.loads(tap.cache_file.read_text(encoding="utf-8"))
        assert cache["tap"] == "fixture-tap"
        assert cache["url"] == tap.url
        assert re.fullmatch(r"[0-9a-f]{40}", cache["commit"])
        assert len(cache["skills"]) == 5
        jira = next(e for e in entries if e["name"] == "jira-integration")
        assert jira["version"] == "2.1.0"
        assert jira["description"] == "Sync commits and PRs to Jira tickets"
        assert jira["rel_dir"] == "skills/jira-integration"
        assert jira["meta"]["requires"] == ["commit-messages"]

    def test_rebuild_uncloned_raises(self, sandbox):
        tap = registry.Tap(name="ghost/tap", url="x")
        with pytest.raises(BoostError) as ei:
            catalog.rebuild_tap(tap)
        assert ei.value.message == "tap ghost/tap is not cloned"
        assert ei.value.hint == "run `boost update ghost/tap`"

    def test_load_tap_cache_hit_needs_no_clone(self, sandbox):
        paths.ensure_dirs()
        tap = registry.Tap(name="fake", url="")
        tap.cache_file.write_text(json.dumps({"skills": [{"name": "cached-skill"}]}), encoding="utf-8")
        assert catalog.load_tap(tap) == [{"name": "cached-skill"}]

    def test_load_tap_rebuild_flag_bypasses_cache(self, sandbox, fixture_tap_src):
        tap = registry.add(str(fixture_tap_src))
        tap.cache_file.write_text(json.dumps({"skills": [{"name": "stale"}]}), encoding="utf-8")
        entries = catalog.load_tap(tap, rebuild=True)
        assert [e["name"] for e in entries] == FIXTURE_NAMES
        assert "brainstorming" in tap.cache_file.read_text(encoding="utf-8")  # cache rewritten

    def test_load_tap_corrupt_cache_rebuilds_when_cloned(self, sandbox, fixture_tap_src):
        tap = registry.add(str(fixture_tap_src))
        tap.cache_file.write_text("{not json", encoding="utf-8")
        entries = catalog.load_tap(tap)
        assert [e["name"] for e in entries] == FIXTURE_NAMES

    def test_load_tap_corrupt_cache_uncloned_empty(self, sandbox):
        paths.ensure_dirs()
        tap = registry.Tap(name="fake", url="")
        tap.cache_file.write_text("{not json", encoding="utf-8")
        assert catalog.load_tap(tap) == []

    def test_load_tap_no_cache_uncloned_empty(self, sandbox):
        assert catalog.load_tap(registry.Tap(name="fake", url="")) == []


class TestEntrySetCache:
    """load_tap memoizes parsed skills on the cache file's (mtime_ns, size)
    stamp, so repeated searches don't re-parse every tap cache."""

    def test_unchanged_cache_returns_memoized_object(self, sandbox):
        paths.ensure_dirs()
        tap = registry.Tap(name="fake", url="")
        tap.cache_file.write_text(json.dumps({"skills": [{"name": "s1"}]}), encoding="utf-8")
        first = catalog.load_tap(tap)
        second = catalog.load_tap(tap)
        # A cache hit returns the memoized list itself; a re-parse would build a
        # fresh list, so identity proves the second call did not touch disk.
        assert first == [{"name": "s1"}]
        assert second is first

    def test_content_change_invalidates_cache(self, sandbox):
        paths.ensure_dirs()
        tap = registry.Tap(name="fake", url="")
        tap.cache_file.write_text(json.dumps({"skills": [{"name": "s1"}]}), encoding="utf-8")
        assert catalog.load_tap(tap) == [{"name": "s1"}]
        # New content ⇒ different size ⇒ new stamp ⇒ the cache must re-read.
        tap.cache_file.write_text(
            json.dumps({"skills": [{"name": "s1"}, {"name": "s2"}]}), encoding="utf-8")
        assert catalog.load_tap(tap) == [{"name": "s1"}, {"name": "s2"}]

    def test_rebuild_pops_stale_memo(self, sandbox, fixture_tap_src):
        tap = registry.add(str(fixture_tap_src))
        catalog.rebuild_tap(tap)          # write the cache file
        catalog.load_tap(tap)             # read + memoize it
        assert str(tap.cache_file) in catalog._ENTRY_CACHE
        catalog.rebuild_tap(tap)          # must evict the now-stale memo
        assert str(tap.cache_file) not in catalog._ENTRY_CACHE

    def test_missing_cache_file_evicts_stamp(self, sandbox):
        paths.ensure_dirs()
        tap = registry.Tap(name="fake", url="")
        tap.cache_file.write_text(json.dumps({"skills": [{"name": "s1"}]}), encoding="utf-8")
        assert catalog.load_tap(tap) == [{"name": "s1"}]
        assert str(tap.cache_file) in catalog._ENTRY_CACHE
        tap.cache_file.unlink()
        assert catalog.load_tap(tap) == []  # no file, uncloned
        assert str(tap.cache_file) not in catalog._ENTRY_CACHE


class TestSplitName:
    """The `tap:skill` grammar, factored out of find() so the lock file and the
    canonical store — both keyed by the *bare* name — split it identically."""

    def test_unqualified_name_has_no_tap(self):
        assert catalog.split_name("differential-review") == (None, "differential-review")

    def test_owner_repo_qualifier(self):
        assert catalog.split_name("trailofbits/skills:differential-review") \
            == ("trailofbits/skills", "differential-review")

    def test_bare_repo_qualifier(self):
        assert catalog.split_name("skills:differential-review") \
            == ("skills", "differential-review")

    def test_splits_on_the_last_colon(self):
        # rsplit, not split: the skill name is always the final segment.
        assert catalog.split_name("a:b:c") == ("a:b", "c")

    def test_empty_qualifier_is_not_none(self):
        # ":x" must stay distinguishable from "x" — find() overrides its `tap`
        # kwarg only when a qualifier was actually present, and "" is falsy.
        assert catalog.split_name(":x") == ("", "x")


class TestTapMatches:
    def test_exact_owner_repo(self):
        assert catalog.tap_matches("trailofbits/skills", "trailofbits/skills") is True

    def test_bare_repo_tail(self):
        assert catalog.tap_matches("trailofbits/skills", "skills") is True

    def test_owner_alone_does_not_select(self):
        assert catalog.tap_matches("trailofbits/skills", "trailofbits") is False

    def test_different_owner_same_tail_needs_the_tail(self):
        assert catalog.tap_matches("vibeeval/vibecosystem", "trailofbits/skills") is False

    def test_empty_tap_name_never_matches(self):
        assert catalog.tap_matches("", "skills") is False

    def test_two_empties_do_not_match_each_other(self):
        # Pins the `bool(tap_name)` guard: without it a tap-less lock entry
        # ("" tap) would satisfy an empty qualifier by string equality.
        assert catalog.tap_matches("", "") is False


class TestAllEntriesAndFind:
    def test_all_entries_config_order(self, sandbox):
        _fake_taps(
            ("zeta", [_entry("z1", "zeta"), _entry("z2", "zeta")]),
            ("alpha", [_entry("a1", "alpha")]),
        )
        assert [e["name"] for e in catalog.all_entries()] == ["z1", "z2", "a1"]

    def test_kind_counts_splits_the_corpus_by_kind(self, sandbox):
        _fake_taps(("t", [dict(_entry("s", "t"), kind="skill"),
                          dict(_entry("r", "t"), kind="rule"),
                          dict(_entry("w", "t"), kind="workflow"),
                          dict(_entry("r2", "t"), kind="rule")]))
        assert catalog.kind_counts() == {"skill": 1, "rule": 2, "workflow": 1}

    def test_kind_counts_names_all_three_kinds_even_at_zero(self, sandbox):
        # `boost_doctor` and boost_list's footer both report a kind sitting at
        # zero as a fact about the machine — "nothing here could have loaded a
        # rule" is the inference. A dict that omits empty kinds would make the
        # caller invent the zero, or quietly drop the line.
        _fake_taps(("t", [dict(_entry("s", "t"), kind="skill")]))
        assert catalog.kind_counts() == {"skill": 1, "rule": 0, "workflow": 0}

    def test_kind_counts_with_no_taps_is_three_zeros(self, sandbox):
        assert catalog.kind_counts() == {"skill": 0, "rule": 0, "workflow": 0}

    def test_an_entry_with_no_kind_counts_as_a_skill(self, sandbox):
        # Caches written before the kind field existed, and any tap whose
        # scanner output is thin. Everything else in the catalog reads a
        # missing kind as a skill; this must not be the one place it vanishes.
        _fake_taps(("t", [_entry("old", "t")]))
        assert catalog.kind_counts()["skill"] == 1

    def test_the_total_still_equals_the_full_scan(self, sandbox):
        # The whole point of this function is that a caller wanting the size of
        # the corpus never materialises it: `boost_doctor` took
        # `len(all_entries())`, building 71,655 dicts to produce one integer.
        # An unrecognised kind therefore gets its own key rather than being
        # dropped — a silently smaller total would be a worse bug than the
        # allocation it replaced.
        _fake_taps(("t", [dict(_entry("s", "t"), kind="skill"),
                          dict(_entry("x", "t"), kind="mcp-server")]))
        counts = catalog.kind_counts()
        assert counts["mcp-server"] == 1
        assert sum(counts.values()) == len(catalog.all_entries())

    def test_find_exact_name(self, sandbox):
        _fake_taps(("t", [_entry("aaa", "t"), _entry("aab", "t")]))
        matches = catalog.find("aaa")
        assert len(matches) == 1
        assert matches[0]["name"] == "aaa"

    def test_find_no_partial_match(self, sandbox):
        _fake_taps(("t", [_entry("aaa", "t")]))
        assert catalog.find("aa") == []
        assert catalog.find("nope") == []

    def test_find_qualified_form(self, sandbox):
        _fake_taps(("owner/alpha", [_entry("dup", "owner/alpha")]),
                   ("beta", [_entry("dup", "beta")]))
        assert len(catalog.find("dup")) == 2
        full = catalog.find("owner/alpha:dup")
        assert [e["tap"] for e in full] == ["owner/alpha"]
        tail = catalog.find("alpha:dup")
        assert [e["tap"] for e in tail] == ["owner/alpha"]
        assert [e["tap"] for e in catalog.find("beta:dup")] == ["beta"]

    def test_find_tap_kwarg(self, sandbox):
        _fake_taps(("owner/alpha", [_entry("dup", "owner/alpha")]),
                   ("beta", [_entry("dup", "beta")]))
        assert [e["tap"] for e in catalog.find("dup", tap="beta")] == ["beta"]
        assert [e["tap"] for e in catalog.find("dup", tap="alpha")] == ["owner/alpha"]

    def test_qualified_tap_beats_another_taps_tail(self, sandbox):
        # angular/skills and microsoft/skills both end in "skills". The
        # qualified form must select exactly one; the untiered `tap in (...)`
        # membership test used to let the tail match leak the other tap in.
        _fake_taps(("angular/skills", [_entry("brainstorming", "angular/skills")]),
                   ("microsoft/skills", [_entry("brainstorming", "microsoft/skills")]))
        got = catalog.find("brainstorming", tap="angular/skills")
        assert [e["tap"] for e in got] == ["angular/skills"]
        got = catalog.find("angular/skills:brainstorming")
        assert [e["tap"] for e in got] == ["angular/skills"]

    def test_ambiguous_tail_returns_every_candidate(self, sandbox):
        # find() reports rather than guesses; the caller decides. `bundle apply`
        # refuses, which is what stops it installing from the wrong tap.
        _fake_taps(("angular/skills", [_entry("brainstorming", "angular/skills")]),
                   ("microsoft/skills", [_entry("brainstorming", "microsoft/skills")]))
        got = catalog.find("brainstorming", tap="skills")
        assert sorted(e["tap"] for e in got) == ["angular/skills", "microsoft/skills"]

    def test_exact_tap_name_wins_over_a_tail(self, sandbox):
        _fake_taps(("owner/skills", [_entry("dup", "owner/skills")]),
                   ("skills", [_entry("dup", "skills")]))
        assert [e["tap"] for e in catalog.find("dup", tap="skills")] == ["skills"]


class TestResolveOne:
    def test_single_hit(self, sandbox):
        _fake_taps(("t", [_entry("only", "t", desc="d")]))
        e = catalog.resolve_one("only")
        assert e["name"] == "only"
        assert e["tap"] == "t"

    def test_miss_with_closest_match_hint(self, sandbox):
        _fake_taps(("t", [_entry("brainstorming", "t", desc="ideation"),
                          _entry("tdd-workflow", "t", desc="testing loop")]))
        with pytest.raises(BoostError) as ei:
            catalog.resolve_one("brainstorm")
        assert ei.value.message == "no skill named 'brainstorm' in any tap"
        assert ei.value.hint == "closest matches: brainstorming"

    def test_miss_hint_caps_at_three_joined_by_comma(self, sandbox):
        # Five near-matches, but the hint lists exactly the top THREE, comma-
        # joined. (Pins `search(name)[:3]` and the `", "` join separator.)
        _fake_taps(("t", [_entry("planner-%d" % i, "t") for i in range(5)]))
        with pytest.raises(BoostError) as ei:
            catalog.resolve_one("planner")
        listed = ei.value.hint.replace("closest matches: ", "").split(", ")
        assert len(listed) == 3
        assert all(n.startswith("planner-") for n in listed)

    def test_miss_hint_dedups_mirrored_copies(self, sandbox):
        # A registry that mirrors one skill per agent scores every copy, and the
        # old hint rendered them by bare name — "mempalace, mempalace,
        # mempalace", three of nothing. One tap, so no qualifier is needed.
        _fake_taps(("MemPalace/mempalace", [
            _entry("mempalace", "MemPalace/mempalace", rel_dir="skills/mempalace"),
            _entry("mempalace", "MemPalace/mempalace",
                   rel_dir=".claude-plugin/skills/mempalace"),
            _entry("mempalace", "MemPalace/mempalace",
                   rel_dir=".codex-plugin/skills/mempalace")]))
        with pytest.raises(BoostError) as ei:
            catalog.resolve_one("mempal")
        assert ei.value.hint == "closest matches: mempalace"

    def test_miss_hint_qualifies_a_name_spanning_taps(self, sandbox):
        # Here the bare name would not resolve either, so the tap earns its keep.
        _fake_taps(("owner/alpha", [_entry("dup", "owner/alpha")]),
                   ("beta", [_entry("dup", "beta")]))
        with pytest.raises(BoostError) as ei:
            catalog.resolve_one("du")
        listed = ei.value.hint.replace("closest matches: ", "").split(", ")
        assert sorted(listed) == ["beta:dup", "owner/alpha:dup"]

    def test_path_shaped_qualifier_names_the_grammar_error(self, sandbox):
        # `boost install MemPalace/mempalace:skills/mempalace` — the tail is a
        # path, so the fuzzy hint could only ever guess. Say what went wrong.
        _fake_taps(("MemPalace/mempalace", [
            _entry("mempalace", "MemPalace/mempalace", rel_dir="skills/mempalace")]))
        with pytest.raises(BoostError) as ei:
            catalog.resolve_one("MemPalace/mempalace:skills/mempalace")
        assert ei.value.message == (
            "no skill named 'skills/mempalace' — after ':' boost expects a "
            "skill name, not a path")
        assert "--path" in ei.value.hint
        assert ("boost install MemPalace/mempalace:mempalace --path "
                "skills/mempalace") in ei.value.hint

    def test_the_suggested_command_actually_resolves(self, sandbox):
        """Run the hint, do not just match its text.

        A hint is a promise that a command will work, and asserting the string
        only proves it was formatted. This lifts the arguments back out and
        feeds them to resolve_one — which is what caught the qualifier being
        dropped: the bare leaf name is ambiguous the moment a second tap ships
        a skill by that name, so the "fix" failed for the user who most needed
        the tap they had already typed correctly.
        """
        _fake_taps(("MemPalace/mempalace", [
            _entry("mempalace", "MemPalace/mempalace", rel_dir="skills/mempalace")]),
            ("other/pack", [_entry("mempalace", "other/pack",
                                   rel_dir="skills/mempalace")]))
        with pytest.raises(BoostError) as ei:
            catalog.resolve_one("MemPalace/mempalace:skills/mempalace")
        cmd = re.search(r"`boost install (\S+) --path (\S+)`", ei.value.hint)
        assert cmd, ei.value.hint
        entry = catalog.resolve_one(cmd.group(1), path=cmd.group(2))
        assert entry["tap"] == "MemPalace/mempalace"

    def test_an_entry_with_no_tap_is_labelled_and_counted_as_untapped(self):
        """Pin the defensive defaults on the two `e.get("tap", …)` reads.

        A catalog row always carries a tap, so this exercises the branch that
        exists for a malformed one. Both defaults matter and differ: the
        collision count treats a missing tap as the empty string (so a row with
        `tap: ""` and a row with no tap are one registry, not two), while the
        label falls back to `?` — a rendered `None:` would read as a real
        registry named None.
        """
        assert catalog._suggestions([({"name": "a"}, 1.0)]) == ["a"]
        assert catalog._suggestions(
            [({"name": "a", "tap": ""}, 1.0), ({"name": "a"}, 0.9)]) == ["a"]
        assert catalog._suggestions(
            [({"name": "a", "tap": "t"}, 1.0), ({"name": "a"}, 0.9)]) == [
                "t:a", "?:a"]

    def test_suggestions_are_deduped_before_the_top_three_are_taken(self, sandbox):
        """Three distinct suggestions, not three slots eaten by one mirror.

        Slicing to three and *then* collapsing is the trap: the mirrored copies
        score adjacently, so the pre-slice holds one name three times and the
        hint shrinks to a single suggestion — in exactly the case the dedupe was
        written for.
        """
        _fake_taps(("reg/pack", [
            _entry("planner", "reg/pack", rel_dir="skills/planner"),
            _entry("planner", "reg/pack", rel_dir=".claude-plugin/skills/planner"),
            _entry("planner", "reg/pack", rel_dir=".codex-plugin/skills/planner"),
            _entry("planner-pro", "reg/pack", rel_dir="skills/planner-pro"),
            _entry("planner-lite", "reg/pack", rel_dir="skills/planner-lite")]))
        with pytest.raises(BoostError) as ei:
            catalog.resolve_one("planne")
        listed = ei.value.hint.replace("closest matches: ", "").split(", ")
        assert len(listed) == 3, listed
        assert len(set(listed)) == 3, listed

    def test_unqualified_slash_name_is_still_a_plain_miss(self, sandbox):
        # No ':' means no grammar to misread — the ordinary miss still applies.
        _fake_taps(("t", [_entry("brainstorming", "t")]))
        with pytest.raises(BoostError) as ei:
            catalog.resolve_one("some/thing")
        assert ei.value.message == "no skill named 'some/thing' in any tap"

    def test_miss_no_close_match_no_hint(self, sandbox):
        _fake_taps(("t", [_entry("brainstorming", "t")]))
        with pytest.raises(BoostError) as ei:
            catalog.resolve_one("qqqq")
        assert ei.value.hint is None

    def test_miss_no_taps_hint(self, sandbox):
        with pytest.raises(BoostError) as ei:
            catalog.resolve_one("anything")
        assert ei.value.message == "no skill named 'anything' in any tap"
        assert ei.value.hint == "no taps configured — start with `boost tap --defaults`"

    def test_multi_tap_ambiguity(self, sandbox):
        _fake_taps(("owner/alpha", [_entry("dup", "owner/alpha")]),
                   ("beta", [_entry("dup", "beta")]))
        with pytest.raises(BoostError) as ei:
            catalog.resolve_one("dup")
        assert ei.value.message == "'dup' exists in multiple taps: owner/alpha, beta"
        assert ei.value.hint == "qualify it, e.g. `owner/alpha:dup`"


class TestResolveOneVendoredCopies:
    """One tap shipping the same skill at several paths must not dead-end.

    Registries commonly vendor their own skills into plugin bundles, so a repo
    holds `skills/x/SKILL.md` *and* `plugins/pack/skills/x/SKILL.md` with
    identical frontmatter. Found by dogfooding: installing
    `debugging-and-error-recovery` reported it in "multiple taps" while naming
    one tap three times, then hinted a qualification that re-raised the very
    same error.
    """

    def _vendored(self):
        # The real shape from lingxling/awesome-skills-cn: three paths, one
        # description, one version — nothing a user could choose between.
        return [_entry("dbg", "t", desc="same", rel_dir=d) for d in (
            "antigravity/plugins/pack-claude/skills/dbg",
            "antigravity/skills/dbg",
            "antigravity/plugins/pack/skills/dbg")]

    def test_indistinguishable_copies_in_one_tap_resolve(self, sandbox):
        # The disambiguation prompt was unanswerable: same name, description,
        # version and meta. Picking one is strictly better than refusing.
        _fake_taps(("t", self._vendored()))
        assert catalog.resolve_one("dbg")["name"] == "dbg"

    def test_the_shallowest_copy_wins_and_is_stable(self, sandbox):
        # Deterministic on purpose — a resolver that varied with dict order
        # would install a different directory run to run. Shallowest path is
        # the canonical copy; the vendored ones sit deeper by construction.
        _fake_taps(("t", self._vendored()))
        first = catalog.resolve_one("dbg")["rel_dir"]
        assert first == "antigravity/skills/dbg"
        _fake_taps(("t", list(reversed(self._vendored()))))
        assert catalog.resolve_one("dbg")["rel_dir"] == first

    def test_equal_depth_copies_break_the_tie_lexicographically(self, sandbox):
        # Without the second sort key the pick would fall back to dict order,
        # which is stable within a run and therefore looks fine in a test while
        # still varying across machines.
        _fake_taps(("t", [_entry("dbg", "t", desc="same", rel_dir=d)
                          for d in ("z/dbg", "m/dbg", "a/dbg")]))
        assert catalog.resolve_one("dbg")["rel_dir"] == "a/dbg"

    def test_same_tap_but_genuinely_different_still_asks(self, sandbox):
        # Differing descriptions mean the user CAN tell them apart, so the
        # choice is theirs to make. Collapsing here would silently install one
        # of two real alternatives.
        _fake_taps(("t", [_entry("dbg", "t", desc="python", rel_dir="a/dbg"),
                          _entry("dbg", "t", desc="rust", rel_dir="b/dbg")]))
        with pytest.raises(BoostError):
            catalog.resolve_one("dbg")

    def test_the_ambiguity_hint_names_the_way_out(self, sandbox):
        """The error told the user to "inspect the paths above" and offered no
        syntax that could act on it — a dead end. It must name `--path`."""
        _fake_taps(("t", [_entry("dbg", "t", desc="python", rel_dir="a/dbg"),
                          _entry("dbg", "t", desc="rust", rel_dir="b/dbg")]))
        with pytest.raises(BoostError) as excinfo:
            catalog.resolve_one("dbg")
        assert "--path" in (excinfo.value.hint or "")

    def test_path_picks_one_of_two_real_alternatives(self, sandbox):
        _fake_taps(("t", [_entry("dbg", "t", desc="python", rel_dir="a/dbg"),
                          _entry("dbg", "t", desc="rust", rel_dir="b/dbg")]))
        assert catalog.resolve_one("dbg", path="b/dbg")["description"] == "rust"
        assert catalog.resolve_one("dbg", path="a/dbg")["description"] == "python"

    def test_path_may_be_a_trailing_segment(self, sandbox):
        """Users copy a path out of the error, but a deep vendored path is long;
        matching on a suffix keeps `--path skills/dbg` usable."""
        _fake_taps(("t", [_entry("dbg", "t", desc="py", rel_dir="deep/x/skills/dbg"),
                          _entry("dbg", "t", desc="rs", rel_dir="b/dbg")]))
        assert catalog.resolve_one("dbg", path="skills/dbg")["description"] == "py"

    def test_the_suffix_match_respects_segment_boundaries(self, sandbox):
        """`endswith(want)` without the leading slash would let `--path s/dbg`
        be satisfied by `not-s/dbg` — a different directory entirely."""
        _fake_taps(("t", [_entry("dbg", "t", desc="wrong", rel_dir="x/not-s/dbg"),
                          _entry("dbg", "t", desc="right", rel_dir="x/s/dbg")]))
        assert catalog.resolve_one("dbg", path="s/dbg")["description"] == "right"

    def test_path_that_matches_nothing_lists_the_real_ones(self, sandbox):
        _fake_taps(("t", [_entry("dbg", "t", desc="python", rel_dir="a/dbg"),
                          _entry("dbg", "t", desc="rust", rel_dir="b/dbg")]))
        with pytest.raises(BoostError) as excinfo:
            catalog.resolve_one("dbg", path="nope/dbg")
        hint = excinfo.value.hint or ""
        assert "a/dbg" in hint and "b/dbg" in hint

    def test_an_exact_path_beats_a_suffix_match(self, sandbox):
        """The real shape from DietrichGebert/ponytail: a canonical
        `skills/ponytail` and an agent mirror `.openclaw/skills/ponytail`. The
        suffix rule alone matches both, so `--path skills/ponytail` — the exact
        rel_dir of one of them — must mean that one, not "still ambiguous"."""
        _fake_taps(("t", [_entry("dbg", "t", desc="canon", rel_dir="skills/dbg"),
                          _entry("dbg", "t", desc="mirror",
                                 rel_dir=".openclaw/skills/dbg")]))
        assert catalog.resolve_one("dbg", path="skills/dbg")["description"] == "canon"
        assert catalog.resolve_one(
            "dbg", path=".openclaw/skills/dbg")["description"] == "mirror"

    def test_path_still_ambiguous_is_still_an_error(self, sandbox):
        """A suffix loose enough to hit both candidates must not silently pick."""
        _fake_taps(("t", [_entry("dbg", "t", desc="python", rel_dir="a/skills/dbg"),
                          _entry("dbg", "t", desc="rust", rel_dir="b/skills/dbg")]))
        with pytest.raises(BoostError):
            catalog.resolve_one("dbg", path="skills/dbg")

    def test_path_cannot_traverse_out_of_the_catalog(self, sandbox):
        """--path only *filters* rows the catalog already has; it never builds
        a filesystem path. Traversal therefore cannot select anything — it can
        only fail to match. Pinned so a future rewrite cannot quietly make this
        flag a path constructor.
        """
        _fake_taps(("t", [_entry("dbg", "t", desc="a", rel_dir="skills/dbg"),
                          _entry("dbg", "t", desc="b", rel_dir="other/dbg")]))
        for hostile in ("../../etc/passwd", "/etc/passwd", "../skills/dbg"):
            with pytest.raises(BoostError):
                catalog.resolve_one("dbg", path=hostile)

    def test_path_does_not_defeat_the_cross_tap_refusal(self, sandbox):
        """Provenance stays load-bearing: --path must never merge two taps."""
        _fake_taps(("owner/alpha", [_entry("dup", "owner/alpha", rel_dir="s/dup")]),
                   ("owner/beta", [_entry("dup", "owner/beta", rel_dir="s/dup")]))
        with pytest.raises(BoostError):
            catalog.resolve_one("dup", path="s/dup")

    def test_path_is_honoured_when_the_name_is_already_unique(self, sandbox):
        _fake_taps(("t", [_entry("solo", "t", rel_dir="a/solo")]))
        assert catalog.resolve_one("solo", path="a/solo")["name"] == "solo"

    def test_a_wrong_path_is_an_error_even_when_the_name_is_unique(self, sandbox):
        """Ignoring an unmatched --path would install the very copy the user
        was trying to steer away from, and report success doing it."""
        _fake_taps(("t", [_entry("solo", "t", rel_dir="a/solo")]))
        with pytest.raises(BoostError):
            catalog.resolve_one("solo", path="typo/solo")

    def test_identical_across_taps_still_asks(self, sandbox):
        # Provenance is the whole point of a tap. Two registries shipping
        # byte-identical text are still two different supply chains, and
        # typosquatting makes that distinction load-bearing (see typosquat.py).
        _fake_taps(("owner/alpha", [_entry("dup", "owner/alpha", desc="same")]),
                   ("owner/beta", [_entry("dup", "owner/beta", desc="same")]))
        with pytest.raises(BoostError):
            catalog.resolve_one("dup")

    def test_a_tap_is_never_listed_twice(self, sandbox):
        # "exists in multiple taps: t, t, t" is simply false.
        _fake_taps(("t", [_entry("dbg", "t", desc="python", rel_dir="a/dbg"),
                          _entry("dbg", "t", desc="rust", rel_dir="b/dbg")]))
        with pytest.raises(BoostError) as ei:
            catalog.resolve_one("dbg")
        assert ei.value.message.count("t,") == 0
        assert "multiple taps" not in ei.value.message

    def test_one_tap_error_names_the_paths_not_a_useless_qualifier(self, sandbox):
        # The old hint said "qualify by tap" when every candidate shared a tap,
        # so following it reproduced the error verbatim. What distinguishes
        # these rows is their path, so that is what the user must be shown.
        _fake_taps(("t", [_entry("dbg", "t", desc="python", rel_dir="a/dbg"),
                          _entry("dbg", "t", desc="rust", rel_dir="b/dbg")]))
        with pytest.raises(BoostError) as ei:
            catalog.resolve_one("dbg")
        shown = ei.value.message + " " + (ei.value.hint or "")
        assert "a/dbg" in shown and "b/dbg" in shown
        assert "qualify it" not in shown

    def test_an_already_qualified_name_is_not_qualified_twice(self, sandbox):
        # A bare tap TAIL can still be ambiguous across owners, so a qualified
        # input can reach the multi-tap branch — which is where the hint used
        # to emit `owner/skills:skills:dbg`, a string that can never resolve.
        _fake_taps(("owner/skills", [_entry("dbg", "owner/skills")]),
                   ("other/skills", [_entry("dbg", "other/skills")]))
        with pytest.raises(BoostError) as ei:
            catalog.resolve_one("skills:dbg")
        assert ei.value.hint.endswith(":dbg`"), ei.value.hint
        assert "skills:skills" not in ei.value.hint

    def test_the_one_tap_error_names_the_bare_skill(self, sandbox):
        # Pins that the message reports the skill, not the tap prefix sliced
        # off the qualified input.
        _fake_taps(("t", [_entry("dbg", "t", desc="python", rel_dir="a/dbg"),
                          _entry("dbg", "t", desc="rust", rel_dir="b/dbg")]))
        with pytest.raises(BoostError) as ei:
            catalog.resolve_one("t:dbg")
        assert ei.value.message.startswith("'dbg' matches 2 ")


class TestSearchRanking:
    def test_tier_ordering_and_exact_scores(self):
        entries = [
            _entry("styler", "t", desc="code fmt utility"),
            _entry("auto-fmt-x", "t"),
            _entry("unrelated", "t", desc="nothing here"),
            _entry("fmt", "t"),
            _entry("fmt-check", "t"),
        ]
        res = catalog.search("fmt", entries=entries)
        assert [e["name"] for e, _ in res] == ["fmt", "fmt-check", "auto-fmt-x", "styler"]
        assert [s for _, s in res] == [114, 94, 74, 38]

    def test_no_match_excluded(self):
        res = catalog.search("fmt", entries=[_entry("unrelated", "t", desc="none")])
        assert res == []

    def test_curated_tiebreak_beats_name_order(self):
        entries = [_entry("az-fmt", "t"), _entry("zz-fmt", "t", curated=True)]
        res = catalog.search("fmt", entries=entries)
        assert [(e["name"], s) for e, s in res] == [("zz-fmt", 77), ("az-fmt", 74)]

    def test_equal_scores_sorted_by_name(self):
        entries = [_entry("beta-fmt", "t"), _entry("alpha-fmt", "t")]
        res = catalog.search("fmt", entries=entries)
        assert [(e["name"], s) for e, s in res] == [("alpha-fmt", 74), ("beta-fmt", 74)]

    def test_empty_query_is_prefix_of_everything(self):
        # "" is a prefix of every name, so an empty query ranks all entries
        # at the prefix tier (80), name-sorted — list-all semantics.
        entries = [_entry("bbb", "t", desc="x"), _entry("aaa", "t")]
        res = catalog.search("", entries=entries)
        assert [(e["name"], s) for e, s in res] == [("aaa", 80), ("bbb", 80)]

    def test_query_case_insensitive(self):
        res = catalog.search("FMT", entries=[_entry("fmt", "t")])
        assert [(e["name"], s) for e, s in res] == [("fmt", 114)]

    def test_multi_token_query_splits_on_separators(self):
        res = catalog.search("alpha beta", entries=[_entry("alpha-beta", "t")])
        assert [(e["name"], s) for e, s in res] == [("alpha-beta", 28)]

    def test_meta_only_match_scores_2(self):
        e = _entry("x", "t", meta={"tags": ["security"]})
        res = catalog.search("security", entries=[e])
        assert [(m["name"], s) for m, s in res] == [("x", 2)]

    def test_meta_key_still_matches(self):
        # keys are part of the search text, just as json.dumps(meta) included
        # them — a query for a frontmatter key name still scores.
        e = _entry("x", "t", meta={"framework": "react"})
        assert [(m["name"], s) for m, s in catalog.search("framework", entries=[e])] \
            == [("x", 2)]

    def test_meta_nested_value_matches(self):
        e = _entry("x", "t", meta={"requires": [{"skill": "planning"}]})
        assert [(m["name"], s) for m, s in catalog.search("planning", entries=[e])] \
            == [("x", 2)]

    def test_desc_bonus_adds_to_name_score_not_replaces(self):
        # An entry that matches BOTH the name and the description must accrue the
        # description bonus (+30) ON TOP of the name-tier score, never reset to
        # it. name "fmt-tool" starts-with "fmt" (+80) + token "fmt" in name (+12)
        # + desc "a fmt helper" contains "fmt" (+30) + token in desc (+6) + token
        # in blob (+2) = 130. (Pins `score += 30`, not `score = 30`.)
        e = _entry("fmt-tool", "t", desc="a fmt helper")
        assert [(m["name"], s) for m, s in catalog.search("fmt", entries=[e])] \
            == [("fmt-tool", 130)]


class TestMetaText:
    def test_flattens_keys_and_values_lowercased(self):
        assert catalog._meta_text({"Tags": ["AI", "ML"]}) == "tags ai ml"

    def test_nested_dicts_and_lists(self):
        out = catalog._meta_text({"a": {"b": [1, "Two"]}})
        assert out == "a b 1 two"

    def test_skips_none_and_empty(self):
        assert catalog._meta_text({}) == ""
        assert catalog._meta_text(None) == ""
        assert catalog._meta_text({"k": None}) == "k"

    def test_description_only_match(self):
        e = _entry("styler", "t", desc="handles jira tickets")
        res = catalog.search("jira", entries=[e])
        assert [(m["name"], s) for m, s in res] == [("styler", 38)]

    def test_curated_entry_with_no_match_is_excluded(self):
        res = catalog.search("xyzzy", entries=[_entry("unrelated", "t", curated=True)])
        assert res == []


class TestSearchBlobPrecompute:
    def test_search_blob_flattens_name_desc_meta_lowercased(self):
        blob = catalog._search_blob(
            "Foo-Bar", "Desc Here", {"tags": ["Alpha"], "x": "On"})
        assert blob == "foo-bar desc here tags alpha x on"

    def test_search_blob_tolerates_empty_description(self):
        assert catalog._search_blob("name", "", {}) == "name  "
        assert catalog._search_blob("name", None, {}) == "name  "

    def test_make_entry_precomputes_blob(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text("body", encoding="utf-8")
        e = catalog._make_entry(
            tmp_path, f, "skill", "fallback-name", "tap", False,
            {"tags": ["Kubernetes"]}, "Handles clusters")
        assert e["search_blob"] == "fallback-name handles clusters tags kubernetes"

    def test_search_reads_precomputed_blob_not_live_meta(self):
        # Token lives only in search_blob, not in meta -> a match proves search
        # consumed the precomputed blob rather than re-walking meta.
        e = _entry("x", "t", meta={})
        e["search_blob"] = "x  zzsentinel"
        res = catalog.search("zzsentinel", entries=[e])
        assert [(m["name"], s) for m, s in res] == [("x", 2)]

    def test_search_falls_back_when_blob_absent(self):
        # Older caches / raw entries have no blob -> recompute from meta.
        e = _entry("x", "t", meta={"tags": ["fallbackword"]})
        assert "search_blob" not in e
        res = catalog.search("fallbackword", entries=[e])
        assert [(m["name"], s) for m, s in res] == [("x", 2)]


class TestLintTargets:
    """`boost lint` scores a SKILL.md directory, so only skills are lintable.

    Rules and workflows are single files with no SKILL.md, so linting them
    scored every one a 0 with a bogus "missing SKILL.md" — the tap's score was
    a function of how many rules it shipped. They are now split out and
    reported as skipped rather than scored or silently dropped.
    """

    ROOT = Path("/taps/demo")

    def _e(self, name, kind=None, rel_dir="."):
        e = {"name": name, "rel_dir": rel_dir}
        if kind is not None:
            e["kind"] = kind
        return e

    def test_skills_become_targets_rules_and_workflows_are_skipped(self):
        entries = [self._e("brainstorm", "skill", "skills/brainstorm"),
                   self._e("py-style", "rule", "rules/py-style.mdc"),
                   self._e("ship-it", "workflow", "commands/ship-it.md")]
        targets, skipped = catalog.lint_targets(entries, self.ROOT)
        assert targets == [("brainstorm", self.ROOT / "skills/brainstorm")]
        # Exact dicts, not just a count: the kind is what the message prints,
        # so a mutant swapping it must fail here.
        assert skipped == [{"name": "py-style", "kind": "rule"},
                           {"name": "ship-it", "kind": "workflow"}]

    def test_a_kindless_entry_counts_as_a_skill(self):
        # Caches written before kinds existed have no `kind`. Treating those
        # as non-skills would make `lint` silently skip everything.
        targets, skipped = catalog.lint_targets([self._e("legacy")], self.ROOT)
        assert targets == [("legacy", self.ROOT)]
        assert skipped == []

    def test_rel_dir_dot_is_the_tap_root_itself(self):
        targets, _ = catalog.lint_targets([self._e("top", "skill", ".")],
                                          self.ROOT)
        assert targets == [("top", self.ROOT)]      # not ROOT/"."

    def test_nested_rel_dir_is_joined(self):
        targets, _ = catalog.lint_targets(
            [self._e("deep", "skill", "a/b/c")], self.ROOT)
        assert targets == [("deep", self.ROOT / "a" / "b" / "c")]

    def test_names_filter_selects_only_the_named_skill(self):
        entries = [self._e("one", "skill", "one"), self._e("two", "skill", "two")]
        targets, skipped = catalog.lint_targets(entries, self.ROOT, ["two"])
        assert targets == [("two", self.ROOT / "two")]
        assert skipped == []

    def test_an_explicitly_named_rule_is_reported_not_dropped(self):
        # The whole point of returning `skipped`: asking to lint a rule by name
        # must say why nothing happened, not exit silently having done nothing.
        entries = [self._e("one", "skill", "one"),
                   self._e("py-style", "rule", "rules/py-style.mdc")]
        targets, skipped = catalog.lint_targets(entries, self.ROOT, ["py-style"])
        assert targets == []
        assert skipped == [{"name": "py-style", "kind": "rule"}]

    def test_an_empty_names_list_does_not_filter_everything_out(self):
        # `args.names or None` yields None for [], but guard the falsy case
        # here too: a mutant turning `if wanted` into `if wanted is not None`
        # would filter every entry away and lint nothing.
        entries = [self._e("one", "skill", "one")]
        assert catalog.lint_targets(entries, self.ROOT, [])[0] == \
            [("one", self.ROOT / "one")]

    def test_order_is_preserved(self):
        entries = [self._e(n, "skill", n) for n in ("c", "a", "b")]
        targets, _ = catalog.lint_targets(entries, self.ROOT)
        assert [n for n, _p in targets] == ["c", "a", "b"]

    def test_no_entries_is_two_empty_lists(self):
        assert catalog.lint_targets([], self.ROOT) == ([], [])

    def test_a_string_tap_root_works_like_a_path(self):
        # cmd_lint passes tap.path (a Path), but the signature accepts str and
        # the join must not become string concatenation.
        targets, _ = catalog.lint_targets([self._e("s", "skill", "d")],
                                          "/taps/demo")
        assert targets == [("s", Path("/taps/demo/d"))]
