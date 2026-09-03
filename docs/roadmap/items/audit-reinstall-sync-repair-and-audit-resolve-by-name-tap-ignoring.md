---
id: audit-reinstall-sync-repair-and-audit-resolve-by-name-tap-ignoring
board: code
section: internals
status: inflight
category: Safety · Bug
complexity: M
impact: High
wow: 2
note: reinstall after install --path swaps the installed bytes for a different mirror's
order: 211
owner: loop/lock-source-resolve
pr:
title: "<code>reinstall</code>, sync repair and <code>audit</code> resolve by name+tap, ignoring the lock's source path"
---
The lock records exactly which copy of an item was installed
(<code>source_dir</code>/<code>source_file</code>), and four code paths ignore it, resolving by
name+tap and taking <code>catalog.find(name)[0]</code>. Verified live: install
<code>ultrawork</code> with <code>--path benchmarks/runs/oma/.agents/workflows</code> (lock
<code>source_file</code> under that path, sha <code>4357283b&hellip;</code>), then
<code>reinstall ultrawork</code> — it prints <em>&ldquo;&#10003; reinstalled workflow ultrawork
v0.0.0&rdquo;</em> and the lock now points at <code>.agents/workflows/ultrawork.md</code>, sha
<code>83ba2052&hellip;</code>. Not just metadata: <code>~/.claude/commands/ultrawork.md</code> hashes
<code>83ba2052</code> and the two tap copies <code>cmp</code> DIFFERENT — the installed bytes were
silently swapped for a different file. <code>sync</code>'s &ldquo;reinstalled missing&rdquo; repair
does the same.

The read side mis-answers the same way. <code>sickn33</code> ships three <code>brainstorming</code>
dirs; <code>safety._upstream_reason</code> hashes whichever entry comes first, so
<code>audit --skills</code> printed <em>&ldquo;LOW behind-tap tap has a newer copy (content)&rdquo;</em>
when only a <em>mirror</em> the user never installed changed (while <code>drift</code> said in-sync),
and stayed silent when the installed copy's own source dir changed (while <code>drift</code> said
upstream-moved). <code>taps</code>' <code>outdated</code> selects <code>matches[0]</code> the same way.
The shipped <code>install-path-disambiguation</code> item added <code>--path</code> to install only —
every downstream resolver still forgets the choice it recorded.

Verified fix: wherever the lock records a source path, select the catalog entry whose
<code>rel_dir</code>/<code>skill_md</code> matches it — <code>cmd_reinstall</code> both branches
(<code>pkg.py:1133-1142</code>, <code>:1174-1181</code>), sync repair
(<code>store.py:1642-1651</code>), <code>safety._upstream_reason</code>
(<code>safety.py:228-241</code>) and <code>taps.py</code>'s outdated — falling back to
<code>matches[0]</code> only when the lock has none, with a warning naming the path chosen. Pin with a
test that installs a <code>--path</code> copy and reinstalls. No doc changes beyond regenerating
<code>docs/commands.html</code> if summaries move (none expected). Found by the 2026-08 CLI audit
(cluster <code>lock-source-ignored-on-reinstall</code>); repro in the audit log.
