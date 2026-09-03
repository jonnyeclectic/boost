---
id: audit-rules-workflows-reported-as-skills-uninstall-claims-a-store
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: M
impact: High
wow: 2
note: rule uninstall prints 'removed ~/.agents/skills/…' for a dir that never existed
order: 210
owner: loop/audit-kinds-not-skills
pr:
title: "Rules/workflows reported as 'skills': <code>uninstall</code> claims a store dir that never existed"
---
All three kinds install by design, but five commands describe every kind as a skill — and
<code>uninstall</code> goes further, narrating actions that never happened. Uninstalling the
<em>rule</em> <code>benchmarking</code> prints <em>&ldquo;&#10003; unlinked &larr; claude-code &middot;
windsurf &middot; cursor &middot; gemini&rdquo;</em> / <em>&ldquo;&#10003; removed
~/.agents/skills/benchmarking&rdquo;</em> / <em>&ldquo;Uninstalled 1 skill&rdquo;</em> — verified live
with the store dir empty: no such directory ever existed and nothing was unlinked; CLAUDE.md blocks and
rule files were deleted. The install side had said <em>&ldquo;Installed 1 new rule&rdquo;</em>, so the
tool contradicts itself across one round trip.

The same kind-blindness runs through the rest. <code>bundle install</code> resolves a
<code>skill dotnet-build</code> Boostfile line to a rule, edits CLAUDE.md/GEMINI.md, and reports
<em>&ldquo;Installed 1 skill&rdquo;</em> — then <code>bundle dump</code> says <em>&ldquo;1 rule not
captured &mdash; Boostfiles carry skills only&rdquo;</em>, so a dump/install round trip does not agree
with itself. <code>taps</code> puts 11 rules under a <code>SKILLS</code> header and footers
<em>&ldquo;20 taps &middot; 10152 skills&rdquo;</em> (3,000+ of those are not skills; the JSON key is
<code>"skills"</code>), although <code>cmd_tap</code> deliberately prints <em>items</em> for exactly
this reason (<code>taps.py:145-147</code>). <code>trending</code> lists a rule and a workflow beside a
skill with no kind marker. And <code>protocol open boost://tap/&hellip;</code> prints
<em>&ldquo;tapped pbakaus/impeccable (42 skills)&rdquo;</em> (<code>team.py:430</code>) for a cache
holding 17 skills + 25 workflows, where <code>boost tap</code> prints <em>&ldquo;(42 items)&rdquo;</em>
for the same count.

Verified fix, one sweep: have <code>store.uninstall</code> return the kind and branch
<code>pkg.py:550-562</code> on it (skip the store-dir line and say &ldquo;removed from&rdquo; rather
than &ldquo;unlinked&rdquo; for rules/workflows, pluralise per kind as <code>cmd_reinstall</code>
already does); count <code>_bundle_install</code> by <code>entry['kind']</code> and make
<code>dump</code> and install agree; rename <code>taps</code>' column/footer/JSON to items (keep
<code>skills</code> as a deprecated JSON alias); change <code>team.py:430</code> to
<code>(%d items)</code>; add a kind column to <code>trending</code> and fix its COMMANDS summary in
<code>cli.py:73</code>. Docs: regenerate <code>docs/commands.html</code> (trending's summary changes in
COMMANDS), and update README.md and <code>docs/index.html</code> where they show taps/bundle output.
Found by the 2026-08 CLI audit (cluster <code>kinds-reported-as-skills</code>); repro in the audit log.
