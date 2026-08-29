# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: skill-information commands — list, info, cat, edit,
preview, explain, log, home, deps, tag."""
from __future__ import annotations

import json
import re
import subprocess
import sys

import pytest

from boost_cli.core import paths


@pytest.fixture()
def rival_tap(boost, tapped, tmp_path):
    """A second real tap that also ships `brainstorming`, at a louder version.

    Two taps carrying one name is the only way to reach the ambiguity error —
    and its hint — so the qualified-name path needs a genuine second clone
    rather than a hand-written cache.
    """
    root = tmp_path / "rival-tap"
    (root / "skills" / "brainstorming").mkdir(parents=True)
    (root / "skills" / "brainstorming" / "SKILL.md").write_text(
        "---\nname: brainstorming\ndescription: A rival ideation skill\n"
        "version: 9.9.9\n---\n\n# Brainstorming\n\nThe other tap's copy.\n",
        encoding="utf-8")
    run = lambda *a: subprocess.run(a, cwd=root, check=True, capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "rival@boost.test")
    run("git", "config", "user.name", "Rival Tap")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "rival skills")
    boost("tap", root)
    return "rival-tap"


def _lock():
    return json.loads(paths.lockfile_path().read_text(encoding="utf-8"))["skills"]


def _journal_events(action=None):
    out = []
    for line in paths.pulse_path().read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if action is None or e.get("action") == action:
            out.append(e)
    return out


def _skill_dir(tmp_path, name):
    d = tmp_path / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: %s\ndescription: locally imported test skill\n"
        "version: 0.1.0\n---\n\n# %s\n\nBody.\n" % (name, name), encoding="utf-8")
    return d


# ── list ─────────────────────────────────────────────────────────────────

class TestList:
    def test_table_and_count(self, boost, tapped):
        boost("install", "brainstorming", "commit-messages")
        r = boost("list")
        assert "NAME" in r.out and "VERSION" in r.out and "FLAGS" in r.out
        assert "brainstorming" in r.out and "1.4.0" in r.out
        assert "commit-messages" in r.out and "1.0.2" in r.out
        # abbreviated agents column: the linked ones only — gemini reads the
        # canonical store directly and is never symlinked
        assert "claude·windsurf·cursor" in r.out
        assert "gemini" not in r.out
        assert "2 skills" in r.out

    def test_json_pure_with_fields(self, boost, installed):
        r = boost("list", "--json")
        data = json.loads(r.out)
        # structured by kind so rules/workflows show up too (not just skills),
        # plus "project" for anything installed into the current repo.
        assert set(data) == {"skills", "rules", "workflows", "project"}
        assert list(data["skills"]) == ["brainstorming"]
        assert data["rules"] == {} and data["workflows"] == {}
        assert data["project"] == {}
        e = data["skills"]["brainstorming"]
        assert e["version"] == "1.4.0"
        assert e["tap"] == "fixture-tap"
        # the lock records real symlinks only, so gemini (which reads the
        # canonical store directly) is absent by design
        assert e["agents"] == ["claude-code", "windsurf", "cursor"]
        assert e["pinned"] is False

    def test_tag_filter(self, boost, tapped):
        boost("install", "brainstorming", "commit-messages")
        boost("tag", "brainstorming", "+fav")
        r = boost("list", "--tag", "fav")
        assert "brainstorming" in r.out
        assert "commit-messages" not in r.out
        assert "1 skill" in r.out
        assert "#fav" in r.out                    # FLAGS column
        r = boost("list", "--tag", "#nosuch")
        assert "no skills installed with tag #nosuch" in r.out

    def test_empty_state_hint(self, boost, sandbox):
        r = boost("list")
        assert "no skills installed" in r.out
        assert "boost tap --defaults && boost search <topic>" in r.out

    def _seed_rule(self, name="team-rules"):
        from boost_cli.core import lockfile
        lockfile.set_rule(name, {
            "kind": "rule", "version": "2.0.0", "tap": "acme/rules",
            "materializations": [{"agent": "claude-code", "mode": "claude"},
                                 {"agent": "cursor", "mode": "file"}]})

    def _seed_workflow(self, name="ship-it"):
        from boost_cli.core import lockfile
        lockfile.set_workflow(name, {
            "kind": "workflow", "version": "1.2.0", "tap": "acme/wf", "slot": "commands",
            "materializations": [{"agent": "claude-code", "slot": "commands"}]})

    def test_lists_installed_rules_and_workflows(self, boost, sandbox):
        self._seed_rule()
        self._seed_workflow()
        r = boost("list")
        assert "installed rules" in r.out
        assert "team-rules" in r.out and "2.0.0" in r.out
        assert "claude·cursor" in r.out          # materialized agents column
        assert "1 rule installed" in r.out
        assert "installed workflows" in r.out
        assert "ship-it" in r.out and "commands" in r.out  # SLOT column
        assert "1 workflow installed" in r.out

    def test_rules_and_workflows_show_without_skills(self, boost, sandbox):
        # empty-state must not fire (and hide them) when only non-skills exist.
        self._seed_rule()
        r = boost("list")
        assert "no skills installed" not in r.out
        assert "team-rules" in r.out

    def test_json_includes_all_kinds(self, boost, sandbox):
        self._seed_rule()
        self._seed_workflow()
        data = json.loads(boost("list", "--json").out)
        assert list(data["rules"]) == ["team-rules"]
        assert data["rules"]["team-rules"]["version"] == "2.0.0"
        assert list(data["workflows"]) == ["ship-it"]

    def test_tag_filter_excludes_rules_and_workflows(self, boost, sandbox):
        # --tag is a skill-only concept: rules/workflows must not leak into it.
        self._seed_rule()
        r = boost("list", "--tag", "fav")
        assert "team-rules" not in r.out
        assert "no skills installed with tag #fav" in r.out

    # ── --kind ───────────────────────────────────────────────────────────
    # `boost list` prints three sections, so on a machine with 25 skills the
    # one rule is off the top of the screen. --kind is how you ask for the
    # section you meant.

    def test_kind_rule_shows_only_rules(self, boost, tapped):
        boost("install", "brainstorming")
        self._seed_rule()
        self._seed_workflow()
        r = boost("list", "--kind", "rule")
        assert "team-rules" in r.out
        assert "1 rule installed" in r.out
        assert "brainstorming" not in r.out
        assert "ship-it" not in r.out
        assert "installed skills" not in r.out
        assert "installed workflows" not in r.out

    def test_kind_workflow_keeps_the_slot_column(self, boost, sandbox):
        self._seed_rule()
        self._seed_workflow()
        r = boost("list", "--kind", "workflow")
        assert "ship-it" in r.out and "SLOT" in r.out and "commands" in r.out
        assert "team-rules" not in r.out

    def test_kind_skill_excludes_rules_and_workflows(self, boost, tapped):
        boost("install", "brainstorming")
        self._seed_rule()
        r = boost("list", "--kind", "skill")
        assert "brainstorming" in r.out
        assert "team-rules" not in r.out

    def test_kind_json_keeps_the_four_key_shape(self, boost, sandbox):
        # Consumers key off a stable envelope: the other kinds go empty rather
        # than disappearing, so `data["skills"]` never raises under --kind.
        self._seed_rule()
        self._seed_workflow()
        data = json.loads(boost("list", "--kind", "rule", "--json").out)
        assert set(data) == {"skills", "rules", "workflows", "project"}
        assert list(data["rules"]) == ["team-rules"]
        assert data["workflows"] == {} and data["skills"] == {}

    def test_kind_empty_state_names_the_kind(self, boost, sandbox):
        # "no skills installed" while asking for rules is the wrong answer to
        # the question asked, and sends you looking for a skill that never was.
        r = boost("list", "--kind", "rule")
        assert "no rules installed" in r.out
        assert "no skills installed" not in r.out

    def test_kind_rejects_an_unknown_kind(self, boost, sandbox):
        r = boost("list", "--kind", "skils", expect=None)
        assert r.rc != 0
        assert "skils" in r.err or "invalid choice" in r.err

    def test_kind_non_skill_with_tag_is_an_error_not_an_empty_table(self, boost, sandbox):
        # Tags only exist on skills. Printing an empty rule table would read as
        # "you have no rules", which is a different and false statement.
        self._seed_rule()
        r = boost("list", "--kind", "rule", "--tag", "fav", expect=None)
        assert r.rc != 0
        assert "tag" in (r.err + r.out).lower()

    def test_kind_skill_with_tag_still_works(self, boost, tapped):
        boost("install", "brainstorming", "commit-messages")
        boost("tag", "brainstorming", "+fav")
        r = boost("list", "--kind", "skill", "--tag", "fav")
        assert "brainstorming" in r.out
        assert "commit-messages" not in r.out


# ── info ─────────────────────────────────────────────────────────────────

class TestInfo:
    def test_installed_fields(self, boost, installed):
        r = boost("info", "brainstorming")
        assert "brainstorming" in r.out
        assert "Structured ideation & divergent-thinking facilitation" in r.out
        assert re.search(r"version\s+1\.4\.0", r.out)
        assert re.search(r"tap\s+fixture-tap", r.out)
        assert "~/.agents/skills/brainstorming" in r.out   # ~-contracted store
        assert re.search(r"quality\s+95/100", r.out)
        assert "claude-code, windsurf, cursor" in r.out
        assert re.search(r"pinned\s+no", r.out)
        assert re.search(r"quarantined\s+no", r.out)
        # D17: identity-card badges beneath the name
        assert "[installed]" in r.out
        assert "[fixture-tap]" in r.out

    def test_tap_only_skill(self, boost, tapped):
        r = boost("info", "jira-integration")
        assert re.search(r"latest\s+2\.1\.0", r.out)
        assert re.search(r"tap\s+fixture-tap", r.out)
        assert re.search(r"source\s+skills/jira-integration", r.out)
        assert "~/.agents/skills" not in r.out      # no store line
        assert "[not installed]" in r.out           # D17 badge for tap-only
        assert re.search(r"quality\s+\d+/100", r.out)

    def test_json_pure(self, boost, installed):
        r = boost("info", "brainstorming", "--json")
        data = json.loads(r.out)
        assert data["name"] == "brainstorming"
        assert data["tap"] == "fixture-tap"
        assert data["latest"] == "1.4.0"
        assert data["installed"]["version"] == "1.4.0"
        assert data["store"] == str(paths.store_dir() / "brainstorming")
        assert data["quality"] == 95
        assert data["files"] == 1

    def test_unknown_rc1(self, boost, tapped):
        r = boost("info", "definitely-nope", expect=1)
        assert "no skill named 'definitely-nope' in any tap" in r.err

    def test_description_wraps_to_a_narrow_pane(self, boost, installed,
                                                 monkeypatch):
        # "Structured ideation & divergent-thinking facilitation" ran the kv
        # row to 69+ columns via a hardcoded textwrap width=62 that ignored
        # the real terminal — it neither shrank for a narrow pane nor grew
        # for a wide one.
        monkeypatch.setenv("COLUMNS", "60")
        r = boost("info", "brainstorming")
        for ln in r.out.split("\n"):
            assert len(ln) <= 60, ln
        assert "Structured ideation" in r.out
        assert "divergent-thinking" in r.out
        assert "facilitation" in r.out

    def test_description_does_not_wrap_needlessly_at_full_width(
            self, boost, installed, monkeypatch):
        monkeypatch.setenv("COLUMNS", "200")
        r = boost("info", "brainstorming")
        assert ("Structured ideation & divergent-thinking facilitation"
               in r.out)


class TestInfoQualifiedName:
    """`boost info owner/repo:skill` — the form the ambiguity error tells the
    user to type, which `info` itself used to reject as an invalid skill name
    because it fed the qualified string straight to `store.skill_store_dir`."""

    def test_ambiguity_hint_is_a_runnable_command(self, boost, rival_tap):
        # The headline regression: whatever the hint tells you to type must work.
        r = boost("info", "brainstorming", expect=1)
        assert "exists in multiple taps" in r.err
        m = re.search(r"qualify it, e\.g\. `([^`]+)`", r.err)
        assert m, "no qualified-name hint in: %s" % r.err
        r2 = boost("info", m.group(1))
        assert "invalid skill name" not in r2.err
        assert "brainstorming" in r2.out

    def test_qualifier_selects_the_named_tap(self, boost, rival_tap):
        r = boost("info", "rival-tap:brainstorming")
        assert re.search(r"latest\s+9\.9\.9", r.out)
        assert re.search(r"tap\s+rival-tap", r.out)
        assert "A rival ideation skill" in r.out
        r = boost("info", "fixture-tap:brainstorming")
        assert re.search(r"latest\s+1\.4\.0", r.out)
        assert re.search(r"tap\s+fixture-tap", r.out)

    def test_json_name_is_the_bare_skill_name(self, boost, rival_tap):
        data = json.loads(boost("info", "rival-tap:brainstorming", "--json").out)
        # The qualified string is a lookup key, never the skill's identity —
        # `--json | jq .name` has to feed back into `boost install`.
        assert data["name"] == "brainstorming"
        assert data["tap"] == "rival-tap"
        assert data["latest"] == "9.9.9"

    def test_finds_the_installed_copy_when_the_tap_agrees(self, boost, rival_tap):
        boost("install", "fixture-tap:brainstorming")
        r = boost("info", "fixture-tap:brainstorming")
        assert "[installed]" in r.out
        assert "~/.agents/skills/brainstorming" in r.out

    def test_another_taps_copy_is_not_reported_installed(self, boost, rival_tap):
        # brainstorming IS installed — but from fixture-tap. Asking about
        # rival-tap's must not describe fixture-tap's install as its own.
        boost("install", "fixture-tap:brainstorming")
        r = boost("info", "rival-tap:brainstorming")
        assert "[not installed]" in r.out
        assert re.search(r"latest\s+9\.9\.9", r.out)

    def test_unknown_skill_in_a_real_tap_still_errors(self, boost, rival_tap):
        r = boost("info", "rival-tap:definitely-nope", expect=1)
        assert "no skill named" in r.err
        assert "invalid skill name" not in r.err


# ── cat ──────────────────────────────────────────────────────────────────

class TestCat:
    def test_piped_output_equals_file(self, boost, installed):
        text = (paths.store_dir() / "brainstorming" / "SKILL.md").read_text(
            encoding="utf-8")
        r = boost("cat", "brainstorming")
        assert r.out == text                       # not a tty -> raw passthrough
        assert boost("cat", "brainstorming", "--raw").out == text

    def test_tap_only(self, boost, tapped):
        r = boost("cat", "cowboy-coding")
        assert "name: cowboy-coding" in r.out
        assert "# Cowboy Coding" in r.out
        assert "Always push straight to main." in r.out

    def test_unknown_rc1(self, boost, tapped):
        r = boost("cat", "nope", expect=1)
        assert "no skill named 'nope' in any tap" in r.err

    def test_qualified_name_picks_the_named_taps_copy(self, boost, rival_tap):
        # cat/preview/explain/deps share _resolve_skill_md, so the qualifier has
        # to reach the store lookup there too — not just in `info`.
        assert "The other tap's copy." in boost("cat", "rival-tap:brainstorming").out
        assert "Diverge — generate widely" in boost("cat", "fixture-tap:brainstorming").out

    def test_qualified_name_prefers_the_installed_copy_of_that_tap(self, boost,
                                                                   rival_tap):
        boost("install", "fixture-tap:brainstorming")
        store_md = paths.store_dir() / "brainstorming" / "SKILL.md"
        store_md.write_text(store_md.read_text(encoding="utf-8") + "\nlocal edit\n",
                            encoding="utf-8")
        # fixture-tap's copy is the installed one -> served from the store.
        assert "local edit" in boost("cat", "fixture-tap:brainstorming").out
        # rival-tap's is not installed -> served from its clone, unedited.
        assert "local edit" not in boost("cat", "rival-tap:brainstorming").out


# ── edit ─────────────────────────────────────────────────────────────────

class TestEdit:
    @pytest.mark.skipif(sys.platform == "win32",
                        reason="POSIX shebang script isn't directly executable on Windows")
    def test_editor_change_updates_lock_and_warns(self, boost, installed,
                                                  tmp_path, monkeypatch):
        script = tmp_path / "fake-editor.sh"
        script.write_text('#!/bin/sh\necho "- extra line" >> "$1"\n', encoding="utf-8")
        script.chmod(0o755)
        monkeypatch.setenv("EDITOR", str(script))
        monkeypatch.delenv("VISUAL", raising=False)
        sha_before = _lock()["brainstorming"]["sha256"]
        r = boost("edit", "brainstorming")
        assert ("local edits diverge from the tap source — "
                "boost drift will flag this") in r.out
        sha_after = _lock()["brainstorming"]["sha256"]
        assert sha_after != sha_before
        assert "- extra line" in (paths.store_dir() / "brainstorming" /
                                  "SKILL.md").read_text(encoding="utf-8")
        assert any(e["subject"] == "brainstorming"
                   for e in _journal_events("edit"))

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="POSIX shebang script isn't directly executable on Windows")
    def test_editor_fails_no_lock_change(self, boost, installed, tmp_path,
                                         monkeypatch):
        script = tmp_path / "fail-editor.sh"
        script.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        script.chmod(0o755)
        monkeypatch.setenv("EDITOR", str(script))
        monkeypatch.delenv("VISUAL", raising=False)
        sha_before = _lock()["brainstorming"]["sha256"]
        r = boost("edit", "brainstorming")
        assert "editor exited with status 1" in r.out
        assert "no changes" in r.out
        assert _lock()["brainstorming"]["sha256"] == sha_before

    def test_not_installed_rc1(self, boost, tapped):
        r = boost("edit", "brainstorming", expect=1)
        assert "brainstorming is not installed" in r.err


# ── preview ──────────────────────────────────────────────────────────────

class TestPreview:
    def test_renders_headings_and_fences(self, boost, installed):
        r = boost("preview", "brainstorming")
        assert "brainstorming · v1.4.0 · fixture-tap" in r.out
        assert "# Brainstorming" not in r.out      # hashes stripped
        assert "Brainstorming" in r.out
        assert "## Rules" not in r.out
        assert "Rules" in r.out
        assert "diverge -> cluster -> converge" in r.out   # fence content
        assert " • Never critique during the diverge phase." in r.out

    def test_prose_wraps_to_a_narrow_pane(self, boost, installed, monkeypatch):
        # "When the user wants to explore ideas, facilitate structured
        # divergent thinking:" (82 cols with its 2-space indent) printed
        # verbatim regardless of terminal width — preview's whole job is to
        # *render* the markdown, not dump it.
        monkeypatch.setenv("COLUMNS", "60")
        r = boost("preview", "brainstorming")
        for ln in r.out.split("\n"):
            assert len(ln) <= 60, ln
        # the sentence must still be there, just folded across lines — check
        # each half separately since the wrap point falls between them
        assert "When the user wants to explore ideas" in r.out
        assert "divergent thinking" in r.out

    def test_fence_content_is_exempt_from_wrapping(self, boost, installed,
                                                    monkeypatch):
        # code inside a ``` fence is data, not prose — it must never be
        # reflowed even when it would overflow a narrow pane.
        monkeypatch.setenv("COLUMNS", "60")
        r = boost("preview", "brainstorming")
        assert "diverge -> cluster -> converge" in r.out

    def test_list_item_wraps_and_continuation_aligns_under_the_bullet(
            self, boost, installed, monkeypatch):
        # "• Always produce at least 12 raw ideas before clustering." (58
        # cols) fits under 60 — none of this audit's real-command scans at
        # 60/80/100/120 forced this branch to actually wrap, so it shipped
        # untested. At 40 columns it must wrap. Scoped to the "Rules"
        # section onward: the titlebar line above it (out.titlebar()) is a
        # separate, pre-existing, never-wrapped decorative element this fix
        # did not touch and is not claimed to be narrow-pane-safe.
        monkeypatch.setenv("COLUMNS", "40")
        r = boost("preview", "brainstorming")
        lines = r.out.split("\n")
        rules_from = next(i for i, ln in enumerate(lines) if ln == "Rules")
        for ln in lines[rules_from:]:
            assert len(ln) <= 40, ln
        idx = next(i for i, ln in enumerate(lines)
                  if ln.startswith(" • Always produce"))
        # the continuation line must be indented to align under the bullet
        # text (prefix = " • ", 3 columns), not flush to column 0
        assert lines[idx + 1].startswith("  ")
        assert "clustering." in lines[idx + 1]


# ── explain (no AI) ──────────────────────────────────────────────────────

class TestExplain:
    def test_no_ai_fallback(self, boost, installed):
        r = boost("explain", "brainstorming")
        assert "using the heuristic fallback" in " ".join(r.out.split())
        assert "Structured ideation & divergent-thinking facilitation" in r.out
        assert "Outline:" in r.out
        assert "Brainstorming" in r.out and "Rules" in r.out
        assert "Key rules:" in r.out
        assert "• Never critique during the diverge phase." in r.out
        assert ("• Always produce at least 12 raw ideas before clustering."
                in r.out)

    def test_description_wraps_via_print_wrapped_at_a_narrow_pane(
            self, boost, installed, monkeypatch):
        # _print_wrapped (shared by explain's AI-reply and no-AI description
        # paths) used a hardcoded textwrap width=76 that ignored COLUMNS
        # entirely — at 40 columns "Structured ideation & divergent-thinking
        # facilitation" (55 cols) must now fold. Scoped to the description
        # block only (the lines before "Outline:"): the separate "Key
        # rules:" bullet list a few lines further down is a different,
        # pre-existing out.info() call this fix did not touch and is not
        # claimed to be narrow-pane-safe.
        monkeypatch.setenv("COLUMNS", "40")
        r = boost("explain", "brainstorming")
        lines = r.out.split("\n")
        desc_block = lines[:lines.index("")] if "" in lines else lines
        for ln in desc_block:
            assert len(ln) <= 40, ln
        assert len(desc_block) > 1, "description did not actually wrap"
        assert "Structured ideation" in r.out
        assert "facilitation" in r.out

    def test_faithful_ai_reply_is_shown(self, boost, installed, monkeypatch):
        from boost_cli.core import ai
        monkeypatch.setattr(ai, "available", lambda: True)
        # A grounded summary — its specifics ("clustering", "diverge") come
        # straight from brainstorming's SKILL.md.
        monkeypatch.setattr(ai, "ask", lambda *a, **k:
                            "The agent runs a diverge then cluster then converge "
                            "flow, never critiquing during diverge.")
        r = boost("explain", "brainstorming")
        assert "diverge then cluster then converge" in r.out
        assert "ungrounded" not in r.out
        assert "Key rules:" not in r.out          # showed the AI reply, no fallback

    def test_ungrounded_ai_reply_falls_back_to_extractive(self, boost, installed,
                                                          monkeypatch):
        from boost_cli.core import ai
        monkeypatch.setattr(ai, "available", lambda: True)
        # A fabricated summary naming tools the skill never mentions.
        monkeypatch.setattr(ai, "ask", lambda *a, **k:
                            "Deploys via `kubectl apply` to K8S and posts to "
                            "`slack-notify` with --webhook.")
        r = boost("explain", "brainstorming", expect=0)
        assert "ungrounded" in r.out              # the guardrail spoke
        assert "kubectl" in r.out                 # names an offending term
        # and it showed the grounded extractive summary instead
        assert "Key rules:" in r.out
        assert "• Never critique during the diverge phase." in r.out

    def test_threshold_config_can_relax_the_guardrail(self, boost, installed,
                                                      monkeypatch):
        from boost_cli.core import ai
        monkeypatch.setattr(ai, "available", lambda: True)
        monkeypatch.setattr(ai, "ask", lambda *a, **k:
                            "Runs `kubectl apply` with --webhook.")
        # Threshold 0 → nothing is ever "too ungrounded", so the AI reply shows.
        boost("config", "set", "ai.explain_faithfulness_min", "0")
        r = boost("explain", "brainstorming")
        assert "kubectl apply" in r.out
        assert "Key rules:" not in r.out


# ── log ──────────────────────────────────────────────────────────────────

class TestLog:
    def test_journal_feed_shows_install(self, boost, installed):
        r = boost("log")
        assert "install brainstorming" in r.out
        assert "tap fixture-tap" in r.out

    def test_limit_one(self, boost, installed):
        r = boost("log", "-n", "1")
        lines = [l for l in r.out.splitlines() if l.strip()]
        assert len(lines) == 1
        assert "install brainstorming" in lines[0]

    def test_negative_limit_rejected_on_every_branch(self, boost, installed):
        for extra in ([], ["--diagnostics"], ["--crashes"]):
            r = boost("log", *extra, "-n", "-1", expect=2)
            assert "argument -n/--limit: must be >= 1" in r.err

    def test_skill_git_history(self, boost, installed):
        r = boost("log", "brainstorming")
        assert "brainstorming — history in fixture-tap" in r.out
        assert "fixture skills" in r.out            # the fixture commit subject

    def test_local_import_no_upstream(self, boost, sandbox, tmp_path):
        boost("import", _skill_dir(tmp_path, "local-one"))
        r = boost("log", "local-one")
        assert "no upstream history (imported locally)" in r.out


# ── home ─────────────────────────────────────────────────────────────────

class TestHome:
    def test_print_github_tree_url_no_browser(self, boost, installed,
                                              monkeypatch):
        # surgically rewrite the tap URL to a GitHub one (clone stays local)
        cfg = json.loads(paths.config_path().read_text(encoding="utf-8"))
        cfg["taps"][0]["url"] = "https://github.com/x/y"
        paths.config_path().write_text(json.dumps(cfg), encoding="utf-8")
        opened = []
        monkeypatch.setattr("boost_cli.commands.info.webbrowser.open",
                            lambda url: opened.append(url))
        r = boost("home", "brainstorming", "--print")
        assert "https://github.com/x/y/tree/HEAD/skills/brainstorming" in r.out
        assert opened == []                        # --print never opens

    def test_local_tap_prints_path(self, boost, installed, fixture_tap_src):
        r = boost("home", "brainstorming", "--print")
        assert (fixture_tap_src.resolve() / "skills" / "brainstorming").as_posix() in r.out

    def test_unknown_rc1(self, boost, tapped):
        r = boost("home", "nope", expect=1)
        assert "no skill named 'nope' in any tap" in r.err


# ── deps ─────────────────────────────────────────────────────────────────

class TestDeps:
    def test_standalone_ok(self, boost, installed):
        r = boost("deps", "brainstorming")
        assert "requires: (none)" in r.out
        assert "conflicts: (none)" in r.out

    def test_requires_met_then_missing(self, boost, tapped):
        boost("install", "jira-integration", "commit-messages")
        r = boost("deps", "jira-integration")
        assert "requires: commit-messages ✓ installed" in r.out
        boost("uninstall", "commit-messages")
        r = boost("deps", "jira-integration", expect=1)
        assert "requires: commit-messages ✗ not installed" in r.out

    def test_conflict_pair_rc1(self, boost, tapped):
        boost("install", "tdd-workflow", "cowboy-coding")
        r = boost("deps", "tdd-workflow", expect=1)
        assert "conflicts: cowboy-coding ✗ installed (conflict!)" in r.out

    def test_json_pure(self, boost, tapped):
        boost("install", "jira-integration", "commit-messages")
        r = boost("deps", "jira-integration", "--json")
        data = json.loads(r.out)
        assert data == {"name": "jira-integration",
                        "requires": [{"name": "commit-messages",
                                      "installed": True, "requires": []}],
                        "conflicts": []}

    def test_scan_all_installed(self, boost, tapped):
        boost("install", "jira-integration", "commit-messages")
        r = boost("deps")
        assert ("no unmet requirements or conflicts across 2 skills" in r.out)
        boost("uninstall", "commit-messages")
        r = boost("deps", expect=1)
        assert "jira-integration requires commit-messages ✗ not installed" in r.out


# ── tag ──────────────────────────────────────────────────────────────────

class TestTag:
    def test_add_remove_show(self, boost, installed):
        r = boost("tag", "brainstorming", "+alpha", "+beta")
        assert "#alpha #beta" in r.out
        assert _lock()["brainstorming"]["tags"] == ["alpha", "beta"]
        r = boost("tag", "brainstorming", "-alpha")
        assert "#beta" in r.out and "#alpha" not in r.out
        assert _lock()["brainstorming"]["tags"] == ["beta"]
        r = boost("tag", "brainstorming")            # show, no change
        assert "brainstorming  #beta" in r.out

    def test_list_mapping_and_json(self, boost, tapped):
        boost("install", "brainstorming", "commit-messages")
        boost("tag", "brainstorming", "+shared")
        boost("tag", "commit-messages", "+shared", "+solo")
        r = boost("tag", "--list")
        assert "#shared" in r.out
        assert "brainstorming, commit-messages" in r.out
        assert "#solo" in r.out
        r = boost("tag", "--list", "--json")
        assert json.loads(r.out) == {
            "shared": ["brainstorming", "commit-messages"],
            "solo": ["commit-messages"]}

    def test_invalid_token_rc1(self, boost, installed):
        r = boost("tag", "brainstorming", "oops", expect=1)
        assert "cannot parse 'oops'" in r.err
        assert "prefix tags with + to add or - to remove" in r.err

    def test_not_installed_rc1(self, boost, tapped):
        r = boost("tag", "brainstorming", "+x", expect=1)
        assert "brainstorming is not installed" in r.err

    def test_journal_records_tag_event(self, boost, installed):
        boost("tag", "brainstorming", "+kept")
        events = _journal_events("tag")
        assert len(events) == 1
        assert events[0]["subject"] == "brainstorming"
        assert events[0]["tags"] == ["kept"]

    def test_operand_order_preserved_add_then_remove(self, boost, installed):
        # `+x -x` in argv order: add then remove -> nets to no tag.
        boost("tag", "brainstorming", "+x", "-x")
        assert _lock()["brainstorming"].get("tags", []) == []

    def test_operand_order_preserved_remove_then_add(self, boost, installed):
        # `-x +x`: remove (no-op on absent) then add -> nets to the tag present.
        boost("tag", "brainstorming", "-x", "+x")
        assert _lock()["brainstorming"]["tags"] == ["x"]

    def test_removal_token_not_parsed_as_option(self, boost, installed):
        # `-alpha` looks like an option but must be treated as a removal.
        boost("tag", "brainstorming", "+alpha", "+beta")
        r = boost("tag", "brainstorming", "-alpha")
        assert "#beta" in r.out and "#alpha" not in r.out
        assert _lock()["brainstorming"]["tags"] == ["beta"]

    def test_list_flag_after_name_still_lists(self, boost, tapped):
        # `--list` anywhere is a flag, not an operand.
        boost("install", "brainstorming")
        boost("tag", "brainstorming", "+shared")
        r = boost("tag", "--list")
        assert "#shared" in r.out


# ── installed rules & workflows ──────────────────────────────────────────

class TestMaterializedKinds:
    """info/cat/log/home/deps serve installed rules truthfully; edit/tag
    decline by kind — never the old "not installed" denial."""

    def _seed_claude_rule(self, name="house", body="Do the thing.",
                          pinned=False):
        from boost_cli.core import lockfile, rules
        cm = paths.home() / ".claude" / "CLAUDE.md"
        cm.parent.mkdir(parents=True, exist_ok=True)
        cm.write_text(rules.merge_block("# my own notes\n", name, body),
                      encoding="utf-8")
        lockfile.set_rule(name, {
            "kind": "rule", "version": "1.2.0", "tap": "some-tap",
            "source_file": "rules/%s.mdc" % name, "scope": "user",
            "installed_at": "2026-01-02T03:04:05Z",
            "pinned": pinned, "quarantined": False,
            "materializations": [
                {"agent": "claude-code", "mode": "claude", "path": str(cm)}]})
        return cm

    def test_info_shows_kind_version_tap_and_agents(self, boost, sandbox):
        self._seed_claude_rule()
        r = boost("info", "house")
        assert re.search(r"kind\s+rule", r.out)
        assert re.search(r"version\s+1\.2\.0", r.out)
        assert re.search(r"tap\s+some-tap", r.out)
        assert re.search(r"materialized\s+claude-code", r.out)
        assert re.search(r"pinned\s+no", r.out)
        assert re.search(r"quarantined\s+no", r.out)
        assert "not installed" not in r.out

    def test_info_reports_pinned_and_quarantined(self, boost, sandbox):
        self._seed_claude_rule()
        boost("pin", "house")
        boost("quarantine", "house")
        r = boost("info", "house")
        assert re.search(r"pinned\s+yes", r.out)
        assert re.search(r"quarantined\s+yes", r.out)

    def test_info_json_carries_kind_and_lock_entry(self, boost, sandbox):
        self._seed_claude_rule()
        r = boost("info", "house", "--json")
        data = json.loads(r.out)
        assert data["kind"] == "rule"
        assert data["name"] == "house"
        assert data["installed"]["version"] == "1.2.0"
        assert data["installed"]["materializations"][0]["agent"] == "claude-code"

    def test_cat_prints_the_materialized_block_only(self, boost, sandbox):
        self._seed_claude_rule(body="Always use two-space indents.")
        r = boost("cat", "house")
        assert "Always use two-space indents." in r.out
        assert "my own notes" not in r.out   # the managed block, not the file

    def test_preview_titles_the_rule_with_its_tap(self, boost, sandbox):
        self._seed_claude_rule()
        r = boost("preview", "house")
        assert "house" in r.out and "some-tap" in r.out
        assert "Do the thing." in r.out

    def test_cat_on_a_quarantined_rule_names_the_release(self, boost, sandbox):
        self._seed_claude_rule()
        boost("quarantine", "house")
        r = boost("cat", "house", expect=1)
        assert "rule house is quarantined" in r.err
        assert "boost quarantine --release house" in r.err

    def test_edit_declines_a_rule_by_kind(self, boost, sandbox):
        self._seed_claude_rule()
        r = boost("edit", "house", expect=1)
        assert "house is a rule — boost edit applies to skills" in r.err
        assert "not installed" not in r.err

    def test_tag_declines_a_rule_as_skill_only(self, boost, sandbox):
        self._seed_claude_rule()
        r = boost("tag", "house", "+x", expect=1)
        assert "house is a rule — boost tag applies to skills" in r.err
        assert "skill-only" in r.err
        assert "not installed" not in r.err

    def test_log_resolves_an_installed_rule(self, boost, sandbox):
        # Before find_any, this fell through to the catalog and errored
        # "no skill named 'house' in any tap" — a denial, not an answer.
        self._seed_claude_rule()
        r = boost("log", "house")
        assert "no upstream history (imported locally)" in r.out

    def test_home_resolves_an_installed_rule(self, boost, sandbox):
        self._seed_claude_rule()
        r = boost("home", "house", "--print")
        assert "rules/house.mdc" in r.out

    def test_deps_counts_an_installed_rule_as_installed(self, boost, tapped):
        # jira-integration requires commit-messages; a rule of that name is
        # installed, and requires: names an item, not a kind.
        boost("install", "jira-integration")
        from boost_cli.core import lockfile
        rp = paths.home() / ".cursor" / "rules" / "commit-messages.mdc"
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text("Always write conventional commits.\n", encoding="utf-8")
        lockfile.set_rule("commit-messages", {
            "kind": "rule", "version": "1.0.0", "tap": "some-tap",
            "materializations": [
                {"agent": "cursor", "mode": "file", "path": str(rp)}]})
        r = boost("deps", "jira-integration")
        assert "requires: commit-messages ✓ installed" in r.out
        r = boost("deps")
        assert "no unmet requirements or conflicts" in r.out
