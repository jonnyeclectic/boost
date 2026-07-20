---
id: mcp-startup-self-harden-fork-safety
board: code
section: compat
status: shipped
category: Compatibility · macOS
complexity: S
impact: Med
wow: 3
note: self-seed no_proxy at startup
order: 9
owner: loop/mcp-startup-fork-safety
pr: 162
title: Self-harden every boost process against the macOS fork-safety abort
---
The launch-env fix (<a href="#mcp-launch-objc-fork-safety">#119</a>) only
           protects hosts that register boost <em>through boost</em>, which
           injects <code>no_proxy=*</code>. A host that <code>fork()</code>s into
           <code>boost mcp --stdio</code> from a stale or hand-written config —
           or any stray default-opener call inside the process — is still one
           <code>getproxies()</code> away from the macOS <code>_scproxy</code>
           Obj-C <code>SIGABRT</code>. Close the gap from inside: at the top of
           <code>main()</code>, seed <code>no_proxy</code> for the current
           process (only when no <code>*_proxy</code> env is already set, so a
           real proxy is never clobbered) so the stdlib default
           <code>getproxies()</code> short-circuits on
           <code>getproxies_environment()</code> and never consults
           SystemConfiguration. Belt-and-suspenders atop the
           <code>nethttp</code> opener (<a href="#fork-safe-network-proxy-handler">#115</a>).
