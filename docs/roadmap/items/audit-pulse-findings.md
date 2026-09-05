---
id: audit-pulse-findings
board: code
section: dx
status: inflight
category: CLI · UX
complexity: S
impact: Med
wow: 1
note: a filter matching 0 of 35 events prints the same line as an empty journal
order: 283
owner: loop/pulse-who-filtered-empty
pr:
title: "<code>boost pulse</code>: CLI audit findings (2026-08)"
---
<b><code>pulse --action</code> and <code>who &lt;name&gt;</code> claim "no activity yet" when only the filter is empty.</b> Reproduced with a populated journal: <code>pulse --action nosuch</code> prints <code>○ no activity yet — events appear as you install and manage skills</code> and <code>who nosuchskill-zzz</code> prints <code>○ no journal activity yet — expertise builds as people install, edit, and evolve skills</code> — while <code>pulse.jsonl</code> held 35 events at audit time (23 on re-verification; both matched verbatim). Both commands compute a filtered <code>events</code> list and print the same global empty state when it is empty, with no branch distinguishing filter-empty from journal-empty — so the output asserts a state ("nothing has happened on this machine") that is simply false, and hides that the user's filter value matched nothing.<br><br>Verified fix (<code>boost_cli/commands/team.py:518-522</code> for <code>cmd_pulse</code>, <code>team.py:692-702</code> for <code>cmd_who</code>): when <code>args.action</code> / the skill argument is set and the unfiltered journal is non-empty, print a filter-specific empty state naming the filter value — e.g. <code>○ no events with action "nosuch" (35 events in the journal)</code> — ideally listing the distinct actions present; for <code>who</code>, name the subject and say "not installed" or offer a did-you-mean when the name is close to a known one. Keep the current message only for a truly empty journal. No flag changes, so no docs regeneration needed.<br><br>Found by the 2026-08 CLI audit (cluster <code>filtered-empty-state</code>); repro in the audit log.
