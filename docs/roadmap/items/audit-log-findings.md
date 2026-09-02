---
id: audit-log-findings
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: "fix landed in cli.py + tests + DEBUGGING.md; PR's CI runs the full gate — sandbox network policy blocked local make check (PyPI unreachable)"
order: 275
owner: loop/cli-log-rc70
pr:
title: "boost log: CLI audit findings (2026-08)"
---
The diagnostic trail journals a crash code for exits that were fine. After
<code>boost edit --help</code> (real exit 0) and <code>boost edit</code> (a usage error, real exit 2),
<code>boost log --diagnostics</code> shows <em>&ldquo;WARNING boost: done: boost edit --help -&gt; rc=70 in
5ms&rdquo;</em> and <em>&ldquo;WARNING boost: done: boost edit -&gt; rc=70 in 4ms&rdquo;</em>. The mechanism is
exact: <code>cli.py:313</code> presets <code>rc=70</code> &ldquo;until a handler proves otherwise&rdquo;, argparse
raises <code>SystemExit</code>, and none of the except clauses at <code>cli.py:317-339</code> catch it (they
catch <code>Exception</code>; <code>SystemExit</code> derives from <code>BaseException</code>) &mdash; so the
<code>finally</code> at <code>cli.py:340-344</code> journals 70 at WARNING for every help and usage exit, while
<code>BoostError</code> and success runs log their true rc.

The trail's whole job (<code>docs/DEBUGGING.md:52-53</code>) is truthful rc lines, and this stamps the
one code reserved for genuine unexpected errors onto the most common benign exits &mdash; anyone grepping the
journal for real crashes wades through a WARNING per <code>--help</code>. Fix: in <code>cli.py</code>
<code>_run</code>, add <code>except SystemExit as e: rc = e.code if isinstance(e.code, int) else 1;
raise</code> before the <code>finally</code>, so completion logs the real exit and WARNING stays meaningful.
Update <code>docs/DEBUGGING.md</code> where it describes the trail. Found by the 2026-08 CLI audit
(cluster <code>log-records-rc70</code>); repro in the audit log.
