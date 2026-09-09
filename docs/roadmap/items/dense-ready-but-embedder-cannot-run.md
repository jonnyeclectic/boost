---
id: dense-ready-but-embedder-cannot-run
board: code
section: planned
status: planned
category: Quality · Retrieval eval
complexity: M
impact: Med
wow: 3
note: localembed.available() (localembed.py:85) tests whether onnxruntime and tokenizers *i…
order: 205
owner:
pr:
title: status() has no state for "ready but the embedder does not work": doctor green-ticks a tier that never ran, the search hint is suppressed, and every search re-pays the failed model fetch
---
<b>Measured.</b> In a store built as provider=local/BAAI/bge-small-en-v1.5/384-d with the weights absent, <code>dense.ready()</code> returns True and <code>status()</code> returns reason=None, degraded=False, while <code>dense.retrieve()</code> returns None on every query — so <code>boost search</code> prints "1 match · ranked by full-content BM25" with no hint (guard: <code>if st.get("ready"): return</code>, discovery.py:339) and <code>boost doctor</code> prints "✓ semantic search active — local BAAI/bge-small-en-v1.5 (384-d), 5 chunks across 1 tap" and exits 0 (guard: <code>if st["ready"]:</code>, quality.py:759); each such search makes exactly one un-cached 133,093,490-byte model fetch (counted in-process: 1 urlopen, 3.72 s, versus a 0.12 s BOOST_NO_EMBED baseline, of which only 0.06 s is the onnxruntime/tokenizers import).

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export HOME=$TMPDIR/verify-dense-f2; export BOOST_HOME=$HOME/.boost; mkdir -p "$HOME"</code><br>
<code>unset VOYAGE_API_KEY OPENAI_API_KEY BOOST_NO_EMBED</code><br>
<code>python3 tests/make_fixture.py $TMPDIR/verify-dense-f2-fix &gt;/dev/null</code><br>
<code>./boost tap $TMPDIR/verify-dense-f2-fix &gt;/dev/null</code><br>
<code># ./boost is system python3 (no sqlite_vec) -&gt; reports no-backend. Use .venv below.</code><br>
<code># PRECONDITION: huggingface.co must be unreachable (blocked here by the proxy).</code><br>
<code>.venv/bin/python - &lt;&lt;'PY'</code><br>
<code>import hashlib, sys; sys.path.insert(0, ".")</code><br>
<code>from boost_cli.core import catalog, dense, embed</code><br>
<code>DIM = 384</code><br>
<code>def fake(texts, input_type=None, timeout=60):</code><br>
<code>    out = []</code><br>
<code>    for t in texts:</code><br>
<code>        h = hashlib.sha256(t.encode()).digest()</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

1. "retries BOTH entries of FILES ... up to 1,200 s" is WRONG. <code>ensure_model</code> (localembed.py:141-150) does <code>if not _fetch(...): return None</code> on the FIRST failure, and <code>FILES</code> orders <code>onnx/model.onnx</code> before <code>tokenizer.json</code>, so tokenizer.json is never attempted on a failing network. Measured: exactly 1 <code>nethttp.urlopen</code> call per process, counted inside a real <code>boost search</code>. Correct statement: ONE fetch per search process, socket timeout 600 s. Do not write "up to 1,200 s"; also do not write "up to 600 s" as a wall-clock ceiling — <code>timeout=600</code> is a per-socket-operation timeout, so a slow-drip server is not bounded by it.

2. Line numbers are off. <code>_hint_semantic_search</code>'s guard is discovery.py:339-340 (<code>if st.get("ready"): return</code>), not 341-343. <code>_report_search_engine</code>'s ready branch is quality.py:759, not 751-755. <code>_load</code> spans localembed.py:153-176 with the <code>ensure_model()</code> call at :164, not 152-166. (localembed.py:85 <code>available()</code> and :124 <code>timeout=600</code> are correct, as are the 133,093,490 B and tokenizer.json byte counts.)

3. The BOOST_NO_EMBED=1 baseline is wrong: measured 0.12/0.12/0.12/0.13/0.14 s, not 1.11/0.80/1.50 s. Delta is 3.5-4.1 s.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE OF MY REPRO — read before writing a card. (a) The failing precondition here is a proxy that truncates the huggingface.co stream, not one that blocks it; the pin in <code>FILES</code> is correct (HF's content-length matches 133,093,490 exactly), so this is not a wrong-hash finding and <code>_verified</code>'s length check is doing its job. (b) All timings are from this sandbox on a 5-entry fixture tap under a disposable HOME; only the structural facts (one fetch per process, no negative cache, both guards keyed on <code>ready</code>, no model probe on either surface) are environment-independent. (c) I could not test the positive case — with the model present dense works and none of this fires — so the finding is strictly about the store-present/model-absent state.

PRIOR DISCLOSURE (the finder declared it, and I confirmed it): docs/roadmap/items/keyless-semantic-search-for-everyone.md, status <code>shipped</code>, body: "retrieval returned zero hits until the model was present — dense.status() reported ready the whole time, because the store genuinely was ready." That card frames it as a limit of what a shard can carry and commits to no work. Nothing in any item body claims doctor's green tick, the search hint's blindness, exit code 0, or the per-search retry cost; grepped all item bodies for localembed / ensure_model / bge-small / weights / "negative cache" / "model fetch" / "133 MB" and read the two candidate cards in full (the other being prerequisites-and-semantic-search-setup, the shipped hint whose blind spot this is).

<b>Why it is worth doing.</b> This is the exact silent-BM25 failure <code>prerequisites-and-semantic-search-setup</code> shipped a hint to close, and the hint is blind to it: the user is told dense is active by doctor, told nothing by search, and pays several seconds per query for a download that can never succeed. A user who runs <code>boost reindex --dense</code> on a laptop with the model cached and then searches from a locked-down network or CI runner gets a slower search than if they had never enabled dense at all, with every surface reporting health.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
