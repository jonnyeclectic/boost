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


def _entry(name, tap, desc="", curated=False, version="1.0.0", meta=None):
    return {"name": name, "description": desc, "version": version, "tap": tap,
            "curated": curated, "rel_dir": ".", "skill_md": "SKILL.md",
            "meta": meta or {}}


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


class TestAllEntriesAndFind:
    def test_all_entries_config_order(self, sandbox):
        _fake_taps(
            ("zeta", [_entry("z1", "zeta"), _entry("z2", "zeta")]),
            ("alpha", [_entry("a1", "alpha")]),
        )
        assert [e["name"] for e in catalog.all_entries()] == ["z1", "z2", "a1"]

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
