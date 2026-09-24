---
id: ci-summary-reports-the-wrong-coverage-gate
board: code
section: planned
status: shipped
owner: loop/ci-summary-coverage-gate
pr: ""
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
<b>Fixed.</b> The summary step now reads <code>fail_under</code> out of
<code>pyproject.toml</code> with <code>tomllib</code> and interpolates it, so the number cannot be
stated twice.
<code>tests/unit/test_coverage_gate_prose.py</code> pins both halves: the summary line must carry
the interpolation and no literal, and every file that states a coverage percentage as the rule in
force — the workflow, the <code>Makefile</code>, <code>CLAUDE.md</code>,
<code>CONTRIBUTING.md</code>, <code>README.md</code> and the two docs that answer an auditor — must
state the current one. It also executes the step's own expression, so a typo inside the shell
string fails here rather than in CI. Roadmap cards are out of scope by design: a card reporting
89% on one module is history, not the gate. Two more drifts turned up while wiring it —
<code>patch-coverage</code>'s comment called the project gate 80% (it now names no percentage at
all, so it cannot drift again) and the LangChain card stated the floor a contributor must not lower
as 80%.
