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
from typing import ClassVar

import pytest

from boost_cli.core import bmad

_STAMP = re.compile(r"<!-- boost:bmad-persona [0-9a-f]{12} -->")

def _pinned_skills() -> set[str]:
    """The skills `bmad-method@BMAD_VERSION` installs, from the checked-in list."""
    path = (Path(__file__).parent / "data"
            / ("bmad-skills-%s.json" % bmad.BMAD_VERSION))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == bmad.BMAD_VERSION
    return set(data["skills"])


class TestPinnedRelease:
    """Every BMAD skill boost names exists in the release it installs.

    The tables were only ever checked against each other, so a name that went
    stale in both passed: the docs track routed at `bmad-document-project`
    after BMAD 6.12.0 stopped installing it. A bump of `BMAD_VERSION` without a
    regenerated `tests/unit/data/bmad-skills-<version>.json` fails here.
    """

    def test_the_snapshot_is_the_pinned_version(self):
        assert len(_pinned_skills()) == 29

    def test_every_persona_skill_is_installed_by_the_pin(self):
        for p in bmad.PERSONAS:
            assert set(p.skills) <= _pinned_skills(), p.slug

    def test_every_track_skill_is_installed_by_the_pin(self):
        for name, track in bmad.TRACKS.items():
            assert track.skill is None or track.skill in _pinned_skills(), name

    def test_docs_routes_at_no_skill_and_says_nothing_about_one(self, tmp_path):
        assert bmad.TRACKS["docs"].skill is None
        lines = bmad.route_lines("update the README for the new flag", tmp_path)
        assert lines[0] == "[BMAD autopilot] track: docs"
        assert not any(line.startswith("BMAD skill:") for line in lines)
        assert lines[3].startswith("Done means:")

    def test_the_briefing_does_not_promise_a_skill_on_every_banner(self):
        """`docs` routes at none, so "the BMAD skill for that track" was a
        claim the banner stopped honouring."""
        assert "the BMAD skill for that track when one fits" in bmad.orientation()

    def test_the_skills_that_need_a_runtime_are_real(self):
        assert set(bmad.RUNTIME_SKILLS) <= _pinned_skills()


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


class TestEvidenceScalesWithLength:
    """One keyword is strong signal in a short prompt and noise in a long one.

    Found in production on the day the autopilot shipped: a user pasted their
    terminal session back into the chat and got a full delegation banner, on the
    strength of `\\bupdate\\b` matching inside "boost self-update". ~90 words,
    one weak hit. The shape gates could not catch it — it is not a question, not
    a slash command, and far past the word floor — so the missing rule is about
    evidence density, not shape.
    """

    # the actual paste, trimmed of ANSI and the shell prompt lines
    PASTE = """boost self-update
  updating via pipx: /opt/homebrew/bin/pipx upgrade boost-skill-cli
  boost v1.0.419 -> v1.0.420
boost bmad on
  BMAD autopilot ON (global) - 7 persona subagent(s) + prompt router
  personas -> ~/.claude/agents
  hooks -> ~/.claude/settings.json (SessionStart + UserPromptSubmit)
  every substantive prompt now names its lead persona and its definition of
  done; trivial asks are left alone
  restart your agent session to pick up the new subagents
  full BMAD workflow skills (needs Node): boost bmad install
boost bmad install
  installed BMAD in /Users/cassandragaston/IdeaProjects/boost (46 skills)"""

    def test_the_paste_that_prompted_this_rule_is_silent(self):
        assert len(self.PASTE.split()) > bmad.LONG_PROMPT_WORDS
        assert bmad.classify(self.PASTE) == "trivial"

    def test_it_is_the_length_that_silences_it_not_the_words(self):
        """The same weak evidence in a short prompt must still route."""
        assert bmad.classify("update the flag") == "build"

    def test_a_long_prompt_with_real_evidence_still_routes(self):
        """Two hits is enough — genuine long asks name the work more than once."""
        prompt = (
            "I have been going back and forth on this for a while and I think "
            "the cleanest thing is to refactor the retrieval layer so that the "
            "dense engine and the BM25 engine share one index build path, "
            "because right now they diverge in ways that are hard to reason "
            "about and it keeps biting us whenever somebody touches either "
            "one of them, so please update the module boundary as well while "
            "you are in there and leave it tidy for the next person"
        )
        assert len(prompt.split()) > bmad.LONG_PROMPT_WORDS
        assert bmad.classify(prompt) == "build"

    def test_exactly_two_hits_is_enough_past_the_cutoff(self):
        """The long-prompt rule asks for two hits, not three."""
        prompt = "please refactor it and update it " + "blah " * bmad.LONG_PROMPT_WORDS
        assert len(prompt.split()) > bmad.LONG_PROMPT_WORDS
        assert bmad.classify(prompt) == "build"

    def test_one_hit_at_exactly_the_cutoff_still_routes(self):
        """The cutoff is exclusive: a 60-word prompt is still short enough."""
        prompt = "please refactor it " + "blah " * (bmad.LONG_PROMPT_WORDS - 3)
        assert len(prompt.split()) == bmad.LONG_PROMPT_WORDS
        assert bmad.classify(prompt) == "build"

    def test_repeating_one_keyword_is_not_more_evidence(self):
        """Scoring counts distinct patterns, not occurrences — so a long log
        that says "update" twenty times still scores 1 and stays silent."""
        wordy = ("please update it " * 20) + ("blah " * bmad.LONG_PROMPT_WORDS)
        assert bmad.classify(wordy) == "trivial"

    def test_a_question_of_exactly_the_cutoff_length_is_trivial(self):
        """The boundary itself is inclusive — 30 words is still a question."""
        prompt = ("how should we handle the case where a tap has no SKILL.md at "
                  "all and the scanner must fix it without crashing the whole "
                  "catalog build for everyone here today")
        assert len(prompt.split()) == bmad.QUESTION_MAX_WORDS
        assert bmad.classify(prompt) == "trivial"


