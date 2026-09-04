---
id: audit-cohort-findings
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: S
impact: Low
wow: 1
note: apply counts a mixed cohort as 1 of 2, exits 0 when nothing applied, journals no event
order: 256
owner: loop/cohort-apply-reporting
pr:
title: "boost cohort: CLI audit findings (2026-08)"
---
<b><code>cohort apply</code> drops not-found members from its summary, exits 0 even when nothing
applied, and journals no event.</b> A cohort whose only skill exists in no tap prints
<em>"! nosuchskill-zzz not found in any tap — skipped"</em> then <em>"applied: 0 installed, 0
already present"</em> and exits 0 — the one member the cohort had is in neither count. Verified
broader than filed: a mixed cohort (<code>brainstorming</code> + a bogus name) reports
<em>"applied: 0 installed, 1 already present"</em>, silently dropping the missing member, because
<code>team.py</code>'s <code>entry is None</code> branch <code>continue</code>s with no counter and
apply returns 0 unconditionally (<code>boost_cli/commands/team.py:125-159</code>).

<br><br>Apply also writes no journal event, so <code>pulse</code>/<code>who</code> never show a
rollout happened — while create (<code>team.py:103</code>), delete (<code>:121</code>) and the
profile ops all journal, making the asymmetry plainly unintentional. Fix: count a
<code>missing</code> counter in the not-found path, print <em>"applied: N installed, N already
present, N not found"</em> (suppressed when 0), add <code>journal.log("cohort", cname, op="apply",
installed=…, present=…, missing=…)</code> per applied cohort, and return 1 when
<code>missing&gt;0</code> and nothing was installed or present. Drive-by from verification:
repeated <code>--skills</code> flags replace rather than append, so <code>--skills a --skills
b</code> creates a one-skill cohort. No doc changes. Found by the 2026-08 CLI audit (cluster
<code>cohort-apply-reporting</code>); repro in the audit log.
