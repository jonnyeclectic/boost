"""Functional tests: Discovery & Search commands, in-process.

search / index / discover / recommend / browse / trending / stats / count,
asserting exact output shapes, exit codes, and on-disk cache effects.
"""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import types

import pytest

from boost_cli.core import paths, util


def _vec_loadable() -> bool:
    """True only if sqlite-vec both imports and loads (see test_dense.py)."""
    try:
        import sqlite_vec  # type: ignore
    except ImportError:
        return False
    con = sqlite3.connect(":memory:")
    try:
        con.enable_load_extension(True)
        sqlite_vec.load(con)
        con.execute("select vec_version()").fetchone()
        return True
    except Exception:
        return False
    finally:
        con.close()


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t"]
                   + list(args), cwd=str(cwd), check=True, capture_output=True)


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
            "# %s\n\nBody text.\n" % (name, desc, tags, name))
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "skills")
    return root


# ---------------------------------------------------------------- search

class TestSearch:
    def test_multiword_ranks_exact_token_hits_first(self, boost, tapped):
        r = boost("search", "commit", "messages")
        assert "commit-messages" in r.out
        assert "jira-integration" in r.out
        assert r.out.index("commit-messages") < r.out.index("jira-integration")
        assert "2 matches · ranked by heuristic relevance" in r.out

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
        assert "2 matches · ranked by heuristic relevance" in r.out

    def test_single_match_uses_singular_footer(self, boost, tapped):
        r = boost("search", "brainstorming")
        assert "1 match · ranked by heuristic relevance" in r.out
        assert "1 matches" not in r.out

    def test_json_is_pure_and_scored(self, boost, tapped):
        r = boost("search", "brainstorming", "--json")
        data = json.loads(r.out)  # whole stdout is one JSON document
        assert r.out.count("\n") == 1
        assert len(data) == 1
        assert data[0]["name"] == "brainstorming"
        assert data[0]["version"] == "1.4.0"
        assert data[0]["tap"] == "fixture-tap"
        assert data[0]["score"] == 114  # 100 exact + 12 token-in-name + 2 blob

    def test_no_taps_fails_with_hint(self, boost):
        r = boost("search", "anything", expect=1)
        assert "no taps configured — nothing to search" in r.err
        assert "boost tap --defaults" in r.err

    def test_no_matches_hints_discover(self, boost, tapped):
        r = boost("search", "zzzznothing")
        assert "no matches for 'zzzznothing'" in r.out
        assert "try `boost discover zzzznothing`" in r.out

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

    def test_smart_without_ai_warns_and_stays_heuristic(self, boost, tapped):
        r = boost("search", "testing", "--smart")
        assert "using the heuristic fallback" in r.out
        assert "ranked by heuristic relevance" in r.out

    def test_smart_with_ai_reorders_and_credits_haiku(self, boost, tapped,
                                                      monkeypatch):
        monkeypatch.delenv("BOOST_NO_AI", raising=False)
        monkeypatch.setattr("boost_cli.core.ai.available", lambda: True)
        monkeypatch.setattr("boost_cli.core.ai.ask",
                            lambda *a, **k: '["tdd-workflow", "cowboy-coding"]')
        r = boost("search", "testing", "--smart")
        assert r.out.index("tdd-workflow") < r.out.index("cowboy-coding")
        assert "ranked by Claude Haiku relevance" in r.out
        assert "heuristic relevance" not in r.out

    def test_smart_with_junk_ai_reply_keeps_heuristic(self, boost, tapped,
                                                      monkeypatch):
        monkeypatch.delenv("BOOST_NO_AI", raising=False)
        monkeypatch.setattr("boost_cli.core.ai.available", lambda: True)
        monkeypatch.setattr("boost_cli.core.ai.ask",
                            lambda *a, **k: "sorry, no list here")
        r = boost("search", "testing", "--smart")
        # heuristic tie broken by name: cowboy-coding sorts first
        assert r.out.index("cowboy-coding") < r.out.index("tdd-workflow")
        assert "ranked by heuristic relevance" in r.out

    def test_limit_must_be_positive_int(self, boost, tapped):
        r = boost("search", "x", "--limit", "0", expect=2)
        assert "must be >= 1" in r.err
        r = boost("search", "x", "--limit", "abc", expect=2)
        assert "invalid int value: 'abc'" in r.err


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
        data = json.loads((paths.cache_dir() / "discovery.json").read_text())
        assert data["github_total"] == 7
        assert data["items"] == [
            {"repo": "octo/skills", "path": "skills/a/SKILL.md",
             "url": "https://github.com/octo/skills/skills/a/SKILL.md",
             "description": "Skill repo"},
            {"repo": "acme/pack", "path": "skills/b/SKILL.md",
             "url": "https://github.com/acme/pack/skills/b/SKILL.md",
             "description": ""}]

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
        data = json.loads((paths.cache_dir() / "discovery.json").read_text())
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
        data = json.loads((paths.cache_dir() / "discovery.json").read_text())
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

