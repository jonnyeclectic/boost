---
id: the-links-concurrency-cap-did-not-hold
board: code
section: internals
status: shipped
owner: loop/links-remap
pr: "984"
category: CI · Flake
complexity: S
impact: Medium
wow: 3
order: 351
title: Capping the burst did not stop the 503s — the whole fetch was signal-free
note: 474 requests to one host, and --accept already takes 403, so the only verdict the live fetch could give that a file check cannot is 404.
---
<b>The previous fix did not hold.</b>
<code>links-job-503s-its-own-write-up-links</code> (#966) capped lychee at
<code>--max-concurrency 8</code> on the theory that the burst was the whole problem. Run
<code>36393345706</code>, the push that landed #981 on <code>main</code>, still lost <b>8</b>
write-up URLs to <code>[503] Service Unavailable</code> under that cap. Every roadmap item
regenerates <code>docs/roadmap.html</code>, so every merge out of the roadmap loop rolled the
dice again: the loop's own output was reddening <code>main</code>.
<br><br>
<b>The right question was what the fetch proves, not how fast it runs.</b> The boards emit a
<code>blob/main/docs/roadmap/items/&lt;id&gt;.md</code> link per settled card — <b>474</b> of
the 483 <code>github.com</code> links in the docs. That URL is derived mechanically from a path
in the very commit being checked, and <code>--accept</code> already takes <code>403</code>, so
a live fetch cannot even tell an inaccessible repo from a reachable one. <b>404 is the only
verdict it discriminates</b>, and the <code>file://</code> check the pull-request path already
used gives that one identically. The guard was paying 474 requests at one host for no signal.
<br><br>
<b>Fixed by making the remap unconditional.</b> Dropping
<code>github.event_name == 'pull_request' &amp;&amp;</code> takes the docs from 483 same-host
fetches to 9 on every event. A write-up URL that does <i>not</i> match the prefix — a card
pointing into the wrong directory — is still fetched for real, so a typo outside the remap is
caught as before, and one inside it fails as <code>File not found</code>.
<code>503</code> stays out of <code>--accept</code>: accepting it was always the cheap non-fix,
and <code>test_a_503_is_still_a_failure</code> still says so. The test that pinned the old rule
is inverted, and a new one asserts what actually replaced the burst — that <b>every</b>
write-up link both boards emit matches the remap pattern, since a cap only makes a burst
slower whereas a remap removes it.
