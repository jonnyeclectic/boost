# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The BMAD autopilot: persona subagents, prompt routing, and a done-contract.

`boost bmad on` is a one-time, global switch. After it, every prompt the agent
receives is classified here and prefixed with a short banner naming the BMAD
persona that should lead, the persona subagents to delegate to, the canonical
BMAD v6 skill for that kind of work, and a definition of done derived from the
repo in front of it. Nothing in this module needs Node, npx, or a `_bmad/`
runtime — that is the point. The heavyweight, canonical provisioning still
lives behind `boost bmad install` (`npx bmad-method install`); this is the
lightweight layer that makes the method *operate* without one.

Three facts about upstream BMAD v6 shape the code, and each cost a real bug the
first time it was assumed rather than checked:

* **`bmad-build` is the canonical implementation workflow.** `bmad-quick-dev`,
  `bmad-dev-story` and `bmad-create-story` still ship, but as deprecated
  v6-shims that redirect (or carry a "Deprecated" description). Routing build
  work at a shim sent every task through a deprecation notice.
* **BMAD does not write `.claude/agents/`.** Its installer's `claude-code`
  platform entry has exactly one target, `.claude/skills`; sub-agents are a
  *runtime* behaviour of `bmad-party-mode`, not an install artifact. So the
  persona subagents below are boost's to author — they duplicate nothing.
* **The bmm module ships five personas, not seven.** Mary, John, Sally, Winston
  and Amelia. Murat (test architect) is the separate `tea` module and Paige
  (technical writer) is a game-dev-studio agent, "on hiatus" in bmm — bmm's own
  `bmad-agent-tech-writer` was retired in v6.11.0 as "generic LLM defaults". boost
  authors all seven anyway, because a routing table with no owner for tests or
  docs cannot honour the done-contract; the two extras are labelled as such.

Frontmatter is kept to `name`/`description`/`model`/`color` on purpose.
`tools:` is omitted so a persona inherits whatever this Claude Code build
offers — naming tools would risk listing one that doesn't exist here, and an
agent resolved to zero valid tools fails at spawn. `permissionMode` is never
written: boost does not escalate permissions on the user's behalf.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import NamedTuple

from . import hookhost

MARKER = "<!-- boost:bmad-persona"
"""Prefix of the ownership stamp boost writes into every persona file.

The stamp carries a digest of the rest of the file — `<!-- boost:bmad-persona
9f2c1ab34de5 -->` — and a file counts as boost's only while that digest still
matches what is on disk. Presence alone was not enough in *either* direction: a
user who edited the body but left the stamp (the likely case — it is an HTML
comment, there is no reason to touch it) had their work silently overwritten by
the next `boost bmad on`, and deleted by `boost bmad off` while it printed that
hand-edited personas were left in place. Digesting the content makes both
statements true: edit the file however you like and boost stops claiming it.
"""

_STAMP_RE = re.compile(r"<!-- boost:bmad-persona ([0-9a-f]{12}) -->")

BMAD_VERSION = "6.12.0"
"""The bmad-method release `boost bmad install` installs, and the tables name.

It used to install `@latest` while the skill names below were hard-coded, and
the tests only checked the tables against each other — so when v6.11.0 turned
`bmad-document-project` into a shim and v6.12.0 stopped installing shims, the
docs track kept routing at a skill no default install contains, and nothing
noticed. `tests/unit/data/bmad-skills-<version>.json` is that release's skill
list; bumping this without regenerating it fails the build.
"""

RUNTIME_SKILLS: tuple[str, ...] = ("bmad-build", "bmad-build-auto")
"""Skills that halt without a per-repo `_bmad/` runtime.

They start by running `{project-root}/_bmad/scripts/render_skill.py`, so a
global install leaves them broken in every repo `boost bmad init` has not
touched — while reporting every skill installed.
"""


class Persona(NamedTuple):
    """A BMAD persona, rendered as one Claude Code subagent definition."""

    slug: str            # subagent name; also the filename stem
    character: str       # BMAD's name for them, e.g. "Amelia"
    title: str
    color: str
    module: str          # upstream BMAD module the persona belongs to
    triggers: str        # one clause: when Claude should delegate here
    mission: str
    playbook: tuple[str, ...]
    skills: tuple[str, ...]   # BMAD v6 skills this persona drives, if installed


class Track(NamedTuple):
    """One kind of incoming work, and who owns it."""

    lead: str                  # persona slug
    support: tuple[str, ...]   # persona slugs to run alongside the lead
    skill: str | None          # canonical BMAD v6 skill, if one fits
    note: str                  # how the lead should open
    done: str                  # what finished looks like: one of DONE_KINDS


DONE_KINDS: tuple[str, ...] = ("change", "findings", "artifact")
"""What a track delivers, which decides what "done" means for it.

Every track used to get the build contract — new coverage, updated docs, a
finished and verified change — so "review the changes on this branch" was told
to add tests and finish a change, and "compare the two caching options" was
told to document what changed when nothing had. A *change* ends in edited
source; *findings* (review, discovery) end in an answer with its evidence; an
*artifact* (product, planning, architecture) ends in a written document. Neither
of the last two refuses work the prompt asked for: the tie-break sends
"implement the spec in specs/retry.md" to *product* on the word "spec", and a
flat "no code" would tell the model not to do what it was just asked to do.
"""


# --------------------------------------------------------------------- personas

_DEV_PLAYBOOK = (
    "Read the surrounding code before writing any: match its idiom, naming and "
    "comment density rather than importing a house style.",
    "Make the smallest change that fully solves the task. Finish it — a "
    "half-done change reported as done is the only unrecoverable failure.",
    "Run the repo's own gate (the router's banner names it) and paste real "
    "output. If it is red, say so with the failure; never infer a pass.",
)

