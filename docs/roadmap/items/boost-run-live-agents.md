---
id: boost-run-live-agents
board: code
section: dx
status: planned
category: Interop
complexity: L
impact: High
wow: 5
note: 
order: 43
owner: 
pr: 
title: <code>boost run</code> — search → adapt → a live agent doing the task, in one command
---
The allure ceiling on <code>boost adapt</code> (#146, #163): it stops at <b>source you assemble</b>, and the adapted agent has a brain (prompt) but no <b>hands</b> (tools). Close both. <code>boost run &lt;skill&gt; [target]</code> = adapt → wire a default toolset (file read, ripgrep/shell, web) → execute on boost's model and stream the result. Opt-in like the conformance path (installs the framework + needs a key, so the zero-dep default holds). Two prerequisites ship with it: (1) <b>tool-wiring</b> — emit/attach the tools a skill needs (or declares) so the agent can act, not roleplay; (2) reuse the <a href="../adapters.html">adapt</a> renderer for the agent def. Pairs with <code>[[framework-adapter-multi-agent]]</code> so a skill like <code>rust-review</code> runs as a real crew. This is the screenshot: "one command → an expert agent audits your repo, on Claude, that you never wrote." <b>Working preview:</b> <code>examples/boost-run-prototype.sh</code> already does this by hand (adapt → wire a read_file tool → <code>Runner.run</code> on a file with planted bugs).
