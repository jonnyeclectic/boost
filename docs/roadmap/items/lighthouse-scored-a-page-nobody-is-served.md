---
id: lighthouse-scored-a-page-nobody-is-served
board: code
section: docsite
status: shipped
category: Docs · Performance
complexity: S
impact: High
wow: 5
note: the page was never the slow part — the harness sent 3.27x the bytes Pages sends
order: 97
owner: fix/lighthouse-serves-uncompressed
title: The performance gate was measuring a page nobody is served
---
<b>The board's Lighthouse score was decided by a missing HTTP header.</b> The gate serves the docs
with <code>python3 -m http.server</code>, which has never sent <code>Content-Encoding</code>. GitHub
Pages answers <code>content-encoding: gzip</code> for the same URL &mdash; checked against the live
site. So every performance number this project has ever recorded for
<code>roadmap.html</code> was measured on a document <b>3.27&times;</b> larger than the one a visitor
receives.

<b>The failing run says so itself.</b> In its own artifact,
<code>uses-text-compression</code> scores <b>0</b> with an estimated saving of 404&nbsp;KiB, and
<code>transferSize</code> 567,874 sits against <code>resourceSize</code> 567,685 &mdash; the bytes on
the wire are the bytes on disk. Lighthouse throttles to <b>1,474.56&nbsp;kbps</b>, where 566&nbsp;KB
is <b>3.08&nbsp;s</b> of download; the observed FCP was <b>3.63&nbsp;s</b>. There is nothing left
over to explain.

<b>And the score decomposes exactly.</b> FCP&nbsp;3,638&nbsp;ms scores 0.31 (&times;10) &middot;
SI&nbsp;3,638&nbsp;ms 0.86 (&times;10) &middot; LCP&nbsp;3,858&nbsp;ms 0.53 (&times;25) &middot;
TBT&nbsp;100&nbsp;ms 0.98 (&times;30) &middot; CLS&nbsp;0 1.00 (&times;25), which totals
<b>79.35 &rarr; 0.79</b>, the reported figure to the digit. The entire 21-point deficit is FCP and
LCP. Both are transfer-bound. Neither is about the page.

<b>This is why two rounds of optimisation moved nothing.</b>
[[roadmap-perf-budget-has-no-local-guard]] records collapsing card bodies into
<code>&lt;details&gt;</code>, which cut laid-out body text 33% and moved the score by <b>0.00</b>,
and trimming 3,066 characters of prose, which also moved it by <b>0.00</b>. Both changed
<i>layout</i> work while the score was being decided by <i>transfer</i>. <code>content-visibility:
auto</code> bought 0.01 &mdash; about all that was on the table, because TBT already scored 0.98.
The conclusions drawn from those experiments were sound about what they measured and wrong about
what they implied: the floor was lowered 0.85&nbsp;&rarr;&nbsp;0.80 and the raise back was declared
"gated on making the page genuinely faster", when the page was never the slow part.

<b>It also names the cheap local proxy that card called not obvious.</b> It is markup bytes &mdash;
the dimension <code>scripts/page_budget.py</code> already measures, shipped by the same PR that
declared the budget non-predictive. Compression is a near-constant factor here (roadmap.html 3.27&times;,
index.html 3.38&times;, boost.css 2.99&times;), so bytes on disk track bytes on the wire, and bytes on
the wire are what FCP is spending.

<b>What shipped.</b> <code>scripts/serve_docs.py</code> &mdash; a stdlib static server that
compresses exactly what Pages compresses (text, JS, JSON, XML, SVG; never images or fonts) and only
when the client asks, so the raw path stays reachable. On the audited page that is
<b>597,782&nbsp;&rarr;&nbsp;184,126&nbsp;B</b>, or <b>3.24&nbsp;s&nbsp;&rarr;&nbsp;1.00&nbsp;s</b> of
download on Lighthouse's link. Nothing else about the harness changed &mdash; not even HTTP/1.1
keep-alive, which was left off on purpose so the score move has one cause and not two.

<b>What it deliberately is not.</b> A way to make the number look better. It is the opposite: the
number now describes bytes someone is actually sent, so a floor raised against it means something.
Twenty-two unit tests pin the behaviour, including that HEAD and GET agree on
<code>Content-Length</code>, that an image is left alone, and that the rc's
<code>startServerReadyPattern</code> still matches the banner &mdash; a drift there does not fail the
job, it hangs it until timeout.
