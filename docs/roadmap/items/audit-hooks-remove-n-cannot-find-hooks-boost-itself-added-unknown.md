---
id: audit-hooks-remove-n-cannot-find-hooks-boost-itself-added-unknown
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: S
impact: High
wow: 2
note: remove -n says "no boost hook named" about a hook boost wrote, and exits 0
order: 207
owner: loop/hooks-remove-name-miss
pr:
title: "hooks remove <code>-n</code> cannot find hooks boost itself added (unknown events skipped, embedded <code># boost:</code> mangles the name)"
---
Two ways a boost-added hook becomes unremovable by its own name. First, unknown events:
<code>hooks add Bogus -c 'echo bogus' -n b1</code> warns and adds, but <code>hooks remove -n
b1</code> prints <em>"! no boost hook named 'b1' in project scope"</em> — exit 0, hook stays —
because with no event given <code>_remove</code> iterates <code>hookhost.events(host)</code>
(<code>hooks.py:147-148</code>), so an event that add accepted-with-warning is never visited. The
hook <em>is</em> removable by naming the event positionally (<code>hooks remove Bogus -n b1</code>),
but nothing says so and the error text is false. Same for a mis-cased <code>sessionstart</code>
added on gemini.

Second, embedded markers: <code>add PostToolUse -c 'echo x # boost:zzz' -n h9</code> stores
<code>echo x # boost:zzz # boost:h9</code>, and <code>claude_settings._hook_name</code> splits on
the <b>first</b> marker (<code>claude_settings.py:119-123</code>, <code>253-260</code>) — so
<code>hooks list</code> shows name <code>zzz # boost:h9</code> and command <code>echo x</code>, and
<code>remove -n h9</code> fails, exit 0. Both leave settings.json in a state boost wrote but cannot
remove by name, and the failed remove reports success to scripts.

Fix: in <code>hooks._remove</code> iterate the events actually present in <code>load(scope,
host=host).get('hooks', {})</code> when no event is given, and exit non-zero on "no boost hook
named"; in <code>core/claude_settings.py</code> use <code>rsplit(MARKER, 1)</code> in
<code>_hook_name</code> and the list display (or refuse marker-bearing commands in
<code>add_hook</code>). Unit tests for both. No <code>docs/commands.html</code> summary/flag change
unless behaviour text is reworded — regenerate if so.

Found by the 2026-08 CLI audit (cluster <code>hooks-remove-name-miss</code>); repro in the audit
log.
