---
id: bmad-roster-drifted-from-bmad-6-12
board: code
section: dx
status: next
category: "Agents · BMAD"
complexity: M
impact: Med
wow: 2
note: docs routes at a skill no default 6.12 install contains
order: 323
owner:
pr:
title: The autopilot routes docs at a skill BMAD 6.12 no longer installs, and no test would notice
---
<code>core/bmad.py</code> hard-codes upstream skill names in persona <code>skills</code> and track
<code>skill</code>, while <code>boost bmad install</code> fetches <code>bmad-method@latest</code>
(<code>commands/bmad.py:410</code>). The tests check the two tables only against <em>each other</em>
(<code>tests/unit/test_bmad_core.py:207</code>) and <code>orientation()</code> against a three-name
denylist (<code>:431</code>), so a name that goes stale in both tables passes.

<b>Against a real install, one name is gone.</b> A pinned <code>bmad-method@6.12.0</code> install
(<code>--tools claude-code --modules bmm</code>) wrote <b>29</b> skills, matching its
<code>skill-manifest.csv</code> <code>canonicalId</code> column exactly. <b>12 of the 13</b> names in
<code>PERSONAS</code>/<code>TRACKS</code> are present, as are all 11 in <code>orientation()</code>. The missing
one is <code>bmad-document-project</code>, the docs track's skill (<code>core/bmad.py:263</code>) and Paige's
only one (<code>:229</code>). v6.11.0 turned it into a <code>v6-shims/</code> forwarder for
<code>bmad-project-context</code> (#2674), and v6.12.0 made shims opt-in on fresh installs. boost passes
no <code>--shims</code>, so the install records <code>installShims: false</code>. Every docs banner still
says <code>invoke it if it is installed</code> (<code>:548</code>). Paige also supports the catch-all
<code>build</code> track (<code>:256</code>), so build banners also ask for a subagent whose file names that skill.

<b>The shipped item's account of Paige is half right.</b> &ldquo;On hiatus&rdquo; matches 6.12.0's
<code>removals.txt</code>, but it also says <code>bmad-agent-tech-writer</code> &ldquo;never existed to
invoke&rdquo;. <code>removals.txt</code> lists it under removed bmm agents as <em>&ldquo;retired —
capabilities were generic LLM defaults&rdquo;</em> (v6.11.0, #2658). That is the same release that shimmed
the one skill boost gave her.

<b><code>install --scope global</code> leaves the build skill broken.</b> Run from origin/main against a
throwaway HOME, it printed <code>installed 29 BMAD skill(s) globally</code>. <code>bmad-build</code> and
<code>bmad-build-auto</code>, the only 2 of the 29 that do this, start by running
<code>{project-root}/_bmad/scripts/render_skill.py</code> and HALT if it fails. In a repo without
<code>_bmad/</code> that is <code>uv</code> exit 2, <code>Failed to spawn … No such file or directory</code>.
The install prints one dim line about <code>boost bmad init</code> (<code>commands/bmad.py:448</code>)
that does not name those skills.

<b>The global path also hides drift.</b> On either scope, installer output is captured
(<code>commands/bmad.py:415</code>), and only a failure's last line is shown (<code>:422</code>). Global
state records no version (<code>:444</code>, unlike <code>:472</code>), and the staged
<code>manifest.yaml</code> that has one is deleted (<code>:496</code>). The copy replaces only directories
the new stage has (<code>:486</code>). Upstream's own cleanup removes what the previous manifest listed plus
<code>removals.txt</code> entries, but it runs inside the empty stage, never against
<code>~/.claude/skills</code>. With the installer stubbed to emit the real 6.12.0 output, a pre-existing
<code>bmad-document-project</code> survived (30 directories on disk).

<b>Fix.</b> <i>(1)</i> Add <code>BMAD_VERSION = "6.12.0"</code> in <code>core/bmad.py</code> and install that,
not <code>@latest</code>. <i>(2)</i> Check in that install's <code>canonicalId</code> column as a versioned
snapshot. Add a test in <code>tests/unit/test_bmad_core.py</code> that every persona, track and
<code>orientation()</code> skill is in it and that its version equals <code>BMAD_VERSION</code>. A pin bump
without a regenerated snapshot then fails CI, and the denylist at <code>test_bmad_core.py:431</code> is
redundant. <i>(3)</i> Make <code>Track.skill</code> optional, drop it for <code>docs</code> (so the banner
omits that line and <code>:207</code> skips the row), and give Paige <code>bmad-project-context</code> for
agent-instruction files only. <i>(4)</i> Have <code>install --scope global</code> name the build skills
that need <code>boost bmad init</code> per repo, and record the staged version and skill list. On reinstall,
it should remove recorded skills the new stage lacks, not every <code>bmad-*</code> directory, since some may
be the user's own. Extend <code>tests/functional/test_cli_bmad.py</code>, which asserts <code>@latest</code>
(<code>:74</code>) and reinstalls the same three skills twice (<code>:264</code>).

<b>Declined: routing <code>docs</code> at <code>bmad-project-context</code>.</b> Upstream names it as the
replacement, but it manages a block in <code>AGENTS.md</code> (&ldquo;Use when invoked by name&rdquo;), and
the shim says deeper docs material is &ldquo;not part of that block&rdquo;. Sending every README edit there
would trade a dead pointer for a misroute.
