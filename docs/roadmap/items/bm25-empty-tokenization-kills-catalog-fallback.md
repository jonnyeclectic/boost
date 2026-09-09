---
id: bm25-empty-tokenization-kills-catalog-fallback
board: code
section: planned
status: planned
category: Quality · Retrieval eval
complexity: L
impact: High
wow: 4
note: rag.tokenize (rag.py:88-91) keeps only [a-z0-9] runs of length &gt;= 2, so "C++", "C#" a…
order: 200
owner:
pr:
title: A query made only of characters <code>tokenize</code> drops returns zero results, and the documented <code>catalog.search</code> fallback is unreachable — <code>boost search "C++"</code> finds nothing on a machine holding …
---
<b>Measured.</b> On the developer's own 440-tap install — with no BOOST_HOME override, where <code>dense.status()</code> reports <code>ready: False, reason: 'provider-changed'</code> so the machine is on the always-on BM25 path — <code>rag.retrieve("C++")</code> returns <b>0</b> hits while <code>rag.retrieve("cpp")</code> returns <b>60</b>, and <code>retrieve_any</code> reports <code>(0, 'BM25 full-content')</code> rather than <code>None</code>, so the <code>catalog.search</code> fallback that finds 45 C++ items can never run.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export BOOST_HOME=$TMPDIR/eval-home BOOST_NO_AI=1</code><br>
<code>./boost search "C++" --json      # []</code><br>
<code>./boost search "C#" --json       # []</code><br>
<code>./boost search "代码审查" --json   # []</code><br>
<code>.venv/bin/python -c "</code><br>
<code>from boost_cli.core import rag, catalog</code><br>
<code>from boost_cli.commands import configuration as cfg</code><br>
<code>es = catalog.all_entries()</code><br>
<code>for q in ['C++','C#','代码审查']:</code><br>
<code>    print(repr(q), 'tokenize=', rag.tokenize(q),</code><br>
<code>          'retrieve_any=', (lambda r:(len(r[0]), r[1]))(rag.retrieve_any(q)),</code><br>
<code>          'catalog.search=', len(catalog.search(q, es)),</code><br>
<code>          [e['name'] for e,_ in catalog.search(q, es)[:3]])</code><br>
<code>print('rag.search(C++) -&gt;', (lambda r: 'None' if r is None else (len(r[0]), r[1]))(rag.search('C++', limit=10, smart=False)))</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

The DEFECT reproduces exactly; five of the six cited anchors are wrong, and the drift pattern says the finder read an older tree.

- <code>rag.py:1288</code> (<code>elif bm25_hits is not None</code>) -&gt; actual <b>rag.py:1286</b> - <code>rag.py:1010-1012</code> (<code>if not terms: return []</code>) -&gt; actual <b>rag.py:1009-1011</b> (<code>terms = tokenize(query)</code> is 1009, <code>if not terms:</code> 1010, <code>return []</code> 1011) - <code>discovery.py:144</code> (<code>use_rag = rag.ensure()</code>) -&gt; actual <b>discovery.py:145</b> - <code>configuration.py:1266</code> (<code>rag.search(...)</code>) -&gt; actual <b>configuration.py:1321</b> (off by 55) - <code>configuration.py:1281</code> (<code>catalog.search(query)[:10]</code>) -&gt; actual <b>configuration.py:1336</b> (off by 55) - <code>not_carded_check</code>: "Read all 318 <code>^title:</code> lines from docs/roadmap/items/*.md" -&gt; actual <b>432</b> items, 432 title lines.

CORRECT as stated: <code>rag.py:88-91</code> for <code>tokenize</code>; <code>discovery.py:164</code> for <code>scored = catalog.search(query)</code>; 45 / 27 / 17 catalog.search counts; 42 entries with literal "c++" in name or description; 93 corpus files containing 代码审查; the MCP return <code>("no skills match 'C++'", False)</code>; and the absence of any <code>BOOST_NO_RAG</code> / <code>--no-rag</code> escape hatch.

The ~55-line configuration.py drift plus a title count off by 114 is not miscounting — the finder measured an older checkout.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE OF MY REPRO. All corpus counts (45 / 27 / 17 / 42 / 93 / 10,152) are from the shared 20-tap eval corpus at $TMPDIR/eval-home and must be labelled as such in the card — the finding says "the same machine", which reads as a real install. The datum that generalises is the one I took from the real 440-tap install (0 for <code>C++</code>, 60 for <code>cpp</code>).

SCOPE OF THE DEFECT — dense rescues it. <code>boost_cli/core/dense.py</code> contains no call to <code>tokenize</code> (it embeds the query string), so <code>retrieve_any</code> takes the <code>elif dense_hits:</code> branch and a machine with a *ready* dense store is NOT hit. The defect is confined to the always-on BM25-only path — every user without a built dense store, plus the MCP surface on such a machine. Note this kills the "invisible from a developer install" excuse the shipped <code>bm25-has-no-stemming</code> card leaned on: this repo's own machine is on that path right now because its dense store was built with <code>BAAI/bge-small-en-v1.5</code> and the configured provider is now <code>voyage</code>.

BLAST RADIUS IS WIDER THAN THE THREE NAMED QUERIES. Any query where *every* token is under 2 alphanumerics or non-Latin wipes out: <code>C++</code>, <code>C#</code>, <code>F#</code>, <code>R</code>, <code>C</code>, <code>how to</code>, <code>a the of</code>, <code>代码审查</code>, <code>日本語</code>. A multi-word query with one ordinary Latin word still works (<code>c++ memory safety</code> -&gt; 60 hits, with <code>c++</code> silently erased — that erasure is sibling finding 6's angle).

DO NOT WRITE "FALL BACK TO catalog.search" AS THE FIX. I measured the naive remedy and it is unsafe: <code>catalog.search('R')</code> returns <b>10,092 of 10,152</b> entries and <code>catalog.search('how to')</code> returns <b>6,229</b> — noise, not results.

<b>Why it is worth doing.</b> A user or agent asking for the most common name of a mainstream language is told the catalogue holds nothing and is sent to <code>boost discover</code> to search all of GitHub for <code>cpp-expert</code>, <code>cpp-reviewer</code> and <code>cpp-coding-standards</code> that are already on their disk — the exact symptom the shipped card <code>bm25-has-no-stemming</code> was written to kill, arriving through a different door. It is worse on the MCP surface, where <code>boost_search</code> answers an agent "no skills match 'C++'" and the agent has no second query to try.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
