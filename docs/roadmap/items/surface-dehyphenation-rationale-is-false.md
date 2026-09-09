---
id: surface-dehyphenation-rationale-is-false
board: code
section: planned
status: planned
category: Quality · Retrieval eval
complexity: M
impact: Med
wow: 3
note: surface() (rag.py:200-208) indexes the name, a de-hyphenated copy of the name, and th…
order: 236
owner:
pr:
title: <code>rag.surface</code>'s de-hyphenated name copy is justified by two claims that are both false, and its real effect — an undocumented 3x name / 2x description field weight — is guarded by a test …
---
<b>Measured.</b> Deleting the "obviously redundant" de-hyphenated copy passes the ENTIRE required gate silently: zero new failures across the full unit + functional suite (the 10 functional failures are a pre-existing <code>dashboard-design</code> CWD leak, identical with and without the ablation), and all four eval floors clear with room to spare (ablated 0.8407 / 0.4725 / 0.6021 / 0.6523 against floors 0.78 / 0.40 / 0.52 / 0.58) — while it silently moves 23 of 141 golden rankings, flips one top-1 result, and drops <code>go-backend-scalability</code> out of the top 10 for the golden query "go backend scalability best practices for microservices and apis", costing exactly 1/91 = 0.011 recall@10.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export BOOST_HOME=$TMPDIR/eval-home BOOST_NO_AI=1</code><br>
<code># 1. the claim is false, corpus-wide</code><br>
<code>.venv/bin/python -c "</code><br>
<code>import re</code><br>
<code>from boost_cli.core import rag, catalog</code><br>
<code>print(re.split(r'[^a-z0-9]+', 'code-reviewer'))</code><br>
<code>es = catalog.all_entries()</code><br>
<code>d = sum(1 for e in es if rag.tokenize(e['name']) != rag.tokenize(e['name'].replace('-',' ').replace('_',' ')))</code><br>
<code>print('entries where de-hyphenation changes the token list:', d, 'of', len(es))</code><br>
<code>tp = rag._tap_paths()</code><br>
<code>e = [x for x in es if x['name']=='docker-expert'][0]</code><br>
<code>print('surface:', rag.surface(e)[:110])</code><br>
<code>print(\"tokenize(surface).count('docker') =\", rag.tokenize(rag.surface(e)).count('docker'))</code><br>
<code>print(\"tf['docker'] =\", rag._make_docs([e], tp)[0]['tf']['docker'])</code><br>
<code>"</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Four numeric/citation corrections. The defect itself is real and every qualitative claim reproduced.

1. LIVE recall@10 is 0.8516 (0.8516483516483516), NOT 0.8571. ABLATED recall@10 is 0.8407 (0.8406593406593407), NOT 0.8462. Both of the finding's absolutes are 0.0055 (= 0.5/91) too high. The DELTA the finding quotes ("0.011 recall@10") is correct: 0.8516 - 0.8407 = 0.010989 = exactly 1/91. Re-derive with <code>scripts/eval_retrieval.py --golden tests/eval/golden.jsonl -k 10 --engines bm25 [--build]</code> against the 20-tap corpus, n=91. My live number reproduces CLAUDE.md's stated 20-tap figures (0.852 / 0.473) exactly.

2. "(hit@1 matches tests/eval/baseline.json exactly)" is FALSE. baseline.json's BM25 row is recall@k 0.8406593407 / hit@1 0.4835164835 (44/91); measured live is 0.8516483516 / 0.4725274725 (43/91). I confirmed the baseline is keyed to the CURRENT query set (<code>golden_key</code> returns <code>golden.jsonl@a0617183f8c9</code>, which is the committed key), so the disagreement is corpus state, not a stale query set. A card must not cite baseline.json as corroboration. Separately: the ablated recall@10 I measured is byte-identical to baseline.json's recall@k (0.8406593406593407) while hit@1 differs — an unexplained coincidence; do not write it up as a claim in either direction.

3. Line citations drifted. <code>surface()</code> is rag.py:202-212 (docstring 203-209, body 210-212), NOT 200-208.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Scope and method limits a card author must not overstate:

- RANKING DIFF METHOD: "top-1 changed 1/141" and "top-10 order changed 23/141" are over RAW <code>rag.retrieve(q, k=10)</code> name lists across 91 golden + 50 golden-natural queries. CLAUDE.md says the eval's GRADED ranked list de-duplicates on the content hash, not the name, so these raw counts are not graded ranks. Do not conflate them. Membership (as opposed to order) changed in only 3/141.

- The ablation I ran drops ONLY the de-hyphenated copy (<code>surface</code> returns <code>name + description</code>). It does not remove <code>surface()</code> entirely; a card claiming "removing surface()" would be a different, larger experiment.

- CORPUS SCOPE: everything is measured against the shared 20-tap / 10,152-entry eval corpus at $TMPDIR/eval-home, which is the corpus the <code>eval</code> gate itself floors against. It is NOT the user's real ~445-tap install, so the 2.64% surface-token share and the per-query ranking flips are properties of the gate corpus. I did not and could not measure the real install.

- I verified the live prebuilt index was not stale by rebuilding an unablated index from the same 20 caches in a third throwaway HOME; it reproduced 0.8516483516483516 / 0.4725274725274725 bit-for-bit, so the 0.011 delta is purely the ablation and not index drift.

- BOTH docstring claims were false AT THE COMMIT THAT WROTE THEM (678bbc26, PR #367): <code>tokenize</code>'s <code>[^a-z0-9]+</code> dates from 329c6eb6 and never changed, and <code>read_body</code> already prepended <code>name\ndescription</code> at 678bbc26.

<b>Why it is worth doing.</b> The stated invariant and the code disagree, which is the failure mode this repo cards as highest-value. A maintainer reading either the docstring or the shipped roadmap card believes the tokenizer does not split hyphens — a false premise that leads either to deleting the "obviously redundant" duplicate (silently moving 23 of 141 golden rankings and costing 0.011 recall@10 on the gate's own query set, with no test failing) or to building hyphen handling that already exists.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
