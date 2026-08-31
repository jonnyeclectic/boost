---
id: audit-onboard-findings
board: code
section: dx
status: planned
category: Safety · Bug
complexity: S
impact: Med
wow: 1
note: onboard --pr pushes absolute /Users/… paths from the global lock file to GitHub
order: 277
owner:
pr:
title: "boost onboard: CLI audit findings (2026-08)"
---
<code>boost onboard</code> commits the machine's <em>global</em> lock file into the repo verbatim:
<code>cmd_onboard</code> (<code>boost_cli/commands/configuration.py:593-675</code>) writes
<code>json.dumps(lockfile.read(), &hellip;)</code> as the repo's <code>.skill-lock.json</code>
(<code>configuration.py:621-622</code>) with no path sanitization. Verified in the
<code>--dry-run</code> preview: with the rule <code>dotnet-build</code> installed, the file carries
<code>rules.dotnet-build.materializations[].path</code> values like
<code>&hellip;/.claude/CLAUDE.md</code> and <code>&hellip;/.windsurf/rules/dotnet-build.md</code> rooted at
the absolute <code>$HOME</code> &mdash; on a real machine, <code>/Users/&lt;name&gt;/&hellip;</code> &mdash;
and <code>--pr</code> pushes exactly that to GitHub.

<br><br>A repo inventory needs names, taps and commits, not one contributor's username and dotdir layout;
every teammate who runs onboard afterwards would churn the file with their own paths. Fix: in
<code>cmd_onboard</code>, project the lock before writing &mdash; strip
<code>materializations[].path</code> or rewrite it <code>~</code>-relative &mdash; so the committed file is
portable. <code>docs/carousel.html</code> (line 362) describes the onboard flow and must match. Found by
the 2026-08 CLI audit (cluster <code>onboard-lock-path-leak</code>); repro in the audit log.
