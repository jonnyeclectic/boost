---
id: mcp-offer-exempt-from-assume-yes
board: code
section: planned
status: planned
category: Safety · MCP
complexity: M
impact: Med
wow: 2
note: an exported BOOST_ASSUME_YES still registers every server a tap declares, machine-wide
order: 381
title: "Consider exempting the MCP registration offer from <code>BOOST_ASSUME_YES</code>"
---
<code>install -y</code> no longer answers the offer to register skill-declared MCP servers. A
typed <code>y</code> does, or running the printed <code>mcp add</code> lines. But
<code>BOOST_ASSUME_YES=1</code> still answers every confirm, this one included. A dotfiles script
or agent environment that <em>exports</em> it, rather than prefixing one command, registers
third-party commands for every project on the machine without anyone reading them.

<b>Option.</b> Give <code>output.confirm</code> an <code>env_bypass=False</code> mode for this prompt,
as <code>protocol open --gui</code> already does for its dialog. Then only a typed answer or the
printed command registers. This changes shipped env-var behaviour, so it needs a deprecation
line first. The 2026-11-06 design review ranked the pinned-consent variant
(<code>--register-mcp SERVER@DIGEST</code>) second, because of its cost.