PERSONAS: tuple[Persona, ...] = (
    Persona(
        slug="bmad-analyst",
        character="Mary",
        title="Business Analyst",
        color="cyan",
        module="bmm",
        triggers="open-ended research, discovery, comparing options, or turning "
                 "a vague idea into a written brief",
        mission="Turn an unclear ask into a grounded brief someone can build "
                "from, with the evidence attached.",
        playbook=(
            "Separate what is known from what is assumed, and label the "
            "assumptions — an unlabelled guess is the expensive kind.",
            "Prefer primary sources (the code, the repo, the vendor's own docs) "
            "over summaries, and cite where each claim came from.",
            "Close with a recommendation, not a survey. Name the trade-off you "
            "are accepting.",
        ),
        skills=("bmad-brainstorming", "bmad-deep-recon", "bmad-product-brief"),
    ),
    Persona(
        slug="bmad-pm",
        character="John",
        title="Product Manager",
        color="purple",
        module="bmm",
        triggers="requirements, scope, PRDs, epics and stories, acceptance "
                 "criteria, or roadmap/backlog bookkeeping",
        mission="Decide what is in scope, write it down so it can be built and "
                "checked, and keep the roadmap honest.",
        playbook=(
            "Write acceptance criteria that a test could assert. If you cannot "
            "imagine the assertion, the criterion is not finished.",
            "Keep the roadmap in sync in the same change: if the repo tracks "
            "items as files, add or update the item rather than the rendered "
            "output, and never hand-type a generated counter.",
            "Cut scope explicitly and say what was cut. Silent narrowing is the "
            "failure mode here.",
        ),
        skills=("bmad-prd", "bmad-create-epics-and-stories",
                "bmad-sprint-planning"),
    ),
    Persona(
        slug="bmad-architect",
        character="Winston",
        title="System Architect",
        color="blue",
        module="bmm",
        triggers="system design, module boundaries, data models and schemas, "
                 "API shape, migration strategy, or a scalability trade-off",
        mission="Choose a structure the team can live with, and write down why "
                "the rejected options were rejected.",
        playbook=(
            "Design against the constraints that already exist in this repo — "
            "its layering, its gates, its dependency budget — not a greenfield.",
            "Give one recommendation plus the runner-up and the deciding "
            "trade-off. A menu is not a decision.",
            "Say which part of the design is reversible and which is not; spend "
            "the review effort on the irreversible part.",
        ),
        skills=("bmad-architecture", "bmad-spec"),
    ),
    Persona(
        slug="bmad-ux",
        character="Sally",
        title="UX Designer",
        color="pink",
        module="bmm",
        triggers="interface and layout work, visual hierarchy, spacing, "
                 "responsive behaviour, accessibility, or a design review",
        mission="Make the thing legible and usable before making it pretty.",
        playbook=(
            "Fix hierarchy, spacing and contrast before colour or motion — most "
            "'looks off' reports are a spacing scale problem.",
            "Check the states that are easy to forget: empty, loading, error, "
            "long content, narrow viewport, keyboard focus.",
            "Verify contrast numerically rather than by eye, and treat an "
            "automated checker's 'incomplete' as unproven, not as a pass.",
        ),
        skills=("bmad-ux",),
    ),
    Persona(
        slug="bmad-dev",
        character="Amelia",
        title="Senior Software Engineer",
        color="green",
        module="bmm",
        triggers="implementing a feature, fixing a bug, refactoring, or any "
                 "change that ends in edited source files",
        mission="Land a complete, verified change that reads like the code "
                "around it.",
        playbook=_DEV_PLAYBOOK,
        skills=("bmad-build", "bmad-code-review"),
    ),
    Persona(
        slug="bmad-tea",
        character="Murat",
        title="Master Test Architect",
        color="orange",
        module="tea",
        triggers="tests, coverage, flaky suites, regression risk, e2e "
                 "generation, or reviewing a change for what could break it",
        mission="Decide what evidence would make this change believable, then "
                "produce it.",
        playbook=(
            "Test behaviour at the boundary that owns it. A test that only "
            "imports a module raises coverage and catches nothing — write "
            "assertions a mutation would fail.",
            "Cover the failure paths deliberately: empty input, corrupt state, "
            "a missing dependency, the second invocation (idempotence).",
            "Run the suite and report the real result, including the numbers. "
            "A red gate reported as green is worse than no gate.",
        ),
        skills=("bmad-qa-generate-e2e-tests", "bmad-code-review"),
    ),
    Persona(
        slug="bmad-scribe",
        character="Paige",
        title="Technical Writer",
        color="yellow",
        module="gds",
        triggers="documentation, READMEs, changelogs, guides, docstrings, or "
                 "explaining a system to the next person who touches it",
        mission="Leave the docs true. Every shipped behaviour change has a "
                "documentation consequence, even when it is 'none'.",
        playbook=(
            "Document what the code does now, verified by reading it — not what "
            "the commit message hoped it would do.",
            "Update generated docs by regenerating them from their source, "
            "never by editing the output; a hand-edit fails the freshness gate.",
            "Write for the reader who arrives at 2am with a broken build: what "
            "it does, how to run it, what breaks it.",
            "`bmad-project-context` is for the agent-instruction block in "
            "`AGENTS.md` only; READMEs and guides need no BMAD skill.",
        ),
        skills=("bmad-project-context",),
    ),
)

PERSONA_BY_SLUG: dict[str, Persona] = {p.slug: p for p in PERSONAS}


# ----------------------------------------------------------------------- tracks

