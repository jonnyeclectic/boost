---
id: main-has-no-branch-protection
board: code
section: pipeline
status: planned
category: Release safety
complexity: S
impact: High
wow: 3
note: nothing enforces the red-merge rule
order: 14
owner:
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
The shape that fits: require <b>status checks</b> to pass (at minimum <code>ci / lint</code>
and <code>ci / tests</code>) and require branches to be up to date, but do <b>not</b>
require reviews. That enforces the release rule that actually matters while leaving
self-merge intact. Decide before adding more concurrent loops, not after.
