---
id: audit-adapt-run-stats-edit-tag-export-reject-the-tap-name-qualifie
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: M
impact: High
wow: 1
note: adapt's hint says type tap:name; typing exactly that string is "invalid skill name"
order: 217
owner: loop/tap-qualifier-resolvers
pr:
title: "adapt/run/stats/edit/tag/export reject the <code>tap:name</code> qualifier that info/install accept and adapt's own hint recommends"
---
<code>boost adapt test-driven-development --to crewai</code> answers <em>&ldquo;exists in multiple
taps &hellip; hint: qualify it, e.g.
<code>NeoLabHQ/context-engineering-kit:test-driven-development</code>&rdquo;</em> &mdash; and typing
exactly that string answers <em>&ldquo;Error: invalid skill name
'NeoLabHQ/context-engineering-kit:test-driven-development'&rdquo;</em>, exit 1. Same for
<code>run --print</code>. <code>info</code> with the identical string prints the full card, exit 0.
Two more shapes of the same defect, both verified: <code>stats</code> given the bare ambiguous name
<b>silently picks the first tap</b> and reports its version/upstream as if unambiguous (where
<code>info</code> refuses and asks to qualify), and given the qualifier says &ldquo;invalid skill
name&rdquo; with no hint; <code>edit</code>, <code>tag</code> and <code>export</code> pass the whole
qualified string to the lock lookup and answer <em>&ldquo;is not installed&rdquo;</em> for a skill
that is installed from that very tap (<code>explain</code>/<code>log</code>/<code>home</code> accept it).

The verification found two rejection mechanisms behind one symptom:
<code>adapt</code>/<code>run</code>/<code>stats</code> hit <code>store.skill_store_dir</code>'s
&ldquo;invalid skill name&rdquo; (<code>boost_cli/core/store.py:63-69</code>) before
<code>catalog.resolve_one</code> is ever reached, while
<code>edit</code>/<code>tag</code>/<code>export</code> hand the unsplit string to the lock. The shipped
<em>info-rejects-the-qualified-name-it-recommends</em> item fixed <code>info</code>/<code>install</code>
only; these six are residual scope, and the ambiguity hint they emit is now actively wrong for them.

Fix (verified recommendation): in <code>pkg._resolve_skill</code>
(<code>boost_cli/commands/pkg.py:1683-1701</code>), probe <code>store.skill_store_dir</code> only when
the name is a safe bare component, else fall through to <code>catalog.resolve_one</code>, which already
parses <code>tap:skill</code>. In <code>cmd_edit</code>/<code>cmd_tag</code>/<code>cmd_export</code>/<code>cmd_stats</code>,
split with <code>catalog.split_name</code>, look the bare name up in the lock and check the tap
matches. Route all six through one shared resolver helper so the next command cannot regress alone.
Docs: <code>docs/adapters.html</code>; regenerate <code>docs/commands.html</code> if usage lines change
(e.g. <code>stats</code>' positional becoming &ldquo;skill name or <code>owner/repo:name</code>&rdquo;).
Found by the 2026-08 CLI audit (cluster <code>qualifier-rejected-elsewhere</code>); repro in the audit log.
