---
id: tap-health
board: code
section: health
status: shipped
category: Bug
complexity: S
impact: Medium
wow: 2
note: drift told users to run a re-tap command that could not parse, and a clone without .git read as healthy while every update failed
order: 375
owner:
pr:
title: Drift re-taps the recorded source, and a clone without .git reads as broken
---
<b>The drift hint for an untapped source was a command that did not work.</b> When a skill's
tap had been untapped, <code>boost drift</code> printed <code>boost tap &lt;name&gt;</code>
built from the tap's derived name. A local tap is named after its directory's basename, so
<code>boost tap fix</code> failed with "cannot parse tap spec". A GitLab tap is named
<code>owner/repo</code>, which <code>parse_spec</code> resolves to GitHub, so following the
hint would clone a different repository.

<b>The lock now records <code>tap_url</code>.</b> Skill, project-skill, rule and workflow
entries store the tap's URL or local path at install time, and
<code>registry.retap_hint</code> builds the hint from it, shell-quoted. A lock entry written
before the field existed falls back to the name only when it is <code>owner/repo</code>-shaped;
otherwise drift says the URL was not recorded and prints no command. A legacy entry from a
non-GitHub host still gets the GitHub-shaped hint, because nothing on disk can tell it apart.

<b>A clone directory without <code>.git</code> looked healthy.</b> <code>Tap.is_cloned</code>
is <code>path.is_dir()</code>, so doctor reported the tap cloned, heal said nothing to heal,
and every <code>boost update</code> failed with "not a git repository" without re-cloning.
<code>Tap.is_broken_clone</code> is a separate check, so the wheel tap (no <code>.git</code> by
design) and the many callers of <code>is_cloned</code> keep their meaning. Doctor counts the
tap as an issue, heal names it, skips its catalog rebuild and exits 1, and both point at
<code>boost update &lt;name&gt;</code>, which now takes the re-clone branch for it and honours a
pin.
