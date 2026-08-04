---
id: mcp-search-hid-which-ranking-ran
board: code
section: internals
status: shipped
category: Correctness · MCP
complexity: S
impact: Medium
wow: 4
note: the degraded order was byte-for-byte the shape of the promised one
order: 101
owner: fix/mcp-search-names-its-ranker
pr: 461
title: boost_search never said which ranking produced its answer
---
<b>The MCP tool tells an agent an LLM reranks every match, "which is what makes the top result worth
acting on rather than skimming ten". When no AI is configured, it doesn't &mdash; and the reply looked
exactly the same.</b> Ten lines, same shape, same confidence, produced by BM25 alone. An agent acts on
the top result because the description told it to.

<b>The signal existed and was thrown away.</b> <code>rag.search</code> returns
<code>(hits,&nbsp;ranker_label)</code>, and <code>rag.rerank</code>'s own docstring says why the label
matters: "the label is the only signal about which engine answered, so a confident
<code>BM25 full-content</code> sent debugging somewhere else." The MCP handler unpacked it into
<code>_ranker</code> and dropped it on the floor. Every degrade path &mdash; no AI available, a reply
that isn't a JSON array &mdash; already returns the retrieval label rather than claiming a rerank, so
the distinction was fully computed and merely unreported.

<b>This is not hypothetical on a normal machine.</b> The rerank needs
<code>ANTHROPIC_API_KEY</code> or the <code>claude</code> CLI. A boost installed with
<code>pipx</code> has neither inside its venv unless the key is exported, so the silent path is the
common one rather than the edge case.

<b>What shipped.</b> The reply now ends with the ranking that produced it &mdash;
<i>"(ranked by Claude relevance)"</i> when the rerank ran, and otherwise a line naming the engine,
saying plainly that the rerank <i>did not</i> run, and telling the caller to treat the order as a
shortlist to read rather than a verdict to act on. <code>rag.LLM_RANKER</code> replaces the literal
so the producer and the consumer of that label cannot drift apart, with a test driving
<code>rerank</code> through all three of its outcomes.

<b>A related claim was already corrected upstream.</b> The "95% against 79%" figures once quoted here
were removed from both the tool description and the server instructions, because 0.791 was the BM25
baseline over the <i>six</i>-repo corpus and the twenty-repo corpus that replaced it measures 0.4725
&mdash; overstating the baseline by 31 points. The mechanism claim survived that edit, which is
exactly the claim this card makes honest.
