---
id: eval-corpus-is-one-strangers-repo
board: code
section: internals
status: shipped
category: Eval · Correctness
complexity: S
impact: High
wow: 3
note: one third-party repo is 62% of the gate's corpus, and if it disappears every PR goes red
order: 84
owner: loop/eval-corpus-availability
pr:
title: 62% of the required gate's corpus is a single third-party repository
---
<b>Pinning the eval corpus to commit SHAs fixed drift. It did not fix concentration, and cannot fix
availability.</b> The twenty repositories in <code>tests/eval/taps.txt</code> resolve to 10,152
entries, wildly unevenly: <code>sickn33/antigravity-awesome-skills</code> is <b>6,309 of them
(62%)</b> and <code>affaan-m/ECC</code> another 1,616 (16%). Two strangers' repositories are
<b>78%</b> of what this project measures retrieval quality against.

<b>The failure mode is every open PR going red at once.</b>
<code>ensure_eval_corpus.sh</code> runs under <code>set -euo pipefail</code> and a failed clone takes
it with it &mdash; verified, not assumed: one unreachable repo in the list exits <b>1</b>, failing
CI's <code>lint</code> job, a required context. A pinned SHA does not help, because a commit still
has to be <em>fetchable</em>, and a repo that is deleted, renamed or made private takes its history
along. Not hypothetical for twenty personal repos: one was already missing from the machine that
measured this.

<b>It also biases the numbers while everything is up.</b> 62% of the corpus being one publisher's
house style is a sampling bias in every recall figure the project reports.

<b>Options, none obviously right.</b> <em>Vendor</em> the needed files into the repo &mdash; no
network, no third parties, but a corpus that no longer resembles a real tap. <em>Cache</em> the
clones in CI keyed on the taps file, so a disappearance degrades to a stale corpus rather than a red
gate, though a cold cache still fails. <em>Rebalance</em> so no single source exceeds some share,
costing corpus size and drawing an arbitrary line. <em>Fail soft</em> on N missing repos, which keeps
merges flowing but silently weakens the gate &mdash; the failure mode this line of work has been
removing. Not proposed: dropping or lowering the gate.

<b>Provenance.</b> The per-repo counts had to be printed to verify the pins in
[[eval-corpus-was-not-actually-pinned]]; the distribution was the surprise.

<b>Measured, and it eliminates one of the four options.</b> &ldquo;Fail soft on N missing repos&rdquo;
reads like the pragmatic choice. It is the dangerous one, because a corpus that loses a repo does not
get harder to pass &mdash; it gets easier. Same 91-query required set, one repo removed and everything
else identical: <code>all 20 &rarr; 10,152 entries, <b>0.852 / 0.473 / 0.605 / 0.657</b></code><br>
<code>minus sickn33 (62%) &rarr; 3,843, <b>0.885 / 0.593 / 0.711 / 0.746</b></code><br>
<code>minus that and ECC (78%) &rarr; 2,227, <b>0.967 / 0.659 / 0.769 / 0.814</b></code><br>
<code>minus LessUp (holds golden targets) &rarr; 9,682, <b>0.676 / 0.374 / 0.483 / 0.523</b></code><br>
<code>floors &rarr; 0.780 / 0.400 / 0.520 / 0.580</code>

So dropping a <em>scale</em> repo sails through all four floors having measured a third of the
intended corpus, and dropping a repo that carries golden targets fails all four in a way
indistinguishable from &ldquo;this PR broke retrieval&rdquo;. Fail-soft is unsafe in both directions.
The same table also kills <em>rebalancing by trimming</em>: cutting the big repo to fix the 62% would
inflate every published number. Diluting concentration means adding breadth, which is
[[eval-corpus-is-96x-smaller-than-a-real-install]]'s problem, not this one.

<b>What shipped.</b> The corpus is now <em>verifiable</em> and its unavailability
<em>distinguishable</em>. Each <code>taps.txt</code> row carries an entry count beside its SHA, and
<code>--ensure</code> refuses to leave a corpus that does not match &mdash; so the "quietly measured
3,843 entries" case above cannot reach the scorer. Unreachable repos exit <b>75</b> (EX_TEMPFAIL)
rather than 1, and every failing repo is named rather than just the first, so a third party's outage
stops reading as a regression here. CI restores the clones from a cache keyed on the tap list's
content, which is what actually stops one deleted repository reddening every open PR; only
third-party bytes are cached, never anything this repo derives, and there are no
<code>restore-keys</code> &mdash; a near-miss restore would carry taps this file no longer pins, and
the index is built from <em>every configured tap</em>. That last hazard is now checked directly:
a <code>BOOST_HOME</code> holding taps outside the list is a hard failure, which is exactly what
[[local-boost-install-is-not-the-eval-corpus]] walked into from the other side.

<b>A second, closer bug fell out of it.</b> The sentinel that makes a local <code>make eval</code>
fast was <em>empty</em> &mdash; it meant &ldquo;some corpus was built here&rdquo;. So editing
<code>taps.txt</code> (moving a pin, adding a repo) left the previous corpus in place and scored it
against the new file's baseline, silently, for as long as the sentinel survived. It now carries the
tap list's digest, so an edit is a cache miss.

<b>What did not ship, and why.</b> The 62% itself. There is no honest way to fix it by removing
anything, and adding breadth changes every published number and needs its own re-baselining. What is
enforced instead is a ratchet: <code>MAX_SHARE</code> fails the audit if any single publisher goes
above 65%, ~3 points over today's measured 62.1%. That stops it getting worse without pretending it
is fixed.
