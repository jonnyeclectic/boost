---
id: BOOST-D12
board: design
track: motion
status: proposed
impact: med
complexity: L
wow: 3
category: motion
ref: commands/discovery.py · search
order: 3
owner:
pr:
title: Stream search hits as they rank
---
<code>search</code> computes the full ranking, then prints the whole list at once — the terminal sits blank, then floods. Stream the top hits as they're scored so the first result paints almost immediately. Perceived latency drops even when total time is unchanged.
