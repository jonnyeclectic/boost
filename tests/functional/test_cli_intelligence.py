# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: Intelligence commands, in-process.

distill / simulate / infer / absorb / evolve / context / focus / impact.
Heuristic (no-AI) fallbacks are exercised first; AI branches run with
boost_cli.core.ai monkeypatched to canned replies.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys

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
    # A backend exists, so a degraded reply is blamed on the reply rather
    # than on PATH -- CI runners have no assistant CLI installed.
    monkeypatch.setattr(ai, "has_cli", lambda: True)

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
        assert FALLBACK not in flat(r.out)
        assert FALLBACK in flat(r.err)
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
        # Each source's own fenced example is structural, not a duplicate
        # heading — its opening/closing fences must both survive, balanced.
        assert text.count("```text") == 2
        assert text.count("diverge -> cluster -> converge") == 1
        assert text.count("feat(parser): tolerate folded YAML scalars") == 1
        fences = [ln for ln in text.splitlines() if ln.strip().startswith("```")]
        assert len(fences) == 4 and len(fences) % 2 == 0

    def test_install_lands_in_store_as_local(self, boost, tapped):
        r = boost("distill", "tdd-workflow", "commit-messages", "--install")
        assert "installed tdd-workflow-distilled" in r.out
        assert (paths.store_dir() / "tdd-workflow-distilled" / "SKILL.md").is_file()
        lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        entry = lock["skills"]["tdd-workflow-distilled"]
        assert entry["tap"] == "local"
        assert entry["version"] == "1.0.0"

    def test_install_replaces_an_existing_unpinned_skill_when_confirmed(
            self, boost, installed):
        # `installed` already put brainstorming on disk from the fixture tap —
        # BOOST_ASSUME_YES (the sandbox default) auto-confirms the replace.
        r = boost("distill", "tdd-workflow", "commit-messages", "-o",
                  "brainstorming", "--install")
        assert "replaced brainstorming" in r.out
        lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        entry = lock["skills"]["brainstorming"]
        assert entry["tap"] == "local"
        assert entry["version"] == "1.0.0"

    def test_yes_flag_is_accepted_by_the_parser(self, boost, installed):
        # Bug: `boost distill ... --install --yes` errored with "unrecognized
        # arguments: --yes" before out.confirm() was ever reached.
        r = boost("distill", "tdd-workflow", "commit-messages", "-o",
                  "brainstorming", "--install", "--yes")
        assert "unrecognized arguments" not in r.err
        assert "replaced brainstorming" in r.out

    def test_install_declined_leaves_the_existing_skill_and_saves_the_generation(
            self, boost, installed, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("distill", "tdd-workflow", "commit-messages", "-o",
                  "brainstorming", "--install", expect=1)
        assert "not installed: brainstorming is already installed from fixture-tap" in r.out
        assert "generated skill saved to" in r.out
        fallback = tmp_path / "brainstorming.SKILL.md"
        assert fallback.is_file()
        lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        assert lock["skills"]["brainstorming"]["tap"] == "fixture-tap"

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
        # rc=1: the install the user asked for did not happen, and a script
        # must be able to tell (it exited 0 here).
        r = boost("distill", "tdd-workflow", "commit-messages", "--install",
                  expect=1)

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

    def test_declined_install_never_overwrites_an_existing_fallback_file(
            self, boost, installed, tmp_path, monkeypatch):
        # Bug: the fallback wrote <name>.SKILL.md unconditionally, destroying a
        # user's file of that name on the very path where they declined.
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("BOOST_ASSUME_YES")
        mine = tmp_path / "brainstorming.SKILL.md"
        mine.write_bytes(b"precious notes\n")
        for n in (1, 2):
            r = boost("distill", "tdd-workflow", "commit-messages", "-o",
                      "brainstorming", "--install", expect=1)
            saved = tmp_path / ("brainstorming.%d.SKILL.md" % n)
            assert "generated skill saved to %s" % paths.tilde(saved) in flat(r.out)
            meta, _ = frontmatter.parse(saved.read_text(encoding="utf-8"))
            assert meta["name"] == "brainstorming"
        assert mine.read_bytes() == b"precious notes\n"

    def test_tap_qualified_sources_name_the_output_by_the_bare_name(
            self, boost, tapped, tmp_path, monkeypatch):
        # Bug: `fixture-tap:tdd-workflow` produced `fixture-tap:tdd-workflow-
        # distilled`, whose printed `boost import` hint then failed.
        monkeypatch.chdir(tmp_path)
        r = boost("distill", "fixture-tap:tdd-workflow",
                  "fixture-tap:commit-messages")
        assert "install it with `boost import ./tdd-workflow-distilled`" in r.out
        assert not [p for p in tmp_path.iterdir() if ":" in p.name]
        skill = tmp_path / "tdd-workflow-distilled" / "SKILL.md"
        assert frontmatter.parse(skill.read_text(encoding="utf-8"))[0]["name"] \
            == "tdd-workflow-distilled"
        boost("import", "./tdd-workflow-distilled")
        lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        assert lock["skills"]["tdd-workflow-distilled"]["tap"] == "local"

    def test_tap_qualified_install_lands_under_the_bare_name(
            self, boost, tapped, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = boost("distill", "fixture-tap:tdd-workflow",
                  "fixture-tap:commit-messages", "--install")
        assert "installed tdd-workflow-distilled" in r.out
        assert (paths.store_dir() / "tdd-workflow-distilled" / "SKILL.md").is_file()

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
        assert FALLBACK not in flat(r.out)
        assert FALLBACK in flat(r.err)
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

    def test_output_name_is_slugified_not_passed_through_raw(
            self, boost, tapped, tmp_path, monkeypatch):
        # Bug: `distill -o "Bad Name!!"` used to write a directory that
        # `boost import` then refused as an invalid skill name.
        monkeypatch.chdir(tmp_path)
        r = boost("distill", "tdd-workflow", "cowboy-coding", "-o", "Bad Name!!")
        assert (tmp_path / "bad-name" / "SKILL.md").is_file()
        assert not (tmp_path / "Bad Name!!").exists()
        assert "install it with `boost import ./bad-name`" in r.out

    @pytest.mark.parametrize("flag", ["--name", "-o", "--output"])
    def test_name_flag_and_its_older_spellings(self, boost, tapped, tmp_path,
                                               monkeypatch, flag):
        monkeypatch.chdir(tmp_path)
        boost("distill", "tdd-workflow", "cowboy-coding", flag, "combo")
        text = (tmp_path / "combo" / "SKILL.md").read_text(encoding="utf-8")
        assert frontmatter.parse(text)[0]["name"] == "combo"

    @pytest.mark.parametrize("value", ["out/merged", "merged.md", "MERGED.MD"])
    def test_a_path_for_the_name_is_refused_not_slugified(
            self, boost, tapped, tmp_path, monkeypatch, value):
        # Every sibling's -o is a FILE; distill's is a NAME. `-o /abs/x.md`
        # used to exit 0 having written ./abs-x-md/SKILL.md in the cwd.
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.chdir(work)
        r = boost("distill", "tdd-workflow", "cowboy-coding", "-o", value,
                  expect=1)
        assert ("distill takes a name for the merged skill, not a path: %s"
                % value) in r.err
        assert "pass `--name NEWNAME`" in r.err
        assert not list(work.rglob("*"))

    def test_name_and_o_together_is_a_usage_error(self, boost, tapped):
        r = boost("distill", "tdd-workflow", "cowboy-coding", "--name", "a",
                  "-o", "b", expect=2)
        assert "not allowed with argument" in r.err

    def test_output_name_with_nothing_to_slug_is_refused(
            self, boost, tapped, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = boost("distill", "tdd-workflow", "cowboy-coding", "-o", "!!!",
                  expect=1)
        assert "output name has no letters or digits" in r.err
        assert not list(tmp_path.glob("*/SKILL.md"))


# ---------------------------------------------------------------- simulate

class TestSimulate:
    def test_fallback_lists_rules_from_tap(self, boost, tapped):
        r = boost("simulate", "tdd-workflow")
        assert "simulating tdd-workflow" in r.out
        assert "(tap fixture-tap)" in r.out
        assert FALLBACK not in flat(r.out)
        assert FALLBACK in flat(r.err)
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

    def test_qualified_name_shows_bare_name_once_not_twice(self, boost, rival_tap):
        r = boost("simulate", "rival-tap:brainstorming")
        assert "simulating brainstorming  (tap rival-tap)" in r.out
        assert "With brainstorming active, Claude would:" in r.out
        assert "rival-tap:brainstorming" not in r.out

    def test_trigger_description_clips_on_word_boundary(
            self, boost, sandbox, tmp_path):
        # repro from the 2026-08 CLI audit: the 100-char clip fell mid-word
        # ("...write the test fir") with no ellipsis. It must now cut on a
        # word boundary and mark the cut.
        desc = ("Use when implementing any feature or bugfix, before "
                "writing implementation code - write the test first, "
                "always run it")
        d = tmp_path / "long-desc-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: long-desc-skill\ndescription: %s\nversion: 0.1.0\n"
            "---\n\n# long-desc-skill\n\n- Always write tests first.\n"
            % desc, encoding="utf-8")
        boost("import", d)
        r = boost("simulate", "long-desc-skill")
        assert ('likely triggers when the task involves: "Use when '
                'implementing any feature or bugfix, before writing '
                'implementation code - write the test …"') in flat(r.out)
        assert "fir\"" not in flat(r.out)


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
        # The AI-fallback note must never land on stdout: `boost infer >
        # SKILL.md` writes stdout verbatim to a file, and a warning ahead of
        # the frontmatter would corrupt it.
        assert FALLBACK not in flat(r.out)
        assert FALLBACK in flat(r.err)
        meta, _ = frontmatter.parse(r.out)
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

    def test_yes_flag_skips_the_overwrite_prompt(self, boost, sandbox, py_project,
                                                  tmp_path, monkeypatch):
        # Bug: `boost infer -o FILE --yes` errored with "unrecognized
        # arguments: --yes" on the second (overwrite) run, before
        # out.confirm() was ever reached.
        out_file = tmp_path / "SKILL.md"
        boost("infer", "--path", py_project, "-o", out_file)
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("infer", "--path", py_project, "-o", out_file, "--yes")
        assert "unrecognized arguments" not in r.err
        assert "wrote" in r.out

    def test_install(self, boost, sandbox, py_project):
        r = boost("infer", "--path", py_project, "--install")
        assert "installed project-conventions" in r.out
        assert (paths.store_dir() / "project-conventions" / "SKILL.md").is_file()
        lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        assert lock["skills"]["project-conventions"]["tap"] == "local"

    def test_refused_install_exits_nonzero_even_with_yes_and_is_not_journaled(
            self, boost, sandbox, py_project, tmp_path, monkeypatch):
        # Bug: a pinned name refused the install, yet `--install -y` exited 0
        # and journaled the infer as if it had happened.
        monkeypatch.chdir(tmp_path)
        boost("infer", "--path", py_project, "--name", "pinme", "--install")
        boost("pin", "pinme")
        before = journal.events(action="infer")
        r = boost("infer", "--path", py_project, "--name", "pinme",
                  "--install", "-y", expect=1)
        assert "not installed:" in r.out
        assert (tmp_path / "pinme.SKILL.md").is_file()
        after = journal.events(action="infer")
        assert len(after) == len(before)

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="chmod can't make a directory unwritable on Windows")
    @pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                        reason="root ignores mode bits")
    def test_install_names_an_agent_dir_that_refused_the_link(
            self, boost, sandbox, py_project):
        # _install_generated backs distill, infer and absorb --install, and
        # printed only the agents it reached.
        cursor = paths.home() / ".cursor" / "skills"
        cursor.mkdir(parents=True, exist_ok=True)
        cursor.chmod(0o500)
        try:
            r = boost("infer", "--path", py_project, "--install")
        finally:
            cursor.chmod(0o700)
        out = " ".join(r.out.split())
        assert "installed project-conventions" in out
        assert "not linked: ~/.cursor/skills is not writable" in out

    def test_ai_path(self, boost, sandbox, py_project, ai_on):
        ai_on(ask_author="---\nname: project-conventions\ndescription: AI says\n"
                         "version: 1.0.0\n---\n\n# Rules\n\n- Use ruff always.\n")
        r = boost("infer", "--path", py_project)
        assert "- Use ruff always." in r.out
        assert FALLBACK not in flat(r.out)

    def test_bad_path(self, boost, sandbox):
        r = boost("infer", "--path", "/nope/nowhere", expect=1)
        assert "is not a directory" in r.err

    def test_unwritable_output_path_is_framed_not_a_crash(
            self, boost, sandbox, py_project, tmp_path):
        # -o pointed through a path component that is a file, not a
        # directory: the mkdir/write used to run unguarded, so this escaped
        # as a raw NotADirectoryError -> exit 70 crash report.
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("", encoding="utf-8")
        out_file = blocker / "nope" / "SKILL.md"
        r = boost("infer", "--path", py_project, "-o", out_file, expect=1)
        assert str(out_file) in r.err


