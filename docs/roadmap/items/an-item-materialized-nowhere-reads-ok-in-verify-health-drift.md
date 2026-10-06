---
id: an-item-materialized-nowhere-reads-ok-in-verify-health-drift
board: code
section: health
status: shipped
category: CLI · Bug
complexity: S
impact: Low
wow: 2
note: a rule whose every materialization row names an agent boost no longer writes reads "ok" in verify and is counted as installed by health — only doctor says otherwise
order: 354
owner: loop/materialized-nowhere
pr: 1040
title: An item materialized <em>nowhere</em> reads <code>ok</code> in <code>verify</code>, <code>health</code> and <code>drift</code>
---
<b>Found by the second review of</b> <code>sync-repairs-a-disabled-agents-row-every-run</code>.
That item fixed a row for an agent boost no longer writes being read as a <em>missing artifact</em>:
nothing wrote the file and nothing ever will, so <code>boost verify</code> failed forever and
<code>boost drift</code> and <code>boost health</code> sent the user to a <code>boost sync</code>
that skips the row by design. The fix is right, and it opens a gap at the other end.

<b>Skipping a row is correct per row and wrong per item.</b> Skip <em>every</em> row an item has
and the item is materialized nowhere — the rule reaches no agent, the workflow is in no command
palette — and the surfaces say it is fine. Measured on a real install (fixture tap, one rule,
then every agent disabled): <code>boost verify</code> &rarr;
<code>team-conventions&nbsp;&nbsp;ok&nbsp;&nbsp;rule</code>, rc 0 &middot; <code>boost drift</code>
&rarr; <code>in-sync</code> &middot; <code>boost health</code> &rarr;
<code>rules&nbsp;&nbsp;1 installed</code>, <code>drift&nbsp;&nbsp;1 in-sync</code>,
<code>● healthy</code> &middot; <code>boost attest --verify</code> &rarr; <code>sha_ok</code>.

<b><code>doctor</code> both names it and denies it.</b> It prints the note —
<em>5 recorded materializations name an agent boost no longer writes…</em> — and two lines later
<em>✓ 1 rule and 0 workflows fully materialized for every agent boost writes</em>, then
<code>● healthy</code>. The count is true as worded and false as read: the write set is empty, so
every item is trivially materialized for all of it. Only the note carries the news, and only
<code>doctor</code> has a note channel — a third state that is neither an issue nor silence. The
other commands have two, so the per-row skip had nowhere to put this and it fell into the healthy
one.

<b>Why it is not cosmetic.</b> <code>verify</code> is what scripts gate on and
<code>attest --verify</code> is the provenance check; an install that reaches nothing and passes
both is wrong in the direction that costs the user something — they installed a rule believing
some agent would read it.

<b>Shape of a fix.</b> Keep the per-row skip; add a per-<em>item</em> question after the loop. An
item whose materialization rows are all unwritten is reported distinctly — <em>unreachable</em>,
neither <code>ok</code> nor <code>missing</code> — and the count line says how many agents it
actually reaches rather than how many of the empty set it satisfies. The work is the state the
three commands do not have: <code>verify</code>'s exit code, what <code>health</code>'s counts
mean, and whether <code>attest --verify</code> should fail it. An item with <em>no</em> rows at all
is a different case (a skill, or a rule installed before rows existed) and must keep reading
<code>ok</code>.
