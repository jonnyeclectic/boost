---
id: mcp-launch-objc-fork-safety
board: code
section: compat
status: shipped
category: Compatibility · macOS
complexity: S
impact: Med
wow: 3
note: OBJC_DISABLE_INITIALIZE_FORK_SAFETY
order: 9
owner: loop/mcp-fork-safety
pr: 119
title: Harden <code>boost mcp</code> launch against macOS Obj-C fork aborts
---
On macOS, a host that spawns <code>boost mcp --stdio</code> via <code>fork()</code>
           can abort on the child side pre-<code>exec</code> when Obj-C is touched
           post-fork (CFPreferences / <code>_scproxy</code> proxy lookup) — the
           classic <em>"crashed on child side of fork pre-exec"</em>
           <code>SIGABRT</code>. Not boost's own code (it aborts before boost
           runs), but boost can make its integration robust: when registering the
           MCP server (<code>boost mcp register</code> / the emitted client
           config), set <code>OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES</code> (and
           <code>no_proxy=*</code>) in the launch environment so the host's fork
           into boost can't trip the Obj-C fork-safety abort. Document it for
           hosts that launch boost directly.
