---
id: gstack-tap-first-then-coexistence
board: code
section: compat
status: shipped
category: Interop · Registry
complexity: M
impact: Med
wow: 3
note: 130k stars of SKILL.md that boost can index today, and a second installer writing into the same dotdirs
order: 106
owner: feat/gstack-registry
pr:
title: <code>garrytan/gstack</code> &mdash; tap it first, then learn to coexist with it
---
<a href="https://github.com/garrytan/gstack">garrytan/gstack</a> is the largest thing in
boost's domain that boost has never heard of: <b>130,344 stars, 19,602 forks</b>, MIT, created
2026-03-11 and pushed the same day this was written. It ships <b>61 measured items</b> &mdash; the repo
<em>description</em> advertises 23 and its README lists ~35, and
<code>scripts/measure_registry.py</code> over a sparse clone of <code>07b59e39</code> counts 61
&mdash; <code>/review</code>, <code>/ship</code>, <code>/qa</code>, <code>/cso</code>,
<code>/autoplan</code>, <code>/office-hours</code> among them, each as a
<code>&lt;name&gt;/SKILL.md</code> directory at the repo root, which is <em>exactly</em> the
layout <code>catalog.scan_dir</code> already indexes. Nothing needs building for boost to
catalogue it.

<b>Tier 1 &mdash; tap it. This is the whole cheap win, and it is real.</b> Add one
<code>SKILLS</code> row to <code>scripts/build_registries.py</code> and regenerate. Two cautions,
both boost's own doctrine: <code>est_items</code> must come from
<code>scripts/measure_registry.py</code>, not a guess &mdash; the repo <em>description</em>
advertises "23 opinionated tools" while the README's own install blurb lists 35 slash commands,
so the count is precisely the kind of claim that gate exists to settle. And the
<code>category</code> comes from the names of the items it ships, not from the README: these are
sprint-workflow roles, so <code>workflow</code>, not <code>meta</code>. The sparse cone earns its
keep here &mdash; the repo is ~123&nbsp;MB and TypeScript, and
<code>gitutil.SPARSE_PATTERNS</code> fetches only the Markdown, which for gstack still means a
1&nbsp;MB <code>CHANGELOG.md</code>, a 222&nbsp;KB <code>TODOS.md</code> and a
<code>review/SKILL.md</code> that is 57&nbsp;KB on its own.

<b>Tier 2 &mdash; the honest limit of <code>boost install</code>.</b> A gstack skill is not a
Markdown file. Its install is
<code>git clone --single-branch --depth 1 … ~/.claude/skills/gstack &amp;&amp; ./setup</code>,
where <code>setup</code> is a 120&nbsp;KB script that renders per-host variants from ten
TypeScript configs in <code>hosts/</code>, and where <code>/browse</code> and <code>/qa</code>
drive a real Chromium behind Bun&nbsp;≥1.0 (plus Node on Windows). boost copies Markdown and
symlinks it. So <code>boost install gstack-review</code> can produce a skill that <em>looks</em>
installed and cannot run &mdash; the failure mode <code>store.source_dir_for</code> and
<code>gitutil.materialize</code> exist to prevent, and one that materializing cannot fix here
because the missing step is <code>bun install</code>, not a fetch. The right answer is to
<b>say so</b>: a registry entry that carries an explicit "installs itself, run its
<code>./setup</code>" marker and refuses to half-copy, rather than an integration that pretends.
Boost should not own bun, Chromium, or someone else's upgrade channel.

<b>Tier 3 &mdash; coexistence, which is the part that is actually about boost.</b> gstack writes
into the same places boost does, and at 130k stars it is now the likeliest other tenant on a
user's machine:

<b>The canonical store.</b> <b>Corrected on implementation:</b> this card claimed repo-local
gstack installs land at <code>.agents/skills/gstack</code>. They do not &mdash; gstack's README
installs to <code>~/.claude/skills/gstack</code>, a <em>real directory</em> inside a linking
agent's skills dir, and the team install bootstraps <code>.claude/</code> rather than
<code>.agents/</code>. The hazard is real either way and lands one path over:
<code>store.duplicate_discovery()</code> is already <em>topology, not ownership</em>, and
<code>sync_plan</code>'s stale-link sweep asks <code>is_symlink()</code> before anything else, so
gstack's real directories are never candidates. Neither had a test saying so, and the cost of
being wrong is an 8&nbsp;MB working install of someone else's program deleted as "boost's stale
links".

<b>Host dotdirs boost does not target.</b> gstack installs to
<code>~/.codex/skills/gstack-*</code>, <code>~/.config/opencode/skills/gstack-*</code>,
<code>~/.cursor/skills/gstack-*</code>, <code>~/.factory/skills/gstack-*</code> and
<code>~/.kiro/skills/gstack-*</code>, and notes that Slate reads <code>.claude/skills</code> as a
fallback. That table is a free, externally-maintained cross-check on boost's own agent table
&mdash; and a shortlist of the next targets worth having.

<b>One <code>settings.json</code>, two writers.</b> <code>./setup</code> registers a default-on
<code>gstack-timeline-stop</code> Stop hook in <code>~/.claude/settings.json</code>, and every run
first calls <code>gstack-settings-hook prune-stale --repoint</code>, which "removes dead gstack
hook entries &hellip; and collapses duplicates". boost's ownership mechanism in the same file is
<code>claude_settings.MARKER = "# boost:"</code>. The namespaces look disjoint and the claim is
that each prunes only its own &mdash; but that is an assumption boost currently has no test for,
and the cost of it being wrong is a user's hooks silently disappearing. <code>boost doctor</code>
should be able to <em>see</em> a foreign hook block and report it without touching it.

<b>Deliberately out of scope:</b> vendoring gstack, re-implementing its skills, or having boost
run <code>./setup</code>. The proposal is one registry row, one honest "self-installing" marker
on the install path, and one coexistence test per hazard named above &mdash; scoped down on purpose,
because the fit is a catalogue fit, not an engine fit.
