---
id: audit-taps-findings
board: code
section: dx
status: inflight
category: CLI · UX
complexity: S
impact: Low
wow: 1
note: one UPDATED column shows "@b29e7cf", "2026-07-24" and "11h ago" with no legend
order: 296
owner: loop/taps-updated-column
pr:
title: "boost taps: CLI audit findings (2026-08)"
---
<b>The UPDATED column mixes <code>@sha</code>, ISO dates and relative times, unexplained</b> (low).
One real table reads <em>&ldquo;anthropics/skills&nbsp;18&nbsp;2026-07-24&rdquo;</em>,
<em>&ldquo;0xfurai/&hellip;&nbsp;138&nbsp;11h ago&rdquo;</em>,
<em>&ldquo;NeoLabHQ/&hellip;&nbsp;92&nbsp;@555b952&rdquo;</em> &mdash; three formats under one header
and nothing saying <code>@sha</code> means pinned. The rendering is half-deliberate: the comment at
<code>taps.py:248-251</code> says a pinned tap &ldquo;should say why on the line the user is already
reading&rdquo;, but nothing actually says why; and <code>_tap_updated</code>
(<code>taps.py:208-221</code>) emits git dates for cloned taps but <code>rel_time</code> for
cache-only taps, two formats by accident. Verification found it broader than the audit stated:
<code>taps --json</code>'s <code>updated</code> field mixes the same two time formats, so scripts get
an unparseable field too.

Fix: print a dim footer in <code>cmd_taps</code> whenever any row is pinned
(<code>@sha = pinned; boost update skips it</code>), and make <code>_tap_updated</code>'s cache
fallback return the <code>generated</code> date instead of <code>rel_time</code> &mdash; one format,
which also fixes the <code>--json</code> field. No doc changes.

Found by the 2026-08 CLI audit (cluster <code>taps-updated-column</code>); repro in the audit log.
