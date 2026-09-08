---
id: audit-protocol-findings
board: code
section: dx
status: shipped
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: macOS status reads "registered" though register never calls Launch Services
order: 282
owner: loop/protocol-audit-findings
pr: 800
title: "<code>boost protocol</code>: CLI audit findings (2026-08)"
---
<b><code>protocol status</code> on macOS reads as registered when only the handler script exists.</b> Verified on real Darwin: <code>protocol register</code> writes only <code>~/.boost/state/boost-protocol-handler.sh</code> plus four manual Automator steps — no Launch Services or URL-scheme call (<code>team.py:433-467</code>) — yet <code>status</code> then prints <code>handler  ~/.boost/state/boost-protocol-handler.sh</code> in the same slot whose negative form reads <code>handler  not registered</code>. Presence reads as "registered", but a <code>boost://</code> link in a browser does nothing until the user builds Boost.app. Fixed: on Darwin, <code>status</code> now prints the script path under a distinct <code>script</code> key and a separate <code>registered</code> key that always reads "no — build Boost.app (see <code>boost protocol register</code>)" — the platform simply has no automatic path to yes. Other platforms keep the original <code>handler</code>/"not registered" pair, which was already accurate for them. No flag text changed, so <code>docs/commands.html</code> needed no regeneration, and README.md does not describe one-click install on macOS.<br><br><b><code>protocol open boost://install/…</code> bypasses install's reporting and <code>via=</code> journaling.</b> Reproduced: the install verb prints three bare lines — no summary box, no Gemini line, no quality score — and <code>pulse -n 2</code> shows the install event with only <code>tap=</code>/<code>version=</code> extras, no <code>via=protocol</code>. Fixed: <code>store.install</code> (and the three kind-specific installers it dispatches to) now takes an optional <code>via</code> kwarg threaded straight to its <code>journal.log</code> call, the same way <code>registry.add</code> already tags a tap event; the protocol-open install branch passes <code>via="protocol"</code> and reports through <code>pkg._report_result</code> — the same helper <code>cmd_install</code> uses — instead of hand-rolling three lines, so it now also gets the Gemini "available to" line, conflict/injection/secret warnings, and an MCP offer, plus a quality-score line for skills.<br><br>Found by the 2026-08 CLI audit (clusters <code>protocol-darwin-status</code>, <code>protocol-install-parity</code>); repro in the audit log.
