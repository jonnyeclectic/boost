---
id: codeql-job-rename-stranded-merge-protection
board: code
section: trust
status: shipped
category: CI · Bug
complexity: S
impact: High
wow: 4
note: a job rename forked the code-scanning config and blocked 100% of merges for a day
order: 37
owner: loop/codeql-analysis-key-guard
pr:
title: A CodeQL job rename silently blocked every merge
---
GitHub identifies a code-scanning configuration by <code>&lt;workflow path&gt;:&lt;job id&gt;</code>, which makes
the job id load-bearing in a way nothing in the workflow file hints at: renaming it does not
<i>move</i> the configuration, it <b>forks</b> it. #259 renamed this job <code>analyze</code> to
<code>codeql-analyze</code> on 2026-07-27. The last <code>:analyze</code> analysis landed 20 seconds
after that merge and never refreshed, stranding <b>247</b> of them on <code>refs/heads/main</code>
where GitHub kept counting them as a configuration present on the base branch. Merge protection
then reported <code>1 configuration not found</code> on every pull request — conclusion
<code>neutral</code> — and because the branch ruleset carries a <code>code_scanning</code> rule,
that neutral <b>blocked 100% of merges</b> while every required status check stayed green.
The cutover is exact: the last <code>success</code> was #263, the first <code>neutral</code> #259,
and every PR from #264 to #316 was neutral regardless of whether its diff contained Python at all.
That symmetry is what makes it so easy to misread — it presents as a rule that rejects docs-only
PRs, and the two hypotheses it invites (<i>"CodeQL has nothing to analyse"</i> and <i>"the rule is
unsatisfiable"</i>) are both wrong. 29 docs-only PRs merged happily under the same rule before the
rename. The check body says the real answer outright, and reading it beats inferring from
<code>mergeable_state</code>. Fixed by deleting the 247 orphaned analyses, which was verified safe
first: every alert still on the stale key was <code>fixed</code>, and all nine dismissed CodeQL
alerts already carried their false-positive rationale on the live key. The job id was <i>already</i>
guarded as a required status-check context by
<code>scripts/check_required_checks.py</code>, and that guard passed during #259 because the
context list was updated in the same commit — only the invisible half broke. So the guard added
here pins the id from the analysis-key side, with a note that a future rename is not finished until
the stale configuration is deleted. Related: [[release-verifies-the-wrong-commit]].
