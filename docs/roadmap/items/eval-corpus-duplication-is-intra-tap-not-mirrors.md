---
id: eval-corpus-duplication-is-intra-tap-not-mirrors
board: code
section: planned
status: planned
category: Quality · Retrieval eval
complexity: S
impact: Low
wow: 2
note: rag.dedupe_by_content is documented against a real install where "registries mirror e…
order: 209
owner:
pr:
title: The corpus's 65.6% duplication is 99.93% inside a single tap, so the required gate never once exercises the cross-tap trust ordering dedup exists for — 0 swaps in 264,735 comparisons
---
<b>Measured.</b> Over the 91 required golden queries on the current pins, 264,544 of 264,735 collapse comparisons inside <code>rag.dedupe_by_content</code> (99.93%) were between two copies in the SAME tap and the source-preference branch executed 0 times; and forcing it to fire — marking one tap curated produces 191 swaps — leaves recall@k / hit@1 / MRR / nDCG@k at 0.8407 / 0.4835 / 0.6065 / 0.6552 both before and after, with all 91 graded ranked-key lists identical.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export HOME=$TMPDIR/audit-corpus-verify &amp;&amp; export BOOST_HOME=$HOME/.boost   # after eval_corpus.py --ensure (see other finding)</code><br>
<code>.venv/bin/python - &lt;&lt;'PY'</code><br>
<code>import sys, json</code><br>
<code>sys.path.insert(0,"."); sys.path.insert(0,"scripts")</code><br>
<code>from boost_cli.core import rag</code><br>
<code>from boost_cli.core.rag import source_rank</code><br>
<code>stats={"collapses":0,"same_tap":0,"diff_tap":0,"swaps":0,"ties":0}</code><br>
<code>def patched(hits, limit):</code><br>
<code>    best={}; out=[]</code><br>
<code>    for hit in hits:</code><br>
<code>        d=hit.get("content")</code><br>
<code>        if not d: out.append(hit); continue</code><br>
<code>        s=best.get(d)</code><br>
<code>        if s is None: best[d]=len(out); out.append(hit); continue</code><br>
<code>        stats["collapses"]+=1; kept=out[s]</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

1. THE REMEDY CLAIM IS WRONG, and this is the correction that matters. The finding's <code>why_it_matters</code> says "adding a single mirror registry to taps.txt would be enough to make it visible." It would not. <code>eval_retrieval.grade_key</code> (scripts/eval_retrieval.py:197-209) keys every ranked slot on the content digest (<code>body:&lt;digest&gt;</code>), the exemplar class (<code>cls:...</code>), or the entry name — and a swap only ever replaces <code>hit["entry"]</code> INSIDE a content cluster, where the digest is identical by construction and, because <code>catalog._content_digest</code> hashes name + description + body, so is the name. Every return branch of <code>grade_key</code> is therefore invariant under a swap; the <code>nohash:tap::skill_md</code> branch at :209 is unreachable for a swapped hit because dedupe never collapses a hit with no digest. Proven, not argued: marking <code>composio-community/awesome-codex-skills</code> curated on the same pinned corpus fires 191 swaps (every cross-tap collapse becomes a swap — the composio copy arrives second in all 191) and leaves recall@k / hit@1 / MRR / nDCG@k at 0.840659 / 0.483516 / 0.606517 / 0.655233 before AND after, with all 91 graded ranked-key lists byte-identical. So a trust-ordering regression is invisible to the required gate BY CONSTRUCTION, regardless of corpus shape — the gap is that the harness never grades on source, not that the corpus lacks mirrors.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE OF MY REPRO — read this before re-verifying. The finder's numbers reproduce ONLY on the CURRENT pins (10,731 entries). The shared read-only corpus at $TMPDIR/eval-home is PRE-REFRESH: 10 of its 20 clones are not at the SHAs in tests/eval/taps.txt (anthropics/skills, NeoLabHQ, LessUp, affaan-m/ECC, first-fluke, langchain-ai, minio, OneWave-AI, sickn33, anthropics/claude-agent-sdk-python), and it holds 10,152 entries. There the same instrumentation gives 1,986 clusters / 6,348 entries (62.5%) / 240,646 collapses / 240,455 same_tap / 191 diff_tap / 0 swaps. I materialised the current pins into a private copy (<code>eval_corpus.py --ensure</code>, network fetch works despite a harmless <code>failed to store: 100001</code> commit-graph warning) to get the finder's exact figures. Anyone re-checking against $TMPDIR/eval-home will get the smaller set and should not read that as refuting the finding — the qualitative result (5 cross-tap clusters, all high/high, 0 swaps, ~99.9% same-tap) is identical on both.

DOC TRAP, not this finding's fault: tests/eval/taps.txt's own header prose says "10,152 entries" and "sickn33 … is 6,309", and CLAUDE.md repeats 10,152 — but the file's own per-repo rows sum to 10,731 with sickn33 at 6,634. The pins were moved in commit cbc0a58b ("test(eval): refresh the pinned retrieval corpus") and the header prose was not updated. A card author quoting corpus size must take the row sum, not the header.

NOT ALREADY CARDED, but read the existing card first.

<b>Why it is worth doing.</b> The required corpus contains essentially none of the duplicate shape that dominates a real install. A user's duplicates arrive as mirror registries republishing each other's skills across taps, which is what <code>source_rank</code> decides between and what determines where a user is told to install from; the gate's duplicates are one publisher re-vendoring itself into 60 plugin bundles, where every candidate has the same tap and the tie-break is a no-op.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
