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
<b>Pinning the eval corpus to commit SHAs fixed drift. It did not fix concentration, and it cannot
fix availability.</b> The twenty repositories in <code>tests/eval/taps.txt</code> resolve to 10,152
entries, and they are not remotely evenly sized:
<code>sickn33/antigravity-awesome-skills</code> is <b>6,309 of them &mdash; 62%</b>.
<code>affaan-m/ECC</code> is another 1,616 (16%). Two strangers' repositories are <b>78%</b> of what
this project measures retrieval quality against, and neither is a registry the project has any
relationship with.

<b>The failure mode is a red required check on every open pull request, at once.</b>
<code>scripts/ensure_eval_corpus.sh</code> runs under <code>set -euo pipefail</code> and clones each
row; a clone that fails raises and takes the script with it. Verified rather than reasoned about
&mdash; putting one unreachable repository in the list and running the script exits <b>1</b>, which
fails CI's <code>lint</code> job, which is a required context. A pinned SHA does not help here: a
commit still has to be <em>fetchable</em>, and a repository that is deleted, renamed, or switched to
private takes its history with it. Nothing about this is hypothetical for a corpus built from twenty
personal repositories &mdash; one of the twenty was already absent from the machine that measured
it.

<b>Why the concentration matters even while everything is up.</b> The gate's numbers are
substantially a statement about one person's repository. If they restructure it &mdash; not delete
it, just reorganise &mdash; the pin holds the old tree, so the gate keeps measuring a snapshot that
diverges further from anything real, which is [[eval-corpus-pins-have-no-refresh-path]]'s subject.
And the fact that 62% of the corpus is one publisher's house style is itself a sampling bias in
every recall number the project reports.

<b>Options, none obviously right.</b> <em>Vendor the corpus</em> &mdash; commit the SKILL.md files
the gate needs into the repo, removing the network and the third parties entirely, at the cost of
size and of a corpus that no longer resembles a real tap. <em>Cache it</em> &mdash; restore the
clones from a CI cache keyed on the taps file, so an upstream disappearance degrades to a stale
corpus instead of a red gate, though a cold cache still fails. <em>Rebalance</em> &mdash; drop or
split the two dominant repos so no single source exceeds some share, which costs corpus size and is
arbitrary about where the line goes. <em>Fail soft</em> &mdash; let the corpus build tolerate N
missing repos and report the shortfall, which keeps merges flowing but silently weakens the gate,
the failure mode this whole line of work has been removing.

<b>Not proposed:</b> dropping the gate, or lowering it. The measurement is worth having; what is
wrong is that its availability depends on people who have never heard of this project.

<b>Provenance.</b> Found while pinning the corpus in
[[eval-corpus-was-not-actually-pinned]] &mdash; the per-repo entry counts had to be printed to
verify the pins, and the distribution was the surprise.
