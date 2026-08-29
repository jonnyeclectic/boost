# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for :mod:`boost_cli.core.bmad` — the autopilot's brain.

Three things are worth pinning here, because all three are load-bearing for
`boost bmad on` and none of them are obvious from reading the code:

1. **Classification is precedence-ordered, not first-match.** Real prompts hit
   several keyword tables at once ("add tests for the scanner" is both a build
   verb and a testing noun); the tie-break table is what decides the lead
   persona, so it gets its own tests rather than being implied by one example.
2. **Trivia must stay silent.** The router runs on *every* prompt. A question
   that gets a five-line delegation banner is worse than no router at all, so
   the silence cases are tested as hard as the routing ones.
3. **The done-checklist is derived from the repo, not hardcoded.** It names the
   test dir, roadmap dir and gate command that actually exist, which is the
   difference between a checklist an agent can act on and boilerplate it skips.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from boost_cli.core import bmad

_STAMP = re.compile(r"<!-- boost:bmad-persona [0-9a-f]{12} -->")

# --------------------------------------------------------------- classification

class TestClassifyTrivial:
    """The router sees every prompt; these must produce no banner at all."""

    @pytest.mark.parametrize("prompt", [
        "",
        "   \n  ",
        "thanks",
        "ok cool",
        "/roadmap-loop",
        "/loop 5m /babysit-prs",
    ])
    def test_empty_short_and_slash_commands_are_trivial(self, prompt):
        assert bmad.classify(prompt) == "trivial"

    @pytest.mark.parametrize("prompt", [
        "what does scan_dir do?",
        "why is the eval gate flooring four metrics?",
        "how do I add a command to boost?",
        "which agent gets a symlink and which does not?",
        "where does the lock file live",
    ])
    def test_informational_questions_are_trivial(self, prompt):
        assert bmad.classify(prompt) == "trivial"

    def test_a_long_question_is_not_trivial(self):
        """An interrogative opener stops meaning "quick question" past ~30 words."""
        prompt = (
            "how should we restructure the retrieval layer so that the dense "
            "engine and the BM25 engine share one index build path, given that "
            "the eval gate floors four metrics and the mutation gate only "
            "targets core, and we also need the docs regenerated for it"
        )
        assert bmad.classify(prompt) != "trivial"

    @pytest.mark.parametrize("prompt", [
        "fix the flaky test in test_catalog, no bmad",
        "add a command — skip bmad for this one",
    ])
    def test_explicit_opt_out_is_honored(self, prompt):
        assert bmad.classify(prompt) == "trivial"

    def test_a_modal_request_is_not_trivial(self):
        """"can you fix X" is a request wearing a question mark."""
        assert bmad.classify("can you fix the crash in store.install?") == "build"

    def test_a_slash_command_is_silent_even_when_it_reads_like_a_task(self):
        """A slash command carries its own instructions; never talk over it.

        The short slash cases above are also caught by the word-count floor, so
        this one is long enough and task-shaped enough to route if the leading
        `/` were not checked in its own right.
        """
        assert bmad.classify(
            "/code-review fix the failing tests in the catalog scanner") == "trivial"

    def test_a_three_word_task_still_routes(self):
        """MIN_WORDS is a floor on acknowledgements, not on terse instructions."""
        assert bmad.classify("fix the bug") == "build"

    def test_a_prompt_matching_no_track_is_trivial(self):
        """Long enough, not a question, no slash — only the zero-score guard
        keeps this silent, so it is the only test that holds that guard."""
        assert bmad.classify("hello there my friend") == "trivial"

    def test_a_question_followed_by_an_instruction_is_not_a_question(self):
        """The gate anchors on the first token, which used to swallow these."""
        assert bmad.classify(
            "Why is test_catalog flaky on Windows? Fix it and add a regression "
            "test.") == "quality"
        assert bmad.classify(
            "Where the CSS grid wraps, the cards overlap. Fix the layout.") == "ux"

    def test_a_dotted_identifier_is_not_a_sentence_boundary(self):
        """`SKILL.md` and `store.install` must not read as end-of-sentence."""
        assert bmad.classify("what does store.install do with SKILL.md?") == "trivial"

    def test_a_question_of_exactly_the_cutoff_length_is_trivial(self):
        """The boundary itself is inclusive — 30 words is still a question."""
        prompt = ("how should we handle the case where a tap has no SKILL.md at "
                  "all and the scanner must fix it without crashing the whole "
                  "catalog build for everyone here today")
        assert len(prompt.split()) == bmad.QUESTION_MAX_WORDS
        assert bmad.classify(prompt) == "trivial"


