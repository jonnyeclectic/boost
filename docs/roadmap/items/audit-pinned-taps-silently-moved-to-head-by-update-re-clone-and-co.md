---
id: audit-pinned-taps-silently-moved-to-head-by-update-re-clone-and-co
board: code
section: internals
status: inflight
category: Safety · Bug
complexity: M
impact: High
wow: 2
note: compact --reclone moved a pin to HEAD and printed "every tap is already compact"
order: 216
owner: loop/pinned-tap-reclone
pr:
title: "Pinned taps silently moved to HEAD by <code>update</code> re-clone and <code>compact --reclone</code>, pin left stale"
---
The pin invariant &mdash; only <code>update --force</code> may move a pinned tap, and moving one is
deciding to stop holding it still &mdash; is broken by three paths, all reproduced byte-for-byte.
<b>1:</b> <code>compact minio/skills --reclone</code> against a tap pinned at <code>d543829&hellip;</code>
printed <em>&ldquo;&#10003; every tap is already compact&rdquo;</em>, yet afterwards the clone's
<code>refs/heads/main</code> is <code>22961d3&hellip;</code> while <code>config.json</code> still says
<code>"pin": "d543829&hellip;"</code>, the catalog cache still says the old commit, <code>boost taps</code>
prints <code>@d543829</code>, and <code>doctor</code> is silent. <b>2:</b> after the clone directory is
deleted, <code>update minio/skills --force</code> re-clones at HEAD but keeps the stale pin &mdash;
breaking <code>--force</code>'s own help promise (<em>&ldquo;move pinned taps too, clearing their
pin&rdquo;</em>) &mdash; and prints no SHA. <b>3:</b> plain <code>update</code> on a pinned tap whose
clone is gone reports <em>&ldquo;&#10003; pinned at b7c025b (skipped) / &#10003; everything up to
date&rdquo;</em> with nothing on disk.

Why it matters is stated in the code itself (<code>boost_cli/core/registry.py:492-496</code>): pinned
commits are what imported shard vectors are keyed to, and a tap moved silently leaves stale vectors
present with no error &mdash; the failure that looks like nothing at all. Here every readout
(<code>taps</code>, cache, <code>doctor</code>) keeps vouching for a commit the clone left.

Fix (verified recommendation): in <code>registry.update</code>'s clone branch
(<code>registry.py:513-522</code>), when <code>tap.pin</code> and not force, clone then check out the
pin (reuse the <code>tap --at</code> path); when force, <code>unpin()</code> as the pull branch does;
print <code>cloned at &lt;sha7&gt;</code>. Move the pin skip (<code>registry.py:491</code>) after the
<code>is_cloned</code> test so a pinned tap with no clone is re-cloned at its pin. In
<code>cmd_compact --reclone</code> (<code>boost_cli/commands/configuration.py:277-279</code>), check
out <code>tap.pin</code> after <code>clone_shallow</code> (or refuse with a hint), run
<code>catalog.rebuild_tap</code>, and report re-clones regardless of size direction &mdash; the
size-only report at <code>configuration.py:288-292</code> is what hid the move. Docs: README.md's
pinned-tap paragraph (lines 176-178) and its <code>compact --reclone</code> line (274); regenerate
<code>docs/commands.html</code> only if the <code>--force</code> help string changes. Found by the
2026-08 CLI audit (cluster <code>pinned-tap-integrity</code>); repro in the audit log.
