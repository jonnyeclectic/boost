---
id: audit-import-all-skips-the-injection-secret-scans-and-the-per-skil
board: code
section: health
status: inflight
category: Safety · Bug
complexity: S
impact: High
wow: 2
note: a skill flagged "moves credentials off the machine" imports via --all with zero warnings
order: 208
owner: loop/import-all-scan-parity
pr:
title: "import <code>--all</code> skips the injection/secret scans and the per-skill report single import runs"
---
Importing one skill runs the safety report: <code>import fx/sketchy/beta</code> prints <em>"! beta:
2 suspicious patterns in SKILL.md (high) — review before use"</em>, <em>"L7 [high] moves
credentials/secrets off the machine"</em>, <em>"! beta: 1 possible secret &hellip; L8 [high] AWS
access key id"</em>. The batch path does not: <code>import fx/sketchy --all</code> on the same
fixtures prints only <em>"&#10003; imported beta v0.1.0 (score 65/100)"</em> — zero warnings, no
linked-agents line, exit 0. Verified on a fresh home; the single, single-in-dir and
<code>--name</code> paths all warn correctly, so the hole is exactly the <code>--all</code> branch.

The cause is one loop: <code>pkg.py:1395-1411</code> calls <code>store.install_from_path</code> +
<code>out.ok</code> only, while every other import path goes through <code>_report_result</code>,
which runs <code>_warn_injection</code>/<code>_warn_secrets</code>. Same class as the shipped
<em>mcp-install-skips-the-injection-scan</em> card — that covered the MCP tool, this is the CLI's
own batch path. The report-shape divergence (no agents named, "imported" capitalised differently)
is the same root.

Fix: route the <code>--all</code> loop through <code>_report_result</code> (keeps the per-item
try/except contract and fixes the report shape too), or at minimum call
<code>_warn_injection(res)</code>/<code>_warn_secrets(res)</code> after each
<code>install_from_path</code> in <code>_import_root</code>. Add a functional test importing a
fixture with an injection line via <code>--all</code> and asserting the warning. No doc changes
(no summary or flag change).

Found by the 2026-08 CLI audit (cluster <code>import-all-parity</code>); repro in the audit log.
