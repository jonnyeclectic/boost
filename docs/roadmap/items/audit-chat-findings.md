---
id: audit-chat-findings
board: code
section: dx
status: shipped
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: chat follow-ups like "which of these" answer from the previous turn; no "&gt; " prompt on piped stdin; search takes -k
order: 255
owner: loop/chat-audit
pr:
title: "boost chat: CLI audit findings (2026-08)"
---
<b>Referential follow-ups retrieve unrelated skills — including the suggestions chat itself prints.</b>
Turn 1 <em>"how do I review a diff?"</em> ranks <code>orch-review</code>; chat then suggests
<em>"what does orch-review actually do?"</em>, and typing that ranks <code>orch-refine-code</code>
<em>above</em> <code>orch-review</code>. Its other suggestion <em>"which of these should I install
first?"</em> returns <code>teach</code>, <code>mercury-mcp</code>, <code>write-concisely</code> —
nothing from the previous turn, and at 7 words it never even hits <code>expand_query</code>'s
&le;6-word gate (<code>core/chat.py:111-128</code>). Not AI-dependent: retrieval bounds any answer.
Fix: resolve referential follow-ups ("the second one", "which of these") against the previous
reply's retrieved skills instead of re-querying; on the no-AI path boost the previous hit set or
stop printing <code>suggest_followups()</code> questions the extractive path cannot answer
(<code>core/chat.py:266-288</code>, <code>:380</code>); rank an exactly-named skill first.
Found by the 2026-08 CLI audit (cluster <code>chat-followup-retrieval</code>); repro in the audit log.

<br><br><b>The interactive "&gt; " prompt is written to stdout when stdin is piped.</b> Verified with
streams separated: three <code>"&gt; "</code> lines in the stdout capture, stderr empty, and
<code>chat &lt; /dev/null</code> ends <code>"…Ctrl-D to exit\n\n&gt; \n"</code> — so a script
capturing answers gets prompt chrome mixed in. <code>_chat_session</code> calls
<code>input("\n&gt; ")</code> unconditionally (<code>boost_cli/commands/intelligence.py:1211</code>);
gate it on <code>sys.stdin.isatty()</code> and add a functional test asserting no
<code>"&gt; "</code> in piped stdout. Found by the 2026-08 CLI audit (cluster
<code>chat-prompt-echo</code>); repro in the audit log.

<br><br><b>chat is the only command that accepts <code>-k</code>.</b> <code>search "…" -k 5</code>
fails with <em>"Error: unrecognized arguments: -k 5"</em> while <code>chat -k 5</code> works
(<code>intelligence.py:1157</code>); every other retrieval-limit sibling takes <code>--limit</code>
only. Add <code>-k</code> as an alias of <code>--limit</code> to <code>cmd_search</code>
(<code>discovery.py:97</code>) — and optionally the other limit commands — then regenerate
<code>docs/commands.html</code> and update <code>docs/chat.html</code>. Found by the 2026-08 CLI
audit (cluster <code>search-k-alias</code>); repro in the audit log.

<br><br><b>Shipped.</b> Measured on a sandbox catalogue (the fixture tap plus a synthetic
tap carrying the audit's names), with <code>BOOST_NO_AI=1</code> and stdin piped. After
<em>"how do I review a diff?"</em>, <em>"which of these should I install first?"</em> used to share
1 of 5 skills with the turn before; it now answers from that turn's list, 5 of 5, sourced as
<code>previous answer</code>, and <em>"what about the second one?"</em> answers with that one row.
Only a pointer counts: <em>"of these"</em>, <em>"from the others"</em>, <em>"that one"</em>,
<em>"those skills"</em>, <em>"the second one"</em>, <em>"about #2"</em>. A new question that merely
uses one of those words is searched as before, and returns what main returns:
<em>"how do I create my first skill?"</em>, <em>"which one is best for setting up pre-commit hooks
for linting?"</em>, <em>"how do I scaffold the other SKILL.md frontmatter?"</em>, <em>"what's the
last skill I should install for linting"</em>, <em>"how do I review PR #2?"</em>. A skill the
question names is ranked first, taken from the rows the user was just shown, then the ranked hits,
then the catalogue, on both paths: <em>"is pre-commit better than those skills?"</em> keeps the
previous list and puts <code>pre-commit</code> first, so an AI answer about it is grounded. A
one-word name only counts when the previous answer showed it. Without AI, chat now suggests only
<em>"what does X actually do?"</em>, the one follow-up the plain list of matches can answer. The
audit's ordering for that question (<code>orch-refine-code</code> above <code>orch-review</code>)
depends on the catalogue: it reproduces where a sibling's description repeats the question's
terms (<code>orch-refine-code</code>: <em>"what does the reviewer actually want changed"</em>).
There main ranks <code>orch-refine-code</code> first and this change ranks <code>orch-review</code>
first.

Piped stdin now gets no <code>"&gt; "</code> prompt and no typing hint (4 prompt lines in stdout
before, 0 after, and <code>chat &lt; /dev/null</code> no longer ends <code>"\n&gt; \n"</code>),
the same rule <code>output.confirm</code> follows. A terminal is unchanged, checked under a real
pty. <code>boost search -k N</code> is now an alias of <code>--limit</code> (it was
<em>"unrecognized arguments: -k 2"</em>, exit 2). The other limit commands are unchanged.
<code>docs/chat.html</code> never said chat was the only command with <code>-k</code>; its
follow-up step now describes answering from the previous list.
