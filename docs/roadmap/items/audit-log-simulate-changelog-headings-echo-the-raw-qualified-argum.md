---
id: audit-log-simulate-changelog-headings-echo-the-raw-qualified-argum
board: code
section: dx
status: inflight
category: CLI · Polish
complexity: S
impact: Low
wow: 1
note: "changelog for anthropics/skills:pdf (anthropics/skills) — the tap printed twice"
order: 243
owner: loop/qualified-name-headings
pr:
title: "<code>log</code>/<code>simulate</code>/<code>changelog</code> headings echo the raw qualified argument, printing the tap twice"
---
Give any of the three a tap-qualified name and the heading repeats the tap. Reproduced verbatim:
<b>changelog</b> &mdash; <code>==&gt; changelog for anthropics/skills:pdf (anthropics/skills)</code>;
<b>log</b> &mdash; <code>==&gt; sickn33/antigravity-awesome-skills:brainstorming &mdash; history in
sickn33/antigravity-awesome-skills</code>; <b>simulate</b> &mdash; <code>==&gt; simulating
sickn33/antigravity-awesome-skills:test-driven-development  (tap sickn33/antigravity-awesome-skills)</code>,
which then carries the raw argument into prose: <code>With
sickn33/antigravity-awesome-skills:test-driven-development active, Claude would:</code>. The bare-name
variation prints the clean form (<code>==&gt; changelog for brainstorming (sickn33/antigravity-awesome-skills)</code>),
so the redundancy is exactly scoped to qualified arguments.

Verification pinned it as an inconsistency, not a choice: all three headings interpolate raw
<code>args.name</code> (<code>quality.py:1154</code>, <code>info.py:844</code>,
<code>intelligence.py:256</code> and <code>:274</code>) with the tap appended, while sibling
<code>cmd_info</code> already splits via <code>catalog.split_name</code> (<code>info.py:401</code>) and shows the
bare name in its headings (<code>info.py:355</code>). <code>split_name</code> was built for exactly this
(shipped item <em>info-rejects-the-qualified-name-it-recommends</em> fixed resolution, not display &mdash;
related, not a duplicate).

Fix: in <code>cmd_log</code>, <code>cmd_simulate</code> and <code>cmd_changelog</code>, split the argument once
(<code>_, bare = catalog.split_name(args.name)</code>) and use <code>bare</code> in the heading and in
simulate's <em>With &hellip; active</em> lead-in, keeping the single tap suffix. Optional polish while there:
bare <code>boost log</code> starts straight in with event rows (<code>47s ago  jonny  install
brainstorming</code>) while its history and diagnostics modes print a <code>==&gt;</code> heading &mdash; an
<code>==&gt; activity</code> heading restores parity. No docs change. Found by the 2026-08 CLI audit
(cluster qualified-name-headings); repro in the audit log.