TRACKS: dict[str, Track] = {
    "discovery": Track(
        lead="bmad-analyst", support=("bmad-pm",), skill="bmad-deep-recon",
        note="Ground it in sources before recommending.", done="findings"),
    "product": Track(
        lead="bmad-pm", support=("bmad-analyst", "bmad-architect"),
        skill="bmad-prd",
        note="Write criteria a test could assert.", done="artifact"),
    "planning": Track(
        lead="bmad-pm", support=("bmad-architect",), skill="bmad-sprint-planning",
        note="Keep the tracked items and the work in sync.", done="artifact"),
    "architecture": Track(
        lead="bmad-architect", support=("bmad-dev",), skill="bmad-architecture",
        note="One recommendation, with the rejected option named.", done="artifact"),
    "ux": Track(
        lead="bmad-ux", support=("bmad-dev",), skill="bmad-ux",
        note="Hierarchy and spacing before colour.", done="change"),
    "build": Track(
        lead="bmad-dev", support=("bmad-tea", "bmad-scribe"), skill="bmad-build",
        note="Ship it complete and verified.", done="change"),
    "quality": Track(
        lead="bmad-tea", support=("bmad-dev",),
        skill="bmad-qa-generate-e2e-tests",
        note="Assertions that a mutation would fail.", done="change"),
    "docs": Track(
        # No skill: `bmad-document-project` is a shim since v6.11.0 and not
        # installed since v6.12.0, and its replacement `bmad-project-context`
        # manages one block in AGENTS.md — routing every README edit there
        # would trade a dead pointer for a misroute.
        lead="bmad-scribe", support=("bmad-dev",), skill=None,
        note="Verify against the code, regenerate what is generated.", done="change"),
    "review": Track(
        lead="bmad-tea", support=("bmad-architect",), skill="bmad-code-review",
        note="Find the failure, not the style nit.", done="findings"),
}

TRACK_ORDER: tuple[str, ...] = (
    "quality", "ux", "docs", "review", "architecture",
    "product", "planning", "discovery", "build",
)
"""Tie-break precedence, most specific first.

Real prompts hit several tables at once. "add tests for scan_dir" is a build
verb *and* a testing noun; "add a roadmap item" is a build verb *and* planning.
`build` is the catch-all and therefore must lose every tie — otherwise every
task in the repo routes to Amelia and the roster is decoration.
"""

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "quality": (
        r"\btests?\b", r"\btesting\b", r"\bcoverage\b", r"\bflaky\b",
        r"\bpytest\b", r"\be2e\b", r"\bend-to-end\b", r"\bregressions?\b",
        r"\bmutation\b", r"\bqa\b", r"\bassert\w*\b", r"\bfixtures?\b",
    ),
    "ux": (
        r"\bux\b", r"\bui\b", r"\blayout\b", r"\bcss\b", r"\bstyling\b",
        r"\baccessib\w*\b", r"\ba11y\b", r"\bresponsive\b", r"\bwireframe\b",
        r"\bspacing\b", r"\bdesign review\b", r"\btypograph\w*\b",
    ),
    "docs": (
        r"\bdocs?\b", r"\bdocument\w*\b", r"\breadme\b", r"\bchangelog\b",
        r"\bdocstrings?\b", r"\bguide\b", r"\btutorial\b", r"\bcomments?\b",
    ),
    "review": (
        r"\breview\w*\b", r"\baudit\w*\b", r"\bcritique\b", r"\bcode smell\b",
        r"\btech debt\b", r"\blint\b",
    ),
    "architecture": (
        r"\barchitect\w*\b", r"\bdesign the\b", r"\bsystem design\b",
        r"\bschemas?\b", r"\bdata model\b", r"\bapi design\b",
        r"\btrade-?offs?\b", r"\bscalab\w*\b", r"\bcoupling\b",
        r"\bmodule boundar\w*\b",
    ),
    "product": (
        r"\bprd\b", r"\brequirements?\b", r"\bspecs?\b", r"\bepics?\b",
        r"\bstor(y|ies)\b", r"\bacceptance criteria\b", r"\bscope\b",
        r"\bproduct brief\b",
    ),
    "planning": (
        r"\broadmap\b", r"\bsprints?\b", r"\bbacklog\b", r"\bmilestones?\b",
        r"\bprioriti[sz]\w*\b", r"\bbreak (it )?down\b", r"\bestimate\b",
        r"\bplan the work\b",
    ),
    "discovery": (
        r"\bresearch\w*\b", r"\binvestigat\w*\b", r"\bexplore\b", r"\bcompare\b",
        r"\bevaluate\b", r"\boptions\b", r"\bbenchmark\w*\b", r"\bfeasib\w*\b",
        r"\bsurvey\b", r"\bprior art\b",
    ),
    "build": (
        # `fix\w*` and `change\w*` used to live here and were a bug: they match
        # "fixture(s)" and "changelog" — the exact words the quality and docs
        # tables above claim. "add fixtures for the sandbox HOME" scored build=2
        # against quality=1 and went to Amelia, and because build won on *score*
        # it never reached TRACK_ORDER, so the "build loses every tie" invariant
        # was bypassed rather than violated. Enumerate the inflections instead.
        r"\bimplement\w*\b", r"\bbuild\b", r"\badd(s|ed|ing)?\b", r"\bcreate\b",
        r"\bfix(es|ed|ing)?\b", r"\bbugs?\b", r"\brefactor\w*\b",
        r"\bmigrat\w*\b", r"\bupdates?\b", r"\bremove\b", r"\bdeletes?\b",
        r"\brename\b", r"\bchang(e|es|ed|ing)\b", r"\bwire\b", r"\bship\b",
        r"\bsupport for\b", r"\bmake it\b",
    ),
}

_COMPILED = {t: tuple(re.compile(p, re.IGNORECASE) for p in pats)
             for t, pats in _KEYWORDS.items()}

