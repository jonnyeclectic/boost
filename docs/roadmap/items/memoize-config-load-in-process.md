---
id: memoize-config-load-in-process
board: code
section: internals
status: inflight
category: Performance
complexity: S
impact: Med-High
wow: 3
note: 
order: 4
owner: loop/memoize-config
pr:
title: Memoize <code>config.load()</code> in-process
---
Every <code>config.get()</code> re-reads <code>config.json</code> and runs a recursive <code>deepcopy</code> of <code>DEFAULTS</code> (<code>core/config.py:80–102</code>). It's called all over hot paths — <code>ai.enabled</code>, per-skill <code>enabled_agents</code> in sync loops, log-level and policy checks — so one command triggers <b>dozens of full reads + deep-copies</b>. Cache the load, invalidate on <code>save</code>.
