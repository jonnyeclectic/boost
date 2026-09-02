---
id: audit-install-dry-run-promises-agents-the-real-install-never-write
board: code
section: dx
status: shipped
category: CLI · Bug
complexity: S
impact: High
wow: 2
note: fixed — dry run now reads agents_for_scope/materializing_agents and plans the MCP action; PR awaiting CI (PyPI unreachable in the authoring sandbox, so make check needs CI's confirmation)
order: 209
owner: loop/install-dry-run-plan-gaps
pr: 704
title: "install <code>--dry-run</code> promises agents the real install never writes (antigravity-cli copy, antigravity materialize) and omits the MCP plan"
---
Three dry-run plans diverge from what install actually does. Project scope: <code>install
brainstorming --local --dry-run</code> prints five <em>"copy &rarr;"</em> lines including an
invented <code>&hellip;/antigravity-cli/skills/brainstorming</code> at the repo root; the real
install reports <em>"&#10003; copied into this repo &rarr; claude-code &middot; windsurf &middot;
cursor &middot; gemini"</em> and <code>find</code> shows four skills dirs, no
<code>antigravity-cli/</code>. Rules/workflows: the dry run says <em>"materialize &rarr; &hellip;
gemini &middot; antigravity"</em>, the real install materializes four (Antigravity reads GEMINI.md
via the gemini agent). And no dry run at either scope mentions MCP, though the real user-scope
install prompts <em>"register 1 server with Claude Code &middot; Antigravity CLI &hellip;?"</em>
and the real <code>--local</code> run writes <code>.mcp.json</code>.

Verified: the user-scope skill dry run is correct — the shipped
<em>dry-run-promised-a-link-nobody-makes</em> fix covered it — so the same class persisted
unshipped in the project-skill branch, the rule/workflow branch, and the missing MCP plan line.
The cause is which table each branch reads: <code>pkg.py:435</code> and
<code>pkg.py:419/452</code> iterate <code>agents.enabled_agents()</code>, while the real
installers iterate <code>agents.agents_for_scope</code> (<code>store.py:627</code>) and
<code>agents.materializing_agents</code> (<code>store.py:863</code>) — both helpers already exist
(<code>agents.py:82-100</code>).

Fix: derive dry-run targets from the installers' own tables — <code>agents.agents_for_scope(pbase)</code>
at <code>pkg.py:435</code>, <code>agents.materializing_agents</code> for the rule/workflow list at
<code>pkg.py:419/452</code> — and add one <code>mcp</code> plan line per declared server (via
<code>mcpdecl</code> on the entry's SKILL.md + sidecar) naming the scope-specific action: offer
<code>&lt;host&gt; mcp add</code> at user scope, record &rarr; <code>.mcp.json</code> at project
scope. Docs: note in <code>docs/roadmap/items/dry-run-promised-a-link-nobody-makes.md</code> that
the class persisted at project scope and for rules/workflows; no <code>docs/commands.html</code>
flag change.

Found by the 2026-08 CLI audit (cluster <code>install-dry-run-plan-gaps</code>); repro in the audit
log.
