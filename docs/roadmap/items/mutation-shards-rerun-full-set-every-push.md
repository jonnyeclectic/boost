---
id: mutation-shards-rerun-full-set-every-push
board: code
section: pipeline
status: planned
category: CI · Performance
complexity: M
impact: Med
wow: 2
note: a re-push repays six ~20-min shards from zero; mutmut's .meta already holds the answers
order: 307
owner:
pr:
title: "Mutation shards re-run <em>every</em> mutant on every push of the same PR"
---
<b>&ldquo;Mutation shard actions take about 20 minutes and re-run with each
commit.&rdquo;</b> The user's words, and the workflow agrees: six
<code>mutation-shard</code> matrix jobs (<code>ci.yml:504</code>,
<code>timeout-minutes: 45</code>, ~20 min each in practice; the header comment
prices the unsharded gate at ~26 min) each run their slice of the ~10.5k mutants
over <code>boost_cli/core</code> from zero on every push. Two mitigations
already exist &mdash; don't re-file them: <code>mutation-scope</code>
(<code>ci.yml:461</code>, <code>is_relevant</code> at
<code>scripts/mutation_shards.py:685</code>) skips the whole gate when a PR
touches nothing mutation-relevant (38% of merged PRs), and the workflow
concurrency group (<code>ci.yml:52</code>) cancels a superseded push's run.
Neither helps the common case: the second, third, fourth push of a real code PR
each pays the full six-shard bill again.

What a re-push repays, verified: each shard re-does checkout at
<code>fetch-depth: 0</code>, <code>setup-python</code> 3.14,
<code>python -m venv</code> plus the hash-pinned
<code>pip install -r requirements/mutation-tools.txt</code>
(<code>ci.yml:536</code>), and mutmut's clean run of the covering suite before
the first mutant. Results already flow per file: mutmut writes one
<code>mutants/&lt;path&gt;.meta</code> per source file
(<code>exit_code_by_key</code>, <code>durations_by_key</code>, &hellip; &mdash;
the exact maps <code>cmd_merge</code> unions,
<code>scripts/mutation_shards.py:545</code>); each shard uploads
<code>mutants/boost_cli/core</code> as artifact <code>mutation-shard-N</code>
(<code>ci.yml:575</code>), the required <code>mutation</code> job downloads
<code>mutation-shard-*</code>, merges, and <code>mutation_gate.py:47-49</code>
divides killed by total&nbsp;&minus;&nbsp;skipped from
<code>export-cicd-stats</code>. But nothing carries any of it to the next push
&mdash; there is no <code>actions/cache</code> in any mutation job (the only
caches in ci.yml are the eval corpus and the BGE weights).

The proposal is the shards manifest's carry-forward shape, one level down:
<code>actions/cache</code> the <code>mutants/</code> results in each shard job.
mutmut 3 re-runs only mutants with no recorded exit code and regenerates a
file's mutants when its source changes (per-source hashing &mdash; that reuse
semantics is from mutmut's docs, not re-verified against the 3.7.0 pin here;
the package isn't installed locally). Key = shard index + Python version + a
hash of exactly the scope job's relevance list <em>minus the sources</em>:
<code>tests/**</code>, <code>setup.cfg</code>, <code>pyproject.toml</code>,
<code>requirements/mutation-tools.txt</code>,
<code>scripts/mutation_*.py</code> (<code>RELEVANT_PREFIXES</code>,
<code>mutation_shards.py:674</code>). Sources stay out of the key on purpose
&mdash; mutmut's per-file hash is the second reuse level, the same two-level
shape as dense reuse (commit, then digest). And <b>no restore-keys</b>: a
prefix restore would resurrect exit codes recorded under different tests or
pins, and mutmut trusts a recorded result rather than re-proving it. An inexact
match must miss and pay the full run &mdash; the merge already fails closed on
any mutant left unrun because mutmut counts it inside <code>total</code>
(<code>mutation_shards.py</code> header), so any skip scheme must carry results
forward, never shrink the denominator.

Alternative worth pricing: per-file <code>.meta</code> artifacts keyed by
source content digest, carried forward fail-closed in the merge job the way
<code>publish_shards.py manifest --carry-forward</code> reuses unchanged
registries &mdash; <code>cmd_merge</code> already unions per-file maps and
refuses on any <code>None</code>, so a digest-gated carry-in is a small
extension of the existing fail-closed path. The bound stays honest either way:
a warm re-push still pays checkout, setup-python, the venv install and the
clean suite run per shard, so a source-only re-push lands at an
<em>estimated</em> ~5&ndash;8 min a shard against ~20 today &mdash; never zero
&mdash; and a push touching <code>tests/**</code> or the pins misses the key
and pays the full run by design. Filed from the user's request during the
2026-08 CLI audit follow-up; verified against ci.yml and scripts/ 2026-08-31.
