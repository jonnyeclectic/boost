---
id: code-scanning-rule-can-be-restored
board: code
section: trust
status: shipped
category: Release safety
complexity: S
impact: Med
wow: 4
note: safe scoped to CodeQL (0 open) — adding Scorecard deadlocks every merge
order: 54
owner:
pr:
title: The <code>code_scanning</code> ruleset rule can go back on &mdash; but only scoped to CodeQL
---
Repairing the <code>main</code> ruleset dropped its <code>code_scanning</code> rule in favour of
<code>codeql-analyze</code> as a required status check (see
<code>main-ruleset-ref-pattern-has-literal-quotes</code>). That was the safe call at the time, and
it left an open question: can the rule come back? <b>Yes &mdash; and the thing that would break it
is not what it looks like.</b>

<b>Nothing is blocking it.</b> Verified without touching the live ruleset: POST a throwaway
ruleset with <code>enforcement: disabled</code> and a ref pattern matching no branch, carrying
<code>code_scanning</code> for tool <code>CodeQL</code> &rarr; <b>HTTP 201</b>, rule stored intact.
Delete it, then diff the live ruleset against a backup taken beforehand &rarr; no drift. That
disabled-and-non-matching probe is the general way to test a ruleset change without risking
anyone's in-flight pull request.

<b>The stale analyses are a red herring.</b> 693 analyses still carry the old
<code>codeql.yml:analyze</code> category against 122 on the current <code>codeql-analyze</code>,
which looks like it should matter and does not: the rule keys on <b>tool name</b>, not category.
Deleting them is irreversible, destroys alert history, and fixes nothing. Don't.

<b>The actual hazard is the tool list.</b> Three tools file into the same code-scanning inbox.
CodeQL has <b>0 open</b> alerts (9 dismissed, 17 fixed). Scorecard has <b>7 open, every one
<code>severity=error</code></b> &mdash; and they are posture metrics that must not be dismissed,
so they will stay open. Enabling the rule with Scorecard in its tool list therefore blocks
<em>every merge in the repository, immediately</em>. The GitHub UI offers every tool that has
reported analyses, so Scorecard sits right next to CodeQL in the picker. That is almost certainly
why this has been assumed to be blocked.

Scoped to CodeQL alone it is safe and adds real protection: <code>codeql.yml</code> carries no
path filters and runs on <code>push</code>, <code>pull_request</code> and
<code>merge_group</code>, so it always reports and cannot produce the never-reports deadlock this
repo has hit twice. And it catches something the status check does not &mdash;
<code>codeql-analyze</code> passes when the <em>job</em> succeeds, including when it succeeds
having found error-severity alerts.

<b>Done &mdash; the rule is back, and scoped exactly as this card prescribed.</b> Read from the live
<code>main</code> ruleset (id <code>19130332</code>): it carries a <code>code_scanning</code> rule
whose <code>code_scanning_tools</code> list is <b><code>CodeQL</code> alone</b>, at
<code>security_alerts_threshold: high_or_higher</code> and <code>alerts_threshold: errors</code>.
Scorecard is not in the list, which is the single decision this card exists to get right.

The safety precondition still holds and was re-checked rather than assumed: <b>CodeQL has 0 open
alerts</b>, while Scorecard has <b>4 open</b> (down from the 7 recorded above), every one still a
posture metric that must not be dismissed. Had Scorecard been added to that tool list, those four
would block every merge in the repository immediately &mdash; the failure mode this card correctly
identifies as the reason the work looked blocked.

No change was needed. Recording it as shipped so the board stops advertising work that is already
in place, and so the tool-list constraint stays written down: anyone re-editing this rule through the
GitHub UI will be offered Scorecard right next to CodeQL in the picker.
