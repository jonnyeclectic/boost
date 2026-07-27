---
id: main-ruleset-ref-pattern-has-literal-quotes
board: code
section: trust
status: shipped
category: Release safety
complexity: S
impact: High
wow: 5
note: 8 active rules enforcing nothing — and the obvious fix deadlocks every PR
order: 51
owner: loop/required-checks-paths
pr:
title: The <code>main</code> ruleset is inert — its ref pattern is <code>refs/heads/"main"</code>, quotes included
---
The repo has an <b>active</b> ruleset named <code>main</code> (id 19130332) carrying eight
rules: <code>deletion</code>, <code>non_fast_forward</code>, <code>pull_request</code>,
<code>required_status_checks</code> (9 contexts), <code>code_quality</code>,
<code>code_coverage</code> (minimum 80), <code>code_scanning</code> and
<code>required_deployments</code>. Its ref condition is:
<code>"include": ["refs/heads/\"main\""]</code> — with <b>literal quote characters</b>, so it
matches a branch named <code>"main"</code>, not <code>main</code>.

GitHub's authoritative endpoint settles it: <code>/rules/branches/main</code> returns
<b>0 rules</b>, while <code>/rules/branches/%22main%22</code> returns all 8. Everything in
that ruleset is unenforced. Only the legacy branch protection is actually gating
<code>main</code>, and it requires a different, shorter list.

<b>Do not just fix the quotes.</b> The ruleset includes
<code>required_deployments: ["github-pages", "pypi"]</code>. Correcting the ref pattern
activates that rule, and no pull request deploys to the <code>pypi</code> environment —
<code>publish.yml</code> runs post-merge on <code>workflow_run</code>. So the one-character
fix converts an inert ruleset into a hard deadlock on every PR, for a reason that has
nothing to do with status checks. Its check list is also stale relative to
<code>.github/required-checks.txt</code> (missing the three Windows legs,
<code>install-smoke</code>, <code>patch-coverage</code>, <code>codeql-analyze</code>) and it
pins <code>CodeQL</code> from the code-scanning app rather than the workflow job.

The safe move is one edit that does all of it: fix the pattern, drop
<code>required_deployments</code>, and reconcile the contexts with the checked-in list — or
delete the ruleset outright and keep the legacy protection as the single mechanism. Two
overlapping systems is how this stayed invisible.

<b>Shipped — repaired in a single write</b>, so it never existed in the deadlocking state:
pattern corrected to <code>refs/heads/main</code>, <code>required_deployments</code> removed,
and the status-check list replaced with the 17 contexts from
<code>.github/required-checks.txt</code> (dropping the code-scanning <code>CodeQL</code>
entry in favour of the <code>codeql-analyze</code> workflow job the checked-in list names).
Verified after: <code>/rules/branches/main</code> returns <b>7</b> rules, and
<code>/rules/branches/%22main%22</code> returns <b>0</b>. Confirmed against all three open
pull requests beforehand that every one of the 17 contexts actually reports — including a PR
touching only <code>.github/</code> — so the tightened list cannot deadlock. One API wrinkle
worth recording: <code>GET</code> returns <code>code_coverage.max_coverage_drop: null</code>
but <code>PUT</code> rejects it ("data matches no possible input"), so round-tripping a
ruleset requires stripping null-valued parameters.
