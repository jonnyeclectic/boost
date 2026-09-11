---
id: compact-answers-a-named-tap-with-a-global-all-clear
board: code
section: internals
status: planned
category: CLI · Bug
complexity: S
impact: Medium
wow: 2
note: boost compact &lt;tap&gt; on an uncloned tap prints a green "no cloned taps to compact" and exits 0
order: 311
owner:
pr:
title: "<code>compact &lt;tap&gt;</code> answers a question about one tap with a global all-clear"
---
<code>cmd_compact</code> resolves its named taps and then filters
(<code>taps = [t for t in taps if t.is_cloned]</code>). A tap that is configured but has
no clone falls out of that list silently, so the empty-list branch fires and prints
<em>&ldquo;&#10003; no cloned taps to compact&rdquo;</em> with exit 0 &mdash; a green,
plural, global-sounding all-clear in answer to a question about one specific tap, which
it never names.

Reproduced on a scratch <code>BOOST_HOME</code>: tap a repo, delete its clone directory,
then <code>boost compact &lt;that-tap&gt;</code> &rarr; <code>rc=0</code>,
<em>&ldquo;&#10003; no cloned taps to compact&rdquo;</em>. Meanwhile
<code>boost doctor</code> exits 1 on the same machine and says
<em>&ldquo;! tap &lt;x&gt; not cloned &mdash; run <code>boost update</code>&rdquo;</em>,
so the information exists and this command is the one that withholds it.

This contradicts the convention <code>registry.update</code> states in its own docstring:
<em>&ldquo;A named tap still raises. <code>boost update sometap</code> is a request about
that one tap, so its failure is the answer to the question asked.&rdquo;</em> The sweep
form is right to stay quiet; the named form is not. Fix: when <code>args.tap</code> named
taps and the filter dropped some, say which and why, and point at
<code>boost update</code> the way <code>doctor</code> does &mdash; and do not report
success for a tap nothing was done to.
