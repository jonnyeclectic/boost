---
id: audit-dry-runs-disagree-with-the-real-run-compact-counts-bytes-it
board: code
section: dx
status: planned
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: compact --dry-run promises "would free 1.0MB"; the live run frees nothing
order: 225
owner:
pr:
title: "Dry-runs disagree with the real run: <code>compact</code>, <code>heal</code> and <code>onboard</code> previews mispredict"
---
A dry-run's one job is to say what the real run will do, and five previews demonstrably don't.
Sharpest case: with an untracked 1&nbsp;MiB <code>scripts/junk.bin</code> planted in a tap clone,
<code>compact minio/skills --dry-run</code> prints <em>&ldquo;would free 1.0MB&rdquo;</em> &mdash; then
<code>compact minio/skills</code> prints <em>&ldquo;&#10003; every tap is already compact&rdquo;</em> and the
file is still there. <code>_freight_bytes</code> (<code>boost_cli/commands/configuration.py:268-275</code>)
counts by <code>rglob</code>, but <code>git sparse-checkout reapply</code> only drops <em>tracked</em> paths
outside the cone, so untracked bytes are promised and never freed. <code>compact --dry-run --reclone</code>
compounds it: identical output with or without <code>--reclone</code>, although a reclone would drop the
clone's whole <code>.git</code>.

<code>heal</code> mispredicts its own branch: with a store copy deleted, <code>heal --dry-run</code> says
<em>&ldquo;would restore brainstorming &hellip; (or drop it from the lock)&rdquo;</em> while the live run on the
same state prints <em>&ldquo;&#10003; reinstalled missing brainstorming from sickn33/&hellip;&rdquo;</em> &mdash; the
&ldquo;drop&rdquo; alternative never fired. And on a fresh HOME it says only <em>&ldquo;would create 4 missing
directories&rdquo;</em>, the one heal action that never names its paths, so nothing in the preview says
<code>~/.agents/skills</code> and the agent skill dirs are what get written.

<code>onboard --dry-run</code> truncates each file preview at 24 lines with no marker
(<code>configuration.py:630</code> is <code>splitlines()[:24]</code>) &mdash; the lock preview ends mid-object
&mdash; and <code>--dry-run --pr</code> on a directory that is not a git repository exits 0 with no PR plan and
no precondition failure, because the dry-run early return at <code>configuration.py:624</code> sits before
the git-repo check at <code>:636</code>. The repo already treats preview/apply divergence as a correctness
defect: the shipped item <em>dry-run-promised-a-link-nobody-makes</em> (PR 460) fixed the same class for
<code>install --dry-run</code>.

Fix per the verified recommendation: compute <code>_freight_bytes</code> from the <code>git ls-files</code>
intersection so the dry run predicts what <code>reapply</code> removes, and estimate <code>.git</code> bytes
when <code>--reclone</code> is given; word heal's restore line from the branch <code>sync_apply</code> will take
and name the directories; have onboard print <em>&ldquo;&hellip; N more lines&rdquo;</em> past 24 lines and run the
read-only <code>--pr</code> precondition checks before the dry-run return. Docs: README.md lines 268-274
(<code>boost compact --dry-run</code>). Found by the 2026-08 CLI audit (cluster dry-run-fidelity); repro in
the audit log.
