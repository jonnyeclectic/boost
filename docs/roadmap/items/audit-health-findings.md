---
id: audit-health-findings
board: code
section: health
status: inflight
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: health calls a drifted machine "● healthy" and scores gemini 1/1 with the store dir gone
order: 270
owner: loop/health-dashboard-coverage
pr:
title: "<code>boost health</code>: CLI audit findings (2026-08)"
---
<b>The dashboard counts skills only, so it calls a drifted machine healthy.</b> With 1 skill, 2 rules
and 1 workflow installed and the workflow locally edited, <code>boost health</code> prints
<em>skills 1 installed &middot; drift 1 in-sync &middot; &#9679; healthy</em> while <code>boost drift</code>
on the same HOME says <em>3 in-sync &middot; 1 local-edits</em>. <code>cmd_health</code> iterates the
skills-only <code>_iter_installed()</code> (<code>quality.py:1172</code>,
<code>_common.py:20</code>) although <code>_iter_installed_all</code> already exists
(<code>_common.py:63</code>), so rules and workflows are invisible to the skills, drift and
attention rows. Fix: iterate <code>_iter_installed_all()</code>, print per-kind counts, and fold the
rule/workflow materialization status into the drift row. <code>docs/DEBUGGING.md</code> needs the
matching update.

<br><br><b>The native-store row is hard-coded green.</b> With an installed skill's store directory
removed, health prints <em>gemini 1/1 &#10003; (reads the store directly)</em> beside
<em>claude-code 0/1 !</em> and <em>drift 1 store-missing</em> in the same report &mdash; the row is
<code>len(expected)/len(expected)</code> with an unconditional &#10003;
(<code>quality.py:1197-1199</code>), never statting the store. Fix: for
<code>agents.native_store_agents()</code> count skills whose
<code>store.skill_store_dir(n).is_dir()</code> over expected. Found by the 2026-08 CLI audit
(cluster <code>health-dashboard-misreports</code>); repro in the audit log.