class TestPromptsThatAreNotTasks:
    """Pasted output, yes/no questions and read-and-tell asks.

    Replayed over one real history, 35% of regular prompts got a banner, and a
    judge found a clear failure in 29 of 41 sampled. These shapes were most of
    it, each reproduced with synthetic prompts: pasted output 4 of 5 routed,
    yes/no questions 11 of 11, read-and-tell 4 of 5.
    """

    PYTEST = (
        "    def test_scan(tmp_path):\n"
        ">       assert scan_dir(tmp_path) == 3\n"
        "E       AssertionError: assert 2 == 3\n"
        "tests/unit/test_catalog.py:42: AssertionError\n"
        "FAILED tests/unit/test_catalog.py::test_scan - AssertionError")
    GIT_STATUS = (
        "On branch main\n"
        "Changes not staged for commit:\n"
        '  (use "git add <file>..." to update what will be committed)\n'
        "\tmodified:   boost_cli/core/bmad.py\n"
        'no changes added to commit (use "git add" and/or "git commit -a")')
    NPM = (
        "npm WARN deprecated glob@7.2.3: no longer supported\n"
        "added 812 packages, and audited 813 packages in 14s\n"
        "  3 vulnerabilities (1 moderate, 2 high)\n"
        "  npm audit fix\n"
        "> app@1.0.0 build\n"
        "> vite build --mode production")
    TRACEBACK = (
        "Traceback (most recent call last):\n"
        '  File "/app/export.py", line 12, in <module>\n'
        "    main()\n"
        "ValueError: bad row in the build step, fix needed")

    @pytest.mark.parametrize("paste", ["PYTEST", "GIT_STATUS", "NPM", "TRACEBACK"])
    def test_pasted_output_alone_is_silent(self, paste):
        assert bmad.classify(getattr(self, paste)) == "trivial"

    @pytest.mark.parametrize("line", [
        "$ make build",
        "==================== short test summary info ====================",
        "2026-09-17 build started",
        "12:03:44 build started",
        "npm ERR! build failed",
        "  npm audit fix",
        "Traceback (most recent call last):",
        "E       AssertionError: build != fix",
        ">       assert build_it() == 3",
        "concurrent.futures.TimeoutError: the build hung",
        "DeprecationWarning: build is deprecated",
        "RuntimeException: build failed",
        "Your branch is behind, update it",
        "Untracked files: fix",
        "nothing to commit, update later",
        "Changes to be committed: build",
        "PASSED the build",
        "SKIPPED the build",
        "ERROR the build",
    ])
    def test_each_machine_shape_counts_as_output(self, line):
        """Three copies of one machine line and one person's line: a paste."""
        prompt = "\n".join([line] * 3 + ["please fix it"])
        assert bmad.classify(prompt) == "trivial"

    @pytest.mark.parametrize("prompt", [
        # an indented task list — indentation alone is not machine output
        "Do these:\n  - add a test for scan_dir\n  - update the docs\n"
        "  - run make check",
        "here's what I need:\n  1. add a retry to the fetcher\n"
        "  2. write a test for it\n  3. update the changelog",
        # a hard-wrapped request, indented as prose wraps
        "Please update the installer so it writes the lock file\n"
        "  atomically, and add a regression test that kills the\n"
        "  mutant where the rename is dropped.",
    ])
    def test_an_indented_request_is_not_a_paste(self, prompt):
        """The indent rule silenced ordinary multi-line asks: a bullet list and
        a wrapped sentence are indented too, and each routes as one line."""
        assert bmad.classify(prompt) != "trivial"

    def test_a_fenced_paste_does_not_outvote_the_ask_around_it(self):
        """The fence is pasted material inside a request, not the request."""
        prompt = ("Add a retry to this function and a test for it:\n"
                  "```python\ndef fetch(url):\n    r = requests.get(url)\n"
                  "    return r.json()\n```")
        assert bmad.classify(prompt) == "quality"

    def test_a_person_asking_over_a_paste_still_routes(self):
        """Two hits in the typed lines are the evidence a paste needs."""
        prompt = ("the export crashes on bad rows, fix it and add a regression "
                  "test:\n" + self.TRACEBACK)
        assert bmad.classify(prompt) == "quality"

    def test_one_word_over_a_paste_is_not_enough(self):
        """The accepted loss: "fix this:" over a paste goes silent."""
        assert bmad.classify("fix this:\n" + self.PYTEST) == "trivial"

    def test_three_lines_can_be_a_paste(self):
        assert bmad.classify("update it\n  x = 1\n  y = 2") == "trivial"

    def test_the_typed_lines_of_a_paste_stay_separate_words(self):
        assert bmad.classify("refactor\nupdate\n  x = 1\n  y = 2") == "build"

    def test_two_lines_are_not_a_paste(self):
        assert bmad.classify("update the flag\n  in the config") == "build"

    def test_mostly_prose_is_not_a_paste(self):
        prompt = ("fix the crash\nin the exporter\n  when a row is empty\n"
                  "and ship it")
        assert bmad.classify(prompt) == "build"

    def test_half_machine_output_is_a_paste(self):
        """At least half the lines, not more than half."""
        prompt = "update it\nplease\n  x = 1\n  y = 2"
        assert bmad.classify(prompt) == "trivial"

    def test_blank_lines_are_neither(self):
        prompt = "update it\n\n\n  x = 1"
        assert bmad.classify(prompt) == "build"

    @pytest.mark.parametrize("prompt", [
        "are there any tests for the parser?",
        "is the export command documented?",
        "do we have docs for the export command?",
        "does the migration need a schema change?",
        "did you update the docs?",
        "has anyone added tests for this?",
        "have you added tests for it?",
        "should we refactor the scanner?",
        "can the scanner build its cache offline?",
        "could you explain how the scanner builds its cache?",
        "would you please describe the schema?",
        "will you tell me what the release changed?",
        "can we summarise the review?",
    ])
    def test_a_yes_no_question_is_silent(self, prompt):
        assert bmad.classify(prompt) == "trivial"

    @pytest.mark.parametrize("prompt,track", [
        ("can you fix the crash in store.install?", "build"),
        ("could you add tests for the parser?", "quality"),
        ("would you refactor the scanner please?", "build"),
        ("will we update the README for the new flag?", "docs"),
        # no question mark: an instruction that opens with "do"
        ("do the migration for the orders table", "build"),
        # another sentence follows: the question was a preamble
        ("Is the parser tested? Add tests for it.", "quality"),
    ])
    def test_a_request_shaped_like_a_question_still_routes(self, prompt, track):
        assert bmad.classify(prompt) == track

    def test_a_long_yes_no_question_is_a_brief(self):
        prompt = ("should we restructure the retrieval layer so the dense engine "
                  "and the BM25 engine share one index build path, given the eval "
                  "gate floors four metrics and we need the docs regenerated?")
        assert len(prompt.split()) > bmad.QUESTION_MAX_WORDS
        assert bmad.classify(prompt) != "trivial"

    @pytest.mark.parametrize("prompt", [
        "read the changelog at https://example.com/changelog and tell me what changed",
        "read https://docs.example.com/guide and tell me what it says about auth",
        "look at the api-schema-design doc and tell me if it is sound",
        "skim docs/bmad.md and summarize the router rules",
        "please read the PRD and summarise it",
        "can you read the review and tell me what it wants?",
        "Read the changelog.\nThen tell me what changed in the build.",
    ])
    def test_read_and_tell_is_a_question(self, prompt):
        assert bmad.classify(prompt) == "trivial"

    def test_a_long_read_and_tell_is_a_brief_not_a_question(self):
        """The read-and-tell gate had no length cap, so a spec that opened
        "read the RFC…" and said "tell me" anywhere went silent."""
        prompt = ("read the RFC at https://example.com/rfc and tell me how we "
                  "should implement the retry budget, what it means for the "
                  "exporter, whether the current backoff is compatible, and "
                  "which tests would need to change before any of it lands")
        assert len(prompt.split()) > bmad.QUESTION_MAX_WORDS
        assert bmad.classify(prompt) != "trivial"

    @pytest.mark.parametrize("prompt", [
        "can you explain how the cache works and add a test for it?",
        "read the spec and then implement it and tell me when done",
        "could you describe the scanner and also fix the flaky test?",
    ])
    def test_a_question_with_work_attached_is_work(self, prompt):
        """The gates read only the first verb, so the work went unrouted."""
        assert bmad.classify(prompt) != "trivial"

    def test_a_then_after_the_ask_turns_it_back_into_work(self):
        assert bmad.classify("read the PRD and tell me the gaps, then add "
                             "stories for them") == "product"

    def test_telling_without_reading_first_is_not_this_rule(self):
        assert bmad.classify("fix the build and tell me when it is done") == "build"


