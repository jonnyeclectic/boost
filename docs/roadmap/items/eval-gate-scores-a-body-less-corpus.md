---
id: eval-gate-scores-a-body-less-corpus
board: code
section: planned
status: planned
category: Quality · Retrieval eval
complexity: M
impact: Med
wow: 3
note: The Tier 1 required gate has no check that the corpus it scores actually contains the…
order: 211
owner:
pr:
title: <code>make eval</code> scores a corpus with every SKILL.md body missing, reports all four floors PASS, and scores HIGHER than the real corpus
---
<b>Measured.</b> With <code>$BOOST_HOME/repos</code> deleted but the digest sentinel and catalog cache intact, <code>make eval</code>'s two commands print "eval corpus already tapped for this taps.txt — skipping", index the identical 10,152 entries across the identical 20 taps under the identical "BM25 full-content" label, and exit 0 with all four floors PASS — while the index's mean document length falls from 814.836780929866 to 40.5795902285264 tokens (95.0% of the scored text absent) and hit@1 RISES from 0.473 to 0.593, clearing its 0.40 floor by 48% instead of 18%.

<b>Reproduce it.</b>

<code># Form A — on a machine that can tap (what a developer hits):</code><br>
<code>cd &lt;repo&gt;</code><br>
<code>make eval                              # builds .eval-home/{repos,cache}, sentinel, scores 0.852/0.473/0.605/0.657</code><br>
<code>rm -rf .eval-home/repos                # clones gone; cache + sentinel survive</code><br>
<code>make eval                              # "already tapped — skipping"; all four floors PASS at 0.852/0.593/0.692/0.723</code><br>
<code>.venv/bin/python -c "import json;print(json.load(open('.eval-home/cache/rag_index.json'))['stats']['avg_len'])"</code><br>
<code># Form B — exactly what I ran, against the read-only shared corpus (no network needed):</code><br>
<code>cd &lt;repo&gt;</code><br>
<code>H=$TMPDIR/audit-eval-tiers-final; rm -rf "$H"; mkdir -p "$H/.boost"</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

One detail in the claim is wrong and must not be copied into a card:

"The index already computes the number that would catch it (<code>stats.avg_len</code>, rag.py:542) and nothing reads it."

<code>avg_len</code> IS read, twice. <code>grep -rn avg_len boost_cli scripts</code> returns three hits: boost_cli/core/rag.py:542 (write) boost_cli/core/rag.py:677 avg = raw.get("stats", {}).get("avg_len") or 1.0 &lt;- read, on every query scripts/build_demo_index.py:64 "avg_len": raw.get("stats", {}).get("avg_len") or 1.0 &lt;- read

rag.py:677 is BM25's own length-normalisation term (<code>avgdl</code>), consumed by the scorer on every search. Correct phrasing: *<code>avg_len</code> is read by the BM25 scorer (rag.py:677) and by build_demo_index.py:64; what nothing does is CHECK it — no gate, guard, doctor line or test compares it against an expected range or a previous build.*

That distinction is also mechanically load-bearing and explains the finding's own strongest observation: because avgdl normalises uniformly, a corpus that shrinks ~20x in every document keeps its rank SET intact — which is exactly why recall@10 is bit-identical at 0.852 while only the ordering moves.

Every other number in the finding is correct as stated: 40.5795902285264 vs 814.836780929866, 95.0%, +0.120/+0.087/+0.066, identical 0.852, 48%/33%/25%, 10,152 entries / 20 taps, 265 MB, and all five file:line references.

Severity is …

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Defect is real and the mechanism is exactly as described; only the "nothing reads avg_len" clause and the severity need fixing.

WHY Med, NOT High — two facts I verified that cap the blast radius: 1. CI cannot be greened by this. ci.yml:275 passes <code>FORCE=1</code>, so the sentinel is bypassed and <code>eval_corpus.py --ensure</code> runs; <code>pin_clone</code> (eval_corpus.py:244-261) raises <code>CorpusError(UNAVAILABLE, ...)</code> when the commit is not reachable, and <code>_materialise</code> collects it (line 293), so a missing clone tree exits 75. No merge can ship behind this. 2. Nothing in the repo PRODUCES the state. I grepped the Makefile and .gitignore: no target removes <code>.eval-home/repos</code> selectively (<code>.eval-home/</code> is gitignored wholesale, so <code>git clean -xdf</code> takes the sentinel with it, which is a cache miss and therefore safe). It takes an out-of-band <code>rm -rf</code> — manual disk reclamation. A local-only false green behind a manual step that CI re-verifies is Med. It would be High if a boost command produced the state or if CI were exposed.

SCOPE LIMITS OF MY REPRO — a card author must not blur these: - I measured the FULLY-missing case. The "half-materialised tap tree" phrasing in <code>why_it_matters</code> was NOT measured by me; degradation is presumably proportional but is unverified.

<b>Why it is worth doing.</b> The gate whose whole job is to say "retrieval still works over a real corpus" returns a confident, better-than-baseline PASS over a corpus that is name+description only — 95% of its text absent. A developer who reclaims the 265 MB <code>repos/</code> tree, or whose tap tree is half-materialised, gets four green floors that attest to nothing, and the greener number makes the loss look like an improvement rather than a defect. Every downstream floor calibration ("each floor sits ~10% under its measured value") is stated against 0.473/0.605/0.657, which the body-less run clears by 48%/33%/25% instead.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
