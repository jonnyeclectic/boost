---
id: osps-baseline-levels
board: code
section: health
status: inflight
category: Security · Posture
complexity: M
impact: Med
wow: 3
note: L1 earned · L2 one DCO decision away · L3 blocked on a second human
order: 5
owner: loop/osps-baseline-2
pr:
title: OSPS Baseline — three levels, audited rather than assumed
---
The <a href="roadmap.html#openssf-best-practices-badge">passing badge</a> is one of
<b>four</b> badges bestpractices.dev issues for a project. The other three are the OSPS
Baseline series, a different criteria set with different questions, and nobody had looked at
them. Audited all three against the repo rather than against a summary.
<b>Level 1 is earned</b> — 24 criteria, and nine of them were sitting unanswered at 63%.
Every one turned out to be already true and merely unrecorded: branch protection plus a
ruleset refuse a direct commit to <code>main</code>, no workflow uses
<code>pull_request_target</code> so a fork's code never sees a secret, and an audit of every
tracked file for binary content found three zero-byte markers and a 10-byte fuzz seed. The
work was proving it, not building it.
<b>Level 2 needed four documents that did not exist</b>, and writing them surfaced things
worth having regardless of the badge: <code>MAINTAINERS.md</code> (who holds which
credential — the answer for PyPI is <i>nobody</i>, because Trusted Publishing means there is
no token to hold), <code>SUPPORT.md</code> (only the latest release is supported, stated as
policy rather than left implicit), <code>docs/dependencies.md</code> (the remediation
threshold at which an SCA finding blocks a merge, and the rule that a suppression needs a
written argument), and <code>docs/verifying-releases.md</code> (the exact
<code>gh attestation verify</code> commands, including the <code>--signer-workflow</code>
form that checks <i>which workflow</i> built the artifact).
<b>Level 3 is blocked, and it is the same wall as gold.</b> OSPS-QA-07.01 requires a
non-author human approval before merging. This repo merges parallel <code>loop/*</code>
branches with no second reviewer, which its own <a href="roadmap.html#scorecard-findings-triage">Scorecard triage</a>
already refuses to lie about. Not a gap to close with a commit — it needs a second person.
