---
id: audit-evolve-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: M
impact: Med
wow: 1
note: empty --feedback writes an empty section + version bump; the revision is left unpinned
order: 266
owner:
pr:
title: "<code>boost evolve</code>: CLI audit findings (2026-08)"
---
<b>evolve accepts empty <code>--feedback</code> and has no stdin/file form.</b>
<code>evolve brainstorming --feedback ""</code> exits 0 and diffs in
<code>+## Feedback (2026-08-31)</code> followed by nothing, plus a bump to
<code>version: 0.0.1</code> &mdash; with <code>--apply</code> that empty section lands in the store
and the lock. <code>--feedback -</code> becomes the literal bullet <code>+- -.</code> and
<code>--feedback @/dev/null</code> becomes <code>+- @/dev/null.</code>. In <code>cmd_evolve</code>
(<code>intelligence.py:663-713</code>) raise <code>BoostError</code> when
<code>args.feedback.strip()</code> is empty before calling the AI or heuristic; treat
<code>-</code> as read-from-stdin and <code>@path</code> as read-from-file, documented in
<code>--help</code> (then regenerate <code>docs/commands.html</code>).

<br><br><b>evolve <code>--apply</code> leaves the revision unpinned, so a later
<code>boost update</code> can silently overwrite it.</b> After <code>--apply</code> the lock holds
the evolved sha and <code>pinned: false</code>, and evolve prints only
<em>&ldquo;&#10003; evolved brainstorming&rdquo;</em>; <code>pkg.py</code>'s update loop
(<code>pkg.py:1035-1039</code>) skips only pinned/quarantined/local entries, so once the tap moves,
<code>store.install(entry, force=True)</code> (<code>pkg.py:1063-1067</code>) replaces the revision
with no warning. On <code>--apply</code> set <code>entry["pinned"] = True</code> (or a
<code>local_revision</code> flag the update loop honours) &mdash; at minimum print
<em>&ldquo;boost pin &lt;name&gt; to keep this across boost update&rdquo;</em> after the success line.

<br><br><b>After evolve, <code>info</code> claims an update to a lower version while
<code>outdated</code> says up to date.</b> With the lock at 0.0.1 and the tap at 0.0.0,
<code>info</code> prints <em>&ldquo;[update available] &hellip; version 0.0.1 / latest 0.0.0 (update
available)&rdquo;</em> &mdash; <code>info.py:477-479</code> and <code>498-501</code> test
<code>latest != inst_v</code> (string inequality) where <code>cmd_outdated</code>
(<code>taps.py:285</code>, <code>340</code>) correctly uses <code>util.semver_gt</code> for the same
decision. Replace both checks with <code>util.semver_gt(latest, inst_v)</code> and label the
locally-ahead case (e.g. <em>local revision, tap has an older 0.0.0</em>).

<br><br>Found by the 2026-08 CLI audit (clusters evolve-feedback-input, evolve-revision-unpinned,
naive-version-comparison); repro in the audit log.
