---
id: audit-skill-profile-name-slugging-is-inconsistent-distill-o-accept
board: code
section: dx
status: inflight
category: CLI · UX
complexity: S
impact: Med
wow: 1
note: fix implemented and tested; full `make check` unverified — see below
order: 226
owner: loop/name-slugging-consistency
pr: 779
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

<br><br><b>Still open</b> &mdash; the fix itself landed (<code>util.slugify_or_raise</code> plus the four
call sites and the <code>profile list</code>/<code>save</code> collision handling, all with new unit and
functional tests), but this session's sandbox could not reach <code>pypi.org</code>/
<code>files.pythonhosted.org</code> (a verified, repeated 403 from the egress policy, on both the direct
and proxied paths) to install the project's pinned toolchain, so the required <code>make check</code>
gate could not be run in full: no <code>pip install -e .</code>, no <code>coverage</code>/<code>mutmut</code>/
<code>pyright</code>/<code>vulture</code>/<code>xenon</code>/<code>interrogate</code>/<code>refurb</code>/
<code>codespell</code>/<code>actionlint</code>/<code>zizmor</code>/<code>import-linter</code>, and no
<code>eval</code> corpus build. Verified instead with what the sandbox already had: <code>ruff</code> and
<code>mypy</code> (unpinned, locally pre-installed) are clean on every changed file; the full
<code>tests/unit</code> and <code>tests/functional</code> suites pass under Python 3.12 (three pre-existing
<code>tests/unit</code> failures are root-vs-chmod sandbox artifacts, reproduced identically on unmodified
<code>origin/main</code>, not a regression); <code>tests/smoke.sh</code> passes 177/177; and
<code>build_registries.py</code>/<code>build_roadmap.py</code>/<code>build_command_reference.py --check</code>
are clean. Whoever picks this back up needs a session with real PyPI egress to run the coverage and
mutation gates and confirm the 90%/80% floors.
