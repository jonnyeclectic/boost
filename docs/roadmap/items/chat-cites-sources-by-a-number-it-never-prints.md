---
id: chat-cites-sources-by-a-number-it-never-prints
board: code
section: dx
status: shipped
category: Bug
complexity: S
impact: Med
wow: 3
note: observed in the field — the citations point at nothing
order: 72
owner: loop/chat-citations
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

<b>CORRECTION &mdash; "not yet located" was wrong.</b> This card said there is no <code>chat</code>
row in <code>cli.py</code>'s <code>COMMANDS</code> table, and told the next reader to start from
<code>pip show -f boost-skill-cli</code> because the behaviour must be coming from an installed
build. The row is at <code>cli.py:93</code>, has been all along, and <code>./boost --help</code>
lists the command. What misled the search was looking for <code>commands/chat.py</code>: the
<code>COMMANDS</code> row names its module, and this one lives in
<code>commands/intelligence.py</code> alongside the rest of the <code>ai</code> group. The
engine is <code>core/chat.py</code>. Treating "is this command still shipping?" as the first
question was right; the answer was simply yes.

<b>What shipped.</b> Both halves now agree on one contract. <code>chat.source_text</code>
numbers the candidates from 1 and the system prompt says to answer from "the numbered skills",
so the rendered block enumerates <code>reply.skills</code> &mdash; the same list, in the same
order, so the indices are the model's rather than a parallel scheme invented at render time.
The extractive answer is numbered too, so the keyless path and the AI path refer to the same
rows the same way.

<b>The ambiguity half is fixed where it is decidable.</b> Every citation now carries a
<code>ref</code>, and the invariant is that a <code>ref</code> can be pasted into
<code>boost info</code> and will resolve. Usually that is just the name; when several taps
carry it &mdash; the exact condition <code>catalog.resolve_one</code> refuses on &mdash; it is
the qualified <code>owner/repo:name</code>. Verified end to end against the pinned 10,152-entry
corpus: <code>boost info code-reviewer</code> errors with "exists in multiple taps", and the
<code>ChrisWiles/claude-code-showcase:code-reviewer</code> the sources block now prints
resolves. A name repeated <em>inside</em> one tap is deliberately left bare, because
<code>resolve_one</code> already picks a canonical row for that case.

<b>One thing deliberately not done.</b> The qualifier does not reach the prompt. The system
prompt tells the model to name skills "exactly as given" and <code>ungrounded_names</code>
grades the reply against the entries' <em>bare</em> names, so feeding it qualified names would
make a correctly-quoted recommendation look invented and throw the whole answer away. So
<code>_describe</code> takes the ref on the answer path only, and a test pins that the prompt
still names skills bare.
