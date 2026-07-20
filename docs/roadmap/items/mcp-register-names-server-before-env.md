---
id: mcp-register-names-server-before-env
board: code
section: compat
status: shipped
category: Bug · MCP
complexity: S
impact: Med
wow: 2
note: unbreak `boost mcp register`
order: 18
owner: loop/mcp-register-argorder
pr:
title: Order the server name before -e flags in `boost mcp register`
---
<code>boost mcp register</code> shelled out to
<code>claude mcp add --scope user -e OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES -e
no_proxy=* boost -- …</code> — the <code>-e</code> flags <em>before</em> the
server name. But <code>claude</code>'s <code>-e</code> is variadic, so it
swallowed <code>boost</code> as a third env var and aborted with
<code>Invalid environment variable format: boost</code>, making the one-command
install path fail outright on macOS. Reordered to
<code>claude mcp add boost --scope user -e … -- …</code> (the
<code>add &lt;name&gt; [options] -- &lt;command&gt;</code> form), so the name is
consumed as the positional before <code>-e</code> can grab it. A regression
test pins <code>name &lt; first -e</code> so a future reorder can't silently
re-break it.
