---
id: gemini-duplicate-skill-discovery
board: code
section: health
status: inflight
category: Interop · Bug
complexity: S
impact: Med
wow: 3
note: Gemini warned once per skill per session and no boost surface could see it
order: 40
owner: loop/gemini-stale-links
pr:
title: Gemini logged a skill conflict every session and <code>boost doctor</code> called the machine healthy
---
Gemini CLI printed this on <b>every session start, once per skill</b>, on a machine whose
<code>boost doctor</code> reported <code>● healthy</code>:

<code>⚠ Skill conflict detected: "hyperframes" from "~/.agents/skills/hyperframes/SKILL.md" is
overriding the same skill from "~/.gemini/skills/hyperframes/SKILL.md".</code>

<b>The architecture predicted this exact failure and nothing checked for it.</b> Gemini implements the
Agent Skills standard and discovers <code>~/.agents/skills</code> — the canonical store — directly, so
it is configured <code>links_skills: false</code> and boost never symlinks into
<code>~/.gemini/skills</code>. The <code>linking_agents</code> note in <code>core/agents.py</code>
spells out the consequence of a second copy: the <code>.agents</code> alias out-ranks
<code>.gemini/skills</code>, so the duplicate can never win, and it costs a warning line per skill per
session. That reasoning was written down, enforced on boost's own writes, and then never verified
against what is actually on disk.

<b>Boost did not create the duplicate, and that is the point.</b> The first read of this bug was
"boost linked before <code>links_skills: false</code> and never cleaned up", which would have made the
fix a migration sweep. Measurement killed it: of the 25 symlinks in the live
<code>~/.gemini/skills</code>, <b>24 lead to <code>~/.claude/skills</code> directories boost does not
manage at all</b> and are another tool's installer output. Exactly one — <code>hyperframes</code> —
resolves into the canonical store, and it is a third-party link that happens to land on a skill boost
installed. A sweep that deleted "boost's stale links" would have deleted 24 files belonging to
somebody else to fix a bug that was not there.

So the check is <b>topology, not ownership</b>: an entry in a <code>links_skills: false</code> agent's
skills dir whose <em>resolved</em> location is inside the canonical store. Whoever wrote it, the agent
loads one skill from two discovery tiers, which is precisely what it complains about.

<b>The resolution has to be full, and the live chain proves it.</b> The real link is
<code>~/.gemini/skills/hyperframes → ../../.claude/skills/hyperframes → ~/.agents/skills/hyperframes</code>
— a relative first hop into <em>another agent's</em> dir, whose entry is then boost's own store
symlink. <code>store.points_into_store</code> reads a single <code>readlink()</code> (correctly: it
judges <em>broken</em> links, where there is nothing to resolve) and stops at
<code>~/.claude/skills</code>, reading the duplicate as foreign. The new
<code>store.resolves_into_store</code> resolves <b>both sides</b> — a sandbox <code>$HOME</code> under
macOS's <code>/var/folders</code> resolves to <code>/private/var/…</code>, so resolving only the
target compares a real path against a nominal one and never matches — and decides containment with
<code>commonpath</code>, so <code>~/.agents/skills-backup</code> stays out.

<b>Detection ships enabled; removal is opt-in and re-gated.</b> <code>boost doctor</code> counts each
duplicate as an issue and names the agent, both paths and one next action.
<code>boost heal</code> names them every run but removes nothing;
<code>boost heal --prune-duplicates</code> removes them, and
<code>store.remove_duplicate_discovery</code> re-checks against the filesystem that the entry is still
a symlink still resolving into the store before it unlinks. A real directory is refused, a link
repointed since the scan is refused. Deleting another tool's file on the strength of a stale report is
worse than the warning it clears.

<b>Why it was invisible.</b> <code>heal</code>'s broken-link sweep walks <code>linking_agents</code>,
which deliberately excludes Gemini, so nothing ever looked in that directory — and the links are not
broken anyway, so a dangling-link sweep would have missed them there too. Two correct decisions
composed into a blind spot, which is the shape most of these have.
