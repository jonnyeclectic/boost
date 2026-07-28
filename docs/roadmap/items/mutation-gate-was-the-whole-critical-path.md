---
id: mutation-gate-was-the-whole-critical-path
board: code
section: pipeline
status: inflight
category: CI speed
complexity: M
impact: High
wow: 4
note: 26 min, 3x the next job, and charged twice per change
order: 60
owner: loop/mutation-speedup
pr:
title: The mutation gate <em>was</em> CI — 26 minutes, three times the next-longest job
---
Measured across twelve consecutive runs, the <code>mutation</code> job took
<b>20.6&ndash;39.2 minutes</b> (median ~27) while the next-longest job in the same run,
<code>tests (windows-latest, 3.12)</code>, took <b>8.6</b>. One job was the critical path,
and it was charged <em>twice</em> per change: once blocking the pull request, then again on
<code>main</code>, because <code>publish.yml</code> fires on <code>workflow_run</code> after
CI completes &mdash; so the PyPI release waited on it too. PR #278 merged at 20:52 and the
release landed at ~21:20, essentially all of it this gate.

The cost is ~10,502 mutants over 45 files in <code>boost_cli/core</code>, run 4-way parallel
(<code>max_children</code> defaults to <code>os.cpu_count()</code>; <code>ubuntu-latest</code>
is 4 vCPU). Generating them takes 5.3 seconds &mdash; the entire cost is executing the unit
suite ten thousand times. A measured local baseline: 1600s wall, <b>6.70 mutations/second</b>,
8850/10502 killed (84.3%).

<b>Two independent wins, because they apply to different pull requests.</b>

<em>Skip what cannot have changed.</em> Sampling the last 40 merged PRs, <b>38% touch neither
<code>boost_cli/</code> nor <code>tests/</code> nor the mutation configuration</b> &mdash; docs,
roadmap cards, other workflows. Their score is identical to the base commit's by construction,
and they were each paying 26 minutes to prove it. The relevance rule is deliberately wider than
<code>boost_cli/core/</code>: <code>setup.cfg</code>'s <code>also_copy</code> ships the whole
package into <code>mutants/</code> and the tests import it, so a change in
<code>commands/</code> can flip a core mutant. It also fails <em>safe</em> &mdash; no resolvable
base commit means run the full gate.

<em>Shard the rest.</em> <code>mutmut run</code> accepts fnmatch patterns over mutant names and
each source file owns a disjoint <code>mutants/&lt;path&gt;.meta</code>, so splitting by file
yields results that merge without any per-mutant reconciliation. Verified live:
<code>mutmut run 'boost_cli.core.nethttp.*'</code> ran 16/16 of that file's mutants and left
<code>store.py</code> at 0/1931. Six shards reach <b>5.44x</b> &mdash; and no further, because
<code>store.py</code> alone is 18% of all mutants and cannot be split. That ceiling is printed
by <code>plan --explain</code> rather than left to be rediscovered.

<b>The dead end, recorded so nobody repeats it.</b> Caching <code>mutants/</code> between runs
is the obvious first idea and it does not work in mutmut 3.6 &mdash; it actively destroys the
data it would need. <code>copy_src_dir</code> skips targets that already exist, so on a warm
tree <code>create_mutants_for_file</code> takes its <code>source_mtime &lt; mutant_mtime</code>
branch and resets <em>every</em> exit code to <code>None</code>. Demonstrated rather than
inferred: a file with 235/235 recorded results came back with <b>185 wiped</b> and the run
re-testing from zero. It would have looked like it was working while saving 5.3 seconds.

<b>What adversarial review caught, which local testing did not.</b> The first working
version sharded by <code>glob("*.py")</code> &mdash; non-recursive &mdash; while mutmut walks
<code>source_paths</code> with <code>os.walk</code>. A subpackage
(<code>core/rag/bm25.py</code>) would therefore be assigned to no shard; and because
<code>export-cicd-stats</code> <em>skips</em> a path with no <code>.meta</code> rather than
counting it unkilled, those mutants would drop out of <code>total</code> entirely and the
required check would report PASS over a subset. Fail-<em>open</em> &mdash; precisely inverting
the property the file's own docstring claimed. Two further finds: no fnmatch pattern can
address <code>__init__.py</code>, because mutmut rewrites <code>.__init__.</code> out of mutant
names (<code>boost_cli.core.__init__.*</code> matches nothing, and
<code>boost_cli.core.*</code> would swallow the whole package); and
<code>git diff --name-only</code> reports only a rename's <em>destination</em>, so moving
<code>core/x.py</code> to <code>docs/x.py</code> looked like a docs-only change and skipped the
gate. All three are now covered by tests that fail against the pre-fix code, and merge asserts
that every mutatable file was actually accounted for &mdash; so future layout drift reddens the
gate instead of quietly narrowing it.

<b>The trap this had to avoid.</b> <code>mutation</code> is a required status check
(<code>.github/required-checks.txt</code>). Path-filtering the job &mdash; the natural way to
implement "skip" &mdash; means GitHub creates no check run at all, and branch protection waits
for a status that never comes. This repository has already deadlocked that way twice. So the
required job always runs (<code>if: always()</code>) and inspects what the upstream jobs
actually did; <code>always()</code> on its own would have reported a failed shard as a green
required check. Merging likewise fails closed: mutmut counts an unrun mutant as "not checked"
inside <code>total</code>, and the gate divides by it, so a partial merge would quietly depress
the score instead of erroring.
