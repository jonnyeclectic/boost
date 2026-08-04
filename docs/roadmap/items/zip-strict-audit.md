---
id: zip-strict-audit
board: code
section: internals
status: shipped
owner: loop/zip-strict
pr: 463
category: Correctness
complexity: S
impact: Med
wow: 2
note: 16 call sites, each a judgement — a silent truncation or a new raise, never a mechanical fix
order: 92
title: audit the 16 <code>zip()</code> calls the 3.12 floor made checkable
---
The <code>&gt;=3.12</code> floor switched on ruff's <code>B905</code>
(<code>zip-without-explicit-strict</code>), which found <b>16</b> call sites. It is in the ignore
list with a rationale rather than fixed, and the rationale is the point: this is a real correctness
signal and <i>not</i> a mechanical fix.

<b>Why it matters.</b> <code>zip()</code> stops at the shortest input and says nothing. When two
sequences are meant to be the same length — a row and its header, an id list and the embedding
vectors it indexes — a mismatch silently drops the tail, and the result looks like a smaller answer
rather than a bug.

<b>Why it cannot be swept.</b> <code>strict=True</code> converts that silent truncation into a
<code>ValueError</code> at runtime. That is the right answer where the lengths are an invariant and
the wrong answer where the truncation is deliberate — so each site needs a decision, and picking
wrong in either direction is a behaviour change rather than a lint fix. ruff itself only offers the
rewrite under <code>--unsafe-fixes</code>.

<b>Where they are.</b> Nine files: <code>core/adapters.py</code> (4),
<code>commands/discovery.py</code> (2), <code>core/chat.py</code>, <code>core/dense.py</code>,
<code>core/output.py</code>, plus <code>evals/</code> (2) and <code>tests/unit/</code> (5). The five
in <code>core/</code> are the ones that matter — that is the mutation-gated engine, and
<code>dense.py</code>'s in particular pairs ids with vectors, which is exactly the shape where a
length mismatch would be silent and wrong.

Do it as one pass with a one-line justification per site, and prefer <code>strict=True</code>
wherever the lengths are an invariant: a raise that names the bug beats a short answer that hides it.
