---
id: links-job-503s-its-own-write-up-links
board: code
section: internals
status: shipped
owner: loop/ci-summary-coverage-gate
pr: ""
category: CI · Flake
complexity: S
impact: Medium
wow: 2
order: 349
title: The links job fetches 467 URLs from one host at once and GitHub 503s a random handful
note: Three attempts of one run failed on three disjoint sets of URLs, every one of which returns 200 on its own.
---
<b>Found by watching the train release land.</b> The <code>links</code> job went red on
<code>main</code> three attempts running after #963 merged, each time with a different set of
<code>[503] Service Unavailable</code> rows — 2 URLs, then 1, then 4, nine attempts' worth of
evidence pointing at no single broken link. All seven return <code>200</code> fetched one at a
time, and every target file is present on <code>main</code>.
<br><br>
<b>It is the burst, and it is a consequence of a deliberate rule.</b> The boards emit a
<code>blob/main</code> link to the write-up of every settled card — 467 of them, all on
<code>github.com</code>. On a pull request those are remapped to the checkout
(<code>--remap</code>, so a card filed as shipped does not 404 before it merges); on a push they
are <b>not</b>, because <code>main</code> is where the published link is proved to work
(<code>test_only_pull_requests_are_remapped</code> pins that on purpose). lychee's default
concurrency is 128, so a push is 467 requests to one host as fast as the runner can issue them, and
GitHub sheds some of them.
<br><br>
<b>Fixed.</b> <code>--max-concurrency 8 --retry-wait-time 5</code>. That keeps the real check —
<code>main</code> still fetches the published URLs — and removes the burst that makes GitHub refuse
them. <code>503</code> stays out of <code>--accept</code>: accepting it is the cheap non-fix, and it
would turn a genuine outage into a green run. Two tests in
<code>tests/unit/test_roadmap_fresh.py</code> hold both halves, beside the remap tests they belong
with, and the cap is asserted against the number of same-host links it has to survive rather than
as a bare number.
