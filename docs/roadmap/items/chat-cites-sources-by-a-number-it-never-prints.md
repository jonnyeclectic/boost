---
id: chat-cites-sources-by-a-number-it-never-prints
board: code
section: dx
status: planned
category: Bug
complexity: S
impact: Med
wow: 3
note: observed in the field — the citations point at nothing
order: 72
owner:
pr:
title: <code>boost chat</code> cites its sources by a number it never prints
---
<code>boost chat</code> answers with numbered references to the sources beneath it, and the
source list is rendered unnumbered — so every citation points at nothing:

<code>$ boost chat "how do I review a diff for security problems?"</code><br>
<code>&nbsp;&nbsp;Use <b>differential-review</b> (#3) &hellip; Alternatively, <b>review-swarm</b> (#2) &hellip;</code><br>
<code>&nbsp;&nbsp;sources · ranked by hybrid RRF (BM25 + dense)</code><br>
<code>&nbsp;&nbsp;&nbsp;&nbsp;code-reviewer&nbsp;&nbsp;workflow&nbsp;&nbsp;(davila7/claude-code-templates)</code><br>
<code>&nbsp;&nbsp;&nbsp;&nbsp;review-swarm&nbsp;&nbsp;skill&nbsp;&nbsp;(lingxling/awesome-skills-cn)</code><br>
<code>&nbsp;&nbsp;&nbsp;&nbsp;differential-review&nbsp;&nbsp;skill&nbsp;&nbsp;(vibeeval/vibecosystem)</code>

The numbers are not wrong — <code>#2</code> and <code>#3</code> are the right rows by position.
They are simply <em>unresolvable</em>, because the renderer never emits the index the prompt
told the model it could cite. The reader has to count rows to decode an answer that was written
to be scanned. Either number the list or stop citing by number; the two halves currently
disagree about which contract is in force.

<b>Second, smaller defect in the same output.</b> The recommended <code>differential-review</code>
is carried by three taps, so the bare name chat handed back was not directly actionable —
<code>boost info differential-review</code> on it errors with an ambiguity. Since chat already
knows which tap each retrieved row came from (it prints it, in parentheses, on the very next
line), it can hand back the qualified <code>tap:skill</code> form when a name is ambiguous and
the follow-up command will work first time. That form is only worth emitting now that
<a href="#info-rejects-the-qualified-name-it-recommends">info accepts it</a>; before that fix,
qualifying the name would have traded one dead end for another.

<b>Not yet located.</b> There is no <code>chat</code> row in <code>cli.py</code>'s
<code>COMMANDS</code> table and no <code>commands/chat.py</code> in this repository — the
observed behaviour comes from an installed <code>boost-skill-cli</code> build. Whoever picks
this up should start from <code>pip show -f boost-skill-cli</code> to find the source, and
should treat "is this command still shipping?" as the first question rather than an assumption.
