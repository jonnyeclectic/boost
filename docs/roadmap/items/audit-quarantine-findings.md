---
id: audit-quarantine-findings
board: code
section: health
status: shipped
category: Safety · Bug
complexity: S
impact: Med
wow: 2
note: release now preserves only_agents and restores a CLAUDE.md block at its original position
order: 284
owner: loop/audit-quarantine-findings
pr: 762
title: "<code>boost quarantine --release</code>: CLI audit findings (2026-08)"
---
<b>Release ignores the skill's <code>only_agents</code> scope and links into every enabled agent.</b> Reproduced: <code>install pdf-official --agent claude-code</code> creates one link; quarantine then <code>--release</code> prints <code>✓ released pdf-official (linked: claude-code, windsurf, cursor, antigravity)</code> — links in all four agent dirs while <code>only_agents</code> still says <code>[claude-code]</code> — and <code>doctor</code> immediately flags the out-of-scope links and exits 1. The round trip should be a no-op on the agent set. Root cause is one missing argument: the release branch calls <code>store.link_agents(name)</code> with no <code>only=</code> (<code>boost_cli/commands/safety.py:471-478</code>), where <code>store.install</code> already passes the preserved scope correctly (<code>store.py:555</code>). Fix: <code>store.link_agents(name, only=entry.get("only_agents"))</code>, keep <code>entry["agents"]</code> consistent with the narrowed set, and add a unit test that installs with <code>--agent</code>, quarantines, releases, and asserts doctor stays clean. Same defect class as the shipped <em>update/reinstall widens agent scope</em> fix — this is the path that sweep missed.<br><br><b>Releasing a quarantined <em>rule</em> re-appends the managed block, reordering the user's own CLAUDE.md text above it.</b> Reproduced: with 3 user lines after the 865-line managed block, quarantine strips the block and keeps the user text (good), but <code>--release dotnet-build</code> restores the file to 868 lines with the user's lines now at the <em>top</em> and the block appended below — though <code>release_materialized</code>'s docstring promises byte-for-byte restore. <code>release_materialized</code> (<code>store.py:1029-1055</code>) hands the post-quarantine file to <code>rules.merge_block</code> (<code>rules.py:112-132</code>), which finds no existing block and unconditionally appends. Fix: record the block's original offset (or the full pre-quarantine text) in the quarantine stash for MODE_CLAUDE materializations and reinsert at that position, falling back to append only when the surrounding text changed — or soften the docstring to say the block is re-appended.<br><br>Found by the 2026-08 CLI audit (clusters <code>release-widens-agent-scope</code>, <code>rule-release-block-position</code>); repro in the audit log.
