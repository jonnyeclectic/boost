---
id: agent-dir-guards
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: High
wow: 3
note: an agent row with no dir linked skills into the working directory, and a disabled agent kept dangling links nobody looked for
order: 374
owner:
pr:
title: An agent row with no <code>dir</code>, and links left in a disabled agent's dir
---
<b>An agent row with no <code>dir</code> linked skills into the working directory.</b>
<code>boost config set agents.curosr.enabled true</code> saves a row with no dir, after its
"did you mean" warning. <code>known_agents</code> expanded the missing value to
<code>Path("")</code>, which is <code>.</code>. So <code>boost install</code> put a
<code>brainstorming</code> symlink in whatever directory it ran from, reported the skill linked
for <code>curosr</code>, and left that link dangling once you uninstalled from somewhere else.
<code>boost doctor</code> said healthy. A row whose dir is missing, blank, <code>.</code>, or
expands to nothing is now <b>skipped</b>, with one warning per command that names the key to
set or unset. <code>boost doctor</code> reports it as an <code>agent-config</code> issue. Unlike
an unresolvable <code>${VAR}</code>, it does not switch the other checks off.

<b>Uninstalling while an agent was disabled left that agent's link dangling.</b>
<code>unlink_agents</code> walked only enabled agents. Disable cursor, uninstall a skill, and
<code>~/.cursor/skills/&lt;name&gt;</code> was left pointing at the deleted store dir, where
Cursor still read it. Doctor's broken-link sweep had the same filter, so it never saw the
link. Both now use <code>agents.unlinking_agents()</code>: every agent that links skills,
enabled or not. Removal still goes through <code>is_boost_link</code>, so a real directory, or
a link that does not point into the store, is left alone. Native-store agents
(<code>links_skills: false</code>, Gemini's shared <code>~/.gemini/skills</code>) stay out of
the set.
