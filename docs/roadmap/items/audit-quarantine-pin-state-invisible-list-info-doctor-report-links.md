---
id: audit-quarantine-pin-state-invisible-list-info-doctor-report-links
board: code
section: health
status: planned
category: Safety · Bug
complexity: S
impact: Med
wow: 2
note: doctor says "healthy, 1 skill with agent links" when the only skill is quarantined
order: 236
owner:
pr:
title: "Quarantine/pin state invisible: <code>list</code>/<code>info</code>/<code>doctor</code> report links and materializations that were removed"
---
Quarantine records its state but the reporting surfaces never consult it. After
<code>boost quarantine brainstorming</code> removes all four agent links on disk,
<code>boost doctor</code> still prints <em>&ldquo;&#10003; 1 skill present in store with agent
links&rdquo;</em> and <em>&ldquo;&#9679; healthy&rdquo;</em>; <code>list</code> keeps the AGENTS cell
<em>&ldquo;claude&middot;windsurf&middot;curs&hellip;&rdquo;</em> because
<code>cmd_quarantine</code>'s skill path sets <code>quarantined=True</code> but leaves
<code>entry["agents"]</code> as installed (<code>safety.py:514-518</code>). Verified against disk:
<code>~/.claude/skills</code> empty and <code>~/.claude/CLAUDE.md</code> gone while list/info still
claim the links. <code>info dotnet-build</code> on a quarantined rule prints
<em>&ldquo;[quarantined] &hellip; materialized claude-code, windsurf, cursor, gemini&rdquo;</em>
&mdash; files that no longer exist &mdash; because <code>_info_materialized</code> renders the
lock's list with no disk or quarantine check (<code>info.py:344-388</code>).

The rules and workflows tables compound it: they have no FLAGS column at all, so a quarantined or
pinned rule renders byte-identical to a healthy one (<code>pin dotnet-build</code> shows
<code>"pinned": true</code> in <code>--json</code> and nothing in the table) &mdash; a user cannot
see what <code>update</code> will skip or what <code>cat</code> will refuse. Doctor's rules branch
deliberately excludes quarantined items (comment at <code>quality.py:500-506</code>) but then
reports nothing &mdash; the &ldquo;1 rule fully materialized&rdquo; line silently vanishes &mdash;
and the skills count at <code>quality.py:473</code> includes quarantined ones: the exclusion logic
exists, the reporting does not. All six findings reproduced.

Verified fix: clear <code>entry["agents"]</code> on quarantine (release already rewrites it,
<code>safety.py:514-518</code>) &middot; add the FLAGS column to <code>_kind_table</code> for
rules and workflows and render AGENTS as &mdash; when quarantined &middot; have
<code>_info_materialized</code> print &ldquo;(removed &mdash; quarantined)&rdquo; &middot; in
<code>cmd_doctor</code> append &ldquo;(N quarantined)&rdquo; to the per-kind summary lines and
exclude quarantined skills from &ldquo;with agent links&rdquo; &middot; optionally return
&ldquo;quarantined&rdquo; from verify/drift for skills as they already do for rules. Docs:
docs/carousel.html (doctor recording alt text, if the wording changes). Found by the 2026-08 CLI
audit (cluster <code>quarantine-pin-invisible</code>); repro in the audit log.
