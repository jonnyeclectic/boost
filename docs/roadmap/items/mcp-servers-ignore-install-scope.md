---
id: mcp-servers-ignore-install-scope
board: code
section: dx
status: planned
category: Bug · MCP
complexity: M
impact: High
wow: 4
note: --scope project installs the skill into the repo and its MCP server machine-wide
order: 14
owner:
pr:
title: A project-scoped install registers its MCP servers <em>machine-wide</em>
---
<code>boost install &lt;skill&gt; --scope project</code> (or <code>--here</code>) is a promise about
blast radius: the skill lands inside this repo, committable, affecting nobody else's machine. The
MCP servers that skill declares do not keep that promise. They are registered at <b>user</b> scope
&mdash; globally, for every repo you open &mdash; whatever scope the skill itself was installed at.

The path is short and the gap is a missing argument. <code>_offer_mcp()</code> in
<code>commands/pkg.py</code> receives the whole <code>InstallResult</code>, so
<code>res.scope</code> is right there, and never reads it. It calls
<code>_register_mcp_server(name, spec, host)</code>, which takes no scope parameter at all, so
<code>mcpdecl.register_argv()</code> falls to its <code>scope="user"</code> default and boost shells
out <code>claude mcp add &lt;name&gt; --scope user …</code>. Nothing warns that the scope the user
asked for was not the scope they got.

<b>The repo-local machinery is already written, and nothing calls it.</b>
<code>mcpdecl.merge_into(existing, rows, skill)</code> merges declared servers into an
<code>.mcp.json</code> document &mdash; the committable, project-scoped file agents already read
(<code>mcpdecl.SIDECAR</code>). It returns a new document rather than mutating, never overwrites a
server the user configured by hand, and stamps each entry it adds with a <code>MARKER_KEY</code>
naming the skill that asked for it, precisely so a later uninstall can remove what boost wrote and
nothing else. It is covered by nine assertions in <code>tests/unit/test_mcpdecl.py</code> and has
<b>zero callers in <code>boost_cli/</code></b>. The install path shells out to the host CLI instead.

That marker matters because of the second half of the bug: <b><code>uninstall</code> never
unregisters anything.</b> Removing a skill sweeps its files and its symlinks and leaves the MCP
server registered, so a skill you installed once to try out keeps launching for every project you
open afterwards. Wiring <code>merge_into</code> gives cleanup something exact to reverse, which
shelling out to <code>mcp add</code> does not.

What the fix has to get right:

<b>Scope must flow, not be re-derived.</b> Thread <code>res.scope</code> from
<code>_offer_mcp</code> through <code>_register_mcp_server</code> into
<code>register_argv(..., scope=…)</code>. Both call sites of
<code>store.declared_mcp_servers</code> (the user-scope and project-scope install paths in
<code>core/store.py</code>) already know their scope; the command layer is where it gets dropped.

<b>Project scope should write the file, not shell out.</b> A registration that lives in
<code>.mcp.json</code> is reviewable in a diff, committable, and shared with the team &mdash; which
is the whole point of <code>--scope project</code>. Shelling out to <code>mcp add --scope
project</code> would work for a host that supports it, but produces nothing to review and re-opens
the per-host grammar problem <code>core/mcphost.py</code> exists to contain.

<b>Uninstall has to reverse exactly what was written.</b> Marker-keyed entries only &mdash; a
server the user added by hand, or one another skill declared, must survive. Note the asymmetry
already documented in <code>core/mcphost.py</code>: <code>claude mcp remove</code> finds a
user-scope server unaided, while <code>gemini mcp remove</code> defaults to project scope and will
report "not found in project settings" while leaving the user-scope entry in place. Removal needs
the scope it was registered at, which is another reason to record it rather than guess.

<b>The prompt should say where.</b> Today it asks "register N servers with Claude Code now?" and
names no scope. It should say which file or scope is about to change, because that is the decision
being made.

Related: [[mcp-aware-skills]] (which added the declaration format),
[[mcp-install-skips-the-injection-scan]] and [[mcp-register-names-server-before-env]].