# ---------------------------------------------------------------- absorb

def _history_line(text):
    return json.dumps({"message": {"role": "user", "content": text}})


def _display_line(text):
    """One row of Claude Code's ~/.claude/history.jsonl (no role, no type)."""
    return json.dumps({"display": text, "pastedContents": {},
                       "project": "/work/repo", "sessionId": "s-1",
                       "timestamp": 1760000000000})


class TestAbsorb:
    def test_no_history_found(self, boost, sandbox):
        r = boost("absorb")
        assert "no chat history found under ~/.claude — nothing to absorb" in r.out
        assert "--history PATH" in r.out

    def test_limit_must_be_positive_int(self, boost, sandbox):
        # --limit 0 used to slice every recurring pattern away and fabricate
        # "no recurring patterns" even when some were found.
        r = boost("absorb", "--limit", "0", expect=2)
        assert "must be >= 1" in r.err
        r = boost("absorb", "--limit", "-1", expect=2)
        assert "must be >= 1" in r.err

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
        # Without --install, stdout carries the generated SKILL.md alone
        # (`boost absorb > SKILL.md` must not corrupt it) — the patterns
        # report goes to stderr instead.
        assert "recurring patterns from 1 history file(s)" in r.err
        assert "always run the linter before committing" in r.err
        assert "4x" in r.err
        assert "recurring patterns from 1 history file(s)" not in r.out
        assert "- Always run the linter before committing. (seen 4x)" in r.out
        assert "name: absorbed-patterns" in r.out

    def test_pattern_surfaced_from_claude_code_history_jsonl(self, boost,
                                                             sandbox):
        # Claude Code's ~/.claude/history.jsonl carries no role/type: each row
        # is one typed prompt under `display`. Every row used to be dropped.
        claude = sandbox / ".claude"
        claude.mkdir()
        (claude / "history.jsonl").write_text("\n".join(
            _display_line("always run the full test suite before committing")
            for _ in range(3)) + "\n", encoding="utf-8")
        r = boost("absorb")
        assert "recurring patterns from 1 history file(s)" in r.err
        assert "always run the full test suite before committing" in r.err
        assert "3x" in r.err
        assert ("- Always run the full test suite before committing. "
                "(seen 3x)") in r.out

    def test_history_jsonl_without_patterns_falls_back_to_projects(
            self, boost, sandbox):
        claude = sandbox / ".claude"
        (claude / "projects" / "p").mkdir(parents=True)
        (claude / "history.jsonl").write_text(
            _display_line("a one off request nobody repeats") + "\n",
            encoding="utf-8")
        (claude / "projects" / "p" / "a.jsonl").write_text("\n".join(
            _history_line("always run the linter before committing")
            for _ in range(3)) + "\n", encoding="utf-8")
        (claude / "projects" / "p" / "b.jsonl").write_text(
            _history_line("unrelated") + "\n", encoding="utf-8")
        r = boost("absorb")
        assert "recurring patterns from 2 history file(s)" in r.err
        assert "- Always run the linter before committing. (seen 3x)" in r.out

    def test_no_patterns_anywhere_counts_every_file_read(self, boost, sandbox):
        claude = sandbox / ".claude"
        (claude / "projects" / "p").mkdir(parents=True)
        (claude / "history.jsonl").write_text(
            _display_line("a one off request nobody repeats") + "\n",
            encoding="utf-8")
        (claude / "projects" / "p" / "a.jsonl").write_text(
            _history_line("another one off request here") + "\n",
            encoding="utf-8")
        r = boost("absorb")
        assert ("no recurring patterns in 2 history file(s) — absorb needs "
                "the same request 3+ times") in r.out

    def test_display_rows_and_role_rows_are_told_apart(self):
        from boost_cli.commands.intelligence import _user_texts
        assert _user_texts({"display": "fix it", "project": "/p"}) == ["fix it"]
        # A row with a role is judged by it, `display` or not.
        assert _user_texts({"role": "assistant", "display": "x",
                            "content": "y"}) == []
        assert _user_texts({"role": "user", "display": "x",
                            "content": "y"}) == ["y"]
        assert _user_texts({"display": {"text": "x"}}) == []
        assert _user_texts({"project": "/p"}) == []

    def test_display_placeholders_and_slash_commands_are_not_requests(self):
        from boost_cli.commands.intelligence import _user_texts
        assert _user_texts({"display": "[Pasted text #1 +12 lines]"}) == []
        assert _user_texts({"display": "[Image #2]"}) == []
        assert _user_texts({"display": "/clear"}) == []
        assert _user_texts({"display": "  /loop 5m /babysit-prs"}) == []
        assert _user_texts({"display": "fix this [Pasted text #3 +4 lines] "
                                       "please"}) == ["fix this   please"]

    def test_repeated_paste_placeholder_is_no_pattern(self, boost, sandbox):
        claude = sandbox / ".claude"
        claude.mkdir()
        (claude / "history.jsonl").write_text("\n".join(
            _display_line("[Pasted text #1 +12 lines]")
            for _ in range(4)) + "\n", encoding="utf-8")
        r = boost("absorb")
        assert "no recurring patterns in 1 history file(s)" in r.out

    def test_refused_install_exits_nonzero(self, boost, sandbox, tmp_path,
                                           monkeypatch):
        monkeypatch.chdir(tmp_path)
        hist = sandbox / ".claude" / "projects" / "proj"
        hist.mkdir(parents=True)
        (hist / "chat.jsonl").write_text("\n".join(
            _history_line("always run the linter before committing")
            for _ in range(3)) + "\n", encoding="utf-8")
        boost("policy", "set", "blocked_skills", "absorbed-patterns")
        r = boost("absorb", "--install", expect=1)
        assert "not installed" in r.out
        assert (tmp_path / "absorbed-patterns.SKILL.md").is_file()
        assert not (paths.store_dir() / "absorbed-patterns").exists()

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
        evs = journal.events(action="absorb")
        assert evs[0]["subject"] == "absorbed-patterns"
        assert evs[0]["patterns"] == 1
        assert evs[0]["files"] == 1

    def test_yes_flag_skips_the_replace_prompt(self, boost, sandbox, tmp_path,
                                                monkeypatch):
        # Bug: `boost absorb --install --yes` errored with "unrecognized
        # arguments: --yes" on the second (replace) run, before
        # out.confirm() was ever reached.
        monkeypatch.chdir(tmp_path)  # a declined replace would fall back to cwd
        f = tmp_path / "h.jsonl"
        f.write_text("\n".join(
            [_history_line("please write docstrings for every function")] * 3), encoding="utf-8")
        boost("absorb", "--history", f, "--install")
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("absorb", "--history", f, "--install", "--yes")
        assert "unrecognized arguments" not in r.err
        assert "replaced absorbed-patterns" in r.out

    def test_stdout_journals_too(self, boost, sandbox, tmp_path):
        f = tmp_path / "h.jsonl"
        f.write_text("\n".join(
            [_history_line("please write docstrings for every function")] * 3), encoding="utf-8")
        boost("absorb", "--history", f)
        evs = journal.events(action="absorb")
        assert evs[0]["subject"] == "absorbed-patterns"
        assert evs[0]["patterns"] == 1
        assert evs[0]["files"] == 1

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
        # The lock keeps the tap copy's digest (see the drift test below).
        assert entry["sha256"] == old_sha
        evs = journal.events(action="evolve")
        assert evs[0]["subject"] == "brainstorming"
        assert evs[0]["version"] == "1.4.1"

    def test_applied_revision_drifts_as_local_edits_not_upstream_moved(
            self, boost, installed):
        # Bug: --apply rewrote the lock sha to the store's new hash, so drift
        # read store == lock != tap as "upstream-moved" with a `boost update`
        # hint, against a tap with no new commits.
        boost("evolve", "brainstorming", "--apply", "--feedback", "be shorter")
        r = boost("drift", "--json")
        rows = {row["name"]: row for row in json.loads(r.out)["skills"]}
        assert rows["brainstorming"]["status"] == "local-edits"
        assert rows["brainstorming"]["hint"] == (
            "boost reinstall brainstorming to discard local edits")

    def test_apply_preserves_untouched_frontmatter_lines_byte_for_byte(
            self, boost, installed):
        # Bug: evolve's heuristic path parsed the whole frontmatter to a
        # dict and dumped it back, rewriting every field through dump()'s
        # own quoting rules — turning `date_added: "2026-02-27"` into the
        # bare, differently-typed `date_added: 2026-02-27` even though the
        # feedback never mentioned it.
        skill_md = paths.store_dir() / "brainstorming" / "SKILL.md"
        _, body = frontmatter.parse(skill_md.read_text(encoding="utf-8"))
        quoted_line = 'date_added: "2026-02-27"'
        skill_md.write_text(
            "---\nname: brainstorming\ndescription: v1\nversion: 1.4.0\n"
            + quoted_line + "\n---\n\n" + body, encoding="utf-8")
        boost("evolve", "brainstorming", "--apply", "--feedback", "cap ideas")
        text = skill_md.read_text(encoding="utf-8")
        assert quoted_line in text
        assert frontmatter.parse(text)[0]["version"] == "1.4.1"

    def test_ai_reply_without_bump_gets_forced_patch(self, boost, installed, ai_on):
        ai_on(ask_author="---\nname: brainstorming\ndescription: v2\n"
                         "version: 1.4.0\n---\n\n# Brainstorming v2\n\n"
                         "- Never exceed 5 ideas.\n")
        r = boost("evolve", "brainstorming", "--apply", "--feedback", "cap ideas")
        assert "evolved brainstorming → v1.4.1" in r.out
        text = (paths.store_dir() / "brainstorming" / "SKILL.md").read_text(encoding="utf-8")
        assert "Never exceed 5 ideas." in text
        assert frontmatter.parse(text)[0]["version"] == "1.4.1"

    # ---- the 2026-08 CLI audit: feedback input, pin on apply, info wording

    def _lock_entry(self):
        return json.loads(paths.lockfile_path().read_text(encoding="utf-8"))[
            "skills"]["brainstorming"]

    @pytest.mark.parametrize("value", ["", "   "])
    def test_empty_feedback_is_refused_before_anything_is_written(
            self, boost, installed, value):
        skill_md = paths.store_dir() / "brainstorming" / "SKILL.md"
        before = skill_md.read_text(encoding="utf-8")
        r = boost("evolve", "brainstorming", "--apply", "--feedback", value,
                  expect=1)
        assert "--feedback is empty" in r.err
        assert "evolving brainstorming" not in r.out
        assert "## Feedback" not in r.out
        assert skill_md.read_text(encoding="utf-8") == before
        assert self._lock_entry()["version"] == "1.4.0"
        assert journal.events(action="evolve") == []

    def test_empty_feedback_is_refused_before_the_ai_is_asked(
            self, boost, installed, ai_on, monkeypatch):
        from boost_cli.core import ai
        calls = []
        monkeypatch.setattr(ai, "ask_author",
                            lambda *a, **k: calls.append(a) or None)
        r = boost("evolve", "brainstorming", "--feedback", " ", expect=1)
        assert "--feedback is empty" in r.err
        assert calls == []

    def test_feedback_dash_reads_stdin(self, boost, installed, monkeypatch):
        monkeypatch.setattr("sys.stdin",
                            io.StringIO("Cap ideas at 5.\nPrefer bullets\n"))
        r = boost("evolve", "brainstorming", "--feedback", "-")
        assert "+- Cap ideas at 5." in r.out
        assert "+- Prefer bullets." in r.out
        assert "+- -." not in r.out

    def test_feedback_dash_with_nothing_on_stdin_is_refused(
            self, boost, installed, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        r = boost("evolve", "brainstorming", "--feedback", "-", expect=1)
        assert "--feedback - read nothing from stdin" in r.err
        assert "+- -." not in r.out

    def _capture_ai_prompt(self, ai_on, monkeypatch):
        """Turn the AI path on and record every prompt it is handed."""
        from boost_cli.core import ai
        ai_on()
        prompts = []
        monkeypatch.setattr(ai, "ask_author",
                            lambda prompt, **k: prompts.append(prompt) or None)
        return prompts

    def test_ai_is_handed_the_text_read_from_stdin_not_a_dash(
            self, boost, installed, ai_on, monkeypatch):
        prompts = self._capture_ai_prompt(ai_on, monkeypatch)
        monkeypatch.setattr("sys.stdin",
                            io.StringIO("Cap ideas at 5.\nPrefer bullets\n"))
        boost("evolve", "brainstorming", "--feedback", "-")
        assert len(prompts) == 1
        assert "FEEDBACK: Cap ideas at 5.\nPrefer bullets\n\n" in prompts[0]
        assert "FEEDBACK: -" not in prompts[0]

    def test_ai_is_handed_the_file_text_not_the_at_path(
            self, boost, installed, ai_on, monkeypatch, tmp_path):
        prompts = self._capture_ai_prompt(ai_on, monkeypatch)
        fb = tmp_path / "feedback.txt"
        fb.write_text("  Cap ideas at 5.\n", encoding="utf-8")
        boost("evolve", "brainstorming", "--feedback", "@%s" % fb)
        assert len(prompts) == 1
        assert "FEEDBACK: Cap ideas at 5.\n\n" in prompts[0]
        assert "FEEDBACK: @" not in prompts[0]
        assert str(fb) not in prompts[0]

    def test_feedback_bare_at_asks_for_a_path(self, boost, installed):
        r = boost("evolve", "brainstorming", "--feedback", "@", expect=1)
        assert "--feedback @ needs a file path" in r.err
        assert "Is a directory" not in r.err
        assert "evolving brainstorming" not in r.out

    def test_feedback_at_file_reads_the_file(self, boost, installed, tmp_path):
        fb = tmp_path / "feedback.txt"
        fb.write_text("Cap ideas at 5; prefer bullet points\n", encoding="utf-8")
        r = boost("evolve", "brainstorming", "--feedback", "@%s" % fb)
        assert "+- Cap ideas at 5." in r.out
        assert "+- prefer bullet points." in r.out
        assert "+- @" not in r.out

    def test_feedback_at_an_empty_file_is_refused(
            self, boost, installed, tmp_path):
        fb = tmp_path / "empty.txt"
        fb.write_text("", encoding="utf-8")
        r = boost("evolve", "brainstorming", "--feedback", "@%s" % fb, expect=1)
        assert "is empty" in r.err
        assert "+- @" not in r.out

    def test_feedback_at_a_missing_file_is_an_error(
            self, boost, installed, tmp_path):
        r = boost("evolve", "brainstorming", "--feedback",
                  "@%s" % (tmp_path / "nope.txt"), expect=1)
        assert "can't read --feedback @" in r.err

    def test_help_documents_stdin_and_file_forms(self, boost, sandbox):
        r = boost("evolve", "--help")
        assert "`-` reads it from stdin, `@FILE` from a file" in flat(r.out)
        assert "and pin it, so `boost update` keeps it" in flat(r.out)

    def test_apply_pins_the_revision_and_says_so(self, boost, installed):
        r = boost("evolve", "brainstorming", "--apply", "--feedback", "cap ideas")
        assert self._lock_entry()["pinned"] is True
        assert ("pinned it so `boost update` keeps this revision; "
                "`boost unpin brainstorming` lets the tap replace it") in flat(r.out)
        assert [e["subject"] for e in journal.events(action="pin")] == [
            "brainstorming"]

    def test_apply_on_an_already_pinned_skill_stays_quiet_about_it(
            self, boost, installed):
        boost("pin", "brainstorming")
        r = boost("evolve", "brainstorming", "--apply", "--feedback", "cap ideas")
        assert self._lock_entry()["pinned"] is True
        assert "pinned it so" not in r.out
        assert len(journal.events(action="pin")) == 1

    def test_update_keeps_the_revision_after_the_tap_moves(
            self, boost, fixture_tap_src, tmp_path):
        tap = tmp_path / "moving-tap"
        shutil.copytree(fixture_tap_src, tap)
        boost("tap", tap)
        boost("install", "brainstorming")
        boost("evolve", "brainstorming", "--apply", "--feedback", "cap ideas")
        md = tap / "skills" / "brainstorming" / "SKILL.md"
        md.write_text(md.read_text(encoding="utf-8") + "\nupstream edit\n",
                      encoding="utf-8")
        _git(tap, "commit", "-aqm", "move brainstorming")

        r = boost("update")
        assert "refreshed brainstorming" not in r.out
        text = (paths.store_dir() / "brainstorming" / "SKILL.md").read_text(
            encoding="utf-8")
        assert "- cap ideas." in text
        assert "upstream edit" not in text
        assert self._lock_entry()["version"] == "1.4.1"
        # outdated still shows the tap moved, marked as held by the pin
        r = boost("outdated")
        assert "1.4.1 (pinned)" in r.out
        assert "pinned and quarantined items stay put" in r.out

    def test_info_after_apply_is_ahead_not_an_update(self, boost, installed):
        boost("evolve", "brainstorming", "--apply", "--feedback", "cap ideas")
        r = boost("info", "brainstorming")
        assert "update available" not in r.out
        assert "[ahead of tap]" in r.out
        assert "(older than installed)" in r.out
        assert "[pinned]" in r.out
        r = boost("outdated")
        assert "everything up to date" in r.out


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
            "enabled": False, "branch": None, "git": True,
            "rules": [{"pattern": "feature/*", "skills": ["tdd-workflow"]}]}
        r = boost("context", "unmap", "feature/*")
        assert "unmapped feature/*" in r.out
        r = boost("context", "unmap", "feature/*", expect=1)
        assert "no rule for pattern 'feature/*'" in r.err

    def test_map_resolves_a_tap_qualified_installed_skill(
            self, boost, tapped, tmp_path, monkeypatch):
        boost("install", "commit-messages")
        boost("install", "tdd-workflow")
        repo = _git_repo(tmp_path / "repo")
        monkeypatch.chdir(repo)
        r = boost("context", "map", "main", "fixture-tap:commit-messages")
        assert "mapped main → commit-messages" in r.out
        assert "not installed" not in r.out
        r = boost("context", "status", "--json")
        assert json.loads(r.out)["rules"] == [
            {"pattern": "main", "skills": ["commit-messages"]}]
        boost("context", "map", "feature/*", "tdd-workflow")
        r = boost("context", "apply")
        assert "sidelined: tdd-workflow" in r.out
        assert "not installed" not in r.out
        assert (paths.home() / ".claude" / "skills" / "commit-messages").is_symlink()

    def test_apply_resolves_a_rule_saved_tap_qualified(
            self, boost, tapped, tmp_path, monkeypatch):
        # Rules written before `map` stored bare names keep working.
        boost("install", "commit-messages")
        boost("install", "tdd-workflow")
        paths.state_dir().mkdir(parents=True, exist_ok=True)
        (paths.state_dir() / "context.json").write_text(json.dumps(
            {"enabled": True, "rules": [
                {"pattern": "main", "skills": ["fixture-tap:commit-messages"]},
                {"pattern": "feature/*", "skills": ["tdd-workflow"]}]}), encoding="utf-8")
        repo = _git_repo(tmp_path / "repo")
        monkeypatch.chdir(repo)
        r = boost("context", "apply")
        assert "sidelined: tdd-workflow" in r.out
        assert "not installed" not in r.out
        assert (paths.home() / ".claude" / "skills" / "commit-messages").is_symlink()

    def test_map_requires_skills(self, boost, sandbox):
        r = boost("context", "map", "feature/*", " , ", expect=1)
        assert "no skills given" in r.err

    def test_status_empty_hint_fits_a_narrow_pane(self, boost, sandbox,
                                                   monkeypatch):
        # "no rules — add one with `boost context map 'feature/*'
        # skill1,skill2`" ran 71 columns unwrapped (it is now an
        # empty_state whose hint carries the command); 60 is well inside the
        # narrow-terminal range this CLI is audited at.
        monkeypatch.setenv("COLUMNS", "60")
        r = boost("context", "status")
        for ln in r.out.split("\n"):
            assert len(ln) <= 60, ln
        assert "`boost context map 'feature/*' skill1,skill2`" in r.out

    def test_help_has_no_line_over_60_columns(self, boost, sandbox,
                                              monkeypatch):
        # the hand-written subparsers metavar
        # "status|enable|disable|map|unmap|apply" overflowed a 60-column pane.
        monkeypatch.setenv("COLUMNS", "60")
        r = boost("context", "--help")
        for ln in r.out.split("\n"):
            assert len(ln) <= 60, ln
        assert "enable" in r.out and "unmap" in r.out

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
        # Held aside, out of the store Gemini CLI and Codex read directly.
        assert not os.path.lexists(paths.store_dir() / "tdd-workflow")
        assert (paths.held_skills_dir() / "tdd-workflow" / "SKILL.md").is_file()
        # brainstorming was never mapped, so it keeps its links
        assert (paths.home() / ".claude" / "skills" / "brainstorming").is_symlink()

        from boost_cli.core import lockfile
        assert lockfile.get_skill("tdd-workflow")["sidelined_by"] == "context"

        r = boost("context", "apply")
        assert "nothing to change" in r.out

        r = boost("context", "disable")
        assert "branch-aware activation disabled — 1 skill(s) relinked" in r.out
        assert link.is_symlink()
        assert "sidelined_by" not in lockfile.get_skill("tdd-workflow")

    def test_disable_counts_only_skills_it_actually_relinks(
            self, boost, tapped, tmp_path, monkeypatch):
        # `link_agents(name).linked` used to drive the count: it relinks
        # unconditionally and is truthy for any mapped skill with an enabled
        # agent, so a still-active skill that was never sidelined got counted
        # as "relinked" right alongside the one `disable` actually restored.
        boost("install", "tdd-workflow")
        boost("install", "brainstorming")
        repo = _git_repo(tmp_path / "work")
        _git(repo, "checkout", "-qb", "feature/x")
        monkeypatch.chdir(repo)
        boost("context", "map", "feature/*", "tdd-workflow")
        boost("context", "map", "chore/*", "brainstorming")

        boost("context", "enable")
        from boost_cli.core import lockfile
        # tdd-workflow's pattern matches the current branch — never sidelined.
        assert "sidelined_by" not in lockfile.get_skill("tdd-workflow")
        # brainstorming's pattern does not — sidelined by context.
        assert lockfile.get_skill("brainstorming")["sidelined_by"] == "context"

        r = boost("context", "disable")
        assert "branch-aware activation disabled — 1 skill(s) relinked" in r.out
        assert "sidelined_by" not in lockfile.get_skill("brainstorming")

    def test_apply_outside_repo(self, boost, sandbox, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = boost("context", "apply")
        assert ("context is disabled (`boost context enable`) — applying anyway"
                in r.err)
        assert "not inside a git repository — nothing to apply" in r.out

    def test_status_and_apply_report_missing_git_binary_distinctly(
            self, boost, sandbox, tmp_path, monkeypatch):
        # A repo that genuinely has no branch must not be worded the same as
        # a machine with no `git` on PATH — the CLI audit found both cases
        # collapsed into the same "(not in a git repository)" text.
        from boost_cli.core import gitutil
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(gitutil, "has_git", lambda: False)

        r = boost("context", "status")
        assert "(git not found on PATH)" in r.out
        assert "not in a git repository" not in r.out
        r = boost("context", "status", "--json")
        assert json.loads(r.out)["git"] is False
        assert json.loads(r.out)["branch"] is None

        r = boost("context", "apply")
        assert "git not found on PATH — nothing to apply" in r.out


# ---------------------------------------------------------------- focus

class TestFocus:
    def test_focus_sidelines_others(self, boost, tapped):
        from boost_cli.core import lockfile

        boost("install", "brainstorming")
        # --no-deps: this test wants exactly two installed skills; without it,
        # jira-integration would also pull in its `requires: commit-messages`.
        boost("install", "jira-integration", "--no-deps")
        r = boost("focus", "brainstorming")
        assert "focus: brainstorming" in r.out
        assert "(other 1 skill sidelined)" in r.out
        jira_link = paths.home() / ".claude" / "skills" / "jira-integration"
        assert not jira_link.exists()
        assert (paths.home() / ".claude" / "skills" / "brainstorming").is_symlink()
        # Held aside, out of the store Gemini CLI and Codex read directly.
        assert not os.path.lexists(paths.store_dir() / "jira-integration")
        assert (paths.held_skills_dir() / "jira-integration" / "SKILL.md"
                ).is_file()

        r = boost("focus", "--status")
        assert "focus: brainstorming" in r.out
        assert "end it with `boost focus --clear`" in r.out
        r = boost("focus", "--json")
        data = json.loads(r.out)
        assert data["active"] == ["brainstorming"]
        assert data["since"]

        r = boost("focus", "--clear")
        # Only jira-integration was actually sidelined by this session —
        # brainstorming stayed linked throughout, so it must not be counted.
        # The old count came from `link_agents(name).linked`, which relinks
        # unconditionally and was truthy for every non-quarantined skill.
        assert "focus cleared — 1 skill(s) restored" in r.out
        assert jira_link.is_symlink()
        assert "sidelined_by" not in lockfile.get_skill("jira-integration")
        assert not (paths.state_dir() / "focus.json").exists()
        r = boost("focus")
        assert "○ no focus session" in r.out
        assert "→ start one with `boost focus SKILL...`" in r.out

    def test_clear_with_no_session_reports_no_session(self, boost, installed):
        # Verified live: `focus --clear` with nothing focused used to say
        # "focus cleared — 2 skill(s) restored" — the count of every
        # non-quarantined skill with an enabled agent, not of anything this
        # command actually changed.
        r = boost("focus", "--clear")
        assert "no focus session" in r.out
        assert "restored" not in r.out

    def test_clear_leaves_a_context_sidelined_skill_alone(
            self, boost, tapped, tmp_path, monkeypatch):
        from boost_cli.core import lockfile

        for n in ("brainstorming", "commit-messages", "tdd-workflow"):
            boost("install", n, "--no-deps")
        repo = _git_repo(tmp_path / "repo")
        monkeypatch.chdir(repo)
        boost("context", "map", "feature/*", "tdd-workflow")
        r = boost("context", "enable")
        assert "sidelined: tdd-workflow" in r.out
        r = boost("focus", "brainstorming")
        assert "(other 1 skill sidelined)" in r.out
        assert lockfile.get_skill("tdd-workflow")["sidelined_by"] == "context"
        r = boost("focus", "--clear")
        assert "focus cleared — 1 skill(s) restored" in r.out
        skills = paths.home() / ".claude" / "skills"
        assert (skills / "commit-messages").is_symlink()
        assert not (skills / "tdd-workflow").exists()
        assert lockfile.get_skill("tdd-workflow")["sidelined_by"] == "context"

    def test_focusing_a_context_sidelined_skill_puts_it_back_at_clear(
            self, boost, tapped, tmp_path, monkeypatch):
        from boost_cli.core import lockfile

        for n in ("brainstorming", "commit-messages", "tdd-workflow"):
            boost("install", n, "--no-deps")
        repo = _git_repo(tmp_path / "repo")
        monkeypatch.chdir(repo)
        boost("context", "map", "feature/*", "tdd-workflow")
        boost("context", "enable")
        assert lockfile.get_skill("tdd-workflow")["sidelined_by"] == "context"
        boost("focus", "tdd-workflow")
        state = json.loads((paths.state_dir() / "focus.json").read_text(
            encoding="utf-8"))
        assert state["prior"] == {"tdd-workflow": "context"}
        skills = paths.home() / ".claude" / "skills"
        assert (skills / "tdd-workflow").is_symlink()
        # A re-focus keeps the record: tdd-workflow is a focus sideline now.
        boost("focus", "brainstorming")
        assert json.loads((paths.state_dir() / "focus.json").read_text(
            encoding="utf-8"))["prior"] == {"tdd-workflow": "context"}
        r = boost("focus", "--clear")
        assert "focus cleared — 2 skill(s) restored" in r.out
        assert ("sidelined again, as before the focus: tdd-workflow"
                in flat(r.out))
        assert not os.path.lexists(skills / "tdd-workflow")
        assert (skills / "commit-messages").is_symlink()
        assert lockfile.get_skill("tdd-workflow")["sidelined_by"] == "context"

    def test_a_disabled_context_is_not_put_back(
            self, boost, tapped, tmp_path, monkeypatch):
        from boost_cli.core import lockfile

        for n in ("brainstorming", "tdd-workflow"):
            boost("install", n, "--no-deps")
        repo = _git_repo(tmp_path / "repo")
        monkeypatch.chdir(repo)
        boost("context", "map", "feature/*", "tdd-workflow")
        boost("context", "enable")
        boost("focus", "tdd-workflow")
        boost("context", "disable")
        r = json.loads(boost("focus", "--clear", "--json").out)
        assert r == {"active": [], "restored": 1, "residelined": [],
                     "had_session": True}
        assert "sidelined_by" not in lockfile.get_skill("tdd-workflow")
        assert (paths.home() / ".claude" / "skills" / "tdd-workflow"
                ).is_symlink()

    def test_status_names_a_focused_skill_a_profile_set_aside(
            self, boost, tapped):
        boost("install", "tdd-workflow", "--no-deps")
        boost("profile", "save", "onlytdd")
        boost("install", "brainstorming", "--no-deps")
        boost("focus", "brainstorming")
        boost("profile", "use", "onlytdd")
        r = boost("focus", "--status")
        assert "focus: brainstorming" in r.out
        assert ("brainstorming is not linked — sidelined by `boost profile` "
                "since the focus began") in flat(r.out)
        data = json.loads(boost("focus", "--json").out)
        assert data["displaced"] == {
            "brainstorming": "sidelined by `boost profile`"}

    def test_an_intact_focus_has_nothing_displaced(self, boost, tapped):
        boost("install", "brainstorming")
        boost("focus", "brainstorming")
        r = boost("focus", "--status")
        assert "not linked" not in r.out + r.err
        assert json.loads(boost("focus", "--json").out)["displaced"] == {}

    def test_focus_set_and_clear_json(self, boost, tapped):
        boost("install", "brainstorming")
        boost("install", "jira-integration", "--no-deps")
        r = json.loads(boost("focus", "brainstorming", "--json").out)
        assert r == {"active": ["brainstorming"], "sidelined": 1}
        r = json.loads(boost("focus", "--clear", "--json").out)
        assert r == {"active": [], "restored": 1, "residelined": [],
                     "had_session": True}

    def test_clear_with_no_session_json(self, boost, installed):
        r = json.loads(boost("focus", "--clear", "--json").out)
        assert r == {"active": [], "restored": 0, "residelined": [],
                     "had_session": False}

    def test_unknown_skill(self, boost, installed):
        r = boost("focus", "nope", expect=1)
        assert "nope is not installed — focus works on installed skills" in r.err

    def test_clear_takes_no_args(self, boost, installed):
        r = boost("focus", "brainstorming", "--clear", expect=1)
        assert "--clear takes no skill arguments" in r.err


# ---------------------------------------------------------------- impact

class TestImpact:
    def test_no_skills_installed(self, boost, sandbox, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)  # not a git repo
        r = boost("impact")
        assert "○ no skills installed" in r.out
        assert "→ boost install <skill> to start" in r.out
        r = boost("impact", "--json")
        assert json.loads(r.out) == {
            "note": "not inside a git repository — commit counts unavailable",
            "git": True, "skills": []}

    def test_table_outside_repo_uses_dash(self, boost, installed, tmp_path,
                                          monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = boost("impact", "brainstorming")
        assert "impact of brainstorming" in r.out
        assert "COMMITS SINCE" in r.out
        row = next(l for l in r.out.splitlines()
                   if l.startswith("brainstorming"))
        assert "—" in row
        assert FALLBACK not in flat(r.out)
        assert FALLBACK in flat(r.err)
        # outside a repo the note says why the count is missing, rather than
        # the in-repo correlation caveat that made no sense without one.
        assert "not inside a git repository — commit counts unavailable" in r.out
        assert "correlation, not causation" not in r.out
        r = boost("impact", "brainstorming", "--json")
        data = json.loads(r.out)
        assert data["note"] == "not inside a git repository — commit counts unavailable"
        assert data["git"] is True
        assert data["skills"][0]["commits_since"] is None

    def test_named_in_repo_json(self, boost, installed, tmp_path, monkeypatch):
        repo = _git_repo(tmp_path / "repo")
        monkeypatch.chdir(repo)
        r = boost("impact", "brainstorming", "--json")
        data = json.loads(r.out)
        assert data["note"] == ("correlation, not causation — commits since "
                                "install in this repo")
        assert data["git"] is True
        assert data["skills"][0]["skill"] == "brainstorming"
        # the repo's one (empty) commit was created after the install
        assert data["skills"][0]["commits_since"] == 1
        assert data["skills"][0]["files_touched"] == 0
        assert data["skills"][0]["events"] == 1
        r = boost("impact", "brainstorming")
        assert "files touched" in r.out
        assert "correlation, not causation" in r.out

    def test_no_git_binary_reports_note_and_json_flag(
            self, boost, installed, tmp_path, monkeypatch):
        from boost_cli.core import gitutil
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(gitutil, "has_git", lambda: False)
        r = boost("impact", "brainstorming", "--json")
        data = json.loads(r.out)
        assert data["git"] is False
        assert data["note"] == "not inside a git repository — commit counts unavailable"
        assert data["skills"][0]["commits_since"] is None

    def test_unknown(self, boost, installed):
        r = boost("impact", "ghost", expect=1)
        assert "ghost is not installed" in r.err

    def test_ai_paragraph(self, boost, installed, tmp_path, monkeypatch, ai_on):
        monkeypatch.chdir(tmp_path)
        ai_on(ask="This data is correlational only.")
        r = boost("impact", "brainstorming")
        assert "This data is correlational only." in r.out
        assert FALLBACK not in flat(r.out)

    def test_a_failed_ai_call_still_warns(self, boost, installed, tmp_path,
                                          monkeypatch, ai_on):
        # Previously silent: AI was available, the call was made, and it came
        # back empty — impact printed the table and said nothing about it.
        monkeypatch.chdir(tmp_path)
        ai_on(ask=None)
        r = boost("impact", "brainstorming")
        assert FALLBACK in flat(r.err)


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


# ------------------------------------------- AI-authored names and bad replies

WRONG_NAME = ("---\nname: something-else\ndescription: AI wrote it\n"
              "version: 1.0.0\n---\n\n# Body\n\n- An AI rule.\n")
JUNK = "{not json [[ garbage"
JUNK_NOTE = ("AI reply was not usable (no SKILL.md frontmatter) — see "
             "~/.boost/logs/boost.log — using the heuristic fallback")


class TestAuthoredName:
    """The model is asked for a name and does not always write it; the file
    must carry the name the user asked for, whatever the reply said."""

    def _history(self, tmp_path):
        f = tmp_path / "h.jsonl"
        f.write_text("\n".join(
            [_history_line("please write docstrings for every function")] * 3),
            encoding="utf-8")
        return f

    def test_distill_writes_the_requested_name(self, boost, tapped, tmp_path,
                                               monkeypatch, ai_on):
        monkeypatch.chdir(tmp_path)
        ai_on(ask_author=WRONG_NAME)
        r = boost("distill", "brainstorming", "tdd-workflow",
                  "--name", "merged-one")
        text = (tmp_path / "merged-one" / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---\nname: merged-one\ndescription: AI wrote it\n")
        assert "- An AI rule." in text
        assert FALLBACK not in flat(r.err)

    def test_infer_output_carries_the_requested_name(self, boost, sandbox,
                                                     py_project, tmp_path,
                                                     ai_on):
        ai_on(ask_author=WRONG_NAME)
        out_file = tmp_path / "inf" / "SKILL.md"
        boost("infer", "--path", py_project, "--name", "my-conv", "-o", out_file)
        meta, body = frontmatter.parse(out_file.read_text(encoding="utf-8"))
        assert meta["name"] == "my-conv"
        assert "- An AI rule." in body

    def test_infer_refuses_a_name_with_nothing_to_slug(self, boost, sandbox,
                                                       py_project):
        r = boost("infer", "--path", py_project, "--name", "!!!", expect=1)
        assert "skill name has no letters or digits: '!!!'" in r.err

    def test_absorb_prints_the_absorbed_name(self, boost, sandbox, tmp_path,
                                             ai_on):
        ai_on(ask_author=WRONG_NAME)
        r = boost("absorb", "--history", self._history(tmp_path))
        assert "name: absorbed-patterns\n" in r.out
        assert "something-else" not in r.out
        assert "- An AI rule." in r.out

    def test_evolve_apply_keeps_the_installed_name(self, boost, installed,
                                                   ai_on):
        ai_on(ask_author=WRONG_NAME.replace("1.0.0", "1.4.1"))
        r = boost("evolve", "brainstorming", "--apply", "--feedback", "terser")
        assert "evolved brainstorming → v1.4.1" in r.out
        text = (paths.store_dir() / "brainstorming" / "SKILL.md").read_text(
            encoding="utf-8")
        assert frontmatter.parse(text)[0]["name"] == "brainstorming"
        assert "- An AI rule." in text

    def test_distill_junk_reply_says_why(self, boost, tapped, tmp_path,
                                         monkeypatch, ai_on):
        monkeypatch.chdir(tmp_path)
        ai_on(ask_author=JUNK)
        r = boost("distill", "brainstorming", "tdd-workflow", "--name", "m3")
        assert JUNK_NOTE in flat(r.err)
        assert "AI unavailable" not in flat(r.err)
        assert (tmp_path / "m3" / "SKILL.md").is_file()

    def test_infer_junk_reply_says_why(self, boost, sandbox, py_project, ai_on):
        ai_on(ask_author=JUNK)
        r = boost("infer", "--path", py_project)
        assert JUNK_NOTE in flat(r.err)
        assert r.out.startswith("---\nname: project-conventions\n")

    def test_absorb_junk_reply_says_why(self, boost, sandbox, tmp_path, ai_on):
        ai_on(ask_author=JUNK)
        r = boost("absorb", "--history", self._history(tmp_path))
        assert JUNK_NOTE in flat(r.err)

    def test_evolve_junk_reply_says_why(self, boost, installed, ai_on):
        ai_on(ask_author=JUNK)
        r = boost("evolve", "brainstorming", "--feedback", "be terser")
        assert JUNK_NOTE in flat(r.err)
        assert "+- be terser." in r.out
