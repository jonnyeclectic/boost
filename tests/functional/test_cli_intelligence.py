# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Functional tests: Intelligence commands, in-process.

distill / simulate / infer / absorb / evolve / context / focus / impact.
Heuristic (no-AI) fallbacks are exercised first; AI branches run with
boost_cli.core.ai monkeypatched to canned replies.
"""
from __future__ import annotations

import json
import subprocess

import pytest

from boost_cli.core import frontmatter, journal, paths

FALLBACK = "using the heuristic fallback"


def flat(text: str) -> str:
    """Collapse whitespace before matching a hint.

    The AI-fallback note is prose wrapped to the pane, so the phrase
    legitimately spans a line break — and `term_width()` falls back to 80 under
    pytest, so it wraps in the suite and not only on a narrow terminal.
    Matching on the collapsed text asserts *that the note was shown* without
    also pinning *where the wrap happened to land*, which is not behaviour any
    of these tests are about.
    """
    return " ".join(text.split())


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t", *list(args)], cwd=str(cwd), check=True, capture_output=True)


def _git_repo(root, *subjects):
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    for s in subjects or ("init",):
        _git(root, "commit", "-q", "--allow-empty", "-m", s)
    _git(root, "branch", "-m", "main")  # old-git-safe default branch name
    return root


@pytest.fixture(autouse=True)
def _reset_fallback_warned(monkeypatch):
    """The warn-once flag persists across in-process invocations; reset it."""
    from boost_cli.commands import intelligence
    monkeypatch.setattr(intelligence, "_warned_fallback", False)


@pytest.fixture()
def ai_on(sandbox, monkeypatch):
    """Enable the AI branch; returns a setter for canned replies."""
    from boost_cli.core import ai
    monkeypatch.delenv("BOOST_NO_AI", raising=False)
    monkeypatch.setattr(ai, "available", lambda: True)

    def set_replies(ask=None, ask_author=None):
        monkeypatch.setattr(ai, "ask", lambda *a, **k: ask)
        monkeypatch.setattr(ai, "ask_author", lambda *a, **k: ask_author)

    return set_replies


# ---------------------------------------------------------------- distill

class TestDistill:
    def test_fallback_merges_both_sources(self, boost, tapped, tmp_path,
                                          monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = boost("distill", "tdd-workflow", "cowboy-coding")
        assert ("distilling tdd-workflow, cowboy-coding → "
                "tdd-workflow-distilled") in r.out
        assert FALLBACK in flat(r.out)
        assert "install it with `boost import ./tdd-workflow-distilled`" in r.out
        text = (tmp_path / "tdd-workflow-distilled" / "SKILL.md").read_text(encoding="utf-8")
        meta, body = frontmatter.parse(text)
        assert meta["name"] == "tdd-workflow-distilled"
        assert meta["version"] == "1.0.0"
        assert meta["tags"] == ["testing", "workflow"]
        assert "Distilled from: tdd-workflow, cowboy-coding." in body
        assert "## From tdd-workflow" in body and "## From cowboy-coding" in body
        assert "Never write production code without a failing test" in body
        assert "Always push straight to main" in body
        evs = journal.events(action="distill")
        assert evs[0]["subject"] == "tdd-workflow-distilled"
        assert evs[0]["sources"] == ["tdd-workflow", "cowboy-coding"]

    def test_dedupes_repeated_lines_and_honors_output_name(self, boost, tapped,
                                                           tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        boost("distill", "brainstorming", "commit-messages", "-o", "combo")
        text = (tmp_path / "combo" / "SKILL.md").read_text(encoding="utf-8")
        assert frontmatter.parse(text)[0]["name"] == "combo"
        assert text.count("## Rules") == 1      # exact-duplicate line dropped
        assert text.count("```text") == 1

    def test_install_lands_in_store_as_local(self, boost, tapped):
        r = boost("distill", "tdd-workflow", "commit-messages", "--install")
        assert "installed tdd-workflow-distilled" in r.out
        assert (paths.store_dir() / "tdd-workflow-distilled" / "SKILL.md").is_file()
        lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        entry = lock["skills"]["tdd-workflow-distilled"]
        assert entry["tap"] == "local"
        assert entry["version"] == "1.0.0"

    def test_refused_install_saves_the_generation_instead_of_losing_it(
            self, boost, tapped, tmp_path, monkeypatch):
        """A refused install must leave the generated skill on disk.

        `_install_generated` builds into a TemporaryDirectory, so letting a
        BoostError escape the `with` block would delete the only copy of a
        just-generated skill — silently discarding an LLM generation the user
        paid for. Now that install_from_path enforces the policy gate, this is
        the arm that actually fires, and it was the one arm with no test.
        """
        monkeypatch.chdir(tmp_path)
        boost("policy", "set", "blocked_skills", "tdd-workflow-distilled")
        r = boost("distill", "tdd-workflow", "commit-messages", "--install",
                  expect=0)

        assert "not installed" in (r.out + r.err)
        assert "policy blocks" in (r.out + r.err)
        # the refusal is not silent about where the work went
        assert "generated skill saved to" in r.out

        fallback = tmp_path / "tdd-workflow-distilled.SKILL.md"
        assert fallback.is_file(), "the generation was discarded on refusal"
        meta, _body = frontmatter.parse(fallback.read_text(encoding="utf-8"))
        assert meta["name"] == "tdd-workflow-distilled"
        # and it really was refused, not quietly installed anyway
        assert not (paths.store_dir() / "tdd-workflow-distilled").exists()

    def test_ai_path_uses_reply(self, boost, tapped, tmp_path, monkeypatch, ai_on):
        monkeypatch.chdir(tmp_path)
        ai_on(ask_author="```markdown\n---\nname: merged-x\ndescription: AI merge\n"
                         "version: 1.0.0\n---\n\n# Merged X\n\n"
                         "- Always do the AI thing.\n```")
        r = boost("distill", "brainstorming", "commit-messages", "-o", "merged-x")
        assert FALLBACK not in flat(r.out)
        text = (tmp_path / "merged-x" / "SKILL.md").read_text(encoding="utf-8")
        assert "Always do the AI thing." in text
        assert frontmatter.parse(text)[0]["name"] == "merged-x"

    def test_ai_empty_reply_falls_back(self, boost, tapped, tmp_path,
                                       monkeypatch, ai_on):
        monkeypatch.chdir(tmp_path)
        ai_on(ask_author=None)
        r = boost("distill", "tdd-workflow", "cowboy-coding")
        assert FALLBACK in flat(r.out)
        assert (tmp_path / "tdd-workflow-distilled" / "SKILL.md").is_file()

    def test_needs_two_distinct_skills(self, boost, tapped):
        r = boost("distill", "brainstorming", expect=1)
        assert "distill needs at least two distinct skills" in r.err
        r = boost("distill", "brainstorming", "brainstorming", expect=1)
        assert "distill needs at least two distinct skills" in r.err

    def test_unknown_skill(self, boost, tapped):
        r = boost("distill", "brainstorming", "ghost", expect=1)
        assert "no skill named 'ghost' in any tap" in r.err

    def test_declined_overwrite_leaves_file(self, boost, tapped, tmp_path,
                                            monkeypatch):
        monkeypatch.chdir(tmp_path)
        dest = tmp_path / "tdd-workflow-distilled" / "SKILL.md"
        dest.parent.mkdir()
        dest.write_text("precious", encoding="utf-8")
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("distill", "tdd-workflow", "cowboy-coding", expect=1)
        assert "aborted" in r.out
        assert dest.read_text(encoding="utf-8") == "precious"


# ---------------------------------------------------------------- simulate

class TestSimulate:
    def test_fallback_lists_rules_from_tap(self, boost, tapped):
        r = boost("simulate", "tdd-workflow")
        assert "simulating tdd-workflow" in r.out
        assert "(tap fixture-tap)" in r.out
        assert FALLBACK in flat(r.out)
        assert "a typical coding task in this repo" in r.out
        assert "Without it: default behavior" in r.out
        assert "With tdd-workflow active, Claude would:" in r.out
        assert "• never write production code without a failing test" in r.out
        assert "• always run the full suite before committing" in r.out
        assert "• follow: write a failing test first. Watch it fail" in r.out
        assert ('likely triggers when the task involves: '
                '"Red-green-refactor test-driven development loop"') in flat(r.out)

    def test_installed_origin_and_custom_task(self, boost, installed):
        r = boost("simulate", "brainstorming", "--task", "plan a feature")
        assert "(installed)" in r.out
        assert "plan a feature" in r.out
        assert "• never critique during the diverge phase" in r.out

    def test_ai_path_prints_reply(self, boost, tapped, ai_on):
        ai_on(ask="- WITHOUT: rushes in\n- WITH: writes tests first")
        r = boost("simulate", "tdd-workflow")
        assert "WITH: writes tests first" in r.out
        assert "Without it: default behavior" not in r.out
        assert FALLBACK not in flat(r.out)


# ---------------------------------------------------------------- infer

@pytest.fixture()
def py_project(tmp_path):
    proj = tmp_path / "pyproj"
    proj.mkdir()
    (proj / "pyproject.toml").write_text(
        "[tool.ruff]\nline-length = 88\n[tool.pytest.ini_options]\n", encoding="utf-8")
    (proj / ".editorconfig").write_text("root = true\n", encoding="utf-8")
    (proj / "tests").mkdir()
    return proj


class TestInfer:
    def test_template_to_stdout(self, boost, sandbox, py_project):
        r = boost("infer", "--path", py_project)
        assert FALLBACK in flat(r.out)
        meta, _ = frontmatter.parse(r.out.split("heuristic fallback", 1)[1].lstrip())
        assert meta["name"] == "project-conventions"
        assert meta["description"] == "Working conventions for this repository (python)"
        assert meta["version"] == "1.0.0"
        assert "- Languages: python" in r.out
        assert "- Frameworks: pytest" in r.out
        assert "- Tests live in `tests/`" in r.out
        assert "- Respect the configured formatters: .editorconfig, ruff." in r.out

    def test_commit_style_conventional(self, boost, sandbox, py_project):
        _git_repo(py_project, "feat: one", "fix: two")
        r = boost("infer", "--path", py_project)
        assert ("Write Conventional Commits (`type(scope): subject`) — "
                "2 of the last 2 subjects follow it.") in r.out

    def test_commit_style_freeform(self, boost, sandbox, tmp_path):
        proj = _git_repo(tmp_path / "free", "hello world")
        (proj / "pyproject.toml").write_text("x = 1\n", encoding="utf-8")
        r = boost("infer", "--path", proj)
        assert ("Commit subjects are freeform (0/1 conventional); keep them "
                "short and imperative.") in r.out

    def test_output_file_and_name(self, boost, sandbox, py_project, tmp_path):
        out_file = tmp_path / "gen" / "SKILL.md"
        r = boost("infer", "--path", py_project, "--name", "My Conventions",
                 "-o", out_file)
        assert "wrote" in r.out
        meta, _ = frontmatter.parse(out_file.read_text(encoding="utf-8"))
        assert meta["name"] == "my-conventions"
        evs = journal.events(action="infer")
        assert evs[0]["subject"] == "my-conventions"

    def test_install(self, boost, sandbox, py_project):
        r = boost("infer", "--path", py_project, "--install")
        assert "installed project-conventions" in r.out
        assert (paths.store_dir() / "project-conventions" / "SKILL.md").is_file()
        lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        assert lock["skills"]["project-conventions"]["tap"] == "local"

    def test_ai_path(self, boost, sandbox, py_project, ai_on):
        ai_on(ask_author="---\nname: project-conventions\ndescription: AI says\n"
                         "version: 1.0.0\n---\n\n# Rules\n\n- Use ruff always.\n")
        r = boost("infer", "--path", py_project)
        assert "- Use ruff always." in r.out
        assert FALLBACK not in flat(r.out)

    def test_bad_path(self, boost, sandbox):
        r = boost("infer", "--path", "/nope/nowhere", expect=1)
        assert "is not a directory" in r.err


# ---------------------------------------------------------------- absorb

def _history_line(text):
    return json.dumps({"message": {"role": "user", "content": text}})


class TestAbsorb:
    def test_no_history_found(self, boost, sandbox):
        r = boost("absorb")
        assert "no chat history found under ~/.claude — nothing to absorb" in r.out
        assert "--history PATH" in r.out

    def test_pattern_surfaced_from_projects_dir(self, boost, sandbox):
        hist = sandbox / ".claude" / "projects" / "proj"
        hist.mkdir(parents=True)
        lines = [_history_line("always run the linter before committing")
                 for _ in range(3)]
        # one repeat arrives in content-list form; assistant lines are ignored
        lines.append(json.dumps({"message": {"role": "user", "content": [
            {"type": "text",
             "text": "always run the linter before committing"}]}}))
        lines.append(json.dumps({"message": {"role": "assistant",
                                             "content": "sure thing"}}))
        lines.append("not json at all")
        lines += [_history_line("ok") for _ in range(5)]  # trivial: too short
        (hist / "chat.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        r = boost("absorb")
        assert "recurring patterns from 1 history file(s)" in r.out
        assert "always run the linter before committing" in r.out
        assert "4x" in r.out
        assert "- Always run the linter before committing. (seen 4x)" in r.out
        assert "name: absorbed-patterns" in r.out

    def test_history_flag_missing_and_empty_dir(self, boost, sandbox, tmp_path):
        r = boost("absorb", "--history", "/no/such/file.jsonl", expect=1)
        assert "no history at" in r.err
        empty = tmp_path / "empty"
        empty.mkdir()
        r = boost("absorb", "--history", empty)
        assert "no .jsonl history files under" in r.out

    def test_no_recurring_patterns(self, boost, sandbox, tmp_path):
        f = tmp_path / "h.jsonl"
        f.write_text("\n".join(_history_line("do the thing number %d ok" % i)
                               for i in range(5)) + "\n", encoding="utf-8")
        r = boost("absorb", "--history", f)
        assert ("no recurring patterns in 1 history file(s) — absorb needs "
                "the same request 3+ times") in r.out

    def test_install(self, boost, sandbox, tmp_path):
        f = tmp_path / "h.jsonl"
        f.write_text("\n".join(
            [_history_line("please write docstrings for every function")] * 3), encoding="utf-8")
        r = boost("absorb", "--history", f, "--install")
        assert "installed absorbed-patterns" in r.out
        lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        assert lock["skills"]["absorbed-patterns"]["tap"] == "local"

    def test_ai_path(self, boost, sandbox, tmp_path, ai_on):
        ai_on(ask_author="---\nname: absorbed-patterns\ndescription: canned\n"
                         "version: 1.0.0\n---\n\n- AI absorbed rule.\n")
        f = tmp_path / "h.jsonl"
        f.write_text("\n".join(
            [_history_line("please write docstrings for every function")] * 3), encoding="utf-8")
        r = boost("absorb", "--history", f)
        assert "- AI absorbed rule." in r.out
        assert FALLBACK not in flat(r.out)


# ---------------------------------------------------------------- evolve

class TestEvolve:
    def test_not_installed(self, boost, tapped):
        r = boost("evolve", "tdd-workflow", "--feedback", "x", expect=1)
        assert "tdd-workflow is not installed — evolve works on installed skills" in r.err

    def test_preview_prints_diff_without_writing(self, boost, installed):
        skill_md = paths.store_dir() / "brainstorming" / "SKILL.md"
        before = skill_md.read_text(encoding="utf-8")
        r = boost("evolve", "brainstorming",
                 "--feedback", "Stop suggesting more than 5 ideas")
        assert "evolving brainstorming" in r.out and "(v1.4.0)" in r.out
        assert "--- a/SKILL.md" in r.out and "+++ b/SKILL.md" in r.out
        assert "+## Feedback (" in r.out
        assert "+- Stop suggesting more than 5 ideas." in r.out
        assert "re-run with --apply to write these changes" in r.out
        assert skill_md.read_text(encoding="utf-8") == before
        lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        assert lock["skills"]["brainstorming"]["version"] == "1.4.0"

    def test_apply_bumps_patch_and_relocks(self, boost, installed):
        old_sha = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))[
            "skills"]["brainstorming"]["sha256"]
        r = boost("evolve", "brainstorming", "--apply",
                 "--feedback", "Cap idea lists at 5; prefer bullet points")
        assert "evolved brainstorming → v1.4.1" in r.out
        text = (paths.store_dir() / "brainstorming" / "SKILL.md").read_text(encoding="utf-8")
        meta, body = frontmatter.parse(text)
        assert meta["version"] == "1.4.1"
        assert "- Cap idea lists at 5." in body
        assert "- prefer bullet points." in body
        entry = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))[
            "skills"]["brainstorming"]
        assert entry["version"] == "1.4.1"
        assert entry["sha256"] != old_sha
        evs = journal.events(action="evolve")
        assert evs[0]["subject"] == "brainstorming"
        assert evs[0]["version"] == "1.4.1"

    def test_ai_reply_without_bump_gets_forced_patch(self, boost, installed, ai_on):
        ai_on(ask_author="---\nname: brainstorming\ndescription: v2\n"
                         "version: 1.4.0\n---\n\n# Brainstorming v2\n\n"
                         "- Never exceed 5 ideas.\n")
        r = boost("evolve", "brainstorming", "--apply", "--feedback", "cap ideas")
        assert "evolved brainstorming → v1.4.1" in r.out
        text = (paths.store_dir() / "brainstorming" / "SKILL.md").read_text(encoding="utf-8")
        assert "Never exceed 5 ideas." in text
        assert frontmatter.parse(text)[0]["version"] == "1.4.1"


# ---------------------------------------------------------------- context

class TestContext:
    def test_map_status_unmap(self, boost, installed, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)  # not a git repo
        r = boost("context", "map", "feature/*", "tdd-workflow")
        assert "mapped feature/* → tdd-workflow" in r.out
        assert "not installed yet: tdd-workflow" in r.out
        r = boost("context", "status")
        assert "enabled" in r.out and "no" in r.out
        assert "(not in a git repository)" in r.out
        assert "feature/*" in r.out and "tdd-workflow" in r.out
        r = boost("context", "status", "--json")
        assert json.loads(r.out) == {
            "enabled": False, "branch": None,
            "rules": [{"pattern": "feature/*", "skills": ["tdd-workflow"]}]}
        r = boost("context", "unmap", "feature/*")
        assert "unmapped feature/*" in r.out
        r = boost("context", "unmap", "feature/*", expect=1)
        assert "no rule for pattern 'feature/*'" in r.err

    def test_map_requires_skills(self, boost, sandbox):
        r = boost("context", "map", "feature/*", " , ", expect=1)
        assert "no skills given" in r.err

    def test_enable_without_rules_warns(self, boost, sandbox):
        r = boost("context", "enable")
        assert "branch-aware activation enabled" in r.out
        assert "no rules configured" in r.out

    def test_branch_lifecycle(self, boost, tapped, tmp_path, monkeypatch):
        boost("install", "tdd-workflow")
        boost("install", "brainstorming")
        repo = _git_repo(tmp_path / "work")
        _git(repo, "checkout", "-qb", "feature/x")
        monkeypatch.chdir(repo)
        boost("context", "map", "feature/*", "tdd-workflow")

        r = boost("context", "enable")
        assert "branch-aware activation enabled" in r.out
        assert "active: tdd-workflow" in r.out
        link = paths.home() / ".claude" / "skills" / "tdd-workflow"
        assert link.is_symlink()

        r = boost("context", "status")
        assert "feature/x" in r.out
        assert "*" in r.out  # MATCH column

        _git(repo, "checkout", "-q", "main")
        r = boost("context", "apply")
        assert "sidelined: tdd-workflow" in r.out
        assert not link.exists()
        assert (paths.store_dir() / "tdd-workflow").is_dir()  # store intact
        # brainstorming was never mapped, so it keeps its links
        assert (paths.home() / ".claude" / "skills" / "brainstorming").is_symlink()

        r = boost("context", "apply")
        assert "nothing to change" in r.out

        r = boost("context", "disable")
        assert "branch-aware activation disabled — 1 skill(s) relinked" in r.out
        assert link.is_symlink()

    def test_apply_outside_repo(self, boost, sandbox, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = boost("context", "apply")
        assert "context is disabled (`boost context enable`) — applying anyway" in r.out
        assert "not inside a git repository — nothing to apply" in r.out


# ---------------------------------------------------------------- focus

class TestFocus:
    def test_focus_sidelines_others(self, boost, tapped):
        boost("install", "brainstorming")
        # --no-deps: this test wants exactly two installed skills; without it,
        # jira-integration would also pull in its `requires: commit-messages`.
        boost("install", "jira-integration", "--no-deps")
        r = boost("focus", "brainstorming")
        assert "focus: brainstorming" in r.out
        assert "(other 1 skills sidelined)" in r.out
        jira_link = paths.home() / ".claude" / "skills" / "jira-integration"
        assert not jira_link.exists()
        assert (paths.home() / ".claude" / "skills" / "brainstorming").is_symlink()
        assert (paths.store_dir() / "jira-integration").is_dir()  # store intact

        r = boost("focus", "--status")
        assert "focus: brainstorming" in r.out
        assert "end it with `boost focus --clear`" in r.out
        r = boost("focus", "--json")
        data = json.loads(r.out)
        assert data["active"] == ["brainstorming"]
        assert data["since"]

        r = boost("focus", "--clear")
        assert "focus cleared — 2 skill(s) restored" in r.out
        assert jira_link.is_symlink()
        assert not (paths.state_dir() / "focus.json").exists()
        r = boost("focus")
        assert "no focus session — start one with `boost focus SKILL...`" in r.out

    def test_unknown_skill(self, boost, installed):
        r = boost("focus", "nope", expect=1)
        assert "nope is not installed — focus works on installed skills" in r.err

    def test_clear_takes_no_args(self, boost, installed):
        r = boost("focus", "brainstorming", "--clear", expect=1)
        assert "--clear takes no skill arguments" in r.err


# ---------------------------------------------------------------- impact

class TestImpact:
    def test_no_skills_installed(self, boost, sandbox, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = boost("impact")
        assert "no skills installed — nothing to measure" in r.out
        r = boost("impact", "--json")
        assert json.loads(r.out) == {
            "note": "correlation, not causation — commits since install in "
                    "this repo", "skills": []}

    def test_table_outside_repo_uses_dash(self, boost, installed, tmp_path,
                                          monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = boost("impact", "brainstorming")
        assert "impact of brainstorming" in r.out
        assert "COMMITS SINCE" in r.out
        row = next(l for l in r.out.splitlines()
                   if l.startswith("brainstorming"))
        assert "—" in row
        assert FALLBACK in flat(r.out)
        assert "correlation, not causation" in r.out

    def test_named_in_repo_json(self, boost, installed, tmp_path, monkeypatch):
        repo = _git_repo(tmp_path / "repo")
        monkeypatch.chdir(repo)
        r = boost("impact", "brainstorming", "--json")
        data = json.loads(r.out)
        assert data["skills"][0]["skill"] == "brainstorming"
        # the repo's one (empty) commit was created after the install
        assert data["skills"][0]["commits_since"] == 1
        assert data["skills"][0]["files_touched"] == 0
        assert data["skills"][0]["events"] == 1
        r = boost("impact", "brainstorming")
        assert "files touched" in r.out

    def test_unknown(self, boost, installed):
        r = boost("impact", "ghost", expect=1)
        assert "ghost is not installed" in r.err

    def test_ai_paragraph(self, boost, installed, tmp_path, monkeypatch, ai_on):
        monkeypatch.chdir(tmp_path)
        ai_on(ask="This data is correlational only.")
        r = boost("impact", "brainstorming")
        assert "This data is correlational only." in r.out
        assert FALLBACK not in flat(r.out)


# ---------------------------------------------------------------- kind declines

class TestKindDeclines:
    """Skill-content commands name the kind instead of denying existence,
    and context switching stops calling installed rules missing."""

    def _seed_claude_rule(self, name="house", body="Do the thing."):
        from boost_cli.core import lockfile, rules
        cm = paths.home() / ".claude" / "CLAUDE.md"
        cm.parent.mkdir(parents=True, exist_ok=True)
        cm.write_text(rules.merge_block("# notes\n", name, body),
                      encoding="utf-8")
        lockfile.set_rule(name, {
            "kind": "rule", "version": "1.0.0", "tap": "some-tap",
            "materializations": [
                {"agent": "claude-code", "mode": "claude", "path": str(cm)}]})

    def test_evolve_declines_a_rule_by_kind(self, boost, sandbox):
        self._seed_claude_rule()
        r = boost("evolve", "house", "--feedback", "be stricter", expect=1)
        assert "house is a rule — boost evolve applies to skills" in r.err
        assert "not installed" not in r.err

    def test_focus_declines_a_rule_by_kind(self, boost, sandbox):
        self._seed_claude_rule()
        r = boost("focus", "house", expect=1)
        assert "house is a rule — boost focus applies to skills" in r.err
        assert "not installed" not in r.err

    def test_impact_declines_a_rule_by_kind(self, boost, sandbox):
        self._seed_claude_rule()
        r = boost("impact", "house", expect=1)
        assert "house is a rule — boost impact applies to skills" in r.err
        assert "not installed" not in r.err

    def test_simulate_declines_a_rule_by_kind(self, boost, sandbox):
        self._seed_claude_rule()
        r = boost("simulate", "house", expect=1)
        assert "house is a rule — this command applies to skills" in r.err
        assert "not installed" not in r.err

    def test_distill_declines_a_rule_by_kind(self, boost, tapped):
        self._seed_claude_rule()
        r = boost("distill", "brainstorming", "house", expect=1)
        assert "house is a rule — this command applies to skills" in r.err

    def test_context_map_does_not_call_an_installed_rule_missing(
            self, boost, sandbox):
        self._seed_claude_rule()
        r = boost("context", "map", "feature/*", "house")
        assert "mapped feature/* → house" in r.out
        assert "not installed" not in r.out
        assert "house is a rule" in r.out

    def test_context_apply_reports_a_mapped_rule_truthfully(
            self, boost, sandbox, tmp_path, monkeypatch):
        self._seed_claude_rule()
        repo = _git_repo(tmp_path / "repo")
        _git(repo, "checkout", "-q", "-b", "feature/x")
        monkeypatch.chdir(repo)
        boost("context", "map", "feature/*", "house")
        boost("context", "enable")
        r = boost("context", "apply")
        assert "mapped but not installed" not in r.out
        assert "house (rule)" in r.out
