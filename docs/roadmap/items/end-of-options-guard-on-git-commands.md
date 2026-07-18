---
id: end-of-options-guard-on-git-commands
board: code
section: shipped
status: shipped
category: Security
complexity: S
impact: Med
wow: 3
note: transport allow-list + -- guard
order: 8
owner: loop/gitutil-transport-guard
pr:
title: End-of-options <code>--</code> guard on git commands
---
<code>clone_shallow</code> passed the clone URL as a positional with no
           <code>--</code> separator, so a value beginning with <code>-</code>
           could be read as a git flag, and git's remote-helper transports
           (<code>ext::sh -c …</code>, <code>file::</code>, <code>fd::</code>)
           can execute arbitrary commands straight from a URL. Now it refuses
           those transports outright and passes <code>--</code> before the URL
           so option parsing can't be hijacked — argument-injection
           defense-in-depth beside <code>registry.parse_spec</code>. Kept scoped
           to the one primitive that takes a user-influenced URL (the refs in
           <code>pull</code>/<code>reset</code> are constants, and <code>--</code>
           there would wrongly mean a pathspec). Six tests, mutation-verified.
