---
id: BOOST-D12
board: design
track: motion
status: declined
impact: med
complexity: L
wow: 3
category: motion
ref: commands/discovery.py · search
order: 3
owner: design/resolve-d12
pr:
title: Stream search hits as they rank
---
<code>search</code> computes the full ranking, then prints the whole list at once. The premise that "the terminal sits blank, then floods" was measured on a 1,500-skill / 11,973-passage index and does not hold: the whole command is <strong>180&nbsp;ms</strong> end to end, of which the ranking — the part streaming would overlap — is <strong>11.8&nbsp;ms</strong>. The rest is <strong>70.7&nbsp;ms</strong> importing core modules and <strong>71.4&nbsp;ms</strong> loading the index, both of which finish <em>before</em> the first hit can be known. Streaming a <em>ranked</em> list is also structurally unavailable to BM25: the top hit is not known until every document is scored, and the renderer needs the widest name and the top score across all shown rows to size the meter column (<code>discovery.py</code>). Progressively revealing an already-complete 180&nbsp;ms result would add latency, not hide it. Parked rather than dropped: if motion work is wanted here the honest target is the 142&nbsp;ms of import + index load, not the 11.8&nbsp;ms of ranking.

<b>Declined, and re-measured first on a bigger index rather than closed on the old numbers.</b>
Over the pinned <b>10,152-entry</b> eval corpus, <code>boost search</code> is
<strong>260&ndash;300&nbsp;ms</strong> end to end. The shape is the same one that refuted the
premise, and it has not improved with scale: <code>26&nbsp;ms</code> Python startup +
<code>44&nbsp;ms</code> importing <code>boost_cli</code> + <code>~150&nbsp;ms</code> retrieval,
of which loading the 8.5&nbsp;MB index is <code>~33&nbsp;ms</code> before a single document has
been scored. Every one of those milliseconds is spent <em>before the first hit can be known</em>,
so there is nothing for a stream to overlap. The structural objection is unchanged and is not a
matter of degree: BM25 cannot name its top hit until every document is scored, and
<code>discovery.py</code> needs the widest name and the highest score across all shown rows to
size the meter column, so the first row cannot be drawn before the last one is known.

<b>Declining it does not discard the perf target.</b> ~70&nbsp;ms of fixed startup is real and
worth attacking &mdash; it is simply a code-board concern about lazy imports and index format,
not a motion one, and keeping it filed under a card about animating a list would put the work
behind the wrong question. <code>scripts/import_budget.py</code> already guards the part of it
that regresses most easily.

<b>One thing checked on the way, and it is a negative result worth recording.</b>
<code>rag._all_postings()</code> takes <b>1.7&nbsp;s</b> over this corpus &mdash; enough to be
alarming if anything interactive called it. Nothing does: its only callers are
<code>scripts/build_demo_index.py</code> and <code>rag._kept_docs</code>, which runs during an
incremental <em>rebuild</em>, where 1.7&nbsp;s sits inside a ~13&nbsp;s reindex. So there is no
hidden hot-path cost hiding behind the one this card measured.
