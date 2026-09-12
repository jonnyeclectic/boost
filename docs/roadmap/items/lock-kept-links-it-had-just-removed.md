---
id: lock-kept-links-it-had-just-removed
board: code
section: health
status: shipped
category: Bug
complexity: S
impact: Low
wow: 3
note: `boost profile use` unlinked four agents and `boost list` kept naming all four
order: 319
owner: fix/land-claims-fixes
pr:
title: The lock kept advertising links it had just removed
---
A skill's <code>agents</code> field is defined as the links measured from disk.
<code>boost quarantine</code> clears it when it removes them, and
<code>quarantine --release</code> recomputes it — the pair that makes the field mean what it
says.

<code>store.sideline</code> did neither. <code>boost profile use</code> set a skill aside,
deleted its symlinks, recorded <code>sidelined_by</code> so <code>doctor</code> and
<code>sync</code> would stop fighting the switch — and left the old <code>agents</code> list
standing. So <code>boost list --json</code> went on naming four agents for a skill none of them
could see. The state was right and the report was wrong, which is the harder kind to notice:
every command that <i>acts</i> on the sideline behaved correctly.

<code>sideline</code> now empties the list and <code>unsideline</code> records what it relinked,
which is exactly the <code>quarantine</code> / <code>--release</code> shape one function over.

Separately, <code>boost taps</code> said "1 taps · 3 items".
