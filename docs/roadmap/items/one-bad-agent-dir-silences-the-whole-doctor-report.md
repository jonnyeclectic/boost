---
id: one-bad-agent-dir-silences-the-whole-doctor-report
board: code
section: health
status: shipped
category: Robustness · Bug
complexity: S
impact: Medium
wow: 2
note: A single agent whose `dir` names an unset variable makes `boost doctor` exit 1 with one line instead of reporting it as an issue…
order: 346
owner: loop/doctor-bad-agent-dir
pr: 1049
title: One unresolvable agent dir silences the whole `boost doctor` report
---
<b>Found by the review of <code>loop/codex-agent-target</code>.</b>
<code>paths.expand</code> now raises a <code>BoostError</code> for a <code>${VAR}</code> with no fallback
and nothing in the environment, rather than resolving it to an empty or literal path — the change that
stopped a mistyped <code>agents.&lt;name&gt;.dir</code> silently installing into
<code>./skills</code>. <code>agents.known_agents</code> calls it for every configured agent, so one bad
row now aborts every command that asks who the agents are: <code>doctor</code>,
<code>heal</code>, <code>clean</code>, <code>install</code>, <code>sync</code>.

For most of those, refusing is the right answer. For <code>doctor</code> it is not: its whole job is to
surface a misconfiguration, and it exits 1 having reported nothing else — no lock check, no store check,
no duplicate-discovery check. The remedy is reachable (<code>boost config set</code> never calls
<code>known_agents</code>, verified in a sandbox), so this is a bad report rather than a lockout.

<b>Fix direction.</b> Catch <code>BoostError</code> around the agent lookups in <code>cmd_doctor</code>
and render it as an issue row, then continue with an empty agent set. The catch has to cover the
indirect callers too — <code>store.duplicate_discovery</code>, <code>store.sync_plan</code> and the
per-agent coverage counts all reach <code>known_agents</code> — so the natural shape is one resolution
step at the top of the command whose failure degrades the agent-dependent sections rather than the run.

<b>Shipped.</b> Reproduced on <code>11dbbc7</code> with <code>agents.cursor.dir = ${NOPE}/skills</code>:
<code>boost doctor</code> printed three lines and the bare <code>expand</code> error, exit 1, no verdict;
<code>--json</code> printed the same error and no JSON; the MCP <code>boost_doctor</code> reply was that error
alone, naming the variable but not the key. A per-call trace over a sandbox holding one skill, one rule and
one workflow found nine doctor call sites reaching <code>known_agents</code>. The fix is the one resolution
step the card asked for: <code>agents.check()</code> returns every unresolvable row keyed by agent name, doctor
reports each as an <code>agent-config</code> issue naming <code>agents.&lt;name&gt;.dir</code>, the
<code>${VAR:-default}</code> fix and the <code>boost config set</code> remedy, and the agent-dependent sections are
skipped and say so. The summary reads "links not checked" as a warning, and neither "with agent links" nor
"fully materialized" is claimed for checks that never ran. <code>known_agents</code> still raises, so install,
sync, heal and clean still refuse. After the fix the same sandbox gives every other check, a verdict of
"1 issue needs attention" and valid JSON. The MCP tool names the key and points at <code>boost doctor</code>,
not at <code>boost sync</code>, which would refuse. The printed remedy was run and clears the issue.
Removing any one of the eight guards (one covers both materialization loops and the reaches-no-agent check) fails the new functional tests.
