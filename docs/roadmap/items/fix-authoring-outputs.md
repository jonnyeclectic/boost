---
id: fix-authoring-outputs
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Medium
wow: 2
note: distill, infer and absorb --install exited 0 on a refused install, clobbered a file of the fallback's name, kept the tap prefix in the output name, and split a scalar tags string into letters
order: 375
owner:
pr:
title: Generated skills report a refused install and never clobber a file
---
<b>A refused <code>--install</code> exited 0.</b> <code>distill</code>, <code>infer</code> and
<code>absorb</code> printed "not installed" and saved the generation beside the cwd, then
exited 0, so a script or CI job could not tell. A pinned name refused even with
<code>-y</code>, and <code>infer</code> journaled the install that never happened. The
install now reports success or failure, each caller exits 1 on failure, and
<code>infer</code> journals only after a real install.

<b>The fallback file overwrote whatever had its name.</b> The save wrote
<code>&lt;name&gt;.SKILL.md</code> unconditionally, on the very path where the user had just
declined a replace. <code>util.write_unclaimed</code> opens each candidate with
<code>"x"</code> and steps to <code>&lt;name&gt;.1.SKILL.md</code>, <code>.2</code>, ...
so an existing file is never touched.

<b><code>distill fx:a fx:b</code> wrote <code>fx:a-distilled</code>.</b> The default output
name came from the raw first argument, prefix and all, and the printed
<code>boost import</code> hint then rejected it as an invalid skill name. The name now comes
from <code>catalog.split_name</code>'s bare half.

<b>A scalar <code>tags: testing</code> merged as <code>t, e, s, i, n, g</code>.</b> The merge
iterated the raw frontmatter value. <code>frontmatter.tags_of</code> reads a list, a comma
string or a number the way the catalogue page already did, and <code>serve</code> now uses it
too.
