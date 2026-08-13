---
id: crash-reports-leak-api-keys
board: code
section: trust
status: shipped
category: Bug
complexity: S
impact: High
wow: 5
note:
order: 3
owner: fix/audit-findings
pr:
title: Crash reports carried API keys in cleartext
---
A crash report is the one file boost actively invites a user to paste into a bug report — its
docstring says so: "a user can attach one file to a bug report instead of reproducing by hand."
<code>_env_snapshot()</code> built that file by printing every <code>BOOST_*</code> variable
verbatim. Since boost documents <code>BOOST_ANTHROPIC_API_KEY</code> as the way to supply a key,
the variable most likely to be <em>set</em> was also the one most likely to be secret.

Found on a real machine, not in review: three reports under <code>~/.boost/logs/</code>, each
carrying a live <code>sk-ant-api03-…</code> key, written by two ordinary
<code>boost install</code> failures and one <code>boost search</code>. Nothing had to go wrong
beyond the crash itself — the leak was the reporting path working as designed.

Values are now withheld two ways, because either alone rots. A name ending in
<code>KEY</code>/<code>TOKEN</code>/<code>SECRET</code>/<code>PASSWORD</code>/<code>AUTH</code> is
redacted, which covers every provider without enumerating them; and a value carrying a known
credential prefix (<code>sk-</code>, <code>ghp_</code>, <code>xox…</code>, <code>AKIA…</code>) is
redacted whatever it is called, because a name denylist always trails the next provider someone
adds. Redacted, never dropped: a missing line reads as "unset", and the fact that a key
<em>was</em> configured is exactly what the reader needs.
