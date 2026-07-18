---
id: frontmatter-scalar-over-coercion
board: code
section: internals
status: planned
category: Correctness
complexity: S
impact: Low
wow: 2
note: 
order: 18
owner:
pr:
title: Frontmatter scalar over-coercion
---
<code>_scalar</code> turns <code>no</code>/<code>on</code>/<code>off</code>/<code>null</code> into bool/None (<code>core/frontmatter.py:32–53</code>), so a tag or name literally equal to one of those parses to the wrong type and leaks into search/ranking meta. Restrict boolean coercion to <code>true</code>/<code>false</code>.