_SLASH = re.compile(r"^\s*/")
_OPT_OUT = re.compile(r"\b(no|skip|without|disable)\s+bmad\b", re.IGNORECASE)
_INFO_QUESTION = re.compile(
    r"^\s*(what|why|how|when|where|which|who|whose|whom)\b", re.IGNORECASE)
_YES_NO_QUESTION = re.compile(
    r"^\s*(is|are|do|does|did|has|have|should|can|could|would|will)\b",
    re.IGNORECASE)
"""An auxiliary opener: with a closing `?`, a yes/no question.

`_INFO_QUESTION` knew only wh-words, so "what tests cover the parser?" was
silent and "are there any tests for the parser?" got a quality banner. Replayed
over real prompts, all 11 synthetic yes/no questions routed.
"""
_MODAL_REQUEST = re.compile(
    r"^\s*(can|could|would|will)\s+(you|we)\b"
    r"(?!\s+(please\s+)?(explain|tell|describe|summari[sz]e)\b)",
    re.IGNORECASE)
""""can you fix the crash?" is a request wearing a question mark.

Unless its verb only asks to be told something: "could you explain the cache?"
is still a question.
"""
_READ_AND_TELL = re.compile(
    r"^\s*((please|can you|could you)\s+)?(read|skim|look at)\b"
    r".*?\b(tell me|summari[sz]e)\b",
    re.IGNORECASE | re.DOTALL)
""""read X and tell me Y" asks for an answer, whatever words X is made of.

The track used to be picked by words inside the thing to be read — `/changelog`
in a URL, `api-schema-design` in a doc name. A `then` after the ask is the one
way it turns back into work (:data:`_THEN`).
"""
_THEN = re.compile(r"\bthen\b", re.IGNORECASE)
_COMPOUND_ASK = re.compile(
    r"\b(and|then|also)\s+(please\s+|also\s+)?"
    r"(add|fix|update|create|implement|refactor|rename|remove|delete|build|"
    r"ship|write|wire|migrate|run)\b", re.IGNORECASE)
"""A second clause that asks for work, after a clause that asks for an answer.

"read the spec and then implement it" and "can you explain the cache and add a
test?" are requests with a question attached, not questions. Without this the
question gates read only the first verb and silenced the work.
"""

PASTE_MIN_LINES = 3
"""Below this, a prompt is not shaped like pasted output."""

_FENCE = re.compile(r"```.*?```", re.DOTALL)
"""A fenced block: pasted *inside* a request, so it is not what the ask is."""

_MACHINE_LINE = re.compile(
    # Indented and code-shaped. Indentation alone is not enough: a bullet list
    # and a hanging-indent sentence are indented too, and reading them as
    # output silenced ordinary multi-line requests ("Do these:\n  - add a test
    # …") that route fine as one line.
    r"^\s+(?![-*•]\s|\d+[.)]\s)\S.*[=(){}\[\];|<>]"
    r"|^\s*(modified|new file|deleted|renamed|both modified):"  # git status
    r"|^\$\s"                                   # a shell prompt
    r"|^Traceback \(most recent call last\)"
    r"|^[A-Za-z_][\w.]*(Error|Exception|Warning)\b"   # its last line
    r"|^\s*npm\b"                                # npm's own log lines
    r"|^[>E]\s"                                  # pytest's source and error marks
    r"|^(FAILED|ERROR|PASSED|SKIPPED)\b"
    r"|^=+ .* =+$"                               # pytest's section rules
    r"|^(On branch|Your branch is|Changes not staged|Changes to be committed"
    r"|Untracked files|nothing to commit|no changes added)\b"  # git status
    r"|\S:\d+\b"                                # path:line
    r"|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}:\d{2}:\d{2}\b",  # timestamps
    re.MULTILINE)
"""A line a program wrote rather than a person."""

_SECOND_SENTENCE = re.compile(r"[.?!]\s+\S")
"""A sentence terminator with more prose after it.

The interrogative gate anchors on the first token only, which made "Why is
test_catalog flaky on Windows? Fix it and add a regression test." trivial — a
real task, silently unrouted. A question that is followed by another sentence is
not a question, it is a preamble to an instruction. Requiring whitespace after
the terminator keeps "SKILL.md" and "store.install" from reading as boundaries.
"""

TRIVIAL = "trivial"
"""The "say nothing" verdict.

A named constant rather than four repeated literals because :func:`classify`
returns it from four different guards and :func:`route_lines` tests for it — a
typo in any one of them would route a "trivial" prompt into ``TRACKS`` and
raise ``KeyError`` inside a hook.
"""

MIN_WORDS = 3
"""Below this, a prompt is an acknowledgement ("thanks", "ok cool"), not a task."""

QUESTION_MAX_WORDS = 30
"""An interrogative opener stops meaning "quick question" somewhere around here.

Short "how does X work?" prompts want an answer, and a delegation banner on one
is pure noise. A 45-word paragraph that happens to begin "how should we…" is a
design brief, so length is what separates them.
"""

LONG_PROMPT_WORDS = 60
"""Past this, one keyword is not enough evidence to route on.

The other trivial gates all key on *shape* — a question, a slash command, too
few words — and a pasted terminal session is none of those. The day the
autopilot shipped, a user pasted ~90 words of their own shell output back into
the chat and got a full delegation banner because `\\bupdate\\b` matched inside
"boost self-update": one weak hit in a wall of text.

Density is the missing signal. In a short prompt every word is deliberate, so a
single keyword is strong evidence; in a long one it is easily incidental, while
a genuine long request names its work more than once ("refactor … and update
…"). Requiring two distinct hits above this length costs real requests nothing
and silences pastes, which is the right way round: this module would rather
under-route than talk over someone.
"""


