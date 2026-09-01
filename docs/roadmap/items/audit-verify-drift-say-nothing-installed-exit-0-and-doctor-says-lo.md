---
id: audit-verify-drift-say-nothing-installed-exit-0-and-doctor-says-lo
board: code
section: health
status: inflight
category: CLI · Bug
complexity: S
impact: High
wow: 2
note: rm the lock, verify exits 0 'nothing installed'; doctor still prints 'lock parses (v3)'
order: 214
owner: loop/lock-integrity-reporting
pr:
title: "<code>verify</code>/<code>drift</code> say 'nothing installed' (exit 0) when the lock file is missing or corrupt"
---
Delete <code>.skill-lock.json</code> after an install (store and four agent links still present) and
<code>verify</code> — whose one-line summary is <em>lock-file integrity</em> — prints
<em>&ldquo;&nbsp;&nbsp;nothing installed&rdquo;</em> and exits 0. Truncate the lock to
<code>{"version": 3, "skills": {</code>: same answer, and <code>drift</code> says <em>&ldquo;no
skills installed&rdquo;</em> exit 0 too. Verified live. <code>doctor</code> on the missing-lock state
prints <em>&ldquo;&#10003; lock file parses (v3)&rdquo;</em> &hellip; <em>&ldquo;! 1 orphaned store
dir (brainstorming)&rdquo;</em> &hellip; <em>&ldquo;&#10003; lock file integrity OK &middot; log
rotation healthy&rdquo;</em> — it does exit 1 via the orphaned-store line, but the two &#10003; lines
assert parsing and integrity for a file that does not exist, contradicting the diagnosis two lines
away.

The cause is that <code>lockfile.read()</code> (<code>lockfile.py:36-76</code>) silently returns an
empty skeleton on a missing or corrupt lock — the warning goes only to the log file — so
<code>cmd_verify</code>'s <em>if no results: &ldquo;nothing installed&rdquo;, return 0</em>
(<code>safety.py:400-403</code>) and <code>cmd_doctor</code>'s <code>lock_ok=True</code>
(<code>quality.py:408-421</code>) both report health for exactly the state these commands exist to
catch. The roadmap's atomic-lock-writes item covers writes, not reporting.

Verified fix: in <code>cmd_verify</code> (and <code>cmd_drift</code>) fail before iterating — lock
absent while the store dir has entries, unparseable, or <code>version != SCHEMA_VERSION</code>
&rarr; error + exit 1, reusing doctor's corrupt/schema wording. In <code>cmd_doctor</code>, print
&ldquo;parses (v3)&rdquo; only after parsing an existing file; absent &rarr; info on an empty store,
<code>bad()</code> when the store is populated (e.g. <em>&ldquo;! lock file missing &mdash; N store
dirs unrecorded, run `boost sync`&rdquo;</em>). Docs: <code>docs/security-design.md</code> (verify's
integrity contract) and <code>docs/DEBUGGING.md</code> (doctor's lock lines); no flag change, so
<code>docs/commands.html</code> needs no regeneration. Found by the 2026-08 CLI audit (cluster
<code>missing-lock-reported-healthy</code>); repro in the audit log.