def _write_index(items, total=42):
    paths.ensure_dirs()
    (paths.cache_dir() / "discovery.json").write_text(json.dumps(
        {"generated": util.now_iso(), "github_total": total, "items": items}))


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
        r = boost("discover", "acme")
        assert "octo/skills" not in r.out
        assert "skills/web/SKILL.md" in r.out and "skills/db/SKILL.md" in r.out
        assert "2 of 3 indexed skills · GitHub reports ~42 total" in r.out
        # multi-token queries AND together
        r = boost("discover", "acme", "web")
        assert "skills/db/SKILL.md" not in r.out
        assert "1 of 3 indexed skills" in r.out

    def test_json_purity(self, boost, sandbox):
        _write_index(_ITEMS)
        r = boost("discover", "acme", "--json")
        assert json.loads(r.out) == _ITEMS[1:]
        assert r.out.count("\n") == 1

    def test_no_match_reports_index_size(self, boost, sandbox):
        _write_index(_ITEMS)
        r = boost("discover", "zzz")
        assert "no indexed skills match 'zzz'" in r.out
        assert "the index holds 3 entries — rebuild with `boost index`" in r.out

    def test_limit(self, boost, sandbox):
        _write_index(_ITEMS)
        r = boost("discover", "--limit", "1")
        assert "1 of 3 indexed skills" in r.out
        assert "acme/pack" not in r.out

    def test_corrupt_index(self, boost, sandbox):
        paths.ensure_dirs()
        (paths.cache_dir() / "discovery.json").write_text("{broken")
        r = boost("discover", expect=1)
        assert "the discovery index is corrupt" in r.err


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
        {"dependencies": {"react": "^18.2.0"}}))
    (proj / "pyproject.toml").write_text("[tool.pytest.ini_options]\naddopts = '-q'\n")
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
        (proj / "package.json").write_text("{not json")     # still javascript
        (proj / "go.mod").write_text("module x\n")
        (proj / "Cargo.toml").write_text("[package]\n")
        (proj / "Gemfile").write_text("gem 'rails'\n")
        (proj / "tsconfig.json").write_text("{}")
        (proj / "Dockerfile").write_text("FROM scratch\n")
        (proj / "pom.xml").write_text("<project>org.springframework</project>")
        (proj / "a.tf").write_text("resource {}\n")
        (proj / "b.tf").write_text("resource {}\n")
        (proj / "x.py").write_text("pass\n")
        (proj / "y.py").write_text("pass\n")
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

    def test_tui_pick_installs(self, boost, tapped, monkeypatch):
        from boost_cli.commands import discovery
        tty = types.SimpleNamespace(isatty=lambda: True)
        monkeypatch.setattr(discovery, "sys",
                            types.SimpleNamespace(stdin=tty, stdout=tty))
        monkeypatch.setattr(
            discovery, "_browse_tui",
            lambda curses, entries: next(e for e in entries
                                         if e["name"] == "brainstorming"))
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
        from boost_cli.commands import discovery
        tty = types.SimpleNamespace(isatty=lambda: True)
        monkeypatch.setattr(discovery, "sys",
                            types.SimpleNamespace(stdin=tty, stdout=tty))
        workflow = {"name": "AGENT-playbook", "kind": "workflow",
                    "version": "1.0", "tap": "fixture-tap"}
        monkeypatch.setattr(discovery, "_browse_tui",
                            lambda curses, entries: workflow)
        r = boost("browse")                       # default expect=0 → no crash
        assert "cannot install yet" in r.out      # friendly message, not Error:
        assert "boost search" in r.out            # the hint is shown
        assert "installed AGENT-playbook" not in r.out

    def test_tui_loop_with_fake_curses(self, boost, tapped):
        from boost_cli.commands import discovery
        from boost_cli.core import catalog

        class FakeCurses:
            A_BOLD, A_DIM, A_REVERSE, A_NORMAL = 1, 2, 4, 0
            KEY_UP, KEY_DOWN, KEY_ENTER, KEY_BACKSPACE = 259, 258, 343, 263
            ACS_HLINE = ord("-")

            class error(Exception):
                pass

            def __init__(self, keys):
                self.keys = list(keys)
                self.drawn = []

            def curs_set(self, n):
                raise self.error("no cursor support")

            def wrapper(self, fn):
                fn(self)

            # screen protocol
            def getmaxyx(self):
                return (24, 80)

            def erase(self):
                pass

            def addnstr(self, y, x, s, n, attr=0):
                self.drawn.append(s)

            def hline(self, *a):
                pass

            def refresh(self):
                pass

            def getch(self):
                return self.keys.pop(0) if self.keys else ord("q")

        entries = sorted(catalog.all_entries(), key=lambda e: e["name"])
        fake = FakeCurses([ord("t"), FakeCurses.KEY_DOWN, 10, FakeCurses.KEY_UP,
                           FakeCurses.KEY_BACKSPACE, ord("i")])
        picked = discovery._browse_tui(fake, entries)
        assert picked["name"] == "brainstorming"
        # the typed query is echoed after the "❯" prompt
        assert "t" in fake.drawn
        assert any("boost browse" in s for s in fake.drawn)
        # ESC quits without a pick
        assert discovery._browse_tui(FakeCurses([27]), entries) is None


