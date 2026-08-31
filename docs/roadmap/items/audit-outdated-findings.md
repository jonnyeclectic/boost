---
id: audit-outdated-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: an untapped skill vanishes from outdated; the same untapped rule shows "source missing"
order: 278
owner:
pr:
title: "boost outdated: CLI audit findings (2026-08)"
---
<code>boost outdated</code> handles the same condition two ways depending on item kind. With the skill
<code>brainstorming</code> installed and its source tap untapped, <code>outdated</code> prints
<em>&ldquo;&#10003; everything up to date&rdquo;</em> &mdash; the skill is silently omitted. Do the same to a
rule and it is reported honestly: <em>&ldquo;code-signing (rule)&nbsp; 0.0.0&nbsp; source missing&nbsp;
Aaronontheweb/dotnet-cursor-rul&hellip;&rdquo;</em>, with the footer <em>&ldquo;1 outdated &middot; `boost
update` upgrades (pinned items stay put)&rdquo;</em> &mdash; a promise <code>boost update</code> cannot keep
for an item whose source is gone.

<br><br>The asymmetry is mechanical and looks unintentional: the skill loop
(<code>boost_cli/commands/taps.py:273-280</code>) silently <code>continue</code>s when
<code>catalog.find</code> has no row for the tap, while the rule/workflow loop
(<code>taps.py:318-344</code>) catches the failure and appends a <em>source missing</em> row &mdash; the skill
path has no comment justifying the skip. Fix: in the skill loop, append a <em>source missing</em> result
instead of <code>continue</code>, matching the rule path, and word the footer per reason so it never sends
source-missing rows to <code>boost update</code>. No flag changes, so <code>docs/commands.html</code> needs no
regeneration. Found by the 2026-08 CLI audit (cluster <code>outdated-untapped-skill</code>); repro in the
audit log.
