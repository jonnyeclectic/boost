---
id: dense-no-key-guard-is-unreachable
board: code
section: planned
status: planned
category: Quality · Retrieval eval
complexity: L
impact: High
wow: 4
note: dense.status() checks prov is None before it looks at the store (dense.py:618-621), b…
order: 204
owner:
pr:
title: fix_hint's no-key guard has been unreachable since the day it was written; a missing API key now prescribes the full re-embed the guard exists to prevent
---
<b>Measured.</b> On a complete <code>[rag]</code> extra with a voyage-4-built vector store and no API key exported, <code>dense.status()</code> returns <code>reason='provider-changed'</code> (not <code>no-key</code>), so all three status-passing surfaces print <code>rebuild it: \</code>boost reindex --dense --force\`<code> and </code>boost doctor<code> exits 1 — measured verbatim, including doctor's "live key is local; searches are using BM25" line — while the guard written to prevent exactly that (</code>21f28223<code>, #444) fires only under </code>BOOST_NO_EMBED=1` or a partial install, both confirmed by direct probe.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export HOME=$TMPDIR/verify-dense-f1; export BOOST_HOME=$HOME/.boost; mkdir -p "$HOME"</code><br>
<code>unset VOYAGE_API_KEY OPENAI_API_KEY BOOST_NO_EMBED</code><br>
<code>python3 tests/make_fixture.py $TMPDIR/verify-dense-f1-fix &gt;/dev/null</code><br>
<code>./boost tap $TMPDIR/verify-dense-f1-fix &gt;/dev/null</code><br>
<code># NOTE: ./boost execs system python3, which has no sqlite_vec, so it always says</code><br>
<code># "no-backend". Every dense command below MUST run under .venv.</code><br>
<code>.venv/bin/python - &lt;&lt;'PY'</code><br>
<code>import hashlib, sys; sys.path.insert(0, ".")</code><br>
<code>from boost_cli.core import catalog, dense, embed</code><br>
<code>DIM = 1024</code><br>
<code>def fake(texts, input_type=None, timeout=60):          # no network, no API spend</code><br>
<code>    out = []</code><br>
<code>    for t in texts:</code><br>
<code>        h = hashlib.sha256(t.encode()).digest()</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

The defect is real and reproduced verbatim, but five stated details are wrong:

1. SOURCE ATTRIBUTION OF THE COST FIGURE. <code>why_it_matters</code> says "which CLAUDE.md prices at ~1.2 s per chunk on CPU". <code>grep -n 'per chunk\|1\.2 s' CLAUDE.md</code> returns nothing. The figure is real but lives in the roadmap: <code>docs/roadmap/items/keyless-semantic-search-for-everyone.md:298</code> ("4,431 s — 74 minutes, about 1.2 s per chunk") and <code>:308</code>, plus <code>the-shard-job-that-could-not-finish.md:17</code> and <code>keyless-dense-tier-local-static-embeddings.md:75</code>. Cite the roadmap, not CLAUDE.md.

2. <code>quality.py:769</code> is wrong -&gt; the fix_hint call is <code>boost_cli/commands/quality.py:780</code> (<code>fix = dense.fix_hint(st["reason"], st)</code>). Line 769 sits inside the unrelated <code>search-quantization</code> warning.

3. <code>pyproject.toml:55-57</code> is wrong -&gt; the three pins are at lines <b>56, 67 and 68</b> (<code>sqlite-vec&gt;=0.1.6</code>, <code>onnxruntime&gt;=1.17</code>, <code>tokenizers&gt;=0.15</code>), split by a 10-line comment justifying the fastembed rejection. They are in one extra, which is the load-bearing part, but the range is not 55-57.

4. THE CAUSAL-ORDER COMMIT PAIR NAMES THE WRONG COMMIT FOR THE GUARD. <code>86163e03</code> (2026-07-31, #364) created <code>test_dense_fix_hint.py</code> <b>and the <code>_FIX</code> table</b>, but not the guard.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

PRECONDITION — state it on the card so nobody reads it as unconditional. The misroute needs (a) a store built with an API provider, (b) the complete <code>[rag]</code> extra so <code>provider()</code> falls through to <code>local</code>, and (c) the key absent from the *process* environment. #444's own commit message documents that shape as recurring in the wild: "the shell exports one; the spawned server does not inherit it."

THE REAL MACHINE IS NOT CURRENTLY IN THE BUG STATE. <code>~/.boost/cache/rag_vectors.sqlite</code> reads provider="local", model="BAAI/bge-small-en-v1.5", dim=384 — so <code>provider()</code> matches <code>built_provider</code> and its reason is None. The 645,592-chunk / 1.20 GB / 440-tap figure is <b>cost-if-the-hint-is-followed</b>, not present harm. Do not let the card imply the machine is broken today. (The 750,416-chunk voyage-4 store in the #444 message and the test docstring is a past state of the same machine.)

THE MISDIAGNOSIS WAS REFUTABLE FROM THE SAME FILE. The <code>_FIX</code> comment — "This reason means 'no key AND no local backend', which in practice is a partial install or BOOST_NO_EMBED" — was already in <code>dense.py</code> from 86163e03 (07-31) when #444 (08-03) added a guard whose docstring asserts the opposite: "an unfinished install with no store and a complete install whose key merely went missing both land here." Two claims about <code>no-key</code>, 30 lines apart, that contradict each other.

<b>Why it is worth doing.</b> A user who opens a new shell without exporting their key is told by doctor, search and the MCP server to re-embed their whole store. On the real machine in this repo that is 645,592 chunks / 1.20 GB, which CLAUDE.md prices at ~1.2 s per chunk on CPU — hours of compute, or a real API bill — to fix a problem whose actual remedy is one <code>export</code>. The repo already decided this was unacceptable and wrote six tests plus a paragraph of docstring to prevent it; the guard has simply never been able to fire.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
