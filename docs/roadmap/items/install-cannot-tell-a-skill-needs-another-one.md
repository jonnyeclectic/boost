---
id: install-cannot-tell-a-skill-needs-another-one
board: code
section: planned
status: planned
category: Install · Research
complexity: M
impact: Med
wow: 3
note: 595 catalogued items declare a prerequisite and boost reads none of them — but only 437 of 1,430 declared values name something boost could install…
order: 348
owner:
pr:
title: "Research: how <code>boost install</code> could tell that a skill needs something else installed first"
---
<b>Requested, and scoped by a census of the real catalog.</b> Some items cannot run alone — a skill
that calls a workflow the user never installed, or one of a set that only works together.
<code>boost install</code> has no concept of a prerequisite: nothing in <code>core/store.py</code>
or <code>core/catalog.py</code> reads one, so the install reports success and the failure surfaces
later, inside an agent session, as a slash command that does not exist.
<br><br>
The data is already on disk, which is what makes this measurable before any code is written.
<code>catalog.scan_dir</code> keeps the <b>full parsed frontmatter</b> in <code>entry["meta"]</code>
(<code>WORKFLOW_META_KEYS</code> only classifies a file as a workflow; it filters nothing), so one
pass over <code>~/.boost/cache/*.json</code> answers it. Over <b>467 taps / 62,791 entries</b> on a
real machine: <b>2,860 entries carry a dependency-ish key</b>, under <b>12 spellings</b> —
<code>requires</code> (2,062) &middot; <code>dependencies</code> (510) &middot;
<code>required</code> (129) &middot; <code>prerequisites</code> (57) &middot;
<code>requires_tools</code> &middot; <code>depends-on</code> &middot; <code>depends_on</code>
&middot; <code>tools_required</code> &middot; <code>requirements</code> &middot;
<code>dependency</code> &middot; <code>requires-extras</code> &middot; <code>uses</code>. But
<b>only 595 of them have a non-empty value</b>: the other 2,265 are an empty <code>requires:</code>
left behind by a template, so the presence of the key says nothing and a reader that treats it as a
declaration is wrong four times in five. And <b>only 35 of the 467 taps</b> use any of them — this
is a convention in a corner of the ecosystem, not a standard.
<br><br>
Those 595 entries declare <b>1,430 values</b>, and they are not one kind of thing.
<b>437 name a catalogued item</b> (<code>prerequisites: [form-cro]</code>) — the only class boost
could act on. <b>486 are bare tokens matching nothing</b> in a 62,791-entry catalog.
<b>230 are namespaced</b> (<code>imbue:proof-of-work</code>, a pack-relative name in a syntax boost
does not parse). <b>183 are package specs</b> (<code>torch&gt;=2.0.0</code>) — a pip requirement,
not a skill. <b>94 are prose.</b>
<br><br>
And the actionable class is the ambiguous one: of the 437 that name a catalogued item, <b>245 name
one that exists in more than one tap</b>. boost already refuses an unqualified name in exactly that
situation
(<code>tests/functional/test_cli_pkg.py::TestBundleEdges::test_unqualified_name_in_two_taps_is_refused</code>),
so a resolver cannot install "the one with that name" — it would have to choose, and choosing
silently is the failure that refusal exists to prevent.
<br><br>
<b>What the research has to answer</b>, in the order that decides whether this ships at all.
<b>1.</b> Is a declaration a declaration? An empty value is not, and 2,265 of 2,860 are empty.
<b>2.</b> What is the value — catalogued item, binary on <code>PATH</code>, Python package, MCP
server? boost can install exactly one of those four, so classification comes before resolution, and
has to be honest about what it cannot classify. <b>3.</b> How is an ambiguous name resolved?
Same-tap-first is the obvious rule and needs measuring against those 245. <b>4.</b> Report, offer,
or install? Installing a <i>rule</i> edits a file the user reads every session, so an auto-install
that walks a dependency graph is more invasive than the thing they asked for; naming what is
missing is cheap and always correct, installing it is neither. <b>5.</b> Cycles and fan-out —
<code>athola/claude-night-market</code>'s <code>architecture-paradigms</code> lists five siblings,
each of which may list it back. <b>6.</b> The prose half: a frontmatter census cannot see "requires
the <code>brainstorming</code> skill" in a body, which is where most of the ecosystem says it, and
whether that is worth reading at all is its own measurement against the false-positive rate.
<br><br>
<b>Deliverable.</b> A measurement note, a decision on question 4, and — if the answer is "report" —
an unmet-prerequisite line on <code>boost install</code> and <code>boost doctor</code> naming the
item and the tap it would come from, wired to whichever spellings survive question 1. The floor for
shipping anything is that it must be wrong less often than silence is: at 2,265 empty declarations
and 486 unresolvable tokens, a naive reader warns on noise far more often than it catches the real
case.
