---
id: audit-sync-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: "First sync run hides a blocked link; --diff prints it as a raw Python tuple"
order: 293
owner:
pr:
title: "boost sync: CLI audit findings (2026-08)"
---
<b>Repairing a missing store dir silently skips a blocked agent link — only a second run reports it.</b> With the store dir deleted and a foreign dir at <code>~/.windsurf/skills/brainstorming</code>: <code>sync --diff</code> showed only missing-store plus 4 stale links, nothing about windsurf; the first <code>sync</code> printed <em>"&#10003; reinstalled missing brainstorming from sickn33/antigravity-awesome-skills"</em> with no windsurf mention (the link was not created — lock agents ended as claude-code, cursor, antigravity); only a second <code>sync</code> said <em>"! 1 agent link could not be created: brainstorming &rarr; windsurf (~/.windsurf/skills/brainstorming in the way)…"</em>. Cause: <code>sync_plan</code> (<code>core/store.py:1471-1473</code>) <code>continue</code>s past link classification when the store dir is missing, and <code>sync_apply</code> (<code>store.py:1651</code>) discards <code>install()</code>'s <code>InstallResult</code>, whose <code>.conflicts</code> names the refused link. Surface those conflicts as blocked-link warnings and still classify agent links for a missing-store entry (or re-plan after repair). This is the residual missing-store case of the shipped fix — note it in <code>docs/roadmap/items/sync-reported-success-for-a-link-it-refused.md</code>. Unit test: missing store + foreign dir reported in one run.

<b><code>--diff</code> renders blocked links as a raw Python tuple, and the two modes disagree on formatting.</b> Observed: <em>"==&gt; agent links blocked by a foreign file (1)"</em> then <code>('brainstorming', 'windsurf', '/private/tmp/…/.windsurf/skills/brainstorming')</code> — <code>_PAIR_KEYS</code> (<code>commands/pkg.py:581-582</code>) covers only 2-tuples, so the 3-tuple falls to the <code>str()</code> else branch (<code>pkg.py:620-625</code>). Also apply says <em>"removed stale link /private/tmp/…/ghost"</em> where <code>--diff</code> shows <code>~/.claude/skills/ghost</code> (<code>store.py:1634</code> uses raw absolute paths), and <code>sync --diff --json</code> is indent=2 (<code>pkg.py:603</code>) while <code>sync --json</code> is one line (<code>pkg.py:660-662</code>). Fix in <code>cmd_sync</code>: a blocked_links branch printing <em>"brainstorming &rarr; windsurf (~/.windsurf/skills/brainstorming in the way)"</em>, <code>_tilde</code> paths in apply's action strings, one <code>json.dumps</code> style. No flag changes, so <code>docs/commands.html</code> needs no regeneration.

Found by the 2026-08 CLI audit (clusters <code>sync-blocked-link-report</code>, <code>sync-diff-formatting</code>); repro in the audit log.
