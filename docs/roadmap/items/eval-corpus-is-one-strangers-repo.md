---
id: eval-corpus-is-one-strangers-repo
board: code
section: internals
status: planned
category: Eval · Correctness
complexity: S
impact: High
wow: 3
note: one third-party repo is 62% of the gate's corpus, and if it disappears every PR goes red
order: 84
owner:
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
