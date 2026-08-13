---
id: shards-pipeline-never-produced-a-shard
board: code
section: internals
status: shipped
category: Build · Bug
complexity: M
impact: High
wow: 4
note: two scheduled runs, 0 artifacts — 40 of 60 jobs tapped a bare SHA, and the other 20 hit an export that cannot work
order: 105
owner: fix/shards-pipeline
pr:
title: The shards workflow has never once produced a shard
---
<code>shards.yml</code> publishes prebuilt dense-vector shards so a keyless user gets semantic search
without paying to embed the catalogue — measured at <b>~1.2&nbsp;s/chunk</b> on CPU, 74 minutes for
743 entries, which is what makes step 2 of the keyless epic a requirement rather than an
optimisation. It has run twice on its weekly schedule, <b>2026-08-02</b> and <b>2026-08-09</b>, and
uploaded <b>nothing</b> either time. Two independent bugs, one in the workflow and one in the engine,
and a scheduled job is exactly where two of those can sit unnoticed: nobody is waiting on a cron.

<b>First bug — the matrix is fields, not rows.</b> A <code>tests/eval/taps.txt</code> row is
<code>owner/repo &lt;40-char sha&gt; &lt;entry count&gt;</code>, and the plan step built its matrix
with <code>grep -v '^#' tests/eval/taps.txt | tr '\n' ' '</code> and then split on whitespace. That
does not split the file into rows, it splits it into <b>fields</b>: twenty registries became a
<b>sixty</b>-entry matrix — twenty repos, twenty bare SHAs and twenty integers, each dispatched to a
job that ran <code>boost tap</code> on it. The run is full of <code>build (18)</code>,
<code>build (1616)</code> and
<code>build (b29e7cf65e5cb78a5ac33d582270551bc74a14eb)</code>. Two thirds of the fleet could never
do anything but fail.

<code>scripts/eval_corpus.parse_taps</code> already parses this format correctly and is already
tested — the workflow had reimplemented it in one line of shell and got it wrong. It now calls
<code>--list-repos</code>, a new flag that prints one name per line, so the row/field distinction is
made once in tested Python instead of re-decided in <code>bash</code>. Deliberately <i>not</i>
<code>--list</code>, which also prints the SHA and count: a caller that splits <i>that</i> on
whitespace reproduces the bug exactly.

<b>Second bug — the export cannot succeed, on any machine.</b> The twenty real registries got past
<code>tap and embed</code> and died in <code>export the shard</code> with
<code>no vectors for 'anthropics/skills'</code>, whose hint reads <i>build them first with
<code>boost reindex --dense</code></i> — the step that had just run, green, in the line above.
<code>dense.export_shard</code> opened the store with a <b>plain</b> <code>sqlite3</code> connection
on the stated theory that it "reads <code>chunks</code>, <code>meta</code> and the stored blobs, all
ordinary tables". True of the first two; false of the third. <code>vec_chunks</code> is a
<b><code>vec0</code> virtual table</b>, so the join raises <code>no such module: vec0</code> — always,
every tap — and <code>except sqlite3.Error</code> turned that into <code>chunks: []</code>.

Proven rather than reasoned: build a store through the real path, reopen it plainly, and the join
raises <code>OperationalError: no such module: vec0</code>. The comment was an accurate description
of an intention and an inaccurate one of the code.

<b>Why the test suite was no help — the fixture disagreed with production in the one way that
mattered.</b> Every shard test hand-builds its store with <code>CREATE TABLE vec_chunks</code>, an
<i>ordinary</i> table, and <code>with_backend</code> patches <code>_connect</code> to a plain
connection. Both are fair shortcuts for tests about validation. Together they mean no test in that
file ever met a virtual table, so <b>twenty passing tests coexisted with a feature that had never
worked</b>. There is even a class named <code>TestWorksWithoutTheExtension</code> asserting the
false claim — written, its docstring says, after an earlier version shipped broken the opposite way.
That is the shape to remember: the first fix traded a failure that was loud for one that was silent,
and the fixture blessed it.

<b>Fixed by separating two states the old code collapsed.</b> <code>chunks</code> is an ordinary
table and always readable, so it can answer "are there rows for this tap at all?" before the join is
attempted. No rows means the shard is empty and <i>"build them first"</i> is right. Rows present but
unreadable is a different problem with a different fix, and now says so, naming the
<code>sqlite-vec</code> extension and stating that <b>no re-embedding is required</b> — the rows are
intact. Sending someone back to a 74-minute embed to solve a missing dependency is the part that
cost two runs.

<b>Both halves are pinned, and one of them runs without the extra.</b>
<code>test_dense_shard_real_schema.py</code> builds through <code>_ensure_schema</code> and the real
<code>vec0</code> table — the only test here that failed before the fix — but it <i>skips</i> without
<code>sqlite-vec</code>, which would leave a bare runner blind.
<code>test_dense_shard_unreadable_vectors.py</code> pins the same contract with nothing installed, by
presenting the store as a plain connection sees it: ordinary tables readable, vector relation not
resolving. Both were run against the pre-fix code and both go red, so neither is decorative.