class TestBannerIsNews:
    """The session half: a pure function, so the hook stays glue."""

    LAST: ClassVar[dict] = {"track": "build", "root": "/work/proj"}

    def test_a_session_with_no_banner_needs_one(self):
        assert bmad.banner_is_news(None, "implement it", "build", "/work/proj")

    def test_a_malformed_record_is_no_record(self):
        assert bmad.banner_is_news("build", "ok do it", "build", "/work/proj")

    def test_the_same_track_in_the_same_repo_is_a_repeat(self):
        assert not bmad.banner_is_news(self.LAST, "refactor it", "build",
                                       "/work/proj")

    def test_another_track_or_repo_is_news(self):
        assert bmad.banner_is_news(self.LAST, "add tests", "quality", "/work/proj")
        assert bmad.banner_is_news(self.LAST, "refactor it", "build", "/work/other")

    @pytest.mark.parametrize("prompt", [
        "ok update both and rerun", "sure, add a test for that too",
        "yes", "Yeah do that", "yep", "okay", "no, use the other one",
        "nope", "go ahead and ship it",
    ])
    def test_a_short_reply_continues_the_session(self, prompt):
        assert not bmad.banner_is_news(self.LAST, prompt, "quality", "/work/other")

    def test_a_reply_at_the_word_limit_is_still_a_reply(self):
        prompt = "ok " + "x " * (bmad.REPLY_MAX_WORDS - 1)
        assert len(prompt.split()) == bmad.REPLY_MAX_WORDS
        assert not bmad.banner_is_news(self.LAST, prompt, "quality", "/work/proj")

    def test_a_long_reply_carries_its_own_task(self):
        prompt = "ok " + "x " * bmad.REPLY_MAX_WORDS
        assert bmad.banner_is_news(self.LAST, prompt, "quality", "/work/proj")

    def test_a_reply_word_inside_a_sentence_is_not_a_reply(self):
        assert bmad.banner_is_news(self.LAST, "token ok, now add tests",
                                   "quality", "/work/proj")


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
            assert track.lead not in track.support
            assert track.note.endswith((".", "!"))
            if track.skill is None:
                continue
            assert track.skill in lead.skills, (
                "track %r routes at %r, which %s does not drive"
                % (name, track.skill, lead.character))

    def test_track_order_covers_every_track_exactly_once(self):
        assert sorted(bmad.TRACK_ORDER) == sorted(bmad.TRACKS)
        assert len(bmad.TRACK_ORDER) == len(set(bmad.TRACK_ORDER))

    def test_build_is_the_lowest_precedence_track(self):
        """Anything more specific than "change some code" must outrank build."""
        assert bmad.TRACK_ORDER[-1] == "build"

    def test_classification_is_case_insensitive(self):
        assert bmad.classify("ADD TESTS FOR THE SCANNER") == "quality"


