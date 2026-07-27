---
id: ci-summary-step-fails-itself
board: code
section: pipeline
status: shipped
category: Bug
complexity: S
impact: Low
wow: 3
note: an always() step that exits 1 on its own
order: 54
owner: loop/ci-reporting-defects
pr:
title: <code>ci.yml</code>'s job summary could exit 1 on its own, under the <code>always()</code> it was given
---
The <code>job summary</code> step is marked <code>if: always()</code> so a run still reports
when something upstream died. Its last line was
<code>[ -n "$SMOKE" ] &amp;&amp; echo "- **Smoke suite:** ${SMOKE}"</code>, which is the final command
of the <code>{ ... } &gt;&gt; "$GITHUB_STEP_SUMMARY"</code> group, and that group is the final
command of the step. GitHub runs <code>shell: bash</code> as
<code>bash --noprofile --norc -eo pipefail</code>, so with <code>$SMOKE</code> empty the
AND-list's status of 1 becomes the group's status and then the step's exit code.

<code>$SMOKE</code> is empty precisely when <code>smoke.sh</code> never printed its
<code>== results:</code> line — an earlier step died first, or smoke never ran. That is the
exact scenario <code>always()</code> exists for, so the reporting step failed in the one case
it was written to survive. Reproduced directly: exit 1 with no match, exit 0 with one.

It never masked a real failure (the job is already red when this happens), but it planted a
second misleading red step, and would have silently reddened the job if that step were ever
moved into a green context. Replaced with an <code>if</code> block.
