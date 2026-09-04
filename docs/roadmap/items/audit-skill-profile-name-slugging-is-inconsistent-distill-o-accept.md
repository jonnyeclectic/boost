---
id: audit-skill-profile-name-slugging-is-inconsistent-distill-o-accept
board: code
section: dx
status: shipped
category: CLI · UX
complexity: S
impact: Med
wow: 1
note: distill accepts "Bad Name!!", then its own import hint rejects it
order: 226
owner: loop/name-slugging
pr: 752
title: "Name slugging is inconsistent: <code>distill -o</code> accepts what <code>import</code> rejects; <code>create</code>/<code>profile</code> slug silently"
---
Three commands treat the same problem &mdash; a user-typed name that is not a valid slug &mdash; three
different ways, and one of them contradicts itself. <code>distill -o "Bad Name!!"</code> writes
<code>&hellip;/Bad Name!!/SKILL.md</code> and hints <em>&ldquo;install it with <code>boost import ./Bad
Name!!</code>&rdquo;</em> (unquoted); following the hint fails with <em>&ldquo;Error: invalid skill name 'Bad
Name!!'&rdquo;</em>. Meanwhile <code>infer --name "My Conventions!!"</code> slugifies to
<code>my-conventions</code> &mdash; the raw pass-through is <code>intelligence.py:172</code> against the
slugify at <code>intelligence.py:316</code>, in the same module.

<code>create</code> slugifies silently with a fallback (<code>configuration.py:350</code>):
<code>create '___'</code> &rarr; <code>&#10003; created &hellip;/skill/SKILL.md</code>, <code>create ''</code>
&rarr; <em>&ldquo;Error: &hellip;/skill/SKILL.md already exists&rdquo;</em> &mdash; a path the user never typed
&mdash; and <code>create '&Uuml;n&iuml;code Skill &#10003;'</code> &rarr; <code>n-code-skill/</code> with no
note that the name changed. <code>profile save</code> slugifies for the filename only
(<code>team.py:192</code>): <code>profile save '!!!'</code> lands on the slug-fallback file
<code>skill.json</code>, so <code>'!!!'</code> and a profile literally named <code>skill</code> silently share
one file; <code>profile list</code> (<code>team.py:248-253</code>) shows raw names but sorts by the slugged
filename, so the rows print as <code>daily, mixed, !!!, Work Profile</code> &mdash; an order that matches
nothing on screen. <code>"My Daily"</code> and <code>"my-daily"</code> would overwrite each other without a
word.

Fix per the verified recommendation: one shared helper &mdash; slugify, refuse an empty or fallback-only
slug (<em>&ldquo;name has no letters or digits&rdquo;</em>), and print the slug whenever it differs from what
was typed. Apply it to <code>distill -o</code> (plus <code>shlex.quote</code> in the import hint),
<code>create</code>, and <code>profile save</code>; sort <code>profile list</code> by the displayed name.
Regenerate docs/commands.html if create/distill help text changes. Found by the 2026-08 CLI audit
(cluster generated-name-slugging); repro in the audit log.