_NOT_INTENT = re.compile(
    r"```.*?```"                           # fenced code
    r"|`[^`\n]*`"                          # inline code
    r"|\b(?:https?|ftp)://\S+|\bwww\.\S+"  # URLs
    r"|(?<!\S)--?[a-z]\S*"                 # --flag, -f, --flag=value
    r"|\b(?:story|ticket|issue|epic|task|bug|card|pr)\s+"
    r"(?:[a-z][a-z0-9]*-\d+|#\d+)\b",      # story ABC-123, issue #42
    re.IGNORECASE | re.DOTALL)
"""Text that names something rather than asking for anything.

A prompt of up to :data:`LONG_PROMPT_WORDS` routes on one keyword, so one match
anywhere decided the track — including words nobody meant as intent. "rerun the
installer with --scope global" went to product on `\\bscope\\b`, a link to
`https://example.com/docs/...` went to docs, "move story ABC-123 to in progress"
went to product. These spans are removed before any table is scored.
"""

_PATH_TOKEN = re.compile(r"\S*/\S*")
"""A token with a `/` in it: a path, which `build` does not score.

"tail logs/build/server.log" is not a build. The rule is build-only because a
path is often the object of the ask — "update docs/README.md" must stay docs —
and build is the catch-all whose single hits are the cheapest.
"""

_ADDRESSEE = re.compile(r"\b\w+\s+(?:me|us)\b", re.IGNORECASE)
"""A verb aimed at the user, not the code: "update me when the CI run finishes".

Build-only for the same reason as :data:`_PATH_TOKEN` — every build keyword is
a verb that also reads as a request to *tell* someone something.
"""


def _intent_text(text: str, root: Path | str | None) -> str:
    """`text` with everything that is not intent blanked out, for scoring.

    The repo's own directory name goes too, whole-word: in a checkout called
    `migrations`, "list the last three commits in migrations" is a `git log`,
    not a migration. The hook already knows the root; this is where it counts.
    """
    text = _NOT_INTENT.sub(" ", text)
    if root is not None and Path(root).name:
        text = re.sub(r"(?<!\w)%s(?!\w)" % re.escape(Path(root).name), " ",
                      text, flags=re.IGNORECASE)
    return text


def classify(prompt: str, root: Path | str | None = None) -> str:
    """Name the track a prompt belongs to, or ``"trivial"`` to stay silent.

    Silence is the default for anything that is not recognisably a unit of
    work: empty input, an acknowledgement, a slash command (which carries its
    own instructions), a short informational question, an explicit opt-out
    ("no bmad"), a prompt that matches no track at all, or — past
    :data:`LONG_PROMPT_WORDS` — one that matches only a single keyword.

    Only intent is scored (:func:`_intent_text`): code spans, URLs, flags,
    tracker IDs and the name of ``root`` — the repo the prompt was typed in —
    never count, and ``build`` additionally ignores paths and verbs addressed
    to the user. The threshold stays where it is; the evidence got cleaner.
    """
    text = prompt.strip()
    if not text or _SLASH.match(text) or _OPT_OUT.search(text):
        return TRIVIAL
    words = text.split()
    if len(words) < MIN_WORDS:
        return TRIVIAL
    if _is_question(text, words):
        return TRIVIAL
    # A fenced block is pasted material inside a request, so it must not
    # outvote the request: strip it before deciding whether this is a paste.
    prose = _paste_prose(_FENCE.sub(" ", text))
    # A paste gets the long-prompt argument whatever its length: one keyword in
    # a wall of machine output is incidental, and only the person's own lines
    # are theirs to score.
    long_or_paste = prose is not None or len(words) > LONG_PROMPT_WORDS
    intent = _intent_text(text if prose is None else prose, root)
    build_intent = _ADDRESSEE.sub(" ", _PATH_TOKEN.sub(" ", intent))
    # Distinct patterns matched, not occurrences: saying "update" twenty times
    # is one piece of evidence, which is what keeps a repetitive log quiet.
    scores = {t: sum(1 for rx in pats
                     if rx.search(build_intent if t == "build" else intent))
              for t, pats in _COMPILED.items()}
    best = max(scores.values())
    if best == 0 or (best < 2 and long_or_paste):
        return TRIVIAL
    return next(t for t in TRACK_ORDER if scores[t] == best)


def _is_question(text: str, words: list[str]) -> bool:
    """A prompt that asks to be told something rather than for work.

    Three shapes: a wh-question, a yes/no question (an auxiliary opener and a
    closing ``?``, unless it is a modal request), and "read X and tell me".
    All three stop being questions past :data:`QUESTION_MAX_WORDS`, once
    another sentence follows, or once a second clause asks for work; the third
    also stops at a ``then`` after the ask.
    """
    if _COMPOUND_ASK.search(text):
        # "can you explain the cache and add a test for it?" asks for both; the
        # tell-me verb only decides the question when nothing else is asked.
        return False
    if len(words) > QUESTION_MAX_WORDS:
        # Past this a question is a brief, whatever shape it opens in. The
        # read-and-tell gate had no cap at all, so a 200-word spec that opened
        # "read the RFC …" and said "tell me" anywhere went silent.
        return False
    if not _SECOND_SENTENCE.search(text):
        if _INFO_QUESTION.match(text):
            return True
        if (text.endswith("?") and _YES_NO_QUESTION.match(text)
                and not _MODAL_REQUEST.match(text)):
            return True
    ask = _READ_AND_TELL.match(text)
    return ask is not None and not _THEN.search(text, ask.end())


