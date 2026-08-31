---
id: audit-index-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: "index: errors glue onto the live progress bar, and 0 results overwrites a 150-entry index"
order: 272
owner:
pr:
title: "<code>boost index</code>: CLI audit findings (2026-08)"
---
<b>The live progress bar is never cleared before an error</b> <em>(med)</em>. On a TTY a failed
GitHub search prints <em>&ldquo;&#9619;&#9619;&#9619;&#9617;&#9617;&#9617; 1/3 searching GitHub for
SKILL.mdError: GitHub code search failed&rdquo;</em> on one line, and a failed page 2 glues
<em>&ldquo;! page 2 failed&rdquo;</em> onto the bar the same way. <code>spin.progress</code>
(<code>spin.py:69-82</code>) clears the line only when <code>current &gt;= total</code>, and
<code>cmd_index</code> raises and warns mid-loop (<code>discovery.py:578-598</code>) without
clearing. Fix: add a <code>spin.progress_clear()</code> helper and call it before the raise and the
warn &mdash; other <code>spin.progress</code> callers with early exits get it too.
(Cluster <code>index-progress-clear</code>.)

<br><br><b>Zero results gets a &#10003; and destroys the previous index</b> <em>(low)</em>. After a
150-entry build, <code>index zzzznomatch</code> prints <em>&ldquo;&#10003; indexed 0 skill files
across 0 repos (GitHub reports 0 total)&rdquo;</em>, exit 0 &mdash; and <code>discovery.json</code>
now holds 0 items, so <code>boost discover --local</code> shows nothing until the next successful
build. <code>discovery.py:619-627</code> writes unconditionally and prints <code>out.ok</code> even
for an empty result. Fix: on <code>not items</code>, warn <em>&ldquo;no SKILL.md files match &hellip;
&mdash; keeping the previous index of N entries&rdquo;</em> and return 0 without writing (write an
empty index only when none exists). (Cluster <code>index-empty-overwrite</code>.)

<br><br><b>A rate-limit failure echoes raw multi-line gh stderr as the hint</b> <em>(low)</em>.
The hint is gh's own prose plus a JSON blob, with continuation lines at column 0 and no
boost-native advice &mdash; while sibling paths in the same function do map their errors
(<code>discovery.py:567-569</code>, <code>:601-603</code>), the <code>returncode!=0</code> branch
(<code>discovery.py:590-595</code>) passes the last three stderr lines straight through. Fix: detect
<em>rate limit</em>/<em>HTTP 403</em>/<em>gh auth login</em> and raise with a one-line hint
(&ldquo;GitHub rate limit hit &mdash; wait a minute or authenticate: <code>gh auth login</code> /
GH_TOKEN&rdquo;), and make <code>out.err</code> indent hint continuation lines. Found by the 2026-08
CLI audit (cluster <code>index-ratelimit-hint</code>); repro in the audit log.
