---
id: mcp-search-cost-was-understated
board: code
section: dx
status: shipped
category: Interop · Adoption
complexity: S
impact: Medium
wow: 2
note: the instructions claimed a second; it is twelve
order: 76
owner: 
pr: 
title: The MCP instructions understated what a search costs by 100x
---
<a href="#mcp-one-benefit-nameable-task">The nameable-task rewrite</a> gave the MCP
server a stated cost, on the reasoning that an unknown-price call with an unknown hit
rate gets skipped. That reasoning still holds. The number was wrong: <em>"Both are
read-only, take about a second, and install nothing."</em> Measured against the real
path, <code>boost_list</code> is instant but <code>boost_search</code> runs
<b>11.7&ndash;17.0&nbsp;s</b> (median ~12) against <b>0.10&nbsp;s</b> with the rerank
off &mdash; because <code>rag.search</code> defaults <code>smart=True</code> and the MCP
tool called it bare, so every agent search spends an LLM call while the CLI makes a
human ask with <code>--smart</code>.
<b>Ship the cost, not a smaller one.</b> The fix is not to hide the latency: the rerank
is the largest measured quality lever in the retrieval stack. On the 91-query golden set
it moves <code>hit@1</code> from <b>0.791 to 0.945</b> &mdash; +14 net queries, against
the ~6-query floor for <em>p</em>&lt;0.05 at this <em>n</em>. For scale, full-content
BM25 beat the old frontmatter search by +0.077, and dense retrieval tied BM25 exactly at
0.000. An agent acts on the top result rather than scanning ten, so it is the caller for
whom those seconds are most clearly worth paying. The instructions now separate the two
tools (<code>boost_list</code> instant, <code>boost_search</code> a few seconds) and say
what the seconds buy, because a wrong cost in the one paragraph whose job is to make the
tool worth reaching for discredits everything around it &mdash; and an agent that
budgeted a second gets a surprise instead of a decision.
<b>The default is now written down.</b> <code>smart=True</code> is passed explicitly at
the MCP call site with the measurement in a comment. It was previously inherited from
<code>rag.search</code>'s signature, which meant the most expensive behaviour in the
tool was an accident nobody had chosen and nobody could find. Same asymmetry as before,
but now it is a decision someone can revisit.
<b>What is still unmeasured:</b> the lift is over <em>raw BM25</em>, the pipeline that
stopped shipping when RRF fusion landed. Whether it survives over the fused ranking
needs the arm that
<a href="#keyless-semantic-search-for-everyone">step 6</a> is already committed to.

<b>Shipped in <code>#391</code></b> (<code>6dc1600</code>, &ldquo;state what a search really costs,
and choose the default&rdquo;). The card sat at <code>inflight</code> after the PR merged, which is
the failure mode a claimed item has: nothing re-checks a status once the work lands, so the board
kept advertising work that was already done.

