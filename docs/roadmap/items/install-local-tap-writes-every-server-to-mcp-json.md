---
id: install-local-tap-writes-every-server-to-mcp-json
board: code
section: planned
status: shipped
category: Safety · MCP
complexity: S
impact: Med
wow: 2
note: --local writes a whole tap's declared servers into .mcp.json unasked, and with --no-mcp says nothing at all
order: 383
owner: loop/mcp-offer-cards
pr: 1325
title: "<code>install &lt;tap&gt; --local</code> records every declared MCP server in <code>.mcp.json</code> unasked — and <code>--no-mcp</code> hides it"
---
A project-scoped install records declared servers in the repo's <code>.mcp.json</code> with no
prompt (<code>store.record_project_mcp</code>), because the file is committed and reviewed. The
report already names them: <em>recorded N MCP servers</em>, followed by the list. Two gaps remain.

- <b>No consent step for a whole tap.</b> With a tap as NAME, one <code>-y</code> writes every
  server the tap's skills declare. That may be dozens of third-party commands, which every
  teammate's agent launches once the file is committed. There is also one report per skill
  rather than one list per run.
- <b><code>--no-mcp</code> hides the write instead of skipping it.</b> <code>install &lt;tap&gt;
  --local --no-mcp -y</code>, or the same with <code>BOOST_NO_MCP_OFFER=1</code>, still writes
  every server: the write has no <code>no_mcp</code> gate. But <code>_offer_mcp</code> returns
  before its project-scope branch, so nothing is printed. The dry run hides it too, because its
  <em>record</em> lines sit behind <code>offer_mcp</code>. This predates the tap install.

<b>Fix.</b> Either make <code>--no-mcp</code> skip the <code>.mcp.json</code> write, or always
report it. Then decide whether a whole-tap <code>--local</code> install asks once, listing every
server, before recording them.

<b>Shipped.</b> <code>--no-mcp</code> (or <code>BOOST_NO_MCP_OFFER</code>) now skips the
<code>.mcp.json</code> write at project scope, and the install says <em>srv not recorded in
.mcp.json (--no-mcp)</em>, naming whichever switch was used. A server already in the file is reported
as still there: the skip removes nothing. The lock row keeps <code>no_mcp</code>, so
<code>reinstall</code>, <code>update</code> and <code>sync</code> do not write what the install left
out, and an uninstall does not hand such a skill a server another skill recorded;
<code>install --local --force</code> without the flag records again. The dry run prints <em>mcp →
not recorded (--no-mcp)</em>, and a reinstall, update or bundle install that does record a server
names it. The whole-tap consent step is not built: it is a design decision for the maintainer.
