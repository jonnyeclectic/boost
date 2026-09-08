---
id: audit-unpin-findings
board: code
section: dx
status: shipped
category: CLI · UX
complexity: S
impact: Low
wow: 1
note: unpin prints 'released the commit pin too' before the unpinned line it qualifies
order: 299
owner: loop/unpin-trailer-order
pr: 792
title: "boost unpin: CLI audit findings (2026-08)"
---
<b><code>unpin</code> prints its trailer before the line it qualifies</b> (low). After
<code>pin brainstorming --commit</code>, <code>unpin brainstorming</code> prints
<em>&ldquo;released the commit pin too&rdquo;</em> first and then
<em>&ldquo;&#10003; unpinned brainstorming (v0.0.0) &mdash; updates apply again&rdquo;</em> &mdash;
the dim note qualifies a line that has not appeared yet. <code>cmd_pin</code> shows the intended
order: main &#10003; line first, dim commit-pin trailer after. The cause is sequencing in
<code>cmd_unpin</code> (<code>pkg.py:1439-1449</code>): it prints the <code>out.dim</code> note
before calling <code>_set_pin(name, False)</code>, and <code>_set_pin</code>
(<code>pkg.py:1470-1477</code>) is what prints the main <em>unpinned</em> line.

Fix: call <code>_set_pin(args.name, False)</code> first, then print the commit-pin trailer,
mirroring <code>cmd_pin</code>'s order (<code>pkg.py:1421-1436</code>) &mdash;
<code>clear_commit_pin</code> can still run before; only the <code>out.dim</code> is deferred. No
doc changes.

Found by the 2026-08 CLI audit (cluster <code>unpin-trailer-order</code>); repro in the audit log.
