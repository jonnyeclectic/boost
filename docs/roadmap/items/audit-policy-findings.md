---
id: audit-policy-findings
board: code
section: health
status: shipped
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: policy check evaluates 4 of the 7 rules install enforces — a refused env "passes"
order: 279
owner: loop/policy-check-coverage
pr:
title: "boost policy: CLI audit findings (2026-08)"
---
<code>boost policy check</code> evaluates only <code>blocked_skills</code>/<code>blocked_taps</code>/<code>allowed_taps</code>/<code>min_quality_score</code>
of the seven rules <code>policy.check_install</code> (<code>boost_cli/core/policy.py:58-79</code>) enforces
at install time &mdash; <code>require_version</code>, <code>require_description</code>,
<code>max_skills</code> and <code>denied_capabilities</code> pass silently. Verified: with
<code>max_skills=1</code> and the installed count already at the limit, <code>policy check</code> prints
<em>&ldquo;&#10003; policy check passed (1 skills)&rdquo;</em> exit 0; with
<code>require_version=true</code> and two version-0.0.0 skills installed &mdash; a state where
<code>install</code> refuses a third with <em>&ldquo;skill has no version (required by
policy)&rdquo;</em> &mdash; check still passes. An environment install would refuse is reported clean.

<br><br>Two adjacent honesty gaps in the same command. With <code>policy_enforce=false</code>,
<code>install</code> lets a blocklisted skill through and <code>policy check</code> then exits 1 naming the
violation &mdash; neither command mentions that enforcement is off, so the two disagree silently. And the
<code>pin_only</code> line claims <em>&ldquo;installs/updates are frozen&rdquo;</em> while <code>boost
update</code> still refreshes unpinned taps (measured: 19&times; &ldquo;pinned at &hellip; (skipped)&rdquo;
plus one real 0.65 s fetch, exit 0) &mdash; <code>registry.update</code> never consults the policy.

<br><br>Fix, per the verified recommendation: in <code>cmd_policy</code> check
(<code>boost_cli/commands/configuration.py:444-505</code>) also evaluate installed count vs
<code>max_skills</code>, per-skill <code>require_version</code>/<code>require_description</code> against the
store copy's frontmatter, and <code>denied_capabilities</code> via <code>policy.check_capabilities</code>;
print a &ldquo;not checked: &hellip;&rdquo; line for anything still unevaluated and an explicit
<em>enforce=false</em> line when <code>policy_enforce</code> is off; and reword the <code>pin_only</code>
sentence to name only installs and skill updates, not tap refreshes. Behavior-only, no flag change, so
<code>docs/commands.html</code> needs no regeneration. Found by the 2026-08 CLI audit (cluster
<code>policy-check-coverage</code>); repro in the audit log.
