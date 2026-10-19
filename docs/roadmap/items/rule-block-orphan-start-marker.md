---
id: rule-block-orphan-start-marker
board: code
section: trust
status: shipped
category: CLI · Bug
complexity: S
impact: Med
wow: 4
note:
order: 372
owner: fix/rule-block-orphan
pr:
title: A rule block missing its end marker made the next reinstall delete the user's own <code>CLAUDE.md</code> text
---
A rule materializes into <code>~/.claude/CLAUDE.md</code> as a block between
<code>&lt;!-- boost:rule:NAME start --&gt;</code> and its <code>end</code> marker. Delete the end
marker by hand, keep notes below the block, and three things went wrong in a row, reproduced in a
sandbox. <code>boost uninstall</code> printed <b>"removed from claude-code"</b>, exited 0 and
dropped the lock row, while the block stayed live: <code>strip_block</code> declined to guess, and
<code>_uninstall_rule</code> counted the agent removed anyway. <code>boost install</code> then
appended a second, complete block below the orphan. And the next <code>reinstall</code> replaced
everything from the orphan <em>start</em> to the new block's <em>end</em>, because
<code>merge_block</code> took the first end marker anywhere after the first start. The user's
<code>keep me</code> line: grep count <b>0</b>.

<b>Fixed.</b> <code>rules.block_span</code> is now the one definition of "the block": a start
marker, its first end marker, and no second start between them. <code>merge_block</code>,
<code>read_block</code> and <code>strip_block</code> all go through it.
<code>require_well_formed</code> tells "absent" from "damaged" and refuses the damaged case with
the file named and the marker to restore. Install checks every context file before the first
write, because <code>GEMINI.md</code> is written after Cursor's rules file, so a refusal from
inside the loop left that file on disk with no lock row to remove it. Uninstall refuses before the
lock is touched, the same all-or-nothing contract as a locked agent dir. Re-running the repro: uninstall,
reinstall and <code>install --force</code> each exit 1 with the hint, the lock row survives, and
<code>keep me</code> is still there. <code>boost doctor</code> still tests for the start marker as
a substring; switching it to <code>read_block</code> belongs to the doctor PR.
