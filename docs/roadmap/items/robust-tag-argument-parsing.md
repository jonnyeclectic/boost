---
id: robust-tag-argument-parsing
board: code
section: internals
status: inflight
category: Maintainability
complexity: M
impact: Med
wow: 2
note: 
order: 16
owner: loop/robust-tag-parsing
pr:
title: Robust <code>tag</code> argument parsing
---
Because <code>-tag</code> looks like an option, <code>cmd_tag</code> calls <code>parse_known_args</code> then re-walks raw <code>argv</code> to reorder tokens (<code>info.py:575–584</code>) — fragile enough that the comment calls it "defensive". Replace with a positional-only sub-parser or an explicit <code>--add/--remove</code> design.
