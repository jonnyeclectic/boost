# evals — boost's offline evaluation harness

A dev/CI quality gate for the retrieval stack, in the same family as mutation
testing: `make evals`, never a `boost` subcommand. Pure stdlib, no network, no
API key.

```bash
make evals              # run the harness and enforce the gate
make evals-baseline     # deliberately re-pin evals/baseline.json
make evals-golden       # regenerate golden_set.json after editing the queries
make evals-online       # + the pinned real-registry corpus and faithfulness
```

## Why this exists alongside `make eval`

The repo has two retrieval gates and they answer different questions.

| | `make eval` | `make evals` |
|---|---|---|
| corpus | pinned GitHub repos (`tests/eval/taps.txt`) | generated locally, 57 items* |
| network | required | none |
| labels | binary | graded 3 / 2 / 1 |
| metrics | recall@k, hit@1, MRR, nDCG@k | recall@5/@10, MRR, nDCG@5/@10 |
| significance | `ranx` t-test, opt-in extra, informational | stdlib paired bootstrap, **gated** |
| catches | "does a real skill come back for a real question" | "did the ranking get worse" |

`eval` grades against the live ecosystem, so it drifts when upstream repos do —
which is why its regression check is deliberately relaxed. This harness fixes
the corpus so the only thing that can move a number is the ranker.

\* 49 skills across 10 topic clusters, plus 4 rules and 4 workflows as ranking
pressure. Confirm the total the way boost sees it:

```bash
BOOST_HOME=$TMPDIR/boost-evals-home boost count     # -> available 57 (across 1 tap)
```

## Layout

| file | what it is |
|---|---|
| `metrics.py` | the arithmetic — recall@k, MRR, nDCG@k, paired bootstrap |
| `make_corpus.py` | generates the corpus; **item table is the source of truth** |
| `make_golden.py` | generates + validates `golden_set.json`; `--check` for drift |
| `golden_set.json` | 36 queries, 107 graded judgments (generated — don't hand-edit) |
| `baseline.json` | pinned per-query scores the bootstrap compares against |
| `run_evals.py` | sets up the sandbox, scores every arm, writes `results.json` |
| `faithfulness.py` | Ragas-methodology faithfulness for `explain` / `distill` |
| `../scripts/eval_gate.py` | reads `results.json`, enforces the thresholds |

The corpus and BM25 index are built into a disposable `BOOST_HOME` under the
system temp dir (`$TMPDIR/boost-evals-home`, override with `BOOST_EVALS_HOME` or
`--home`) — outside the repo on purpose, because it is itself a git repo and a
nested one confuses `git status`, coverage discovery, and mutmut's tree copy.

## The five metrics

- **recall@5 / recall@10** — of everything graded relevant, what fraction landed
  in the top k. Grades are binarized here (any grade ≥ 1 counts); recall asks
  "did we find it", not "did we order it well".
- **MRR** — 1/rank of the first relevant hit, averaged. Sensitive to the top of
  the list only, which is where users actually look.
- **nDCG@5 / nDCG@10** — DCG over ideal DCG, with the standard `log2(rank + 1)`
  discount and exponential graded gains (`2^rel − 1`, so a perfect hit is worth
  7 and a marginal one 1). This is the only metric that can tell a correct set
  of results in the wrong order from the right order.

## The grading scale

| grade | meaning |
|---|---|
| 3 | perfect — the skill the query is asking for |
| 2 | useful — a competent answer, not the best one |
| 1 | marginal — topically adjacent; better than an unrelated hit |
| — | absent from the label map, i.e. irrelevant |

Grading the tail matters: a query labeled with only its perfect answer teaches
nDCG nothing about the four results underneath it.

## How the gate works

`scripts/eval_gate.py` runs two independent checks and both must pass.

1. **Absolute floors** — each metric must clear a floor calibrated ~0.05 below
   the first measured run. This catches slow erosion across many merges, which a
   compare-to-last-commit check never notices.
2. **Significant regression vs the baseline** — a metric fails only when it drops
   by more than `--regression-eps` (0.02) **and** a paired bootstrap over the
   per-query deltas returns `p < 0.05`.

Requiring both conditions is the whole design. The two arms answer the same 36
queries, so pairing cancels out "this query is just hard" and leaves the effect
of the change; resampling those differences 10,000 times (seeded, so the p-value
is reproducible) asks how often a different draw of queries would have reversed
the sign. A drop that is large but not significant is one unlucky query. A drop
that is significant but tiny is a rounding change nobody should re-baseline for.
Only a drop that is both is a regression.

Accepting a genuine ranking change is `make evals-baseline` — its own commit,
which says why.

## Faithfulness

`explain` and `distill` generate prose from a `SKILL.md`; their shared failure
mode is overclaiming. Faithfulness measures it with the Ragas procedure —
decompose the answer into atomic statements, verify each against the source,
score supported/total — implemented directly on boost's `core.ai` bridge so the
harness stays dependency-free and grades the same prompts the shipped commands
use.

Two numbers are reported per sample, and the gap between them is the point:

| column | what it is |
|---|---|
| `judged` | the Ragas score over the **raw** model reply |
| `runtime guard` | what `boost explain` would actually do with that reply |

`boost explain` does not print whatever the model returns — `core/faithfulness.py`
scores it for grounding and falls back to the deterministic extractive summary
below a config-tunable threshold. Grading only the raw reply would answer a
question nobody asks: how faithful is text the user may never see. The guard
column costs no extra API calls (the sample already exists) and the run reports
how many generations would have been discarded.

The denominator is the number of statements **extracted**, never the number of
verdicts returned. A judge reply is capped at `max_tokens`, so dividing by the
verdicts would score 3/3 = 1.0 for an answer where 7 of 10 claims went
unexamined — the metric would read best exactly when the judge coped worst. A
short verdict list is a failed judging pass, not a score.

It **skips, never fails**, when there is no `claude` CLI and no
`ANTHROPIC_API_KEY`, and reports a status rather than a bare number so that
"could not measure" is never mistakable for "scored 0.0". Because it needs a
model it is not part of `make check`; run it via `make evals-online`.

`--faithfulness-scorer ragas` cross-checks the stdlib scorer against the
reference implementation by **delegating to `scripts/eval_explain.py`**, which
owns the ragas path (`make eval-explain`, plus its own CI workflow). That script
stays the ragas eval for the pinned real-registry corpus; this module is the
hermetic, key-free counterpart that also covers `distill`. Delegating rather
than copying is deliberate — an earlier draft duplicated its judge setup and
silently dropped its `RunConfig` timeout.

## Extending the golden set

1. Add a row to `QUERIES` in `make_golden.py` with a fresh id, the query as a
   user would actually type it, and a grade for **every** skill you would accept.
2. Run `make evals-golden` and commit both files. `make_golden.py --check` runs
   in `lint` and fails if they disagree.
3. Adding queries invalidates the baseline — run `make evals-baseline` in the
   same change and say so in the commit message.

Add corpus items the same way, in `make_corpus.py`'s `SKILLS` table. Resist the
temptation to reword a query because it scores badly: `q29` ("which alerts are
worth paging someone for") currently misses entirely, because BM25 does not stem
and the target skill says *alert*, not *alerts*. That is a real property of the
shipped ranker, and an eval you tune until it looks good has stopped being one.
