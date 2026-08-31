---
id: audit-root-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: Low
wow: 1
note: EPIPE exits 120 with stderr noise; `help version` suggests verify; launcher gates at 3.9
order: 245
owner:
pr:
title: "boost ROOT: CLI audit findings (2026-08)"
---
<b>EPIPE leaks past main's own handler.</b> <code>boost --help | (exec 0&lt;&amp;-; sleep 0.3)</code>
exits <b>120</b> with <em>&ldquo;Exception ignored on flushing sys.stdout: BrokenPipeError&rdquo;</em>
&mdash; 3/3 runs, and <code>count</code>, <code>taps</code> and <code>--version</code> leak the same way.
<code>cli.py:327-331</code> deliberately catches BrokenPipeError and returns 0, but stdout is never
flushed inside the try, so any output that fits the stdio buffer raises at interpreter exit &mdash; and
the <code>--help</code>/<code>--version</code> early returns (<code>cli.py:292-302</code>) sit before
the try with no handler at all. Fix: cover the early returns, flush <code>sys.stdout</code> inside the
try, and <code>os.dup2</code> a devnull fd over stdout in the handler so the exit flush cannot raise.

<br><br><b>Help routing rejects main's own aliases.</b> <code>boost help --help</code> &rarr;
<em>&ldquo;unknown command: --help / hint: did you mean: heal?&rdquo;</em> exit 2;
<code>boost help version</code> suggests <em>verify</em> while <code>boost version</code> works;
even <code>boost help help</code> fails. The aliases live only in <code>cli.main</code>
(<code>cli.py:292-302</code>) and <code>print_command_help</code> resolves against COMMANDS alone,
then difflib-guesses any token &mdash; dash-prefixed ones included. And <code>boost --help</code>
documents none of the working global flags (<code>-V</code>/<code>-v</code>/<code>--debug</code>/<code>-q</code>).
Fix: short-circuit the aliases in <code>print_command_help</code> before difflib, say
<em>unknown option</em> for dash tokens in <code>_unknown</code> (<code>cli.py:231-236</code>), and add
one dim Options line under Usage in <code>print_help</code>.

<br><br><b>The <code>./boost</code> launcher still gates at Python 3.9</b> &mdash; tuple
(<code>boost:27</code>), hint text (<code>boost:37</code>) and header comment (<code>boost:5</code>) all
say 3.9+ while <code>pyproject.toml:22</code> requires <code>&gt;=3.12</code>. On a stock macOS whose
only <code>python3</code> is 3.9 the launcher selects it and the user gets a SyntaxError from
<code>core/workflows.py</code>'s match statements instead of the friendly hint. The shipped
<em>python-floor-moves-to-312</em> item enumerated every floor touchpoint and missed this one. Fix:
bump all three sites to 3.12 and add a unit test pinning the launcher's floor to
<code>requires-python</code>. README already says 3.12+ &mdash; no doc change needed; none of the three
fixes touches a COMMANDS row, so <code>docs/commands.html</code> is unaffected.

<br><br>Found by the 2026-08 CLI audit (clusters <code>broken-pipe-exit</code>,
<code>help-routing-aliases</code>, <code>launcher-python-floor</code>); repro in the audit log.
