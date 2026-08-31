---
id: audit-completions-findings
board: code
section: dx
status: planned
category: CLI · UX
complexity: M
impact: Low
wow: 1
note: TAB after `policy set ` offers nothing; unset $SHELL gets a bash script with no warning
order: 257
owner:
pr:
title: "boost completions: CLI audit findings (2026-08)"
---
<b>Generated completions never offer subcommand choices or policy keys.</b>
<code>__complete boost policy ""</code>, <code>… policy set ""</code>, <code>… schedule ""</code>
and <code>… completions ""</code> all exit 0 with zero output, while the controls work
(<code>… policy "--"</code> → <code>--json</code>; <code>… boost "poli"</code> →
<code>policy</code>). Verified broader than filed: every command with a static
<code>choices=</code> positional — <code>config</code>, <code>protocol</code>, <code>tag</code> too
— completes nothing, because <code>complete._source_for</code>
(<code>core/complete.py:123-161</code>) knows only catalog/installed/tap sources. Not a duplicate of
the shipped <code>completions-complete-only-command-names</code>: that item's scope was names +
flags, and the choices tuples are exact, so offering them contradicts nothing in
<code>complete.py:44-50</code>'s no-guessing rationale. Fix: scrape positional
<code>choices=(…)</code> tuples from the command source the way <code>_flags_for</code> scrapes
flags, with per-position sources so <code>policy set &lt;TAB&gt;</code> offers the
<code>policy.DEFAULTS</code> keys, degrading to nothing for non-literal choices. Found by the
2026-08 CLI audit (cluster <code>completions-choices</code>); repro in the audit log.

<br><br><b>Shell detection fails silently.</b> With <code>SHELL=/usr/local/bin/nu</code>,
<code>boost completions</code> prints the full <em>bash</em> script and bash install hint with no
warning; with <code>$SHELL</code> unset it still prints the bash script, and
<code>--install</code> errors with <em>"no one-shot install for&nbsp; yet"</em> — an empty shell
name and no mention that <code>$SHELL</code> is unset or that a shell can be passed positionally.
Root: <code>configuration.py:769</code> falls back to <code>"bash"</code> uncommented and
<code>:740</code> makes <code>detected</code> empty. Fix once at the detection site: error when
<code>detected</code> is empty ("cannot detect your shell ($SHELL unset) — pass bash, zsh or
fish"), warn before the bash fallback for a real unsupported shell, keep <code>_rc_path</code>'s
message for the install path. No doc changes beyond the follow-up note in the shipped completions
item. Found by the 2026-08 CLI audit (cluster <code>completions-shell-detection</code>); repro in
the audit log.
