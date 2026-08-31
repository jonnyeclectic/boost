---
id: bmad-autopilot-one-command-persona-routing
board: code
section: dx
status: shipped
category: Agents · BMAD
complexity: M
impact: High
wow: 5
note: one command, no Node, routes every prompt
order: 33
owner: loop/bmad-autopilot
pr:
title: <code>boost bmad</code> needed Node and a per-project install before it did anything
---
<code>boost bmad</code> was a scope-aware wrapper around <code>npx bmad-method install</code>.
Every path through it required Node.js 20.12+, a network round trip and a per-project
<code>_bmad/</code> runtime, and what you got at the end was a <code>SessionStart</code> paragraph
telling the model that skills existed. Nothing routed. The user still had to know which persona
owned the task in front of them and invoke it by hand — so the personas were documentation, not
behaviour.
Shipped: <b><code>boost bmad on</code></b> — one command, global by default, pure stdlib. It writes
seven BMAD persona subagents into <code>~/.claude/agents/</code> and installs two hooks: the
existing <code>SessionStart</code> briefing, and a <code>UserPromptSubmit</code> router that
classifies each incoming prompt into one of nine tracks and prefixes it with the lead persona, the
support personas to spawn alongside, the canonical BMAD v6 skill for that track, and a definition of
done. The heavy <code>npx</code> path stays exactly as it was behind <code>boost bmad install</code>;
the two compose, and the banner says which case you are in.

<b>The definition of done is read off the repo, not hardcoded.</b>
<code>core/bmad.project_signals()</code> probes for the test directory, the doc paths, the roadmap
items directory and the gate command (<code>make check</code> → <code>make test</code> →
<code>npm test</code> → per-language default), so the banner names <code>tests/</code>,
<code>docs/roadmap/items/</code> and <code>make check</code> in this repo and says something
different in yours. A checklist that names a path which does not exist teaches the agent to skip the
whole banner, so clauses for a roadmap or a gate appear only when there is one — while tests and
docs are unconditional, because &ldquo;no doc change needed&rdquo; is a conclusion to reach, not a
step to skip.

<b>Classification is precedence-ordered, and <code>build</code> loses every tie.</b> Real prompts hit
several keyword tables at once: &ldquo;add tests for scan_dir&rdquo; is a build verb <em>and</em> a
testing noun, &ldquo;add a roadmap item&rdquo; is a build verb <em>and</em> planning. First-match
ordering sent all three to Amelia and made the other six personas decoration, so
<code>TRACK_ORDER</code> is an explicit tie-break with the catch-all last.

<b>Three upstream facts drove the design, and each was checked rather than assumed.</b>
<i>(1)</i> The orientation text this command shipped was advertising <code>bmad-quick-dev</code> and
<code>bmad-dev-story</code>; both are now <b>deprecated v6-shims</b> that redirect to
<code>bmad-build</code>, so every build task was being routed through a deprecation notice. <i>(2)</i>
It also named <code>bmad-agent-tech-writer</code> as a persona — Paige is a <code>gds</code>
(game-dev-studio) agent and is <b>&ldquo;on hiatus&rdquo; in <code>bmm</code></b>, so that skill never
existed to invoke. <i>(3)</i> BMAD's installer <b>never writes <code>.claude/agents/</code></b> — its
<code>claude-code</code> platform entry has exactly one target, <code>.claude/skills</code>, and
sub-agents are a runtime behaviour of <code>bmad-party-mode</code>. The persona subagents duplicate
nothing upstream.

<b>The router must never exit non-zero.</b> On <code>UserPromptSubmit</code> an exit code of 2 blocks
the prompt <em>and erases it from the transcript</em>, so a crash in the router would eat the user's
message. Every failure mode — unreadable stdin, junk that is not JSON, a raising
<code>project_signals</code> — degrades to silence and exit 0, and the tests drive each of those
paths. The same instinct governs when it stays quiet on purpose: acknowledgements, slash commands
(which carry their own instructions), short informational questions and an explicit
<code>no bmad</code> opt-out all produce no banner, because a delegation banner on
&ldquo;what does <code>scan_dir</code> do?&rdquo; is worse than no router at all.

<b>Ownership is content-derived, because marker-presence was wrong in both directions.</b>
Persona files carry a <code>&lt;!-- boost:bmad-persona &lt;digest&gt; --&gt;</code> stamp, and a file
counts as boost's only while that digest still matches the rest of the file. The first cut
tested for the marker alone, which <em>looked</em> like the rule <code>claude_settings</code>
applies to hooks but was not: the marker is an HTML comment a user editing the body has no
reason to remove, so an edited persona was silently overwritten by the next
<code>boost bmad on</code> <em>and</em> deleted by <code>boost bmad off</code> — while that
command printed &ldquo;hand-edited personas were left in place&rdquo;. Digesting the content
makes both statements true: <code>on</code> reports an edited file as kept, <code>off</code>
leaves it, and the README no longer promises something the code did not do.

<b>The router's never-exit-non-zero rule had a hole above it.</b> <code>_route</code> catches
everything and returns 0, but argparse never reaches it: the hook is installed against
<code>paths.launcher()</code> — whatever <code>boost</code> is on PATH, not necessarily the
build that wrote the hook — so a stale pipx install or a later downgrade hits
<code>bmad route</code>, fails <code>invalid choice</code>, and exits <b>2</b>. On
<code>UserPromptSubmit</code> that does not merely log: it blocks the prompt and erases it
from the transcript, so every message the user typed would vanish until they found the hook.
The guard has to sit outside any version of boost, so the installed command ends
<code>|| true</code>.

<b>First production tuning: evidence has to scale with prompt length.</b> Within an hour of
release, the first real-world false positive arrived — a user pasted their own terminal session
back into the chat (~90 words of <code>boost self-update</code> output) and got a full delegation
banner, because <code>\bupdate\b</code> matches inside &ldquo;self-<b>update</b>&rdquo;. One weak
hit in a wall of text. Every existing trivial gate keys on <em>shape</em> &mdash; a question, a
slash command, too few words &mdash; and a pasted log is none of those, so none of them could
fire. The missing signal was density: in a short prompt every word is deliberate, so one keyword
is strong evidence; in a long one it is easily incidental, while a genuine long request names its
work more than once (&ldquo;refactor &hellip; and update &hellip;&rdquo;). Past
<code>LONG_PROMPT_WORDS</code> (60) the router now needs two distinct keyword hits. Verified
against the real paste and against 80- and 69-word genuine requests, which still route.

<b>Two keyword-table defects, found by routing real prompts rather than by reading.</b>
<code>\bfix\w*\b</code> matches &ldquo;fixture&rdquo; and <code>\bchange\w*\b</code> matches
&ldquo;changelog&rdquo; — the exact words the quality and docs tables claim — so &ldquo;add
fixtures for the sandbox HOME&rdquo; scored build=2 against quality=1 and went to Amelia.
Because build won on <em>score</em> it never reached <code>TRACK_ORDER</code>, so the
&ldquo;build loses every tie&rdquo; invariant was bypassed rather than violated: the fix is to
enumerate inflections, not to reorder. Separately, the interrogative gate anchored on the
first token only, making &ldquo;Why is test_catalog flaky on Windows? Fix it and add a
regression test.&rdquo; trivial — a real task, silently unrouted. A question followed by
another sentence is a preamble to an instruction, not a question.
