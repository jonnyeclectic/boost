---
id: audit-pulse-findings
board: code
section: dx
status: inflight
category: CLI · UX
complexity: S
impact: Med
wow: 1
note: "fix implemented + tested; make check's eval/mutation/smoke gates could not run locally (no PyPI egress) — see PR for what did run"
order: 283
owner: loop/pulse-who-filtered-empty
pr:
title: "<code>boost pulse</code>: CLI audit findings (2026-08)"
---
<b><code>pulse --action</code> and <code>who &lt;name&gt;</code> claim "no activity yet" when only the filter is empty.</b> Reproduced with a populated journal: <code>pulse --action nosuch</code> prints <code>○ no activity yet — events appear as you install and manage skills</code> and <code>who nosuchskill-zzz</code> prints <code>○ no journal activity yet — expertise builds as people install, edit, and evolve skills</code> — while <code>pulse.jsonl</code> held 35 events at audit time (23 on re-verification; both matched verbatim). Both commands compute a filtered <code>events</code> list and print the same global empty state when it is empty, with no branch distinguishing filter-empty from journal-empty — so the output asserts a state ("nothing has happened on this machine") that is simply false, and hides that the user's filter value matched nothing.<br><br>Verified fix (<code>boost_cli/commands/team.py:518-522</code> for <code>cmd_pulse</code>, <code>team.py:692-702</code> for <code>cmd_who</code>): when <code>args.action</code> / the skill argument is set and the unfiltered journal is non-empty, print a filter-specific empty state naming the filter value — e.g. <code>○ no events with action "nosuch" (35 events in the journal)</code> — ideally listing the distinct actions present; for <code>who</code>, name the subject and say "not installed" or offer a did-you-mean when the name is close to a known one. Keep the current message only for a truly empty journal. No flag changes, so no docs regeneration needed.<br><br>Found by the 2026-08 CLI audit (cluster <code>filtered-empty-state</code>); repro in the audit log.

<br><br><b>Status.</b> Implemented as two pure helpers in <code>core/journal.py</code>
(<code>pulse_empty_state</code>, <code>who_empty_state</code>, unit-tested) consumed by
<code>cmd_pulse</code>/<code>cmd_who</code>; <code>who_empty_state</code> also covers the
"installed but no journal history" case and a <code>difflib</code>-based did-you-mean
against subjects that actually appear in the journal. Verified end to end against a real
build (the exact repro commands from this card) and with functional/unit tests added. This
session's sandbox had no PyPI/apt egress (a verified, repeated 403), so the pinned
<code>make check</code> toolchain (ruff/mypy pins, pytest-cov, mutmut, the eval corpus)
could not be installed; what ran instead with the system-provided <code>ruff</code>
0.15.8 / <code>mypy</code> 1.19.1 / <code>pytest</code> 9.0.2 (bound to Python 3.11, not
the repo's required 3.12): <code>ruff</code> and <code>mypy</code> clean on every changed
file; the new/changed tests all pass (58 assertions across
<code>tests/unit/test_journal.py</code> and the pulse/who classes in
<code>tests/functional/test_cli_team.py</code>); the full <code>tests/unit</code> suite
and <code>tests/smoke.sh</code> reproduce the same failures on this diff as on unmodified
<code>main</code> under the same tool (all traced to <code>shutil.rmtree(onexc=...)</code>,
a Python-3.12-only kwarg, being run under the sandbox's Python-3.11-backed pytest — a
pre-existing environment artifact, not a regression). CI has real network access and
should run the full gate before merge.
