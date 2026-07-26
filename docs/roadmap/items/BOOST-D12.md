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
<code>search</code> computes the full ranking, then prints the whole list at once. The premise that "the terminal sits blank, then floods" was measured on a 1,500-skill / 11,973-passage index and does not hold: the whole command is <strong>180&nbsp;ms</strong> end to end, of which the ranking — the part streaming would overlap — is <strong>11.8&nbsp;ms</strong>. The rest is <strong>70.7&nbsp;ms</strong> importing core modules and <strong>71.4&nbsp;ms</strong> loading the index, both of which finish <em>before</em> the first hit can be known. Streaming a <em>ranked</em> list is also structurally unavailable to BM25: the top hit is not known until every document is scored, and the renderer needs the widest name and the top score across all shown rows to size the meter column (<code>discovery.py</code>). Progressively revealing an already-complete 180&nbsp;ms result would add latency, not hide it. Parked rather than dropped: if motion work is wanted here the honest target is the 142&nbsp;ms of import + index load, not the 11.8&nbsp;ms of ranking.
