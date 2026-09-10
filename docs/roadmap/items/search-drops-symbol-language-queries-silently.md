---
id: search-drops-symbol-language-queries-silently
board: code
section: pipeline
status: shipped
category: UX · Bug
complexity: L
impact: High
wow: 4
note: c++/c#/f#/objective-c now alias to indexable tokens on BOTH the index and query side (INDEX_VERSION 7 -&gt; 8); a term that is still dropped is named on stdout, on stderr under --json, and in the MCP reply
order: 230
owner: loop/symbol-language-queries
pr: 840
title: <code>boost search 'C++'</code> returns zero and blames the catalogue: tokenize drops every 1-char token, and nothing ever says a term was discarded
---
<b>Measured.</b> On a corpus holding 42 entries that name C++ in their name or description, <code>boost search 'c++ testing'</code>, <code>boost search 'c# testing'</code> and <code>boost search 'testing'</code> produce byte-identical <code>--json</code> output (md5 70050f6044e9957148ceec29f76a8fb2, 15 rows each, top row <code>testing-qa</code>) with exactly 0 bytes on stderr — the language term is erased with no notice and the query silently becomes a search for <code>testing</code>, while <code>cpp testing</code> (md5 dd4b3d1c…) returns cpp-review/cpp-test/cpp-testing at ranks 1-5.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export BOOST_HOME=$TMPDIR/eval-home</code><br>
<code>./boost search 'C++'</code><br>
<code>./boost search 'c#'</code><br>
<code>./boost search 'C++' --json ; echo "rc=$?"</code><br>
<code>./boost search 'c++ testing' --limit 5</code><br>
<code>./boost search 'cpp testing' --limit 5</code><br>
<code>./boost search 'c++ testing' --json &gt; $TMPDIR/a.json</code><br>
<code>./boost search 'c# testing'  --json &gt; $TMPDIR/b.json</code><br>
<code>./boost search 'testing'     --json &gt; $TMPDIR/c.json</code><br>
<code>cmp -s $TMPDIR/a.json $TMPDIR/b.json &amp;&amp; echo 'c++ == c# : IDENTICAL'</code><br>
<code>cmp -s $TMPDIR/a.json $TMPDIR/c.json &amp;&amp; echo 'c++ == testing : IDENTICAL'</code><br>
<code>.venv/bin/python -c "from boost_cli.core import rag; [print(repr(q),'-&gt;',rag.tokenize(q)) for q in ['C++','c#','F#','R','C','Go','k8s','Objective-C','pyhton']]"</code><br>
<code># corpus counts</code><br>
<code>python3 - &lt;&lt;'EOF'</code><br>
…

<b>Verification found nothing to correct.</b> Every number, <code>file:line</code> and command output above was independently re-derived and matched exactly.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE LIMIT THE CARD MUST STATE (my most important finding, and the finding does not mention it): <code>dense.retrieve</code> (dense.py:1609-1614) embeds the RAW query string — <code>qv = embed.embed([query], input_type="query")</code> — and never calls <code>tokenize</code>. So a machine with a built dense store plausibly answers <code>C++</code> fine, and <code>retrieve_any</code> would fuse or use it. I could NOT verify that here (the BAAI model cannot be downloaded in this sandbox, and I must not build against the shared read-only eval corpus). The card must therefore scope the defect to the BM25-only path — which is the always-on, zero-dependency default, what every user without the <code>[rag]</code> extra runs, and the path the required <code>eval</code> gate floors. This is also why it survived: the identical "invisible from a developer install" argument that <code>bm25-has-no-stemming</code> makes about itself.

UNITS: 42 C++ / 27 C# are ENTRIES (rows across 20 tap caches), not distinct skills — 13 and 10 distinct names respectively. Write "entries". Do not let "42 skills" ship.

WITHIN-BATCH DUPLICATE — finding 9 (<code>bm25-empty-tokenization-kills-catalog-fallback</code>) shares this exact root cause and cites the same rag.py:88-91 and rag.py:1010-1012. Finding 6 is the search-UX half (silent erasure, no notice, --json ambiguity); finding 9 is the dead-<code>catalog.search</code>-fallback half. If the orchestrator merges them, the 42-vs-45 discrepancy is resolved, not a defect in either: I measured both denominators in the same loop — name+description contains "c++" = 42 (finding 6's figure), <code>search_blob</code> contains "c++" = 45 (finding 9's figure).

<b>Why it is worth doing.</b> C++ and C# are among the most-typed language names a skill catalogue will ever receive, and boost answers both with the one message that means "this machine has nothing" plus a remedy that sends the user off to GitHub for 42 skills already sitting on their disk. This is the exact failure <code>bm25-has-no-stemming</code> shipped to fix ("returns zero and sends the user to <code>boost discover</code> to search all of GitHub for something already in their catalogue") arriving through a different door.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CONFIRMED</b>. No fix is prescribed here — the measurement is the contribution.</em>

<b>What shipped.</b> <code>rag.SYMBOL_ALIASES</code> folds four language names the splitter destroys — <code>c++</code>&rarr;<code>cpp</code>, <code>c#</code>&rarr;<code>csharp</code>, <code>f#</code>&rarr;<code>fsharp</code>, <code>objective-c</code>&rarr;<code>objectivec</code> — before the split, on the <b>index</b> side as well as the query side. That symmetry is the fix: a query-side-only map reaches the items already named <code>cpp-*</code> and still misses every entry whose description spells it <code>C++</code>, which is most of them. Lookarounds keep <code>basic++</code> from indexing as a C++ mention and the musical note <code>c#5</code> from becoming a language. Unlike <code>stem_expansions</code> this conflates terms that both exist, so it is an <code>INDEX_VERSION</code> bump (7 &rarr; 8) and one forced re-tokenize.

The table is deliberately four rows. <code>.NET</code> already reaches its 124 entries through the token <code>net</code> and <code>node.js</code> through <code>node</code>+<code>js</code>, so remapping those would change rankings that work today to fix nothing.

<b>And what is still dropped is now said out loud.</b> <code>rag.dropped_terms</code> names the words that fell out of the tokenizer — a single character, a non-Latin script. <code>boost search</code> reports them beside the results they are not in, on <b>stderr</b> under <code>--json</code> (same contract as the <code>--smart</code> fallback note, so a script reading stdout as JSON still learns), and as its own empty state when every term went: <code>no searchable terms in 'R'</code> rather than <code>no matches</code>, and no <code>boost discover</code> suggestion for a query that never reached an index. <code>mcp.no_results</code> grew the same third branch, because an agent told "no skills match 'C++'" has no second query to try. <code>docs/demo.html</code> ports the tokenizer to JS and a test pins the table in both, so the browser demo cannot drift into answering <code>C++</code> differently from the CLI.

<b>What was rejected.</b> Falling back to <code>catalog.search</code> for an untokenizable query, exactly as the verifier warned: substring-matching <code>R</code> returns 10,092 of 10,152 entries. The fallback stays unreachable on purpose; what changed is that the answer now says why.
