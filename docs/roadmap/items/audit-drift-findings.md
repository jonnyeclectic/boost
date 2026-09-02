---
id: audit-drift-findings
board: code
section: health
status: shipped
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: fixed in #719 — all required CI (lint, eval, full test matrix, smoke, mutation) passed and it landed in main via the train-10 batch
order: 264
owner: loop/drift-source-missing-hint
pr: 719
title: "boost drift: CLI audit findings (2026-08)"
---
<b>drift hints <code>boost update</code> for source-missing items whose tap was untapped — a
guaranteed no-op.</b> After <code>untap Aaronontheweb/dotnet-cursor-rules</code>, drift reports
<em>"dotnet-build (rule)&nbsp; source-missing&nbsp; boost update"</em>; running
<code>boost update</code> prints 19 "pinned &hellip; (skipped)" lines then <em>"✓ everything up to
date"</em> and the rule stays source-missing. It can never work:
<code>registry.update</code> iterates configured taps only, and <code>_drift_hint</code>
(<code>quality.py:268-280</code>) maps source-missing to the constant string while receiving only
<code>(name, status)</code>, so it cannot know the tap is gone from config. Verification narrowed
the hint's useful case further: deleting a still-configured tap's clone did <em>not</em> surface
as source-missing (drift re-served it), so the hint fires mainly in exactly the untapped case
where it is a no-op.
<br><br>
The lock entry still records the tap name, so the correct remedy is derivable. Fix: pass the
entry's tap into <code>_drift_hint</code> (<code>quality.py:255-258</code>) and return
<code>boost tap &lt;tap&gt;</code> when that tap is not among the configured registries, keeping
<code>boost update</code> only for a configured-but-uncloned tap. No flag changes, so
<code>docs/commands.html</code> is untouched. Found by the 2026-08 CLI audit (cluster
<code>drift-source-missing-hint</code>); repro in the audit log.
