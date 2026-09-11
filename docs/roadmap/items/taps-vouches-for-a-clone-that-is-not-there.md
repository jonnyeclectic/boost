---
id: taps-vouches-for-a-clone-that-is-not-there
board: code
section: internals
status: planned
category: CLI · Bug
complexity: S
impact: Medium
wow: 3
note: boost taps prints item counts and an UPDATED date for a tap whose clone was deleted
order: 312
owner:
pr:
title: "<code>boost taps</code> vouches for a clone that is not there"
---
<code>boost taps</code> reads the per-tap catalog cache, and
<code>catalog.load_tap</code> deliberately serves a stale cache when the clone is gone
(rescanning is only possible while the clone exists &mdash; making the missing clone an
error there would trade a missing field for a missing catalogue). The consequence
reaches the readout unlabelled: a tap whose clone has been deleted still prints its
<code>NAME</code>, an <code>ITEMS</code> count and an <code>UPDATED</code> date, and the
footer still counts it in <em>&ldquo;N taps &middot; N items&rdquo;</em>. Nothing on the
line says the clone is missing.

Measured on a scratch <code>BOOST_HOME</code>: after deleting the clone directory,
<code>boost taps</code> printed <code>probe-src &nbsp;1&nbsp; 2026-09-10</code> and
<em>&ldquo;1 taps &middot; 1 items&rdquo;</em> &mdash; while <code>boost doctor</code>
exited 1 with <em>&ldquo;! tap &lt;x&gt; not cloned&rdquo;</em>. Two readouts of the same
machine, one of which is wrong, and the wrong one is the command whose entire job is to
describe the taps.

It is the same shape as the pin bugs in
<code>audit-pinned-taps-silently-moved-to-head-by-update-re-clone-and-co</code>: a
readout that keeps vouching for state the clone no longer has. The precedent is in
the tree: <code>boost list</code> carries a <code>FLAGS</code> column for exactly this
reason, and <code>info.py:239-241</code> states it &mdash; <em>&ldquo;so a quarantined or
pinned rule/workflow doesn't render byte-identical to a healthy one &hellip; a reader
needs to see that here, not just in --json&rdquo;</em>. Its values are
<code>pinned</code> and <code>quarantined</code>; a tap with no clone is the same class of
fact about a different table. Fix: <code>taps</code> already has
<code>tap.is_cloned</code> in hand, so mark the row and keep the footer counts honest,
rather than leaving <code>doctor</code> as the only command that knows.
