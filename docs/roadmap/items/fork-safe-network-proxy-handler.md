---
id: fork-safe-network-proxy-handler
board: code
section: health
status: shipped
category: Reliability · Network
complexity: S
impact: Med
wow: 3
note: avoid macOS _scproxy Obj-C path
order: 9
owner: loop/fork-safe-proxy
pr: 115
title: Fork-safe network layer — explicit <code>ProxyHandler</code>
---
<code>core/ai.py</code> and <code>core/embed.py</code> call
           <code>urllib.request.urlopen</code> with the default opener, which on
           macOS runs <code>getproxies_macosx_sysconf()</code> →
           <code>_scproxy</code> → SystemConfiguration/CoreFoundation — an
           Obj-C path that is <strong>not fork-safe</strong> and aborts on the
           child side of a <code>fork()</code>. Harmless in today's single-process
           CLI, but fragile if boost ever runs post-fork (a future multiprocessing
           worker, or an embedding host). Build the opener with an explicit
           <code>ProxyHandler</code> honoring <code>HTTP(S)_PROXY</code>/<code>NO_PROXY</code>
           so network calls never touch the Obj-C proxy machinery — deterministic
           and fork-safe.
