---
id: eval-corpus-was-not-actually-pinned
board: code
section: internals
status: shipped
category: Eval · Correctness
complexity: M
impact: High
wow: 4
note: 62% of the required gate's corpus was one unpinned third-party repo, against a 1.15-query margin
order: 82
owner: loop/pin-eval-corpus
pr:
title: The &ldquo;pinned&rdquo; eval corpus pinned names, not commits
---
<b>The required <code>eval</code> gate called its corpus pinned. It pinned repository
<em>names</em>.</b> <code>tests/eval/taps.txt</code> listed twenty <code>owner/repo</code> lines and
<code>ensure_eval_corpus.sh</code> shallow-cloned each one at whatever its default branch pointed at,
so the corpus a required check measured was reproducible only for as long as twenty third parties
happened not to push.

<b>Nothing had drifted, and that is worth saying plainly</b> &mdash; today's scores match the
committed baseline to sixteen decimal places, so this is a latent coupling rather than a bug that
already fired. What is surprising is the shape of what was uncoupled. Those twenty repos resolve to
<b>10,152 entries</b>, and a single one of them &mdash;
<code>sickn33/antigravity-awesome-skills</code> &mdash; is <b>6,309 of them, 62% of the gate's entire
corpus</b>. <code>affaan-m/ECC</code> is another 1,616 (16%). Two strangers' repositories were 78% of
what the project measured retrieval quality against.

<b>The margin they were spending is 1.15 queries.</b> BM25 scores recall@10 <b>0.863</b> over this
corpus and CI floored it at <b>0.85</b>: across 91 golden queries that is a buffer of 1.15
recall-units, so <em>one</em> query can fall out of the top ten and the gate still passes, and two
cannot. One upstream push to the repo holding 62% of the corpus could therefore have turned a
required check red on a pull request that touched nothing to do with retrieval &mdash; and on this
project a red required check blocks a merge, and every merge cuts a PyPI release.

<b>A second thing fell out of measuring it: the gate was not the gate.</b> <code>make check</code>
claims to be the required gate, and <code>CLAUDE.md</code> documents <code>eval</code> as four floors
&mdash; recall@k 0.78, hit@1 0.40, MRR 0.52, nDCG@k 0.58. CI ran
<code>--fail-under 0.85</code> and <b>no other floor</b>. So the required check was simultaneously
<em>tighter</em> than the documented gate on one metric and <em>absent</em> on the other three
&mdash; the three added specifically to catch a ranker that finds the right answer every time and
never ranks it first. A regression driving hit@1 to 0.000 would have passed CI while
<code>make check</code> failed locally. Its comment also asserted &ldquo;measured 1.000 over the
pinned corpus, wide margin&rdquo;, which was wrong in both halves.

<b>What shipped.</b> Every row of <code>taps.txt</code> now carries a 40-character commit SHA;
<code>scripts/eval_corpus.py</code> parses the list, fetches the pinned commit when a shallow clone
lacks it, checks it out and rebuilds that tap's cache from the pinned tree. A malformed SHA is fatal
rather than silently treated as unpinned, because a typo that reads as a pin is the failure this
exists to prevent. CI's invocation was aligned with <code>make eval</code>, and a unit test now
compares the flags in <code>Makefile</code> and <code>ci.yml</code> and fails the build when they
disagree &mdash; the drift was invisible precisely because two files each looked right on their own.

<b>Stated limits.</b> Pinning fixes reproducibility, not representativeness: the corpus is still
10,152 entries where a real install runs far more, which is
[[eval-corpus-is-96x-smaller-than-a-real-install]]'s subject and unaffected by this. Moving a pin is
now a deliberate edit that requires regenerating the baseline, which is the intended cost. And the
recall floor was loosened 0.85 &rarr; 0.78 to match the documented gate; that is a real loosening,
bought back by three metrics gaining floors they did not have and by the corpus no longer being able
to move underneath the number.

<b>Provenance.</b> Found while researching options for
[[eval-corpus-is-96x-smaller-than-a-real-install]] and
[[golden-set-grades-by-name-not-by-skill]] &mdash; measuring the corpus in order to size a second
tier is what turned up the fact that nobody knew how big the first one was. It also corrects a claim
I made while researching it: I reported the corpus as 3,843 entries and the margin as +0.062, both
measured on an install that was missing the repo holding 62% of it.