class TestClassifyTracks:
    @pytest.mark.parametrize("prompt,track", [
        # build is the catch-all workhorse, so it must lose every tie
        ("implement the new install command", "build"),
        ("fix the crash when a tap has no SKILL.md", "build"),
        ("migrate the annotations to PEP 585", "build"),
        # quality outranks build: "add tests" is Murat's job, not Amelia's
        ("add tests for catalog.scan_dir", "quality"),
        ("fix the flaky test in the functional suite", "quality"),
        ("the mutation gate dropped below 80, raise coverage", "quality"),
        # docs
        ("update the README for the new flag", "docs"),
        ("write a migration guide for v3 lock files", "docs"),
        # planning / product
        ("add a roadmap item for the Gemini sanitizer", "planning"),
        ("write the PRD for the policy engine", "product"),
        ("break the epic into stories", "product"),
        # architecture / ux / discovery
        ("design the schema for the pulse feed", "architecture"),
        ("the install command's output layout looks off, fix the spacing", "ux"),
        ("research how other CLIs pin their toolchains", "discovery"),
        # review
        ("review the changes on this branch", "review"),
    ])
    def test_known_prompts_land_on_the_right_track(self, prompt, track):
        assert bmad.classify(prompt) == track

    def test_every_track_has_a_lead_persona_that_exists(self):
        slugs = {p.slug for p in bmad.PERSONAS}
        for name, track in bmad.TRACKS.items():
            assert track.lead in slugs, "%s leads with unknown persona" % name
            for s in track.support:
                assert s in slugs, "%s supports with unknown persona" % name

    def test_every_track_routes_at_a_skill_its_lead_actually_drives(self):
        """Only the `build` row is pinned end to end by the golden banner, and
        mutmut generates no mutants for a module-level dict — so without this
        the other eight rows could be edited to anything."""
        for name, track in bmad.TRACKS.items():
            lead = bmad.PERSONA_BY_SLUG[track.lead]
            assert track.skill in lead.skills, (
                "track %r routes at %r, which %s does not drive"
                % (name, track.skill, lead.character))
            assert track.lead not in track.support
            assert track.note.endswith((".", "!"))

    def test_track_order_covers_every_track_exactly_once(self):
        assert sorted(bmad.TRACK_ORDER) == sorted(bmad.TRACKS)
        assert len(bmad.TRACK_ORDER) == len(set(bmad.TRACK_ORDER))

    def test_build_is_the_lowest_precedence_track(self):
        """Anything more specific than "change some code" must outrank build."""
        assert bmad.TRACK_ORDER[-1] == "build"

    def test_classification_is_case_insensitive(self):
        assert bmad.classify("ADD TESTS FOR THE SCANNER") == "quality"


# ------------------------------------------------------------- project signals

