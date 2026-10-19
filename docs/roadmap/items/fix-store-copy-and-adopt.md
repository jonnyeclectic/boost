---
id: fix-store-copy-and-adopt
board: code
section: internals
status: shipped
category: Bug
complexity: M
impact: High
wow: 3
note: a skill with a symlink crashed install, and a lost lock made heal adopt a workflow's skill copy as a local skill
order: 375
owner:
pr:
title: Symlinked skills install, and a lost lock no longer adopts a workflow's skill copy
---
<b>Two store bugs: one crashed an install, the other gave a false all-clear after recovery.</b>
<code>_copy_skill</code> called <code>copytree</code>, which follows every link by default. A
skill that linked to <code>../../shared/helper.py</code> pointed at a file the sparse tap clone
had never checked out, so install failed with a raw <code>shutil.Error</code>, exit 2, and
nothing was installed. A dangling link failed the same way, and a link out of the tap would
have copied whatever it pointed at into the store. Now <code>source_dir_for</code> first
fetches each link target that lies inside the tap (<code>gitutil.materialize_paths</code>,
using <code>add</code> and never <code>set</code>). A link that stays inside the skill is copied
as a link. A link elsewhere in the tap is copied as its target. A link to nothing, out of
the tap, or back over the skill is skipped, and the install says which one it skipped. A copy
error that still gets through is a <code>BoostError</code>, not a crash.
<br><br>
With the lock file gone, the only record that a store dir was a workflow's skill copy was
gone too. <code>boost heal</code> re-recorded the copy as a <code>local</code> skill, the next
run linked it into every agent next to the workflow's own file, and <code>boost doctor</code>
then reported healthy. <code>store.workflow_copy_evidence</code> now asks the disk instead:
a store dir whose <code>SKILL.md</code> is exactly what an agent's
<code>agents/&lt;name&gt;.md</code> or <code>commands/&lt;name&gt;.md</code> renders to is that
workflow's copy. It is never adopted or linked, and heal, sync and both doctors name it with
<code>boost install &lt;workflow&gt;</code> as the fix. Because that install now claims a
store dir that holds exactly its own copy, a single install converges.
Known limits: rule blocks and workflow files the lost lock recorded are not rebuilt from
disk, and a Gemini-only workflow's TOML command is no evidence.
