---
id: roadmap-html-goes-stale-on-every-rebase
board: code
section: dx
status: planned
category: DX
complexity: M
impact: Med
wow: 3
note: hit twice on one PR in a single afternoon
order: 59
owner:
pr:
title: <code>roadmap.html</code> goes stale on every rebase, so a card and a merge race redden the whole matrix
---
The data-driven roadmap solved the conflict problem for <em>item files</em>: two loops adding
two cards touch two different files and merge cleanly. But <code>docs/roadmap.html</code> is
still a single committed artifact generated from <b>all</b> of them, and
<code>update-branch</code> merges it textually.

So whenever another roadmap-carrying PR merges first, the rebase brings in the new item
<code>.md</code> cleanly and leaves the generated HTML behind. The board no longer matches
<code>docs/roadmap/items/</code>, and both <code>build_roadmap.py --check</code> (in lint) and
<code>tests/unit/test_roadmap_fresh.py</code> fail — on <b>every</b> test leg, for a PR that
changed no Python at all. It reads as a catastrophic failure and is really a stale generated
file.

This is not hypothetical: one PR hit it twice in a single afternoon, each time needing a
manual regenerate-and-push, and the cost scales with the number of concurrent loops — the
exact workload the item-file split was introduced to support. With <code>strict: true</code>
every merge rebases every open PR, so any PR carrying a card is guaranteed to hit it if it
sits behind one other roadmap PR.

Options, roughly in order of appeal: have CI regenerate and push the board on the PR branch
(fixes it silently, needs a bot token and care with the required checks); a custom merge
driver for the generated boards that reruns the generator instead of merging text; or stop
committing the HTML and build the site at deploy time (biggest change, and it removes the
artifact from review). At minimum, make the <code>--check</code> failure message say
"regenerate after rebasing" so the cause is obvious from the log.
