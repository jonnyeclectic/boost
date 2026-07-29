---
id: roadmap-html-goes-stale-on-every-rebase
board: code
section: dx
status: shipped
category: DX
complexity: M
impact: Med
wow: 3
note: two of the three fixes measured dead; one survivor, and it needs a Pages change
order: 59
owner: loop/roadmap-stale-diagnosis
pr: 307
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
<b>Update 2026-07-29 — the three options were measured, and two of them do not work.</b>
First, the repro, because both halves matter and they fail differently. Two branches each
adding one item to the same section: the <em>cards</em> hard-conflict (same insertion point),
while the <em>counters</em> merge silently to a wrong value — base <code>N</code>, both sides
<code>N+1</code>, git keeps <code>N+1</code>, the truth is <code>N+2</code>. So a clean merge
still fails <code>--check</code>. That is why one root cause reddens ~6 checks.
<b>"Custom merge driver" is dead.</b> GitHub's server-side merge ignores
<code>.gitattributes</code> merge strategies — not just custom drivers, the built-in ones too.
Measured on this repo with four throwaway branches and
<code>POST /repos/&hellip;/merges</code>: <b>409 without</b> the attribute and <b>409 with</b>
<code>docs/roadmap.html merge=union</code>, while the identical merge <em>locally</em> succeeds
cleanly and one <code>build_roadmap.py</code> run makes it correct. The attribute would help
only whoever resolves the conflict by hand, which is the case that already works.
<b>"CI regenerates and pushes on the PR branch" is dead too</b>, at least with
<code>GITHUB_TOKEN</code>: a push made with it deliberately does not trigger workflows, so the
fix-up commit would land a new head with <b>no check runs at all</b> and the required contexts
would never report — the PR blocks forever instead of for one cycle. It needs a PAT or a GitHub
App, i.e. a new long-lived secret with write access to every branch.
<b>The survivor is the third one</b> — stop committing the generated HTML and build the site at
deploy time — and it has a prerequisite that is a repository <em>setting</em>, not a commit:
Pages is currently <code>build_type: legacy</code> serving <code>main:/</code>, so it publishes
whatever bytes are committed. The artifact cannot leave git until Pages builds it, which means
either an Actions-built site or a generated <code>gh-pages</code> branch (the pattern
<code>ci.yml</code> already uses for the coverage badge, and one that does <b>not</b> re-trigger
<code>ci</code> → <code>publish</code>, so it cuts no extra release). Everything that reads
<code>docs/*.html</code> off disk — <code>html-validate</code>, <code>visual</code>,
<code>lighthouse</code>, <code>check_anchors</code>, <code>a11y_check</code>,
<code>test_docsite_chrome</code> — would need a generate step first, and
<code>test_roadmap_fresh</code> loses its purpose. That is the whole cost, and it is bounded;
what it is not is a change one loop should make to a live public site on its own initiative.
