---
id: audit-deps-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: Med
wow: 2
note: deps shows ✗ not installed yet exits 0; the only real-world requires: shape reads as (none)
order: 261
owner:
pr:
title: "boost deps: CLI audit findings (2026-08)"
---
<b>A transitive unmet requirement is shown as ✗ but exits 0, and the two JSON modes disagree on
shape.</b> <code>deps dep-child</code> prints <code>&#8627; ghost-skill ✗ not installed</code> yet
exits 0, while <code>deps</code> (all-installed mode) exits 1 for the same fact — in
<code>cmd_deps</code>, <code>problems</code> (<code>info.py:915-917</code>) tests only direct
requires while the renderer walks one level deeper, so the command shows a problem its exit code
denies (single-name <code>--json</code> has the same hole). The envelopes were written separately
and share nothing: <code>deps --json</code> gives
<code>{"unmet":[{"skill","requires"}],"conflicts":[[a,b]]}</code> where single-name mode gives
<code>{"name", "requires":[{"name","installed","requires"}], "conflicts":[{"name","installed"}]}</code>
— same facts, keyed <code>skill</code> vs <code>name</code>, conflicts as bare pairs vs objects,
and nested requires are bare strings with no <code>installed</code> flag. Fix in
<code>info.py:897-973</code>: fold displayed sub-requirement states into <code>problems</code>,
emit nested requires as <code>{name, installed}</code> objects, unify the two envelopes on one
requirement/conflict record shape, and print a one-line summary with a
<code>boost install &lt;missing&gt;</code> hint when problems exist.
<br><br>
<b>deps prints <code>requires: (none)</code> for the only <code>requires:</code> shape the shipped
corpus actually uses.</b> seismic-automation's SKILL.md declares <code>requires:</code> /
<code>mcp: [rube]</code> (the audit counted 832 composio SKILL.md files using this mapping form,
and none in the 20 taps using a name list); <code>deps seismic-automation</code> answers
<code>requires: (none)</code> exit 0 while <code>info seismic-automation</code> shows
<code>mcp servers  rube</code> — the two commands contradict each other about what the skill
needs, because <code>_as_list</code> (<code>info.py:177-183</code>) handles only string/list
forms. Fix: when <code>meta["requires"]</code> is a mapping, surface its <code>mcp</code> list
(reuse <code>store.declared_mcp_servers</code>, which <code>cmd_info</code> already reads at
<code>info.py:448</code>) as e.g. <code>requires: mcp rube (not registered)</code> and emit an
<code>mcp</code> key in <code>--json</code>; keep plain name lists unchanged. No flag changes, so
<code>docs/commands.html</code> is untouched. Found by the 2026-08 CLI audit (clusters
<code>deps-exit-and-json</code>, <code>deps-requires-mcp</code>); repro in the audit log.
