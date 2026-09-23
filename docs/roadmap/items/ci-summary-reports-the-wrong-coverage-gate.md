---
id: ci-summary-reports-the-wrong-coverage-gate
board: code
section: planned
status: planned
category: CI · Docs
complexity: S
impact: Low
wow: 1
note: The summary a maintainer reads without opening the log says the gate is 80% when it is 90%…
order: 338
title: The CI job summary reports the coverage gate as 80% when it is 90%
---
<b>Found by the audit of the repo's own automation.</b> The <code>tests</code> job's summary step in
<code>.github/workflows/ci.yml</code> prints the measured percentage beside a hard-coded
<code>gate: 80%</code>, while the gate that actually applies is <code>fail_under = 90</code> in
<code>pyproject.toml</code>. So a run at 90.4% reads as comfortably clear when it is four tenths of a
point from red. The summary is the one place the number is read without opening the log.
<br><br>
<b>Fix.</b> Read the threshold from <code>pyproject.toml</code> rather than restating it, and pin the
two together in <code>tests/unit/test_eval_corpus.py</code>'s style — the repo already fails the
build when CI and the Makefile state a floor differently.
