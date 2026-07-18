---
id: command-reference-docs-site
board: code
section: docsite
status: planned
category: Docs · Command reference
complexity: M
impact: High
wow: 4
note: Read the Docs–style
order: 10
owner:
pr:
title: Command reference documentation site
---
boost has no browsable command reference — help lives only in
           <code>--help</code> output and scattered README prose, so there's no
           versioned, searchable home for what each command does. Build a proper
           docs site in the shape of
           <a href="https://learning-python.readthedocs.io/en/latest/">learning-python.readthedocs.io</a>:
           a left-nav tree of commands, per-command pages (synopsis, flags,
           examples, exit codes), and full-text search. Generate the command
           pages from the CLI's own definitions so the docs can't drift from the
           code, and publish alongside the existing Pages site under the Aurora theme.
