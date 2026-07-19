---
id: atomic-corruption-safe-lock-file-writes
board: code
section: shipped
status: shipped
category: Correctness · Robustness
complexity: M
impact: High
wow: 4
note: already fixed in #65
order: 1
owner: loop/roadmap-hygiene-stale-cards
pr: 65
title: Atomic, corruption-safe lock-file writes
---
Shipped in <b>#65</b> (this card lingered as "next" after the fact).
<code>core/lockfile.py</code> now writes through <code>util.atomic_write_text</code>
(temp file + <code>os.replace()</code>) and <code>read()</code> tells "empty"
apart from "corrupt": an unparseable lock is preserved as <code>&lt;lock&gt;.corrupt</code>
and surfaced loudly rather than silently overwritten, so an interrupted or
concurrent write can no longer drop every prior install record.
