---
id: audit-missing-json-on-doctor-test-health-changelog-trending-log-ho
board: code
section: dx
status: planned
category: CLI · UX
complexity: M
impact: Med
wow: 1
note: doctor — the check CI would poll, mirrored by an MCP tool — offers only prose
order: 232
owner:
pr:
title: "Missing --json on <code>doctor</code>, <code>test</code>, <code>health</code>, <code>changelog</code>, <code>trending</code>, <code>log</code>, <code>hooks list</code> and friends; <code>bundle install</code> lacks --dry-run"
---
Eleven read-only reporting commands reject <code>--json</code> that their group siblings all have:
<code>doctor</code>, <code>test</code> (and <code>quarantine --list</code>), <code>health</code>,
<code>changelog</code>, <code>trending</code>, <code>log</code>, <code>hooks list</code>,
<code>clean</code>, <code>compact</code>, <code>context</code> (top-level &mdash;
<code>context status --json</code> works, bare <code>context</code> means status, yet
<code>context --json</code> is rejected) and <code>index</code>. Each prints
<em>"Error: unrecognized arguments: --json"</em> with exit 2, verified against positive controls
(<code>lint --json</code>, <code>context status --json</code> emit valid JSON). The sharpest cases:
<code>doctor</code> is the check CI would poll and the MCP server exposes a
<code>boost_doctor</code> tool, yet the CLI offers only prose; <code>test</code> is the command a CI
gate would parse; <code>log --json</code> is rejected while <code>pulse --json</code> works over the
same journal &mdash; and <code>log</code> also drops the <code>key=value</code> event fields pulse
shows. Separately but in the same sweep: <code>bundle install</code> has no <code>--dry-run</code>
although sibling <code>install</code> documents one, and bundle install taps registries, installs
skills <em>and can edit CLAUDE.md via rules</em> with no way to preview.

The fix is one consistency sweep, not new computation: each command already holds the facts &mdash;
emit them. <code>doctor</code>: <code>{checks: [{name, status, message, hint}], issues, verdict}</code>
with exit codes unchanged &middot; <code>test</code>: per-skill rows with failed checks &middot;
<code>health</code>: the kv dict plus status &middot; <code>changelog</code>/<code>log</code>: parsed
entries (<code>[{sha, date, author, subject}]</code> via a separator-based <code>--pretty</code>
format; journal events verbatim) &middot; <code>trending</code>: rows including <code>kind</code> so
rules/workflows are distinguishable &middot; <code>hooks list</code>: the
<code>cs.list_all_hooks</code> rows (host, scope, event, name, matcher, command, timeout) &middot;
<code>clean</code>/<code>compact</code>: the items list with path/kind/bytes plus totals &middot;
top-level <code>context --json</code> forwards to status. Add <code>--dry-run</code> to
<code>cmd_bundle</code> (skip <code>registry.add</code>/<code>store.install</code>, print what would
happen). New flags mean regenerating <code>docs/commands.html</code>; <code>README.md</code> and
<code>docs/DEBUGGING.md</code> mention doctor/health output and need a pass. Found by the 2026-08
CLI audit (cluster <code>missing-json-flags</code>); repro in the audit log.