class TestIncidentalKeywords:
    """A prompt of up to 60 words routes on one keyword, so it must be intent.

    Replayed over a real prompt history, 89 of 143 routed prompts were decided
    by exactly one keyword — often one nobody meant: a URL, a path, a flag, a
    tracker ID, the repo's own name. Every row marked trivial below routed on
    origin/main (the track it went to is in the comment). The fix removes text
    that is not intent before scoring rather than raising the threshold, which
    measured worse on genuine short asks.
    """

    @pytest.mark.parametrize("prompt,repo,expected", [
        # the repo's own name (was: build, discovery, discovery)
        ("list the last three commits in migrations", "migrations", "trivial"),
        ("list the new notebooks in benchmarks", "benchmarks", "trivial"),
        ("list the new notebooks in Benchmarks", "benchmarks", "trivial"),
        # flags, long and short (was: product, quality)
        ("rerun the installer with --scope global and paste the output",
         "proj", "trivial"),
        ("rerun mvn package with -Dmaven.test.skip=true and paste the log",
         "proj", "trivial"),
        # URLs (was: docs, docs)
        ("open https://example.com/docs/setup and paste what it says",
         "proj", "trivial"),
        ("open www.example.com/docs and paste what it says", "proj", "trivial"),
        # code, inline and fenced (was: build, build)
        ("paste the output of `npm run build` here", "proj", "trivial"),
        ("paste what this prints:\n```\nnpm run build\n```", "proj", "trivial"),
        # a path, for build only (was: build)
        ("tail logs/build/server.log and paste the last error", "proj", "trivial"),
        # tracker IDs (was: product, build)
        ("move story ABC-123 to in progress", "proj", "trivial"),
        ("close bug #42 in the tracker", "proj", "trivial"),
        # a verb aimed at the user (was: build, build)
        ("update me when the CI run finishes", "proj", "trivial"),
        ("keep an eye on it and update us once the deploy is done",
         "proj", "trivial"),
        # residue, pinned where it lands today so a later fix shows as a diff
        ("add the meeting notes to my summary", "proj", "build"),
        ("pull the comments on story ABC-123 into a list", "proj", "docs"),
        ("add tests for catalog.scan_dir", "tests", "build"),
        # a name is dropped whole-word only
        ("add tests for catalog.scan_dir", "test", "quality"),
        # genuine asks keep routing: not verb-first, late verb, path objects
        ("we need to fix the crash in the exporter", "proj", "build"),
        ("the scanner is slow, so refactor the walk loop", "proj", "build"),
        ("once that lands, please implement the export command", "proj", "build"),
        ("fix the crash in boost_cli/core/store.py", "proj", "build"),
        ("fix bug ABC-123 in the exporter", "proj", "build"),
        ("update docs/README.md with the new flag", "proj", "docs"),
        ("add tests to tests/unit/test_catalog.py", "proj", "quality"),
        ("document the helpers in boost_cli/core/rag.py", "proj", "docs"),
    ])
    def test_only_intent_is_scored(self, prompt, repo, expected):
        assert bmad.classify(prompt, Path("/work") / repo) == expected

    def test_a_removed_span_does_not_glue_its_neighbours(self):
        """Blanked out, not deleted: `rename` must still read as a word."""
        assert bmad.classify("rename`load_tap`to`read_tap` in the scanner") == "build"

    def test_no_root_means_no_name_is_dropped(self):
        assert bmad.classify("list the last three commits in migrations") == "build"

    def test_a_root_with_no_name_drops_nothing(self):
        assert bmad.classify("fix the bug", Path("/")) == "build"

    def test_the_hook_root_reaches_the_classifier(self, tmp_path):
        """`route_lines` has the repo; the name only counts if it passes it on."""
        root = tmp_path / "migrations"
        root.mkdir()
        prompt = "list the last three commits in migrations"
        assert bmad.route_lines(prompt, root) == []
        assert bmad.route_lines(prompt, tmp_path) != []


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

    def test_a_change_always_demands_tests_and_docs_even_in_a_bare_repo(
            self, tmp_path):
        line = " ".join(bmad.done_checklist(bmad.project_signals(tmp_path),
                                            "change"))
        assert "test" in line.lower()
        assert "doc" in line.lower()

    def _full_repo(self, root):
        (root / "tests").mkdir()
        (root / "docs" / "roadmap" / "items").mkdir(parents=True)
        (root / "CLAUDE.md").write_text("rules", encoding="utf-8")
        (root / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
        return bmad.project_signals(root)

    def test_findings_are_evidence_and_no_edits_unless_asked(self, tmp_path):
        """"fix the lint errors in the scanner" routes to review, hence "unless"."""
        assert bmad.done_checklist(self._full_repo(tmp_path), "findings") == [
            "findings: each with its evidence (file:line, output or source)",
            "no edits unless asked; an edit gets tests and `make check` like "
            "any change",
            "`CLAUDE.md` is binding",
        ]

    def test_findings_in_a_bare_repo_name_no_gate(self, tmp_path):
        assert bmad.done_checklist(bmad.project_signals(tmp_path), "findings") == [
            "findings: each with its evidence (file:line, output or source)",
            "no edits unless asked; an edit gets tests like any change",
        ]

    def test_an_artifact_is_written_not_coded_and_keeps_the_roadmap(self, tmp_path):
        assert bmad.done_checklist(self._full_repo(tmp_path), "artifact") == [
            "a written artifact; no code unless the prompt asks for a change, "
            "which then gets the change contract",
            "roadmap: create or claim the item under `docs/roadmap/items/`",
            "`CLAUDE.md` is binding",
        ]

    def test_an_artifact_in_a_bare_repo_is_just_the_artifact(self, tmp_path):
        assert bmad.done_checklist(bmad.project_signals(tmp_path), "artifact") == [
            "a written artifact; no code unless the prompt asks for a change, "
            "which then gets the change contract"]

    @pytest.mark.parametrize("kind", ["findings", "artifact"])
    def test_neither_kind_refuses_work_that_was_asked_for(self, tmp_path, kind):
        """The tie-break sends real change requests onto both kinds: "fix the
        lint errors in the scanner" is review, "implement the spec in
        specs/retry.md" is product. A flat "no code" contradicts the prompt."""
        line = " ".join(bmad.done_checklist(bmad.project_signals(tmp_path), kind))
        assert "unless" in line and ("asked" in line or "asks" in line)

    def test_an_edit_request_that_tie_breaks_onto_product_is_not_told_no_code(
            self, tmp_path):
        assert bmad.classify("implement the spec in specs/retry.md",
                             tmp_path) == "product"
        done = next(ln for ln in
                    bmad.route_lines("implement the spec in specs/retry.md", tmp_path)
                    if ln.startswith("Done means:"))
        assert "no code unless the prompt asks for a change" in done

    def test_the_default_kind_is_a_change(self, tmp_path):
        signals = self._full_repo(tmp_path)
        assert bmad.done_checklist(signals) == bmad.done_checklist(signals,
                                                                   "change")

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

    def test_a_change_is_finished_but_approval_steps_still_hold(self, tmp_path):
        """Not "work autonomously": that line competed with approval gates a
        user adds on purpose, such as a brainstorming skill's HARD-GATE."""
        lines = bmad.route_lines("fix the crash in store.install", tmp_path)
        assert lines[-1] == bmad.CHANGE_CLOSE
        assert "approval step" in bmad.CHANGE_CLOSE
        assert "autonom" not in bmad.route_context(
            "fix the crash in store.install", tmp_path).lower()

    @pytest.mark.parametrize("prompt,kind", [
        ("review the changes on this branch and tell me what could break",
         "findings"),
        ("compare the two caching options and recommend one", "findings"),
        ("write the PRD for the policy engine", "artifact"),
        ("prioritize the backlog for next sprint", "artifact"),
        ("design the schema for the pulse feed", "artifact"),
    ])
    def test_findings_and_artifacts_get_no_build_contract(
            self, tmp_path, prompt, kind):
        (tmp_path / "tests").mkdir()
        (tmp_path / "README.md").write_text("x", encoding="utf-8")
        (tmp_path / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
        track = bmad.classify(prompt, tmp_path)
        assert bmad.TRACKS[track].done == kind
        lines = bmad.route_lines(prompt, tmp_path)
        done = next(line for line in lines if line.startswith("Done means:"))
        assert "tests:" not in done and "docs:" not in done
        assert bmad.CHANGE_CLOSE not in lines
        assert lines[-1] == done

    def test_every_track_declares_what_it_delivers(self):
        assert {name: t.done for name, t in bmad.TRACKS.items()} == {
            "build": "change", "quality": "change", "docs": "change",
            "ux": "change", "review": "findings", "discovery": "findings",
            "product": "artifact", "planning": "artifact",
            "architecture": "artifact",
        }
        assert set(bmad.DONE_KINDS) == {t.done for t in bmad.TRACKS.values()}

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
            "Finish the change and verify it; stop only for a choice that "
            "changes what gets delivered, or an approval step a repo guide or "
            "a loaded skill requires.",
        ]

    def test_the_whole_review_banner_is_exactly_this(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
        assert bmad.route_lines("review the changes on this branch", tmp_path) == [
            "[BMAD autopilot] track: review",
            "Lead: `bmad-tea` subagent — Murat, Master Test Architect. "
            "Find the failure, not the style nit.",
            "Support: `bmad-architect` (Winston) — spawn them with the Agent "
            "tool, in parallel where the work is independent.",
            "BMAD skill: `bmad-code-review` — invoke it if it is installed; "
            "otherwise the persona's own playbook stands.",
            "Done means: findings: each with its evidence (file:line, output or "
            "source) · no edits unless asked; an edit gets tests and "
            "`make check` like any change",
        ]

    def test_the_whole_discovery_banner_is_exactly_this(self, tmp_path):
        assert bmad.route_lines("research how other CLIs pin their toolchains",
                                tmp_path) == [
            "[BMAD autopilot] track: discovery",
            "Lead: `bmad-analyst` subagent — Mary, Business Analyst. "
            "Ground it in sources before recommending.",
            "Support: `bmad-pm` (John) — spawn them with the Agent tool, in "
            "parallel where the work is independent.",
            "BMAD skill: `bmad-deep-recon` — invoke it if it is installed; "
            "otherwise the persona's own playbook stands.",
            "Done means: findings: each with its evidence (file:line, output or "
            "source) · no edits unless asked; an edit gets tests like any change",
        ]

    def test_no_persona_file_anywhere_means_no_subagent_is_named(self, tmp_path):
        """A banner must not send the model after a subagent it cannot spawn."""
        dirs = (tmp_path / "home-agents", tmp_path / "repo-agents")
        lines = bmad.route_lines("implement the new export command", tmp_path, dirs)
        assert lines[0] == "[BMAD autopilot] track: build"
        assert not any(line.startswith(("Lead:", "Support:")) for line in lines)
        assert any(line.startswith("Done means:") for line in lines)
        assert "bmad-build" in lines[1]
        assert "Lead:" not in bmad.route_context(
            "implement the new export command", tmp_path, dirs)

    def test_an_edited_lead_in_either_dir_still_counts(self, tmp_path):
        """Edited is not absent: the session still loads that subagent."""
        home, repo = tmp_path / "home-agents", tmp_path / "repo-agents"
        repo.mkdir()
        (repo / "bmad-dev.md").write_text("my own Amelia", encoding="utf-8")
        lines = bmad.route_lines("implement the new export command", tmp_path,
                                 (home, repo))
        assert lines[1].startswith("Lead: `bmad-dev`")
        assert lines[2].startswith("Support:")
        assert bmad.route_context("implement the new export command", tmp_path,
                                  (home, repo)) == "\n".join(lines)

    def test_only_the_lead_decides_not_a_support_persona(self, tmp_path):
        agents = tmp_path / "agents"
        agents.mkdir()
        (agents / "bmad-tea.md").write_text("x", encoding="utf-8")
        lines = bmad.route_lines("implement the new export command", tmp_path,
                                 (agents,))
        assert not any(line.startswith("Lead:") for line in lines)

    def test_on_gemini_the_lead_is_a_role_not_a_subagent(self, tmp_path):
        """Gemini's subagent tool is `invoke_agent` and boost writes it no
        personas, so nothing on that host may point at a Claude subagent."""
        (tmp_path / "tests").mkdir()
        (tmp_path / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
        lines = bmad.route_lines("implement the new export command", tmp_path,
                                 host="gemini")
        assert lines[:3] == [
            "[BMAD autopilot] track: build",
            "Lead: take the role of Amelia, Senior Software Engineer. "
            "Ship it complete and verified.",
            "Support: bring in the view of Murat (Master Test Architect), "
            "Paige (Technical Writer).",
        ]
        text = "\n".join(lines)
        for claude_only in ("subagent", "Agent tool", "~/.claude"):
            assert claude_only not in text
        assert bmad.route_context("implement the new export command", tmp_path,
                                  host="gemini") == text

    def test_on_gemini_absent_persona_files_do_not_drop_the_role(self, tmp_path):
        lines = bmad.route_lines("implement the new export command", tmp_path,
                                 (tmp_path / "none",), host="gemini")
        assert lines[1].startswith("Lead: take the role of Amelia")

    def test_a_single_support_role_reads_as_one(self, tmp_path):
        lines = bmad.route_lines("review the changes on this branch", tmp_path,
                                 host="gemini")
        assert lines[2] == ("Support: bring in the view of Winston "
                            "(System Architect).")

    def test_route_context_joins_the_lines_with_newlines(self, tmp_path):
        lines = bmad.route_lines("implement the export command", tmp_path)
        assert bmad.route_context("implement the export command", tmp_path) == (
            "\n".join(lines))
        assert len(lines) > 1        # ...so the join is actually doing something


class TestOrientation:
    def test_names_only_skills_the_pinned_release_installs(self):
        """v6 deprecated the shims this text used to advertise, and a denylist
        of three of them could not notice the next one. The pinned release's
        own skill list can."""
        text = bmad.orientation()
        named = {t for t in re.findall(r"\bbmad-[a-z0-9-]+", text)
                 if t not in bmad.PERSONA_BY_SLUG}
        assert "bmad-build" in named
        assert named <= _pinned_skills()

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

    def test_the_gemini_briefing_names_no_claude_machinery(self):
        text = bmad.orientation("gemini")
        for claude_only in ("subagent", "Agent tool", "~/.claude"):
            assert claude_only not in text
        assert "names the\npersona whose role to take on" in text
        assert "  bmad-dev        Amelia, Senior Software Engineer" in text

    def test_the_claude_briefing_is_the_default(self):
        assert bmad.orientation() == bmad.orientation("claude")
        assert "~/.claude/agents and are delegated to with the Agent tool" in (
            bmad.orientation())

    def test_it_names_the_command_that_turns_it_off(self):
        assert "boost bmad off" in bmad.orientation()

    def test_the_house_rule_names_all_three_kinds_of_done(self):
        rule = bmad.orientation().split("House rule:")[1]
        assert "a change is done when its tests, its docs and its tracked item" in rule
        assert "findings are done when each carries its evidence" in rule
        assert "an artifact is done when it is\nwritten down and tracked" in rule


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
            'description: "Sally, UX Designer (BMAD bmm). Use when a [BMAD '
            'autopilot] routing banner names bmad-ux, or the user asks for it '
            'by name. Covers interface and layout work, visual hierarchy, '
            'spacing, responsive behaviour, accessibility, or a design review."',
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

    def test_persona_state_is_absent_before_anything_is_written(self, tmp_path):
        assert bmad.persona_state(tmp_path, bmad.PERSONAS[0]) == "absent"

    def test_persona_state_is_managed_right_after_write(self, tmp_path):
        bmad.write_personas(tmp_path)
        assert bmad.persona_state(tmp_path, bmad.PERSONA_BY_SLUG["bmad-dev"]) == "managed"

    def test_persona_state_is_edited_once_the_body_changes(self, tmp_path):
        """The bug this closes: an edited-but-present file used to read the
        same as no file at all everywhere counts and labels were derived from
        `installed_personas` (managed-only)."""
        bmad.write_personas(tmp_path)
        mine = tmp_path / "bmad-ux.md"
        mine.write_text(
            mine.read_text(encoding="utf-8") + "\nmy own note\n", encoding="utf-8")
        assert bmad.persona_state(
            tmp_path, bmad.PERSONA_BY_SLUG["bmad-ux"]) == "edited"

    def test_persona_states_covers_every_persona(self, tmp_path):
        bmad.write_personas(tmp_path)
        states = bmad.persona_states(tmp_path)
        assert set(states) == {p.slug for p in bmad.PERSONAS}
        assert set(states.values()) == {"managed"}

    def test_present_personas_counts_managed_and_edited_but_not_absent(
            self, tmp_path):
        bmad.write_personas(tmp_path)
        mine = tmp_path / "bmad-ux.md"
        mine.write_text(
            mine.read_text(encoding="utf-8") + "\nmy own note\n", encoding="utf-8")
        (tmp_path / "bmad-pm.md").unlink()

        present = bmad.present_personas(tmp_path)
        assert "bmad-ux" in present            # edited, still present
        assert "bmad-pm" not in present         # deleted, truly absent
        assert len(present) == len(bmad.PERSONAS) - 1

    def test_present_personas_is_empty_on_a_bare_directory(self, tmp_path):
        assert bmad.present_personas(tmp_path) == []

    def test_an_empty_but_existing_file_is_edited_not_absent(self, tmp_path):
        """A file that exists with zero bytes is still a file on disk — it
        must not be reported the same as no file at all."""
        tmp_path.mkdir(parents=True, exist_ok=True)
        (tmp_path / "bmad-dev.md").write_text("", encoding="utf-8")
        assert bmad.persona_state(
            tmp_path, bmad.PERSONA_BY_SLUG["bmad-dev"]) == "edited"

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

    CONTRACT = """A change: tests updated and actually run, documentation left true, any tracked
roadmap or backlog item moved to match, and the repo's own gate green with
output you have seen.
Findings: each one with its evidence, and no edits unless you were asked.
An artifact: the written document itself, with any tracked item moved to match —
no code unless you were asked for a change, which then gets the contract above."""

    def test_every_persona_body_states_the_contract_for_each_kind(self):
        """`bmad-tea` leads quality (a change) and review (findings), so a
        persona cannot carry one kind's contract."""
        for p in bmad.PERSONAS:
            assert self.CONTRACT in bmad.persona_markdown(p), p.slug

    def test_persona_descriptions_are_delegation_triggers(self):
        """Claude picks a subagent off `description`; it must say when to use it."""
        for p in bmad.PERSONAS:
            desc = bmad.persona_description(p)
            assert len(desc) > 40
            assert "\n" not in desc

    def test_the_banner_is_the_trigger_not_the_description(self):
        """"Use PROACTIVELY" let a persona spawn on a prompt the router kept
        silent, so the silence and `no bmad` governed only the banner."""
        for p in bmad.PERSONAS:
            desc = bmad.persona_description(p)
            assert "proactive" not in desc.lower(), p.slug
            assert "routing banner names %s," % p.slug in desc
            assert desc.endswith("Covers %s." % p.triggers)
