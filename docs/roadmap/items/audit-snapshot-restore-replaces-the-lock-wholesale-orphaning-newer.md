---
id: audit-snapshot-restore-replaces-the-lock-wholesale-orphaning-newer
board: code
section: internals
status: planned
category: Safety · Bug
complexity: S
impact: High
wow: 2
note: restore forgets a newer rule; its 865-line CLAUDE.md block stays, uninstall refuses
order: 219
owner:
pr:
title: "<code>snapshot restore</code> replaces the lock wholesale, orphaning newer rules' CLAUDE.md blocks"
---
<code>_snapshot_save</code> tars every child of <code>store_dir()</code> including
<code>.skill-lock.json</code> (<code>boost_cli/commands/pkg.py:1509-1511</code>), and
<code>_snapshot_restore</code> empties the store and extracts, replacing the live lock wholesale
(<code>pkg.py:1592-1600</code>). So restoring a snapshot taken before a rule was installed silently
forgets the rule while leaving its managed block in every context file. Verified live: with rule
<code>dotnet-build</code> in the lock and its ~865-line block in <code>~/.claude/CLAUDE.md</code>,
<code>snapshot restore snap-20260831-140734</code> printed only <em>&ldquo;&#10003; restored &hellip;
(1 skill)&rdquo;</em>; afterwards the lock's rules section is empty, the CLAUDE.md and GEMINI.md
blocks are still there, and <code>uninstall dotnet-build</code> answers <em>&ldquo;Error: dotnet-build
is not installed&rdquo;</em>, exit 1 &mdash; a block boost wrote and can no longer remove. CLAUDE.md's
own rule sets the stakes: installing a rule edits a file the user reads every session, so orphaning
one is worse than orphaning a skill.

The verifier found the surrounding prose is false in both directions. The v01 warning can never fire
because <code>_others_installed()</code> runs after the lock is already replaced; the reverse path
prints <em>&ldquo;&#10003; re-materialized rule dotnet-build &hellip;&rdquo;</em> and then
<em>&ldquo;! 1 rule untouched &mdash; snapshots cover the skill store only&rdquo;</em>
(<code>pkg.py:1602-1607</code>) &mdash; two lines apart; and since the lock (rules and workflows
included) <b>is</b> in the archive, <code>save</code>'s &ldquo;1 rule not captured&rdquo; line
(<code>pkg.py:1521-1523</code>) is false too.

Fix (verified recommendation): in <code>_snapshot_restore</code>, read the live lock's
rules/workflows sections before emptying the store and write them back over the restored lock &mdash;
a restore-side merge fixes every archive already on disk; compute the delta between pre-restore and
restored lock and word the trailer from it (re-materialized / kept / none), warning when archive
entries differ; fix <code>save</code>'s &ldquo;not captured&rdquo; line the same way. Functional test:
install a rule, restore an older snapshot, assert the rule is still in the lock and still
uninstallable. Docs: <code>docs/commands.html</code> (snapshot entry &mdash; clarify what restore does
to rules/workflows; regenerate only if the summary changes) and <code>docs/index.html</code>. Found by
the 2026-08 CLI audit (cluster <code>snapshot-restore-rules-loss</code>); repro in the audit log.