def _paste_prose(text: str) -> str | None:
    """The lines a person typed, when the prompt is mostly pasted output.

    ``None`` when it is not paste-shaped: fewer than :data:`PASTE_MIN_LINES`
    non-blank lines, or more of them prose than machine output. A `git status`
    paste routed to build on git's own words ("Changes not staged", "to
    update"), and an npm log on the `fix` of `npm audit fix`.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < PASTE_MIN_LINES:
        return None
    prose = [ln for ln in lines if not _MACHINE_LINE.search(ln)]
    if 2 * len(prose) > len(lines):
        return None
    return "\n".join(prose)


# --------------------------------------------------------------------- sessions

REPLY_MAX_WORDS = 12
"""Past this, an "ok, …" is carrying a task of its own, not agreeing to one."""

_REPLY = re.compile(r"^\s*(yes|yep|yeah|ok|okay|sure|no|nope|go ahead)\b",
                    re.IGNORECASE)


def banner_is_news(last: dict | None, prompt: str, track: str, root: str) -> bool:
    """Whether a routed prompt's banner tells the session anything new.

    ``last`` is the record of the banner this session was last given
    (``{"track", "root"}``), or ``None`` if it has had none. A banner is a
    function of track and root alone, and Claude Code keeps hook context in the
    conversation where it fired, so the same track in the same repo repeats
    what the model already holds. A short reply — "ok update both and rerun",
    "sure, add a test for that too" — continues the task that banner set up;
    re-routing it handed the lead to another persona mid-task.
    """
    if not isinstance(last, dict):
        return True
    if _REPLY.match(prompt) and len(prompt.split()) <= REPLY_MAX_WORDS:
        return False
    return (last.get("track"), last.get("root")) != (track, root)


# -------------------------------------------------------------- project signals

_TEST_DIRS = ("tests", "test", "spec", "__tests__")
_DOC_PATHS = ("README.md", "docs", "CHANGELOG.md")
_ROADMAP_PATHS = ("docs/roadmap/items", "docs/roadmap", "ROADMAP.md",
                  "docs/ROADMAP.md")
_GUIDES = ("CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md")
_LANG_GATES = (("pyproject.toml", "pytest"), ("setup.cfg", "pytest"),
               ("Cargo.toml", "cargo test"), ("go.mod", "go test ./..."))


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return ""


def _label(root: Path, rel: str) -> str:
    """`docs` -> `docs/` when it is a directory, so the banner reads unambiguously."""
    return rel + "/" if (root / rel).is_dir() else rel


def _gate_command(root: Path) -> str | None:
    """The one command that proves the change is done, as this repo defines it."""
    makefile = _read(root / "Makefile")
    if re.search(r"^check:", makefile, re.MULTILINE):
        return "make check"
    if re.search(r"^test:", makefile, re.MULTILINE):
        return "make test"
    pkg = _read(root / "package.json")
    if pkg:
        try:
            data = json.loads(pkg)
        except ValueError:
            data = {}
        scripts = data.get("scripts") if isinstance(data, dict) else None
        if isinstance(scripts, dict) and scripts.get("test"):
            return "npm test"
    for marker, cmd in _LANG_GATES:
        if (root / marker).exists():
            return cmd
    return None


def project_signals(root: Path) -> dict:
    """What this repo expects of a finished change, read off the filesystem.

    Returns ``{tests, docs, roadmap, gate, guide}``. Every value is either a
    repo-relative path/command string or ``None``/``[]`` — so the checklist can
    name real paths instead of reciting a generic "remember to add tests".
    """
    root = Path(root)
    return {
        "tests": next((d + "/" for d in _TEST_DIRS if (root / d).is_dir()), None),
        "docs": [_label(root, d) for d in _DOC_PATHS if (root / d).exists()],
        "roadmap": next((_label(root, r) for r in _ROADMAP_PATHS
                         if (root / r).exists()), None),
        "gate": _gate_command(root),
        "guide": next((g for g in _GUIDES if (root / g).is_file()), None),
    }


def done_checklist(signals: dict, done: str = "change") -> list[str]:
    """The definition of done for one kind of work, in the repo's own vocabulary.

    For a *change*, tests and docs are unconditional — "no doc change needed"
    is a conclusion to reach, not a step to skip. Roadmap and gate clauses
    appear only when the repo actually has one, because an instruction to
    update a file that does not exist teaches the agent to ignore the whole
    banner. *Findings* and *artifacts* are not changes, so they get no tests or
    docs clause: they are done when the answer or the document is. Both carry
    an "unless asked" escape, because the tie-break routes real change requests
    onto them — "fix the lint errors in the scanner" goes to review, and
    "implement the spec in specs/retry.md" to product.
    """
    guide = signals.get("guide")
    binding = ["`%s` is binding" % guide] if guide else []
    if done == "findings":
        gate = signals.get("gate")
        return ["findings: each with its evidence (file:line, output or source)",
                "no edits unless asked; an edit gets tests%s like any change"
                % (" and `%s`" % gate if gate else ""), *binding]
    if done == "artifact":
        roadmap = signals.get("roadmap")
        tracked = (["roadmap: create or claim the item under `%s`" % roadmap]
                   if roadmap else [])
        return ["a written artifact; no code unless the prompt asks for a "
                "change, which then gets the change contract", *tracked, *binding]

    items: list[str] = []

    tests = signals.get("tests")
    if tests:
        items.append("tests: add or update coverage under `%s`, and run them" % tests)
    else:
        items.append("tests: cover the change, and run whatever suite exists")

    docs = signals.get("docs") or []
    if docs:
        items.append("docs: update %s wherever the change shows"
                     % " / ".join("`%s`" % d for d in docs))
    else:
        items.append("docs: write down what changed for the next reader")

    roadmap = signals.get("roadmap")
    if roadmap:
        items.append("roadmap: create or claim the item under `%s`" % roadmap)

    gate = signals.get("gate")
    if gate:
        items.append("gate: `%s` green, with real output" % gate)

    return items + binding


# --------------------------------------------------------------------- routing

def route_lines(prompt: str, root: Path | None = None,
                agents_dirs: tuple[Path, ...] | None = None,
                host: str = hookhost.CLAUDE) -> list[str]:
    """The banner for one prompt: `[]` when the prompt is not a unit of work.

    Kept to a handful of lines on purpose — this is prepended to *every*
    substantive prompt, so its cost is paid on each turn of every session.

    ``agents_dirs`` are the directories a session loads subagents from. When
    given, and the lead's file is in none of them, the Lead and Support lines
    are dropped: naming a subagent the session cannot spawn sends the model
    after something that does not exist. An edited file counts as present —
    it is still a subagent, just no longer boost's.

    On a host other than Claude Code the personas are roles to adopt, not
    subagents: Gemini's subagent tool is `invoke_agent` and boost writes no
    personas for it, so its banner names no subagent, no Agent tool and no
    ``~/.claude`` path.
    """
    root = Path(root) if root is not None else Path.cwd()
    track_name = classify(prompt, root)
    if track_name == TRIVIAL:
        return []
    track = TRACKS[track_name]
    lead = PERSONA_BY_SLUG[track.lead]
    signals = project_signals(root)
    delegate = agents_dirs is None or any(
        persona_state(d, lead) != "absent" for d in agents_dirs)

    lines = ["[BMAD autopilot] track: %s" % track_name]
    if host != hookhost.CLAUDE:
        lines.append("Lead: take the role of %s, %s. %s"
                     % (lead.character, lead.title, track.note))
        if track.support:
            lines.append("Support: bring in the view of %s." % ", ".join(
                "%s (%s)" % (PERSONA_BY_SLUG[s].character, PERSONA_BY_SLUG[s].title)
                for s in track.support))
    elif delegate:
        lines.append("Lead: `%s` subagent — %s, %s. %s"
                     % (lead.slug, lead.character, lead.title, track.note))
        if track.support:
            lines.append(
                "Support: %s — spawn them with the Agent tool, in parallel where "
                "the work is independent."
                % ", ".join("`%s` (%s)" % (s, PERSONA_BY_SLUG[s].character)
                            for s in track.support))
    if track.skill:
        lines.append("BMAD skill: `%s` — invoke it if it is installed; otherwise "
                     "the persona's own playbook stands." % track.skill)
    lines.append("Done means: " + " · ".join(done_checklist(signals, track.done)))
    if track.done == "change":
        # Not "work autonomously": that competed with approval gates people add
        # on purpose, and the guide clause above only exists when a guide does.
        lines.append(CHANGE_CLOSE)
    return lines


CHANGE_CLOSE = ("Finish the change and verify it; stop only for a choice that "
                "changes what gets delivered, or an approval step a repo guide "
                "or a loaded skill requires.")
"""The closing banner line for a change, and only a change."""


def route_context(prompt: str, root: Path | None = None,
                  agents_dirs: tuple[Path, ...] | None = None,
                  host: str = hookhost.CLAUDE) -> str:
    """:func:`route_lines` as one string (``""`` when there is nothing to say)."""
    return "\n".join(route_lines(prompt, root, agents_dirs, host))


# ----------------------------------------------------------------- orientation

_SUBAGENT_INTRO = ("This session routes work through BMAD personas. Persona "
                   "subagents live in\n~/.claude/agents and are delegated to "
                   "with the Agent tool:")
_ROLE_INTRO = ("This session routes work through BMAD personas. A routing banner "
               "names the\npersona whose role to take on for that prompt:")


def orientation(host: str = hookhost.CLAUDE) -> str:
    """The SessionStart briefing: the roster, the phases, and the house rule.

    Only Claude Code gets persona subagents; elsewhere the roster is a list of
    roles, for the same reason as :func:`route_lines`.
    """
    roster = "\n".join(
        "  %-15s %s, %s" % (p.slug, p.character, p.title) for p in PERSONAS)
    return """[BMAD autopilot active]
