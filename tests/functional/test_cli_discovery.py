# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: Discovery & Search commands, in-process.

search / index / discover / recommend / browse / trending / stats / count,
asserting exact output shapes, exit codes, and on-disk cache effects.
"""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import time
import types

import pytest

from boost_cli.core import output, paths, util


def _curses_available() -> bool:
    """False on Windows: curses isn't in the stdlib there, and boost degrades
    to the plain-catalog fallback (see cmd_browse) rather than shipping the
    third-party windows-curses package boost's zero-dependency design avoids."""
    try:
        import curses  # noqa: F401
    except ImportError:
        return False
    return True


def _vec_loadable() -> bool:
    """True only if sqlite-vec both imports, loads, and can run a bound-LIMIT
    KNN query (see test_dense.py — some sqlite3/sqlite-vec combinations load
    fine but reject that query shape)."""
    try:
        import sqlite_vec  # type: ignore
    except ImportError:
        return False
    con = sqlite3.connect(":memory:")
    try:
        con.enable_load_extension(True)
        sqlite_vec.load(con)
        con.execute("select vec_version()").fetchone()
        con.execute("create virtual table t using vec0(embedding float[3])")
        con.execute("insert into t(rowid, embedding) values (1, ?)",
                    (sqlite_vec.serialize_float32([1.0, 0.0, 0.0]),))
        con.execute(
            "select rowid, distance from t where embedding match ? "
            "order by distance limit ?",
            (sqlite_vec.serialize_float32([1.0, 0.0, 0.0]), 5)).fetchall()
        return True
    except Exception:
        return False
    finally:
        con.close()


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t", *list(args)], cwd=str(cwd), check=True, capture_output=True)


def _make_tap(root):
    """A tiny extra tap whose skills match common stack keywords."""
    skills = {
        "python-style": ("Idiomatic Python formatting with pytest fixtures",
                         "[python, pytest]"),
        "react-patterns": ("Component patterns for React and TypeScript apps",
                           "[react, javascript]"),
    }
    for name, (desc, tags) in skills.items():
        d = root / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: %s\ndescription: %s\nversion: 1.0.0\ntags: %s\n---\n\n"
            "# %s\n\nBody text.\n" % (name, desc, tags, name), encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "skills")
    return root


# ---------------------------------------------------------------- search

class TestSearch:
    def test_defaults_to_bm25_without_reindex(self, boost, tapped):
        # RAG is the default: the first search auto-builds the full-content
        # index, so a fresh user gets BM25 ranking without running `boost
        # reindex` first.
        r = boost("search", "commit", "messages")
        assert "ranked by full-content BM25" in r.out
        assert "commit-messages" in r.out

    def test_multiword_ranks_exact_token_hits_first(self, boost, tapped):
        r = boost("search", "commit", "messages")
        assert "commit-messages" in r.out
        assert "jira-integration" in r.out
        assert r.out.index("commit-messages") < r.out.index("jira-integration")
        assert "2 matches · ranked by full-content BM25" in r.out

    def test_results_show_relevance_meter(self, boost, tapped):
        # D07: the ranking is visible as a per-result meter; the top exact
        # match earns a full bar.
        r = boost("search", "commit", "messages")
        assert "▰" in r.out
        top = next(l for l in r.out.splitlines() if "commit-messages" in l)
        assert "▰▰▰▰" in top

    def test_limit_caps_rows_but_footer_counts_all(self, boost, tapped):
        r = boost("search", "workflow", "--limit", "1")
        assert "tdd-workflow" in r.out
        assert "jira-integration" not in r.out
        assert "2 matches · ranked by full-content BM25" in r.out

    def test_single_match_uses_singular_footer(self, boost, tapped):
        r = boost("search", "brainstorming")
        assert "1 match · ranked by full-content BM25" in r.out
        assert "1 matches" not in r.out

    def test_json_is_pure_and_scored(self, boost, tapped):
        r = boost("search", "brainstorming", "--json")
        data = json.loads(r.out)  # whole stdout is one JSON document
        assert r.out.count("\n") == 1
        assert len(data) == 1
        assert data[0]["name"] == "brainstorming"
        assert data[0]["version"] == "1.4.0"
        assert data[0]["tap"] == "fixture-tap"
        # BM25 (the default engine) scores are positive floats, not the old
        # integer heuristic score — assert the shape, not a magic constant.
        assert isinstance(data[0]["score"], float) and data[0]["score"] > 0

    def test_a_stem_query_reaches_the_inflected_skill_and_says_so(
            self, boost, tapped):
        """`boost search brainstorm` used to return nothing at all while
        `brainstorming` returned the skill, and send the user off to search the
        whole of GitHub for something already in their catalogue."""
        r = boost("search", "brainstorm")
        assert "brainstorming" in r.out
        assert "no matches" not in r.out
        # The widening is stated, not silent — the user asked for one word and
        # is being shown results for another.
        assert "no exact match for 'brainstorm'" in r.out
        assert "brainstorming" in r.out

    def test_an_exact_query_is_not_annotated(self, boost, tapped):
        r = boost("search", "brainstorming")
        assert "brainstorming" in r.out
        assert "no exact match" not in r.out

    def test_a_query_matching_nothing_is_not_annotated_either(self, boost, tapped):
        r = boost("search", "zzzznothing")
        assert "no exact match" not in r.out
        assert "no matches for 'zzzznothing'" in r.out

    def test_no_taps_fails_with_hint(self, boost):
        r = boost("search", "anything", expect=1)
        assert "no taps configured — nothing to search" in r.err
        assert "boost tap --defaults" in r.err

    def test_no_matches_hints_discover(self, boost, tapped):
        r = boost("search", "zzzznothing")
        assert "no matches for 'zzzznothing'" in r.out
        assert "try `boost discover zzzznothing`" in r.out

    def test_no_matches_wears_the_standard_empty_state(self, boost, tapped):
        # The ○/→ grammar every other empty surface uses — "nothing here"
        # reads identically across commands.
        r = boost("search", "zzzznothing")
        assert "○ no matches" in r.out
        assert "→ try `boost discover" in r.out

    def test_rows_carry_the_kind_column(self, boost, tapped):
        r = boost("search", "commit", "messages")
        top = next(ln for ln in r.out.splitlines() if "commit-messages" in ln)
        assert "[skill]" in top

    def test_installed_names_get_a_dot(self, boost, tapped):
        boost("install", "brainstorming")
        r = boost("search", "brainstorming")
        top = next(ln for ln in r.out.splitlines() if "brainstorming" in ln)
        assert "●" in top

    def test_uninstalled_names_get_no_dot(self, boost, tapped):
        r = boost("search", "brainstorming")
        top = next(ln for ln in r.out.splitlines() if "brainstorming" in ln)
        assert "●" not in top

    def test_tap_column_appears_only_on_wide_terminals(self, boost, tapped,
                                                       monkeypatch):
        monkeypatch.setenv("COLUMNS", "100")
        wide = boost("search", "commit", "messages")
        top = next(ln for ln in wide.out.splitlines()
                   if "commit-messages" in ln)
        assert "fixture-tap" in top
        monkeypatch.setenv("COLUMNS", "60")
        narrow = boost("search", "commit", "messages")
        top = next(ln for ln in narrow.out.splitlines()
                   if "commit-messages" in ln)
        assert "fixture-tap" not in top

    def test_curated_tap_gets_star(self, boost, fixture_tap_src):
        boost("tap", fixture_tap_src, "--curated")
        r = boost("search", "brainstorming")
        assert "★ curated" in r.out

    def test_result_rows_clamp_to_terminal_width(self, boost, tapped,
                                                 monkeypatch):
        # D05: every result stays one line within the terminal width; a long
        # description is clipped instead of blowing up the pane.
        monkeypatch.setenv("COLUMNS", "60")
        r = boost("search", "workflow")
        ansi = re.compile(r"\x1b\[[0-9;]*m")
        rows = [ln for ln in r.out.splitlines() if ln and "ranked by" not in ln]
        assert rows
        for ln in rows:
            assert len(ansi.sub("", ln)) <= 60

    def test_smart_without_ai_warns_and_keeps_base_ranker(self, boost, tapped):
        # Without AI, --smart warns and keeps the base ranking — which is now
        # the BM25 default, not the heuristic.
        r = boost("search", "workflow", "--smart")
        assert "using the heuristic fallback" in " ".join(r.out.split())
        assert "ranked by full-content BM25" in r.out

    def test_smart_with_ai_reorders_and_credits_haiku(self, boost, tapped,
                                                      monkeypatch):
        monkeypatch.delenv("BOOST_NO_AI", raising=False)
        monkeypatch.setattr("boost_cli.core.ai.available", lambda: True)
        # BM25 for "workflow" returns tdd-workflow then jira-integration; the
        # rerank flips them.
        monkeypatch.setattr("boost_cli.core.ai.ask",
                            lambda *a, **k: '["jira-integration", "tdd-workflow"]')
        r = boost("search", "workflow", "--smart")
        assert r.out.index("jira-integration") < r.out.index("tdd-workflow")
        assert "ranked by Claude Haiku relevance" in r.out
        assert "full-content BM25" not in r.out

    def test_smart_with_junk_ai_reply_keeps_base_ranker(self, boost, tapped,
                                                        monkeypatch):
        monkeypatch.delenv("BOOST_NO_AI", raising=False)
        monkeypatch.setattr("boost_cli.core.ai.available", lambda: True)
        monkeypatch.setattr("boost_cli.core.ai.ask",
                            lambda *a, **k: "sorry, no list here")
        r = boost("search", "workflow", "--smart")
        # junk reply → keep the base BM25 order (tdd-workflow ranks first)
        assert r.out.index("tdd-workflow") < r.out.index("jira-integration")
        assert "ranked by full-content BM25" in r.out

    def test_index_build_failure_degrades_to_heuristic(self, boost, tapped,
                                                       monkeypatch):
        # If the on-demand index build fails, search must not crash — it falls
        # back to the frontmatter heuristic.
        def _boom(*a, **k):
            raise RuntimeError("disk full")
        monkeypatch.setattr("boost_cli.core.rag.build", _boom)
        r = boost("search", "commit", "messages")
        assert "commit-messages" in r.out
        assert "ranked by heuristic relevance" in r.out

    def test_limit_must_be_positive_int(self, boost, tapped):
        r = boost("search", "x", "--limit", "0", expect=2)
        assert "must be >= 1" in r.err
        r = boost("search", "x", "--limit", "abc", expect=2)
        assert "invalid int value: 'abc'" in r.err

    def test_collapse_near_duplicates_flag_is_a_no_op_without_a_dense_store(
            self, boost, tapped):
        # Opt-in and unwired into the default path (see
        # rag.NEAR_DUPLICATE_THRESHOLD): with no dense index built, the flag
        # must parse and change nothing about a plain BM25 search.
        with_flag = boost("search", "commit", "messages",
                          "--collapse-near-duplicates")
        without_flag = boost("search", "commit", "messages")
        assert with_flag.out == without_flag.out


