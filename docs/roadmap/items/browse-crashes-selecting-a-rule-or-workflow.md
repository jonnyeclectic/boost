---
id: browse-crashes-selecting-a-rule-or-workflow
board: code
section: next
status: inflight
category: Bug · UX
complexity: S
impact: Med
wow: 2
note: user-reported
order: 3
owner: loop/fix-browse-crash
pr:
title: <code>browse</code> crashes when you pick a rule or workflow
---
<code>cmd_browse</code> lists <em>every</em> catalog entry — skills, rules
<b>and</b> workflows (<code>commands/discovery.py:791</code>) — then calls
<code>store.install(picked)</code> unconditionally
(<code>discovery.py:804</code>). Only <code>skill</code> installs, so selecting a
rule or workflow raises
<code>… is a workflow, which boost indexes but cannot install yet</code> and the
TUI exits with a fatal <code>Error:</code> after the user has already navigated
and chosen. Reported from a real <code>boost browse</code> session on
<code>AGENT-playbook-to-automated-agent-workflow</code>. Fix: keep non-installable
kinds browsable but handle a non-skill pick gracefully (a friendly "search/tap
only" message, stay put or exit 0) instead of crashing — mirror how
<code>store.install</code> already distinguishes the three item kinds.