%s

%s

Every substantive prompt arrives with a one-line routing banner naming the lead
persona, the support personas, the BMAD skill for that track when one fits, and
the definition of done for this repo. Follow it. Trivial asks get no banner — answer those
directly and skip the ceremony.

BMAD v6 workflow skills, if installed (`boost bmad install`): plan with
bmad-brainstorming / bmad-product-brief / bmad-prd / bmad-architecture /
bmad-create-epics-and-stories / bmad-sprint-planning; ship with bmad-build
(the canonical implementation workflow) / bmad-code-review /
bmad-qa-generate-e2e-tests / bmad-retrospective; bmad-help lists the rest.
Full workflow skills need a per-project `_bmad/` runtime — `boost bmad init`.

House rule: a change is done when its tests, its docs and its tracked item are;
findings are done when each carries its evidence; an artifact is done when it is
written down and tracked. Turn this off with `boost bmad off`.""" % (
        _SUBAGENT_INTRO if host == hookhost.CLAUDE else _ROLE_INTRO, roster)


# ------------------------------------------------------------ persona files

def persona_description(persona: Persona) -> str:
    """The one-line `description:` Claude reads when choosing a subagent.

    Claude Code treats this line as a delegation rule, and its docs recommend
    "use proactively" to make delegation *more* eager. That wording made the
    router's silence cosmetic: a prompt the router judged trivial, or marked
    `no bmad`, got no banner but could still spawn a persona on the strength of
    its description alone. Tying the trigger to the banner makes the router the
    one place that decides, while naming the persona by slug keeps delegation
    working when a banner does name it, or the user does.
    """
    return ("%s, %s (BMAD %s). Use when a [BMAD autopilot] routing banner names "
            "%s, or the user asks for it by name. Covers %s."
            % (persona.character, persona.title, persona.module, persona.slug,
               persona.triggers))


def persona_markdown(persona: Persona) -> str:
    """One persona as a Claude Code subagent definition file, stamped.

    The stamp is inserted after the frontmatter and carries a digest of
    everything else in the file, so :func:`is_managed` can tell boost's own
    output from a copy the user has since edited.
    """
    text = _persona_text(persona)
    head, _sep, tail = text.partition("---\n\n")
    # The stamp line is *inserted*, not substituted: removing it again has to
    # yield `text` byte for byte, blank line included, or the digest can never
    # be recomputed from the file on disk.
    return "%s---\n%s\n\n%s" % (head, _stamp(_digest(text)), tail)


def _stamp(digest: str) -> str:
    return "%s %s -->" % (MARKER, digest)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _unstamp(text: str) -> tuple[str | None, str]:
    """Split a stamped file into ``(digest, the-text-that-was-digested)``.

    Returns ``(None, text)`` when there is no stamp. Removing the stamp line
    exactly — comment plus its trailing newline — is what makes the digest
    reproducible from the file alone.
    """
    m = _STAMP_RE.search(text)
    if not m:
        return None, text
    end = m.end() + 1 if text[m.end():m.end() + 1] == "\n" else m.end()
    return m.group(1), text[:m.start()] + text[end:]


def is_managed(text: str) -> bool:
    """True only for a persona file boost wrote and nobody has edited since."""
    digest, original = _unstamp(text)
    return digest is not None and digest == _digest(original)


def _persona_text(persona: Persona) -> str:
    """The persona file *without* its stamp — the bytes the digest covers."""
    playbook = "\n".join("- %s" % b for b in persona.playbook)
    skills = ", ".join("`%s`" % s for s in persona.skills)
    return """---
