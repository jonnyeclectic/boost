---
id: langchain-retriever-metadata-and-k-floor
board: code
section: compat
status: inflight
category: Compat · Bug
complexity: S
impact: Med
wow: 3
note: both found by graphing the repo, not by reading it
order: 105
owner: loop/langchain-retriever-contract
pr: 488
title: <code>BoostRetriever</code> advertised a <code>source</code> that does not open, and <code>k=0</code> returned nothing forever
---
Two silent failures in the same twelve lines of <code>boost_langchain/retriever.py</code>, both of
the kind the file's own comments say construction-time validation exists to prevent.

<b>1. <code>metadata["source"]</code> was not openable.</b> It carried
<code>entry["skill_md"]</code>, which the catalog defines as <em>"path of the defining file relative
to the repo root"</em> (<code>core/catalog.py:7</code>) &mdash; <code>skills/brainstorming/SKILL.md</code>,
not a path to anything. Only <code>rag.read_body</code> ever made it real, by joining it to the tap's
clone directory internally and keeping the result to itself. So a chain that did the obvious thing
with a key named <code>source</code> &mdash; cite it, re-read it, hand it to a file tool &mdash;
resolved it against whatever the process CWD happened to be and got a miss, with no error to read.

The tell was next door: <code>SkillMarkdownLoader</code>, the sibling seam in the same package, sets
<code>"source": str(path)</code> (<code>loader.py:59</code>) with a comment insisting that
<em>"metadata provenance must state where the bytes came from"</em>. Two seams of one package
disagreed about what <code>source</code> means, and the retriever was the one that was wrong.

<b>The fix keeps both answers rather than trading one for the other</b>, because they are different
questions. <code>path</code> is the tap-relative one: stable across machines, and what a provenance
line should quote. <code>source</code> is resolved and openable, matching LangChain's convention and
the loader. That distinction is load-bearing for <code>skill_context_node</code>, whose injected
prefix is read out of transcripts on other machines &mdash; it now quotes <code>path</code>, so an
absolute <code>$HOME</code>-rooted path never leaks into a model's context. A test pins that the
injected block contains no home directory.

The join itself moved to <code>rag.entry_path(entry, tap_paths=None)</code> in <code>core/</code>,
where the mutation gate reaches it, and <code>read_body</code> now calls it instead of duplicating
it. The duplication <em>was</em> the bug: with no public way to ask "where does this entry live?",
the caller that needed one reached for the closest-looking field.

<b>2. <code>k=0</code> constructed happily and then returned <code>[]</code> forever.</b> The field
was <code>Field(default=8, ge=0)</code>, and the comment three lines above named exactly this class
of failure &mdash; a typo'd kind, a negative <code>k</code> &mdash; as the reason the field is
validated at all. <code>retrieve_any</code> slices its hits to <code>[:k]</code>
(<code>core/rag.py</code>), so <code>k=0</code> yields an empty list that is indistinguishable from
an empty catalog, from a query that matched nothing, and from a machine with nothing tapped. The
existing test pinned <code>k=-1</code> and stopped one short of the edge that actually shipped. The
floor is now <b>1</b>, with tests on both the direct constructor and the
<code>skill_context_node(k=...)</code> path that builds the default retriever.

<b>How they were found is the part worth keeping.</b> Neither came out of reading the file. Both
came out of building a knowledge graph over the repo and asking why
<code>BoostRetriever</code> had unusually high betweenness &mdash; a question about graph shape, not
about correctness. The answer to the literal question was mostly deflationary: the four communities
it bridges are its own method, its own file, its own tests and its sibling module's tests, and two
of those splits are clustering artifacts rather than architecture. Chasing it anyway is what put
these twelve lines under a microscope.

Worth recording alongside that: the betweenness figure that started the chase was itself wrong.
graphify's report samples 100 pivots and then reports the top three <em>after deleting every file
node</em>, which turned a rank of <b>148/9301</b> (exact betweenness 0.004141) into a reported "rank
~3, 0.020". The investigation that followed was sound; the number that motivated it was inflated
about 4.7&times; by sampling and then re-ranked by a filter the report never mentions.
