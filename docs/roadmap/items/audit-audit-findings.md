---
id: audit-audit-findings
board: code
section: health
status: inflight
category: Safety · Bug
complexity: M
impact: Med
wow: 2
note: rm -rf ~/ passes clean, hidden.js is never scanned, and a missing dir counts as scanned
order: 249
owner: loop/audit-audit-findings
pr:
title: "boost audit: CLI audit findings (2026-08)"
---
<b>Three honesty gaps in the trust scanner.</b> A seeded <code>rm -rf ~/</code> (and <code>rm -rf
/*</code>) in SKILL.md produced <b>no finding</b> while <code>sudo rm -rf /</code> on the next file
was flagged HIGH: the destructive regex's lookahead (<code>safety.py:46</code>) rejects a trailing
<code>/</code> or <code>/*</code> after the target. Only SKILL.md plus <code>*.sh</code>/<code>*.py</code>
are scanned (<code>safety.py:93-96</code>), so <code>scripts/hidden.js</code> carrying <em>&ldquo;ignore
previous instructions&rdquo;</em> and <code>curl x | sh</code>, and a <code>NOTES.md</code> with
<code>rm -rf ~</code>, are invisible. And a skill whose store dir was deleted still reports
<em>&ldquo;&#10003; no safety findings across 1 item&rdquo;</em>, exit 0 &mdash; scanned-and-clean with
zero files scanned. Fix: widen the lookahead, scan every UTF-8 text file under the skill dir (or at
least <code>*.md</code>/<code>*.js</code>/<code>*.ts</code>/<code>*.rb</code>/<code>*.ps1</code>) and
state the scope in <code>--help</code>, and report <em>store dir missing &mdash; nothing to scan</em>
instead of counting it. Update <code>docs/security-design.md</code>; regenerate
<code>docs/commands.html</code> if the help text changes.

<br><br><b>&ldquo;last tap sync&rdquo; measures the wrong clock.</b> Twelve minutes after tapping all
20 taps, <code>health</code> printed <em>&ldquo;last tap sync 4w ago&rdquo;</em>
(<code>quality.py:1215-1227</code> runs <code>git log -1 --format=%ct</code> &mdash; the upstream's
newest commit, unchangeable by any sync), and <code>audit --skills</code> words the same number as
<em>&ldquo;tap last synced 37 days ago&rdquo;</em> (<code>trustaudit.py:127-129</code>) &mdash;
unactionable for a deliberately pinned tap, which <code>registry.update</code> skips. Fix: read
<code>paths.tap_refresh_marker</code> (the source <code>search</code>'s stale hint already uses) for
the sync row, reword STALE_TAP to <em>&ldquo;tap's newest commit is N days old&rdquo;</em>, and skip
or annotate pinned taps. Update <code>docs/DEBUGGING.md</code>.

<br><br><b>The content scan prints findings in pattern order.</b> Seeded output showed a HIGH row
after LOW and MED ones &mdash; insertion order is the pattern outer loop
(<code>safety.py:103-107</code>) &mdash; while <code>--skills</code> sorts worst-first via
<code>trustaudit.sort_findings</code>, and <code>--json</code> serialises the same unsorted array.
Fix: sort each skill's findings by (severity rank, file, label) before the <code>args.json</code>
branch; do <b>not</b> call <code>trustaudit.sort_findings</code> verbatim &mdash; it keys on
<code>f['detail']</code>, which content findings lack (KeyError).

<br><br><b>Empty-state drift is back after BOOST-D18.</b> <code>list</code> still hints <code>boost
tap --defaults</code> with 20 taps configured; the check group has four phrasings (<em>nothing to
lint</em> / <em>nothing installed</em> / <em>no skills installed</em> / <em>nothing installed
yet&hellip;</em>); <code>audit --skills --json</code> is pretty-printed while its siblings are
single-line (<code>safety.py:299</code>); and <code>list --tag</code>'s count line drops the filter
its own empty state names. Fix: condition the hint on <code>registry.list_taps()</code>, route
deps/drift/verify/lint/audit empties through <code>out.empty_state</code> with one phrasing, drop
<code>indent=2</code>, and append <code>with tag #&lt;tag&gt;</code> at <code>info.py:326-327</code>.

<br><br>Found by the 2026-08 CLI audit (clusters <code>audit-scan-blindspots</code>,
<code>tap-sync-age-mislabel</code>, <code>audit-finding-order</code>,
<code>empty-state-hint-drift</code>); repro in the audit log.
