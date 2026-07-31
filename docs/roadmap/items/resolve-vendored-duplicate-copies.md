---
id: resolve-vendored-duplicate-copies
board: code
section: dx
status: shipped
category: Catalog · DX
complexity: S
impact: Med
wow: 4
note: found by dogfooding — the fix hint re-raised the error it was fixing
order: 78
owner:
pr:
title: <code>install</code> dead-ends on a registry that vendors its own skills
---
<b>Found by using boost, not by reading it.</b> Installing
<code>debugging-and-error-recovery</code> failed with <code>exists in multiple taps:
addyosmani/agent-skills, lingxling/awesome-skills-cn, lingxling/awesome-skills-cn,
lingxling/awesome-skills-cn</code> &mdash; one tap named <b>three times</b>, under a heading that
says &ldquo;multiple taps&rdquo;. Following the hint made it worse, and this is the part that
matters: qualifying by tap re-raised <b>the identical error</b>, now hinting
<code>lingxling/awesome-skills-cn:lingxling/awesome-skills-cn:debugging-and-error-recovery</code>
&mdash; a string that can never resolve. The escape route from the error was the error.

<b>Three defects behind one symptom.</b> The message joined <code>e["tap"]</code> across matches
with no dedupe, so a repeated tap read as repeated registries. The hint re-qualified
<code>name</code> rather than the bare name, so an already-qualified input got a second prefix. And
&ldquo;qualify it by tap&rdquo; is not advice at all when every candidate <em>shares</em> a tap.

<b>The cause is a registry convention, not a corrupt cache.</b>
<code>lingxling/awesome-skills-cn</code> vendors its own skills into plugin bundles, so the same
skill exists at <code>antigravity/skills/dbg</code>, <code>.../plugins/pack/skills/dbg</code> and
<code>.../plugins/pack-claude/skills/dbg</code> &mdash; three paths, one identical
<code>search_blob</code>. boost was asking the user to choose between three rows that render
identically everywhere it displays them. That prompt is unanswerable by construction.

<b>So it now chooses, but only where choosing is safe.</b> When every candidate shares a tap
<em>and</em> is indistinguishable on name, description, version and frontmatter, boost resolves to
the shallowest path &mdash; the original, since vendored copies sit deeper by construction &mdash;
tie-broken lexicographically so the pick cannot drift with dict order between machines. The earlier
duplicate census is what makes this safe rather than merely convenient: of 29,938 entries, 78.3%
are byte-identical duplicates and <b>zero</b> content-clusters span more than one name, so
collapsing identical rows can never merge two genuinely different skills.

<b>Two cases deliberately still refuse.</b> Identical content in <em>different</em> taps stays an
error &mdash; two registries shipping the same text are still two supply chains, and
<code>typosquat.py</code> exists because that distinction is load-bearing. Same tap but genuinely
different rows also stays an error, since the user can tell them apart and the choice is theirs;
that case now names the conflicting <em>paths</em>, because the path is the only thing that
distinguishes them, instead of offering a tap qualifier that cannot help.

<b>Nine tests, written before the fix.</b> Five failed against the old resolver and the two
&ldquo;still refuses&rdquo; guards passed from the start, which is what showed the change was
additive rather than a loosening. Verified end to end against the real catalogue: the qualified
form now resolves to <code>antigravity-awesome-skills/skills/debugging-and-error-recovery</code>,
the top-level copy.
