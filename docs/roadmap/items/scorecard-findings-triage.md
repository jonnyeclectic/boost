---
id: scorecard-findings-triage
board: code
section: pipeline
status: planned
category: Supply chain
complexity: M
impact: Med
wow: 2
note: 15 open · 3 fixed, 4 intentional, 5 not code-fixable
order: 13
owner:
pr:
title: OpenSSF Scorecard's 15 findings, triaged into three piles
---
Scorecard files into the same code-scanning inbox as CodeQL, so its findings read like
code defects and get ignored alongside the false positives. They are not defects — they
are <b>posture metrics</b>, and they must not be dismissed as "false positive" the way the
<code>serve.py</code> traversal alerts legitimately were, because that misrepresents the
repo's security posture. Triaged 2026-07-25:
<b>Fixed</b> — <code>TokenPermissions</code> #26/#27/#28: <code>ci</code>,
<code>codeql</code> and <code>adapter-conformance</code> had no top-level
<code>permissions:</code> block at all, scoring 0. Added <code>contents: read</code> as the
least-privilege default.
<b>Intentional, leave</b> — <code>TokenPermissions</code> #39/#37/#25/#24:
<code>publish.yml</code> needs <code>contents: write</code> to create the release and tag,
<code>osv-scanner</code> needs <code>security-events: write</code> to upload SARIF, and
<code>ci.yml</code>'s <code>tests</code> job needs <code>contents: write</code> for the
coverage-badge push. "Fixing" these breaks the release pipeline. They should be
<b>dismissed as used-in-tests/acceptable-risk with a reason</b>, not left open to rot the list.
<b>Not code-fixable</b> — <code>MaintainedID</code> is repository age; <code>CodeReviewID</code>
counts approved changesets and is structurally 0 while loops self-merge;
<code>CIIBestPracticesID</code> is an opt-in badge programme; the four
<code>PinnedDependencies</code> hits are <code>npx</code> and <code>pip</code> invocations
inside steps, not actions, so SHA-pinning does not apply to them as written.
<code>BranchProtectionID</code> is tracked separately in
<a href="#main-has-no-branch-protection">its own card</a> — it is a workflow decision, not a
config oversight.
