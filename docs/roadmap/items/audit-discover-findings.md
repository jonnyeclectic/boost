---
id: audit-discover-findings
board: code
section: dx
status: inflight
category: CLI · UX
complexity: S
impact: Low
wow: 1
note: footer blames the network when gh is missing; --json prints [] silently with no index
order: 262
owner: loop/discover-audit-findings-v2
pr:
title: "boost discover: CLI audit findings (2026-08)"
---
<b>The empty-result footer says "GitHub could not be reached" whatever the real reason.</b>
With <code>gh</code> absent: <em>"! GitHub search needs the `gh` CLI"</em> then <em>"this searched
a local sample of 300 entries because GitHub could not be reached"</em>; with gh present but
rate-limited (a real HTTP 403 — GitHub answered), the same footer. <code>discovery.py:820-821</code>
hardcodes the phrase for every non-<code>--local</code> fall-through although
<code>_fall_back</code> already holds the real reason (gh missing at <code>:722</code>, code
search failed at <code>:727</code>). Fix: pass the fall-back reason into the footer —
<em>"because the `gh` CLI is not installed"</em> / <em>"because GitHub code search failed"</em> —
or the neutral <em>"because GitHub was not searched (see above)"</em>.
<br><br>
<b><code>discover --json</code> with no index prints <code>[]</code> silently.</b> Fresh HOME:
stdout <code>[]</code>, stderr empty, exit 0 — a script cannot tell "nothing indexed" from "no
matches", while the text path explains itself and the live-fallback path already warns on stderr
under <code>--json</code>. <code>_fall_back</code>'s own docstring
(<code>discovery.py:704-713</code>) states the convention: its lines go to stderr <em>"so it
survives --json: suppressing it was the defect"</em>. Fix: in the <code>not dpath.exists()</code>
branch (<code>discovery.py:781-784</code>) emit the same "discovery index has not been built yet /
build it with <code>boost index</code>" lines via <code>out.info(&hellip;, stream=sys.stderr)</code>
before printing <code>[]</code>.
<br><br>
<b>The local-index table is per file where the live table is per repo.</b> Local, no query:
25 rows over 7 repos, agent mirrors included (<code>acme/skills skills/skill-0/&hellip;</code>,
<code>dave/mono .claude/skills/s10/SKILL.md</code>); live, same fake corpus: 7 collapsed rows
(<code>acme/skills (15)</code>). Verification found it broader than reported: on a queried live
search that fell back (rate-limited), one repo filled the entire <code>--limit</code> with itself
(6/6 rows = acme/skills) — exactly the pathology <code>_by_repo</code>'s docstring
(<code>discovery.py:671-698</code>, "the repo is the unit that belongs on screen") says discover
exists to avoid. Fix: run the local branch's hits through <code>_by_repo()</code> before slicing
to <code>--limit</code>, render the same <code>(N)</code> repo-count cell, reword the footer to
count repos; keep <code>--json</code> rows per-file with <code>source:"local-index"</code>
unchanged, and update <code>tests/bdd/features/discover.feature</code> row assertions. No flag
changes, so <code>docs/commands.html</code> is untouched. Found by the 2026-08 CLI audit (clusters
<code>discover-fallback-reason</code>, <code>discover-json-empty-note</code>,
<code>discover-table-shapes</code>); repro in the audit log.
