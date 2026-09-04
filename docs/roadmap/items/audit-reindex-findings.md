---
id: audit-reindex-findings
board: code
section: internals
status: inflight
category: CLI · Bug
complexity: S
impact: Med
wow: 2
note: reindex --json names taps two ways in one object (reused vs reindexed)
order: 287
owner: loop/reindex-json-tap-names
pr:
title: "boost reindex: CLI audit findings (2026-08)"
---
<b>A truncated manifest download is reported as a broken manifest.</b> Already fixed &mdash; landed in <code>f77a04c</code> (#626, <em>fix(shards): stop reporting network and format problems as bad data</em>), which added the read-until-EOF loop and short-read error <code>shards.py</code>'s <code>_read_capped</code>/<code>_verify_complete</code> now describe. No further work needed here.

<b><code>reindex --json</code> names taps two ways in one object.</b> Still open as of this item's claim. <code>"reused"</code> held cache stems &mdash; <code>0xfurai__claude-code-subagents</code> (<code>rag.py:293-298</code>, <code>:313</code>) &mdash; while <code>"reindexed"</code> held tap names &mdash; <code>0xfurai/claude-code-subagents</code> (<code>rag.py:307</code>), so a script that set-differences the two lists saw every tap as changed. Fixed: <code>rag.build</code> now maps each reused safe name back to its tap name using the full <code>entries</code> list it already has in hand (every reused tap still has entries there, just not in <code>fresh</code>) rather than reaching for <code>registry.list_taps()</code>, so the mapping can't drift from what the build actually saw. A unit test asserts <code>set(reindexed) | set(reused)</code> equals the tap-name set entries carry. No flag text changes, so docs/commands.html needs no regeneration.

Found by the 2026-08 CLI audit (clusters <code>manifest-truncated-read</code>, <code>reindex-json-tap-names</code>); repro in the audit log.
