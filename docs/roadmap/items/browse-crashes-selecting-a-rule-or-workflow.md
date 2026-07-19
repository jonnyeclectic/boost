---
id: browse-crashes-selecting-a-rule-or-workflow
board: code
section: shipped
status: shipped
category: Bug · UX
complexity: S
impact: Med
wow: 2
note: user-reported crash, fixed
order: 3
owner: loop/fix-browse-crash
pr: 118
title: <code>browse</code> crashes when you pick a rule or workflow
---
<code>cmd_browse</code> lists <em>every</em> catalog entry — skills, rules
<b>and</b> workflows — then called <code>store.install(picked)</code>
unconditionally, so selecting a rule or workflow raised
<code>… is a workflow, which boost indexes but cannot install yet</code> and the
TUI exited with a fatal <code>Error:</code> after the user had already navigated
and chosen (reported from a real <code>boost browse</code> session on
<code>AGENT-playbook-to-automated-agent-workflow</code>). Fixed in <b>#118</b>:
the install call now catches <code>BoostError</code> and renders the message +
hint as a friendly non-fatal notice (exit 0), so a non-skill pick — or an
already-installed / pinned skill — no longer crashes the browser. Covered by a
regression test that picks a workflow and asserts no fatal exit.
