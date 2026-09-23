---
id: import-budget-gate-passes-when-boost-cannot-import
board: code
section: planned
status: shipped
category: CI · Bug
complexity: S
impact: Medium
wow: 3
note: A required check that asserts a name is absent, and reports OK when nothing ran at all…
order: 335
owner: loop/import-budget-exit-code
title: The import-budget gate reports OK when the command it measures never ran
---
<b>Found by the audit of the repo's own automation.</b> <code>scripts/import_budget.py</code>'s
<code>imported_modules()</code> runs <code>python -X importtime -c 'from boost_cli.cli import main;
main([...])'</code> in a subprocess and parses <code>proc.stderr</code>, discarding
<code>proc.returncode</code>. If that subprocess dies — a broken <code>boost_cli.cli</code> import, a
command removed from <code>COMMANDS</code>, a crash inside argument parsing — the stderr it did emit
names no denylisted module, <code>leaks_for()</code> returns nothing, and the script prints
<code>import-budget: OK</code> and exits 0.
<br><br>
Measured: pointing the script's <code>ROOT</code> at a directory holding no <code>boost_cli</code> at
all still printed <code>import-budget: OK — no heavy/optional module imported by 4 common
commands</code> and returned 0. It is a required check on every pull request
(<code>ci.yml</code>'s <code>lint</code> job), and the assertion it exists to make is a
<i>name is absent</i> assertion, which is exactly the shape that passes vacuously when nothing runs.
The realistic harm is the partial case: one measured command starts failing early, is silently no
longer measured, and a top-level <code>sqlite_vec</code> or <code>dense</code> import added after
that point is never seen again.
<br><br>
<b>Fix.</b> Fail on a non-zero return code, naming the command and its stderr, and assert each
measured command produced a plausible module count rather than an empty parse.
