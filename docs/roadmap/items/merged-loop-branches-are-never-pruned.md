---
id: merged-loop-branches-are-never-pruned
board: code
section: pipeline
status: planned
category: Hygiene · DX
complexity: S
impact: Low
wow: 2
note: 68 of 70 loop/* branches have a merged PR; one setting fixes it
order: 66
owner:
pr:
title: 68 of the repo's 77 branches are merged <code>loop/*</code> branches nobody deletes
---
The repository carries <b>77 branches, 70 of them <code>loop/*</code></b>. Classifying each by the
state of its pull request: <b>68 have a merged PR</b> and are safe to delete, <b>1</b> has an open
PR (<code>loop/dependabot-findings</code>), and 1 has no PR on record. The default branch list is
almost entirely finished work.

<b>The obvious measurement is wrong here, which is worth recording.</b> Testing "is it merged?"
with <code>compare(main...branch).ahead_by == 0</code> reports <b>0 of 70</b> as merged &mdash;
because this repo squash-merges, and a squash leaves the branch's original commits outside
<code>main</code>'s history forever. Every merged branch looks permanently ahead. The state has to
come from the pull request, not from commit reachability.

The cause is a single repository setting: <code>delete_branch_on_merge</code> is <b>false</b>, so
nothing removes a head branch when its PR merges. No workflow prunes them either &mdash; none of
the 25 workflow files triggers on <code>create</code>/<code>delete</code> or touches
<code>loop/*</code>, and no <code>scripts/</code> entry or Makefile target does branch cleanup.
The one branch-deletion automation in the tree is <code>demo.yml</code>'s
<code>delete-branch: true</code>, which is <code>create-pull-request</code> tidying its own
<code>bot/demo-gif</code> branch and has nothing to do with <code>loop/*</code>. No documentation
asks anyone to clean up either: <code>CONTRIBUTING.md</code>, <code>CLAUDE.md</code> and
<code>.claude/commands/roadmap-loop.md</code> all describe branching and squash-merging, and none
of the three mentions deleting the branch afterwards.

<b>Not a claim that branches are never deleted.</b> The item files name <b>144 distinct</b>
<code>owner: loop/&lt;topic&gt;</code> values against 70 surviving branches, so roughly 98 have
gone at some point &mdash; by hand, or by topic reuse. The accurate statement is narrower:
nothing in the repo <em>causes</em> cleanup, so merged branches accumulate until someone does it
manually.

Low impact and near-zero risk to fix &mdash; flip <code>delete_branch_on_merge</code> to true and
the backlog can be pruned by listing merged PR head refs. The reason it is worth doing at all is
that CLAUDE.md tells every agent to run <code>git worktree list</code> and inspect branch state
before touching a tree, and 68 stale entries make that check noisier for every concurrent loop.