name: %s
description: %s
model: inherit
color: %s
---

You are %s, %s — the BMAD Method persona for this kind of work.

Mission: %s

How you work:
%s

BMAD skills to prefer when they are installed: %s.
They are not required — when they are absent, the playbook above is the method.

Before you report back, meet the contract for the kind of work you were given,
the same one the session that spawned you works to.

A change: tests updated and actually run, documentation left true, any tracked
roadmap or backlog item moved to match, and the repo's own gate green with
output you have seen.
Findings: each one with its evidence, and no edits unless you were asked.
An artifact: the written document itself, with any tracked item moved to match —
no code unless you were asked for a change, which then gets the contract above.

If you could not finish a part of it, say which part and why — do not narrow
the task silently.
""" % (persona.slug, json.dumps(persona_description(persona)), persona.color,
       persona.character, persona.title, persona.mission, playbook, skills)


def write_personas(agents_dir: Path) -> tuple[list[str], list[str]]:
    """Write the personas into `agents_dir`; return ``(written, skipped)``.

    Idempotent, and never destructive: a file that exists but is not boost's own
    unedited output is left exactly as it is and reported as skipped, so
    re-running `boost bmad on` cannot silently discard someone's customisation.
    """
    agents_dir = Path(agents_dir)
    agents_dir.mkdir(parents=True, exist_ok=True)
    written, skipped = [], []
    for persona in PERSONAS:
        path = agents_dir / ("%s.md" % persona.slug)
        existing = _read(path)
        if existing and not is_managed(existing):
            skipped.append(persona.slug)
            continue
        path.write_text(persona_markdown(persona), encoding="utf-8")
        written.append(persona.slug)
    return sorted(written), sorted(skipped)


def installed_personas(agents_dir: Path) -> list[str]:
    """The personas on disk that boost still owns (stamp digest still matches).

    This is the *deletion* set — :func:`remove_personas` must only ever touch
    files boost still owns. It is the wrong set for a user-facing count: an
    edited persona file is still on disk and Claude Code still loads it, so
    counting only the managed ones understates what is actually installed.
    Use :func:`present_personas` for that.
    """
    agents_dir = Path(agents_dir)
    return sorted(p.slug for p in PERSONAS
                  if is_managed(_read(agents_dir / ("%s.md" % p.slug))))


def persona_state(agents_dir: Path, persona: Persona) -> str:
    """One of ``"managed"``, ``"edited"`` or ``"absent"`` for one persona file.

    The three states used to collapse to a boolean — "does boost still own
    this file" — which is right for deciding what `bmad off` may delete and
    wrong for reporting what is installed: an edited file is not boost's to
    delete, but it is still on disk and Claude Code loads it same as any
    other subagent definition.
    """
    path = Path(agents_dir) / ("%s.md" % persona.slug)
    text = _read(path)
    if not text and not path.is_file():
        return "absent"
    return "managed" if is_managed(text) else "edited"


def persona_states(agents_dir: Path) -> dict[str, str]:
    """``{slug: state}`` for every known persona, per :func:`persona_state`."""
    agents_dir = Path(agents_dir)
    return {p.slug: persona_state(agents_dir, p) for p in PERSONAS}


def present_personas(agents_dir: Path) -> list[str]:
    """Slugs whose file exists — managed *or* edited — both are real, working
    subagents from Claude Code's point of view; only "absent" is not installed.
    """
    return sorted(slug for slug, state in persona_states(agents_dir).items()
                  if state != "absent")


def remove_personas(agents_dir: Path) -> list[str]:
    """Delete only the persona files boost wrote; return the slugs removed.

    A file the user has edited no longer matches its stamp, so it is not ours to
    delete. `boost bmad off` must never eat someone's work.
    """
    agents_dir = Path(agents_dir)
    removed = []
    for slug in installed_personas(agents_dir):
        try:
            (agents_dir / ("%s.md" % slug)).unlink()
        except OSError:
            continue
        removed.append(slug)
    return removed
