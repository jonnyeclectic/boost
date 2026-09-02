---
id: audit-install-local-writes-empties-the-repo-s-mcp-json-silently-of
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: S
impact: High
wow: 2
note: a file the user is told to commit is written and emptied with zero output
order: 212
owner: loop/mcp-project-scope-report
pr: 686
title: "<code>install --local</code> writes the repo's <code>.mcp.json</code> silently — the 'recorded N servers' report never runs"
---
Installing a skill that declares an MCP server with <code>--local</code> prints
<em>&ldquo;&#10003; copied into this repo &rarr; claude-code &middot; windsurf &middot; cursor &middot;
gemini / &#10003; project lock updated (.boost/skill-lock.json) / commit .boost/ to share these with
the team&rdquo;</em> — and nothing about MCP. Yet the repo's <code>.mcp.json</code> now contains
<code>mcpServers.demo-echo {command: npx, args, env, x-boost-skill}</code>. Verified live, both
directions: <code>uninstall --local</code> empties it to <code>{"mcpServers": {}}</code> with equally
zero output. A file the user is explicitly told to commit is edited without a word, and the commit
hint doesn't name it.

The report exists and is dead code. <code>_offer_mcp</code>'s project branch — the
<em>&ldquo;recorded N MCP servers in .mcp.json&rdquo;</em> lines at <code>pkg.py:137-157</code> — is
only called at <code>pkg.py:259</code>, but <code>_report_result</code>'s
<code>SCOPE_PROJECT</code> branch returns early at <code>pkg.py:243</code>, so the write
(<code>store.py:711</code> <code>register_project_mcp</code>, emptied at <code>:740</code>) always
happens unreported. The shipped roadmap card <code>mcp-servers-ignore-install-scope</code> presents
this report as working.

Verified fix, one call-ordering change: in <code>_report_result</code>, call
<code>_offer_mcp(res, no_mcp=no_mcp)</code> before the early return in the
<code>res.scope == SCOPE_PROJECT</code> branch (<code>pkg.py:243</code>); add a functional test
asserting the <em>&ldquo;recorded 1 MCP server in .mcp.json&rdquo;</em> line for a
<code>--local</code> install of a skill with a <code>.mcp.json</code> sidecar, plus a line on the
uninstall side. Docs: fix <code>docs/roadmap/items/mcp-servers-ignore-install-scope.md</code>, which
describes the recorded-report as reachable; no flag change, so <code>docs/commands.html</code> only
needs regenerating if a summary moves. Found by the 2026-08 CLI audit (cluster
<code>mcp-project-scope-report</code>); repro in the audit log.
