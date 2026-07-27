---
id: post-deploy-always-defeated-by-skipped-setup
board: code
section: pipeline
status: shipped
category: Bug
complexity: S
impact: Med
wow: 4
note: the always() destroyed the signal it was written to preserve
order: 55
owner: loop/ci-reporting-defects
pr:
title: <code>post-deploy.yml</code>'s <code>always()</code> destroyed the second signal it existed to preserve
---
The console-health step carries <code>if: always()</code> with the comment
"an HTTP failure above must not hide a console failure here — they are different breakages
and both belong in one report". But the two steps it depends on —
<code>actions/setup-node</code> and the <code>npm install</code> that fetches puppeteer — had
<b>no <code>if:</code> at all</b>. A failure in the HTTP smoke skips both, so the console
check then runs with no <code>node_modules</code> and produces an environment error rather
than a console verdict.

The run history separates the two cleanly: an environment error exits <b>2</b>, a genuine
console failure exits <b>1</b>. Run 30214061945 has
<code>HTTP smoke = failure, setup-node = skipped, npm = skipped, console = failure (exit 2)</code>,
while the four runs where the npm install actually happened all exit 1. So in exactly the
case the <code>always()</code> was written for, the second signal was destroyed instead of
preserved — and the report said "console check failed" when it meant "the console check
never ran".

Fixed by putting <code>always()</code> on the setup steps too, so the dependency chain the
final step needs survives the failure it is meant to outlive.
