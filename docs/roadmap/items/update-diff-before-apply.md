---
id: update-diff-before-apply
board: code
section: trust
status: shipped
category: Security · Supply chain
complexity: M
impact: Med
wow: 3
note: no silent overwrites
order: 5
owner: loop/update-diff-gate
pr: 132
title: Update-diff before apply
---
Shipped in <b>#132</b>. <code>boost update</code> no longer overwrites an
installed skill in place unseen. A new pure core module
<code>core/updatediff.py</code> diffs the installed tree against the incoming
source (<code>diff_tree</code>) and flags when the change adds
<em>executable-looking instructions</em> — shell commands, pipe-to-shell,
shebangs (<code>touches_executable</code>). When it does,
<code>cmd_update</code> prints the unified diff and requires confirmation before
applying, so a poisoned update is <em>visible</em> instead of silent; routine
version bumps and prose edits still apply quietly. Fully unit-tested and
mutation-covered, plus functional coverage of the confirm / decline / no-gate
paths.
