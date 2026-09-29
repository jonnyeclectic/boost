---
id: eval-corpus-counted-by-the-method-the-repo-disavows
board: code
section: shipped
status: shipped
category: Quality · Retrieval eval
complexity: L
impact: High
wow: 4
note: taps.txt rows gained a distinct-content count and the gate gained a second ceiling. The raw count stays — BM25 indexes without de-duplicating, so the copies really are documents — but sickn33 is 61.8% of the rows and 35.7% of the content, and only one number was being floored.
order: 208
owner: loop/eval-corpus-distinct-count
pr: 992
title: The eval corpus's size and its concentration ceiling are counted with <code>len(scan_dir)</code> — the measure <code>measure_registry.py</code> exists to say is wrong — so 44.7% of the gate's corpus is vendored …
---
<b>SHIPPED.</b> taps.txt rows gained a fourth field — the distinct-content count — and the concentration gate became two ceilings instead of one.

<code>anthropics/skills   3b3fad9…   20    20</code><br>
<code>sickn33/antigravity-awesome-skills   782f684…   6634  2117</code>

<code>MAX_SHARE</code> is now <code>MAX_ROW_SHARE</code> (0.65) and is joined by <code>MAX_CONTENT_SHARE</code> (0.40), and both are checked on every <code>--ensure</code>, <code>--relock</code>, <code>--refresh</code> and <code>--audit</code>. At the current pins: sickn33 is <b>61.8% of the rows and 35.7% of the content</b>, and affaan-m/ECC is <b>15.1% of rows and 26.7% of content</b> — the two orderings differ, which is the whole reason there are two numbers. The corpus is 10,731 rows over 5,938 distinct items, so the rows overstate it <b>1.81x</b>, and taps.txt now says so in its own generated size block.

<b>The raw count was kept, deliberately.</b> This card's title reads as "the raw count is wrong", and the fix is not to replace it. <code>rag.build</code> indexes <code>catalog.all_entries()</code> with <b>no</b> de-duplication, so a registry vendoring the same skill sixty-eight times really does occupy sixty-eight of the documents BM25 ranks a query against: the raw count is the honest number for the DRIFT check and for "BM25 scored N documents". What was missing was the second number, not a correction to the first. Hence two fields and two ceilings rather than one replaced.

