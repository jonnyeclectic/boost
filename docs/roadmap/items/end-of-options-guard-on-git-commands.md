---
id: end-of-options-guard-on-git-commands
board: code
section: internals
status: next
category: Security
complexity: S
impact: Med
wow: 3
note: 
order: 6
owner:
pr:
title: End-of-options <code>--</code> guard on git commands
---
<code>clone_shallow</code>/<code>fetch</code>/<code>reset</code> pass the URL &amp; ref as positionals with no <code>--</code> separator (<code>core/gitutil.py:34–46</code>), so a value starting with <code>-</code> is parsed as a git option. <code>parse_spec</code> constrains most URL shapes, but adding <code>--</code> before positionals and rejecting <code>ext::</code>/<code>file::</code>/<code>fd::</code> transports closes the argument-injection surface as defense-in-depth.
