---
id: audit-declined-confirms-never-name-y-boost-assume-yes-snapshot-cle
board: code
section: dx
status: planned
category: CLI · UX
complexity: M
impact: Med
wow: 1
note: only 5 of the confirming parsers declare -y; BOOST_ASSUME_YES appears in 0 help texts
order: 224
owner:
pr:
title: "Declined confirms never name <code>-y</code>/<code>BOOST_ASSUME_YES</code>; snapshot, clean, infer/distill/absorb and sync reject <code>--yes</code>"
---
One pattern across seven commands. <code>snapshot restore</code>, piped without <code>BOOST_ASSUME_YES</code>: output is exactly <code>&nbsp;&nbsp;cancelled</code>, exit 0 &mdash; no prompt shown, no reason, no bypass named &mdash; and <code>snapshot restore ID --yes</code> answers <code>Error: unrecognized arguments: --yes</code> (exit 2). <code>clean --deep --yes</code> hits the same error, and its declined path claims <code>&#10003; nothing to clean</code> when a snapshot was in fact kept. <code>sync --prune</code> declined tells the user to run <code>boost sync --prune</code> &mdash; the command just run. <code>untap</code> and <code>bmad uninstall</code> print bare <code>cancelled</code>/<code>aborted</code> lines (bmad exits 0 with nothing removed); <code>infer -o</code>/<code>distill</code> abort with no hint and reject <code>--yes</code>. <code>BOOST_ASSUME_YES</code> appears in zero command help texts.

The mechanism makes it one fix, not seven: <code>out.confirm</code> (<code>boost_cli/core/output.py:788-806</code>) already honours <code>--yes</code>/<code>-y</code> off <code>sys.argv</code>, but argparse rejects the flag in every command that does not declare it &mdash; only five parsers do (<code>taps.py:181</code>, <code>configuration.py:605</code>, <code>bmad.py:106</code>, <code>pkg.py:522</code>, <code>pkg.py:990</code>) &mdash; so <code>docs/DEBUGGING.md:218</code>'s claim that <code>--yes</code>/<code>-y</code> auto-confirm is false for snapshot, clean, infer and sync. One narrowing from verification: <code>uninstall</code>'s silent non-TTY proceed is documented-deliberate (roadmap item <em>uninstall-has-no-confirmation-prompt</em> &mdash; non-TTY must not break CI callers), so only the missing hint stands there.

Fix, per the verified recommendation: add a shared cliparse <code>-y/--yes</code> option to the confirming parsers that lack it (snapshot, clean, infer/distill/absorb, sync); have <code>out.confirm</code>'s declined/non-TTY branch append <em>pass -y or set BOOST_ASSUME_YES=1</em> once so every caller inherits the hint; return 1 from destructive commands that declined; and stop <code>clean</code> printing <code>nothing to clean</code> when items were skipped. Docs: fix <code>docs/DEBUGGING.md</code> line 218, <code>docs/bmad.md</code>, and regenerate <code>docs/commands.html</code> after the new flags.

Found by the 2026-08 CLI audit (cluster <code>confirm-bypass-hints</code>); repro in the audit log. Verified against source 2026-08-31.
