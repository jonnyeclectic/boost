---
id: dense-kill-switch-has-no-reason-state
board: code
section: planned
status: planned
category: Quality · Retrieval eval
complexity: M
impact: Med
wow: 3
note: embed.enabled() short-circuits provider() to None (embed.py:134), so BOOST_NO_EMBED=1…
order: 203
owner:
pr:
title: BOOST_NO_EMBED has no state in the reason ladder: doctor calls a deliberate kill switch a degraded fault (exit 1) and hands advice that is a measured no-op in both branches
---
<b>Measured.</b> With <code>BOOST_NO_EMBED=1</code> and a 5-chunk voyage-4 store, <code>dense.fix_hint</code> tells the user "set the key it was built with: <code>export VOYAGE_API_KEY=...</code>"; exporting that key produces a byte-identical status (reason='no-key', degraded=True, ready=False) and the byte-identical hint — the kill switch is read in <code>provider()</code> before any key, so boost's own remedy is a measured no-op, on both <code>boost doctor</code> (exit 1) and <code>boost search</code>.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export HOME=$TMPDIR/verify-dense-f3; export BOOST_HOME=$HOME/.boost; mkdir -p "$HOME"</code><br>
<code>unset VOYAGE_API_KEY OPENAI_API_KEY BOOST_NO_EMBED</code><br>
<code>python3 tests/make_fixture.py $TMPDIR/verify-dense-f3-fix &gt;/dev/null</code><br>
<code>./boost tap $TMPDIR/verify-dense-f3-fix &gt;/dev/null</code><br>
<code># ./boost is system python3 (no sqlite_vec) -&gt; reports no-backend. Use .venv below.</code><br>
<code>build () {   # $1 provider  $2 model  $3 dim</code><br>
<code>.venv/bin/python - "$1" "$2" "$3" &lt;&lt;'PY'</code><br>
<code>import hashlib, sys; sys.path.insert(0, ".")</code><br>
<code>from boost_cli.core import catalog, dense, embed</code><br>
<code>P, M, DIM = sys.argv[1], sys.argv[2], int(sys.argv[3])</code><br>
<code>def fake(texts, input_type=None, timeout=60):</code><br>
<code>    out = []</code><br>
<code>    for t in texts:</code><br>
<code>        h = hashlib.sha256(t.encode()).digest()</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Every card-worthy measurement is exact. Only citation ranges drift:

1. "eight lines away in the same module" (why_it_matters) is FALSE as written and is the one non-trivial correction. <code>embed.fallback_note()</code> is in boost_cli/core/embed.py:170-179; the inert <code>_FIX</code> table is in boost_cli/core/dense.py:520-534. Different files, ~340 lines and one module apart. Do not put "eight lines away" on the card — it misstates where the fix lives. 2. "dense.py:513-516 states the invariant" -&gt; the quoted sentence spans dense.py:512-514 (512 is "# Why dense retrieval isn't serving...", 513 is "# Each names the ONE next action..."). 3. "<code>_FIX</code> (dense.py:522-533)" -&gt; <code>_FIX</code> is dense.py:520-534; the entries span 521-533. The 8-key count is correct. 4. "tests/unit/test_dense_status.py:100-101" -&gt; the comment and the <code>assert st["degraded"] is False</code> are at 101-102 (line 100 is <code>assert st["model"] is None</code>). 5. "embed.py:134" -&gt; the guard <code>if not enabled():</code> is 133 and <code>return None</code> is 134. Accurate enough as cited.

Confirmed exact: reason/degraded/built_provider in both branches; both hint strings verbatim; doctor rc=1; the fallback_note string; 8 <code>_FIX</code> keys; test_dense_status.py:264 and its lack of a store; 432 roadmap items; 0 BOOST_NO_EMBED hits in roadmap items; embed.py:32 kill-switch doc line.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

1. BLAST RADIUS IS TWO SURFACES, NOT ONE. The finding only measured <code>boost doctor</code>. I also measured <code>boost search</code> under the kill switch: it prints the same inert "set the key it was built with" line (both read the one <code>dense.fix_hint</code> table, by design — CLAUDE.md's "doctor and search cannot give contradictory advice" rule). The card should say both.

2. AN EXISTING CARD PROPOSES A FIX THAT WOULD MAKE THIS WORSE. <code>docs/roadmap/items/audit-quickstart-findings.md</code> line 18 ("The <code>[rag]</code> install hint has three different wordings") proposes: "have <code>embed.fallback_note()</code> and both quickstart paths call <code>dense.fix_hint()</code>". Executed as written that deletes the only correct kill-switch sentence in the codebase (embed.py:178). This card's fix must go the other direction — add a <code>disabled</code> reason to the ladder in <code>status()</code> and give <code>_FIX</code> that key — or the two cards collide. This is not a duplicate (that card is about zsh-unsafe unquoted <code>pip install boost-skill-cli[rag]</code>, not the kill switch), but a card author must be told.

3. THE ONLY ESCAPE IS DELETING THE VECTORS. I renamed the store away and <code>degraded</code> flipped to False (reason stays 'no-key' but <code>degraded = store_exists and reason is not None</code>). So the exit code is not literally unfixable — but the only remedy is discarding every vector the user paid to embed, and no hint mentions it. "red forever" in why_it_matters should be phrased as "red until you delete the store".

4. PRECONDITION IS NARROW — do not overstate reach. You must have BUILT a dense store and THEN set the kill switch.

<b>Why it is worth doing.</b> <code>BOOST_NO_EMBED</code> is documented as a hard kill switch (embed.py:32) and is what a user or a CI job sets to opt out deliberately — including anyone who hits the previous two findings and wants to stop paying for a broken embedder. Doing so turns <code>boost doctor</code> red forever, which breaks it as a CI gate, and the only remedies boost offers are provably inert: reinstalling an installed package, or exporting a key the kill switch never reads. The correct sentence already exists eight lines away in the same module.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CONFIRMED</b>. No fix is prescribed here — the measurement is the contribution.</em>
