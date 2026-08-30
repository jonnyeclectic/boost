---
id: dense-reindex-has-no-progress-or-durability
board: code
section: internals
status: next
category: Observability · UX
complexity: M
impact: High
wow: 3
note: 5 h 33 m of silence, 18.26 GB RSS, nothing on disk
order: 125
owner:
pr:
title: "<code>reindex --dense</code> runs for hours behind a bare spinner, and a cancel discards all of it"
---
A keyless <code>boost reindex --dense</code> on a 465-tap / <b>63,003-entry</b> install ran
<b>5&nbsp;h&nbsp;33&nbsp;m</b> and emitted exactly one thing the whole time:
<code>⠏ embedding chunks into the dense store</code>. Nothing on the machine could answer
&ldquo;how far along is it, and should I cancel?&rdquo; &mdash; three independent reasons, each
separately fixable.

<b>(1) The loop is holding the numbers and never prints them.</b> <code>_embed_and_store</code>'s
batch loop (<code>dense.py:781</code>) has <code>start</code> and <code>len(order)</code> in scope
&mdash; precisely the pair <code>spin.progress(current, total, label)</code> takes.
That helper already exists in <code>boost_cli/spin.py</code>, is already TTY-gated so piped, CI and
test output stay clean, and already has a caller <em>one module over</em> at
<code>discovery.py:478</code>. So this is a one-line call into shipped, exercised code, not new
machinery.

<b>(2) <code>--debug</code> is a dead end on this path.</b> <code>dense.py</code> never constructs a
logger, so <code>--debug</code>, <code>BOOST_DEBUG=1</code> and <code>BOOST_LOG_LEVEL=DEBUG</code>
all produce the same bare spinner. <code>~/.boost/logs/boost.log</code> records <code>invoke:</code>
and <code>done:</code> and nothing in between &mdash; which for a six-hour command is the one
interval that matters.

<b>(3) The store cannot serve as a proxy either, and that is the deeper defect.</b>
<code>_embed_and_store</code> accumulates every vector into the <code>vec_of</code> dict and inserts
nothing until the final batch returns (<code>dense.py:802</code>); <code>build()</code> then commits
<b>once</b>, at <code>dense.py:535</code>. Measured across the entire run:
<code>rag_vectors.sqlite</code> sat at <b>24,924,160 bytes</b> with its mtime unchanged and no
<code>-journal</code> beside it. A user watching the file sees a dead process.

The only thing that actually worked was reading the live frame:
<code>sudo py-spy dump --pid &lt;pid&gt; --locals</code> &rarr; <code>start: 361216</code>. The
<code>--locals</code> is load-bearing; a plain <code>dump</code> gives the function but not the
position. From that one number: <b>361,216 distinct texts in 20,006 s = 18.1/s</b>, on
<b>1 of 18 cores</b>, at <b>18.26 GB RSS</b> of 48 GB &mdash; <code>vec_of</code> grows
monotonically and is never drained.

<b>And <code>start</code> alone is still not an answer, which is the sharpest form of the bug.</b>
A numerator without its denominator is not progress. <code>len(order)</code> is <em>not</em>
printable from a py-spy dump, so establishing it meant re-deriving boost's own chunking over all 465
cached catalogs out-of-process: <b>647,597 chunks spanning 390,978 distinct texts</b> (39.63%
duplicates) from <b>62,041 entries across 457 fresh taps</b>. Only then does
<code>start: 361216</code> resolve to <b>92.4% complete, ~27 min remaining</b>. Requiring a user to
reimplement the chunker to read a percentage is the whole defect in one sentence &mdash; and the
process already had both numbers in the same stack frame the entire time.

<b>What the opacity actually costs.</b> Because the only commit is at the end, Ctrl-C rolls the whole
transaction back; and <code>build()</code> records per-tap commits only <em>after</em>
<code>_embed_and_store</code> returns, so a cancelled run records nothing and a re-run re-embeds from
zero. The user is therefore asked to bet five and a half hours of CPU on a guess about whether a
spinner is stuck. That is the real bug &mdash; the missing progress line is how it reaches them.

<b>Fix, smallest first.</b>
<b>(a)</b> <code>spin.progress(start, len(order), "embedding chunks")</code> in the batch loop.
<b>(b)</b> A <code>logger.debug</code> per batch, so <code>--debug</code> leaves a trail a bug report
can carry.
<b>(c)</b> Stream rather than accumulate &mdash; embed a batch, insert it, commit every N &mdash;
which bounds peak RSS instead of letting it reach tens of GB, and makes a cancel cost one batch
rather than the whole run.
<b>(c) is what makes (a) worth trusting</b>: a progress bar over work that evaporates on Ctrl-C is
still a bad deal. Note (c) has to keep the current failure semantics &mdash; a tap whose batch the
provider rejected must still not get a recorded commit, or one transient failure leaves that tap
permanently marked built and empty.
