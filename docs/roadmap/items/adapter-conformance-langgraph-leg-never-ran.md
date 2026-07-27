---
id: adapter-conformance-langgraph-leg-never-ran
board: code
section: pipeline
status: shipped
category: Bug
complexity: S
impact: Med
wow: 3
note: shipped broken, first run exposed it
order: 48
owner: loop/adapter-conformance-install
pr:
title: <code>adapter-conformance</code>'s LangGraph leg never passed — a quoted matrix value
---
The install step ran
<code>pip -q install "${{ matrix.pip }}"</code>. Quoting is correct for the two legs
whose matrix value is a single token (<code>crewai[anthropic]</code>,
<code>openai-agents[litellm]</code>) — the brackets would otherwise be shell globs.
But the LangGraph leg's value is a requirement <em>list</em>,
<code>langgraph langchain-anthropic</code>, so the quotes handed pip one bogus
requirement and it refused before installing anything:
<code>ERROR: Invalid requirement: 'langgraph langchain-anthropic'</code>.

The leg landed 2026-07-22 and the workflow was <code>schedule</code>/<code>workflow_dispatch</code>
only, so nothing exercised it on its own pull request — the first Monday cron was
its first execution ever, five days later, and it has a 0% pass rate. It read as
upstream framework drift; it was never that. Reproduced locally, and with the
step fixed the whole leg passes end to end against live PyPI: langgraph 1.2.9 +
langchain-anthropic 1.5.2 resolve clean, <code>boost adapt --to langgraph</code>
renders, and the factory builds a real
<code>langgraph.graph.state.CompiledStateGraph</code>.

Fix: pass the spec through <code>env:</code> (rather than inlining a
<code>${{ }}</code> expansion into <code>run:</code>, the shape zizmor flags) and
let it word-split under <code>set -f</code>, which keeps the <code>[extra]</code>
brackets literal — without it, <code>crewai[anthropic]</code> glob-expands against
any matching filename. Also added a narrow <code>pull_request</code> trigger on
<code>adapters.py</code> and this workflow, so an edit to the thing under test is
tested on the PR that makes it. That trigger is path-filtered, so it must stay out
of the required-check list: a required context that does not report on a PR leaves
it pending forever.
