---
id: scorecard-findings-triage
board: code
section: pipeline
status: shipped
category: Supply chain
complexity: M
impact: Med
wow: 2
note: 7 open · 3 now hash-pinned, 3 decided, 1 clears itself
order: 13
owner: loop/scorecard-pinned-deps
pr:
title: OpenSSF Scorecard's findings, triaged into three piles
---
Scorecard files into the same code-scanning inbox as CodeQL, so its findings read like
code defects and get ignored alongside the false positives. They are not defects — they
are <b>posture metrics</b>, and they must not be dismissed as "false positive" the way the
<code>serve.py</code> traversal alerts legitimately were, because that misrepresents the
repo's security posture. Triaged 2026-07-25, re-triaged 2026-07-29 against the 7 still open.
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
<b>Correction — <code>PinnedDependencies</code> was NOT "not code-fixable".</b> The first
pass filed #40/#41/#48 under <i>"npx and pip invocations inside steps, not actions, so
SHA-pinning does not apply"</i>. That reads the check as being about action SHAs, and it
is not: for npm the remediation is a <b>committed lockfile</b>, and all three hits were
<code>npm install</code> steps. <code>tests/visual/package.json</code> pinned its two direct
deps exactly — and <code>.gitignore</code> then <i>excluded the lockfile</i>, so 79
transitive packages resolved fresh on every run. <code>theme-lint</code> was worse:
<code>npm install stylelint@16 eslint@9</code> re-resolved the whole linter every run, so
the linter CI executed was never the linter anyone reviewed. Both trees are now hash-pinned
(181 + 81 packages, integrity on every one) and installed with <code>npm ci</code>;
<code>dependabot.yml</code> gains both npm directories, because a pin with no update path is
only half the job.
<b>What the pin immediately exposed.</b> Committing the lock made
<code>osv-scanner</code> able to see the transitive tree for the first time, and it failed
the branch at once on <b>CVE-2026-14257</b> (<code>brace-expansion</code>, CVSS 7.5,
unbounded expansion → OOM). Pre-existing, not introduced: the old floating
<code>npm install eslint@9</code> resolved the same package, invisibly. The advisory's range
is <i>all versions below 5.0.8</i>, so the 1.x maintenance line has no fix — and the obvious
patch, an <code>overrides</code> entry forcing <code>brace-expansion@^5</code>, <b>breaks
eslint</b>: v5 exports <code>{ expand }</code> where <code>minimatch@3</code> requires a
callable default, so <code>eslint "style/**/*.{js,mjs}"</code> dies with
<i>"expand is not a function"</i> while plain <code>eslint style/</code> still passes — a
green-looking linter with a broken glob path. The real fix is upstream:
<code>eslint@10</code> depends on <code>minimatch@^10.2.5</code>, which requires the patched
<code>brace-expansion@^5.0.8</code>. Bumped 9.39.5 → 10.8.0; all 262 packages across both
locks now return zero OSV advisories.
<b>Open by decision, correctly</b> — <code>BranchProtectionID</code> #33 (4/10) and
<code>CodeReviewID</code> #34 (0/26 approved changesets) are two readings of one deliberate
choice recorded in <a href="#main-has-no-branch-protection">its own card</a>: require status
checks, do <i>not</i> require reviews, because the working model is parallel
<code>loop/*</code> branches that self-merge and there is no second reviewer. Every warning
Scorecard prints under #33 — stale-review dismissal, required approvers, CODEOWNERS review,
last-push approval — follows from that one choice. They stay open because the score is
<b>accurate</b>: this repo really does merge without human review. Dismissing them would be
the lie.
<b>Clears itself</b> — <code>MaintainedID</code> #35 is <i>"repository was created within the
last 90 days"</i>. Created 2026-07-17, so it resolves on its own around 2026-10-15. Nothing
to do but not dismiss it.
<b>Needs a human, not a commit</b> — <code>CIIBestPracticesID</code> #36 is the one
remaining actionable finding, and it cannot be fixed from a branch: it asks whether the
project is registered for an OpenSSF Best Practices badge, which means creating a project
entry at <code>bestpractices.dev</code> under a real account and answering its criteria.
<i>Answering</i> them turned out to be a commit after all — see
<a href="roadmap.html#openssf-best-practices-badge">all 67 passing criteria answered</a>,
which found two MUST criteria this card had assumed were covered. Only the registration
itself still needs a human.
