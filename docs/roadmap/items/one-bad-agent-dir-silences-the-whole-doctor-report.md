---
id: one-bad-agent-dir-silences-the-whole-doctor-report
board: code
section: health
status: planned
category: Robustness · Bug
complexity: S
impact: Medium
wow: 2
note: A single agent whose `dir` names an unset variable makes `boost doctor` exit 1 with one line instead of reporting it as an issue…
order: 346
owner: loop/codex-agent-target
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
