---
id: audit-taps-outdated-decay-policy-snapshot-json-emit-display-string
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: one array holds "updated":"2026-07-24" and "updated":"11h ago" — same key, two formats
order: 230
owner:
pr:
title: "<code>taps</code>/<code>outdated</code>/<code>decay</code>/<code>policy</code>/<code>snapshot</code> --json emit display strings as machine fields"
---
Five <code>--json</code> outputs leak the table renderer's strings into the machine-readable
document, because each command builds <b>one record</b> and feeds it to both the table and
<code>json.dumps</code>. Verified, all five: <code>taps --json</code> mixes
<code>"updated": "2026-07-24"</code> and <code>"updated": "11h ago"</code> in one array (cloned
vs imported taps) with <code>"pin": ""</code> for unset &middot; <code>outdated --json</code>'s
<code>latest</code> is a composite &mdash; <code>"0.0.0 (b36e082)"</code>,
<code>"source missing"</code>, <code>"x (content changed)"</code> &mdash; and the table spells one
state two ways (<code>(b36e082)</code> for skills, <code>(content changed)</code> for rules) &middot;
<code>decay --json</code>'s <code>last_activity</code> is humanised in two formats
(<code>"1m ago"</code> / <code>"2026-07-02"</code>) &middot; <code>policy check --json</code> folds
the kind into the name: <code>{"skill": "dotnet-build (rule)"}</code> &middot;
<code>snapshot list --json</code> emits <code>"skills": "?"</code> (a string) beside sibling rows'
<code>"skills": 1</code> when a sidecar is missing, a type change across rows of one key.

Why it matters: a consumer must parse display text back apart &mdash; regex the sha out of
<code>latest</code>, guess whether <code>updated</code> is a date or a relative age, strip
<code>" (rule)"</code> off a field named <code>skill</code> &mdash; and type-unstable values break
any typed loader. Sibling commands already do it right: <code>impact --json</code> emits
<code>null</code> for unknown.

The fix is one sweep with one rule: records carry machine values, and the table branch alone
applies <code>rel_time()</code>, placeholders and composites. Concretely: ISO timestamps or
<code>null</code> for <code>updated</code>/<code>last_activity</code>; separate
<code>name</code>/<code>kind</code> in policy violations (keep <code>skill</code> as a deprecated
alias if compatibility matters); <code>latest</code> + <code>reason: version|content|source-missing</code>
+ <code>latest_commit</code> in outdated, unifying the two content-changed spellings while there;
numeric-or-null counts in snapshot list. Sites: <code>boost_cli/commands/taps.py:208-221</code>,
<code>taps.py:239-242</code>, <code>taps.py:300</code>, <code>taps.py:308</code>,
<code>taps.py:331</code>, <code>taps.py:341-347</code>, plus the decay/policy/snapshot row builders.
No flag or summary changes, so no doc regeneration needed. Found by the 2026-08 CLI audit
(cluster <code>json-display-strings</code>); repro in the audit log.
