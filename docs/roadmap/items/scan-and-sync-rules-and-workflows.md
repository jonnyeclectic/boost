---
id: scan-and-sync-rules-and-workflows
board: code
section: internals
status: inflight
category: Install engine · Safety
complexity: M
impact: Med
wow: 2
note: close the last skill-only gaps for rules/workflows
order: 26
owner: loop/scan-sync-all-kinds
pr:
title: Scan and <code>sync</code> rules/workflows like skills
---
Two skill-only gaps remained after rule (<code>#141</code>) / workflow
           (<code>#150</code>) install: the install-time injection + secret scan
           read <code>res.dest/SKILL.md</code>, which doesn't exist for a
           rule/workflow (a single file / merged block), so their executable
           Markdown went unscanned; and <code>boost sync</code> only reconciled
           skills, so a deleted rule/workflow materialization couldn't be
           repaired. Fix both: carry the raw source on the install result
           (<code>scan_text</code>) so injectscan/secretscan see exactly what was
           installed, and extend <code>sync_plan</code>/<code>sync_apply</code>
           with a <code>missing_materializations</code> pass that re-materializes
           a rule/workflow from its tap when a drop file or CLAUDE.md block is
           gone — mirroring the missing-store-dir repair for skills.