<b>The identity is <code>catalog._content_digest</code>, not <code>measure_registry.py</code>'s.</b> Two new helpers in <code>boost_cli/core/catalog.py</code> — <code>content_unique()</code> and <code>distinct_content()</code> — collapse on <code>entry["content"]</code>, the digest over name + description + body already stamped at scan time and already what <code>rag.dedupe_by_content</code> uses. <code>measure_registry.py</code>'s digest hashes the body <em>alone</em> with agent-dotdir tokens normalised, which is right for <code>est_items</code> (one skill rendered into five agents' directories is one item) and wrong here (two different skills with the same body are two documents in the index). The card's premise that these are the same rule is what <code>measure_registry.py</code>'s docstring claims and is not true; the gate now uses the one that matches what it scores.

<b>An unsatisfiable ceiling is not a strict one.</b> A ceiling of <em>c</em> cannot be met by fewer than <code>1/c</code> repositories, because the smallest possible top share is <code>1/N</code> — two repos cannot get below 50%, so a 40% content ceiling would refuse every two-repo corpus however it was balanced, and the only remedy it could print ("add breadth") is the only thing that could ever clear it. <code>check_concentration</code> therefore does not judge a corpus below that floor. The shipped list has twenty repos against a floor of three, so the real gate is untouched; what it buys is that a fixture corpus can exercise the same code path.

<b>Not regenerated: <code>tests/eval/baseline.json</code>.</b> No pin moved and the indexed corpus is byte-identical, so the scores are unchanged — regenerating it would have been noise in the diff and a claim that something had been re-measured.

<b>Measured.</b> Two tools in this repo, run on the same clone at the same pinned SHA, give item counts 3.16x apart — <code>scripts/measure_registry.py</code> says <code>est_items=2100</code> while <code>scripts/eval_corpus.py --ensure</code> records <code>6634 entries</code> — and the tool that is right is the one the eval gate does not use: measure_registry.py's own docstring (lines 6-11) states that <code>len(catalog.scan_dir(repo))</code> is not the measurement, "the same rule the eval gate's ranked list uses". <code>eval_corpus.py:299</code> is still <code>counts[repo] = len(entries)</code>, and <code>MAX_SHARE = 0.65</code> (line 113) ratchets on that number inside CI's required <code>lint</code> job — so 976 extra vendored copies from one stranger's repository, containing zero new content, turn every open pull request red.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export HOME=$TMPDIR/audit-corpus-verify &amp;&amp; mkdir -p "$HOME" &amp;&amp; export BOOST_HOME=$HOME/.boost</code><br>
<code>.venv/bin/python scripts/eval_corpus.py --ensure      # -&gt; "corpus: 10731 entries"; "concentration: ... 61.8%"</code><br>
<code>.venv/bin/python scripts/measure_registry.py "$BOOST_HOME/repos/sickn33__antigravity-awesome-skills"   # -&gt; est_items=2100</code><br>
<code>.venv/bin/python - &lt;&lt;'PY'</code><br>
<code>import json, pathlib, collections, os</code><br>
<code>home=pathlib.Path(os.environ["BOOST_HOME"]); ents=[]</code><br>
<code>for f in sorted((home/"cache").glob("*.json")):</code><br>
<code>    if f.stem.startswith("rag_"): continue</code><br>
<code>    d=json.loads(f.read_text())</code><br>
<code>    for e in d["skills"]: e["_tap"]=d["tap"]; ents.append(e)</code><br>
<code>alld={e["content"] for e in ents}</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

1. MATERIALLY WRONG — "The vendoring is 60 <code>plugins/agentic-bundle-*/</code> directories". There are 58 <code>agentic-bundle-*</code> dirs (60 <code>plugins/*</code> dirs total), and they hold only 449 of the 6,634 entries (6.8%; median 8 entries each). The 3.13x inflation is two FULL CATALOG MIRRORS: <code>plugins/agentic-awesome-skills-claude</code> (2,049 entries) and <code>plugins/agentic-awesome-skills</code> (2,027) = 4,076 entries, digest-identical to <code>skills/</code> (2,107 entries, all distinct). This reframes the ceiling scenario: "one more bundle render... adds ~2,117 entries" is impossible — a bundle is ~8-10 entries. The correct unit is "one more per-agent mirror", ~2,049 entries -&gt; 67.9%, still over 65%. Sharper still: only 976 extra vendored sickn33 entries are needed to cross the ceiling (&lt; half a mirror). The conclusion survives; the unit does not — and the correct unit is exactly the pattern the <code>est-items</code> card already documents.

2. "Read all 318 titles from <code>grep -h '^title:' docs/roadmap/items/*.md</code>" — there are 432 items / 432 title lines today (verified identical to origin/main except one unrelated file). The not-carded sweep was run over a smaller set than exists.

3. "Every one of them... none measures distinct content" is wrong.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE OF MY REPRO — what I actually settled, and what I did not. - I materialised the corpus at the CURRENT taps.txt pins in my own disposable HOME and reproduced every headline number independently. The pre-refresh figures (10,152 / 5,790 / 62.1% / 34.5% / 3.16x) I took from the SHARED read-only eval-home at $TMPDIR/eval-home, which is still at the older pins — a read-only census, no writes. - The repo checkout was on a peer session's branch <code>loop/missing-json</code>, not <code>main</code>. I diffed every file this finding touches (scripts/eval_corpus.py, tests/eval/taps.txt, boost_cli/core/rag.py, .github/workflows/eval-corpus-refresh.yml, all of docs/roadmap/items/) against origin/main: identical except one unrelated roadmap item. The verification holds against main (origin/main af4bdbfd). - I could NOT isolate the causal mechanism of the 22 rank changes. The finding asserts "BM25 statistics (N and document frequency), not slot consumption". My data is CONSISTENT with that — <code>dedupe_by_content</code> does run over the full pool before k (rag.py:1053, confirmed), and recall@k is bit-identical while the rank-sensitive metrics move — but I did not separate idf from avgdl, nor rule out that a different byte-identical copy survives dedupe and carries a different <code>grade_key</code>. Write it as "consistent with", not "confirmed".

WHY HIGH RATHER THAN MEDIUM. The metric movement alone cannot fail anything: hit@1 +0.011, MRR +0.010, nDCG +0.008 against 0.06-0.10 of headroom over the floors. The severity is the ratchet's teeth, which the finder never traced.

<b>Why it is worth doing.</b> <code>MAX_SHARE</code> is the only shipped guard against the gate's corpus becoming one publisher's house style, and it is measured on a quantity a third party can inflate by ~3x without publishing a single new skill — so it can fire on a repo contributing a third of the content, and cannot fire on a repo that dominates the content without vendoring. The same raw count is the headline everywhere (<code>10,152 entries</code> / <code>62%</code>) and is what the monthly refresh PR reports as growth, overstating real content growth 4x.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
