---
id: audit-doctor-findings
board: code
section: health
status: planned
category: CLI · UX
complexity: S
impact: Low
wow: 1
note: crash line wears "!" but verdicts "● healthy" exit 0; and "1 issue need attention"
order: 263
owner:
pr:
title: "boost doctor: CLI audit findings (2026-08)"
---
<b>Three wording defects in one report, all verified.</b> The crash-report notice —
<em>"! 1 crash report in ~/.boost/logs (newest: &hellip;) — see `boost log --crashes`"</em> —
wears the "!" issue glyph but is never counted: <code>bad()</code>
(<code>quality.py:375-378</code>) is count + <code>out.warn</code>, and the crash notice
(<code>quality.py:609-612</code>) calls <code>out.warn</code> directly. Verification widened the
scope: with the crash line as the <em>only</em> warning, doctor prints "!" yet verdicts
<em>"● healthy"</em> with exit 0, and TTY rendering colours the uncounted line the same yellow as
counted issues. Fix: render it via <code>out.info</code>/<code>dim</code> (crash reports are
history, not current faults) or route it through <code>bad()</code> — pick one so glyph matches
count.
<br><br>
Second, the dense hint joins <code>fix_hint</code> with <code>". "</code>, producing a lowercase
sentence start: <em>"&hellip; searches are using BM25. install the extra: `pip install
'boost-skill-cli[rag]'`"</em> — <code>fix_hint</code> strings begin lowercase by design, and the
other consumers already join correctly (<code>discovery.py:290</code> uses
<code>— %s</code>, <code>mcp.py:449</code> uses <code>, %s.</code>); doctor
(<code>quality.py:689</code>) is the inconsistent surface. Join with <code>" — "</code>. Third,
found in verification: the verdict line itself has a number-agreement slip — <em>"● 1 issue need
attention"</em> — because <code>quality.py:637</code> pluralises the noun but not the verb; make
it <em>"1 issue needs attention"</em>. Update <code>docs/DEBUGGING.md</code> (its doctor output
excerpts at <code>:159-164</code>) to match. Found by the 2026-08 CLI audit (cluster
<code>doctor-output-polish</code>); repro in the audit log.