class TestBrowseAurora:
    """The curses browser paints itself in the single-source Aurora palette."""

    def test_curses_rgb1000_parity_with_tokens(self):
        from boost_cli.commands import discovery
        from boost_cli.core import output as out
        rgb = discovery._curses_rgb1000()
        assert set(rgb) == set(out.TOKENS)
        # cyan #22d3ee scaled 0..255 -> 0..1000
        r, g, b = out.TOKENS["cyan"]
        assert rgb["cyan"] == (round(r / 255 * 1000), round(g / 255 * 1000),
                               round(b / 255 * 1000))
        for triple in rgb.values():
            assert all(0 <= c <= 1000 for c in triple)

    def test_nearest_base_covers_every_token(self):
        import curses
        from boost_cli.commands import discovery
        from boost_cli.core import output as out
        base = discovery._nearest_base(curses)
        assert set(base) == set(out.TOKENS)
        assert base["cyan"] == curses.COLOR_CYAN
        assert base["violet"] == base["pink"] == curses.COLOR_MAGENTA

    def test_match_positions(self):
        from boost_cli.commands import discovery
        assert discovery._match_positions("bs", "brainstorm") == [0, 5]
        assert discovery._match_positions("", "anything") == []
        assert discovery._match_positions("zzz", "brainstorm") == []
        # left-to-right greedy: first 'o', then trailing 'm'
        assert discovery._match_positions("om", "brainstorm") == [7, 9]

    def test_scrollbar_math(self):
        from boost_cli.commands import discovery
        assert discovery._scrollbar(5, 10, 0) is None      # all fits
        assert discovery._scrollbar(10, 0, 0) is None      # no rows
        start, length = discovery._scrollbar(100, 10, 0)
        assert start == 0 and 1 <= length <= 10
        end_start, _ = discovery._scrollbar(100, 10, 90)   # scrolled to bottom
        assert end_start == 10 - length

    def test_grad_segments_partition(self):
        from boost_cli.commands import discovery
        assert discovery._grad_segments(0) == []
        segs = discovery._grad_segments(10, 3)
        assert [s[1] for s in segs] == [4, 3, 3]           # sums to width
        assert sum(s[1] for s in segs) == 10
        assert [s[0] for s in segs] == [0, 4, 7]           # contiguous
        assert len(discovery._grad_segments(2, 3)) == 2    # n clamps to width

    def test_theme_upgrades_to_colour(self):
        from boost_cli.commands import discovery

        class ColorCurses:
            COLOR_CYAN, COLOR_MAGENTA, COLOR_GREEN = 6, 5, 2
            COLOR_YELLOW, COLOR_RED = 3, 1
            COLORS = 256
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
                return True

            def init_color(self, slot, r, g, b):
                self.colors[slot] = (r, g, b)

            def init_pair(self, i, fg, bg):
                self.pairs[i] = (fg, bg)

            def color_pair(self, i):
                return i << 8

        cc = ColorCurses()
        th = discovery._aurora_theme(cc)
        # custom colours were defined from the parity-locked palette
        assert cc.colors[16] == discovery._curses_rgb1000()["cyan"]
        # title carries a colour pair plus bold, not bare monochrome
        assert th["title"] & cc.A_BOLD
        assert th["title"] & ~cc.A_BOLD
        assert len(th["rule"]) == 3
        assert th["rule"][0] != th["rule"][1] != th["rule"][2]

    def test_theme_falls_back_without_colour(self):
        from boost_cli.commands import discovery

        class MonoCurses:
            A_BOLD, A_DIM, A_REVERSE, A_NORMAL = 1, 2, 4, 0
        th = discovery._aurora_theme(MonoCurses)
        assert th["title"] == MonoCurses.A_BOLD
        assert th["sel_bar"] == MonoCurses.A_REVERSE
        assert th["rule"] == [MonoCurses.A_NORMAL] * 3


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
        # D23: description column must not dump raw — it clips to the width.
        boost("install", "brainstorming")
        monkeypatch.setenv("COLUMNS", "40")
        r = boost("trending")
        assert "brainstorming" in r.out
        assert "…" in r.out


