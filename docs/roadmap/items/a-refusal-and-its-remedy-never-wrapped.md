---
id: a-refusal-and-its-remedy-never-wrapped
board: code
section: planned
status: shipped
category: Polish · Bug
complexity: S
impact: Low
wow: 2
note: Every other emitter folds to the pane; the one that prints a failure printed its remedy at 173 columns…
order: 334
owner: loop/unwrapped-error-and-preview
pr: 951
title: A refusal and its remedy print past the pane, on the one line a user reads before acting
---
<b>Found by the review of release train 6.</b>
<code>output.err</code> — the renderer every <code>BoostError</code> reaches — printed its message and its
<code>hint:</code> line at whatever length they happened to be, at every pane width. On a machine holding
an API key with no vector store, <code>boost update --shards</code> and <code>boost reindex
--fetch-shards</code> printed a 111-column <code>Error:</code> line and a 173-column <code>hint:</code>
line at 40 columns, while <code>boost doctor</code>, <code>boost search</code> and <code>boost quickstart
--dry-run</code> folded the identical sentence correctly — the hint is one string, shared by
<code>dense.fix_hint</code>. The remedy carries two backtick command spans, and the pane it overflowed is
the one the user is about to type into.
<br><br>
The fix keeps the chrome/data split: the hint always folds, and the message folds only when the call
site says it is prose (<code>BoostError(..., wrap=True)</code>), because most messages are a label and
its path and folding those moves the path off the label that names it — eleven tests across five files
assert that adjacency. Five refusals that are sentences opt in: the two shard surfaces above, the
self-installing-registry refusal, the modified-since-install refusal (both copies) and the
deduplicate rollback.
<br><br>
The same review found the preview headline <code>boost quickstart --dry-run</code> prints: naming the
download size grew it past 60 columns, and it was the one line on that surface with no
<code>wrap=True</code>, though its live twin (<code>fetching …</code>) folds and every line printed under
it folds.
