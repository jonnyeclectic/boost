---
id: cli-output-ignored-the-terminal
board: code
section: dx
status: inflight
category: CLI · Output
complexity: S
impact: Med
wow: 3
note: an 80-command sweep found a box that drew wider than the pane, a help screen that never measured it, and a literal %% on screen
order: 125
owner: loop/cli-output-defects
pr: 552
title: The box drew 108 columns into an 80-column pane, and <code>--help</code> never asked how wide the pane was
---
<b>Every one of the 80 commands was run, not just read.</b> All 80 answered
<code>--help</code> with exit 0 and no traceback; ~73 were then driven for their real effect
against a disposable <code>HOME</code> — install, link, quarantine, focus, snapshot, replay,
cohort, hooks and the rest, checking the filesystem after each rather than trusting the success
line. <code>boost focus tdd-workflow</code> was confirmed by listing
<code>~/.claude/skills</code> and finding the other two skills genuinely unlinked with the
canonical store intact, and <code>focus --clear</code> by finding all three back. Seven commands
could not run here and are recorded as blocked rather than passed: <code>serve</code> (the
sandbox denies <code>socket.bind</code>), <code>discover</code> and <code>index</code> (no
<code>gh</code> auth), <code>run</code> live (no Agents SDK — <code>--print</code> was verified
instead), plus the interactive halves of <code>browse</code>, <code>chat</code> and
<code>edit</code>, each of which degraded with a correct hint.

<b>A literal <code>%%</code> was reaching the terminal.</b>
<code>boost cohort</code> printed <code>sha256(user:cohort) %% 100 &lt; rollout</code> and its
<code>--help</code> epilog offered <code>a 50%% rollout</code>. Both strings carry printf
escaping and neither is ever <code>%</code>-formatted, so the escape survived to the screen. The
existing test asserted <code>"membership = sha256(user:cohort)" in r.out</code> — it stops one
character short of the defect, which is exactly how it survived. Four other <code>%%</code> in
the same file are correct: they sit inside real <code>%</code>-format calls, including the
<code>Exec=%s %%u</code> that a <code>.desktop</code> file requires.

<b><code>panel()</code> sized itself to its content and never asked the terminal.</b> Measured:
<code>boost count</code> drew <b>108 columns into an 80-column pane</b>. A box is the worst
thing to overflow, because the border wraps and the shape itself breaks. It now clamps to
<code>term_width() - 4</code> — the four columns the border costs — and clips over-long content,
so every row stays the same width at any pane size.

<b>The help screen was the one screen that never measured the pane.</b>
<code>search</code> already adapts, dropping the tap column and truncating at 60 columns —
<code>term_width()</code> existed and <code>discovery.py</code> was its only caller. Meanwhile
<code>boost --help</code>, the first thing a new user sees, emitted a fixed <b>102-column</b>
banner at every width. It now fits exactly at 60, 80 and 100. Command <em>names</em> are never
clipped, because the help's whole job is to be an index you can copy a command out of; summaries
and the tagline are. The version never is — it is what a bug report needs.

<b>Two findings were measured and deliberately left for their own items.</b> Eleven commands
still overflow 80 columns, but the remainder are prose hints, and the worst of them is one shared
string that six test files and a BDD feature pin by substring — wrapping it is a cross-cutting
output change, not a rider on this one. See <code>long-hints-overflow-narrow-panes</code> and
<code>bm25-has-no-stemming</code>.