class TestSearchCategoryFilter:
    """Every fixture skill's `category` (see catalog.CACHE_FORMAT 2) is its
    first frontmatter tag, since none declares an explicit `category`:
    tdd-workflow/cowboy-coding -> "testing", jira-integration -> "jira"."""

    def test_narrows_to_matching_category(self, boost, tapped):
        r = boost("search", "workflow", "--category", "testing", "--json")
        data = json.loads(r.out)
        assert [e["name"] for e in data] == ["tdd-workflow"]

    def test_case_insensitive(self, boost, tapped):
        r = boost("search", "workflow", "--category", "Testing", "--json")
        data = json.loads(r.out)
        assert [e["name"] for e in data] == ["tdd-workflow"]

    def test_no_filter_keeps_every_match(self, boost, tapped):
        r = boost("search", "workflow", "--json")
        data = json.loads(r.out)
        assert {e["name"] for e in data} == {"tdd-workflow", "jira-integration"}

    def test_filtering_to_nothing_reuses_the_standard_empty_state(self, boost, tapped):
        r = boost("search", "workflow", "--category", "no-such-category")
        assert "no matches for 'workflow'" in r.out


# ---------------------------------------------------------------- index

def _gh_page(items, total=7):
    return json.dumps({"total_count": total, "items": items})


def _gh_item(repo, path, desc="Skill repo"):
    return {"repository": {"full_name": repo, "description": desc},
            "path": path, "html_url": "https://github.com/%s/%s" % (repo, path)}


