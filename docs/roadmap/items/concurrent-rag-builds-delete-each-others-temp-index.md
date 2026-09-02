---
id: concurrent-rag-builds-delete-each-others-temp-index
board: code
section: internals
status: shipped
category: Reliability · Bug
complexity: S
impact: High
wow: 3
note: two overlapping rag.build() runs share one .tmp name; the second unlinks the first's finished 644 MB file and the first dies on replace()
order: 308
owner: loop/postings-temp-race
pr: 693
title: "Two concurrent <code>rag.build()</code> runs delete each other's temp index"
---
Observed on a real 464-tap install during <code>boost update --shards</code>, at boost 1.2.80:
<code>FileNotFoundError: [Errno&nbsp;2] No such file or directory: '~/.boost/cache/rag_postings.sqlite.tmp' -&gt; '~/.boost/cache/rag_postings.sqlite'</code>, raised from <code>tmp.replace(final)</code> in <code>_write_postings</code>. <code>_write_postings</code> wrote every build to the <b>same</b> fixed temp path and unlinked it on entry, so a second build starting mid-flight deleted the first's <em>completed</em> file: A builds its 644&nbsp;MB temp &rarr; B enters and <code>unlink()</code>s it &rarr; A crashes on the swap. Confirmed by timestamps &mdash; the crash landed at 21:25 and a fresh <code>.tmp</code> appeared at 21:26, which then swapped in cleanly, so the index was never corrupt and the loser simply threw away several minutes of work and returned a crash report. It needs no exotic setup: <code>boost search</code> builds on a cold index, so two terminals is enough, and <code>_ingest_shards</code> rebuilds the index for any tap that moved. Fixed by giving each build its own <code>tempfile.mkstemp</code> name and unlinking it on failure &mdash; the same shape <code>util.atomic_write_text</code> already uses for every other file boost must not lose.