# ---------------------------------------------------------------- stats

class TestStats:
    def test_installed_fields(self, boost, installed):
        lock = json.loads(paths.lockfile_path().read_text())
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

    def test_update_available(self, boost, installed):
        p = paths.lockfile_path()
        lock = json.loads(p.read_text())
        lock["skills"]["brainstorming"]["version"] = "1.0.0"
        p.write_text(json.dumps(lock))
        r = boost("stats", "brainstorming")
        assert "1.4.0 (update available)" in r.out

    def test_catalog_only(self, boost, tapped):
        r = boost("stats", "jira-integration")
        assert "not installed — `boost install jira-integration`" in r.out
        assert "2.1.0" in r.out
        assert "Sync commits and PRs to Jira tickets" in r.out
        assert "0 installs · 0 updates · 0 uninstalls" in r.out

    def test_unknown(self, boost, tapped):
        r = boost("stats", "nope", expect=1)
        assert "no skill named 'nope' installed or in any tap" in r.err
        assert "try `boost search nope`" in r.err

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
        assert json.loads(r.out) == {"installed": 1, "available": 5,
                                     "taps": 1, "discovery": 3}

    def test_corrupt_discovery_counts_as_missing(self, boost, sandbox):
        paths.ensure_dirs()
        (paths.cache_dir() / "discovery.json").write_text("{oops")
        r = boost("count", "--json")
        assert json.loads(r.out) == {"installed": 0, "available": 0,
                                     "taps": 0, "discovery": None}


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

    def test_dense_skipped_without_embeddings_key(self, boost, tapped):
        r = boost("reindex", "--dense")
        assert "indexed" in r.out                 # BM25 still builds
        assert "dense index skipped" in r.out

    def test_dense_builds_vector_store(self, boost, tapped, monkeypatch):
        if not _vec_loadable():
            pytest.skip("sqlite-vec extension not loadable here")
        from boost_cli.core import dense, embed

        def toy(texts, input_type=None, timeout=60):
            return [[float(len(t) % 5) + 1.0, 2.0, 3.0] for t in texts]
        monkeypatch.setattr(embed, "embed", toy)
        monkeypatch.setattr(embed, "available", lambda: True)
        monkeypatch.setattr(embed, "provider", lambda: "openai")
        monkeypatch.setattr(embed, "model", lambda: "toy-3")
        monkeypatch.setattr(embed, "dimension", lambda: 3)
        data = json.loads(boost("reindex", "--dense", "--json").out)
        assert data["bm25"]["docs"] >= 1
        assert data["dense"]["chunks"] >= 1
        assert data["dense"]["provider"] == "openai"
        assert dense.ready() is True
