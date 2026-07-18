"""Unit tests: boost_cli/core/catalog.py — scanning, tap caches, lookup, search."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from boost_cli.core import catalog, config, paths, registry
from boost_cli.errors import BoostError

FIXTURE_NAMES = ["brainstorming", "commit-messages", "cowboy-coding",
                 "jira-integration", "tdd-workflow"]


def write_skill(dirpath, fm=None, body="Some body line\n"):
    dirpath.mkdir(parents=True, exist_ok=True)
    text = (fm + "\n" if fm else "") + body
    (dirpath / "SKILL.md").write_text(text)


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
            json.dumps({"skills": entries}))


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
            "---\ndescription: React best practices\nglobs: '*.tsx'\n---\n\nUse hooks.\n")
        (e,) = catalog.scan_dir(root)
        assert e["kind"] == "rule"
        assert e["name"] == "react"
        assert e["description"] == "React best practices"
        assert e["skill_md"] == ".cursor/rules/react.mdc"
        assert e["rel_dir"] == ".cursor/rules"

    def test_cursorrules_dotfile_named_after_parent_dir(self, tmp_path):
        root = tmp_path / "tap"
        (root / "nextjs").mkdir(parents=True)
        (root / "nextjs" / ".cursorrules").write_text("You are a Next.js expert.\n")
        (e,) = catalog.scan_dir(root)
        assert e["kind"] == "rule"
        assert e["name"] == "nextjs"
        assert e["description"] == "You are a Next.js expert."

    def test_windsurfrules_and_clinerules_indexed(self, tmp_path):
        root = tmp_path / "tap"
        (root / "a").mkdir(parents=True)
        (root / "b").mkdir(parents=True)
        (root / "a" / ".windsurfrules").write_text("windsurf rule\n")
        (root / "b" / ".clinerules").write_text("cline rule\n")
        kinds = {e["name"]: e["kind"] for e in catalog.scan_dir(root)}
        assert kinds == {"a": "rule", "b": "rule"}

    def test_workflow_under_commands_dir(self, tmp_path):
        root = tmp_path / "tap"
        (root / "commands").mkdir(parents=True)
        (root / "commands" / "review.md").write_text(
            "---\ndescription: Review the diff\n---\n\nDo a review.\n")
        (e,) = catalog.scan_dir(root)
        assert e["kind"] == "workflow"
        assert e["name"] == "review"

    def test_workflow_under_claude_agents_dir(self, tmp_path):
        root = tmp_path / "tap"
        (root / ".claude" / "agents").mkdir(parents=True)
        (root / ".claude" / "agents" / "backend.md").write_text(
            "---\nname: backend-architect\ndescription: Designs APIs\n---\n\nBody.\n")
        (e,) = catalog.scan_dir(root)
        assert e["kind"] == "workflow"
        assert e["name"] == "backend-architect"

    def test_root_subagent_signature_detected(self, tmp_path):
        root = tmp_path / "tap"
        root.mkdir(parents=True)
        (root / "code-reviewer.md").write_text(
            "---\nname: code-reviewer\ndescription: Reviews code\ntools: Read, Grep\n---\n\nX.\n")
        (e,) = catalog.scan_dir(root)
        assert e["kind"] == "workflow"
        assert e["name"] == "code-reviewer"

    def test_plain_markdown_and_docs_not_indexed(self, tmp_path):
        root = tmp_path / "tap"
        root.mkdir(parents=True)
        (root / "README.md").write_text("# Readme\n\nHello.\n")
        (root / "notes.md").write_text("# Notes\n\nJust prose, no frontmatter.\n")
        (root / "commands").mkdir()
        (root / "commands" / "README.md").write_text("# Commands index\n")
        assert catalog.scan_dir(root) == []

    def test_reference_files_inside_skill_dir_not_double_counted(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "skills" / "s", "---\nname: s\n---")
        # a skill that ships a bundled rule/command as reference material
        (root / "skills" / "s" / "extra.mdc").write_text("bundled rule\n")
        (root / "skills" / "s" / "commands").mkdir()
        (root / "skills" / "s" / "commands" / "helper.md").write_text(
            "---\ndescription: helper\n---\nx\n")
        entries = catalog.scan_dir(root)
        assert [e["name"] for e in entries] == ["s"]
        assert entries[0]["kind"] == "skill"

    def test_unreadable_rule_file_skipped(self, tmp_path):
        root = tmp_path / "tap"
        (root / "a").mkdir(parents=True)
        (root / "b").mkdir(parents=True)
        (root / "a" / "locked.mdc").write_text("---\ndescription: x\n---\n")
        (root / "b" / "open.mdc").write_text("---\ndescription: y\n---\n")
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

    def test_mixed_kinds_all_present(self, tmp_path):
        root = tmp_path / "tap"
        write_skill(root / "skills" / "s", "---\nname: s\n---")
        (root / "rules").mkdir()
        (root / "rules" / "py.mdc").write_text("---\ndescription: python\n---\nx\n")
        (root / "commands").mkdir()
        (root / "commands" / "ship.md").write_text("---\ndescription: ship it\n---\nx\n")
        kinds = sorted(e["kind"] for e in catalog.scan_dir(root))
        assert kinds == ["rule", "skill", "workflow"]


class TestTapCaches:
    def test_rebuild_writes_cache(self, sandbox, fixture_tap_src):
        tap = registry.add(str(fixture_tap_src))
        entries = catalog.rebuild_tap(tap)
        assert [e["name"] for e in entries] == FIXTURE_NAMES
        cache = json.loads(tap.cache_file.read_text())
        assert cache["tap"] == "fixture-tap"
        assert cache["url"] == tap.url
        assert re.fullmatch(r"[0-9a-f]{40}", cache["commit"])
        assert len(cache["skills"]) == 5
        jira = [e for e in entries if e["name"] == "jira-integration"][0]
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
        tap.cache_file.write_text(json.dumps({"skills": [{"name": "cached-skill"}]}))
        assert catalog.load_tap(tap) == [{"name": "cached-skill"}]

    def test_load_tap_rebuild_flag_bypasses_cache(self, sandbox, fixture_tap_src):
        tap = registry.add(str(fixture_tap_src))
        tap.cache_file.write_text(json.dumps({"skills": [{"name": "stale"}]}))
        entries = catalog.load_tap(tap, rebuild=True)
        assert [e["name"] for e in entries] == FIXTURE_NAMES
        assert "brainstorming" in tap.cache_file.read_text()  # cache rewritten

    def test_load_tap_corrupt_cache_rebuilds_when_cloned(self, sandbox, fixture_tap_src):
        tap = registry.add(str(fixture_tap_src))
        tap.cache_file.write_text("{not json")
        entries = catalog.load_tap(tap)
        assert [e["name"] for e in entries] == FIXTURE_NAMES

    def test_load_tap_corrupt_cache_uncloned_empty(self, sandbox):
        paths.ensure_dirs()
        tap = registry.Tap(name="fake", url="")
        tap.cache_file.write_text("{not json")
        assert catalog.load_tap(tap) == []

    def test_load_tap_no_cache_uncloned_empty(self, sandbox):
        assert catalog.load_tap(registry.Tap(name="fake", url="")) == []


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

    def test_description_only_match(self):
        e = _entry("styler", "t", desc="handles jira tickets")
        res = catalog.search("jira", entries=[e])
        assert [(m["name"], s) for m, s in res] == [("styler", 38)]

    def test_curated_entry_with_no_match_is_excluded(self):
        res = catalog.search("xyzzy", entries=[_entry("unrelated", "t", curated=True)])
        assert res == []
