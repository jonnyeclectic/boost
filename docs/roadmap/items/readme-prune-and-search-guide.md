---
id: readme-prune-and-search-guide
board: code
section: health
status: inflight
category: Docs · Onboarding
complexity: S
impact: Med
wow: 2
note: 609 → 399 lines; 75 em dashes → 2; a real semantic-search guide
order: 9
owner: loop/docs-voice
pr:
title: The README read like a machine wrote it — measurably
---
The README had grown to <b>609 lines and 3,687 words of prose</b>, and it was carrying
reference material nobody reads on a landing page: the whole semantic-search setup, the whole
BMAD surface, the eval harness in full. Both are now their own pages and the README links to
them, which took it to <b>399 lines and 2,009 words</b>.
<b>The "does this read like AI" question turned out to be measurable</b>, which is more useful
than an opinion. Audited against
<a href="https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing">Wikipedia's signs-of-AI-writing
guide</a>, the vocabulary was <b>completely clean</b>: zero hits across the whole watch list
(<code>delve</code>, <code>leverage</code>, <code>robust</code>, <code>seamless</code>,
<code>underscores</code>, <code>testament to</code>, <code>Moreover</code>, …), no curly
quotes, no emoji headings, no "it's not just X, it's Y" parallelisms, no section summaries.
Two tells were real and both were structural: <b>75 em dashes</b> in 3,687 words, one every 49,
and <b>69 bold spans</b>. Those are now <b>2</b> and <b>0</b>. The dash was doing the work a
comma, a colon or a full stop should have done, and dropping it forced sentences to commit to
a structure.
<b>The new guide fills a real gap.</b> <code>docs/rag-architecture.md</code> is a design
document, so a user who wanted semantic search had a README subsection and nothing else.
<code>docs/semantic-search.md</code> is the task version: the two commands, what the local
model costs, how to tell which engine is actually serving, the whole <code>fix_hint</code>
table as a troubleshooting matrix, sharing vectors instead of re-embedding them, and why a
store built against an API key must not be "fixed" by reinstalling the extra — that answer
re-embeds every vector already paid for.