class TestProjectSignals:
    def test_bare_directory_reports_nothing_found(self, tmp_path):
        sig = bmad.project_signals(tmp_path)
        assert sig["tests"] is None
        assert sig["roadmap"] is None
        assert sig["gate"] is None
        assert sig["docs"] == []
        assert sig["guide"] is None

    def test_detects_a_boost_shaped_repo(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "docs" / "roadmap" / "items").mkdir(parents=True)
        (tmp_path / "README.md").write_text("hi", encoding="utf-8")
        (tmp_path / "CLAUDE.md").write_text("rules", encoding="utf-8")
        (tmp_path / "Makefile").write_text(
            "venv:\n\techo\ncheck: lint test\n\techo\n", encoding="utf-8")

        sig = bmad.project_signals(tmp_path)
        assert sig["tests"] == "tests/"
        assert sig["roadmap"] == "docs/roadmap/items/"
        assert sig["gate"] == "make check"
        assert sig["guide"] == "CLAUDE.md"
        assert "README.md" in sig["docs"] and "docs/" in sig["docs"]

    def test_make_test_is_the_fallback_when_there_is_no_check_target(self, tmp_path):
        # the target deliberately is NOT the first line: `^` has to be anchoring
        # per-line, or a real Makefile (which opens with variables) never matches
        (tmp_path / "Makefile").write_text(
            "PY := .venv/bin/python\n\ntest:\n\tpytest\n", encoding="utf-8")
        assert bmad.project_signals(tmp_path)["gate"] == "make test"

    def test_a_target_named_mid_line_is_not_a_target(self, tmp_path):
        """`^` must anchor: "no-check: ..." is not the `check` target."""
        (tmp_path / "Makefile").write_text(
            "help:\n\t@echo 'run check: to lint'\n", encoding="utf-8")
        assert bmad.project_signals(tmp_path)["gate"] is None

    def test_a_makefile_that_is_not_utf8_still_yields_its_gate(self, tmp_path):
        """Undecodable bytes must degrade to a replacement char, not to no gate."""
        (tmp_path / "Makefile").write_bytes(b"# caf\xe9 build\ncheck:\n\ttrue\n")
        assert bmad.project_signals(tmp_path)["gate"] == "make check"

    def test_npm_test_script(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"scripts": {"test": "vitest run"}}), encoding="utf-8")
        assert bmad.project_signals(tmp_path)["gate"] == "npm test"

    def test_corrupt_package_json_does_not_raise(self, tmp_path):
        (tmp_path / "package.json").write_text("{oops", encoding="utf-8")
        assert bmad.project_signals(tmp_path)["gate"] is None

    @pytest.mark.parametrize("marker,gate", [
        ("pyproject.toml", "pytest"),
        ("Cargo.toml", "cargo test"),
        ("go.mod", "go test ./..."),
    ])
    def test_language_default_gates(self, tmp_path, marker, gate):
        (tmp_path / marker).write_text("", encoding="utf-8")
        assert bmad.project_signals(tmp_path)["gate"] == gate

    def test_makefile_wins_over_language_default(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
        assert bmad.project_signals(tmp_path)["gate"] == "make check"

    def test_agents_md_is_recognised_as_a_guide(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("x", encoding="utf-8")
        assert bmad.project_signals(tmp_path)["guide"] == "AGENTS.md"

    def test_roadmap_falls_back_to_a_plain_file(self, tmp_path):
        (tmp_path / "ROADMAP.md").write_text("x", encoding="utf-8")
        assert bmad.project_signals(tmp_path)["roadmap"] == "ROADMAP.md"

    def test_unreadable_root_degrades_to_empty(self, tmp_path):
        sig = bmad.project_signals(tmp_path / "does-not-exist")
        assert sig["tests"] is None and sig["docs"] == []


class TestDoneChecklist:
    def test_names_the_paths_that_exist(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "docs" / "roadmap" / "items").mkdir(parents=True)
        (tmp_path / "README.md").write_text("x", encoding="utf-8")
        (tmp_path / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
        items = bmad.done_checklist(bmad.project_signals(tmp_path))
        assert items == [
            "tests: add or update coverage under `tests/`, and run them",
            "docs: update `README.md` / `docs/` wherever the change shows",
            "roadmap: create or claim the item under `docs/roadmap/items/`",
            "gate: `make check` green, with real output",
        ]

    def test_the_bare_repo_wording_is_the_fallback_not_a_path(self, tmp_path):
        assert bmad.done_checklist(bmad.project_signals(tmp_path)) == [
            "tests: cover the change, and run whatever suite exists",
            "docs: write down what changed for the next reader",
        ]

    def test_always_demands_tests_and_docs_even_in_a_bare_repo(self, tmp_path):
        line = " ".join(bmad.done_checklist(bmad.project_signals(tmp_path)))
        assert "test" in line.lower()
        assert "doc" in line.lower()

    def test_no_roadmap_means_no_roadmap_clause(self, tmp_path):
        line = " ".join(bmad.done_checklist(bmad.project_signals(tmp_path)))
        assert "roadmap" not in line.lower()

    def test_a_repo_guide_is_named_as_binding(self, tmp_path):
        """CLAUDE.md/AGENTS.md outrank anything the banner itself says."""
        (tmp_path / "CLAUDE.md").write_text("rules", encoding="utf-8")
        items = bmad.done_checklist(bmad.project_signals(tmp_path))
        assert items[-1] == "`CLAUDE.md` is binding"

    def test_no_gate_means_no_gate_clause(self, tmp_path):
        line = " ".join(bmad.done_checklist(bmad.project_signals(tmp_path)))
        assert "green" not in line


# ------------------------------------------------------------------- rendering

class TestRouteContext:
    def test_trivial_prompts_render_nothing(self, tmp_path):
        assert bmad.route_context("what is a tap?", tmp_path) == ""
        assert bmad.route_lines("what is a tap?", tmp_path) == []

    def test_a_build_prompt_names_lead_support_skill_and_dod(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
        text = bmad.route_context("implement the new export command", tmp_path)
        assert "BMAD" in text
        assert "bmad-dev" in text            # lead persona subagent
        assert "Amelia" in text              # ...named, so the banner reads human
        assert "bmad-tea" in text            # support
        assert "bmad-build" in text          # the canonical v6 implementation skill
        assert "make check" in text          # repo-derived definition of done
        assert "tests/" in text

    def test_the_banner_stays_short(self, tmp_path):
        """It is prepended to every substantive prompt — it cannot be an essay."""
        text = bmad.route_context("implement the new export command", tmp_path)
        assert len(bmad.route_lines("implement the new export command", tmp_path)) <= 8
        assert len(text) < 1200

    def test_it_tells_the_agent_not_to_wait_for_a_human(self, tmp_path):
        text = bmad.route_context("fix the crash in store.install", tmp_path)
        assert "autonom" in text.lower()

    def test_quality_prompts_lead_with_the_test_architect(self, tmp_path):
        text = bmad.route_context("add tests for catalog.scan_dir", tmp_path)
        assert "bmad-tea" in text and "Murat" in text

    def test_it_reads_the_root_it_is_given_not_the_cwd(self, tmp_path):
        """The hook reports `cwd`; the router must use it, not its own.

        Asserted with a test dir boost itself does not have (`spec/`), because a
        banner built from the wrong root still looks plausible when both roots
        happen to be Python repos with a `tests/`.
        """
        (tmp_path / "spec").mkdir()
        text = bmad.route_context("implement the export command", tmp_path)
        assert "spec/" in text
        assert "tests/" not in text

    def test_the_whole_banner_is_exactly_this(self, tmp_path):
        """The banner *is* the product — pin it verbatim, not by keyword.

        Every line here is read by a model on every substantive turn, so a
        silent edit to the wording is a behaviour change and should fail a test
        rather than slip through on a `"bmad-dev" in text` assertion.
        """
        (tmp_path / "tests").mkdir()
        (tmp_path / "README.md").write_text("x", encoding="utf-8")
        (tmp_path / "Makefile").write_text(
            "PY := python\n\ncheck: lint test\n\ttrue\n", encoding="utf-8")

        assert bmad.route_lines("implement the new export command", tmp_path) == [
            "[BMAD autopilot] track: build",
            "Lead: `bmad-dev` subagent — Amelia, Senior Software Engineer. "
            "Ship it complete and verified.",
            "Support: `bmad-tea` (Murat), `bmad-scribe` (Paige) — spawn them "
            "with the Agent tool, in parallel where the work is independent.",
            "BMAD skill: `bmad-build` — invoke it if it is installed; otherwise "
            "the persona's own playbook stands.",
            "Done means: tests: add or update coverage under `tests/`, and run "
            "them · docs: update `README.md` wherever the change shows · "
            "gate: `make check` green, with real output",
            "Work autonomously through to a finished, verified change; stop to "
            "ask only when a choice would change what gets delivered.",
        ]

    def test_route_context_joins_the_lines_with_newlines(self, tmp_path):
        lines = bmad.route_lines("implement the export command", tmp_path)
        assert bmad.route_context("implement the export command", tmp_path) == (
            "\n".join(lines))
        assert len(lines) > 1        # ...so the join is actually doing something


class TestOrientation:
    def test_names_only_live_v6_skills(self):
        """v6 deprecated the shims this text used to advertise.

        `bmad-quick-dev` and `bmad-dev-story` are now redirect shims; the
        canonical implementation workflow is `bmad-build`. Naming a shim sent
        every build task through a deprecation notice.
        """
        text = bmad.orientation()
        assert "bmad-build" in text
        assert "bmad-quick-dev" not in text
        assert "bmad-dev-story" not in text
        assert "bmad-create-story" not in text

    def test_does_not_claim_a_persona_that_bmm_does_not_ship(self):
        """Paige is a game-dev-studio agent, on hiatus in bmm."""
        assert "bmad-agent-tech-writer" not in bmad.orientation()

    def test_lists_the_persona_subagents(self):
        text = bmad.orientation()
        for p in bmad.PERSONAS:
            assert p.slug in text

    def test_the_roster_is_one_aligned_line_per_persona(self):
        lines = bmad.orientation().splitlines()
        roster = [ln for ln in lines if ln.startswith("  bmad-")]
        assert len(roster) == len(bmad.PERSONAS)
        assert "  bmad-dev        Amelia, Senior Software Engineer" in roster

    def test_it_names_the_command_that_turns_it_off(self):
        assert "boost bmad off" in bmad.orientation()


# -------------------------------------------------------------------- personas

class TestPersonaFiles:
    def test_roster_is_well_formed(self):
        slugs = [p.slug for p in bmad.PERSONAS]
        assert len(slugs) == len(set(slugs))
        for p in bmad.PERSONAS:
            assert p.slug.startswith("bmad-")
            # Claude Code rejects ':' and expects lowercase-with-hyphens names
            assert p.slug == p.slug.lower() and ":" not in p.slug
            assert p.character and p.title and p.mission

    def test_markdown_has_valid_subagent_frontmatter(self):
        md = bmad.persona_markdown(bmad.PERSONAS[0])
        assert md.startswith("---\n")
        body = md.split("---\n", 2)[1]
        assert "name: " in body and "description: " in body
        assert "model: inherit" in body
        # boost never escalates permissions on the user's behalf
        assert "permissionMode" not in md
        assert bmad.MARKER in md

    def test_the_frontmatter_block_is_exactly_this(self):
        """Claude reads these four keys; a wrong one loads nothing and says so
        nowhere. The description is quoted because it contains `.` and `(`
        after a colon, which bare YAML would mis-parse."""
        md = bmad.persona_markdown(bmad.PERSONA_BY_SLUG["bmad-ux"])
        lines = md.splitlines()
        assert lines[:6] == [
            "---",
            "name: bmad-ux",
            'description: "Sally, UX Designer (BMAD bmm). Use PROACTIVELY for '
            'interface and layout work, visual hierarchy, spacing, responsive '
            'behaviour, accessibility, or a design review."',
            "model: inherit",
            "color: pink",
            "---",
        ]
        assert re.fullmatch(r"<!-- boost:bmad-persona [0-9a-f]{12} -->", lines[6])

    def test_rendering_is_deterministic(self):
        """Two renders must agree, or every `bmad on` would rewrite every file."""
        for persona in bmad.PERSONAS:
            assert bmad.persona_markdown(persona) == bmad.persona_markdown(persona)


class TestOwnershipStamp:
    """`on` must not clobber an edited persona and `off` must not delete one.

    Marker *presence* used to decide this, which was wrong in both directions:
    the marker is an HTML comment a user editing the body has no reason to
    remove, so their work was silently overwritten and then deleted while boost
    printed that hand edits were left in place.
    """

    def test_boost_owns_what_it_just_wrote(self):
        assert bmad.is_managed(bmad.persona_markdown(bmad.PERSONAS[0]))

    @pytest.mark.parametrize("edit", [
        lambda md: md.replace("Mission:", "MY MISSION:"),          # body edited
        lambda md: md.replace("model: inherit", "model: opus"),    # frontmatter
        lambda md: md + "\nextra instruction\n",                   # appended
        lambda md: md.replace("<!-- boost:bmad-persona", "<!-- mine"),
    ])
    def test_any_edit_releases_the_claim(self, edit):
        md = bmad.persona_markdown(bmad.PERSONA_BY_SLUG["bmad-ux"])
        assert not bmad.is_managed(edit(md))

    def test_a_forged_digest_is_not_ownership(self):
        md = bmad.persona_markdown(bmad.PERSONA_BY_SLUG["bmad-ux"])
        forged = _STAMP.sub("<!-- boost:bmad-persona 000000000000 -->", md)
        assert not bmad.is_managed(forged)

    def test_an_unstamped_file_is_never_ours(self):
        assert not bmad.is_managed("---\nname: bmad-ux\n---\nmine\n")
        assert not bmad.is_managed("")

    def test_write_skips_a_file_it_does_not_own(self, tmp_path):
        bmad.write_personas(tmp_path)
        mine = tmp_path / "bmad-dev.md"
        mine.write_text("---\nname: bmad-dev\n---\nmy own version\n",
                        encoding="utf-8")

        written, skipped = bmad.write_personas(tmp_path)
        assert skipped == ["bmad-dev"]
        # every *other* persona is still refreshed: one customised file must not
        # stop the rest from being updated
        assert written == sorted(
            p.slug for p in bmad.PERSONAS if p.slug != "bmad-dev")
        assert mine.read_text(encoding="utf-8").endswith("my own version\n")

    def test_write_skips_a_stamped_file_whose_body_was_edited(self, tmp_path):
        """The case marker-presence got wrong: stamp kept, body changed."""
        bmad.write_personas(tmp_path)
        mine = tmp_path / "bmad-dev.md"
        edited = mine.read_text(encoding="utf-8").replace(
            "Mission:", "Mission (mine):")
        mine.write_text(edited, encoding="utf-8")

        written, skipped = bmad.write_personas(tmp_path)
        assert skipped == ["bmad-dev"] and "bmad-dev" not in written
        assert mine.read_text(encoding="utf-8") == edited
        # ...and `off` must not delete it either
        assert "bmad-dev" not in bmad.remove_personas(tmp_path)
        assert mine.exists()

    def test_the_playbook_renders_one_bullet_per_line(self):
        persona = bmad.PERSONA_BY_SLUG["bmad-ux"]
        md = bmad.persona_markdown(persona)
        bullets = [ln for ln in md.splitlines() if ln.startswith("- ")]
        assert bullets == ["- %s" % b for b in persona.playbook]

    def test_the_skills_line_lists_every_skill_comma_separated(self):
        md = bmad.persona_markdown(bmad.PERSONA_BY_SLUG["bmad-tea"])
        assert ("BMAD skills to prefer when they are installed: "
                "`bmad-qa-generate-e2e-tests`, `bmad-code-review`.") in md

    def test_write_personas_creates_missing_parent_directories(self, tmp_path):
        """`~/.claude/agents` usually does not exist yet on a first install."""
        nested = tmp_path / "home" / ".claude" / "agents"
        bmad.write_personas(nested)
        assert (nested / "bmad-dev.md").is_file()

    def test_write_creates_one_file_per_persona(self, tmp_path):
        written, skipped = bmad.write_personas(tmp_path)
        assert written == sorted(p.slug for p in bmad.PERSONAS)
        assert skipped == []
        for slug in written:
            assert (tmp_path / ("%s.md" % slug)).is_file()

    def test_write_is_idempotent(self, tmp_path):
        bmad.write_personas(tmp_path)
        first = (tmp_path / "bmad-dev.md").read_text(encoding="utf-8")
        written, skipped = bmad.write_personas(tmp_path)
        assert (tmp_path / "bmad-dev.md").read_text(encoding="utf-8") == first
        assert len(list(tmp_path.glob("*.md"))) == len(bmad.PERSONAS)
        # an untouched file is still ours, so it is rewritten rather than skipped
        assert skipped == [] and len(written) == len(bmad.PERSONAS)

    def test_installed_personas_reports_what_is_on_disk(self, tmp_path):
        assert bmad.installed_personas(tmp_path) == []
        bmad.write_personas(tmp_path)
        assert bmad.installed_personas(tmp_path) == sorted(
            p.slug for p in bmad.PERSONAS)

    def test_remove_only_touches_boost_authored_files(self, tmp_path):
        bmad.write_personas(tmp_path)
        # a hand-written agent that happens to share the prefix must survive
        mine = tmp_path / "bmad-dev.md"
        mine.write_text("---\nname: bmad-dev\n---\nmy own edit\n", encoding="utf-8")
        (tmp_path / "unrelated.md").write_text("keep me", encoding="utf-8")

        assert bmad.remove_personas(tmp_path) == sorted(
            p.slug for p in bmad.PERSONAS if p.slug != "bmad-dev")
        assert mine.exists()
        assert (tmp_path / "unrelated.md").exists()
        assert not (tmp_path / "bmad-pm.md").exists()

    def test_remove_on_a_missing_dir_is_a_no_op(self, tmp_path):
        assert bmad.remove_personas(tmp_path / "nope") == []

    def test_an_undeletable_persona_is_skipped_not_reported_removed(
            self, tmp_path, monkeypatch):
        """`off` reports what it actually deleted, not what it tried to."""
        bmad.write_personas(tmp_path)
        real_unlink = Path.unlink

        def refuse(self, *a, **kw):
            if self.name == "bmad-dev.md":
                raise OSError("read-only file system")
            return real_unlink(self, *a, **kw)

        monkeypatch.setattr(Path, "unlink", refuse)
        assert bmad.remove_personas(tmp_path) == sorted(
            p.slug for p in bmad.PERSONAS if p.slug != "bmad-dev")
        assert (tmp_path / "bmad-dev.md").exists()

    def test_every_persona_body_carries_the_done_contract(self):
        for p in bmad.PERSONAS:
            md = bmad.persona_markdown(p)
            low = md.lower()
            assert "test" in low and "doc" in low

    def test_persona_descriptions_are_delegation_triggers(self):
        """Claude picks a subagent off `description`; it must say when to use it."""
        for p in bmad.PERSONAS:
            desc = bmad.persona_description(p)
            assert len(desc) > 40
            assert "\n" not in desc
