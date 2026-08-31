---
id: audit-create-distill-infer-absorb-install-silently-replace-an-inst
board: code
section: dx
status: planned
category: Safety · Bug
complexity: S
impact: High
wow: 2
note: a tap skill becomes the TODO scaffold, lock flips to local — and the message says installed
order: 206
owner:
pr:
title: "create/distill/infer/absorb <code>--install</code> silently replace an installed (unpinned) skill and flip its lock provenance to local"
---
The generated-skill install path never checks whether the name is already taken. Verified: after
<code>install brainstorming</code> (sickn33 tap), <code>create brainstorming --install</code>
printed <em>"&#10003; installed brainstorming &rarr; ~/.agents/skills/brainstorming"</em> and the
store SKILL.md became the TODO scaffold (<code>description: "TODO: describe when this skill should
trigger"</code>), lock now <code>tap=local v0.1.0</code>. <code>distill --install -o
brainstorming &hellip;</code> likewise: lock <code>tap=local v1.0.0</code> with
<code>source_dir</code> pointing at a deleted <code>/tmp/&hellip;/boost-gen-&hellip;</code>
tempdir. Exit 0, no warning either time, and repeating any <code>--install</code> run re-copies
over the store with no notice. Only a <b>pinned</b> skill is protected — the unpinned default is
silently destroyed, with provenance flipped so the loss is invisible to <code>list</code>.

The gate belongs in the callers, not the store: <code>store.install_from_path</code>'s docstring
(<code>store.py:1175-1177</code>) deliberately omits the already-installed refusal because it
serves re-import/reinstall. Neither <code>_install_generated</code>
(<code>intelligence.py:103-123</code>) nor <code>cmd_create</code>
(<code>configuration.py:370-371</code>) checks <code>lockfile.get_skill</code>.

Fix: in <code>_install_generated</code> and <code>cmd_create</code>, check
<code>lockfile.get_skill(name)</code> before <code>store.install_from_path</code>: refuse with a
hint ("already installed from &lt;tap&gt;; <code>boost uninstall</code> first, pass
<code>--force</code>, or pick another name") or <code>out.confirm</code>; print "replaced" rather
than "installed" when overwriting is confirmed. Keep <code>install_from_path</code> itself
unchanged. Regenerate <code>docs/commands.html</code> if a <code>--force</code> flag is added to
create/distill/infer/absorb.

Found by the 2026-08 CLI audit (cluster <code>generated-install-overwrites</code>); repro in the
audit log.
