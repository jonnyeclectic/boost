---
id: audit-bmad-findings
board: code
section: dx
status: inflight
category: CLI · UX
complexity: M
impact: Med
wow: 1
note: an edited persona reads "not installed"; each no-op bmad on burns 4 of 50 history slots
order: 250
owner: loop/bmad-audit-findings
pr:
title: "boost bmad: CLI audit findings (2026-08)"
---
<b>An edited persona is reported as not installed</b> (cluster <code>bmad-edited-persona</code>, med).
After appending one line to <code>~/.claude/agents/bmad-ux.md</code>, <code>bmad on</code> says
<em>&ldquo;&#10003; BMAD autopilot ON (global) &mdash; 6 persona subagent(s)&rdquo;</em> and
<code>bmad personas</code> lists <em>&ldquo;bmad-ux&nbsp;&nbsp;Sally, UX Designer (bmm) &mdash; not
installed&rdquo;</em> &mdash; but seven files are on disk and Claude Code loads all seven. The
ownership model is right (the edited file is skipped, never deleted); only the reporting reuses
&ldquo;managed&rdquo; as &ldquo;installed&rdquo;: <code>installed_personas()</code>
(<code>boost_cli/core/bmad.py:673-677</code>) counts stamp-managed files only, the correct set for
deletion and the wrong one for counts. Fix: a three-state helper (managed / edited / absent) in
<code>core/bmad</code>, render edited files as &ldquo;installed (edited)&rdquo; at
<code>commands/bmad.py:344</code> and count managed+edited at <code>:254</code> and in status;
<code>docs/bmad.md</code> gains the edited state.

<br><br><b>Four status-surface polish defects</b> (cluster <code>bmad-status-polish</code>, low), all
source-confirmed: <code>bmad startup bogus</code> silently falls through to status
(<code>bmad.py:474</code>) although help promises <em>on | off | status</em>; <code>bmad startup
on</code> writes the orient hook <em>without</em> the <code>|| true</code> guard <code>bmad on</code>
applies (<code>bmad.py:459-461</code> vs <code>:247</code> &mdash; <code>_never_fails</code>'s own
docstring explains why the guard exists); a second <code>bmad off</code> claims <em>&ldquo;removed 0
persona(s) and both hooks&rdquo;</em> (<code>:281</code> hardcodes the clause); and status prints
<em>&ldquo;installed=False&rdquo;</em> beside <em>&ldquo;autopilot=off&rdquo;</em>. Fix per the
verified recommendation: raise <code>BoostError</code> for a bad startup value, wrap the startup hook
with <code>_never_fails()</code> and pin it in a test, return a real count from
<code>_remove_hook_everywhere</code>, and format the two booleans with the on/off helper.

<br><br><b>No-op <code>bmad on</code> churns the settings history</b> (cluster
<code>settings-history-churn</code>, low). Three runs in a fresh HOME left four byte-identical
575-byte <code>global-*.json</code> snapshots (md5 <code>791156bf&hellip;</code>) &mdash; each no-op
run consumes 4 of the <code>HISTORY_KEEP=50</code> slots (2 hosts &times; 2 writes), so ~13 no-op runs
evict every real pre-change snapshot. <code>claude_settings.save()</code>
(<code>boost_cli/core/claude_settings.py:80-102</code>) snapshots unconditionally; fix is to serialise
first and return early when the content equals the current file, which also collapses the double write
per host.

<br><br>Found by the 2026-08 CLI audit; repro in the audit log. Behaviour-only fixes &mdash;
regenerate <code>docs/commands.html</code> only if a summary changes; <code>docs/bmad.md</code>
must document the edited-persona state.
