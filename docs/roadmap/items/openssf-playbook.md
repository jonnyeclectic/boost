---
id: openssf-playbook
board: code
section: docsite
status: shipped
category: Docs
complexity: S
impact: Med
wow: 3
note: the method, not the answers — so another repo can repeat it
order: 6
owner: loop/openssf-playbook
pr:
title: The OpenSSF badge playbook
---
Three badges in one session left two kinds of artifact behind. <a href="roadmap.html#openssf-best-practices-badge">The
answer sheets</a> record <i>what boost answered</i>, which is worth exactly nothing to
anybody else. This records <b>the method</b>.
The parts that cost real time to discover: the badge site issues <b>four independent
badges</b>, not one with tiers, each at its own <code>/&lt;level&gt;/edit</code> form. The
authoritative criteria need <b>two</b> upstream files — <code>criteria.yml</code> has the
MUST/SHOULD and <code>na_allowed</code> flags but no prose, <code>en.yml</code> has the
prose — and the obvious <code>/criteria/0.json</code> endpoint returns 406. A parser that
does not stop at <code>- '1':</code> folds silver into passing; passing is exactly 67, so
the count is the check.
The part that changes how you plan: <b>most unanswered criteria are already satisfied and
merely unrecorded</b>. Nine of Baseline Level 1's 24 were open and every one was already
true — the work was proving it, not building it, and the badge went 63% → 100% with no code.
So every criterion sorts into three buckets: documentation you can write, a repository
setting you cannot do from a branch, and <b>structurally blocked — say so and move on</b>.
Also records the three honesty traps this project walked into and had to back out of:
claiming a setting that needs credentials to read, restating a claim the repo's own
Scorecard triage refuses to make, and inheriting "the licence is MIT" when it was GPL-3.0.
