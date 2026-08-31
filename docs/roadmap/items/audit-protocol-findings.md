---
id: audit-protocol-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: macOS status reads "registered" though register never calls Launch Services
order: 282
owner:
pr:
title: "<code>boost protocol</code>: CLI audit findings (2026-08)"
---
<b><code>protocol status</code> on macOS reads as registered when only the handler script exists.</b> Verified on real Darwin: <code>protocol register</code> writes only <code>~/.boost/state/boost-protocol-handler.sh</code> plus four manual Automator steps — no Launch Services or URL-scheme call (<code>team.py:433-467</code>) — yet <code>status</code> then prints <code>handler  ~/.boost/state/boost-protocol-handler.sh</code> in the same slot whose negative form reads <code>handler  not registered</code>. Presence reads as "registered", but a <code>boost://</code> link in a browser does nothing until the user builds Boost.app. Fix (<code>boost_cli/commands/team.py:482-498</code>): on Darwin print the script path under a distinct <code>script</code> key and a separate <code>registered</code> key defaulting to "no — build Boost.app (see <code>boost protocol register</code>)". Update the protocol entry in <code>docs/commands.html</code> (regenerate; no flag change) and README.md if it describes one-click install on macOS.<br><br><b><code>protocol open boost://install/…</code> bypasses install's reporting and <code>via=</code> journaling.</b> Reproduced: the install verb prints three bare lines — no summary box, no Gemini line, no quality score — and <code>pulse -n 2</code> shows the install event with only <code>tap=</code>/<code>version=</code> extras, no <code>via=protocol</code>. The asymmetry sits inside one function: the tap branch adds <code>journal.log(..., via='protocol')</code> (<code>team.py:429</code>) while the install branch (<code>team.py:406-414</code>) hand-rolls its output and <code>store.install</code>'s journal call (<code>store.py:587</code>) takes no via kwarg. Route the install branch through the reporting helper <code>pkg.cmd_install</code> uses and thread an optional <code>via</code> kwarg to the journal call so one-click installs can be told apart the way taps already are.<br><br>Found by the 2026-08 CLI audit (clusters <code>protocol-darwin-status</code>, <code>protocol-install-parity</code>); repro in the audit log.
