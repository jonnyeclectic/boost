---
id: audit-test-findings
board: code
section: health
status: inflight
category: CLI · Bug
complexity: S
impact: Med
wow: 2
note: a skill boost lint fails (exit 1) passes boost test outright (exit 0)
order: 297
owner: loop/test-lint-consistency
pr:
title: "boost test: CLI audit findings (2026-08)"
---
<b><code>boost test</code>'s lint check passes skills that <code>boost lint</code> fails</b> (med).
The two commands use different predicates: <code>cmd_test</code> fails its <em>lint</em> check only on
<code>score &lt; 40</code> (<code>quality.py:829-831</code>) while <code>cmd_lint</code> fails on
score below min <em>or any hard error</em> (<code>quality.py:742-756</code>). Audited case: a broken
SKILL.md gives <code>boost test</code> &rarr; <em>&ldquo;pdf-official&nbsp;&nbsp;FAIL&nbsp;&nbsp;parses,
verify&rdquo;</em> with lint not even listed, while <code>boost lint</code> says
<em>&ldquo;40/100 / error: missing required field: name&rdquo;</em>, exit 1. Verification found it
worse than the audit stated: a skill missing its description scores 85, so <code>boost test</code>
prints <em>&ldquo;PASS / 1 passed, 0 failed&rdquo;</em> exit 0 while <code>boost lint</code> exits 1
on the same state &mdash; opposite verdicts from the two commands whose job is agreeing on health.
Fix: extract lint's failure predicate (score &lt; min or any hard error) into a shared helper, e.g.
<code>quality._lint_failed(sdir, min_score=40)</code>, and call it from <code>cmd_test</code> so
<em>lint</em> fails whenever <code>boost lint</code> would.

<b>A skill named twice counts twice</b> (low). <code>boost test brainstorming brainstorming</code>
prints two <em>PASS</em> rows and <em>&ldquo;2 passed, 0 failed&rdquo;</em> for one installed skill;
verification reproduced the same in <code>boost lint</code> (three args &rarr; &ldquo;3 skills pass
lint&rdquo;) and it reaches every <code>_iter_installed</code> caller (test, lint, drift, the
decay family), because <code>_common.py:48</code> returns one tuple per argv name with no dedupe.
Fix: order-preserving <code>names = list(dict.fromkeys(names))</code> in
<code>_common._iter_installed</code> (and <code>_iter_installed_all</code>,
<code>_common.py:29-49,:63</code>) so every skill-list command reports each skill once. No doc
changes for either finding.

Found by the 2026-08 CLI audit (clusters <code>test-vs-lint-predicate</code>,
<code>repeated-name-args</code>); repro in the audit log.