class TestIndex:
    def test_requires_gh(self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: None)
        r = boost("index", expect=1)
        assert "the GitHub CLI (gh) is required to build the index" in r.err
        assert "brew install gh" in r.err

    def test_builds_cache_from_gh_json(self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        seen = []

        def fake_run(cmd, **kw):
            seen.append(cmd)
            return types.SimpleNamespace(returncode=0, stderr="", stdout=_gh_page(
                [_gh_item("octo/skills", "skills/a/SKILL.md"),
                 _gh_item("acme/pack", "skills/b/SKILL.md", desc="")]))

        monkeypatch.setattr("boost_cli.commands.discovery.subprocess.run", fake_run)
        r = boost("index", "--limit", "100")
        assert ("indexed 2 skill files across 2 repos (GitHub reports 7 total)"
                in r.out)
        assert len(seen) == 1
        assert "search/code?q=filename:SKILL.md&per_page=100&page=1" in seen[0]
        data = json.loads((paths.cache_dir() / "discovery.json").read_text(encoding="utf-8"))
        assert data["github_total"] == 7
        assert data["items"] == [
            {"repo": "octo/skills", "path": "skills/a/SKILL.md",
             "url": "https://github.com/octo/skills/skills/a/SKILL.md",
             "description": "Skill repo"},
            {"repo": "acme/pack", "path": "skills/b/SKILL.md",
             "url": "https://github.com/acme/pack/skills/b/SKILL.md",
             "description": ""}]

    def test_query_narrows_the_sample(self, boost, sandbox, monkeypatch):
        """Without a query the index is a lucky draw; terms let it be aimed."""
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        seen = []
        monkeypatch.setattr(
            "boost_cli.commands.discovery.subprocess.run",
            lambda cmd, **kw: seen.append(cmd) or types.SimpleNamespace(
                returncode=0, stderr="", stdout=_gh_page(
                    [_gh_item("MemPalace/mempalace", "skills/mempalace/SKILL.md")])))
        boost("index", "memory", "palace", "--limit", "100")
        assert "filename:SKILL.md" in seen[0][-1]
        assert "memory" in seen[0][-1] and "palace" in seen[0][-1]
        data = json.loads((paths.cache_dir() / "discovery.json").read_text(encoding="utf-8"))
        # recorded, so a later reader can tell an aimed sample from a blind one
        assert data["query"] == "memory palace"

    def test_no_query_keeps_the_bare_filename_filter(self, boost, sandbox,
                                                     monkeypatch):
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        seen = []
        monkeypatch.setattr(
            "boost_cli.commands.discovery.subprocess.run",
            lambda cmd, **kw: seen.append(cmd) or types.SimpleNamespace(
                returncode=0, stderr="", stdout=_gh_page([])))
        boost("index", "--limit", "100")
        assert "search/code?q=filename:SKILL.md&per_page=100&page=1" in seen[0][-1]
        data = json.loads((paths.cache_dir() / "discovery.json").read_text(encoding="utf-8"))
        assert data["query"] == ""

    def test_respects_limit(self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        monkeypatch.setattr(
            "boost_cli.commands.discovery.subprocess.run",
            lambda cmd, **kw: types.SimpleNamespace(
                returncode=0, stderr="", stdout=_gh_page(
                    [_gh_item("octo/skills", "a/SKILL.md"),
                     _gh_item("octo/skills", "b/SKILL.md")])))
        r = boost("index", "--limit", "1")
        assert "indexed 1 skill files across 1 repos" in r.out
        data = json.loads((paths.cache_dir() / "discovery.json").read_text(encoding="utf-8"))
        assert len(data["items"]) == 1

    def test_gh_failure_on_first_page(self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        monkeypatch.setattr(
            "boost_cli.commands.discovery.subprocess.run",
            lambda cmd, **kw: types.SimpleNamespace(
                returncode=1, stdout="", stderr="gh: Not Found (HTTP 404)"))
        r = boost("index", "--limit", "50", expect=1)
        assert "GitHub code search failed" in r.err
        assert "gh: Not Found (HTTP 404)" in r.err

    def test_unparseable_json(self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        monkeypatch.setattr(
            "boost_cli.commands.discovery.subprocess.run",
            lambda cmd, **kw: types.SimpleNamespace(
                returncode=0, stdout="not json", stderr=""))
        r = boost("index", "--limit", "10", expect=1)
        assert "gh api returned unparseable JSON" in r.err

    def test_page2_failure_keeps_page1_items(self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        naps = []
        monkeypatch.setattr("boost_cli.commands.discovery.time.sleep", naps.append)
        calls = {"n": 0}

        def fake_run(cmd, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                items = [_gh_item("octo/r%d" % i, "s/SKILL.md")
                         for i in range(100)]
                return types.SimpleNamespace(returncode=0, stderr="",
                                             stdout=_gh_page(items, total=250))
            return types.SimpleNamespace(returncode=1, stdout="", stderr="boom")

        monkeypatch.setattr("boost_cli.commands.discovery.subprocess.run", fake_run)
        r = boost("index", "--limit", "200")
        assert "page 2 failed — keeping the 100 items fetched so far" in r.out
        assert "indexed 100 skill files across 100 repos (GitHub reports 250 total)" in r.out
        assert naps == [1]
        data = json.loads((paths.cache_dir() / "discovery.json").read_text(encoding="utf-8"))
        assert len(data["items"]) == 100

    def test_gh_oserror(self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")

        def boom(cmd, **kw):
            raise OSError("no exec")

        monkeypatch.setattr("boost_cli.commands.discovery.subprocess.run", boom)
        r = boost("index", expect=1)
        assert "gh api timed out on page 1" in r.err


class TestGithubSkillSearch:
    """The one-shot reach-out helper behind the boost_discover_github MCP tool."""

    def test_none_without_gh(self, sandbox, monkeypatch):
        from boost_cli.commands import discovery
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: None)
        assert discovery.github_skill_search("react") is None

    def test_returns_mapped_items(self, sandbox, monkeypatch):
        from boost_cli.commands import discovery
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        seen = []

        def fake_run(cmd, **kw):
            seen.append(cmd)
            return types.SimpleNamespace(returncode=0, stderr="", stdout=_gh_page(
                [_gh_item("octo/skills", "a/SKILL.md"),
                 _gh_item("acme/pack", "b/SKILL.md", desc="")]))

        monkeypatch.setattr("boost_cli.commands.discovery.subprocess.run", fake_run)
        out = discovery.github_skill_search("react hooks", limit=5)
        assert out == [
            {"repo": "octo/skills", "path": "a/SKILL.md",
             "url": "https://github.com/octo/skills/a/SKILL.md",
             "description": "Skill repo"},
            {"repo": "acme/pack", "path": "b/SKILL.md",
             "url": "https://github.com/acme/pack/b/SKILL.md", "description": ""}]
        # single page, user query appended (url-encoded) to the filename filter
        assert "per_page=5&page=1" in seen[0][-1]
        assert "filename:SKILL.md" in seen[0][-1]
        assert "react" in seen[0][-1] and "hooks" in seen[0][-1]

    def test_no_query_uses_bare_filename_filter(self, sandbox, monkeypatch):
        from boost_cli.commands import discovery
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        seen = []
        monkeypatch.setattr(
            "boost_cli.commands.discovery.subprocess.run",
            lambda cmd, **kw: seen.append(cmd) or types.SimpleNamespace(
                returncode=0, stderr="", stdout=_gh_page([])))
        assert discovery.github_skill_search() == []
        assert "q=filename:SKILL.md&per_page=20&page=1" in seen[0][-1]

    def test_limit_capped_and_sliced(self, sandbox, monkeypatch):
        from boost_cli.commands import discovery
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        seen = []
        items = [_gh_item("o/r%d" % i, "s/SKILL.md") for i in range(10)]
        monkeypatch.setattr(
            "boost_cli.commands.discovery.subprocess.run",
            lambda cmd, **kw: seen.append(cmd) or types.SimpleNamespace(
                returncode=0, stderr="", stdout=_gh_page(items)))
        out = discovery.github_skill_search("x", limit=3)
        assert len(out) == 3                       # sliced to per_page
        assert "per_page=3&page=1" in seen[0][-1]
        # a limit above the code-search cap is clamped to 100
        discovery.github_skill_search("x", limit=9999)
        assert "per_page=100&page=1" in seen[1][-1]

    def test_gh_failure_returns_none(self, sandbox, monkeypatch):
        from boost_cli.commands import discovery
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        monkeypatch.setattr(
            "boost_cli.commands.discovery.subprocess.run",
            lambda cmd, **kw: types.SimpleNamespace(
                returncode=1, stdout="", stderr="404"))
        assert discovery.github_skill_search("x") is None

    def test_bad_json_returns_none(self, sandbox, monkeypatch):
        from boost_cli.commands import discovery
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        monkeypatch.setattr(
            "boost_cli.commands.discovery.subprocess.run",
            lambda cmd, **kw: types.SimpleNamespace(
                returncode=0, stdout="not json", stderr=""))
        assert discovery.github_skill_search("x") is None

    def test_oserror_returns_none(self, sandbox, monkeypatch):
        from boost_cli.commands import discovery
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")

        def boom(cmd, **kw):
            raise OSError("no exec")

        monkeypatch.setattr("boost_cli.commands.discovery.subprocess.run", boom)
        assert discovery.github_skill_search("x") is None


# ---------------------------------------------------------------- discover

def _write_index(items, total=42, query=""):
    paths.ensure_dirs()
    (paths.cache_dir() / "discovery.json").write_text(json.dumps(
        {"generated": util.now_iso(), "github_total": total, "query": query,
         "items": items}), encoding="utf-8")


_ITEMS = [
    {"repo": "octo/skills", "path": "skills/tdd/SKILL.md",
     "url": "u1", "description": "tdd stuff"},
    {"repo": "acme/pack", "path": "skills/web/SKILL.md",
     "url": "u2", "description": "react helpers"},
    {"repo": "acme/pack", "path": "skills/db/SKILL.md",
     "url": "u3", "description": ""},
]


class TestDiscover:
    def test_without_index_hints_gh_missing(self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: None)
        r = boost("discover")
        assert "the discovery index has not been built yet" in r.out
        assert "install the GitHub CLI first" in r.out

    def test_without_index_hints_gh_present(self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        r = boost("discover")
        assert "build it with `boost index` (GitHub Code Search)" in r.out
        r = boost("discover", "--json")
        assert json.loads(r.out) == []

    def test_query_filters_and_footer_counts(self, boost, sandbox):
        _write_index(_ITEMS)
        r = boost("discover", "--local", "acme")
        assert "octo/skills" not in r.out
        assert "skills/web/SKILL.md" in r.out and "skills/db/SKILL.md" in r.out
        # "when this index was built" is load-bearing: `boost index` now takes a
        # query, so github_total is the total for *that* query at *that* time,
        # not a live GitHub-wide count.
        assert ("2 of 3 indexed skills · GitHub reported ~42 total when this "
                "index was built") in r.out
        # multi-token queries AND together
        r = boost("discover", "--local", "acme", "web")
        assert "skills/db/SKILL.md" not in r.out
        assert "1 of 3 indexed skills" in r.out

    def test_the_footer_names_the_query_the_index_was_built_with(self, boost,
                                                                 sandbox):
        _write_index(_ITEMS, query="react")
        r = boost("discover", "--local", "acme")
        assert "~42 total matching 'react' when this index was built" in r.out

    def test_json_purity(self, boost, sandbox):
        _write_index(_ITEMS)
        r = boost("discover", "--local", "acme", "--json")
        rows = json.loads(r.out)
        assert r.out.count("\n") == 1
        assert [{k: v for k, v in row.items() if k != "source"}
                for row in rows] == _ITEMS[1:]
        assert {row["source"] for row in rows} == {"local-index"}

    def test_no_match_names_what_it_searched(self, boost, sandbox):
        """The miss must not read as a verdict on GitHub — it only saw the cache."""
        _write_index(_ITEMS)
        r = boost("discover", "--local", "zzz")
        assert "no locally indexed skills match 'zzz'" in r.out
        assert "a local sample of 3 entries, not GitHub" in r.out
        assert "drop --local to search GitHub itself" in r.out

    def test_limit(self, boost, sandbox):
        _write_index(_ITEMS)
        r = boost("discover", "--limit", "1")
        assert "1 of 3 indexed skills" in r.out
        assert "acme/pack" not in r.out

    def test_corrupt_index(self, boost, sandbox):
        paths.ensure_dirs()
        (paths.cache_dir() / "discovery.json").write_text("{broken", encoding="utf-8")
        r = boost("discover", expect=1)
        assert "the discovery index is corrupt" in r.err


class TestDiscoverLive:
    """A query asks about GitHub, so it must reach GitHub — no index required.

    This is the parity the MCP `boost_discover_github` tool always had and the
    CLI did not: before, a query only ever searched whatever untargeted sample
    `boost index` happened to cache.
    """

    def _gh(self, monkeypatch, items, rc=0, stdout=None):
        seen = []
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        monkeypatch.setattr(
            "boost_cli.commands.discovery.subprocess.run",
            lambda cmd, **kw: seen.append(cmd) or types.SimpleNamespace(
                returncode=rc, stderr="",
                stdout=_gh_page(items) if stdout is None else stdout))
        return seen

    def test_query_hits_github_without_any_index(self, boost, sandbox, monkeypatch):
        seen = self._gh(monkeypatch, [_gh_item("MemPalace/mempalace",
                                               "skills/mempalace/SKILL.md")])
        r = boost("discover", "mempalace")
        assert "MemPalace/mempalace" in r.out
        assert "live GitHub Code Search" in r.out
        assert "boost tap <repo>" in r.out
        # the user's terms reached the code-search query
        assert "mempalace" in seen[0][-1] and "filename:SKILL.md" in seen[0][-1]

    def test_repo_rows_collapse_mirrored_copies(self, boost, sandbox, monkeypatch):
        """One repo mirroring a skill per agent is one row, not four."""
        self._gh(monkeypatch, [
            _gh_item("MemPalace/mempalace", "skills/mempalace/SKILL.md"),
            _gh_item("MemPalace/mempalace", ".claude-plugin/skills/mempalace/SKILL.md"),
            _gh_item("MemPalace/mempalace", ".codex-plugin/skills/mempalace/SKILL.md"),
            _gh_item("octo/other", "skills/x/SKILL.md")])
        r = boost("discover", "mempalace")
        assert "2 repo(s)" in r.out
        assert "MemPalace/mempalace (3)" in r.out
        # the shallowest copy is the one worth naming, not whichever hit first
        assert "skills/mempalace/SKILL.md" in r.out
        assert ".codex-plugin" not in r.out

    def test_the_shallowest_copy_wins_whatever_the_hit_order(self, boost, sandbox,
                                                             monkeypatch):
        """The tie-break must survive an unsorted page.

        Code search does not rank by path depth, so feeding the shallowest hit
        first proves nothing — the naive "keep the first" implementation passes
        that too. Deepest first is the ordering that separates them.
        """
        self._gh(monkeypatch, [
            _gh_item("MemPalace/mempalace", ".codex-plugin/a/b/skills/m/SKILL.md"),
            _gh_item("MemPalace/mempalace", ".claude-plugin/skills/m/SKILL.md"),
            _gh_item("MemPalace/mempalace", "skills/m/SKILL.md")])
        r = boost("discover", "m", "--json")
        row = json.loads(r.out)[0]
        assert row["path"] == "skills/m/SKILL.md", row
        assert row["files"] == 3

    def test_a_description_arrives_from_whichever_copy_has_one(self, boost, sandbox,
                                                               monkeypatch):
        # The first hit for a repo can be the one with an empty description;
        # the row should still end up carrying the text a later copy supplies.
        self._gh(monkeypatch, [
            _gh_item("o/r", "a/SKILL.md", desc=""),
            _gh_item("o/r", "b/SKILL.md", desc="the real blurb")])
        r = boost("discover", "x", "--json")
        assert json.loads(r.out)[0]["description"] == "the real blurb"

    def test_json_is_live_rows(self, boost, sandbox, monkeypatch):
        self._gh(monkeypatch, [_gh_item("o/r", "s/SKILL.md")])
        r = boost("discover", "x", "--json")
        data = json.loads(r.out)
        assert r.out.count("\n") == 1
        assert data[0]["repo"] == "o/r" and data[0]["files"] == 1
        assert data[0]["source"] == "github"

    def test_limit_counts_repos_not_code_search_files(self, boost, sandbox,
                                                      monkeypatch):
        """`--limit` is documented as "max rows", and a row is a repo.

        Passing it through as the code-search page size spent the budget on
        files instead: one large registry owns the top hits, so `--limit 25`
        returned a single row. Here 30 files across 5 repos, 20 of them from one
        registry — asking for 4 rows must give 4.
        """
        hits = [_gh_item("big/registry", "skills/s%d/SKILL.md" % i)
                for i in range(20)]
        hits += [_gh_item("r%d/pack" % i, "skills/x/SKILL.md") for i in range(4)]
        seen = self._gh(monkeypatch, hits)
        r = boost("discover", "x", "--limit", "4", "--json")
        assert len(json.loads(r.out)) == 4
        # and the whole page was requested, not `--limit` files
        assert "per_page=100" in seen[0][-1]

    def test_local_flag_never_touches_the_network(self, boost, sandbox, monkeypatch):
        def boom(cmd, **kw):
            raise AssertionError("--local must not shell out to gh")

        # gh present, or the guard below is vacuous: without a query reaching
        # `_discover_live`, `boom` is never called and the test passes on any
        # machine that simply has no gh installed.
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        monkeypatch.setattr("boost_cli.commands.discovery.subprocess.run", boom)
        _write_index(_ITEMS)
        r = boost("discover", "--local", "acme")
        assert "2 of 3 indexed skills" in r.out

    def test_bare_discover_still_browses_the_cache(self, boost, sandbox, monkeypatch):
        """No query is a browse request, and browsing the cache is free."""
        def boom(cmd, **kw):
            raise AssertionError("a query-less browse must not shell out to gh")

        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: "/usr/bin/gh")
        monkeypatch.setattr("boost_cli.commands.discovery.subprocess.run", boom)
        _write_index(_ITEMS)
        r = boost("discover")
        assert "3 of 3 indexed skills" in r.out

    def test_empty_github_result_is_reported_not_masked(self, boost, sandbox,
                                                        monkeypatch):
        self._gh(monkeypatch, [])
        _write_index(_ITEMS)
        r = boost("discover", "acme")
        assert "no SKILL.md repositories on GitHub match 'acme'" in r.out
        # GitHub is authoritative for "what exists on GitHub" — a stale cache
        # hit must not be dressed up as a live answer.
        assert "skills/web/SKILL.md" not in r.out

    def test_gh_failure_falls_back_to_the_index(self, boost, sandbox, monkeypatch):
        self._gh(monkeypatch, [], rc=1)
        _write_index(_ITEMS)
        r = boost("discover", "acme")
        # The notice belongs on stderr — see test_json_survives_a_fallback.
        assert "GitHub code search failed" in r.err
        assert "2 of 3 indexed skills" in r.out

    def test_missing_gh_falls_back_to_the_index(self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: None)
        _write_index(_ITEMS)
        r = boost("discover", "acme")
        assert "GitHub search needs the `gh` CLI" in r.err
        assert "2 of 3 indexed skills" in r.out

    def test_a_fallback_miss_does_not_blame_a_flag_you_never_passed(
            self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: None)
        _write_index(_ITEMS)
        r = boost("discover", "zzz")
        assert "because GitHub could not be reached" in r.out
        # "drop --local" contradicts the warning above it for a user who never
        # typed --local, and is advice they cannot act on.
        assert "drop --local" not in r.out

    def test_json_survives_a_fallback_and_says_which_corpus_answered(
            self, boost, sandbox, monkeypatch):
        """A script must be able to tell the two answers apart.

        Suppressing the warning kept stdout parseable but destroyed the only
        signal, so "GitHub has no matches" and "GitHub was never searched" came
        back identical — in *different row shapes*. Warning to stderr, `source`
        on every row.
        """
        monkeypatch.setattr("boost_cli.commands.discovery.shutil.which",
                            lambda c: None)
        _write_index(_ITEMS)
        r = boost("discover", "acme", "--json")
        rows = json.loads(r.out)          # stdout still parses
        assert r.out.count("\n") == 1
        assert {row["source"] for row in rows} == {"local-index"}
        assert "GitHub search needs the `gh` CLI" in r.err

    def test_terminal_control_bytes_from_github_are_stripped(
            self, boost, sandbox, monkeypatch):
        """A repo name is attacker-chosen text rendered into a table.

        `\\x1b[1A\\x1b[2K` moves the cursor up a line and erases it, so one
        crafted field can rewrite rows already on screen — including the row
        naming a repo the user was about to tap.
        """
        self._gh(monkeypatch, [
            _gh_item("evil/\x1b[1A\x1b[2Ktrusted-repo", "skills/x/SKILL.md")])
        r = boost("discover", "x")
        assert "\x1b[1A" not in r.out and "\x1b[2K" not in r.out
        assert "trusted-repo" in r.out


# ---------------------------------------------------------------- recommend

@pytest.fixture()
def stack_tap(boost, tmp_path):
    tap = _make_tap(tmp_path / "stack-tap")
    boost("tap", tap)
    return tap


@pytest.fixture()
def react_project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "package.json").write_text(json.dumps(
        {"dependencies": {"react": "^18.2.0"}}), encoding="utf-8")
    (proj / "pyproject.toml").write_text("[tool.pytest.ini_options]\naddopts = '-q'\n", encoding="utf-8")
    return proj


class TestRecommend:
    def test_stack_line_and_suggestions(self, boost, stack_tap, react_project):
        r = boost("recommend", "--path", react_project)
        assert "stack: javascript, python · frameworks: pytest, react" in r.out
        assert r.out.index("python-style") < r.out.index("react-patterns")
        assert "because: pytest, python" in r.out
        assert "because: javascript, react" in r.out

    def test_json_purity(self, boost, stack_tap, react_project):
        r = boost("recommend", "--path", react_project, "--json")
        data = json.loads(r.out)
        assert r.out.count("\n") == 1
        assert data["stack"] == {
            "languages": ["javascript", "python"],
            "frameworks": ["pytest", "react"],
            "keywords": ["javascript", "pytest", "python", "react"]}
        recs = data["recommendations"]
        assert recs[0]["name"] == "python-style"
        assert recs[0]["score"] == 168
        assert recs[0]["because"] == ["pytest", "python"]
        assert recs[1]["name"] == "react-patterns"
        assert recs[1]["score"] == 132
        assert recs[1]["because"] == ["javascript", "react"]

    def test_detect_stack_kitchen_sink(self, boost, stack_tap, tmp_path):
        proj = tmp_path / "kitchen"
        proj.mkdir()
        (proj / "package.json").write_text("{not json", encoding="utf-8")     # still javascript
        (proj / "go.mod").write_text("module x\n", encoding="utf-8")
        (proj / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
        (proj / "Gemfile").write_text("gem 'rails'\n", encoding="utf-8")
        (proj / "tsconfig.json").write_text("{}", encoding="utf-8")
        (proj / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
        (proj / "pom.xml").write_text("<project>org.springframework</project>", encoding="utf-8")
        (proj / "a.tf").write_text("resource {}\n", encoding="utf-8")
        (proj / "b.tf").write_text("resource {}\n", encoding="utf-8")
        (proj / "x.py").write_text("pass\n", encoding="utf-8")
        (proj / "y.py").write_text("pass\n", encoding="utf-8")
        (proj / ".github" / "workflows").mkdir(parents=True)
        r = boost("recommend", "--path", proj, "--json")
        stack = json.loads(r.out)["stack"]
        assert stack["languages"] == ["go", "java", "javascript", "python",
                                      "ruby", "rust", "typescript"]
        assert stack["frameworks"] == ["rails", "spring"]
        assert stack["keywords"] == ["ci", "docker", "go", "java", "javascript",
                                     "python", "rails", "ruby", "rust",
                                     "spring", "terraform", "typescript"]

    def test_curated_fallback_when_stack_unmatched(self, boost, fixture_tap_src,
                                                   tmp_path):
        boost("tap", fixture_tap_src, "--curated")
        proj = tmp_path / "empty-proj"
        proj.mkdir()
        r = boost("recommend", "--path", proj)
        assert "no stack-specific matches — curated picks instead:" in r.out
        assert "brainstorming" in r.out

    def test_no_recommendations_at_all(self, boost, tapped, tmp_path):
        proj = tmp_path / "empty-proj"
        proj.mkdir()
        r = boost("recommend", "--path", proj)
        assert "no recommendations for this stack — try `boost search <keyword>`" in r.out

    def test_bad_path(self, boost, tapped):
        r = boost("recommend", "--path", "/definitely/not/here", expect=1)
        assert "no such directory" in r.err

    def test_no_taps(self, boost, tmp_path):
        r = boost("recommend", "--path", tmp_path, expect=1)
        assert "no skills in any tap to recommend from" in r.err

    def test_category_narrows_the_curated_fallback(self, boost, fixture_tap_src,
                                                    tmp_path):
        boost("tap", fixture_tap_src, "--curated")
        proj = tmp_path / "empty-proj"
        proj.mkdir()
        r = boost("recommend", "--path", proj, "--category", "testing")
        assert "tdd-workflow" in r.out or "cowboy-coding" in r.out
        assert "brainstorming" not in r.out
        assert "jira-integration" not in r.out
        assert "commit-messages" not in r.out

    def test_category_matching_nothing_raises_with_hint(self, boost, tapped,
                                                         tmp_path):
        proj = tmp_path / "empty-proj"
        proj.mkdir()
        r = boost("recommend", "--path", proj, "--category", "no-such-category",
                  expect=1)
        assert "no entries in category 'no-such-category'" in r.err

    def test_ai_picks(self, boost, stack_tap, react_project, monkeypatch):
        monkeypatch.delenv("BOOST_NO_AI", raising=False)
        monkeypatch.setattr("boost_cli.core.ai.available", lambda: True)
        monkeypatch.setattr(
            "boost_cli.core.ai.ask",
            lambda *a, **k: '[{"name": "python-style", "reason": "fits the stack"}]')
        r = boost("recommend", "--path", react_project)
        assert "AI picks" in r.out
        assert "python-style  fits the stack" in r.out


# ---------------------------------------------------------------- browse

class _FakeCurses:
    """Minimal curses stand-in for driving _browse_tui without a real TTY."""

    A_BOLD, A_DIM, A_REVERSE, A_NORMAL = 1, 2, 4, 0
    KEY_UP, KEY_DOWN, KEY_ENTER, KEY_BACKSPACE = 259, 258, 343, 263
    KEY_LEFT, KEY_RIGHT, KEY_NPAGE, KEY_PPAGE = 260, 261, 338, 339
    ACS_HLINE = ord("-")

    class error(Exception):
        pass

    def __init__(self, keys, size=(24, 80)):
        self.keys = list(keys)
        self.drawn = []
        self.size = size

    def curs_set(self, n):
        raise self.error("no cursor support")

    def timeout(self, ms):
        pass

    def wrapper(self, fn):
        fn(self)

    # screen protocol
    def getmaxyx(self):
        return self.size

    def erase(self):
        pass

    def addnstr(self, y, x, s, n, attr=0):
        self.drawn.append(s)

    def hline(self, *a):
        pass

    def refresh(self):
        pass

    def getch(self):
        # ESC, not "q": once space types into the query every printable key
        # types, so `q` is a character and only ESC still quits.
        return self.keys.pop(0) if self.keys else 27


class TestBrowse:
    def test_non_tty_prints_full_catalog(self, boost, tapped):
        r = boost("browse")
        assert "interactive mode needs a TTY — showing the full catalog" in r.out
        for name in ("brainstorming", "commit-messages", "cowboy-coding",
                     "jira-integration", "tdd-workflow"):
            assert name in r.out
        assert "5 skills · install with `boost install <name>`" in r.out

    def test_no_skills(self, boost, sandbox):
        r = boost("browse", expect=1)
        assert "no skills available to browse" in r.err

    def test_category_narrows_the_non_tty_fallback(self, boost, tapped):
        # tdd-workflow and cowboy-coding are the only fixture skills whose
        # (first-tag-derived) category is "testing".
        r = boost("browse", "--category", "testing")
        assert "tdd-workflow" in r.out
        assert "cowboy-coding" in r.out
        for name in ("brainstorming", "commit-messages", "jira-integration"):
            assert name not in r.out

    def test_category_case_insensitive(self, boost, tapped):
        r = boost("browse", "--category", "TESTING")
        assert "tdd-workflow" in r.out

    def test_category_matching_nothing_raises_with_hint(self, boost, tapped):
        r = boost("browse", "--category", "no-such-category", expect=1)
        assert "no entries in category 'no-such-category'" in r.err

    def test_tui_pick_installs(self, boost, tapped, monkeypatch):
        if not _curses_available():
            pytest.skip("curses not available on this platform")
        from boost_cli.commands import discovery
        tty = types.SimpleNamespace(isatty=lambda: True)
        monkeypatch.setattr(discovery, "sys",
                            types.SimpleNamespace(stdin=tty, stdout=tty))
        monkeypatch.setattr(
            discovery, "_browse_tui",
            lambda curses, entries: [next(e for e in entries
                                          if e["name"] == "brainstorming")])
        r = boost("browse")
        assert "installed brainstorming v1.4.0" in r.out
        assert "linked into: Claude Code, Windsurf, Cursor" in r.out
        assert (paths.store_dir() / "brainstorming" / "SKILL.md").is_file()

    def test_tui_quit_installs_nothing(self, boost, tapped, monkeypatch):
        from boost_cli.commands import discovery
        tty = types.SimpleNamespace(isatty=lambda: True)
        monkeypatch.setattr(discovery, "sys",
                            types.SimpleNamespace(stdin=tty, stdout=tty))
        monkeypatch.setattr(discovery, "_browse_tui", lambda curses, entries: None)
        r = boost("browse")
        assert "installed" not in r.out
        assert not (paths.store_dir() / "brainstorming").exists()

    def test_tui_pick_non_skill_does_not_crash(self, boost, tapped, monkeypatch):
        # browse lists rules/workflows too; picking one must not exit the TUI
        # with a fatal Error (regression: `boost browse` crashed on a workflow).
        # Workflows install now, but a pick whose source can't be read must still
        # surface a friendly non-fatal notice rather than crash the browser.
        if not _curses_available():
            pytest.skip("curses not available on this platform")
        from boost_cli.commands import discovery
        tty = types.SimpleNamespace(isatty=lambda: True)
        monkeypatch.setattr(discovery, "sys",
                            types.SimpleNamespace(stdin=tty, stdout=tty))
        workflow = {"name": "AGENT-playbook", "kind": "workflow",
                    "version": "1.0", "tap": "fixture-tap"}
        monkeypatch.setattr(discovery, "_browse_tui",
                            lambda curses, entries: [workflow])
        r = boost("browse")                       # default expect=0 → no crash
        assert "vanished from tap" in r.out       # friendly message, not Error:
        assert "boost update" in r.out            # the hint is shown
        assert "installed AGENT-playbook" not in r.out

    def test_tui_loop_with_fake_curses(self, boost, tapped):
        from boost_cli.commands import discovery
        from boost_cli.core import catalog

        entries = sorted(catalog.all_entries(), key=lambda e: e["name"])
        fake = _FakeCurses([ord("t"), _FakeCurses.KEY_DOWN, _FakeCurses.KEY_UP,
                            _FakeCurses.KEY_BACKSPACE, 10])
        picked = discovery._browse_tui(fake, entries)
        # Enter with nothing Tab-selected installs just the highlighted pick
        assert [e["name"] for e in picked] == ["brainstorming"]
        # the typed query is echoed after the "❯" prompt
        assert "t" in fake.drawn
        assert any("boost browse" in s for s in fake.drawn)
        # ESC quits without a pick
        assert discovery._browse_tui(_FakeCurses([27]), entries) is None

    def test_tab_selects_multiple_for_batch_install(self, boost, tapped):
        """Selection moved from SPACE to TAB so a space can reach the query."""
        from boost_cli.commands import discovery
        from boost_cli.core import catalog

        # alphabetical: brainstorming, commit-messages, cowboy-coding, ...
        entries = sorted(catalog.all_entries(), key=lambda e: e["name"])
        keys = [9,                                            # check brainstorming
                _FakeCurses.KEY_DOWN, _FakeCurses.KEY_DOWN,   # -> cowboy-coding
                9,                                            # check cowboy-coding
                10]                                           # Enter: install both
        fake = _FakeCurses(keys)
        picked = discovery._browse_tui(fake, entries)
        assert [e["name"] for e in picked] == ["brainstorming", "cowboy-coding"]
        assert any("2 selected" in s for s in fake.drawn)

    def test_a_batch_install_runs_one_at_a_time(self, boost, tapped):
        """Every `store.install` read-modify-writes the lock file, so two at
        once lost an entry — a Tab-select of two skills wrote both to disk and
        recorded one. Caught as a test that passed alone and failed 3 runs in 5
        in the suite, so the check is on overlap, not on the outcome."""
        import threading

        from boost_cli.commands import discovery
        from boost_cli.core import catalog

        live, overlapped = [], []
        gate = threading.Lock()

        def slow_install(entry):
            with gate:
                live.append(entry["name"])
                if len(live) > 1:
                    overlapped.append(tuple(live))
            time.sleep(0.05)
            with gate:
                live.remove(entry["name"])
            return types.SimpleNamespace(dest=paths.store_dir() / entry["name"],
                                         linked=[], conflicts=[])

        entries = sorted(catalog.all_entries(), key=lambda e: e["name"])
        keys = [9, _FakeCurses.KEY_DOWN, 9, _FakeCurses.KEY_DOWN, 9, 10]
        discovery._browse_tui(_FakeCurses(keys), entries, install=slow_install)
        assert not overlapped, "installs ran concurrently: %r" % overlapped

    def test_space_types_into_the_query_instead_of_selecting(self, boost, tapped):
        """The reported bug: SPACE was bound to select and excluded from the
        printable range, so two words could never be searched for."""
        from boost_cli.commands import discovery
        from boost_cli.core import catalog

        entries = sorted(catalog.all_entries(), key=lambda e: e["name"])
        fake = _FakeCurses([ord("t"), ord("d"), ord(" "), ord("w")])
        assert discovery._browse_tui(fake, entries) is None   # ESC quits
        assert any("td w" in s for s in fake.drawn), \
            "the space never reached the query"

    def test_a_two_word_query_narrows_to_the_matching_skill(self, boost, tapped):
        from boost_cli.commands import discovery
        from boost_cli.core import catalog

        entries = sorted(catalog.all_entries(), key=lambda e: e["name"])
        # "tdd" from the name, "workflow" from the name too — both must match
        fake = _FakeCurses([ord(c) for c in "tdd work"] + [10])
        picked = discovery._browse_tui(fake, entries)
        assert [e["name"] for e in picked] == ["tdd-workflow"]

    def test_tui_cards_show_type_tap_badges_and_descriptions(self, boost, tapped):
        from boost_cli.commands import discovery
        from boost_cli.core import catalog

        entries = sorted(catalog.all_entries(), key=lambda e: e["name"])
        # Wide enough for the whole badge row: on a narrow list pane the tap
        # badge is dropped from the tail by design, and the detail panel on the
        # right carries the tap instead.
        fake = _FakeCurses([], size=(24, 140))  # one draw, then ESC quits
        picked = discovery._browse_tui(fake, entries)
        assert picked is None
        assert "[skill]" in fake.drawn
        assert "[fixture-tap]" in fake.drawn
        assert "v1.0.2" in fake.drawn          # commit-messages' version
        assert "Conventional, atomic commit message discipline" in fake.drawn

    def test_the_detail_panel_carries_the_tap_when_the_badge_is_dropped(
            self, boost, tapped):
        """Nothing is lost on a narrow list — it moves to the right pane."""
        from boost_cli.commands import discovery
        from boost_cli.core import catalog

        entries = sorted(catalog.all_entries(), key=lambda e: e["name"])
        fake = _FakeCurses([], size=(24, 80))
        discovery._browse_tui(fake, entries)
        assert any("fixture-tap" in s for s in fake.drawn)


class TestBrowseAurora:
    """The curses browser paints itself in the single-source Aurora palette."""

    def test_curses_rgb1000_parity_with_tokens(self):
        from boost_cli.commands import discovery
        from boost_cli.core import output as out
        rgb = discovery._curses_rgb1000()
        assert set(rgb) == set(out.TOKENS)
        # cyan #40cbe3 scaled 0..255 -> 0..1000
        r, g, b = out.TOKENS["cyan"]
        assert rgb["cyan"] == (round(r / 255 * 1000), round(g / 255 * 1000),
                               round(b / 255 * 1000))
        for triple in rgb.values():
            assert all(0 <= c <= 1000 for c in triple)

    def test_nearest_base_covers_every_token(self):
        if not _curses_available():
            pytest.skip("curses not available on this platform")
        import curses

        from boost_cli.commands import discovery
        from boost_cli.core import output as out
        base = discovery._nearest_base(curses)
        assert set(base) == set(out.TOKENS)
        assert base["cyan"] == curses.COLOR_CYAN
        assert base["violet"] == base["pink"] == curses.COLOR_MAGENTA

    def test_match_positions(self):
        from boost_cli.core import browse
        assert browse.match_positions("bs", "brainstorm") == [0, 5]
        assert browse.match_positions("", "anything") == []
        assert browse.match_positions("zzz", "brainstorm") == []
        # left-to-right greedy: first 'o', then trailing 'm'
        assert browse.match_positions("om", "brainstorm") == [7, 9]

    def test_scrollbar_math(self):
        # The geometry moved into core (mutation-gated); the command layer
        # keeps a thin alias so both panes provably share one implementation.
        from boost_cli.commands import discovery
        from boost_cli.core import browse
        assert discovery._scrollbar is browse.scrollbar
        assert discovery._scrollbar(5, 10, 0) is None      # all fits
        assert discovery._scrollbar(10, 0, 0) is None      # no rows
        start, length = discovery._scrollbar(100, 10, 0)
        assert start == 0 and 1 <= length <= 10
        end_start, _ = discovery._scrollbar(100, 10, 90)   # scrolled to bottom
        assert end_start == 10 - length

    def test_grad_segments_partition(self):
        from boost_cli.commands import discovery
        from boost_cli.core import browse
        assert discovery._grad_segments is browse.rule_segments
        assert discovery._grad_segments(0) == []
        segs = discovery._grad_segments(10, 3)
        assert [s[1] for s in segs] == [4, 3, 3]           # sums to width
        assert sum(s[1] for s in segs) == 10
        assert [s[0] for s in segs] == [0, 4, 7]           # contiguous
        assert len(discovery._grad_segments(2, 3)) == 2    # n clamps to width

    @staticmethod
    def _color_curses(colors=256, can_change=True):
        class ColorCurses:
            COLOR_CYAN, COLOR_MAGENTA, COLOR_GREEN = 6, 5, 2
            COLOR_YELLOW, COLOR_RED = 3, 1
            COLORS = colors
            A_BOLD, A_DIM, A_REVERSE, A_NORMAL = 1, 2, 4, 0

            class error(Exception):
                pass

            def __init__(self):
                self.colors, self.pairs = {}, {}

            def start_color(self):
                pass

            def use_default_colors(self):
                pass

            def can_change_color(self):
                return can_change

            def init_color(self, slot, r, g, b):
                self.colors[slot] = (r, g, b)

            def init_pair(self, i, fg, bg):
                self.pairs[i] = (fg, bg)

            def color_pair(self, i):
                return i << 8

        return ColorCurses()

    def test_theme_upgrades_to_colour(self):
        from boost_cli.commands import discovery

        cc = self._color_curses()
        th = discovery._browse_theme(cc)
        # custom colours were defined from the parity-locked palette
        assert cc.colors[16] == discovery._curses_rgb1000()["cyan"]
        # title carries a colour pair plus bold, not bare monochrome
        assert th["title"] & cc.A_BOLD
        assert th["title"] & ~cc.A_BOLD
        # truecolor-capable terminals get the cyan -> violet -> pink rule
        assert len(th["rule"]) == 3
        assert len(set(th["rule"])) == 3

    def test_gradient_rule_collapses_to_one_hue_on_8_colour(self):
        """Mirrors out.gradient's 16-colour fallback: cyan/magenta/magenta
        would read as confetti, so a terminal that cannot define custom
        colours paints the whole rule in the one accent."""
        from boost_cli.commands import discovery

        cc = self._color_curses(colors=8, can_change=False)
        th = discovery._browse_theme(cc)
        assert len(th["rule"]) == 3
        assert len(set(th["rule"])) == 1
        assert th["rule"][0]                    # the accent pair, not bare 0

    def test_theme_falls_back_without_colour(self):
        from boost_cli.commands import discovery

        class MonoCurses:
            A_BOLD, A_DIM, A_REVERSE, A_NORMAL = 1, 2, 4, 0
        th = discovery._browse_theme(MonoCurses)
        assert th["title"] == MonoCurses.A_BOLD
        assert th["row_sel"] == MonoCurses.A_REVERSE
        assert th["rule"] == [MonoCurses.A_DIM] * 3


class TestBrowseCards:
    """Row badges, tap categories, and the boost-explain lazy description
    fallback that power the browse card list."""

    def test_tap_categories_reads_curated_registry_catalog(self, monkeypatch):
        from boost_cli.commands import discovery
        from boost_cli.core import config
        monkeypatch.setattr(config, "load_registry_catalog", lambda: [
            {"name": "a/b", "category": "framework"},
            {"name": "c/d", "category": ""},
            {"name": "e/f"},
        ])
        assert discovery._tap_categories() == {"a/b": "framework"}

    def test_kind_theme_key_maps_known_kinds_and_falls_back(self):
        from boost_cli.commands import discovery
        assert discovery._kind_theme_key("skill") == "badge_skill"
        assert discovery._kind_theme_key("rule") == "badge_rule"
        assert discovery._kind_theme_key("workflow") == "badge_workflow"
        assert discovery._kind_theme_key("whatever") == "badge_skill"

    def test_row_badges_order_and_category_only_when_known(self):
        from boost_cli.commands import discovery
        e = {"name": "x", "version": "1.0.0", "tap": "a/b", "kind": "rule"}
        with_category = discovery._row_badges(e, {"a/b": "framework"})
        assert with_category == [
            ("[rule]", "badge_rule"), ("v1.0.0", "version"),
            ("[a/b]", "tap"), ("[framework]", "badge_category")]
        without_category = discovery._row_badges(e, {})
        assert without_category == with_category[:3]  # category badge dropped

    def test_entry_source_path_resolves_within_the_tap(self, boost, tapped):
        from boost_cli.commands import discovery
        from boost_cli.core import catalog
        e = next(x for x in catalog.all_entries()
                 if x["name"] == "commit-messages")
        path = discovery._entry_source_path(e)
        assert path is not None and path.is_file()
        assert path.name == "SKILL.md"

    def test_entry_source_path_none_for_unknown_tap(self):
        from boost_cli.commands import discovery
        e = {"name": "x", "tap": "no/such-tap", "skill_md": "skills/x/SKILL.md"}
        assert discovery._entry_source_path(e) is None

    def test_lazy_description_falls_back_without_ai(self, boost, tapped):
        # the `sandbox` fixture sets BOOST_NO_AI=1, so ai.available() is False.
        from boost_cli.commands import discovery
        from boost_cli.core import catalog
        e = next(x for x in catalog.all_entries()
                 if x["name"] == "commit-messages")
        assert discovery._lazy_description(e) == "no description available"

    def test_lazy_description_uses_ai_when_available(self, boost, tapped, monkeypatch):
        from boost_cli.commands import discovery
        from boost_cli.core import ai, catalog
        monkeypatch.setattr(ai, "available", lambda: True)
        monkeypatch.setattr(ai, "ask", lambda *a, **k: "Writes tidy commits.\nextra")
        e = next(x for x in catalog.all_entries()
                 if x["name"] == "commit-messages")
        assert discovery._lazy_description(e) == "Writes tidy commits."


# ---------------------------------------------------------------- trending

class TestTrending:
    def test_no_installs_no_curated(self, boost, tapped):
        r = boost("trending")
        assert "curated picks (no local install data yet)" in r.out
        assert "no curated skills available — add taps with `boost tap --defaults`" in r.out

    def test_no_installs_curated_picks(self, boost, fixture_tap_src):
        boost("tap", fixture_tap_src, "--curated")
        r = boost("trending", "--limit", "2")
        assert "curated picks (no local install data yet)" in r.out
        assert "brainstorming" in r.out and "v1.4.0" in r.out
        assert "commit-messages" in r.out
        assert "cowboy-coding" not in r.out  # limited to 2, sorted by name

    def test_orders_by_install_count(self, boost, tapped):
        boost("install", "brainstorming")
        boost("install", "jira-integration")
        boost("uninstall", "jira-integration")
        boost("install", "jira-integration")
        r = boost("trending")
        assert r.out.index("jira-integration") < r.out.index("brainstorming")
        jira = next(l for l in r.out.splitlines()
                    if l.startswith("jira-integration"))
        brain = next(l for l in r.out.splitlines()
                     if l.startswith("brainstorming"))
        assert jira.split()[1] == "2"
        assert brain.split()[1] == "1"
        assert "based on local install activity" in r.out
        r = boost("trending", "--limit", "1")
        assert "jira-integration" in r.out
        assert "brainstorming" not in r.out

    def test_long_description_is_clipped(self, boost, tapped, monkeypatch):
        # D23/D24: at a narrow width the table clips wide text columns to fit
        # one line rather than wrapping — a recognizable name prefix and an
        # ellipsis survive, and no rendered row exceeds the terminal.
        boost("install", "brainstorming")
        monkeypatch.setenv("COLUMNS", "40")
        r = boost("trending")
        assert "brainstor" in r.out
        assert "…" in r.out
        for line in r.out.splitlines():
            assert output.visible_len(line) <= 40


# ---------------------------------------------------------------- stats

class TestStats:
    def test_installed_fields(self, boost, installed):
        lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        entry = lock["skills"]["brainstorming"]
        r = boost("stats", "brainstorming")
        lines = {l.split()[0]: l for l in r.out.splitlines() if l.strip()}
        assert "1.4.0" in lines["version"]
        assert "fixture-tap" in lines["tap"]
        assert entry["sha256"][:12] in lines["sha256"]
        assert "claude-code, windsurf, cursor" in lines["agents"]
        assert "no" in lines["pinned"]
        sdir = paths.store_dir() / "brainstorming"
        assert util.human_size(util.dir_size(sdir)) in lines["size"]
        assert "1 installs · 0 updates · 0 uninstalls" in lines["activity"]
        assert "1.4.0 (up to date)" in lines["latest"]
        assert "fixture skills" in lines["upstream"]  # fixture commit subject

    def test_upstream_wraps_to_a_narrow_pane(self, boost, installed,
                                             monkeypatch):
        # "b2b9486  2026-08-28  Boost Fixture  fixture skills" (50 cols) plus
        # the 16-column kv lead ran to 66 — over a 60-column pane.
        monkeypatch.setenv("COLUMNS", "60")
        r = boost("stats", "brainstorming")
        for ln in r.out.split("\n"):
            assert len(ln) <= 60, ln
        assert "fixture" in r.out and "skills" in r.out

    def test_update_available(self, boost, installed):
        p = paths.lockfile_path()
        lock = json.loads(p.read_text(encoding="utf-8"))
        lock["skills"]["brainstorming"]["version"] = "1.0.0"
        p.write_text(json.dumps(lock), encoding="utf-8")
        r = boost("stats", "brainstorming")
        assert "1.4.0 (update available)" in r.out

    def test_catalog_only(self, boost, tapped):
        r = boost("stats", "jira-integration")
        assert "not installed — `boost install jira-integration`" in r.out
        assert "2.1.0" in r.out
        assert "Sync commits and PRs to Jira tickets" in r.out
        assert "0 installs · 0 updates · 0 uninstalls" in r.out

    def test_installed_but_no_longer_in_any_tap(self, boost, installed):
        # The asymmetric case: `lock` exists, `cat` is None. cmd_stats guards
        # "neither" and then relies on that guard two screens later — enabling
        # check_untyped_defs on the command layer is what surfaced the reliance,
        # so it gets a test rather than an implicit invariant.
        boost("untap", "fixture-tap", "--force")
        r = boost("stats", "brainstorming")
        assert "1.4.0" in r.out              # version from the lock
        assert "not installed" not in r.out
        assert "0 installs" in r.out or "installs" in r.out

    def test_unknown(self, boost, tapped):
        r = boost("stats", "nope", expect=1)
        assert "no skill named 'nope' installed or in any tap" in r.err
        assert "try `boost search nope`" in r.err

    def test_installed_rule_reports_lock_facts(self, boost, tapped):
        # Before find_any this raised "no skill named 'house-style'" for a
        # name `boost list` shows installed.
        from boost_cli.core import lockfile
        rp = paths.home() / ".cursor" / "rules" / "house.mdc"
        rp.parent.mkdir(parents=True)
        rp.write_text("rule body", encoding="utf-8")
        lockfile.set_rule("house-style", {
            "kind": "rule", "version": "1.2.0", "tap": "rule-tap",
            "sha256": "a" * 64, "pinned": True,
            "installed_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "materializations": [
                {"agent": "cursor", "mode": "file", "path": str(rp)}]})
        r = boost("stats", "house-style")
        lines = {l.split()[0]: l for l in r.out.splitlines() if l.strip()}
        assert "house-style (rule)" in r.out
        assert "1.2.0" in lines["version"]
        assert "rule-tap" in lines["tap"]
        assert "cursor" in lines["agents"]
        assert "yes" in lines["pinned"]
        assert ("a" * 12) in lines["sha256"]
        assert "0 installs · 0 updates · 0 uninstalls" in lines["activity"]
        data = json.loads(boost("stats", "house-style", "--json").out)
        assert data["kind"] == "rule"
        assert data["installed"] is True
        assert data["lock"]["version"] == "1.2.0"

    def test_json_purity(self, boost, installed):
        r = boost("stats", "brainstorming", "--json")
        data = json.loads(r.out)
        assert r.out.count("\n") == 1
        assert data["name"] == "brainstorming"
        assert data["installed"] is True
        assert data["lock"]["version"] == "1.4.0"
        assert data["activity"] == {"install": 1, "update": 0, "uninstall": 0}
        assert data["catalog"]["latest"] == "1.4.0"
        assert data["catalog"]["tap"] == "fixture-tap"
        assert data["size"] > 0


# ---------------------------------------------------------------- count

class TestCount:
    def test_empty(self, boost, sandbox):
        r = boost("count")
        assert ("installed 0 · available 0 (across 0 taps) · "
                "discovery index not built") in r.out

    def test_exact_line_single_tap(self, boost, installed):
        r = boost("count")
        assert ("installed 1 · available 5 (across 1 tap) · "
                "discovery index not built") in r.out
        # D06: framed inventory card
        assert "╭─ inventory" in r.out
        assert "╰" in r.out

    def test_with_discovery_index_and_json(self, boost, installed):
        _write_index(_ITEMS)
        r = boost("count")
        assert "discovery index 3" in r.out
        r = boost("count", "--json")
        assert json.loads(r.out) == {"installed": 1, "skills": 1, "rules": 0,
                                     "workflows": 0, "available": 5,
                                     "taps": 1, "discovery": 3}

    def test_corrupt_discovery_counts_as_missing(self, boost, sandbox):
        paths.ensure_dirs()
        (paths.cache_dir() / "discovery.json").write_text("{oops", encoding="utf-8")
        r = boost("count", "--json")
        assert json.loads(r.out) == {"installed": 0, "skills": 0, "rules": 0,
                                     "workflows": 0, "available": 0,
                                     "taps": 0, "discovery": None}

    def test_counts_rules_and_workflows_with_labels(self, boost, installed):
        # "installed 1" with a rule in the lock was a false total; the
        # breakdown appears once a non-skill kind is present.
        from boost_cli.core import lockfile
        lockfile.set_rule("house-style", {"kind": "rule", "version": "1.0.0",
                                          "tap": "rule-tap",
                                          "materializations": []})
        lockfile.set_workflow("ship-it", {"kind": "workflow", "version": "1.0.0",
                                          "tap": "rule-tap", "slot": "commands",
                                          "materializations": []})
        r = boost("count")
        assert "installed 3 (1 skill · 1 rule · 1 workflow)" in r.out
        data = json.loads(boost("count", "--json").out)
        assert data["installed"] == 3
        assert (data["skills"], data["rules"], data["workflows"]) == (1, 1, 1)


# ---------------------------------------------------------------- reindex

class TestReindex:
    def test_builds_full_content_index(self, boost, tapped):
        from boost_cli.core import rag
        r = boost("reindex")
        assert "indexed" in r.out and "passages" in r.out
        assert rag.ready() is True

    def test_json_stats(self, boost, tapped):
        r = boost("reindex", "--json")
        data = json.loads(r.out)
        assert data["docs"] >= 1
        assert data["entries"] >= 1
        assert data["taps"] == 1

    def test_reuses_unchanged_tap_on_second_run(self, boost, tapped):
        boost("reindex")
        data = json.loads(boost("reindex", "--json").out)
        assert data["reused"]        # the tap commit is unchanged
        assert data["reindexed"] == []

    def test_force_reindexes_everything(self, boost, tapped):
        boost("reindex")
        data = json.loads(boost("reindex", "--force", "--json").out)
        assert data["reused"] == []

    def test_no_taps_errors(self, boost):
        r = boost("reindex", expect=1)
        assert "no taps configured" in r.err
        assert "boost tap --defaults" in r.err

    def test_search_switches_to_full_content_after_reindex(self, boost, tapped):
        boost("reindex")
        r = boost("search", "brainstorming")
        assert "ranked by full-content BM25" in r.out

    def test_search_sees_a_tap_added_after_the_index_was_built(
            self, boost, tapped, tmp_path):
        """`boost tap X` then `boost search` must find X, with no reindex.

        The regression this pins: `cmd_search` gated on `rag.ready()`, which
        only asks whether an index *exists*. Once one did, a newly tapped repo
        stayed invisible to search forever — while `boost info` described it
        happily from the same machine, and search told the user to go looking
        on GitHub for something already on their disk.
        """
        boost("search", "brainstorming")          # builds the index over `tapped`

        root = tmp_path / "second-tap"
        second = root / "skills" / "zeppelin-telemetry"
        second.mkdir(parents=True)
        (second / "SKILL.md").write_text(
            "---\nname: zeppelin-telemetry\n"
            "description: Stream airship gondola telemetry to a ground station.\n"
            "---\n\n# Zeppelin telemetry\n\n"
            "Mount the gondola sensor array and stream zeppelin telemetry "
            "frames to the ground station dashboard.\n",
            encoding="utf-8")
        # `boost tap` clones its source, so the source has to be a real repo.
        for cmd in (("init", "-q"),
                    ("config", "user.email", "fixture@boost.test"),
                    ("config", "user.name", "fixture"),
                    ("add", "-A"),
                    ("commit", "-qm", "second tap")):
            subprocess.run(("git", *cmd), cwd=str(root),
                           check=True, capture_output=True)
        boost("tap", str(root))

        # Deliberately no `boost reindex` — that is the whole point.
        r = boost("search", "zeppelin telemetry gondola")
        assert "zeppelin-telemetry" in r.out
        assert "no matches" not in r.out

    def test_search_stops_offering_an_untapped_repo(self, boost, tapped):
        """After `boost untap`, its skills must stop ranking.

        Note what actually carries this: `rag.retrieve` filters every hit
        against the live catalog, so a removed tap's documents are dropped even
        from a stale index. It therefore passes with or without the staleness
        check, and is a guard on that filter rather than on `rag.stale`; the
        removal branch of `stale()` is pinned by its own unit test. Worth
        keeping as the end-to-end statement of the promise, not as evidence for
        the fix beside it.
        """
        assert "brainstorming" in boost("search", "brainstorming").out
        boost("untap", tapped.name)          # untap takes the tap's name
        r = boost("search", "brainstorming", expect=None)
        assert "brainstorming" not in r.out

    def test_dense_skipped_when_no_backend_at_all(self, boost, tapped, monkeypatch):
        """No key and no local model: BM25 still builds, dense says why it didn't.

        `local_available` is forced off because the [rag] extra now ships a
        model — without this the command really does build a dense index here,
        and the assertion below was passing only where the extra was absent.
        """
        from boost_cli.core import embed
        monkeypatch.setattr(embed, "local_available", lambda: False)
        r = boost("reindex", "--dense")
        assert "indexed" in r.out                 # BM25 still builds
        assert "dense index skipped" in r.out

    def test_dense_builds_vector_store(self, boost, tapped, monkeypatch):
        if not _vec_loadable():
            pytest.skip("sqlite-vec extension not loadable here")
        from boost_cli.core import dense, embed

        def toy(texts, input_type=None, timeout=60):
            return [[float(len(t) % 5) + 1.0, 2.0, 3.0] + [0.0] * 5 for t in texts]
        monkeypatch.setattr(embed, "embed", toy)
        monkeypatch.setattr(embed, "available", lambda: True)
        monkeypatch.setattr(embed, "provider", lambda: "openai")
        monkeypatch.setattr(embed, "model", lambda: "toy-8")
        monkeypatch.setattr(embed, "dimension", lambda: 8)
        data = json.loads(boost("reindex", "--dense", "--json").out)
        assert data["bm25"]["docs"] >= 1
        assert data["dense"]["chunks"] >= 1
        assert data["dense"]["provider"] == "openai"
        assert dense.ready() is True

    def test_cli_search_uses_dense_when_the_vector_store_is_built(
            self, boost, tapped, monkeypatch):
        """`boost search` must answer from the same engine the MCP server does.

        It previously called ``rag.retrieve`` directly, so a built dense index
        served the MCP path while the CLI stayed BM25-only.
        """
        if not _vec_loadable():
            pytest.skip("sqlite-vec extension not loadable here")
        from boost_cli.core import dense, embed

        def toy(texts, input_type=None, timeout=60):
            return [[1.0, 2.0, 3.0] + [0.0] * 5 for _ in texts]
        monkeypatch.setattr(embed, "embed", toy)
        monkeypatch.setattr(embed, "available", lambda: True)
        monkeypatch.setattr(embed, "provider", lambda: "openai")
        monkeypatch.setattr(embed, "model", lambda: "toy-8")
        monkeypatch.setattr(embed, "dimension", lambda: 8)
        boost("reindex", "--dense")
        assert dense.ready() is True
        r = boost("search", "brainstorming")
        # Both indexes are built here, so retrieve_any fuses rather than
        # picking: the label names both engines. It used to read "ranked by
        # dense vectors", from when a ready dense store ended the search —
        # see rag.retrieve_any for why the golden-set tie retired that.
        assert "ranked by hybrid RRF (BM25 + dense)" in r.out
        assert "ranked by BM25 full-content" not in r.out, \
            "a built dense store must still contribute, not be bypassed"

    def test_empty_store_warns_instead_of_reporting_success(
            self, boost, tapped, monkeypatch):
        """A store left empty by an earlier run must not print a green check.

        Reporting success on an empty store cost a real user a long debugging
        detour: every tap reads as already-built, so the reuse path skips
        everything and stores nothing.
        """
        if not _vec_loadable():
            pytest.skip("sqlite-vec extension not loadable here")
        from boost_cli.core import dense, embed

        def toy(texts, input_type=None, timeout=60):
            return [[1.0, 2.0, 3.0] + [0.0] * 5 for _ in texts]
        monkeypatch.setattr(embed, "embed", toy)
        monkeypatch.setattr(embed, "available", lambda: True)
        monkeypatch.setattr(embed, "provider", lambda: "openai")
        monkeypatch.setattr(embed, "model", lambda: "toy-8")
        monkeypatch.setattr(embed, "dimension", lambda: 8)
        # Records every tap commit while storing nothing — the exact state a
        # rate-limited pre-fix run left behind.
        dense.build(entries=[], force=True)
        r = boost("reindex", "--dense")
        assert "dense vector store is empty" in r.out
        assert "--force" in r.out
        assert dense.ready() is False


class TestSearchSemanticHint:
    """`boost search` must say a better engine exists, not just which one ran.

    The gap this closes: search reported "ranked by full-content BM25" and
    stopped. A user who installed the [rag] extra but never ran `boost reindex
    --dense` saw nothing to suggest the semantic search they think they enabled
    has never once run — `boost doctor` was the only surface that said so, and
    nobody runs doctor after a search that merely felt mediocre.

    The hint is deliberately quiet, so these tests pin the *silences* as hard as
    the message: no hint when vectors already served, and none in --json.
    """

    def test_bm25_only_search_says_semantic_is_off(self, boost, tapped):
        boost("reindex")
        r = boost("search", "brainstorming")
        assert "ranked by full-content BM25" in r.out      # unchanged
        assert "semantic search is off" in r.out

    def test_hint_names_the_one_next_action(self, boost, tapped):
        # Without the extra the remedy is the install; with it, the reindex.
        # Either way exactly one command is named, never the whole setup.
        #
        # Matched against the whole output with whitespace collapsed, because
        # the hint legitimately wraps across lines in a narrow pane — asserting
        # on a single line made this test fail at COLUMNS=40 for a layout the
        # code was getting right.
        boost("reindex")
        r = boost("search", "brainstorming")
        flat = " ".join(r.out.split())
        assert "semantic search is off" in flat
        assert "pip install" in flat or "boost reindex --dense" in flat

    def test_zero_results_still_hints(self, boost, tapped):
        # The strongest case for the hint: a keyword engine finding nothing is
        # exactly the shape of query a semantic one exists to answer.
        r = boost("search", "zzzznotathinginanycatalog")
        assert "no matches" in r.out
        assert "semantic search is off" in r.out

    def test_json_output_carries_no_hint(self, boost, tapped):
        # --json is parsed by other programs; a stray human line corrupts it.
        boost("reindex")
        r = boost("search", "brainstorming", "--json")
        assert "semantic search is off" not in r.out
        json.loads(r.out)                                  # still valid JSON

    def test_no_hint_once_dense_is_ready(self, boost, tapped, monkeypatch):
        # The inverse: a user who finished the setup must never be nagged.
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "status", lambda: {"ready": True, "reason": None})
        boost("reindex")
        r = boost("search", "brainstorming")
        assert "semantic search is off" not in r.out


class TestReindexShards:
    """`--export-shard` / `--import-shard`, the user-facing half of shards.

    The engine is covered in tests/unit/test_dense_shards.py; this pins the CLI
    contract — exit codes, JSON on stdout, and that a refused shard reports why
    rather than half-importing.
    """

    def test_exporting_a_tap_with_no_vectors_fails_with_a_hint(self, boost,
                                                               tapped):
        r = boost("reindex", "--export-shard", "acme/skills", expect=1)
        assert "no vectors" in r.err
        assert "reindex --dense" in r.err        # names the one next action

    def test_export_writes_json_to_stdout(self, boost, tapped, monkeypatch):
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "export_shard", lambda tap: {
            "tap": tap, "commit": "c1", "provider": "local", "model": "bge",
            "dim": 8, "chunks": [{"name": "a", "tap": tap, "path": "a/SKILL.md",
                                  "kind": "skill", "cix": 0, "snip": "s",
                                  "embedding": "AAAA"}]})
        r = boost("reindex", "--export-shard", "acme/skills")
        payload = json.loads(r.out)              # must be parseable, not pretty
        assert payload["tap"] == "acme/skills"
        assert len(payload["chunks"]) == 1

    def test_importing_a_missing_file_is_an_error(self, boost, tapped, tmp_path):
        r = boost("reindex", "--import-shard", str(tmp_path / "nope.json"),
                  expect=1)
        assert "cannot read shard" in r.err

    def test_importing_malformed_json_is_an_error(self, boost, tapped, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        r = boost("reindex", "--import-shard", str(bad), expect=1)
        assert "cannot read shard" in r.err

    def test_a_refused_shard_reports_the_reason(self, boost, tapped, tmp_path,
                                                monkeypatch):
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "import_shard",
                            lambda shard, commit: (False, "dim mismatch"))
        f = tmp_path / "s.json"
        f.write_text(json.dumps({"tap": "acme/skills"}), encoding="utf-8")
        r = boost("reindex", "--import-shard", str(f), expect=1)
        assert "dim mismatch" in r.err
        assert "reindex --dense" in r.err        # the fallback that always works

    def test_a_good_shard_reports_what_landed(self, boost, tapped, tmp_path,
                                              monkeypatch):
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "import_shard",
                            lambda shard, commit: (True, "imported 7 chunks"))
        f = tmp_path / "s.json"
        f.write_text(json.dumps({"tap": "acme/skills"}), encoding="utf-8")
        r = boost("reindex", "--import-shard", str(f))
        assert "imported 7 chunks" in r.out
        assert "acme/skills" in r.out
