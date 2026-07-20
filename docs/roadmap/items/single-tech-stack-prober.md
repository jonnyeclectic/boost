---
id: single-tech-stack-prober
board: code
section: internals
status: shipped
category: Tech-debt
complexity: M
impact: Med
wow: 2
note: prober moved to core
order: 13
owner: loop/core-stack-prober
pr: 140
title: Single tech-stack prober
---
Shipped in <b>#140</b>. The canonical <code>detect_stack</code> prober — a
~75-line pure function that lived in the <b>command</b> module
<code>commands/discovery.py</code> yet was imported across the command layer by
both <code>intelligence</code> and <code>quality</code> — now lives in one place:
a new pure core module <code>core/stackprobe.py</code> (with its private
<code>_SKIP_DIRS</code>/<code>_EXT_LANGS</code>/<code>_read_text</code> helpers,
used nowhere else). Every consumer imports the single core prober;
<code>discovery</code> re-exports it for compatibility, and the now-dead helpers
+ unused <code>os</code> import were removed from it. Covered by 16 new
mutation-gated unit tests. The consumer-local enrichment fallbacks
(<code>_local_stack</code>, <code>_STACK_MARKERS</code>) are intentionally kept —
they add coarse filesystem signal the language-only prober doesn't.
