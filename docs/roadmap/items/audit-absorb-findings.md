---
id: audit-absorb-findings
board: code
section: dx
status: planned
category: CLI · Consistency
complexity: S
impact: Low
wow: 1
note: absorb is the only generated-skill command with no journal.log call at all
order: 246
owner:
pr:
title: "boost absorb: CLI audit findings (2026-08)"
---
<b><code>cmd_absorb</code> never calls <code>journal.log</code>.</b> After two
<code>absorb --install</code> runs, <code>boost log</code> lists <em>&ldquo;infer
project-conventions&rdquo;</em>, <em>&ldquo;distill brainstorming-distilled&rdquo;</em> and an
<em>&ldquo;import absorbed-patterns&rdquo;</em> entry &mdash; the last written by
<code>install_from_path</code> (<code>core/store.py:1228</code>), not by absorb &mdash; and the verb
<em>absorb</em> never appears. Without <code>--install</code> (stdout mode) the command leaves
<b>zero</b> journal trace, while its siblings journal in both output branches: distill at
<code>commands/intelligence.py:187</code>, infer at <code>:326</code>/<code>:330</code>. An omission,
not a choice &mdash; absorb is the only generated-skill command with no <code>journal.log</code> call.

<br><br>The auditor's second half &mdash; that <code>--install</code> output differs from
<code>install</code>'s report &mdash; reproduced but was <b>declined on design review</b>:
<code>_install_generated</code> (<code>intelligence.py:103-125</code>) is the deliberate shared
renderer for all generated skills (distill/infer/absorb), and reusing <code>store.install</code>'s tap
report would misreport a local re-import as a fresh tap install. Fix is the journal line alone: add
<code>journal.log("absorb", name, patterns=len(patterns), files=len(files))</code> after generation in
both branches of <code>cmd_absorb</code> (<code>intelligence.py:528-580</code>), mirroring distill's
placement. No doc changes.

<br><br>Found by the 2026-08 CLI audit (cluster <code>absorb-parity</code>); repro in the audit log.
