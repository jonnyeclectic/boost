---
id: search-never-notices-a-new-tap
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: High
wow: 4
note: search said "no matches" for a skill `boost info` described from the same machine
order: 93
owner: loop/rag-index-stale-after-tap
title: <code>boost search</code> never noticed a tap added after the first search
---
<code>boost tap X</code> followed by <code>boost search</code> could not find anything in
<code>X</code> — not until the user happened to run <code>boost reindex</code>, a command nothing
told them to run. Worse than a miss: search answered <b>"no matches"</b> and suggested
<code>boost discover</code> to go searching GitHub, for a skill sitting on the user's own disk that
<code>boost info</code> would describe on request.

<b>Reproduced before it was diagnosed</b>, in a throwaway <code>HOME</code> with two fixture taps:

<code>boost tap fixB</code> &rarr; <i>"✓ Tapped fixB (6 skills)"</i> &middot;
<code>boost info zeppelin-telemetry</code> &rarr; <i>"[not installed] [fixB]"</i>, describing it
happily &middot; <code>boost search "zeppelin telemetry airship"</code> &rarr; <i>"no matches"</i>,
plus the suggestion to try <code>boost discover</code>. The catalog cache for <code>fixB</code> had
just been written; the BM25 index files still carried the timestamp from before the tap existed.

<b>Two layers, and only fixing the first would have looked right and changed nothing.</b>
<code>rag.ensure()</code> short-circuited on <code>ready()</code>, and <code>ready()</code> only asks
whether an index <i>exists</i> — never whether it still describes the taps on disk. But
<code>cmd_search</code> did not call <code>ensure()</code> at all once an index existed: it called
<code>rag.ready()</code> itself and reached <code>ensure()</code> only on the cold path. So a fix
confined to <code>ensure()</code> passed its unit tests and left the CLI exactly as broken. The
comment above that line already claimed "rag.ensure() is incremental… so a search never hard-fails",
describing a call the code no longer made.

<b>The check is deliberately stat-only.</b> The obvious test — compare the stored per-tap commits
against <code>_tap_commits()</code> — parses every tap's catalog JSON on every search, which is the
cold-start cost that moving postings into SQLite existed to remove. Instead <code>rag.stale()</code>
asks two cheap questions: does the tap set still match the set the index recorded (a new or removed
tap need not touch any existing cache file), and is any tap's catalog cache newer than the index
(<code>build()</code> writes the index only after every cache it consumed). Measured after the fix: a
warm repeat search is <b>0.107 s</b> and leaves the index mtime untouched, so there is no rebuild
loop. Refreshing is cheap anyway — <code>build()</code> reuses every tap whose commit is unchanged,
so noticing one new tap costs one tap's indexing, not the corpus.

<b>Verification worth naming.</b> Nine hand-applied mutants of <code>stale()</code> — including
<code>&gt;</code>→<code>&gt;=</code> on the mtime compare and <code>!=</code>→<code>==</code> on the
tap-set compare — were all killed by the new tests. The functional test was then confirmed to
<i>fail</i> with the fix reverted, because a regression test that passes either way pins nothing.
That same check demoted its sibling: the untap case passes with or without this change, since
<code>rag.retrieve</code> already filters hits against the live catalog, so its docstring now says it
guards that filter rather than pretending to be evidence for this fix.
