---
id: mypy-strict-mode-for-commands
board: code
section: health
status: shipped
category: Testing · Type
complexity: M
impact: High
wow: 3
note:
order: 11
owner: loop/mypy-check-command-bodies
pr: 309
title: mypy's default mode skips untyped command bodies
---
<code>[tool.mypy]</code> in <code>pyproject.toml</code> sets only <code>python_version</code>/
<code>files</code>, leaving mypy in its default permissive mode — a function with any untyped
parameter has its <em>body</em> skipped entirely. All 76 <code>cmd_*</code> functions across
<code>boost_cli/commands/*.py</code> take a bare <code>argv</code>, and a third have no return-type
annotation, so the required "zero mypy errors" lint gate isn't actually checking most of the CLI's
dispatch logic. Scoping <code>disallow_untyped_defs</code> (or at least
<code>check_untyped_defs</code>) to <code>boost_cli.commands</code> will surface a real backlog —
exactly what the gate is supposed to catch.
