---
id: eval-corpus-counted-by-the-method-the-repo-disavows
board: code
section: planned
status: planned
category: Quality · Retrieval eval
complexity: L
impact: High
wow: 4
note: scripts/eval_corpus.py counts a repo's contribution as len(entries) from a raw scan (…
order: 208
owner:
pr:
title: The eval corpus's size and its concentration ceiling are counted with <code>len(scan_dir)</code> — the measure <code>measure_registry.py</code> exists to say is wrong — so 44.7% of the gate's corpus is vendored …
---
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
