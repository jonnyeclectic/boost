---
id: audit-chat-findings
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: chat's own printed suggestion retrieves the wrong skill; its "&gt; " prompt leaks into piped stdout
order: 255
owner: loop/chat-audit-findings
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
