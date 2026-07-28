---
id: make-lint-masks-actionlint-failures
board: code
section: dx
status: planned
category: Testing · Bug
complexity: S
impact: Med
wow: 4
note: a failing actionlint prints "not on PATH" and make exits 0
order: 60
owner:
pr:
title: <code>make lint</code> reports success when <code>actionlint</code> fails &mdash; and says it wasn't installed
---
<code>Makefile:64</code> guards the workflow linter like this:

<code>@command -v actionlint &gt;/dev/null 2&gt;&amp;1 &amp;&amp; actionlint || echo "actionlint not on PATH &mdash; skipping (CI enforces it)"</code>

Because <code>||</code> binds to the whole <code>&amp;&amp;</code> chain, the fallback fires in
<b>both</b> failure modes &mdash; actionlint absent, <em>and</em> actionlint present and reporting
findings. Reproduced with a stub that exits 1:

<code>actionlint: FAKE ERROR</code><br>
<code>actionlint not on PATH &mdash; skipping (CI enforces it)</code><br>
<code>make exit=0</code>

So a real workflow-lint failure is swallowed, and the message asserts something false &mdash; that
the tool is not installed, when it is installed and just failed. <b><code>make lint</code> and
therefore <code>make check</code> can never fail on actionlint.</b> CLAUDE.md calls
<code>make check</code> "the one gate that matters" and tells every agent to run it before calling
a change done; for this tool it returns green unconditionally, and the developer who reads the
output is told the opposite of what happened.

The local-versus-CI gap is wider than this one line. CI's required <code>lint</code> job runs
three workflow/security tools that <code>make lint</code> has no equivalent for at all:
<b>actionlint</b> (present but unfailable), <b>zizmor</b> and <b>gitleaks</b> (absent from the
Makefile entirely). No CI job invokes <code>make lint</code>, so the two lists are hand-maintained
duplicates with nothing checking they agree &mdash; which is how they drifted.

Minimal fix is to stop discarding the exit status:

<code>@if command -v actionlint &gt;/dev/null 2&gt;&amp;1; then actionlint; else echo "actionlint not on PATH &mdash; skipping (CI enforces it)"; fi</code>

The stricter option is to install actionlint in <code>make venv</code> and let absence itself
fail, so <code>make check</code> cannot report success while skipping a required gate. The same
masking idiom appears at <code>Makefile:143</code> (hyperfine) and <code>Makefile:167</code>
(node); neither is reached by <code>check</code>, so they are cosmetic by comparison, but they are
the same bug. Incidental drift found alongside: <code>CLAUDE.md</code> describes the lint recipe
as "18 commands" and it is 19.
