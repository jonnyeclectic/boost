---
id: audit-update-findings
board: code
section: dx
status: planned
category: CLI · Performance
complexity: M
impact: Med
wow: 1
note: a no-op update over 20 taps takes ~14 s serial; --force drops 20 pins without a word
order: 301
owner:
pr:
title: "<code>boost update</code>: CLI audit findings (2026-08)"
---
<b>update pulls all taps serially with no progress indicator: ~14 s no-op over 20 taps</b> (med). A plain <code>update</code> over 20 taps with nothing to fetch took <b>13.93 s</b> under TTY (verifier re-measured 13.89 s), <code>update --force</code> 17.82 s; each line appears only after its ~0.7 s pull, nothing on screen between lines. <code>registry.update()</code> (<code>registry.py:465-525</code>) is a plain <code>for tap in targets:</code> loop calling <code>gitutil.pull</code>/<code>clone_shallow</code> serially &mdash; the exact latency-bound pattern <code>registry.add_many</code> already parallelises for clones. Fix: pull in a <code>ThreadPoolExecutor</code> mirroring <code>add_many</code>, keep catalog rebuilds and the single config write serial on the caller's thread, and print a <em>refreshing N taps&hellip;</em> line or spinner while pulls run.
<br><br>
<b>--force clears pins with no per-line notice; an all-pinned run claims &ldquo;everything up to date&rdquo;</b> (low). After <code>update --force</code>, <code>config.json</code> went from 20 <code>pin</code> keys to 0 with no line mentioning a pin &mdash; and the verifier's follow-up probe showed the cost: the next plain <code>update</code> fetched all 20 taps, 0.13 s &rarr; 13.32 s. Clearing on <code>--force</code> is deliberate (CLAUDE.md, <code>registry.py:518-522</code>); the silence is the defect &mdash; <code>registry.py</code>'s own comments call a silent state change &ldquo;the failure that looks like nothing at all&rdquo;. Separately, a fully pinned environment prints 20 &times; <em>&#10003; &lt;tap&gt;: pinned at &lt;sha7&gt; (skipped)</em> then <em>&#10003; everything up to date</em> in 0.13 s with zero network contact and no <code>--force</code> hint. Fix (verified recommendation): in <code>registry.update</code> append <code>(pin cleared)</code> to a tap's summary when force unpinned it; in <code>cmd_update</code> (<code>pkg.py:1080-1084</code>) count pinned skips, print a muted hint that <code>boost update --force</code> moves them and drops their pins, and word the trailer <em>nothing to refresh &mdash; all taps pinned</em> when nothing was checked. No doc changes needed. Found by the 2026-08 CLI audit (clusters <code>update-serial-pulls</code>, <code>pin-clearing-messaging</code>); repro in the audit log.
