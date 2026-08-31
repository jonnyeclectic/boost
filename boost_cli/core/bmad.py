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
  (technical writer) is a game-dev-studio agent, "on hiatus" in bmm. boost
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
    skill: str                 # canonical BMAD v6 skill for this track
    note: str                  # how the lead should open


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
        ),
        skills=("bmad-document-project",),
    ),
)

PERSONA_BY_SLUG: dict[str, Persona] = {p.slug: p for p in PERSONAS}


# ----------------------------------------------------------------------- tracks

TRACKS: dict[str, Track] = {
    "discovery": Track(
        lead="bmad-analyst", support=("bmad-pm",), skill="bmad-deep-recon",
        note="Ground it in sources before recommending."),
    "product": Track(
        lead="bmad-pm", support=("bmad-analyst", "bmad-architect"),
        skill="bmad-prd",
        note="Write criteria a test could assert."),
    "planning": Track(
        lead="bmad-pm", support=("bmad-architect",), skill="bmad-sprint-planning",
        note="Keep the tracked items and the work in sync."),
    "architecture": Track(
        lead="bmad-architect", support=("bmad-dev",), skill="bmad-architecture",
        note="One recommendation, with the rejected option named."),
    "ux": Track(
        lead="bmad-ux", support=("bmad-dev",), skill="bmad-ux",
        note="Hierarchy and spacing before colour."),
    "build": Track(
        lead="bmad-dev", support=("bmad-tea", "bmad-scribe"), skill="bmad-build",
        note="Ship it complete and verified."),
    "quality": Track(
        lead="bmad-tea", support=("bmad-dev",),
        skill="bmad-qa-generate-e2e-tests",
        note="Assertions that a mutation would fail."),
    "docs": Track(
        lead="bmad-scribe", support=("bmad-dev",), skill="bmad-document-project",
        note="Verify against the code, regenerate what is generated."),
    "review": Track(
        lead="bmad-tea", support=("bmad-architect",), skill="bmad-code-review",
        note="Find the failure, not the style nit."),
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


def classify(prompt: str) -> str:
    """Name the track a prompt belongs to, or ``"trivial"`` to stay silent.

    Silence is the default for anything that is not recognisably a unit of
    work: empty input, an acknowledgement, a slash command (which carries its
    own instructions), a short informational question, an explicit opt-out
    ("no bmad"), a prompt that matches no track at all, or — past
    :data:`LONG_PROMPT_WORDS` — one that matches only a single keyword.
    """
    text = prompt.strip()
    if not text or _SLASH.match(text) or _OPT_OUT.search(text):
        return TRIVIAL
    words = text.split()
    if len(words) < MIN_WORDS:
        return TRIVIAL
    if (_INFO_QUESTION.match(text) and len(words) <= QUESTION_MAX_WORDS
            and not _SECOND_SENTENCE.search(text)):
        return TRIVIAL
    # Distinct patterns matched, not occurrences: saying "update" twenty times
    # is one piece of evidence, which is what keeps a repetitive log quiet.
    scores = {t: sum(1 for rx in pats if rx.search(text))
              for t, pats in _COMPILED.items()}
    best = max(scores.values())
    if best == 0 or (best < 2 and len(words) > LONG_PROMPT_WORDS):
        return TRIVIAL
    return next(t for t in TRACK_ORDER if scores[t] == best)


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


def done_checklist(signals: dict) -> list[str]:
    """The definition of done, in the repo's own vocabulary.

    Tests and docs are unconditional — "no doc change needed" is a conclusion to
    reach, not a step to skip. Roadmap and gate clauses appear only when the
    repo actually has one, because an instruction to update a file that does
    not exist teaches the agent to ignore the whole banner.
    """
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

    guide = signals.get("guide")
    if guide:
        items.append("`%s` is binding" % guide)

    return items


# --------------------------------------------------------------------- routing

def route_lines(prompt: str, root: Path | None = None) -> list[str]:
    """The banner for one prompt: `[]` when the prompt is not a unit of work.

    Kept to a handful of lines on purpose — this is prepended to *every*
    substantive prompt, so its cost is paid on each turn of every session.
    """
    track_name = classify(prompt)
    if track_name == TRIVIAL:
        return []
    track = TRACKS[track_name]
    lead = PERSONA_BY_SLUG[track.lead]
    signals = project_signals(Path(root) if root is not None else Path.cwd())

    lines = [
        "[BMAD autopilot] track: %s" % track_name,
        "Lead: `%s` subagent — %s, %s. %s"
        % (lead.slug, lead.character, lead.title, track.note),
    ]
    if track.support:
        lines.append(
            "Support: %s — spawn them with the Agent tool, in parallel where "
            "the work is independent."
            % ", ".join("`%s` (%s)" % (s, PERSONA_BY_SLUG[s].character)
                        for s in track.support))
    lines.extend((
        "BMAD skill: `%s` — invoke it if it is installed; otherwise the "
        "persona's own playbook stands." % track.skill,
        "Done means: " + " · ".join(done_checklist(signals)),
        "Work autonomously through to a finished, verified change; stop to ask "
        "only when a choice would change what gets delivered.",
    ))
    return lines


def route_context(prompt: str, root: Path | None = None) -> str:
    """:func:`route_lines` as one string (``""`` when there is nothing to say)."""
    return "\n".join(route_lines(prompt, root))


# ----------------------------------------------------------------- orientation

def orientation() -> str:
    """The SessionStart briefing: the roster, the phases, and the house rule."""
    roster = "\n".join(
        "  %-15s %s, %s" % (p.slug, p.character, p.title) for p in PERSONAS)
    return """[BMAD autopilot active]
This session routes work through BMAD personas. Persona subagents live in
~/.claude/agents and are delegated to with the Agent tool:

%s

Every substantive prompt arrives with a one-line routing banner naming the lead
persona, the support personas, the BMAD skill for that track, and the definition
of done for this repo. Follow it. Trivial asks get no banner — answer those
directly and skip the ceremony.

BMAD v6 workflow skills, if installed (`boost bmad install`): plan with
bmad-brainstorming / bmad-product-brief / bmad-prd / bmad-architecture /
bmad-create-epics-and-stories / bmad-sprint-planning; ship with bmad-build
(the canonical implementation workflow) / bmad-code-review /
bmad-qa-generate-e2e-tests / bmad-retrospective; bmad-help lists the rest.
Full workflow skills need a per-project `_bmad/` runtime — `boost bmad init`.

House rule: no change is done until its tests, its docs and its tracked item
are done with it. Turn this off with `boost bmad off`.""" % roster


# ------------------------------------------------------------ persona files

def persona_description(persona: Persona) -> str:
    """The one-line `description:` Claude reads when choosing a subagent."""
    return ("%s, %s (BMAD %s). Use PROACTIVELY for %s."
            % (persona.character, persona.title, persona.module,
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

Before you report back, the same contract applies to you as to the session that
spawned you: tests updated and actually run, documentation left true, any
tracked roadmap or backlog item moved to match, and the repo's own gate green
with output you have seen. If you could not finish a part of it, say which part
and why — do not narrow the task silently.
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
    """The personas on disk that boost still owns (stamp digest still matches)."""
    agents_dir = Path(agents_dir)
    return sorted(p.slug for p in PERSONAS
                  if is_managed(_read(agents_dir / ("%s.md" % p.slug))))


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
