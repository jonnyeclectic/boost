---
id: heal-deleted-links-it-never-made
board: code
section: internals
status: shipped
category: Safety · Correctness
complexity: S
impact: Medium
wow: 4
note: a dangling link is not garbage — an unmounted volume comes back, and heal deleted it anyway
order: 99
owner: fix/heal-only-removes-links-it-owns
pr: 459
title: heal removed symlinks boost never created
---
<b><code>boost heal</code> deleted a symlink boost did not make, does not track, and has no claim
to.</b> Reproduced against a sandbox: plant
<code>~/.claude/skills/my-own-skill&nbsp;&rarr;&nbsp;~/elsewhere/my-own-skill</code>, run
<code>boost heal</code>, and it reports <i>"removed broken link ~/.claude/skills/my-own-skill"</i>.
Same scenario on the fixed build leaves it exactly where it was.

<b>A broken link is not the same as garbage.</b> <code>~/.claude/skills/</code> is the user's own
directory that boost happens to link into. A dangling entry there can be a skill on an unmounted
volume, a repo checked out somewhere else for the afternoon, or a link into a detached drive
&mdash; all of which come back. Removing one is not a repair; it is data loss under a reassuring
name, from a command whose entire promise is that it is safe to run.

<b>Ownership is legible from the link itself.</b> Every link boost creates points into the canonical
store, <code>~/.agents/skills/&lt;name&gt;</code>. Reading the target beats consulting the lock,
because the two moments a dangling link is most likely to exist &mdash; a skill uninstalled
mid-sweep, a lock file that has gone missing &mdash; are exactly the moments the lock cannot answer.
Links into the store are swept; everything else is <i>named</i> and left alone, because the user
should still know it is dangling.

<b>The scan was also looking somewhere it has no business.</b> <code>_broken_links</code> iterated
<code>agents.enabled_agents()</code>, which includes Gemini &mdash; and boost never links into
<code>~/.gemini/skills</code> at all, because Gemini CLI reads the canonical store directly.
CLAUDE.md states the rule outright: iterate <code>linking_agents()</code> "for anything
symlink-shaped (link, unlink, stale-link sweeps, coverage counts)". The <i>same function</i> already
had it right eleven lines further down, where <code>cmd_heal</code> builds its list of missing
directories and comments on precisely this distinction.

<b>A macOS-only trap sat inside the fix.</b> The first attempt compared
<code>store_dir().resolve()</code> against a normalised link target &mdash; resolving the side that
exists and not the side that does not. On macOS <code>/tmp</code> is itself a symlink to
<code>/private/tmp</code>, so a genuine boost link read as foreign and <code>heal</code> declined to
repair anything at all. Both sides are now resolved down to their deepest real ancestor, which is
the only comparison that is correct when one path is dangling by definition.

<b><code>doctor</code> reports it without going red.</b> A foreign broken link is printed as
information, not counted as an issue: <code>heal</code> deliberately will not fix it, so counting it
would leave <code>doctor</code> permanently red on something no boost command can clear &mdash;
which is how a health check stops being read. Two tests pin the behaviour and both fail with the
ownership check reverted.
