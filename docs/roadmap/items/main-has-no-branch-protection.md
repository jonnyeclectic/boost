---
id: main-has-no-branch-protection
board: code
section: pipeline
status: shipped
category: Release safety
complexity: S
impact: High
wow: 3
note: decided, applied, and now gated against deadlock
order: 14
owner: loop/required-checks-paths
pr:
title: <code>main</code> has no branch protection, so the release rules are honour-system
---
<code>GET /branches/main/protection</code> returns <b>"Branch not protected"</b>. Scorecard
flags it (<code>BranchProtectionID</code>, score 0), but the sharper way to see it is this:
CLAUDE.md says <i>"never merge onto a red release"</i> and <i>"every merge to main cuts a
PyPI release"</i> — and <b>nothing enforces either</b>. A merge with a red gate succeeds
silently, and the release workflow then ships that commit to PyPI. The rule exists only in
the head of whoever is merging.
This is a <b>decision, not a bug</b>, which is why it is filed rather than fixed. Requiring
status checks would have stopped the exact situation that occurred on
2026-07-25, when three PRs sat red on a <code>lock_toolchain --check</code> failure that
belonged to none of them. But protection cuts both ways here: the repo's whole working model
is parallel <code>loop/*</code> branches opening and merging their own PRs, so
<b>"require pull request reviews"</b> would deadlock every loop (there is no second
reviewer), and that same absence is what keeps <code>CodeReviewID</code> pinned at 0/30.
The shape that fits: require <b>status checks</b> to pass (at minimum <code>lint</code>
and the <code>tests</code> matrix) and require branches to be up to date, but do <b>not</b>
require reviews. That enforces the release rule that actually matters while leaving
self-merge intact. Decide before adding more concurrent loops, not after.
<b>Update — the blocker is gone.</b> This prescription was not implementable as written: <code>lint</code> named <i>three</i> different jobs (ci, markdownlint, theme-lint), and GitHub matches required checks by name alone. Those collisions are now renamed, the required list is checked-in at <code>.github/required-checks.txt</code> and gated against drift, and <code>python3 scripts/check_required_checks.py --print-api</code> emits the exact payload — with <code>required_pull_request_reviews: null</code>, so self-merging loops keep working. Still a decision, but now a one-command one.
<b>Shipped.</b> The decision was taken as prescribed — status checks yes, reviews no.
<code>GET /branches/main/protection</code> now returns <code>strict: true</code> with
<code>required_pull_request_reviews</code> absent, so a red gate blocks the merge that would
have cut the release, and loops still self-merge. One correction to the prescription above:
requiring "at minimum <code>lint</code> and the <code>tests</code> matrix" is right, but the
list must contain <i>only</i> checks that run on <b>every</b> PR — the first version also
required four path-filtered docs checks, which report on some PRs and not others and would
have hung any PR that touched no matching file. See
<code>required-checks-can-declare-a-check-that-deadlocks-prs</code>.
