---
id: a-new-shipped-card-always-404s-its-own-write-up-link
board: code
section: pipeline
status: planned
category: CI · Bug
complexity: S
impact: Medium
wow: 3
note: the links check goes red on every correct PR that files a new card as shipped, and green again on merge
order: 313
owner:
pr:
title: "A new card filed as <code>shipped</code> always 404s its own write-up link"
---
<code>build_roadmap.py</code> renders a settled card's body as a link to the item file on
<b><code>main</code></b> &mdash; <code>ITEMS_URL</code> (line 206) is
<code>https://github.com/jonnyeclectic/boost/blob/main/docs/roadmap/items</code>, and
<code>_body_html</code> emits it for any status in <code>_SETTLED</code>. The
<code>links</code> job runs on <code>pull_request</code> over
<code>docs/*.html</code>. So a PR that files a <em>new</em> card at
<code>status: shipped</code> renders a link to a file that does not exist on
<code>main</code> yet, and lychee rejects it 404 &mdash; on a PR where nothing is wrong.
It goes green by itself the moment the PR merges.

Observed on PR <code>#845</code>, whose 22 required checks were all green:
<em>&ldquo;[404] &lt;&hellip;/blob/main/docs/roadmap/items/reclone-leaves-a-clone-on-head-when-it-cannot-reach-the-pin.md&gt; (at 4125:54) | Rejected status code: 404 Not Found&rdquo;</em>.
The mechanism is deterministic from the three sources above rather than inferred from that
one run: any new item file whose first committed status is settled hits it. Cards that were
already on <code>main</code> and merely change status do not, which is why this went
unnoticed &mdash; the usual shape is claim-then-ship across two PRs.

It matters because the remedy people reach for is the wrong one: either the card gets
filed at a status that misdescribes it to keep CI quiet, or a check that is right about
everything else gets learned as noise. <code>links</code> is advisory rather than
required, which caps the damage and is also what lets it rot unnoticed. Options, cheapest
first: resolve the link against the <em>head</em> ref in CI
(<code>GITHUB_HEAD_REF</code>) and <code>main</code> elsewhere; or let lychee treat a
<code>blob/main</code> URL whose path exists in the working tree as satisfied; or link the
raw file relatively and accept that GitHub Pages serves <code>.md</code> as a download
rather than rendered Markdown &mdash; which is the reason the absolute URL was chosen, so
that one is a trade, not a fix.
